"""Version fetching helpers used by the monitoring worker.

This module mirrors the status fetcher pattern: execute a remote command to
obtain running component versions and normalize the output into a mapping of
component -> version. The implementation is intentionally forgiving: it will
try to parse JSON output, but will also accept simple "component: version"
lines.
"""

import json
import logging

from .remote_executor import FabricRemoteExecutor

logger = logging.getLogger(__name__)


class VersionFetcher:
    """Fetch per-host running version information and normalize it.

    The fetcher exposes a `fetch_versions` method that returns a tuple of
    (mapping, raw_output) where mapping is a dict of component -> version
    and raw_output is the original command output.
    """

    DEFAULT_COMMANDS = {
        "version_info": "tcsexecute version",
    }

    def __init__(self, executor=None, command_map=None):
        self.executor = executor or FabricRemoteExecutor()
        if not hasattr(self.executor, "run"):
            raise TypeError("executor must provide a run(host, username, password, command) method")
        self.command_map = dict(self.DEFAULT_COMMANDS)
        if command_map:
            self.command_map.update(command_map)

    def get_command(self, command_name, host, server_type=None):
        _ = (host, server_type)
        return self.command_map.get(command_name)

    def execute_command(self, command_name, host, username, password, server_type=None):
        command = self.get_command(command_name, host, server_type=server_type)
        if not command:
            logger.info("Skipping version command %s for host %s because it is not configured.", command_name, host)
            return ""

        result = self.executor.run(host, username, password, command)
        if not result.ok:
            logger.warning(
                "Version command %s failed for host %s exit_code=%s stderr=%s",
                command_name,
                host,
                result.exit_code,
                (result.stderr or "").strip() or "n/a",
            )
            return result.combined_output or ""
        return result.stdout or result.combined_output or ""

    def parse_output(self, output_string):
        """Parse command output into a dict of component -> version.

        Accepts either JSON (object mapping) or plain text lines with
        "component: version" pairs. Returns an ordered dict-like plain dict.
        """
        if not output_string:
            return {}, ""

        text = output_string.strip()
        # Try JSON first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Normalize all values to strings
                return {str(k): (str(v) if v is not None else None) for k, v in parsed.items()}, text
        except Exception:
            pass

        result = {}
        for line in text.splitlines():
            if not line:
                continue
            if ":" in line:
                parts = line.split(":", 1)
                name = parts[0].strip()
                ver = parts[1].strip()
                if name:
                    result[name] = ver or None
            else:
                # If the line doesn't contain a colon, attempt to treat the
                # whole line as a version for a default component (skip).
                continue

        return result, text

    def fetch_versions(self, host, username, password, server_type=None, host_label=None):
        """Fetch and parse version information for one host."""
        try:
            output = self.execute_command(
                "version_info",
                host,
                username,
                password,
                server_type=server_type,
            )
            mapping, raw = self.parse_output(output)
            return mapping, raw
        except Exception:
            logger.exception("Failed to fetch version info for host %s.", host)
            return {}, ""
