(function () {
    function parseJsonResponse(response) {
        return response.text().then(function (text) {
            let data = {};
            if (text) {
                try {
                    data = JSON.parse(text);
                } catch (error) {
                    data = { error: "Server returned an invalid response." };
                }
            }
            return { ok: response.ok, data: data };
        });
    }

    function fetchJson(url, options) {
        return fetch(url, options).then(parseJsonResponse);
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatLocalInput(value) {
        return value ? moment.utc(value).local().format("YYYY-MM-DDTHH:mm") : "";
    }

    function formatDisplayDate(value) {
        return value ? moment.utc(value).local().format("YYYY-MM-DD HH:mm") : "";
    }

    function getUserTimezone(fallback) {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || fallback || "UTC";
    }

    function initDateTimeTimezoneHints() {
        const nodes = document.querySelectorAll(".js-datetime-timezone");
        nodes.forEach(function (node) {
            const fallback = node.getAttribute("data-fallback-timezone") || "UTC";
            const timezone = getUserTimezone(fallback);
            node.textContent = "(Timezone: " + timezone + ")";
        });
    }

    function buildLocalDateTimeValue(options) {
        const config = options || {};
        const value = new Date();
        value.setSeconds(0, 0);
        value.setHours(
            Number.isFinite(config.hours) ? config.hours : value.getHours(),
            Number.isFinite(config.minutes) ? config.minutes : value.getMinutes(),
            0,
            0
        );
        if (Number.isFinite(config.dayOffset) && config.dayOffset !== 0) {
            value.setDate(value.getDate() + config.dayOffset);
        }

        const pad = function (part) {
            return String(part).padStart(2, "0");
        };

        return [
            value.getFullYear(),
            pad(value.getMonth() + 1),
            pad(value.getDate())
        ].join("-") + "T" + [
            pad(value.getHours()),
            pad(value.getMinutes())
        ].join(":");
    }

    function padTimePart(value) {
        return String(value).padStart(2, "0");
    }

    function roundDateToSlot(date, slotMinutes, roundUp) {
        const slot = Math.max(1, Number(slotMinutes) || 30);
        const rounded = new Date(date.getTime());
        rounded.setSeconds(0, 0);

        const totalMinutes = rounded.getHours() * 60 + rounded.getMinutes();
        const nextMinutes = roundUp
            ? Math.ceil(totalMinutes / slot) * slot
            : Math.floor(totalMinutes / slot) * slot;

        rounded.setHours(0, nextMinutes, 0, 0);
        return rounded;
    }

    function formatDateInputValue(date) {
        return [
            date.getFullYear(),
            padTimePart(date.getMonth() + 1),
            padTimePart(date.getDate())
        ].join("-");
    }

    function formatTimeSlotValue(date) {
        return padTimePart(date.getHours()) + ":" + padTimePart(date.getMinutes());
    }

    function buildLocalDateValue(options) {
        const config = options || {};
        const value = new Date();
        value.setHours(0, 0, 0, 0);

        if (Number.isFinite(config.dayOffset) && config.dayOffset !== 0) {
            value.setDate(value.getDate() + config.dayOffset);
        }

        return formatDateInputValue(value);
    }

    function buildLocalDateTimeParts(options) {
        const config = options || {};
        const slotMinutes = Math.max(1, Number(config.slotMinutes) || 30);
        const roundUp = config.roundUp !== false;
        const base = roundDateToSlot(new Date(), slotMinutes, roundUp);

        if (Number.isFinite(config.addMinutes) && config.addMinutes !== 0) {
            base.setMinutes(base.getMinutes() + config.addMinutes);
        }
        if (Number.isFinite(config.dayOffset) && config.dayOffset !== 0) {
            base.setDate(base.getDate() + config.dayOffset);
        }

        return {
            date: formatDateInputValue(base),
            time: formatTimeSlotValue(base),
        };
    }

    function getTodayDateString() {
        return buildLocalDateTimeParts({ slotMinutes: 30, roundUp: false }).date;
    }

    function populateTimeSlotOptions(config) {
        const select = typeof config.selectId === "string"
            ? document.getElementById(config.selectId)
            : config.select;
        const placeholder = config.placeholder || "Select time...";
        const selectedValue = config.selectedValue || "";
        const slotMinutes = Math.max(1, Number(config.slotMinutes) || 30);
        if (!select) {
            return;
        }

        select.innerHTML = '<option value="">' + escapeHtml(placeholder) + "</option>";

        for (let totalMinutes = 0; totalMinutes < 24 * 60; totalMinutes += slotMinutes) {
            const hours = Math.floor(totalMinutes / 60);
            const minutes = totalMinutes % 60;
            const value = padTimePart(hours) + ":" + padTimePart(minutes);
            select.insertAdjacentHTML(
                "beforeend",
                '<option value="' + escapeHtml(value) + '">' + escapeHtml(value) + "</option>"
            );
        }

        if (selectedValue) {
            select.value = selectedValue;
        }
    }

    function combineLocalDateAndTime(dateValue, timeValue) {
        if (!dateValue || !timeValue) {
            return "";
        }
        return dateValue + "T" + timeValue;
    }

    function isPastDateTimeSelection(dateValue, timeValue) {
        const combined = combineLocalDateAndTime(dateValue, timeValue);
        if (!combined) {
            return false;
        }

        return new Date(combined).getTime() < Date.now();
    }

    function applyMinDate(input) {
        const resolvedInput = typeof input === "string"
            ? document.getElementById(input)
            : input;
        if (!resolvedInput) {
            return;
        }

        resolvedInput.min = getTodayDateString();
    }

    function validateNoPastDate(input, onInvalid) {
        const resolvedInput = typeof input === "string"
            ? document.getElementById(input)
            : input;
        if (!resolvedInput || !resolvedInput.value) {
            return true;
        }

        const today = getTodayDateString();
        if (resolvedInput.value >= today) {
            return true;
        }

        resolvedInput.value = today;
        if (typeof onInvalid === "function") {
            onInvalid();
        }
        return false;
    }

    function validateNoPastDateTime(dateInput, timeInput, onInvalid) {
        const resolvedDateInput = typeof dateInput === "string"
            ? document.getElementById(dateInput)
            : dateInput;
        const resolvedTimeInput = typeof timeInput === "string"
            ? document.getElementById(timeInput)
            : timeInput;
        if (!resolvedDateInput || !resolvedTimeInput || !resolvedDateInput.value || !resolvedTimeInput.value) {
            return true;
        }

        if (!isPastDateTimeSelection(resolvedDateInput.value, resolvedTimeInput.value)) {
            return true;
        }

        resolvedTimeInput.value = "";
        if (typeof onInvalid === "function") {
            onInvalid();
        }
        return false;
    }

    function populateEnvironmentOptions(config) {
        const select = document.getElementById(config.selectId);
        const environments = config.environments || [];
        const envType = config.envType || "";
        const selectedEnvId = config.selectedEnvId || "";
        const placeholder = config.placeholder || "Select environment...";
        if (!select) {
            return;
        }

        const filtered = envType
            ? environments.filter(function (env) {
                return env.env_type === envType;
            })
            : environments;

        select.innerHTML = '<option value="">' + escapeHtml(placeholder) + "</option>";
        filtered.forEach(function (env) {
            select.insertAdjacentHTML(
                "beforeend",
                '<option value="' + escapeHtml(env.env_id) + '">' +
                escapeHtml(env.env_id + " (" + env.env_type + ")") +
                "</option>"
            );
        });

        if (selectedEnvId) {
            select.value = selectedEnvId;
        }
    }

    function setInlineMessage(config) {
        const messageEl = document.getElementById(config.messageId);
        const textEl = document.getElementById(config.textId);
        if (!messageEl || !textEl) {
            return;
        }

        textEl.textContent = config.message;
        messageEl.className = "form-message " + (config.type || "muted");
        messageEl.style.display = "flex";
    }

    function showAlertHost(config) {
        const host = document.getElementById(config.hostId);
        if (!host) {
            return;
        }

        const type = config.type || "info";
        const dismissible = config.dismissible !== false;
        const button = dismissible
            ? '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>'
            : "";
        const extraClass = dismissible ? " alert-dismissible fade show" : "";
        host.innerHTML = '<div class="alert alert-' + escapeHtml(type) + extraClass + '" role="alert">' +
            escapeHtml(config.message || "") +
            button +
            "</div>";
        host.style.display = "block";
    }

    function clearHost(hostId) {
        const host = document.getElementById(hostId);
        if (!host) {
            return;
        }
        host.innerHTML = "";
        host.style.display = "none";
    }

    function resetSelect(selectId, placeholder) {
        const select = document.getElementById(selectId);
        if (!select) {
            return;
        }
        select.innerHTML = '<option value="">' + escapeHtml(placeholder || "Select...") + "</option>";
    }

    function inferEnvType(environments, envId) {
        const match = (environments || []).find(function (env) {
            return env.env_id === envId;
        });
        return match ? match.env_type : "";
    }

    window.WorkspaceCommon = {
        clearHost: clearHost,
        combineLocalDateAndTime: combineLocalDateAndTime,
        applyMinDate: applyMinDate,
        buildLocalDateTimeParts: buildLocalDateTimeParts,
        buildLocalDateValue: buildLocalDateValue,
        escapeHtml: escapeHtml,
        fetchJson: fetchJson,
        buildLocalDateTimeValue: buildLocalDateTimeValue,
        formatDisplayDate: formatDisplayDate,
        formatLocalInput: formatLocalInput,
        getTodayDateString: getTodayDateString,
        getUserTimezone: getUserTimezone,
        initDateTimeTimezoneHints: initDateTimeTimezoneHints,
        inferEnvType: inferEnvType,
        isPastDateTimeSelection: isPastDateTimeSelection,
        parseJsonResponse: parseJsonResponse,
        populateEnvironmentOptions: populateEnvironmentOptions,
        populateTimeSlotOptions: populateTimeSlotOptions,
        resetSelect: resetSelect,
        setInlineMessage: setInlineMessage,
        showAlertHost: showAlertHost,
        validateNoPastDate: validateNoPastDate,
        validateNoPastDateTime: validateNoPastDateTime,
    };

    document.addEventListener("DOMContentLoaded", initDateTimeTimezoneHints);
}());
