(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environments = pageData.environments || [];
    const serverTimezone = pageData.serverTimezone || "UTC";
    const reservationPolicy = pageData.reservationPolicy || {};
    const mutualReservationEnabled = !!reservationPolicy.mutual_env_reservation_enabled;
    let cachedBookings = [];

    function isBlockingDeploymentRequest(booking) {
        if (!booking || !booking.is_standalone_deployment_request) {
            return false;
        }
        return ["completed", "cancelled", "failed", "rejected"].indexOf(booking.lifecycle_status) === -1;
    }

    function getAvailabilitySuccessMessage() {
        if (!mutualReservationEnabled) {
            return "This environment appears available for the selected window.";
        }
        return "This environment appears available for the selected window, including deployment reservations.";
    }

    function populateQuickEnvOptions(envType) {
        common.populateEnvironmentOptions({
            selectId: "formEnvId",
            environments: environments,
            envType: envType,
        });
    }

    function showFormMessage(message, type) {
        common.setInlineMessage({
            messageId: "formMessage",
            textId: "formMessageText",
            message: message,
            type: type || "muted",
        });
    }

    function fetchBookingList() {
        return common.fetchJson("/api/bookings", { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to load current bookings");
                }
                cachedBookings = Array.isArray(result.data) ? result.data : [];
                return cachedBookings;
            })
            .catch(function () {
                cachedBookings = [];
                return [];
            });
    }

    function checkAvailability() {
        const startTime = document.getElementById("formStartTime").value;
        const endTime = document.getElementById("formEndTime").value;
        const envId = document.getElementById("formEnvId").value;

        if (!startTime || !endTime || !envId) {
            showFormMessage("Select environment, start time, and end time first.", "danger");
            return;
        }

        if (new Date(startTime) >= new Date(endTime)) {
            showFormMessage("End time must be after start time.", "danger");
            return;
        }

        return fetchBookingList().then(function () {
            const conflictingItem = cachedBookings.find(function (booking) {
                const overlaps = booking.env_id === envId &&
                    booking.lifecycle_status !== "cancelled" &&
                    new Date(startTime) < new Date(booking.end_time) &&
                    new Date(endTime) > new Date(booking.start_time);

                if (!overlaps) {
                    return false;
                }

                if (!booking.is_standalone_deployment_request) {
                    return true;
                }

                return mutualReservationEnabled && isBlockingDeploymentRequest(booking);
            });

            if (conflictingItem) {
                if (conflictingItem.is_standalone_deployment_request) {
                    showFormMessage("This environment already has a deployment reservation in the selected window.", "danger");
                    return;
                }
                showFormMessage("This environment is not available for the selected time.", "danger");
                return;
            }

            showFormMessage(getAvailabilitySuccessMessage(), "success");
        });
    }

    function updatePolicyHint() {
        if (!mutualReservationEnabled) {
            return;
        }
        showFormMessage("Bookings are checked against both reservations and deployment windows.", "muted");
    }

    function handleQuickBookingSubmit(event) {
        event.preventDefault();
        const startTime = document.getElementById("formStartTime").value;
        const endTime = document.getElementById("formEndTime").value;
        const envId = document.getElementById("formEnvId").value;
        const description = document.getElementById("formDescription").value.trim();

        if (!startTime || !endTime || !envId) {
            showFormMessage("Please fill start time, end time, and environment.", "danger");
            return;
        }

        if (new Date(startTime) >= new Date(endTime)) {
            showFormMessage("End time must be after start time.", "danger");
            return;
        }

        const payload = {
            env_id: envId,
            start_time: new Date(startTime).toISOString(),
            end_time: new Date(endTime).toISOString(),
            booking_type: "RESERVATION",
            description: description,
            user_timezone: common.getUserTimezone(serverTimezone),
        };

        common.fetchJson("/api/bookings", {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        })
            .then(function (result) {
                if (!result.ok) {
                    showFormMessage(result.data.error || "Booking failed. Please try again.", "danger");
                    return;
                }
                showFormMessage("Booking created successfully.", "success");
                document.getElementById("quickBookingForm").reset();
                populateQuickEnvOptions("");
                fetchBookingList();
            })
            .catch(function () {
                showFormMessage("Unable to reach the booking service.", "danger");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("formEnvType").addEventListener("change", function () {
            populateQuickEnvOptions(this.value);
        });
        document.getElementById("checkAvailabilityBtn").addEventListener("click", checkAvailability);
        document.getElementById("quickBookingForm").addEventListener("submit", handleQuickBookingSubmit);

        populateQuickEnvOptions("");
        fetchBookingList();
        updatePolicyHint();
    });
}());
