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
        escapeHtml: escapeHtml,
        fetchJson: fetchJson,
        formatDisplayDate: formatDisplayDate,
        formatLocalInput: formatLocalInput,
        getUserTimezone: getUserTimezone,
        inferEnvType: inferEnvType,
        parseJsonResponse: parseJsonResponse,
        populateEnvironmentOptions: populateEnvironmentOptions,
        resetSelect: resetSelect,
        setInlineMessage: setInlineMessage,
        showAlertHost: showAlertHost,
    };
}());
