(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const currentUser = pageData.currentUser;
    const userRole = pageData.userRole;
    const environments = pageData.environments || [];
    const componentConfig = pageData.componentConfig || {};
    const deploymentTargets = pageData.deploymentTargets || [];
    const serverTimezone = pageData.serverTimezone || "UTC";

    let allBookings = [];
    let visibleBookings = [];
    let activeBooking = null;
    let editModal = null;

    function formatWindowDisplay(startValue, endValue, lifecycleStatus) {
        const start = moment.utc(startValue).local();
        const end = moment.utc(endValue).local();
        const today = moment().startOf("day");
        const startDay = start.clone().startOf("day");
        const endDay = end.clone().startOf("day");
        const yesterday = today.clone().subtract(1, "day");

        if (lifecycleStatus === "completed" && startDay.isSame(yesterday) && endDay.isSame(yesterday)) {
            return "Yesterday";
        }
        if (startDay.isSame(today) && endDay.isSame(today)) {
            return "Today " + start.format("HH:mm") + " -> " + end.format("HH:mm");
        }
        if (startDay.isSame(yesterday) && endDay.isSame(yesterday)) {
            return "Yesterday " + start.format("HH:mm") + " -> " + end.format("HH:mm");
        }
        if (startDay.isSame(today)) {
            return "Today " + start.format("HH:mm") + " -> " + end.format("DD MMM HH:mm");
        }
        if (startDay.isSame(yesterday)) {
            return "Yesterday " + start.format("HH:mm") + " -> " + end.format("DD MMM HH:mm");
        }
        if (startDay.isSame(endDay)) {
            return start.format("DD MMM HH:mm") + " -> " + end.format("HH:mm");
        }
        return start.format("DD MMM HH:mm") + " -> " + end.format("DD MMM HH:mm");
    }

    function inferEnvType(envId) {
        return common.inferEnvType(environments, envId);
    }

    function bookingEnvironmentLabel(booking) {
        const deployment = booking.deployment_request || {};
        return deployment.environment_display || booking.env_id || "-";
    }

    function bookingEnvironmentTypeLabel(booking) {
        const deployment = booking.deployment_request || {};
        return deployment.requested_env_type || inferEnvType(booking.env_id) || "-";
    }

    function bookingResolvedHostsLabel(booking) {
        const deployment = booking.deployment_request || {};
        return deployment.resolved_hosts_summary || "";
    }

    function userCanSeeBooking(booking) {
        return userRole === "admin" || booking.requested_by === currentUser;
    }

    function userCanModifyBooking(booking) {
        if (booking.is_standalone_deployment_request) {
            return false;
        }
        return (userRole === "admin" || booking.requested_by === currentUser) && booking.lifecycle_status === "scheduled";
    }

    function filteredBookings() {
        const envType = document.getElementById("filterEnvType").value;
        const bookingType = document.getElementById("filterBookingType").value;
        const status = document.getElementById("filterStatus").value;
        const search = document.getElementById("filterSearch").value.trim().toLowerCase();

        return allBookings.filter(function (booking) {
            if (!userCanSeeBooking(booking)) {
                return false;
            }
            if (envType && bookingEnvironmentTypeLabel(booking) !== envType) {
                return false;
            }
            if (bookingType && booking.booking_type !== bookingType) {
                return false;
            }
            if (status && booking.lifecycle_status !== status) {
                return false;
            }
            if (!search) {
                return true;
            }

            const haystack = [
                booking.booking_id,
                booking.env_id,
                bookingEnvironmentLabel(booking),
                bookingEnvironmentTypeLabel(booking),
                bookingResolvedHostsLabel(booking),
                booking.requested_by,
                booking.requested_by_name,
                booking.requested_by_team,
                booking.requested_by_display,
                booking.description,
            ].join(" ").toLowerCase();
            return haystack.includes(search);
        });
    }

    function updateSummary() {
        const scheduled = visibleBookings.filter(function (booking) {
            return booking.lifecycle_status === "scheduled";
        }).length;
        const deployments = visibleBookings.filter(function (booking) {
            return booking.booking_type === "DEPLOYMENT";
        }).length;

        document.getElementById("summaryVisible").textContent = visibleBookings.length;
        document.getElementById("summaryScheduled").textContent = scheduled;
        document.getElementById("summaryDeployments").textContent = deployments;
    }

    function statusPill(booking) {
        return '<span class="status-pill status-' + common.escapeHtml(booking.lifecycle_status) + '">' +
            common.escapeHtml(booking.status_label || booking.lifecycle_status) +
            "</span>";
    }

    function typePill(type) {
        const className = type === "DEPLOYMENT" ? "type-deployment" : "type-reservation";
        return '<span class="type-pill ' + className + '">' + common.escapeHtml(type) + "</span>";
    }

    function renderTable() {
        const tbody = document.getElementById("bookingTableBody");
        visibleBookings = filteredBookings();
        updateSummary();

        if (!visibleBookings.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No booking requests match the current filters.</td></tr>';
            return;
        }

        tbody.innerHTML = visibleBookings.map(function (booking) {
            const canModify = userCanModifyBooking(booking);
            const note = booking.description
                ? '<div class="row-note">' + common.escapeHtml(booking.description) + "</div>"
                : "";
            const environmentLabel = bookingEnvironmentLabel(booking);
            const environmentType = bookingEnvironmentTypeLabel(booking);
            const resolvedHosts = bookingResolvedHostsLabel(booking);
            const environmentNote = resolvedHosts || environmentType;
            const actions = canModify
                ? '<div class="action-group">' +
                    '<button class="btn btn-sm btn-outline-primary" data-action="edit" data-id="' + common.escapeHtml(booking.booking_id) + '">Edit</button>' +
                    '<button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="' + common.escapeHtml(booking.booking_id) + '">Cancel</button>' +
                    "</div>"
                : '<div class="action-group">' +
                    '<button class="btn btn-sm btn-outline-secondary" data-action="view" data-id="' + common.escapeHtml(booking.booking_id) + '">View</button>' +
                    "</div>";

            const windowText = booking.is_standalone_deployment_request
                ? common.formatDisplayDate(booking.start_time)
                : formatWindowDisplay(booking.start_time, booking.end_time, booking.lifecycle_status);

            return '<tr>' +
                '<td><div class="fw-semibold">' + common.escapeHtml(booking.booking_id) + "</div>" + note + "</td>" +
                '<td><div class="fw-semibold">' + common.escapeHtml(environmentLabel) + '</div><div class="row-note">' + common.escapeHtml(environmentNote || "-") + "</div></td>" +
                "<td><div>" + common.escapeHtml(windowText) + "</div></td>" +
                "<td>" + typePill(booking.booking_type) + "</td>" +
                "<td>" + statusPill(booking) + "</td>" +
                "<td>" + actions + "</td>" +
                "</tr>";
        }).join("");
    }

    function setModalMode(mode) {
        const isView = mode === "view";
        const title = document.getElementById("editModalTitle");
        const saveButton = document.getElementById("saveBookingButton");
        const deleteButton = document.getElementById("deleteBookingButton");
        const form = document.getElementById("editBookingForm");

        title.textContent = isView && activeBooking ? "View " + activeBooking.booking_id : title.textContent;
        saveButton.style.display = isView ? "none" : "";
        deleteButton.style.display = isView ? "none" : "";

        Array.from(form.querySelectorAll("input, select, textarea")).forEach(function (field) {
            field.disabled = isView;
        });
    }

    function showPageMessage(message, type) {
        common.showAlertHost({
            hostId: "pageMessage",
            message: message,
            type: type,
        });
    }

    function showModalMessage(message, type) {
        common.showAlertHost({
            hostId: "modalMessage",
            message: message,
            type: type,
            dismissible: false,
        });
    }

    function clearModalMessage() {
        common.clearHost("modalMessage");
    }

    function populateEnvironmentOptions(selectId, envType, selectedEnvId) {
        common.populateEnvironmentOptions({
            selectId: selectId,
            environments: environments,
            envType: envType,
            selectedEnvId: selectedEnvId,
        });
    }

    function populateSharedEnvironmentDisplay(selectId, displayLabel) {
        const select = document.getElementById(selectId);
        select.innerHTML = "";
        select.insertAdjacentHTML(
            "beforeend",
            '<option value="" selected>' + common.escapeHtml(displayLabel || "Shared") + "</option>"
        );
    }

    function populateComponentNames(componentType, selectedValues) {
        const select = document.getElementById("editComponentNames");
        select.innerHTML = "";
        (componentConfig[componentType] || []).forEach(function (name) {
            select.insertAdjacentHTML(
                "beforeend",
                '<option value="' + common.escapeHtml(name) + '">' + common.escapeHtml(name) + "</option>"
            );
        });
        if (selectedValues && selectedValues.length) {
            Array.from(select.options).forEach(function (option) {
                option.selected = selectedValues.includes(option.value);
            });
        }
    }

    function getTargetByKey(targetKey) {
        return deploymentTargets.find(function (target) {
            return target.target_key === targetKey;
        }) || null;
    }

    function populateVersionOptionsForRequest(targetKey, selectedPackages, selectedVersion) {
        const packageKey = (selectedPackages || [])[0] || "";
        const select = document.getElementById("editVersion");
        select.innerHTML = '<option value="">Loading...</option>';

        if (!targetKey || !packageKey) {
            common.resetSelect("editVersion", "Select version...");
            return Promise.resolve();
        }

        let url = "/api/component-versions?target_key=" + encodeURIComponent(targetKey);
        if (targetKey === "TOOLS") {
            url += "&package_key=" + encodeURIComponent(packageKey);
        }

        return common.fetchJson(url, {
            credentials: "include",
        })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Failed to load versions");
                }
                common.resetSelect("editVersion", "Select version...");
                (result.data.versions || []).forEach(function (version) {
                    select.insertAdjacentHTML(
                        "beforeend",
                        '<option value="' + common.escapeHtml(version) + '">' + common.escapeHtml(version) + "</option>"
                    );
                });
                if (selectedVersion) {
                    select.value = selectedVersion;
                }
            })
            .catch(function () {
                common.resetSelect("editVersion", "Select version...");
            });
    }

    function loadVersions(componentType, selectedVersion) {
        const select = document.getElementById("editVersion");
        select.innerHTML = '<option value="">Loading...</option>';

        if (!componentType) {
            common.resetSelect("editVersion", "Select version...");
            return Promise.resolve();
        }

        return common.fetchJson("/api/component-versions?target_key=" + encodeURIComponent(componentType), {
            credentials: "include",
        })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Failed to load versions");
                }
                common.resetSelect("editVersion", "Select version...");
                (result.data.versions || []).forEach(function (version) {
                    select.insertAdjacentHTML(
                        "beforeend",
                        '<option value="' + common.escapeHtml(version) + '">' + common.escapeHtml(version) + "</option>"
                    );
                });
                if (selectedVersion) {
                    select.value = selectedVersion;
                }
            })
            .catch(function () {
                common.resetSelect("editVersion", "Select version...");
            });
    }

    function resetServiceTypes() {
        Array.from(document.getElementById("editServiceTypes").options).forEach(function (option) {
            option.selected = false;
        });
    }

    function handleEditComponentTypeChange() {
        const componentType = document.getElementById("editComponentType").value;
        populateComponentNames(componentType, []);
        loadVersions(componentType, null);
        document.getElementById("editServiceTypesGroup").style.display = componentType === "TCS_APP" ? "block" : "none";
        if (componentType !== "TCS_APP") {
            resetServiceTypes();
        }
    }

    function openEditBooking(bookingId) {
        const booking = allBookings.find(function (item) {
            return item.booking_id === bookingId;
        });
        if (!booking) {
            return;
        }
        if (booking.is_standalone_deployment_request) {
            openViewBooking(bookingId);
            return;
        }

        activeBooking = booking;
        clearModalMessage();

        document.getElementById("editModalTitle").textContent = "Edit " + booking.booking_id;
        document.getElementById("editStartTime").value = common.formatLocalInput(booking.start_time);
        document.getElementById("editEndTime").value = common.formatLocalInput(booking.end_time);
        document.getElementById("editEnvType").value = inferEnvType(booking.env_id);
        populateEnvironmentOptions("editEnvId", document.getElementById("editEnvType").value, booking.env_id);
        document.getElementById("editBookingTypeDisplay").value = booking.booking_type === "DEPLOYMENT" ? "Deployment" : "Reservation";
        document.getElementById("editDescription").value = booking.description || "";

        const deployment = booking.deployment_request || null;
        if (booking.booking_type === "DEPLOYMENT" && deployment) {
            document.getElementById("deploymentSection").style.display = "block";
            document.getElementById("editComponentType").value = deployment.target_key || "";
            populateComponentNames(deployment.target_key || "", deployment.package_keys || []);
            populateVersionOptionsForRequest(
                deployment.target_key || "",
                deployment.package_keys || [],
                deployment.requested_version || ""
            );
            document.getElementById("editTestingMode").value = deployment.testing_mode || "";
            document.getElementById("editServiceTypesGroup").style.display = deployment.target_key === "TCS_APP" ? "block" : "none";
            Array.from(document.getElementById("editServiceTypes").options).forEach(function (option) {
                option.selected = (deployment.service_types || []).includes(option.value);
            });
        } else {
            document.getElementById("deploymentSection").style.display = "none";
            document.getElementById("editComponentType").value = "";
            common.resetSelect("editVersion", "Select version...");
            document.getElementById("editComponentNames").innerHTML = "";
            document.getElementById("editTestingMode").value = "";
            document.getElementById("editServiceTypesGroup").style.display = "none";
            resetServiceTypes();
        }

        setModalMode("edit");
        editModal.show();
    }

    function openViewBooking(bookingId) {
        const booking = allBookings.find(function (item) {
            return item.booking_id === bookingId;
        });
        if (!booking) {
            return;
        }

        if (booking.is_standalone_deployment_request) {
            activeBooking = booking;
            clearModalMessage();
            const deployment = booking.deployment_request || {};
            const envType = deployment.requested_env_type || inferEnvType(booking.env_id);
            const environmentLabel = bookingEnvironmentLabel(booking);
            document.getElementById("editModalTitle").textContent = "View " + booking.booking_id;
            document.getElementById("editStartTime").value = common.formatLocalInput(booking.start_time);
            document.getElementById("editEndTime").value = booking.end_time ? common.formatLocalInput(booking.end_time) : "";
            document.getElementById("editEnvType").value = envType || "";
            if (booking.env_id) {
                populateEnvironmentOptions("editEnvId", envType, booking.env_id);
            } else {
                populateSharedEnvironmentDisplay("editEnvId", environmentLabel);
            }
            document.getElementById("editBookingTypeDisplay").value = "Deployment";
            document.getElementById("editDescription").value = booking.description || "";

            document.getElementById("deploymentSection").style.display = "block";
            document.getElementById("editComponentType").value = deployment.target_key || "";
            document.getElementById("editVersion").innerHTML = '<option value="' + common.escapeHtml(deployment.requested_version || "") + '" selected>' + common.escapeHtml(deployment.requested_version || "N/A") + "</option>";
            document.getElementById("editTestingMode").value = deployment.testing_mode || "";
            document.getElementById("editComponentNames").innerHTML = (deployment.package_keys || []).map(function (name) {
                return '<option value="' + common.escapeHtml(name) + '" selected>' + common.escapeHtml(name) + "</option>";
            }).join("");
            document.getElementById("editServiceTypesGroup").style.display = deployment.target_key === "TCS_APP" ? "block" : "none";
            resetServiceTypes();
            Array.from(document.getElementById("editServiceTypes").options).forEach(function (option) {
                option.selected = (deployment.service_types || []).includes(option.value);
            });

            setModalMode("view");
            editModal.show();
            return;
        }

        openEditBooking(bookingId);
        setModalMode("view");
        document.getElementById("editModalTitle").textContent = "View " + booking.booking_id;
    }

    function buildBookingPayload() {
        const payload = {
            env_id: document.getElementById("editEnvId").value,
            start_time: moment(document.getElementById("editStartTime").value).utc().toISOString(),
            end_time: moment(document.getElementById("editEndTime").value).utc().toISOString(),
            booking_type: activeBooking ? activeBooking.booking_type : "RESERVATION",
            description: document.getElementById("editDescription").value.trim(),
            user_timezone: common.getUserTimezone(serverTimezone),
        };

        if (payload.booking_type === "DEPLOYMENT") {
            payload.deployment_request = {
                target_key: document.getElementById("editComponentType").value,
                requested_version: document.getElementById("editVersion").value,
                testing_mode: document.getElementById("editTestingMode").value,
                package_keys: Array.from(document.getElementById("editComponentNames").selectedOptions).map(function (opt) {
                    return opt.value;
                }),
                service_types: Array.from(document.getElementById("editServiceTypes").selectedOptions).map(function (opt) {
                    return opt.value;
                }),
            };
        }

        return payload;
    }

    function saveBookingChanges() {
        if (!activeBooking) {
            return;
        }

        common.fetchJson("/api/bookings/" + encodeURIComponent(activeBooking.booking_id), {
            method: "PUT",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(buildBookingPayload()),
        })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to update booking.");
                }
                editModal.hide();
                showPageMessage(result.data.message || "Booking updated successfully.", "success");
                fetchBookings();
            })
            .catch(function (error) {
                showModalMessage(error.message, "danger");
            });
    }

    function deleteBooking(bookingId) {
        if (!confirm("Cancel this booking/request?")) {
            return;
        }

        common.fetchJson("/api/bookings/" + encodeURIComponent(bookingId), {
            method: "DELETE",
            credentials: "include",
        })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to cancel booking.");
                }
                if (editModal) {
                    editModal.hide();
                }
                showPageMessage(result.data.message || "Booking cancelled successfully.", "success");
                fetchBookings();
            })
            .catch(function (error) {
                if (editModal && activeBooking && activeBooking.booking_id === bookingId) {
                    showModalMessage(error.message, "danger");
                    return;
                }
                showPageMessage(error.message, "danger");
            });
    }

    function fetchBookings() {
        common.fetchJson("/api/bookings", { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to load bookings.");
                }
                allBookings = Array.isArray(result.data) ? result.data : [];
                renderTable();
            })
            .catch(function (error) {
                showPageMessage(error.message, "danger");
                document.getElementById("bookingTableBody").innerHTML = '<tr><td colspan="6" class="empty-state">Unable to load booking requests.</td></tr>';
            });
    }

    function clearFilters() {
        document.getElementById("filterEnvType").value = "";
        document.getElementById("filterBookingType").value = "";
        document.getElementById("filterStatus").value = "";
        document.getElementById("filterSearch").value = "";
        renderTable();
    }

    document.addEventListener("DOMContentLoaded", function () {
        editModal = new bootstrap.Modal(document.getElementById("editBookingModal"));

        ["filterEnvType", "filterBookingType", "filterStatus"].forEach(function (id) {
            document.getElementById(id).addEventListener("change", renderTable);
        });
        document.getElementById("filterSearch").addEventListener("input", renderTable);
        document.getElementById("clearFiltersButton").addEventListener("click", clearFilters);
        document.getElementById("editEnvType").addEventListener("change", function () {
            populateEnvironmentOptions("editEnvId", this.value, "");
        });
        document.getElementById("editComponentType").addEventListener("change", handleEditComponentTypeChange);
        document.getElementById("saveBookingButton").addEventListener("click", saveBookingChanges);
        document.getElementById("deleteBookingButton").addEventListener("click", function () {
            if (activeBooking) {
                deleteBooking(activeBooking.booking_id);
            }
        });
        document.getElementById("bookingTableBody").addEventListener("click", function (event) {
            const button = event.target.closest("button[data-action][data-id]");
            if (!button) {
                return;
            }
            if (button.dataset.action === "edit") {
                openEditBooking(button.dataset.id);
                return;
            }
            if (button.dataset.action === "delete") {
                deleteBooking(button.dataset.id);
                return;
            }
            openViewBooking(button.dataset.id);
        });

        fetchBookings();
    });
}());
