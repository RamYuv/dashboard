(function () {
    const common = window.WorkspaceCommon;
    const pageData = window.pageData || {};
    let deploymentRequests = pageData.deploymentRequests || [];
    const statusLabels = pageData.statusLabels || {};

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

    function getStatusLabel(status) {
        return statusLabels[status] || status;
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
        const fullName = String(item.requested_by_name || "").trim();
        if (!fullName || fullName === userId) {
            return common.escapeHtml(userId || "-");
        }
        return '<div class="fw-semibold">' + common.escapeHtml(userId) + '</div>' +
            '<div class="text-muted small">' + common.escapeHtml(fullName) + "</div>";
    }

    function filteredRequests() {
        const status = document.getElementById("statusFilter").value;
        const query = document.getElementById("searchFilter").value.trim().toLowerCase();
        return deploymentRequests.filter(function (item) {
            if (status && item.status !== status) {
                return false;
            }
            if (!query) {
                return true;
            }

            const haystack = [
                item.deployment_request_id,
                item.env_id,
                item.environment_display,
                item.requested_env_type,
                item.requested_by,
                item.requested_by_name,
                item.target_key,
                item.requested_version,
                item.status,
                item.resolved_hosts_summary,
            ].join(" ").toLowerCase();
            return haystack.includes(query);
        });
    }

    function renderQueue() {
        const rows = filteredRequests();
        const body = document.getElementById("queueTableBody");
        const empty = document.getElementById("queueEmpty");

        if (!rows.length) {
            body.innerHTML = "";
            empty.style.display = "block";
            return;
        }

        empty.style.display = "none";
        body.innerHTML = rows.map(function (item) {
            const packages = (item.selected_packages || []).join(", ") || "-";
            const environmentLabel = item.environment_display || item.env_id || "-";
            const resolvedHosts = item.resolved_hosts_summary || "";
            const actions = (item.available_actions || [])
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
                .join("");

            return '<tr>' +
                '<td><div class="fw-semibold">' + common.escapeHtml(item.deployment_request_id) + '</div><div class="text-muted small">' + common.escapeHtml(packages) + "</div></td>" +
                '<td><div class="fw-semibold">' + common.escapeHtml(environmentLabel) + '</div><div class="text-muted small">' + common.escapeHtml(resolvedHosts || "Host not resolved") + "</div></td>" +
                "<td>" + common.escapeHtml(common.formatDisplayDate(item.planned_start_time)) + "</td>" +
                "<td>" + requesterDisplay(item) + "</td>" +
                "<td>" + common.escapeHtml(item.target_key) + "</td>" +
                "<td>" + common.escapeHtml(item.requested_version) + '</td>' +
                '<td><span class="status-pill ' + common.escapeHtml(statusClass(item.status)) + '">' + common.escapeHtml(getStatusLabel(item.status)) + "</span></td>" +
                '<td><div class="table-actions">' + (actions || '<span class="text-muted small">No actions</span>') + "</div></td>" +
                "</tr>";
        }).join("");
    }

    function fetchQueue() {
        const status = document.getElementById("statusFilter").value;
        const params = new URLSearchParams({ scope: "env" });
        if (status) {
            params.set("status", status);
        }

        return common.fetchJson("/api/deployment-requests?" + params.toString(), { credentials: "include" })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.data.error || "Unable to load deployment requests.");
                }
                deploymentRequests = result.data.deployment_requests || [];
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
        document.getElementById("statusFilter").addEventListener("change", fetchQueue);
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
