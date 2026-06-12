(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environments = pageData.environments || [];
    const statusLabels = pageData.statusLabels || {};
    const userTimezone = common.getUserTimezone(pageData.serverTimezone || "UTC");
    let calendar = null;
    let allBookings = [];
    let bookingDetailsModal = null;
    let calendarResizeObserver = null;
    let hoverCard = null;
    let hoverTitle = null;
    let hoverMeta = null;
    let activeHoverEventId = null;

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
            String(item.booking.requested_by_name || "").toLowerCase().includes(requestedBy) ||
            String(item.booking.requested_by_team || "").toLowerCase().includes(requestedBy) ||
            String(item.booking.requested_by_display || "").toLowerCase().includes(requestedBy);
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

    function requesterDisplay(booking) {
        const explicitDisplay = String(booking.requested_by_display || "").trim();
        if (explicitDisplay) {
            return explicitDisplay;
        }

        const userId = String(booking.requested_by || "").trim();
        const teamName = String(booking.requested_by_team || "").trim();
        if (userId && teamName) {
            return userId + " (" + teamName + ")";
        }
        if (userId) {
            return userId;
        }

        return String(booking.requested_by_name || "").trim() || "-";
    }

    function formatHoverRow(label, value) {
        return '<div class="calendar-hover-row">' +
            '<span class="calendar-hover-label">' + common.escapeHtml(label) + "</span>" +
            '<span class="calendar-hover-value">' + common.escapeHtml(value || "-") + "</span>" +
            "</div>";
    }

    function hoverPreviewHtml(event) {
        const booking = event.extendedProps.booking;
        const status = getStatusLabel(event.extendedProps.computed_status);
        const localStart = moment.utc(booking.start_time).local().format("YYYY-MM-DD HH:mm");
        const localEnd = moment.utc(booking.end_time || booking.start_time).local().format("YYYY-MM-DD HH:mm");
        return [
            formatHoverRow("Type", booking.booking_type || "-"),
            formatHoverRow("Requester", String(booking.requested_by || "").trim() || String(booking.requested_by_name || "").trim() || "-"),
            formatHoverRow("Status", status || "-"),
            formatHoverRow("Window", booking.is_standalone_deployment_request ? localStart : localStart + " -> " + localEnd),
        ].join("");
    }

    function positionHoverCard(jsEvent) {
        if (!hoverCard || hoverCard.hidden) {
            return;
        }

        const margin = 12;
        const rect = hoverCard.getBoundingClientRect();
        let left = jsEvent.clientX + 16;
        let top = jsEvent.clientY + 16;

        if (left + rect.width > window.innerWidth - margin) {
            left = jsEvent.clientX - rect.width - 16;
        }
        if (left < margin) {
            left = margin;
        }

        if (top + rect.height > window.innerHeight - margin) {
            top = jsEvent.clientY - rect.height - 16;
        }
        if (top < margin) {
            top = margin;
        }

        hoverCard.style.left = left + "px";
        hoverCard.style.top = top + "px";
    }

    function showHoverCard(event, jsEvent) {
        if (!hoverCard || !hoverTitle || !hoverMeta) {
            return;
        }

        activeHoverEventId = event.id;
        hoverTitle.textContent = event.title || "Booking";
        hoverMeta.innerHTML = hoverPreviewHtml(event);
        hoverCard.hidden = false;
        positionHoverCard(jsEvent);
    }

    function hideHoverCard() {
        activeHoverEventId = null;
        if (!hoverCard) {
            return;
        }
        hoverCard.hidden = true;
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
            buildDetailRow("Requested By", requesterDisplay(booking)),
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
            detailRows.push(buildDetailRow("Target", deployment.target_key || "-"));
            detailRows.push(buildDetailRow("Requested Version", deployment.requested_version || "-"));
            detailRows.push(buildDetailRow("Testing Mode", deployment.testing_mode || "-"));
            detailRows.push(buildDetailRow("Servers", deployment.selected_servers_summary || "-"));
            detailRows.push(buildDetailRow("Service Types", (deployment.service_types || []).join(", ") || "-"));
        }

        detailsHost.className = "detail-list";
        detailsHost.innerHTML = detailRows.join("");
        if (bookingDetailsModal) {
            bookingDetailsModal.show();
        }
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

    function updateCalendarLayout() {
        if (!calendar) {
            return;
        }

        window.requestAnimationFrame(function () {
            calendar.updateSize();
        });
        window.setTimeout(function () {
            calendar.updateSize();
        }, 120);
        window.setTimeout(function () {
            calendar.updateSize();
            calendar.render();
        }, 360);
    }

    function clearFilters() {
        document.getElementById("filterEnvType").value = "";
        document.getElementById("filterBookingType").value = "";
        document.getElementById("filterStatus").value = "";
        document.getElementById("filterRequestedBy").value = "";
        refreshCalendar();
    }

    document.addEventListener("DOMContentLoaded", function () {
        bookingDetailsModal = new bootstrap.Modal(document.getElementById("bookingDetailsModal"));
        hoverCard = document.getElementById("calendarHoverCard");
        hoverTitle = document.getElementById("calendarHoverTitle");
        hoverMeta = document.getElementById("calendarHoverMeta");
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
            eventMouseEnter: function (info) {
                if (window.matchMedia("(hover: hover)").matches) {
                    showHoverCard(info.event, info.jsEvent);
                }
            },
            eventMouseLeave: function () {
                hideHoverCard();
            },
        });

        calendar.render();
        updateCalendarLayout();

        ["filterEnvType", "filterBookingType", "filterStatus"].forEach(function (id) {
            document.getElementById(id).addEventListener("change", refreshCalendar);
        });
        document.getElementById("filterRequestedBy").addEventListener("input", refreshCalendar);
        document.getElementById("clearFiltersButton").addEventListener("click", clearFilters);
        window.addEventListener("resize", updateCalendarLayout);
        document.addEventListener("mousemove", function (event) {
            if (activeHoverEventId && hoverCard && !hoverCard.hidden) {
                positionHoverCard(event);
            }
        });
        document.addEventListener("scroll", function () {
            if (activeHoverEventId) {
                hideHoverCard();
            }
        }, true);
        document.addEventListener("workspaceSidebarChange", updateCalendarLayout);

        if (window.ResizeObserver) {
            calendarResizeObserver = new ResizeObserver(function () {
                updateCalendarLayout();
            });
            calendarResizeObserver.observe(document.querySelector(".main-content"));
            calendarResizeObserver.observe(document.getElementById("calendar"));
        }
    });
}());
