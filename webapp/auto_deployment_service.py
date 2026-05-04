"""
Helpers for launching external auto-deployment scripts.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import current_app


class AutoDeploymentError(RuntimeError):
    """Raised when auto-deployment cannot be started."""


class AutoDeploymentService:
    """Launch the configured deployment script for approved requests."""

    @staticmethod
    def _resolve_script_command(script_path):
        suffix = script_path.suffix.lower()
        if suffix == ".py":
            return [sys.executable, str(script_path)]
        if suffix == ".ps1":
            return [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ]
        return [str(script_path)]

    @staticmethod
    def _payload_dir():
        configured_dir = current_app.config.get("AUTO_DEPLOY_PAYLOAD_DIR")
        if configured_dir:
            return Path(configured_dir)
        return Path(current_app.config.get("LOG_DIR", ".")) / "deployments"

    @staticmethod
    def _workdir(script_path):
        configured_workdir = current_app.config.get("AUTO_DEPLOY_WORKDIR")
        if configured_workdir:
            return str(Path(configured_workdir))
        return str(script_path.parent)

    @staticmethod
    def _build_payload(deployment_request):
        payload = deployment_request.to_dict()
        payload["triggered_at"] = datetime.utcnow().isoformat() + "Z"
        return payload

    @staticmethod
    def start(deployment_request):
        if not current_app.config.get("AUTO_DEPLOY_ENABLED", False):
            raise AutoDeploymentError("Auto deployment is disabled by configuration.")

        configured_script = (current_app.config.get("AUTO_DEPLOY_SCRIPT") or "").strip()
        if not configured_script:
            raise AutoDeploymentError("AUTO_DEPLOY_SCRIPT is not configured.")

        script_path = Path(configured_script)
        if not script_path.is_absolute():
            script_path = Path(current_app.config.get("PROJECT_ROOT", ".")) / script_path
        if not script_path.exists():
            raise AutoDeploymentError(
                "Auto deployment script was not found at '{}'.".format(script_path)
            )

        payload_dir = AutoDeploymentService._payload_dir()
        payload_dir.mkdir(parents=True, exist_ok=True)

        request_id = deployment_request.deployment_request_id
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        payload_path = payload_dir / "{}-payload.json".format(request_id)
        log_path = payload_dir / "{}-{}.log".format(request_id, timestamp)

        payload = AutoDeploymentService._build_payload(deployment_request)
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        command = AutoDeploymentService._resolve_script_command(script_path)
        command.extend([
            "--payload",
            str(payload_path),
            "--request-id",
            str(request_id),
        ])

        env = os.environ.copy()
        env["ENVBOOKING_DEPLOYMENT_REQUEST_ID"] = str(request_id)
        env["ENVBOOKING_DEPLOYMENT_PAYLOAD"] = str(payload_path)

        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=AutoDeploymentService._workdir(script_path),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=env,
            )

        return {
            "pid": process.pid,
            "command": command,
            "payload_path": str(payload_path),
            "log_path": str(log_path),
        }
