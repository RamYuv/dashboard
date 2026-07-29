(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    const environmentOperationsApiUrl = pageData.environmentOperationsApiUrl || "/api/environment-operations";
    let operations = pageData.operations || [];

    function showPageMessage(message, type) {
        common.setInlineMessage({
            messageId: "pageMessage",
            textId: "pageMessageText",
            message: message,
            type: type || "muted",
        });
    }

    function statusClass(status) {
        return "status-" + String(status || "").toLowerCase().replaceAll("_", "-");
    }

    function actionLabel(action) {
        return String(action || "")
            .replaceAll("_", " ")
            .replace(/\b\w/g, function (char) {
                return char.toUpperCase();
            });
    }

    function requesterDisplay(item) {
        const userId = String(item.requested_by || "").trim();
        const fallbackName = String(item.requested_by_name || "").trim();
        return '<div class="fw-semibold">' + common.escapeHtml(userId || fallbackName || "-") + "</div>";
    }

    function typePill(requestType) {
        const className = requestType === "DEPLOYMENT" ? "type-deployment" : "type-reservation";
        return '<span class="type-pill ' + className + '">' + common.escapeHtml(requestType === "DEPLOYMENT" ? "Deployment" : "Booking") + "</span>";
    }

    function formatStart(item) {
        return common.formatDisplayDate(item.window_start) || "-";
    }

    function formatEnd(item) {
        if (item.request_type === "DEPLOYMENT") {
            return "";
        }
        return common.formatDisplayDate(item.window_end) || "-";
    }

    function serviceDisplay(item) {
        return (item.tcs_service_names || []).join(", ") || "-";
    }

    function modeDisplay(item) {
        return item.tcs_deployment_mode || "-";
    }

    function versionDisplay(item) {
        return item.requested_version || "-";
    }

    function filteredOperations() {
        const status = document.getElementById("statusFilter").value;
        const type = document.getElementById("typeFilter").value;
        const query = document.getElementById("searchFilter").value.trim().toLowerCase();
        return operations.filter(function (item) {
            if (status && item.status !== status) {
                return false;
            }
            if (type && item.request_type !== type) {
                return false;
            }
            if (!query) {
                return true;
            }

            const haystack = [
                item.request_id,
                item.request_type,
                item.env_id,
                item.environment_display,
                item.env_type,
                item.requested_by,
                item.requested_by_name,
                item.requested_by_team,
                item.requested_by_display,
                (item.tcs_service_names || []).join(" "),
                item.tcs_deployment_mode,
                item.requested_version,
                item.target_key,
                item.selected_servers_summary,
                item.status,
                item.resolved_hosts_summary,
                item.description,
            ].join(" ").toLowerCase();
            return haystack.includes(query);
        });
    }

    function renderQueue() {
        const rows = filteredOperations();
        const body = document.getElementById("queueTableBody");
        const empty = document.getElementById("queueEmpty");

        if (!rows.length) {
            body.innerHTML = "";
            empty.style.display = "block";
            return;
        }

        empty.style.display = "none";
        body.innerHTML = rows.map(function (item) {
            const environmentLabel = item.environment_display || item.env_id || "-";
            const environmentNote = item.resolved_hosts_summary || item.env_type || "";
            const actions = item.request_type === "DEPLOYMENT"
                ? (item.available_actions || [])
                    .filter(function (action) {
                        return action !== "view";
                    })
                    .map(function (action) {
                        return '<button type="button" class="btn btn-sm btn-outline-primary" data-action="' +
                            common.escapeHtml(action) +
                            '" data-id="' +
                            common.escapeHtml(item.deployment_request_id) +
                            '">' +
                            common.escapeHtml(actionLabel(action)) +
                            "</button>";
                    })
                    .join("")
                : "";
            const descriptionNote = item.description
                ? '<div class="text-muted small">' + common.escapeHtml(item.description) + "</div>"
                : "";

            return '<tr>' +
                '<td><div class="fw-semibold">' + common.escapeHtml(environmentLabel) + '</div><div class="text-muted small">' + common.escapeHtml(environmentNote || "-") + "</div></td>" +
                "<td>" + typePill(item.request_type) + "</td>" +
                "<td>" + common.escapeHtml(formatStart(item)) + "</td>" +
                "<td>" + common.escapeHtml(formatEnd(item)) + "</td>" +
                "<td>" + requesterDisplay(item) + "</td>" +
                "<td>" + common.escapeHtml(serviceDisplay(item)) + "</td>" +
                "<td>" + common.escapeHtml(modeDisplay(item)) + "</td>" +
                "<td>" + common.escapeHtml(versionDisplay(item)) + '</td>' +
                '<td><span class="status-pill ' + common.escapeHtml(statusClass(item.status)) + '">' + common.escapeHtml(item.status_label || item.status || "-") + "</span></td>" +
                '<td><div class="table-actions">' + (actions || '<span class="text-muted small">View only</span>') + "</div></td>" +
                "</tr>";
        }).join("");
    }

    function fetchQueue() {
        return common.fetchJson(environmentOperationsApiUrl, { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to load environment operations.");
                }
                operations = result.data.operations || [];
                renderQueue();
            })
            .catch(function (error) {
                showPageMessage(error.message, "danger");
            });
    }

    function buildActionPayload(action) {
        const payload = { action: action };
        if (["reject", "mark_failed", "cancel"].includes(action)) {
            const reason = window.prompt("Enter a reason:");
            if (reason === null) {
                return null;
            }
            payload.reason = reason.trim();
        }
        return payload;
    }

    function applyAction(requestId, action) {
        const payload = buildActionPayload(action);
        if (!payload) {
            return;
        }

        common.fetchJson("/api/deployment-requests/" + encodeURIComponent(requestId) + "/actions", {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to update deployment request.");
                }
                showPageMessage(result.data.message || "Deployment request updated.", "success");
                return fetchQueue();
            })
            .catch(function (error) {
                showPageMessage(error.message, "danger");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("statusFilter").addEventListener("change", renderQueue);
        document.getElementById("typeFilter").addEventListener("change", renderQueue);
        document.getElementById("searchFilter").addEventListener("input", renderQueue);
        document.getElementById("refreshQueueBtn").addEventListener("click", fetchQueue);
        document.getElementById("queueTableBody").addEventListener("click", function (event) {
            const button = event.target.closest("button[data-action][data-id]");
            if (!button) {
                return;
            }
            applyAction(button.dataset.id, button.dataset.action);
        });

        renderQueue();
    });
}());
