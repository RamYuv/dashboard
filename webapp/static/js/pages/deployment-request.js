(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environments = pageData.environments || [];
    const environmentServerMappings = pageData.environmentServerMappings || [];
    const deploymentTargets = pageData.deploymentTargets || [];
    const deploymentMode = pageData.mode || "standard";
    const serverTimezone = pageData.serverTimezone || "UTC";
    const reservationPolicy = pageData.reservationPolicy || {};
    const mutualReservationEnabled = !!reservationPolicy.mutual_env_reservation_enabled;
    const deploymentReservationWindowMinutes = Math.max(
        1,
        parseInt(reservationPolicy.deployment_reservation_window_minutes || 60, 10)
    );
    let deploymentSuccessToast = null;

    function showFormMessage(message, type) {
        common.setInlineMessage({
            messageId: "formMessage",
            textId: "formMessageText",
            message: message,
            type: type || "muted",
        });
    }

    function showDeploymentSuccessToast(message) {
        const toastBody = document.getElementById("deploymentSuccessToastBody");
        if (toastBody) {
            toastBody.textContent = message;
        }
        if (deploymentSuccessToast) {
            deploymentSuccessToast.show();
        }
    }

    function applyDefaultStartTime(force) {
        common.populateTimeSlotOptions({
            selectId: "formStartTime",
            placeholder: "Select time...",
            selectedValue: document.getElementById("formStartTime") ? document.getElementById("formStartTime").value : "",
            slotMinutes: 30,
        });

        const startInput = document.getElementById("formStartTime");
        const startDateInput = document.getElementById("formStartDate");
        if (startInput && startDateInput && (force || !startInput.value || !startDateInput.value)) {
            const startSlot = common.buildLocalDateTimeParts({ slotMinutes: 30, roundUp: true });
            startDateInput.value = startSlot.date;
            startInput.value = startSlot.time;
        }
    }

    function applyDateRestrictions() {
        common.applyMinDate("formStartDate");
    }

    function showPastTimePopup() {
        window.alert("Previous time is not allowed.");
    }

    function validateDateNotInPast() {
        return common.validateNoPastDate("formStartDate", function () {
            showFormMessage("Previous booking date is not allowed.", "danger");
            window.alert("Previous booking date is not allowed.");
        });
    }

    function validateTimeNotInPast() {
        return common.validateNoPastDateTime("formStartDate", "formStartTime", function () {
            showFormMessage("Previous time is not allowed.", "danger");
            showPastTimePopup();
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
        if (deploymentMode === "tools") {
            showFormMessage("Tool deployments use a tool environment, tool name, requested version, and configured tool server.", "muted");
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
        if (!targetSelect) {
            return;
        }
        if (deploymentMode === "tools") {
            targetSelect.innerHTML = '<option value="TOOLS">Tools</option>';
            targetSelect.value = "TOOLS";
            return;
        }
        if (targetSelect.options.length > 1) {
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

    }

    function getTargetByKey(targetKey) {
        return deploymentTargets.find(function (target) {
            return target.target_key === targetKey;
        }) || null;
    }

    function getSelectedTargetKey() {
        return deploymentMode === "tools"
            ? "TOOLS"
            : document.getElementById("formTargetKey").value;
    }

    function getSelectedToolKey() {
        const toolField = document.getElementById("formToolKey");
        return toolField ? toolField.value : "";
    }

    function populateToolOptions() {
        const toolSelect = document.getElementById("formToolKey");
        if (!toolSelect) {
            return;
        }

        const toolsTarget = getTargetByKey("TOOLS");
        const packages = (toolsTarget && toolsTarget.packages) || [];
        toolSelect.innerHTML = '<option value="">Select tool...</option>';
        packages.forEach(function (tool) {
            const toolKey = tool.package_key || "";
            if (!toolKey) {
                return;
            }
            toolSelect.insertAdjacentHTML(
                "beforeend",
                '<option value="' + common.escapeHtml(toolKey) + '">' +
                common.escapeHtml((tool.build_name || tool.package_name || toolKey).toUpperCase()) +
                "</option>"
            );
        });
    }

    function populateEnvOptions(envType) {
        common.populateEnvironmentOptions({
            selectId: "formEnvId",
            environments: environments,
            envType: deploymentMode === "tools" ? "" : envType,
        });
    }

    function resetServiceSelections() {
        const tcsService = document.getElementById("formTcsService");
        if (!tcsService) {
            return;
        }
        tcsService.value = "";
    }

    function getServerMappingsForSelection() {
        const envId = document.getElementById("formEnvId").value;
        const targetKey = getSelectedTargetKey();
        if (!envId || !targetKey) {
            return [];
        }
        return environmentServerMappings.filter(function (mapping) {
            return mapping.env_id === envId && mapping.target_key === targetKey;
        });
    }

    function populateServerMappingOptions() {
        const serverSelect = document.getElementById("formServerMappings");
        const mappings = getServerMappingsForSelection();
        const targetKey = getSelectedTargetKey();
        serverSelect.innerHTML = "";
        if (!document.getElementById("formEnvId").value || !getSelectedTargetKey()) {
            serverSelect.innerHTML = deploymentMode === "tools"
                ? '<option value="">Select environment first...</option>'
                : '<option value="">Select environment and target first...</option>';
            return;
        }
        if (!mappings.length) {
            serverSelect.innerHTML = '<option value="">No configured servers found for this environment and target...</option>';
            return;
        }
        if (deploymentMode !== "tools" && mappings.length > 1) {
            serverSelect.insertAdjacentHTML(
                "beforeend",
                '<option value="ALL">ALL</option>'
            );
        }
        mappings.forEach(function (mapping) {
            serverSelect.insertAdjacentHTML(
                "beforeend",
                '<option value="' + common.escapeHtml(String(mapping.environment_host_mapping_id)) + '">' +
                common.escapeHtml(mapping.display_label || mapping.hostname || mapping.server_type_key || String(mapping.environment_host_mapping_id)) +
                "</option>"
            );
        });
    }

    function loadDeploymentOptions() {
        const targetKey = getSelectedTargetKey();
        const target = getTargetByKey(targetKey);
        const versionSelect = document.getElementById("formVersion");
        const serviceTypesGroup = document.getElementById("formTcsServicesGroup");
        const testingMode = document.getElementById("formTestingMode");

        versionSelect.innerHTML = '<option value="">Select version...</option>';
        populateServerMappingOptions();
        if (serviceTypesGroup) {
            serviceTypesGroup.style.display = targetKey === "TCS_APP" ? "grid" : "none";
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
            versionSelect.innerHTML = deploymentMode === "tools"
                ? '<option value="">Select tool first...</option>'
                : '<option value="">Select deployment target first...</option>';
            return;
        }
        loadVersionOptions();
    }

    function loadVersionOptions() {
        const targetKey = getSelectedTargetKey();
        const versionSelect = document.getElementById("formVersion");
        const selectedToolKey = getSelectedToolKey();

        versionSelect.innerHTML = '<option value="">Select version...</option>';
        if (!targetKey) {
            versionSelect.innerHTML = deploymentMode === "tools"
                ? '<option value="">Select tool first...</option>'
                : '<option value="">Select deployment target first...</option>';
            return;
        }
        if (deploymentMode === "tools" && !selectedToolKey) {
            versionSelect.innerHTML = '<option value="">Select tool first...</option>';
            return;
        }

        versionSelect.innerHTML = '<option value="">Loading versions...</option>';
        const params = new URLSearchParams({ target_key: targetKey });
        if (deploymentMode === "tools" && selectedToolKey) {
            params.set("package_key", selectedToolKey);
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
        const startValue = common.combineLocalDateAndTime(
            document.getElementById("formStartDate").value,
            document.getElementById("formStartTime").value
        );
        const targetKey = getSelectedTargetKey();
        const toolKey = getSelectedToolKey();
        const selectedServerMappingId = document.getElementById("formServerMappings").value;
        const selectedServerMappingIds = selectedServerMappingId === "ALL"
            ? getServerMappingsForSelection().map(function (mapping) {
                return String(mapping.environment_host_mapping_id);
            })
            : (selectedServerMappingId ? [selectedServerMappingId] : []);
        return {
            env_id: document.getElementById("formEnvId").value,
            requested_env_type: deploymentMode === "tools"
                ? "TOOLS"
                : document.getElementById("formEnvType").value,
            planned_start_time: startValue ? new Date(startValue).toISOString() : "",
            description: document.getElementById("formDescription").value.trim(),
            user_timezone: common.getUserTimezone(serverTimezone),
            deployment_request: {
                target_key: targetKey,
                env_scope_type: "ENV",
                requested_version: document.getElementById("formVersion").value.trim(),
                package_keys: deploymentMode === "tools" && toolKey ? [toolKey] : [],
                tcs_deployment_mode_id: targetKey === "TCS_APP" ? document.getElementById("formTestingMode").value : "",
                selected_server_mapping_ids: selectedServerMappingIds,
                tcs_service_ids: targetKey === "TCS_APP" && document.getElementById("formTcsService").value
                    ? [document.getElementById("formTcsService").value]
                    : [],
            },
        };
    }

    function validateDeploymentRequest(payload) {
        if (!payload.planned_start_time) {
            return "Planned start time is required.";
        }
        if (common.isPastDateTimeSelection(
            document.getElementById("formStartDate").value,
            document.getElementById("formStartTime").value
        )) {
            showPastTimePopup();
            return "Previous time is not allowed.";
        }
        if (!payload.env_id) {
            return deploymentMode === "tools"
                ? "Tool environment is required."
                : "Environment is required.";
        }
        if (deploymentMode !== "tools" && !payload.requested_env_type) {
            return "Environment type is required.";
        }
        if (deploymentMode !== "tools" && !payload.env_id) {
            return "Environment is required.";
        }
        const deployment = payload.deployment_request;
        if (!deployment.target_key) {
            return "Deployment target is required.";
        }
        if (deploymentMode === "tools" && (!deployment.package_keys || !deployment.package_keys.length)) {
            return "Tool name is required.";
        }
        if (!deployment.selected_server_mapping_ids || !deployment.selected_server_mapping_ids.length) {
            return "Target server selection is required.";
        }
        if (!deployment.requested_version) {
            return "Requested version is required.";
        }
        if (deployment.target_key === "TCS_APP" && !deployment.tcs_deployment_mode_id) {
            return "Deployment mode is required.";
        }
        if (deployment.target_key === "TCS_APP" && (!deployment.tcs_service_ids || !deployment.tcs_service_ids.length)) {
            return "TCS service is required.";
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
        const serviceTypesGroup = document.getElementById("formTcsServicesGroup");
        const testingMode = document.getElementById("formTestingMode");
        if (serviceTypesGroup) {
            serviceTypesGroup.style.display = "none";
        }
        if (testingMode) {
            testingMode.required = false;
        }
        common.resetSelect("formVersion", "Select version...");
        const serverSelect = document.getElementById("formServerMappings");
        if (serverSelect) {
            serverSelect.innerHTML = deploymentMode === "tools"
                ? '<option value="">Select environment first...</option>'
                : '<option value="">Select environment and target first...</option>';
        }
        populateEnvOptions("");
        if (deploymentMode === "tools") {
            populateToolOptions();
        }
        applyDefaultStartTime(true);
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
                const successMessage =
                    "Deployment request submitted successfully. Status: " + (requestData.status || "OPEN") + ".";
                showFormMessage(successMessage, "success");
                showDeploymentSuccessToast(successMessage);
                resetFormState();
            })
            .catch(function () {
                showFormMessage("Unable to reach the booking service.", "danger");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const toastElement = document.getElementById("deploymentSuccessToast");
        if (toastElement) {
            deploymentSuccessToast = new bootstrap.Toast(toastElement, {
                autohide: true,
                delay: 3200,
            });
        }

        applyDateRestrictions();
        applyDefaultStartTime(false);
        const startDateField = document.getElementById("formStartDate");
        const startTimeField = document.getElementById("formStartTime");
        if (startDateField) {
            startDateField.addEventListener("change", function () {
                validateDateNotInPast();
                validateTimeNotInPast();
            });
        }
        if (startTimeField) {
            startTimeField.addEventListener("change", function () {
                validateTimeNotInPast();
            });
        }
        const envTypeField = document.getElementById("formEnvType");
        if (envTypeField) {
            envTypeField.addEventListener("change", function () {
                populateEnvOptions(this.value);
                populateServerMappingOptions();
            });
        }
        document.getElementById("formEnvId").addEventListener("change", function () {
            populateServerMappingOptions();
        });
        if (deploymentMode === "tools") {
            const toolField = document.getElementById("formToolKey");
            if (toolField) {
                toolField.addEventListener("change", loadVersionOptions);
            }
        } else {
            document.getElementById("formTargetKey").addEventListener("change", loadDeploymentOptions);
        }
        document.getElementById("deploymentRequestForm").addEventListener("submit", handleDeploymentSubmit);

        populateTargetOptions();
        populateEnvOptions("");
        if (deploymentMode === "tools") {
            populateToolOptions();
        }
        const serviceTypesGroup = document.getElementById("formTcsServicesGroup");
        const testingMode = document.getElementById("formTestingMode");
        if (serviceTypesGroup) {
            serviceTypesGroup.style.display = "none";
        }
        if (testingMode) {
            testingMode.required = false;
        }
        if (deploymentMode === "tools") {
            populateServerMappingOptions();
            loadVersionOptions();
        }
        updatePolicyHint();
    });
}());
