(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environments = pageData.environments || [];
    const serverTimezone = pageData.serverTimezone || "UTC";
    const reservationPolicy = pageData.reservationPolicy || {};
    const currentDeploymentsApiUrl = pageData.currentDeploymentsApiUrl || "/api/current-deployments";
    const mutualReservationEnabled = !!reservationPolicy.mutual_env_reservation_enabled;
    const RUNTIME_PLACEHOLDER_MESSAGE = "Select an environment to view the currently deployed TCS version, service, and mode.";
    const RUNTIME_LOADING_MESSAGE = "Loading current TCS runtime...";
    const RUNTIME_EMPTY_MESSAGE = "No current TCS runtime details were found for the selected environment.";
    const RUNTIME_ERROR_MESSAGE = "Unable to load current TCS runtime right now.";
    let cachedBookings = [];
    const queryParams = new URLSearchParams(window.location.search);
    const initialEnvId = queryParams.get("env_id") || "";
    const initialStart = queryParams.get("start") || "";
    const initialEnd = queryParams.get("end") || "";
    let runtimeRequestToken = 0;
    let availabilityToast = null;
    const elements = {};

    function cacheElements() {
        elements.form = document.getElementById("quickBookingForm");
        elements.envType = document.getElementById("formEnvType");
        elements.envId = document.getElementById("formEnvId");
        elements.startDate = document.getElementById("formStartDate");
        elements.startTime = document.getElementById("formStartTime");
        elements.endDate = document.getElementById("formEndDate");
        elements.endTime = document.getElementById("formEndTime");
        elements.description = document.getElementById("formDescription");
        elements.checkAvailabilityBtn = document.getElementById("checkAvailabilityBtn");
        elements.runtimeEmpty = document.getElementById("currentTcsRuntimeEmpty");
        elements.runtimeDetails = document.getElementById("currentTcsRuntimeDetails");
        elements.availabilityToast = document.getElementById("availabilityToast");
        elements.availabilityToastBody = document.getElementById("availabilityToastBody");
    }

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

    function uniqueValues(values) {
        return (values || []).filter(function (value, index, items) {
            return value && items.indexOf(value) === index;
        });
    }

    function extractVersionDate(version) {
        const value = String(version || "").trim();
        const match = value.match(/_(\d{8})$/);
        return match ? match[1] : "";
    }

    function selectPreferredVersion(versions) {
        const candidates = uniqueValues(versions);
        if (!candidates.length) {
            return "";
        }

        return candidates.reduce(function (best, candidate) {
            const bestDate = extractVersionDate(best);
            const candidateDate = extractVersionDate(candidate);

            if (!best) {
                return candidate;
            }
            if (candidateDate && (!bestDate || candidateDate > bestDate)) {
                return candidate;
            }
            return best;
        }, "");
    }

    function setRuntimeField(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value || "-";
        }
    }

    function showRuntimePlaceholder(message) {
        if (elements.runtimeEmpty) {
            elements.runtimeEmpty.textContent = message;
            elements.runtimeEmpty.hidden = false;
        }
        if (elements.runtimeDetails) {
            elements.runtimeDetails.hidden = true;
        }
        setRuntimeField("currentTcsRuntimeVersion", "-");
        setRuntimeField("currentTcsRuntimeService", "-");
        setRuntimeField("currentTcsRuntimeMode", "-");
    }

    function showRuntimeDetails(runtime) {
        if (elements.runtimeEmpty) {
            elements.runtimeEmpty.hidden = true;
        }
        if (elements.runtimeDetails) {
            elements.runtimeDetails.hidden = false;
        }

        setRuntimeField("currentTcsRuntimeVersion", runtime.version);
        setRuntimeField("currentTcsRuntimeService", runtime.tcsServiceNames);
        setRuntimeField("currentTcsRuntimeMode", runtime.tcsDeploymentModes);
    }

    function aggregateTcsRuntime(rows) {
        const versions = uniqueValues(rows.map(function (row) {
            return (row.current_version || "").trim();
        }).filter(Boolean));
        const serviceTypes = uniqueValues(rows.map(function (row) {
            return (row.tcs_service_name || "").trim();
        }).filter(Boolean));
        const testingModes = uniqueValues(rows.map(function (row) {
            return (row.tcs_deployment_mode || "").trim();
        }).filter(Boolean));

        return {
            version: selectPreferredVersion(versions) || "-",
            tcsServiceNames: serviceTypes[0] || "-",
            tcsDeploymentModes: testingModes.join(", ") || "-",
        };
    }

    function loadCurrentTcsRuntime(envId) {
        const selectedEnvId = String(envId || "").trim();
        runtimeRequestToken += 1;
        const requestToken = runtimeRequestToken;

        if (!selectedEnvId) {
            showRuntimePlaceholder(RUNTIME_PLACEHOLDER_MESSAGE);
            return Promise.resolve();
        }

        showRuntimePlaceholder(RUNTIME_LOADING_MESSAGE);

        const params = new URLSearchParams({
            env_scope_type: "ENV",
            env_id: selectedEnvId,
            target_key: "TCS_APP",
        });

        return common.fetchJson(currentDeploymentsApiUrl + "?" + params.toString(), {
            credentials: "include",
        }).then(function (result) {
            if (requestToken !== runtimeRequestToken) {
                return;
            }

            if (!result.ok) {
                throw new Error(result.data.error || "Unable to load current TCS runtime.");
            }

            const rows = Array.isArray(result.data.current_deployments)
                ? result.data.current_deployments
                : [];

            if (!rows.length) {
                showRuntimePlaceholder(RUNTIME_EMPTY_MESSAGE);
                return;
            }

            showRuntimeDetails(aggregateTcsRuntime(rows));
        }).catch(function () {
            if (requestToken !== runtimeRequestToken) {
                return;
            }
            showRuntimePlaceholder(RUNTIME_ERROR_MESSAGE);
        });
    }

    function applyDefaultDateTimeValues(force) {
        common.populateTimeSlotOptions({
            selectId: "formStartTime",
            placeholder: "Select time...",
            selectedValue: elements.startTime ? elements.startTime.value : "",
            slotMinutes: 30,
        });
        common.populateTimeSlotOptions({
            selectId: "formEndTime",
            placeholder: "Select time...",
            selectedValue: elements.endTime ? elements.endTime.value : "",
            slotMinutes: 30,
        });

        if (elements.startDate && elements.startTime && (force || !elements.startDate.value || !elements.startTime.value)) {
            const startSlot = common.buildLocalDateTimeParts({ slotMinutes: 30, roundUp: true });
            elements.startDate.value = startSlot.date;
            elements.startTime.value = startSlot.time;
        }
        if (elements.endDate && elements.endTime && (force || !elements.endDate.value || !elements.endTime.value)) {
            const endSlot = common.buildLocalDateTimeParts({ slotMinutes: 30, roundUp: true, addMinutes: 60 });
            elements.endDate.value = endSlot.date;
            elements.endTime.value = endSlot.time;
        }
    }

    function applyDateRestrictions() {
        common.applyMinDate(elements.startDate);
        common.applyMinDate(elements.endDate);
    }

    function showPastTimePopup() {
        window.alert("Previous time is not allowed.");
    }

    function validateDateNotInPast(dateElement) {
        return common.validateNoPastDate(dateElement, function () {
            showFormMessage("Previous booking date is not allowed.", "danger");
            window.alert("Previous booking date is not allowed.");
        });
    }

    function validateTimeNotInPast(dateElement, timeElement) {
        return common.validateNoPastDateTime(dateElement, timeElement, function () {
            showFormMessage("Previous time is not allowed.", "danger");
            showPastTimePopup();
        });
    }

    function validateBookingWindowNotInPast() {
        if (common.isPastDateTimeSelection(elements.startDate.value, elements.startTime.value)) {
            showFormMessage("Previous time is not allowed.", "danger");
            showPastTimePopup();
            return false;
        }

        if (common.isPastDateTimeSelection(elements.endDate.value, elements.endTime.value)) {
            showFormMessage("Previous time is not allowed.", "danger");
            showPastTimePopup();
            return false;
        }

        return true;
    }

    function applyInitialEnvironmentSelection() {
        if (!initialEnvId) {
            return;
        }

        const selectedEnvironment = environments.find(function (env) {
            return env.env_id === initialEnvId;
        });
        if (!selectedEnvironment) {
            return;
        }

        elements.envType.value = selectedEnvironment.env_type || "";
        populateQuickEnvOptions(selectedEnvironment.env_type || "");
        elements.envId.value = selectedEnvironment.env_id;
        loadCurrentTcsRuntime(selectedEnvironment.env_id);
        showFormMessage(
            "Environment " + selectedEnvironment.env_id + " was preselected from the health dashboard.",
            "muted"
        );
    }

    function splitLocalDateTime(value) {
        const rawValue = String(value || "").trim();
        if (!rawValue || rawValue.indexOf("T") === -1) {
            return null;
        }

        const parts = rawValue.split("T");
        const dateValue = parts[0] || "";
        const timeValue = (parts[1] || "").slice(0, 5);
        if (!dateValue || !timeValue) {
            return null;
        }

        return {
            date: dateValue,
            time: timeValue,
        };
    }

    function applyInitialDateRangeSelection() {
        const startParts = splitLocalDateTime(initialStart);
        const endParts = splitLocalDateTime(initialEnd);
        if (!startParts) {
            return;
        }

        if (elements.startDate) {
            elements.startDate.value = startParts.date;
        }
        if (elements.startTime) {
            elements.startTime.value = startParts.time;
        }

        if (endParts) {
            if (elements.endDate) {
                elements.endDate.value = endParts.date;
            }
            if (elements.endTime) {
                elements.endTime.value = endParts.time;
            }
        }

        showFormMessage("Booking window was prefilled from the calendar selection.", "muted");
    }

    function showFormMessage(message, type) {
        common.setInlineMessage({
            messageId: "formMessage",
            textId: "formMessageText",
            message: message,
            type: type || "muted",
        });
    }

    function showAvailabilityToast(message) {
        if (elements.availabilityToastBody) {
            elements.availabilityToastBody.textContent = message;
        }
        if (availabilityToast) {
            availabilityToast.show();
        }
    }

    function getFormValues() {
        const startDateTime = common.combineLocalDateAndTime(elements.startDate.value, elements.startTime.value);
        const endDateTime = common.combineLocalDateAndTime(elements.endDate.value, elements.endTime.value);

        return {
            startTime: startDateTime,
            endTime: endDateTime,
            envId: elements.envId.value,
            description: elements.description.value.trim(),
        };
    }

    function hasInvalidTimeRange(startTime, endTime) {
        return new Date(startTime) >= new Date(endTime);
    }

    function resetBookingForm() {
        elements.form.reset();
        populateQuickEnvOptions("");
        applyDefaultDateTimeValues(true);
        showRuntimePlaceholder(RUNTIME_PLACEHOLDER_MESSAGE);
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
        const values = getFormValues();

        if (!values.startTime || !values.endTime || !values.envId) {
            showFormMessage("Select environment, start date/time, and end date/time first.", "danger");
            return;
        }

        if (!validateBookingWindowNotInPast()) {
            return;
        }

        if (hasInvalidTimeRange(values.startTime, values.endTime)) {
            showFormMessage("End time must be after start time.", "danger");
            return;
        }

        return fetchBookingList().then(function () {
            const conflictingItem = cachedBookings.find(function (booking) {
                const overlaps = booking.env_id === values.envId &&
                    booking.lifecycle_status !== "cancelled" &&
                    new Date(values.startTime) < new Date(booking.end_time) &&
                    new Date(values.endTime) > new Date(booking.start_time);

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
            showAvailabilityToast(getAvailabilitySuccessMessage());
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
        const values = getFormValues();

        if (!values.startTime || !values.endTime || !values.envId) {
            showFormMessage("Please fill start date/time, end date/time, and environment.", "danger");
            return;
        }

        if (!validateBookingWindowNotInPast()) {
            return;
        }

        if (hasInvalidTimeRange(values.startTime, values.endTime)) {
            showFormMessage("End time must be after start time.", "danger");
            return;
        }

        const payload = {
            env_id: values.envId,
            start_time: new Date(values.startTime).toISOString(),
            end_time: new Date(values.endTime).toISOString(),
            booking_type: "RESERVATION",
            description: values.description,
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
                resetBookingForm();
                fetchBookingList();
            })
            .catch(function () {
                showFormMessage("Unable to reach the booking service.", "danger");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        cacheElements();

        if (elements.availabilityToast) {
            availabilityToast = new bootstrap.Toast(elements.availabilityToast, {
                autohide: true,
                delay: 3200,
            });
        }

        elements.envType.addEventListener("change", function () {
            populateQuickEnvOptions(this.value);
            showRuntimePlaceholder(RUNTIME_PLACEHOLDER_MESSAGE);
        });
        elements.envId.addEventListener("change", function () {
            loadCurrentTcsRuntime(this.value);
        });
        elements.startDate.addEventListener("change", function () {
            validateDateNotInPast(elements.startDate);
            if (elements.endDate && elements.endDate.value && elements.endDate.value < elements.startDate.value) {
                elements.endDate.value = elements.startDate.value;
            }
            validateTimeNotInPast(elements.startDate, elements.startTime);
        });
        elements.endDate.addEventListener("change", function () {
            validateDateNotInPast(elements.endDate);
            validateTimeNotInPast(elements.endDate, elements.endTime);
        });
        elements.startTime.addEventListener("change", function () {
            validateTimeNotInPast(elements.startDate, elements.startTime);
        });
        elements.endTime.addEventListener("change", function () {
            validateTimeNotInPast(elements.endDate, elements.endTime);
        });
        elements.checkAvailabilityBtn.addEventListener("click", checkAvailability);
        elements.form.addEventListener("submit", handleQuickBookingSubmit);

        populateQuickEnvOptions("");
        applyDateRestrictions();
        applyDefaultDateTimeValues(false);
        applyInitialDateRangeSelection();
        showRuntimePlaceholder(RUNTIME_PLACEHOLDER_MESSAGE);
        fetchBookingList();
        updatePolicyHint();
        applyInitialEnvironmentSelection();
    });
}());
