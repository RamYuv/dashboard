"""Monitoring health snapshots and demo fallback data.

This module still contains lightweight mock/demo health data used when no
live environment mappings are available or when a richer fallback snapshot is
needed for dashboard rendering.
"""

import random
import threading
from datetime import datetime, timezone


POLL_INTERVAL_SECONDS = 30


ENVIRONMENT_HEALTH_TARGETS = [
    {
        "env_id": "ENV-{0:03d}".format(index),
        "env_type": "DB" if index % 3 else "APP",
        "host": "server-{0:03d}.example.local".format(index),
        "owner_team": ["alpha", "beta", "support"][index % 3],
    }
    for index in range(1, 61)
]


class EnvironmentHealthMonitor(object):
    """Background poller for mock environment health targets."""

    def __init__(self, targets, poll_interval=POLL_INTERVAL_SECONDS):
        self.targets = targets
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._statuses = []
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the background polling thread if it is not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self.refresh_once()
        self._thread = threading.Thread(target=self._run, name="environment-health-monitor")
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """Request background polling shutdown."""
        self._stop_event.set()

    def refresh_once(self):
        """Refresh all configured targets one time and replace the cached snapshot."""
        statuses = [self._check_target(target) for target in self.targets]
        with self._lock:
            self._statuses = statuses

    def snapshot(self):
        """Return a copy of the latest computed health snapshot."""
        with self._lock:
            return [dict(item) for item in self._statuses]

    def summary(self):
        """Return a rolled-up summary view over the latest snapshot."""
        snapshot = self.snapshot()
        total = len(snapshot)
        healthy = len([item for item in snapshot if item["status"] == "healthy"])
        warning = len([item for item in snapshot if item["status"] == "warning"])
        critical = len([item for item in snapshot if item["status"] == "critical"])
        unknown = len([item for item in snapshot if item["status"] == "unknown"])
        return {
            "total": total,
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "unknown": unknown,
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

    def _run(self):
        """Loop until stopped, polling at the configured interval."""
        while not self._stop_event.wait(self.poll_interval):
            self.refresh_once()

    def _check_target(self, target):
        """Generate one mock health result for a target."""
        score = random.randint(1, 100)
        if score >= 90:
            status = "critical"
        elif score >= 75:
            status = "warning"
        else:
            status = "healthy"
        return {
            "env_id": target["env_id"],
            "env_type": target["env_type"],
            "host": target["host"],
            "owner_team": target["owner_team"],
            "status": status,
            "cpu_percent": random.randint(5, 96),
            "memory_percent": random.randint(10, 98),
            "disk_percent": random.randint(20, 99),
            "database_status": "reachable" if status != "critical" else "unreachable",
            "message": self._message_for_status(status),
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }

    def _message_for_status(self, status):
        """Return a human-readable summary for one synthetic health status."""
        if status == "critical":
            return "SSH check failed or database is unreachable."
        if status == "warning":
            return "Server is reachable but resource usage is high."
        return "Server and database checks are healthy."


health_monitor = EnvironmentHealthMonitor(ENVIRONMENT_HEALTH_TARGETS)


def build_dummy_environment_snapshot():
    """Return a stable demo snapshot used as a live-data fallback."""
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "DEV-01": {
            "env_color": "Green",
            "env_type": "DEV",
            "timestamp": timestamp,
            "vm_count": 2,
            "component_summary": {"running": 8, "notrunning": 0, "unknown": 0},
            "message": "All logical servers are healthy.",
            "vm_details": {
                "DEV-01:cor-tcs": {"vm_color": "Green", "component_data": {"app1": {"run_status": "Running", "pid": "12345"}, "disc1": {"run_status": "Running", "pid": "44232"}, "disc2": {"run_status": "Running", "pid": "63453"}, "stat1": {"run_status": "Running", "pid": "03984"}}},
                "DEV-01:gateway-tcs": {"vm_color": "Green", "component_data": {"app4": {"run_status": "Running", "pid": "65453"}, "Notif1": {"run_status": "Running", "pid": "12346"}, "Notif2": {"run_status": "Running", "pid": "12347"}, "mq-listener": {"run_status": "Running", "pid": "12348"}}},
            },
        },
        "DEV-02": {
            "env_color": "Yellow",
            "env_type": "DEV",
            "timestamp": timestamp,
            "vm_count": 2,
            "component_summary": {"running": 6, "notrunning": 0, "unknown": 0},
            "message": "Services are up, but one logical server has no running apps.",
            "vm_details": {
                "DEV-02:cor-tcs": {"vm_color": "Green", "component_data": {"app1": {"run_status": "Running", "pid": "22345"}, "disc1": {"run_status": "Running", "pid": "24232"}, "disc2": {"run_status": "Running", "pid": "26453"}}},
                "DEV-02:gateway-tcs": {"vm_color": "Yellow", "component_data": {"status-check": {"run_status": "Running", "pid": "29876"}, "scheduler": {"run_status": "Running", "pid": "29877"}, "audit": {"run_status": "Running", "pid": "29878"}}},
            },
        },
        "QA-01": {
            "env_color": "Red",
            "env_type": "QA",
            "timestamp": timestamp,
            "vm_count": 2,
            "component_summary": {"running": 4, "notrunning": 2, "unknown": 0},
            "message": "Two components are not running in QA.",
            "vm_details": {
                "QA-01:cor-tcs": {"vm_color": "Red", "component_data": {"app1": {"run_status": "Running", "pid": "32345"}, "disc1": {"run_status": "NotRunning", "pid": None}, "disc2": {"run_status": "NotRunning", "pid": None}}},
                "QA-01:gateway-tcs": {"vm_color": "Green", "component_data": {"gateway": {"run_status": "Running", "pid": "35555"}, "notif": {"run_status": "Running", "pid": "35556"}, "audit": {"run_status": "Running", "pid": "35557"}}},
            },
        },
        "UAT-01": {
            "env_color": "Black",
            "env_type": "UAT",
            "timestamp": timestamp,
            "vm_count": 1,
            "component_summary": {"running": 0, "notrunning": 0, "unknown": 2},
            "message": "Host unreachable or status command unavailable.",
            "vm_details": {
                "UAT-01:cor-tcs": {"vm_color": "Black", "component_data": {"app1": {"run_status": "Unknown", "pid": None}, "disc1": {"run_status": "Unknown", "pid": None}}},
            },
        },
        "PROD-01": {
            "env_color": "Green",
            "env_type": "PROD",
            "timestamp": timestamp,
            "vm_count": 2,
            "component_summary": {"running": 10, "notrunning": 0, "unknown": 0},
            "message": "Production services are healthy.",
            "vm_details": {
                "PROD-01:cor-tcs": {"vm_color": "Green", "component_data": {"app1": {"run_status": "Running", "pid": "42345"}, "disc1": {"run_status": "Running", "pid": "44232"}, "disc2": {"run_status": "Running", "pid": "46453"}, "stat1": {"run_status": "Running", "pid": "43984"}, "mq": {"run_status": "Running", "pid": "43985"}}},
                "PROD-01:gateway-tcs": {"vm_color": "Green", "component_data": {"gateway": {"run_status": "Running", "pid": "45555"}, "notif": {"run_status": "Running", "pid": "45556"}, "audit": {"run_status": "Running", "pid": "45557"}, "batch": {"run_status": "Running", "pid": "45558"}, "cache": {"run_status": "Running", "pid": "45559"}}},
            },
        },
    }
