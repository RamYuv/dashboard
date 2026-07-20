(function () {
    const configElement = document.getElementById("environmentHealthConfig");

    if (!configElement) {
        return;
    }

    const config = JSON.parse(configElement.textContent);
    const API_URL = config.apiUrl;
    const BOOKING_GRID_URL = config.bookingGridUrl;
    const ACCESS_SESSION_API_URL = config.accessSessionApiUrl;
    const CLOSE_ACCESS_SESSION_API_URL = config.closeAccessSessionApiUrl;
    const ACCESS_LINK_API_URL = config.accessLinkApiUrl;
    const ACCESS_ACTIONS = config.accessActions || {};
    const REFRESH_SECONDS = Number(config.refreshSeconds || 30);
    const SIDEBAR_STATE_KEY = "envDashboardSidebarCollapsed";
    const USER_ROLE = (config.userRole || "").toString().toLowerCase();
    const BOOKABLE_ENV_IDS = (config.bookableEnvIds || []).map(function (envId) {
        return (envId || "").toString().toUpperCase();
    });
    const terminalSessionWindows = new Map();

    let latestStatuses = config.statuses || [];
    let activeEnvIds = config.activeEnvs || [];
    let currentSummary = config.summary || {};
    let activeContextEnv = null;

    function safeLower(value) {
        return (value || "unknown").toString().toLowerCase();
    }

    function escapeAttribute(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatBrowserTimestamp(value) {
        if (!value || value === "-" || value === "Never") {
            return value || "-";
        }

        if (window.moment) {
            const parsed = moment.utc(value);
            if (parsed.isValid()) {
                return parsed.local().format("YYYY-MM-DD HH:mm:ss");
            }
        }

        const fallbackDate = new Date(value);
        if (Number.isNaN(fallbackDate.getTime())) {
            return value;
        }

        const pad = function (part) {
            return String(part).padStart(2, "0");
        };

        return [
            fallbackDate.getFullYear(),
            pad(fallbackDate.getMonth() + 1),
            pad(fallbackDate.getDate())
        ].join("-") + " " + [
            pad(fallbackDate.getHours()),
            pad(fallbackDate.getMinutes()),
            pad(fallbackDate.getSeconds())
        ].join(":");
    }

    function normalizeSummary(summary) {
        return {
            total: Number(summary.total || 0),
            healthy: Number(summary.healthy || 0),
            warning: Number(summary.warning || 0),
            critical: Number(summary.critical || 0),
            maintenance: Number(summary.maintenance || 0),
            last_updated: formatBrowserTimestamp(summary.last_updated || "-")
        };
    }

    function updateSummary(summary) {
        const normalized = normalizeSummary(summary);

        document.getElementById("totalCount").textContent = normalized.total;
        document.getElementById("healthyCount").textContent = normalized.healthy;
        document.getElementById("warningCount").textContent = normalized.warning;
        document.getElementById("criticalCount").textContent = normalized.critical;
        document.getElementById("maintenanceCount").textContent = normalized.maintenance;
        document.getElementById("lastUpdated").textContent = normalized.last_updated;
    }

    function getGroupDisplayName(teamName) {
        const value = (teamName || "").toString().trim();
        if (!value) {
            return "Unassigned";
        }
        return value.toUpperCase();
    }

    function canBookEnvironment(envId) {
        if (USER_ROLE === "admin") {
            return true;
        }
        return BOOKABLE_ENV_IDS.indexOf((envId || "").toString().toUpperCase()) !== -1;
    }

    function clearTooltipPlacement(card) {
        if (!card) {
            return;
        }
        card.classList.remove("tooltip-align-left", "tooltip-align-right", "tooltip-align-center", "tooltip-below");
    }

    function updateTooltipPlacement(card) {
        if (!card) {
            return;
        }

        clearTooltipPlacement(card);

        const rect = card.getBoundingClientRect();
        const mainContent = document.querySelector(".main-content");
        const mainRect = mainContent
            ? mainContent.getBoundingClientRect()
            : { left: 0, right: window.innerWidth || document.documentElement.clientWidth || 0 };
        const availableWidth = Math.max(220, mainRect.right - mainRect.left - 24);
        const estimatedTooltipWidth = Math.min(360, availableWidth);
        const centeredLeft = rect.left + (rect.width / 2) - (estimatedTooltipWidth / 2);
        const centeredRight = rect.left + (rect.width / 2) + (estimatedTooltipWidth / 2);
        const safeLeft = mainRect.left + 12;
        const safeRight = mainRect.right - 12;
        const tooltipLineCount = ((card.dataset.tooltip || "").match(/\n/g) || []).length + 1;
        const estimatedTooltipHeight = Math.min(320, Math.max(72, (tooltipLineCount * 20) + 24));
        const topBar = document.querySelector(".top-bar, .navbar, header");
        const topBarBottom = topBar ? topBar.getBoundingClientRect().bottom : 0;
        const safeTop = Math.max(12, topBarBottom + 12);

        if (rect.top - estimatedTooltipHeight < safeTop) {
            card.classList.add("tooltip-below");
        }

        if (centeredLeft < safeLeft) {
            card.classList.add("tooltip-align-left");
            return;
        }

        if (centeredRight > safeRight) {
            card.classList.add("tooltip-align-right");
            return;
        }

        card.classList.add("tooltip-align-center");
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
            const groupKey = status.team || "unassigned";

            if (!groups[groupKey]) {
                groups[groupKey] = [];
            }

            groups[groupKey].push(status);
            return groups;
        }, {});
    }

    function buildNotRunningTooltipLines(components) {
        const items = Array.isArray(components) ? components.filter(Boolean) : [];
        if (!items.length) {
            return [];
        }

        const maxVisible = 15;
        const visibleItems = items.slice(0, maxVisible);
        const lines = ["Not Running Applications:"];

        visibleItems.forEach(function (name, index) {
            lines.push((index + 1) + ". " + name);
        });

        if (items.length > maxVisible) {
            lines.push("+ " + (items.length - maxVisible) + " more");
        }

        return lines;
    }

    function getTooltipStatusLine(serverStatus) {
        if (serverStatus === "healthy") {
            return "Status: Running";
        }
        if (serverStatus === "warning") {
            return "Status: Idle";
        }
        return "";
    }

    function createCardHTML(status) {
        const envId = status.env_id || "UNKNOWN";
        const active = activeEnvIds.includes(envId) ? " active-booking" : "";
        const runtime = status.tcs_runtime || {};
        const versions = runtime.display_version || "";
        const serviceTypes = (runtime.tcs_service_names || []).join(", ");
        const testingModes = (runtime.tcs_deployment_modes || []).join(", ");
        const notRunningComponents = status.not_running_components || [];
        const serverStatus = safeLower(status.status);
        const statusLine = getTooltipStatusLine(serverStatus);
        const tooltipLines = [
            envId,
            [
                versions ? "Version: " + versions : "",
                serviceTypes ? "Service: " + serviceTypes : "",
                testingModes ? "MODE: " + testingModes : ""
            ].filter(Boolean).join(" | "),
            statusLine
        ].concat(serverStatus === "critical" ? buildNotRunningTooltipLines(notRunningComponents) : [])
        .filter(function (line, index) {
            if (!line) {
                return false;
            }

            if (index === 1) {
                return line.trim().length > 0;
            }

            return true;
        });
        const tooltip = tooltipLines.join("\n");

        let statusClass = serverStatus;
        if (!["healthy", "warning", "critical", "maintenance"].includes(statusClass)) {
            statusClass = "unknown";
        }

        return [
            '<div class="env-card' + active + '" tabindex="0" data-tooltip="' + escapeAttribute(tooltip) + '" data-env-id="' + escapeAttribute(envId) + '" data-env-type="' + escapeAttribute(status.env_type || "") + '" data-team="' + escapeAttribute(status.team || "") + '">',
            '<div class="env-card-row">',
            '<div class="status-signal">',
            '<span class="signal-dot ' + statusClass + '"></span>',
            "</div>",
            '<div class="env-card-title">' + escapeAttribute(envId) + '</div>',
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
                "<h3>" + getGroupDisplayName(envType) + "</h3>",
                '<span class="group-count">- ' + servers.length + " Servers</span>",
                "</div>",
                '<div class="server-grid">',
                cards,
                "</div>",
                "</section>"
            ].join("");
        }).join("");
    }

    function getContextMenuElements() {
        return {
            menu: document.getElementById("envContextMenu"),
            title: document.getElementById("envContextMenuTitle"),
        };
    }

    function hideContextMenu() {
        const elements = getContextMenuElements();
        if (!elements.menu) {
            return;
        }
        elements.menu.hidden = true;
        activeContextEnv = null;
    }

    function updateContextMenuActions() {
        const elements = getContextMenuElements();
        if (!elements.menu || !activeContextEnv) {
            return;
        }

        const bookingButton = elements.menu.querySelector('button[data-action="booking"]');
        if (!bookingButton) {
            return;
        }

        const bookingAllowed = canBookEnvironment(activeContextEnv.env_id);
        bookingButton.disabled = !bookingAllowed;
        bookingButton.title = bookingAllowed
            ? ""
            : "Booking is allowed only for environments assigned to your team.";
    }

    function getAccessActionLabel(action) {
        const actionConfig = ACCESS_ACTIONS[action] || {};
        return actionConfig.label || "Access Link";
    }

    function getTerminalAccessType(action) {
        const actionConfig = ACCESS_ACTIONS[action] || {};
        return actionConfig.kind === "terminal" ? (actionConfig.access_type || "") : "";
    }

    function getLinkAccessType(action) {
        const actionConfig = ACCESS_ACTIONS[action] || {};
        return actionConfig.kind === "link" ? (actionConfig.access_type || "") : "";
    }

    function closeTerminalAccessSession(sessionId) {
        if (!sessionId || !CLOSE_ACCESS_SESSION_API_URL) {
            return;
        }

        fetch(CLOSE_ACCESS_SESSION_API_URL, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ session_id: sessionId }),
        }).catch(function () {
            return null;
        });
    }

    function launchTerminalAccessSession(action) {
        const accessType = getTerminalAccessType(action);
        if (!accessType || !ACCESS_SESSION_API_URL || !activeContextEnv || !activeContextEnv.env_id) {
            hideContextMenu();
            return;
        }

        const pendingWindow = window.open("", "_blank");
        if (!pendingWindow) {
            window.alert("Popup was blocked. Please allow popups for terminal access.");
            hideContextMenu();
            return;
        }

        try {
            pendingWindow.document.write("<title>Opening terminal...</title><p>Opening terminal access...</p>");
            pendingWindow.document.close();
        } catch (_error) {
            return null;
        }

        fetch(ACCESS_SESSION_API_URL, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                env_id: activeContextEnv.env_id,
                access_type: accessType,
            }),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    pendingWindow.close();
                    window.alert(result.data.error || "Failed to start terminal access.");
                    return;
                }

                pendingWindow.location.replace(result.data.access_url);
                terminalSessionWindows.set(result.data.session_id, pendingWindow);
            })
            .catch(function () {
                pendingWindow.close();
                window.alert("Failed to start terminal access.");
            })
            .finally(function () {
                hideContextMenu();
            });
    }

    function monitorClosedTerminalWindows() {
        terminalSessionWindows.forEach(function (accessWindow, sessionId) {
            if (!accessWindow || accessWindow.closed) {
                terminalSessionWindows.delete(sessionId);
                closeTerminalAccessSession(sessionId);
            }
        });
    }

    function launchConfiguredLink(action) {
        const accessType = getLinkAccessType(action);
        if (!accessType || !ACCESS_LINK_API_URL || !activeContextEnv || !activeContextEnv.env_id) {
            hideContextMenu();
            return;
        }

        fetch(ACCESS_LINK_API_URL, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                env_id: activeContextEnv.env_id,
                access_type: accessType,
            }),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    window.alert(result.data.error || "Failed to open configured link.");
                    return;
                }
                window.open(result.data.access_url, "_blank");
            })
            .catch(function () {
                window.alert("Failed to open configured link.");
            })
            .finally(function () {
                hideContextMenu();
            });
    }

    function showContextMenu(event, card) {
        const elements = getContextMenuElements();
        if (!elements.menu || !card) {
            return;
        }

        const envId = card.dataset.envId || "";
        const envType = card.dataset.envType || "";
        const team = card.dataset.team || "";
        activeContextEnv = {
            env_id: envId,
            env_type: envType,
            team: team,
        };

        elements.title.textContent = envId || "Environment";
        updateContextMenuActions();
        elements.menu.hidden = false;

        const menuRect = elements.menu.getBoundingClientRect();
        const left = Math.min(
            event.clientX,
            window.innerWidth - menuRect.width - 12
        );
        const top = Math.min(
            event.clientY,
            window.innerHeight - menuRect.height - 12
        );

        elements.menu.style.left = Math.max(12, left) + "px";
        elements.menu.style.top = Math.max(12, top) + "px";
    }

    function handleContextMenuAction(action) {
        if (!activeContextEnv || !activeContextEnv.env_id) {
            hideContextMenu();
            return;
        }

        if (action === "booking") {
            const params = new URLSearchParams({
                env_id: activeContextEnv.env_id,
            });
            window.location.href = BOOKING_GRID_URL + "?" + params.toString();
            return;
        }

        if (action === "logs") {
            fetch("/api/environment-health/" + encodeURIComponent(activeContextEnv.env_id) + "/logs", {
                credentials: "include",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    window.alert(result.data.error || result.data.message || "Feature is not available yet.");
                })
                .catch(function () {
                    window.alert("Feature is not available yet.");
                });
            hideContextMenu();
            return;
        }

        const actionConfig = ACCESS_ACTIONS[action] || {};

        if (actionConfig.kind === "terminal") {
            launchTerminalAccessSession(action);
            return;
        }

        if (actionConfig.kind === "link") {
            launchConfiguredLink(action);
            return;
        }

        if (action === "remediate") {
            fetch("/api/environment-health/" + encodeURIComponent(activeContextEnv.env_id) + "/auto-remediate", {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({}),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    window.alert(result.data.error || result.data.message || "Feature is not available yet.");
                })
                .catch(function () {
                    window.alert("Feature is not available yet.");
                });
            hideContextMenu();
        }
    }

    function isMobileViewport() {
        return window.matchMedia("(max-width: 768px)").matches;
    }

    function renderSidebarToggleMarkup(sidebarVisible) {
        return [
            '<span class="sidebar-toggle-label">',
            '<i class="fas fa-layer-group"></i>',
            '<span>Menu</span>',
            '</span>',
            '<span class="sidebar-toggle-arrow" aria-hidden="true">',
            '<i class="fas ' + (sidebarVisible ? 'fa-angle-left' : 'fa-angle-right') + '"></i>',
            '</span>'
        ].join("");
    }

    function updateSidebarButton(button, layout, reopenButton) {
        if (!layout) {
            return;
        }

        const sidebarVisible = isMobileViewport()
            ? layout.classList.contains("sidebar-open")
            : !layout.classList.contains("sidebar-collapsed");

        const label = sidebarVisible ? "Hide Menu" : "Show Menu";

        if (button) {
            button.setAttribute("aria-expanded", sidebarVisible ? "true" : "false");
            button.setAttribute("aria-label", label);
            button.setAttribute("title", label);
            button.innerHTML = '<i class="fas ' + (sidebarVisible ? 'fa-angle-left' : 'fa-angle-right') + '"></i>';
        }

        if (reopenButton) {
            reopenButton.setAttribute("aria-expanded", sidebarVisible ? "true" : "false");
            reopenButton.setAttribute("aria-label", sidebarVisible ? "Hide Menu" : "Show Menu");
            reopenButton.setAttribute("title", sidebarVisible ? "Hide Menu" : "Show Menu");
            reopenButton.innerHTML = renderSidebarToggleMarkup(sidebarVisible);
        }
    }

    function syncBackdrop(backdrop, layout) {
        if (!backdrop || !layout) {
            return;
        }

        backdrop.hidden = !(isMobileViewport() && layout.classList.contains("sidebar-open"));
    }

    function applyInitialSidebarState(layout, backdrop, button, reopenButton) {
        if (!layout) {
            return;
        }

        if (isMobileViewport()) {
            layout.classList.remove("sidebar-collapsed");
            layout.classList.remove("sidebar-open");
        } else {
            const storedState = window.localStorage.getItem(SIDEBAR_STATE_KEY);
            layout.classList.toggle("sidebar-collapsed", storedState === "true");
            layout.classList.remove("sidebar-open");
        }

        syncBackdrop(backdrop, layout);
        updateSidebarButton(button, layout, reopenButton);
    }

    function toggleSidebar(layout, backdrop, button, reopenButton) {
        if (!layout) {
            return;
        }

        if (isMobileViewport()) {
            layout.classList.toggle("sidebar-open");
        } else {
            const collapsed = layout.classList.toggle("sidebar-collapsed");
            window.localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? "true" : "false");
        }

        syncBackdrop(backdrop, layout);
        updateSidebarButton(button, layout, reopenButton);
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
        const layout = document.getElementById("environmentDashboardLayout");
        const sidebarBackdrop = document.getElementById("environmentDashboardSidebarBackdrop");
        const toggleSidebarButton = document.getElementById("toggleSidebarButton");
        const sidebarReopenButton = document.getElementById("sidebarReopenButton");
        const dashboardGroups = document.getElementById("dashboardGroups");
        const contextMenu = document.getElementById("envContextMenu");

        document.getElementById("refreshSecondsText").textContent = REFRESH_SECONDS;
        document.getElementById("refreshButton").addEventListener("click", function () {
            refreshHealth(true);
        });
        if (toggleSidebarButton) {
            toggleSidebarButton.addEventListener("click", function () {
                toggleSidebar(layout, sidebarBackdrop, toggleSidebarButton, sidebarReopenButton);
            });
        }
        if (sidebarReopenButton) {
            sidebarReopenButton.addEventListener("click", function () {
                toggleSidebar(layout, sidebarBackdrop, toggleSidebarButton, sidebarReopenButton);
            });
        }
        if (sidebarBackdrop) {
            sidebarBackdrop.addEventListener("click", function () {
                if (isMobileViewport()) {
                    layout.classList.remove("sidebar-open");
                    syncBackdrop(sidebarBackdrop, layout);
                    updateSidebarButton(toggleSidebarButton, layout, sidebarReopenButton);
                }
            });
        }
        window.addEventListener("resize", function () {
            applyInitialSidebarState(layout, sidebarBackdrop, toggleSidebarButton, sidebarReopenButton);
            hideContextMenu();
        });
        dashboardGroups.addEventListener("contextmenu", function (event) {
            const card = event.target.closest(".env-card");
            if (!card) {
                hideContextMenu();
                return;
            }
            event.preventDefault();
            showContextMenu(event, card);
        });
        dashboardGroups.addEventListener("click", function () {
            hideContextMenu();
        });
        dashboardGroups.addEventListener("mouseover", function (event) {
            const card = event.target.closest(".env-card");
            if (!card) {
                return;
            }
            updateTooltipPlacement(card);
        });
        dashboardGroups.addEventListener("focusin", function (event) {
            const card = event.target.closest(".env-card");
            if (!card) {
                return;
            }
            updateTooltipPlacement(card);
        });
        document.addEventListener("click", function (event) {
            if (!contextMenu || contextMenu.hidden) {
                return;
            }
            if (!event.target.closest("#envContextMenu")) {
                hideContextMenu();
            }
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                hideContextMenu();
            }
        });
        if (contextMenu) {
            contextMenu.addEventListener("click", function (event) {
                const button = event.target.closest("button[data-action]");
                if (!button) {
                    return;
                }
                if (button.disabled) {
                    event.preventDefault();
                    return;
                }
                handleContextMenuAction(button.dataset.action);
            });
        }

        updateSummary(currentSummary);
        renderDashboard();
        applyInitialSidebarState(layout, sidebarBackdrop, toggleSidebarButton, sidebarReopenButton);
        window.setInterval(monitorClosedTerminalWindows, 4000);
        window.addEventListener("beforeunload", function () {
            terminalSessionWindows.forEach(function (_accessWindow, sessionId) {
                closeTerminalAccessSession(sessionId);
            });
        });

        window.setInterval(function () {
            refreshHealth(false);
        }, REFRESH_SECONDS * 1000);
    });
}());
