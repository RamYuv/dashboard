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
    """Launch an external deployment engine for approved requests."""

    SUPPORTED_ENGINES = {"SCRIPT", "PYTHON", "JENKINS", "ANSIBLE"}

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
        configured_dir = (
            current_app.config.get("DEPLOYMENT_PAYLOAD_DIR")
            or current_app.config.get("AUTO_DEPLOY_PAYLOAD_DIR")
        )
        if configured_dir:
            return Path(configured_dir)
        return Path(current_app.config.get("LOG_DIR", ".")) / "deployments"

    @staticmethod
    def _workdir(script_path):
        configured_workdir = (
            current_app.config.get("DEPLOYMENT_LAUNCHER_WORKDIR")
            or current_app.config.get("AUTO_DEPLOY_WORKDIR")
        )
        if configured_workdir:
            return str(Path(configured_workdir))
        return str(script_path.parent)

    @staticmethod
    def engine_name():
        configured_engine = (
            current_app.config.get("DEPLOYMENT_ENGINE")
            or "SCRIPT"
        )
        normalized_engine = str(configured_engine).strip().upper() or "SCRIPT"
        if normalized_engine not in AutoDeploymentService.SUPPORTED_ENGINES:
            raise AutoDeploymentError(
                "Unsupported DEPLOYMENT_ENGINE '{}'. Supported engines: {}.".format(
                    normalized_engine,
                    ", ".join(sorted(AutoDeploymentService.SUPPORTED_ENGINES)),
                )
            )
        return normalized_engine

    @staticmethod
    def _configured_launcher():
        return (
            current_app.config.get("DEPLOYMENT_LAUNCHER")
            or current_app.config.get("AUTO_DEPLOY_SCRIPT")
            or ""
        ).strip()

    @staticmethod
    def _build_payload(deployment_request):
        payload = deployment_request.to_dict()
        payload["triggered_at"] = datetime.utcnow().isoformat() + "Z"
        payload["deployment_engine"] = AutoDeploymentService.engine_name()
        payload["execution_contract_version"] = "v1"
        return payload

    @staticmethod
    def _build_command(engine, launcher_path, payload_path, request_id):
        if engine == "ANSIBLE":
            return [
                "ansible-playbook",
                str(launcher_path),
                "-e",
                "@{}".format(payload_path),
                "-e",
                "envbooking_request_id={}".format(request_id),
            ]

        command = AutoDeploymentService._resolve_script_command(launcher_path)
        command.extend([
            "--payload",
            str(payload_path),
            "--request-id",
            str(request_id),
            "--engine",
            engine,
        ])
        return command

    @staticmethod
    def start(deployment_request):
        if not current_app.config.get("AUTO_DEPLOY_ENABLED", False):
            raise AutoDeploymentError("Auto deployment is disabled by configuration.")

        engine = AutoDeploymentService.engine_name()
        configured_launcher = AutoDeploymentService._configured_launcher()
        if not configured_launcher:
            raise AutoDeploymentError("No deployment launcher is configured.")

        launcher_path = Path(configured_launcher)
        if not launcher_path.is_absolute():
            launcher_path = Path(current_app.config.get("PROJECT_ROOT", ".")) / launcher_path
        if engine != "ANSIBLE" and not launcher_path.exists():
            raise AutoDeploymentError(
                "Deployment launcher was not found at '{}'.".format(launcher_path)
            )
        if engine == "ANSIBLE" and not launcher_path.exists():
            raise AutoDeploymentError(
                "Ansible playbook was not found at '{}'.".format(launcher_path)
            )

        payload_dir = AutoDeploymentService._payload_dir()
        payload_dir.mkdir(parents=True, exist_ok=True)

        request_id = deployment_request.deployment_request_id
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        payload_path = payload_dir / "{}-payload.json".format(request_id)
        log_path = payload_dir / "{}-{}.log".format(request_id, timestamp)

        payload = AutoDeploymentService._build_payload(deployment_request)
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        command = AutoDeploymentService._build_command(
            engine,
            launcher_path,
            payload_path,
            request_id,
        )

        env = os.environ.copy()
        env["ENVBOOKING_DEPLOYMENT_REQUEST_ID"] = str(request_id)
        env["ENVBOOKING_DEPLOYMENT_PAYLOAD"] = str(payload_path)
        env["ENVBOOKING_DEPLOYMENT_ENGINE"] = engine

        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=AutoDeploymentService._workdir(launcher_path),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=env,
            )

        return {
            "engine": engine,
            "pid": process.pid,
            "command": command,
            "payload_path": str(payload_path),
            "log_path": str(log_path),
        }
