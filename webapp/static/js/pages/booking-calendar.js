(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environments = pageData.environments || [];
    const statusLabels = pageData.statusLabels || {};
    const userTimezone = common.getUserTimezone(pageData.serverTimezone || "UTC");
    let calendar = null;
    let allBookings = [];

    function getStatusLabel(status) {
        return statusLabels[status] || status;
    }

    function inferEnvType(envId) {
        return common.inferEnvType(environments, envId);
    }

    function getComputedBookings() {
        return allBookings.map(function (booking) {
            return {
                booking: booking,
                start: moment.utc(booking.start_time).local(),
                end: moment.utc(booking.end_time || booking.start_time).local(),
                computedStatus: booking.lifecycle_status,
            };
        });
    }

    function matchesFilters(item) {
        const envType = document.getElementById("filterEnvType").value;
        const bookingType = document.getElementById("filterBookingType").value;
        const status = document.getElementById("filterStatus").value;
        const requestedBy = document.getElementById("filterRequestedBy").value.trim().toLowerCase();
        const selectedEnvType = inferEnvType(item.booking.env_id);

        if (envType && selectedEnvType !== envType) {
            return false;
        }
        if (bookingType && item.booking.booking_type !== bookingType) {
            return false;
        }
        if (status && item.computedStatus !== status) {
            return false;
        }
        if (!requestedBy) {
            return true;
        }

        return String(item.booking.requested_by || "").toLowerCase().includes(requestedBy) ||
            String(item.booking.requested_by_name || "").toLowerCase().includes(requestedBy);
    }

    function mapBookingToEvent(item) {
        const booking = item.booking;
        return {
            id: booking.booking_id,
            title: booking.env_id + (booking.booking_type === "DEPLOYMENT" ? " | DEPLOY" : ""),
            start: item.start.toDate(),
            end: item.end.toDate(),
            classNames: [
                "booking-" + item.computedStatus,
                booking.booking_type === "DEPLOYMENT" ? "booking-deployment" : "",
            ].filter(Boolean),
            extendedProps: {
                booking: booking,
                env_type: inferEnvType(booking.env_id),
                computed_status: item.computedStatus,
            },
        };
    }

    function updateStats(visibleBookings) {
        const computed = getComputedBookings();
        const active = computed.filter(function (item) {
            return item.computedStatus === "active";
        }).length;
        const deployments = computed.filter(function (item) {
            return item.booking.booking_type === "DEPLOYMENT";
        }).length;

        document.getElementById("statTotal").textContent = computed.length;
        document.getElementById("statActive").textContent = active;
        document.getElementById("statDeployment").textContent = deployments;
        document.getElementById("statVisible").textContent = visibleBookings.length;
    }

    function loadBookings(fetchInfo, successCallback, failureCallback) {
        common.fetchJson("/api/bookings", { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Failed to load bookings.");
                }

                allBookings = Array.isArray(result.data) ? result.data : [];
                const visibleBookings = getComputedBookings().filter(matchesFilters);
                updateStats(visibleBookings);
                successCallback(visibleBookings.map(mapBookingToEvent));
            })
            .catch(function (error) {
                showMessage(error.message, "danger");
                failureCallback(error);
            });
    }

    function buildDetailRow(label, value, isHtml) {
        return '<div class="detail-item">' +
            '<span class="detail-label">' + common.escapeHtml(label) + "</span>" +
            '<div class="detail-value">' + (isHtml ? value : common.escapeHtml(value)) + "</div>" +
            "</div>";
    }

    function renderDetails(event) {
        const detailsHost = document.getElementById("bookingDetails");
        const booking = event.extendedProps.booking;
        const deployment = booking.deployment_request || null;
        const status = event.extendedProps.computed_status;
        const localStart = moment.utc(booking.start_time).local().format("YYYY-MM-DD HH:mm");
        const localEnd = moment.utc(booking.end_time || booking.start_time).local().format("YYYY-MM-DD HH:mm");
        const detailRows = [
            buildDetailRow("Booking ID", booking.booking_id),
            buildDetailRow("Environment", booking.env_id),
            buildDetailRow("Environment Type", event.extendedProps.env_type || "-"),
            buildDetailRow("Requested By", booking.requested_by_name || booking.requested_by || "-"),
            buildDetailRow("Booking Type", booking.booking_type || "-"),
            buildDetailRow("Status", '<span class="status-pill status-' + common.escapeHtml(status) + '">' + common.escapeHtml(getStatusLabel(status)) + "</span>", true),
            buildDetailRow("Start", localStart + " (" + userTimezone + ")"),
            buildDetailRow(
                booking.is_standalone_deployment_request ? "Planned Window" : "End",
                booking.is_standalone_deployment_request
                    ? localStart + " (" + userTimezone + ")"
                    : localEnd + " (" + userTimezone + ")"
            ),
            buildDetailRow("Description", booking.description || "-"),
        ];

        if (deployment) {
            detailRows.push(buildDetailRow("Component Type", deployment.component_type || "-"));
            detailRows.push(buildDetailRow("Requested Version", deployment.requested_version || "-"));
            detailRows.push(buildDetailRow("Testing Mode", deployment.testing_mode || "-"));
            detailRows.push(buildDetailRow("Component Names", (deployment.component_names || []).join(", ") || "-"));
            detailRows.push(buildDetailRow("Service Types", (deployment.service_types || []).join(", ") || "-"));
        }

        detailsHost.className = "detail-list";
        detailsHost.innerHTML = detailRows.join("");
    }

    function showMessage(message, type) {
        common.showAlertHost({
            hostId: "messageContainer",
            message: message,
            type: type,
        });
    }

    function refreshCalendar() {
        if (calendar) {
            calendar.refetchEvents();
        }
    }

    function clearFilters() {
        document.getElementById("filterEnvType").value = "";
        document.getElementById("filterBookingType").value = "";
        document.getElementById("filterStatus").value = "";
        document.getElementById("filterRequestedBy").value = "";
        refreshCalendar();
    }

    document.addEventListener("DOMContentLoaded", function () {
        calendar = new FullCalendar.Calendar(document.getElementById("calendar"), {
            initialView: "dayGridMonth",
            height: "auto",
            nowIndicator: true,
            editable: false,
            selectable: false,
            slotMinTime: "00:00:00",
            slotMaxTime: "24:00:00",
            headerToolbar: {
                left: "prev,next today",
                center: "title",
                right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
            },
            events: loadBookings,
            eventClick: function (info) {
                renderDetails(info.event);
            },
        });

        calendar.render();

        ["filterEnvType", "filterBookingType", "filterStatus"].forEach(function (id) {
            document.getElementById(id).addEventListener("change", refreshCalendar);
        });
        document.getElementById("filterRequestedBy").addEventListener("input", refreshCalendar);
        document.getElementById("clearFiltersButton").addEventListener("click", clearFilters);
    });
}());
