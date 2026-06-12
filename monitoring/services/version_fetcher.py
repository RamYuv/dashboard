"""Version fetching helpers used by the monitoring worker.

This module mirrors the status fetcher pattern: execute a remote command to
obtain running component versions and normalize the output into a mapping of
component -> version. The implementation is intentionally forgiving: it will
try to parse JSON output, but will also accept simple "component: version"
lines.
"""

import json
import logging
import re

from .remote_executor import FabricRemoteExecutor

logger = logging.getLogger(__name__)


class VersionFetcher:
    """Fetch per-host running version information and normalize it.

    The fetcher exposes a `parse_output` method that returns a JSON-style
    object and a `fetch_versions` method that returns a backward-compatible
    tuple of (mapping, raw_output).
    """

    DEFAULT_COMMANDS = {
        "version_info": "tcsexec version",
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
        """Parse command output into a JSON-style payload.

        Accepts either JSON (object mapping) or plain text lines with
        "component: version" pairs.

        Returns:
            {
                "versions": {"component": "version"},
                "deployment_details": {
                    "mode": "<runtime mode>",
                    "service_types": ["<running service>"]
                },
                "raw_output": "<raw command output>"
            }
        """
        if not output_string:
            return {
                "versions": {},
                "deployment_details": {"mode": "", "service_types": []},
                "raw_output": "",
            }

        text = output_string.strip()
        # Try JSON first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Normalize all values to strings
                return {
                    "versions": {
                        str(k): (str(v) if v is not None else None)
                        for k, v in parsed.items()
                    },
                    "deployment_details": {"mode": "", "service_types": []},
                    "raw_output": text,
                }
        except Exception:
            pass

        deploy_info_mapping, deploy_info_details = self._parse_deploy_info_output(text)
        if deploy_info_mapping:
            return {
                "versions": deploy_info_mapping,
                "deployment_details": deploy_info_details,
                "raw_output": text,
            }

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

        return {
            "versions": result,
            "deployment_details": {"mode": "", "service_types": []},
            "raw_output": text,
        }

    def _parse_deploy_info_output(self, text):
        deploy_info = {}
        for raw_line in text.splitlines():
            line = (raw_line or "").strip()
            if not line or line.startswith("["):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            deploy_info[key.strip().lower()] = value.strip()

        versions_raw = deploy_info.get("versions")
        if not versions_raw:
            return {}, {"mode": "", "service_types": []}

        version = self._select_preferred_version(versions_raw)
        if not version:
            return {}, {"mode": "", "service_types": []}

        component_name = (
            deploy_info.get("server")
            or deploy_info.get("deploy_service")
            or deploy_info.get("env_name")
            or "version"
        )
        return {
            component_name: version
        }, {
            "mode": (deploy_info.get("mode") or "").strip(),
            "service_types": self._parse_service_types(
                deploy_info.get("deploy_service"),
            ),
        }

    def _parse_service_types(self, service_types_raw):
        if not service_types_raw:
            return []

        normalized = []
        for token in re.split(r"[\s,]+", service_types_raw or ""):
            value = token.strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    def _select_preferred_version(self, versions_raw):
        candidates = [
            token.strip()
            for token in re.split(r"\s+", versions_raw or "")
            if token.strip()
        ]
        if not candidates:
            return None

        for candidate in candidates:
            if "_patch" in candidate.lower():
                return candidate
        return candidates[0]

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
            parsed = self.parse_output(output)
            return parsed.get("versions", {}), parsed.get("raw_output", "")
        except Exception:
            logger.exception("Failed to fetch version info for host %s.", host)
            return {}, ""
