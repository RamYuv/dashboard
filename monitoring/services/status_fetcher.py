"""VM status fetching and parsing helpers used by the monitoring worker."""

import logging

from .remote_executor import FabricRemoteExecutor

logger = logging.getLogger(__name__)

STANDARD_STATUS_SUPPORTED_SERVER_TYPES = {"core", "getway", "gateway"}
NOT_IMPLEMENTED_OUTPUT = "__MONITORING_NOT_IMPLEMENTED__"
REMOTE_EXECUTION_FAILED_OUTPUT = "__REMOTE_EXECUTION_FAILED__"


class VmStatusFetcher:
    """Fetch per-host service status and normalize it into VM health metadata."""

    DEFAULT_COMMANDS = {
        "service_status": "tcsexecute status",
    }

    def __init__(self, executor=None, command_map=None):
        """Accept any remote executor implementation, defaulting to Fabric."""
        self.executor = executor or FabricRemoteExecutor()
        if not hasattr(self.executor, "run"):
            raise TypeError("executor must provide a run(host, username, password, command) method")
        self.command_map = dict(self.DEFAULT_COMMANDS)
        if command_map:
            self.command_map.update(command_map)

    def supports_standard_status_command(self, server_type=None):
        """Return whether the default status command is supported for this server type."""
        normalized_server_type = (server_type or "").strip().lower()
        return normalized_server_type in STANDARD_STATUS_SUPPORTED_SERVER_TYPES

    def get_command(self, command_name, host, server_type=None):
        """Resolve the remote shell command for one monitoring action."""
        _ = (host, server_type)
        return self.command_map.get(command_name)

    def execute_command(self, command_name, host, username, password, server_type=None):
        """Execute one named monitoring command and return raw output."""
        command = self.get_command(command_name, host, server_type=server_type)
        if not command:
            logger.info(
                "Skipping monitoring command %s for host %s because it is not configured.",
                command_name,
                host,
            )
            return NOT_IMPLEMENTED_OUTPUT

        result = self.executor.run(host, username, password, command)
        if not result.ok:
            logger.warning(
                "Monitoring command %s failed for host %s exit_code=%s stderr=%s",
                command_name,
                host,
                result.exit_code,
                (result.stderr or "").strip() or "n/a",
            )
            return result.combined_output or REMOTE_EXECUTION_FAILED_OUTPUT
        return result.stdout or result.combined_output

    def service_status(self, host, username, password, server_type=None, host_label=None):
        """Execute the standard remote status command for one host."""
        display_host = host_label or host
        if not self.supports_standard_status_command(server_type=server_type):
            logger.info(
                "Skipping standard service status command for host %s server_type=%s because a dedicated monitor command is not implemented yet.",
                display_host,
                server_type,
            )
            return NOT_IMPLEMENTED_OUTPUT
        return self.execute_command(
            "service_status",
            host,
            username,
            password,
            server_type=server_type,
        )

    def parse_output(self, output_string):
        """Parse raw command output into a normalized VM health payload."""
        vm_status = {"vm_color": None, "component_data": {}}
        if not output_string:
            vm_status["vm_color"] = "Black"
            return vm_status
        normalized = output_string.strip().lower()
        if NOT_IMPLEMENTED_OUTPUT.lower() in normalized:
            vm_status["vm_color"] = "Black"
            return vm_status
        if REMOTE_EXECUTION_FAILED_OUTPUT.lower() in normalized:
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

    def fetch_vm_status(self, host, username, password, server_type=None, host_label=None):
        """Fetch and parse one host's status, returning a safe fallback on errors."""
        try:
            output = self.service_status(
                host,
                username,
                password,
                server_type=server_type,
                host_label=host_label,
            )
            return self.parse_output(output)
        except Exception:
            logger.exception("Failed to fetch VM status for host %s.", host)
            return {"vm_color": "Black", "component_data": {}}
