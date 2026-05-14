"""VM status fetching and parsing helpers used by the monitoring worker."""

import logging
import random

logger = logging.getLogger(__name__)

STANDARD_STATUS_SUPPORTED_HOSTS = {"core-host", "getway-host"}


class VmStatusFetcher:
    """Fetch per-host service status and normalize it into VM health metadata."""

    def __init__(self):
        pass

    def supports_standard_status_command(self, host):
        """Return whether the default status command is supported for this host."""
        normalized_host = (host or "").strip()
        return normalized_host in STANDARD_STATUS_SUPPORTED_HOSTS

    def service_status(self, host, username, password):
        """Return mock command output for one host.

        This remains a stub for now; production implementations can replace
        it with SSH or other remote execution logic.
        """
        if not self.supports_standard_status_command(host):
            logger.info(
                "Skipping standard service status command for host %s because a dedicated monitor command is not implemented yet.",
                host,
            )
            return "__MONITORING_NOT_IMPLEMENTED__"

        mock_outputs = [
            "Getting status of instances .....................done\nNo instances running",
            "Getting status of instances .................. done\nStatus of required instances for session: [24, 40]\napp1\t\t: Running(pid: 12345)\ndisc1\t\t: Running(pid: 44232)\ndisc2\t\t: Running(pid: 63453)\nstat1\t\t: Running(pid: 03984)\napp4\t\t: Running(pid: 65453)",
            "Getting status of instances .................. done\nStatus of required instances for session: [24, 40]\napp1\t\t: Running(pid: 12345)\ndisc1\t\t: Running(pid: 44232)\ndisc2\t\t: Running(pid: 63453)\nstat1\t\t: Running(pid: 03984)\napp4\t\t: Running(pid: 65453)\nNotif1\t\t: NotRunning(pid: None)\nNotif2\t\t: NotRunning(pid: None)",
            "-bash: tcsexc: command not found",
        ]
        return random.choice(mock_outputs)

    def parse_output(self, output_string):
        """Parse raw command output into a normalized VM health payload."""
        vm_status = {"vm_color": None, "component_data": {}}
        if not output_string:
            vm_status["vm_color"] = "Black"
            return vm_status
        normalized = output_string.strip().lower()
        if "__monitoring_not_implemented__" in normalized:
            vm_status["vm_color"] = "Black"
            return vm_status
        if "command not found" in normalized:
            vm_status["vm_color"] = "Black"
            return vm_status
        if "no apps are running" in normalized or "no instances running" in normalized:
            vm_status["vm_color"] = "Yellow"
            return vm_status

        comp_data = {}
        not_running_count = 0
        for line in output_string.splitlines():
            line = line.strip()
            if not line:
                continue
            lower_line = line.lower()
            if lower_line.startswith("getting status") or lower_line.startswith("status of required instances"):
                continue
            if ":" not in line:
                continue
            parts = line.split(":", 1)
            comp_name = parts[0].strip()
            status_part = parts[1].strip() if len(parts) > 1 else ""
            pid = None
            if "notrunning" in status_part.lower() or "not running" in status_part.lower():
                run_status = "NotRunning"
                not_running_count += 1
            elif "running" in status_part.lower():
                run_status = "Running"
            else:
                run_status = status_part or "Unknown"
            if "pid:" in status_part.lower():
                pid_part = status_part.lower().split("pid:")[1].strip()
                pid_part = pid_part.strip("() ").strip()
                pid = pid_part if pid_part and pid_part.lower() != "none" else None
            comp_data[comp_name] = {"run_status": run_status, "pid": pid}

        if not comp_data:
            vm_status["vm_color"] = "Yellow"
            vm_status["component_data"] = comp_data
            return vm_status
        if not_running_count == len(comp_data):
            status_color = "Yellow"
        elif not_running_count > 0:
            status_color = "Red"
        else:
            status_color = "Green"
        vm_status["vm_color"] = status_color
        vm_status["component_data"] = comp_data
        return vm_status

    def fetch_vm_status(self, host, username, password):
        """Fetch and parse one host's status, returning a safe fallback on errors."""
        try:
            output = self.service_status(host, username, password)
            return self.parse_output(output)
        except Exception:
            logger.exception("Failed to fetch VM status for host %s.", host)
            return {"vm_color": "Black", "component_data": {}}
