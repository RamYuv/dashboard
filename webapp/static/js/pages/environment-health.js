(function () {
    const configElement = document.getElementById("environmentHealthConfig");

    if (!configElement) {
        return;
    }

    const config = JSON.parse(configElement.textContent);
    const API_URL = config.apiUrl;
    const REFRESH_SECONDS = Number(config.refreshSeconds || 30);

    let latestStatuses = config.statuses || [];
    let activeEnvIds = config.activeEnvs || [];
    let currentSummary = config.summary || {};

    function safeLower(value) {
        return (value || "unknown").toString().toLowerCase();
    }

    function calculatePercent(value, total) {
        if (!total || total === 0) {
            return "0.0%";
        }

        return ((value / total) * 100).toFixed(1) + "%";
    }

    function normalizeSummary(summary) {
        return {
            total: Number(summary.total || 0),
            healthy: Number(summary.healthy || 0),
            warning: Number(summary.warning || 0),
            critical: Number(summary.critical || 0),
            maintenance: Number(summary.maintenance || 0),
            last_updated: summary.last_updated || "-"
        };
    }

    function updateSummary(summary) {
        const normalized = normalizeSummary(summary);

        document.getElementById("totalCount").textContent = normalized.total;
        document.getElementById("healthyCount").textContent = normalized.healthy;
        document.getElementById("warningCount").textContent = normalized.warning;
        document.getElementById("criticalCount").textContent = normalized.critical;
        document.getElementById("maintenanceCount").textContent = normalized.maintenance;
        document.getElementById("healthyPercent").textContent = calculatePercent(normalized.healthy, normalized.total);
        document.getElementById("warningPercent").textContent = calculatePercent(normalized.warning, normalized.total);
        document.getElementById("criticalPercent").textContent = calculatePercent(normalized.critical, normalized.total);
        document.getElementById("maintenancePercent").textContent = calculatePercent(normalized.maintenance, normalized.total);
        document.getElementById("lastUpdated").textContent = normalized.last_updated;
    }

    function getEnvDisplayName(envType) {
        const key = (envType || "").toUpperCase();
        const names = {
            DEV: "Development (DEV)",
            ST: "System Testing (ST)",
            PROD: "Production",
            QA: "QA",
            UAT: "UAT",
            DR: "DR",
            TOOLS: "Tools"
        };

        return names[key] || envType;
    }

    function getEnvIcon(envType) {
        const key = (envType || "").toUpperCase();

        if (key === "DEV") return "fas fa-code";
        if (key === "ST") return "fas fa-flask";
        if (key === "PROD") return "fas fa-server";
        if (key === "QA") return "fas fa-check-double";
        if (key === "UAT") return "fas fa-users";
        if (key === "DR") return "fas fa-shield-alt";
        if (key === "TOOLS") return "fas fa-tools";

        return "fas fa-cog";
    }

    function groupStatuses(statuses) {
        return (statuses || []).reduce(function (groups, status) {
            const envType = status.env_type || "OTHER";

            if (!groups[envType]) {
                groups[envType] = [];
            }

            groups[envType].push(status);
            return groups;
        }, {});
    }

    function createCardHTML(status) {
        const serverStatus = safeLower(status.status);
        const envId = status.env_id || "UNKNOWN";
        const active = activeEnvIds.includes(envId) ? " active-booking" : "";
        const componentSummary = status.component_summary || {};
        const serverTypes = (status.server_types || []).join(", ");
        const tooltip = [
            envId + " - " + serverStatus.toUpperCase(),
            "Running: " + Number(componentSummary.running || 0),
            "Not running: " + Number(componentSummary.notrunning || 0),
            "Unknown: " + Number(componentSummary.unknown || 0),
            serverTypes ? "Server types: " + serverTypes : ""
        ].filter(Boolean).join(" | ");

        const redActive = serverStatus === "critical" ? "active" : "";
        const yellowActive = serverStatus === "warning" ? "active" : "";
        const greenActive = serverStatus === "healthy" ? "active" : "";
        const blueActive = serverStatus === "maintenance" ? "active" : "";

        let statusClass = serverStatus;
        if (!["healthy", "warning", "critical", "maintenance"].includes(statusClass)) {
            statusClass = "unknown";
        }

        return [
            '<div class="env-card' + active + '" title="' + tooltip + '">',
            '<div class="env-card-title">' + envId + '</div>',
            '<div class="traffic-light">',
            '<span class="light red ' + redActive + '"></span>',
            '<span class="light yellow ' + yellowActive + '"></span>',
            '<span class="light ' + (blueActive ? "blue" : "green") + ' ' + (blueActive || greenActive) + '"></span>',
            "</div>",
            '<div class="env-card-status ' + statusClass + '">',
            serverStatus.toUpperCase(),
            "</div>",
            "</div>"
        ].join("");
    }

    function renderDashboard() {
        const grouped = groupStatuses(latestStatuses);
        const container = document.getElementById("dashboardGroups");
        const envTypes = Object.keys(grouped).sort();

        if (envTypes.length === 0) {
            container.innerHTML = [
                '<div class="no-results">',
                '<i class="fas fa-search fa-2x mb-3"></i>',
                "<div>No server data available</div>",
                "</div>"
            ].join("");
            return;
        }

        container.innerHTML = envTypes.map(function (envType) {
            const servers = grouped[envType];
            const cards = servers.map(createCardHTML).join("");

            return [
                '<section class="group-card">',
                '<div class="group-header">',
                '<i class="' + getEnvIcon(envType) + '"></i>',
                "<h3>" + getEnvDisplayName(envType) + "</h3>",
                '<span class="group-count">- ' + servers.length + " Servers</span>",
                "</div>",
                '<div class="server-grid">',
                cards,
                "</div>",
                "</section>"
            ].join("");
        }).join("");
    }

    function refreshHealth(manual) {
        const button = document.getElementById("refreshButton");
        const originalHtml = button.innerHTML;

        if (manual) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing';
        }

        fetch(API_URL, { credentials: "include" })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }

                return response.json();
            })
            .then(function (data) {
                latestStatuses = data.statuses || [];
                activeEnvIds = data.active_envs || [];
                currentSummary = data.summary || {};
                updateSummary(currentSummary);
                renderDashboard();
            })
            .catch(function (error) {
                console.error("Failed to refresh environment health:", error);
            })
            .finally(function () {
                if (manual) {
                    button.disabled = false;
                    button.innerHTML = originalHtml;
                }
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById("refreshSecondsText").textContent = REFRESH_SECONDS;
        document.getElementById("refreshButton").addEventListener("click", function () {
            refreshHealth(true);
        });

        updateSummary(currentSummary);
        renderDashboard();

        window.setInterval(function () {
            refreshHealth(false);
        }, REFRESH_SECONDS * 1000);
    });
}());
