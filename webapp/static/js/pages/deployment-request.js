(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environments = pageData.environments || [];
    const deploymentTargets = pageData.deploymentTargets || [];
    const deploymentMode = pageData.mode || "standard";
    const serverTimezone = pageData.serverTimezone || "UTC";
    const reservationPolicy = pageData.reservationPolicy || {};
    const mutualReservationEnabled = !!reservationPolicy.mutual_env_reservation_enabled;
    const deploymentReservationWindowMinutes = Math.max(
        1,
        parseInt(reservationPolicy.deployment_reservation_window_minutes || 60, 10)
    );

    function showFormMessage(message, type) {
        common.setInlineMessage({
            messageId: "formMessage",
            textId: "formMessageText",
            message: message,
            type: type || "muted",
        });
    }

    function isEnvScopedReservation(payload) {
        return payload &&
            payload.env_id &&
            payload.deployment_request &&
            payload.deployment_request.env_scope_type === "ENV";
    }

    function getDeploymentWindow(payload) {
        const start = payload && payload.planned_start_time ? new Date(payload.planned_start_time) : null;
        if (!start || Number.isNaN(start.getTime())) {
            return { start: null, end: null };
        }
        return {
            start: start,
            end: new Date(start.getTime() + (deploymentReservationWindowMinutes * 60 * 1000)),
        };
    }

    function updatePolicyHint() {
        if (!mutualReservationEnabled) {
            return;
        }
        if (deploymentMode === "tools") {
            showFormMessage("Tool deployments target the configured server role for the selected environment and are checked against existing bookings.", "muted");
            return;
        }
        showFormMessage(
            "Env-scoped deployment requests reserve " +
            deploymentReservationWindowMinutes +
            " minute(s) and are checked against existing bookings.",
            "muted"
        );
    }

    function populateTargetOptions() {
        const targetSelect = document.getElementById("formTargetKey");
        const targetDebug = document.getElementById("targetDebug");
        if (deploymentMode === "tools") {
            targetSelect.innerHTML = '<option value="TOOLS">Tools</option>';
            targetSelect.value = "TOOLS";
            if (targetDebug) {
                targetDebug.textContent = "Tools deployment target loaded.";
            }
            return;
        }
        if (targetSelect.options.length > 1) {
            if (targetDebug) {
                targetDebug.textContent = "Loaded " + Math.max(targetSelect.options.length - 1, 0) + " targets.";
            }
            return;
        }

        const currentValue = targetSelect.value;
        targetSelect.innerHTML = '<option value="">Select deployment target...</option>';
        deploymentTargets.forEach(function (target) {
            targetSelect.insertAdjacentHTML(
                "beforeend",
                '<option value="' + common.escapeHtml(target.target_key) + '">' +
                common.escapeHtml(target.display_name) +
                "</option>"
            );
        });
        if (currentValue) {
            targetSelect.value = currentValue;
        }

        if (targetDebug) {
            const names = deploymentTargets.map(function (target) {
                return target.display_name;
            }).join(", ");
            targetDebug.textContent = names
                ? "Loaded " + deploymentTargets.length + " targets: " + names
                : "Loaded 0 targets.";
        }
    }

    function getTargetByKey(targetKey) {
        return deploymentTargets.find(function (target) {
            return target.target_key === targetKey;
        }) || null;
    }

    function getSelectedPackageConfig() {
        const target = getTargetByKey(document.getElementById("formTargetKey").value);
        const selectedPackageKey = document.getElementById("formComponentNames").value;
        if (!target || !selectedPackageKey) {
            return null;
        }
        return (target.packages || []).find(function (pkg) {
            return pkg.package_key === selectedPackageKey;
        }) || null;
    }

    function populateEnvOptions(envType) {
        common.populateEnvironmentOptions({
            selectId: "formEnvId",
            environments: environments,
            envType: envType,
        });
    }

    function syncToolScopeFields() {
        if (deploymentMode !== "tools") {
            return;
        }
        const scopeType = document.getElementById("formScopeType").value;
        const envIdGroup = document.getElementById("formEnvIdGroup");
        const envTypeGroup = document.getElementById("formEnvTypeGroup");
        const envIdSelect = document.getElementById("formEnvId");
        const envTypeSelect = document.getElementById("formEnvType");

        envIdGroup.style.display = scopeType === "ENV" ? "block" : "none";
        envTypeGroup.className = scopeType === "ENV" ? "col-md-6" : "col-md-12";
        envIdSelect.required = scopeType === "ENV";
        envTypeSelect.required = true;
    }

    function syncToolScopeAvailability() {
        if (deploymentMode !== "tools") {
            return;
        }

        const scopeSelect = document.getElementById("formScopeType");
        const envTypeOption = Array.from(scopeSelect.options).find(function (option) {
            return option.value === "ENV_TYPE";
        });
        const envOption = Array.from(scopeSelect.options).find(function (option) {
            return option.value === "ENV";
        });
        const selectedPackage = getSelectedPackageConfig();
        const supportedScopes = selectedPackage && selectedPackage.supported_scopes
            ? selectedPackage.supported_scopes
            : ["ENV", "ENV_TYPE"];

        if (envTypeOption) {
            envTypeOption.disabled = supportedScopes.indexOf("ENV_TYPE") === -1;
        }
        if (envOption) {
            envOption.disabled = supportedScopes.indexOf("ENV") === -1;
        }

        if (scopeSelect.value === "ENV_TYPE" && supportedScopes.indexOf("ENV_TYPE") === -1) {
            scopeSelect.value = "ENV";
        } else if (scopeSelect.value === "ENV" && supportedScopes.indexOf("ENV") === -1) {
            scopeSelect.value = "ENV_TYPE";
        }

        syncToolScopeFields();
    }

    function resetServiceSelections() {
        const serviceTypes = document.getElementById("formServiceTypes");
        if (!serviceTypes) {
            return;
        }
        Array.from(serviceTypes.options).forEach(function (option) {
            option.selected = false;
        });
    }

    function loadDeploymentOptions() {
        const targetKey = document.getElementById("formTargetKey").value;
        const target = getTargetByKey(targetKey);
        const versionSelect = document.getElementById("formVersion");
        const componentNames = document.getElementById("formComponentNames");
        const serviceTypesGroup = document.getElementById("formServiceTypesGroup");
        const testingMode = document.getElementById("formTestingMode");

        versionSelect.innerHTML = '<option value="">Select version...</option>';
        componentNames.innerHTML = '<option value="">Select package...</option>';
        if (serviceTypesGroup) {
            serviceTypesGroup.style.display = targetKey === "TCS_APP" ? "block" : "none";
        }
        if (testingMode) {
            testingMode.required = targetKey === "TCS_APP";
        }

        if (targetKey !== "TCS_APP") {
            if (testingMode) {
                testingMode.value = "";
            }
            resetServiceSelections();
        }

        if (!target) {
            versionSelect.innerHTML = '<option value="">Select deployment target first...</option>';
            return;
        }

        if (target.allow_multiple_packages && (target.packages || []).length > 1) {
            componentNames.insertAdjacentHTML("beforeend", '<option value="all">all</option>');
        }

        (target.packages || []).forEach(function (pkg) {
            const scopes = (pkg.supported_scopes || []).join("/");
            const label = pkg.package_key +
                " (" + (pkg.server_role_key || "-") + ")" +
                (scopes ? " [" + scopes + "]" : "");
            componentNames.insertAdjacentHTML(
                "beforeend",
                '<option value="' + common.escapeHtml(pkg.package_key) + '">' +
                common.escapeHtml(label) +
                "</option>"
            );
        });

        if ((target.packages || []).length === 1 && !target.allow_multiple_packages) {
            componentNames.value = target.packages[0].package_key;
        }

        syncToolScopeAvailability();

        if (componentNames.value) {
            loadVersionOptions();
        } else {
            versionSelect.innerHTML = '<option value="">Select target package first...</option>';
        }
    }

    function loadVersionOptions() {
        const targetKey = document.getElementById("formTargetKey").value;
        const selectedPackage = document.getElementById("formComponentNames").value;
        const versionSelect = document.getElementById("formVersion");

        versionSelect.innerHTML = '<option value="">Select version...</option>';
        if (!targetKey) {
            versionSelect.innerHTML = '<option value="">Select deployment target first...</option>';
            return;
        }

        if (!selectedPackage) {
            versionSelect.innerHTML = '<option value="">Select target package first...</option>';
            return;
        }

        versionSelect.innerHTML = '<option value="">Loading versions...</option>';
        const params = new URLSearchParams({ target_key: targetKey });
        if (targetKey === "TOOLS" && selectedPackage) {
            params.set("package_key", selectedPackage);
        }

        common.fetchJson("/api/component-versions?" + params.toString(), { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to load versions");
                }

                versionSelect.innerHTML = '<option value="">Select version...</option>';
                (result.data.versions || []).forEach(function (version) {
                    versionSelect.insertAdjacentHTML(
                        "beforeend",
                        '<option value="' + common.escapeHtml(version) + '">' +
                        common.escapeHtml(version) +
                        "</option>"
                    );
                });
            })
            .catch(function () {
                versionSelect.innerHTML = '<option value="">Select version...</option>';
            });
    }

    function getDeploymentRequestPayload() {
        const startValue = document.getElementById("formStartTime").value;
        const targetKey = document.getElementById("formTargetKey").value;
        const selectedPackage = document.getElementById("formComponentNames").value;
        return {
            env_id: deploymentMode === "tools" && document.getElementById("formScopeType").value === "ENV_TYPE"
                ? ""
                : document.getElementById("formEnvId").value,
            requested_env_type: document.getElementById("formEnvType").value,
            planned_start_time: startValue ? new Date(startValue).toISOString() : "",
            description: document.getElementById("formDescription").value.trim(),
            user_timezone: common.getUserTimezone(serverTimezone),
            deployment_request: {
                target_key: targetKey,
                env_scope_type: deploymentMode === "tools"
                    ? document.getElementById("formScopeType").value
                    : "ENV",
                requested_version: document.getElementById("formVersion").value.trim(),
                testing_mode: targetKey === "TCS_APP" ? document.getElementById("formTestingMode").value : "",
                package_keys: selectedPackage ? [selectedPackage] : [],
                service_types: targetKey === "TCS_APP"
                    ? Array.from(document.getElementById("formServiceTypes").selectedOptions).map(function (opt) {
                        return opt.value;
                    })
                    : [],
            },
        };
    }

    function validateDeploymentRequest(payload) {
        if (!payload.planned_start_time) {
            return "Planned start time is required.";
        }
        if (deploymentMode === "tools") {
            if (!payload.requested_env_type) {
                return "Environment type is required.";
            }
            if (payload.deployment_request.env_scope_type === "ENV" && !payload.env_id) {
                return "Specific environment is required for environment-scoped tool deployments.";
            }
        } else if (!payload.env_id) {
            return "Environment is required.";
        }
        const deployment = payload.deployment_request;
        if (!deployment.target_key) {
            return "Deployment target is required.";
        }
        if (!deployment.package_keys || !deployment.package_keys.length) {
            return "Target package is required.";
        }
        if (!deployment.requested_version) {
            return "Build/version is required.";
        }
        if (deployment.target_key === "TCS_APP" && !deployment.testing_mode) {
            return "Testing mode is required.";
        }
        return null;
    }

    function checkBookingConflict(payload) {
        if (!mutualReservationEnabled || !isEnvScopedReservation(payload)) {
            return Promise.resolve(null);
        }

        const deploymentWindow = getDeploymentWindow(payload);
        if (!deploymentWindow.start || !deploymentWindow.end) {
            return Promise.resolve(null);
        }

        return common.fetchJson("/api/bookings", { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to validate environment availability.");
                }

                const bookings = Array.isArray(result.data) ? result.data : [];
                return bookings.find(function (item) {
                    if (!item || item.is_standalone_deployment_request) {
                        return false;
                    }
                    if (item.env_id !== payload.env_id || item.lifecycle_status === "cancelled") {
                        return false;
                    }

                    const start = new Date(item.start_time);
                    const end = new Date(item.end_time);
                    return deploymentWindow.start < end && deploymentWindow.end > start;
                }) || null;
            });
    }

    function resetFormState() {
        document.getElementById("deploymentRequestForm").reset();
        const serviceTypesGroup = document.getElementById("formServiceTypesGroup");
        const testingMode = document.getElementById("formTestingMode");
        if (serviceTypesGroup) {
            serviceTypesGroup.style.display = "none";
        }
        if (testingMode) {
            testingMode.required = false;
        }
        common.resetSelect("formVersion", "Select version...");
        common.resetSelect("formComponentNames", "Select package...");
        populateEnvOptions("");
        if (deploymentMode === "tools") {
            document.getElementById("formTargetKey").value = "TOOLS";
            document.getElementById("formScopeType").value = "ENV_TYPE";
            syncToolScopeFields();
        }
    }

    function handleDeploymentSubmit(event) {
        event.preventDefault();
        const payload = getDeploymentRequestPayload();
        const error = validateDeploymentRequest(payload);

        if (error) {
            showFormMessage(error, "danger");
            return;
        }

        checkBookingConflict(payload)
            .then(function (conflictingBooking) {
                if (conflictingBooking) {
                    showFormMessage(
                        "This environment already has booking " +
                        conflictingBooking.booking_id +
                        " in the requested deployment window.",
                        "danger"
                    );
                    return null;
                }

                return common.fetchJson("/api/deployment-requests", {
                    method: "POST",
                    credentials: "include",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                });
            })
            .then(function (result) {
                if (!result) {
                    return;
                }
                if (!result.ok) {
                    showFormMessage(result.data.error || "Deployment request failed. Please try again.", "danger");
                    return;
                }
                const requestData = result.data.deployment_request || {};
                showFormMessage(
                    "Deployment request submitted successfully. Status: " + (requestData.status || "OPEN") + ".",
                    "success"
                );
                resetFormState();
            })
            .catch(function () {
                showFormMessage("Unable to reach the booking service.", "danger");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("formEnvType").addEventListener("change", function () {
            populateEnvOptions(this.value);
        });
        if (deploymentMode === "tools") {
            document.getElementById("formScopeType").addEventListener("change", syncToolScopeFields);
        }
        document.getElementById("formTargetKey").addEventListener("change", loadDeploymentOptions);
        document.getElementById("formComponentNames").addEventListener("change", function () {
            syncToolScopeAvailability();
            loadVersionOptions();
        });
        document.getElementById("deploymentRequestForm").addEventListener("submit", handleDeploymentSubmit);

        populateTargetOptions();
        populateEnvOptions("");
        const serviceTypesGroup = document.getElementById("formServiceTypesGroup");
        const testingMode = document.getElementById("formTestingMode");
        if (serviceTypesGroup) {
            serviceTypesGroup.style.display = "none";
        }
        if (testingMode) {
            testingMode.required = false;
        }
        if (deploymentMode === "tools") {
            syncToolScopeFields();
            loadDeploymentOptions();
        }
        updatePolicyHint();
    });
}());
