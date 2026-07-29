(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const currentUser = pageData.currentUser;
    const userRole = pageData.userRole;
    const environments = pageData.environments || [];
    const serverTimezone = pageData.serverTimezone || "UTC";

    let allBookings = [];
    let visibleBookings = [];
    let activeBooking = null;
    let editModal = null;

    function populateTimeSlotFields() {
        common.populateTimeSlotOptions({
            selectId: "editStartTime",
            placeholder: "Select time...",
            selectedValue: document.getElementById("editStartTime").value,
            slotMinutes: 30,
        });
        common.populateTimeSlotOptions({
            selectId: "editEndTime",
            placeholder: "Select time...",
            selectedValue: document.getElementById("editEndTime").value,
            slotMinutes: 30,
        });
    }

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

    function bookingVersionLabel(booking) {
        const deployment = booking.deployment_request || {};
        const snapshotRuntime = booking.snapshot_runtime || {};
        return deployment.requested_version || snapshotRuntime.version || "-";
    }

    function bookingServiceLabel(booking) {
        const deployment = booking.deployment_request || {};
        const snapshotRuntime = booking.snapshot_runtime || {};
        const values = deployment.tcs_service_names || snapshotRuntime.tcs_service_names || [];
        return values.length ? values.join(", ") : "-";
    }

    function bookingModeLabel(booking) {
        const deployment = booking.deployment_request || {};
        const snapshotRuntime = booking.snapshot_runtime || {};
        if (deployment.tcs_deployment_mode) {
            return deployment.tcs_deployment_mode;
        }
        const values = snapshotRuntime.tcs_deployment_modes || [];
        return values.length ? values.join(", ") : "-";
    }

    function bookingDetailsHtml(booking) {
        const details = [
            "Version: " + bookingVersionLabel(booking),
            "Service: " + bookingServiceLabel(booking),
            "Mode: " + bookingModeLabel(booking),
        ];
        return details.map(function (detail) {
            return '<div class="row-note">' + common.escapeHtml(detail) + "</div>";
        }).join("");
    }

    function bookingOwnerLabel(booking) {
        const ownerValue =
            String(booking.requested_by_name || "").trim() ||
            String(booking.requested_by || "").trim() ||
            String(booking.requested_by_display || "").trim() ||
            "";

        if (!ownerValue) {
            return "-";
        }

        return ownerValue.replace(/\s*\([^)]*\)\s*$/, "").trim() || ownerValue;
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
                bookingResolvedHostsLabel(booking),
                (booking.deployment_request && booking.deployment_request.selected_servers_summary) || "",
                bookingVersionLabel(booking),
                bookingServiceLabel(booking),
                bookingModeLabel(booking),
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
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No booking requests match the current filters.</td></tr>';
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
            const ownerLabel = bookingOwnerLabel(booking);
            const detailsHtml = bookingDetailsHtml(booking);
            const actions = canModify
                ? '<div class="action-group">' +
                    '<button class="btn btn-sm btn-outline-primary" data-action="edit" data-id="' + common.escapeHtml(booking.booking_id) + '">Edit</button>' +
                    '<button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="' + common.escapeHtml(booking.booking_id) + '">Cancel</button>' +
                    "</div>"
                : '<div class="action-group">' +
                    '<button class="btn btn-sm btn-outline-secondary" data-action="view" data-id="' + common.escapeHtml(booking.booking_id) + '">View</button>' +
                    "</div>";

            const startText = booking.start_time
                ? common.formatDisplayDate(booking.start_time)
                : "-";
            const endText = booking.is_standalone_deployment_request
                ? ""
                : (booking.end_time ? common.formatDisplayDate(booking.end_time) : "-");

            return '<tr>' +
                '<td><div><span class="app-env-label">' + common.escapeHtml(environmentLabel) + '</span></div><div class="row-note">' + common.escapeHtml(environmentNote || "-") + "</div></td>" +
                "<td>" + typePill(booking.booking_type) + "</td>" +
                "<td><div>" + common.escapeHtml(startText) + "</div></td>" +
                "<td><div>" + common.escapeHtml(endText) + "</div></td>" +
                '<td><div class="fw-semibold">' + common.escapeHtml(ownerLabel) + "</div>" + note + "</td>" +
                "<td>" + detailsHtml + "</td>" +
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
        const localStart = moment.utc(booking.start_time).local();
        const localEnd = moment.utc(booking.end_time).local();

        document.getElementById("editModalTitle").textContent = "Edit " + booking.booking_id;
        document.getElementById("editStartDate").value = localStart.format("YYYY-MM-DD");
        document.getElementById("editStartTime").value = localStart.format("HH:mm");
        document.getElementById("editEndDate").value = localEnd.format("YYYY-MM-DD");
        document.getElementById("editEndTime").value = localEnd.format("HH:mm");
        populateTimeSlotFields();
        document.getElementById("editEnvType").value = inferEnvType(booking.env_id);
        populateEnvironmentOptions("editEnvId", document.getElementById("editEnvType").value, booking.env_id);
        document.getElementById("editBookingTypeDisplay").value = booking.booking_type === "DEPLOYMENT" ? "Deployment" : "Reservation";
        document.getElementById("editDescription").value = booking.description || "";

        const deployment = booking.deployment_request || null;
        if (booking.booking_type === "DEPLOYMENT" && deployment) {
            document.getElementById("deploymentSection").style.display = "block";
            document.getElementById("editComponentType").value = deployment.target_key || "";
            document.getElementById("editVersion").value = deployment.requested_version || "";
            document.getElementById("editTestingMode").value = deployment.tcs_deployment_mode || "";
            document.getElementById("editComponentNames").value = deployment.selected_servers_summary || "";
            document.getElementById("editServiceTypesGroup").style.display = deployment.target_key === "TCS_APP" ? "block" : "none";
            document.getElementById("editServiceTypes").value = (deployment.tcs_service_names || []).join(", ");
        } else {
            document.getElementById("deploymentSection").style.display = "none";
            document.getElementById("editComponentType").value = "";
            document.getElementById("editVersion").value = "";
            document.getElementById("editComponentNames").value = "";
            document.getElementById("editTestingMode").value = "";
            document.getElementById("editServiceTypesGroup").style.display = "none";
            document.getElementById("editServiceTypes").value = "";
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
            document.getElementById("editStartDate").value = moment.utc(booking.start_time).local().format("YYYY-MM-DD");
            document.getElementById("editStartTime").value = moment.utc(booking.start_time).local().format("HH:mm");
            document.getElementById("editEndDate").value = booking.end_time ? moment.utc(booking.end_time).local().format("YYYY-MM-DD") : "";
            document.getElementById("editEndTime").value = booking.end_time ? moment.utc(booking.end_time).local().format("HH:mm") : "";
            populateTimeSlotFields();
            document.getElementById("editEnvType").value = envType || "";
            populateEnvironmentOptions("editEnvId", envType, booking.env_id);
            document.getElementById("editBookingTypeDisplay").value = "Deployment";
            document.getElementById("editDescription").value = booking.description || "";

            document.getElementById("deploymentSection").style.display = "block";
            document.getElementById("editComponentType").value = deployment.target_key || "";
            document.getElementById("editVersion").value = deployment.requested_version || "";
            document.getElementById("editTestingMode").value = deployment.tcs_deployment_mode || "";
            document.getElementById("editComponentNames").value = deployment.selected_servers_summary || "";
            document.getElementById("editServiceTypesGroup").style.display = deployment.target_key === "TCS_APP" ? "block" : "none";
            document.getElementById("editServiceTypes").value = (deployment.tcs_service_names || []).join(", ");

            setModalMode("view");
            editModal.show();
            return;
        }

        openEditBooking(bookingId);
        setModalMode("view");
        document.getElementById("editModalTitle").textContent = "View " + booking.booking_id;
    }

    function buildBookingPayload() {
        const startTime = common.combineLocalDateAndTime(
            document.getElementById("editStartDate").value,
            document.getElementById("editStartTime").value
        );
        const endTime = common.combineLocalDateAndTime(
            document.getElementById("editEndDate").value,
            document.getElementById("editEndTime").value
        );
        const payload = {
            env_id: document.getElementById("editEnvId").value,
            start_time: moment(startTime).utc().toISOString(),
            end_time: moment(endTime).utc().toISOString(),
            booking_type: activeBooking ? activeBooking.booking_type : "RESERVATION",
            description: document.getElementById("editDescription").value.trim(),
            user_timezone: common.getUserTimezone(serverTimezone),
        };

        return payload;
    }

    function saveBookingChanges() {
        if (!activeBooking) {
            return;
        }

        const startTime = common.combineLocalDateAndTime(
            document.getElementById("editStartDate").value,
            document.getElementById("editStartTime").value
        );
        const endTime = common.combineLocalDateAndTime(
            document.getElementById("editEndDate").value,
            document.getElementById("editEndTime").value
        );

        if (!startTime || !endTime) {
            showModalMessage("Please select both start and end date/time.", "danger");
            return;
        }

        if (new Date(startTime) >= new Date(endTime)) {
            showModalMessage("End time must be after start time.", "danger");
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
                document.getElementById("bookingTableBody").innerHTML = '<tr><td colspan="7" class="empty-state">Unable to load booking requests.</td></tr>';
            });
    }

    function clearFilters() {
        document.getElementById("filterEnvType").value = "";
        document.getElementById("filterBookingType").value = "";
        document.getElementById("filterStatus").value = "";
        document.getElementById("filterSearch").value = "";
        renderTable();
    }

    function buildExportQuery() {
        const params = new URLSearchParams();
        const envType = document.getElementById("filterEnvType").value;
        const bookingType = document.getElementById("filterBookingType").value;
        const status = document.getElementById("filterStatus").value;
        const search = document.getElementById("filterSearch").value.trim();

        if (envType) {
            params.set("env_type", envType);
        }
        if (bookingType) {
            params.set("booking_type", bookingType);
        }
        if (status) {
            params.set("status", status);
        }
        if (search) {
            params.set("search", search);
        }

        return params.toString();
    }

    function exportCsv() {
        const query = buildExportQuery();
        window.location.href = "/api/bookings/export" + (query ? "?" + query : "");
    }

    document.addEventListener("DOMContentLoaded", function () {
        editModal = new bootstrap.Modal(document.getElementById("editBookingModal"));
        populateTimeSlotFields();

        ["filterEnvType", "filterBookingType", "filterStatus"].forEach(function (id) {
            document.getElementById(id).addEventListener("change", renderTable);
        });
        document.getElementById("filterSearch").addEventListener("input", renderTable);
        document.getElementById("clearFiltersButton").addEventListener("click", clearFilters);
        document.getElementById("exportCsvButton").addEventListener("click", exportCsv);
        document.getElementById("editEnvType").addEventListener("change", function () {
            populateEnvironmentOptions("editEnvId", this.value, "");
        });
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
