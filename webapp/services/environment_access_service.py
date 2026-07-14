import os
import random
import socket
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from flask import current_app

from ..models import EnvironmentHostMapping, PayUi, PayUiAccessType, ServerTypeKey


class EnvironmentAccessService:
    _sessions = {}
    _lock = threading.Lock()

    @classmethod
    def start_terminal_session(cls, env_id, access_type, user=None, request_host=None):
        server_type_enum = ServerTypeKey.from_value(access_type)
        normalized_access_type = (
            server_type_enum.value if server_type_enum is not None else (access_type or "").strip().lower()
        )

        mapping = EnvironmentHostMapping.find_terminal_access_mapping(env_id, normalized_access_type)
        if mapping is None:
            return None, "Environment host mapping was not found."

        payload = mapping.terminal_access_payload()
        hostname = (payload.get("hostname") or "").strip()
        deployment_user = (payload.get("deployment_user") or "").strip()
        password_value = payload.get("deploy_user_hzn")

        if not hostname:
            return None, "Mapped host is missing a hostname."
        if not deployment_user:
            return None, "Mapped host is missing a deployment user."
        if not password_value:
            return None, "Mapped host is missing an access password."

        ttyd_path = cls._resolve_binary_path(
            current_app.config.get("TTYD_BINARY"),
            default_name="ttyd",
        )
        sshpass_path = cls._resolve_binary_path(
            current_app.config.get("SSHPASS_BINARY"),
            default_name="sshpass",
        )

        if ttyd_path is None:
            return None, "ttyd binary was not found."
        if sshpass_path is None:
            return None, "sshpass binary was not found."

        port = cls._reserve_port()
        password_file = cls._write_password_file(env_id, normalized_access_type, password_value)
        command = [
            str(ttyd_path),
            "-p",
            str(port),
            "-m",
            str(current_app.config.get("TTYD_MAX_CONNECTIONS", 100)),
            "-w",
            str(sshpass_path),
            "-f",
            password_file,
            "ssh",
            "{}@{}".format(deployment_user, hostname),
        ]

        process = subprocess.Popen(
            command,
            cwd=current_app.config.get("PROJECT_ROOT"),
        )
        session_id = uuid.uuid4().hex
        session = {
            "session_id": session_id,
            "env_id": payload.get("env_id"),
            "access_type": normalized_access_type,
            "port": port,
            "process": process,
            "password_file": password_file,
            "request_user": getattr(user, "user_id", None),
            "host": hostname,
        }
        with cls._lock:
            cls._sessions[session_id] = session

        return {
            "session_id": session_id,
            "access_url": cls._build_terminal_url(request_host, port),
            "port": port,
            "host": hostname,
            "server_type_key": payload.get("server_type_key"),
        }, None

    @classmethod
    def close_terminal_session(cls, session_id):
        normalized_session_id = (session_id or "").strip()
        if not normalized_session_id:
            return False, "session_id is required."

        with cls._lock:
            session = cls._sessions.pop(normalized_session_id, None)

        if session is None:
            return False, "Terminal session was not found."

        process = session.get("process")
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        password_file = session.get("password_file")
        if password_file:
            try:
                os.remove(password_file)
            except OSError:
                pass

        return True, None

    @classmethod
    def get_pay_ui_link(cls, env_id, access_type):
        normalized_env_id = (env_id or "").strip()
        access_enum = PayUiAccessType.from_value(access_type)
        normalized_access_type = (
            access_enum.value if access_enum is not None else (access_type or "").strip().lower()
        )
        if not normalized_env_id:
            return None, "env_id is required."
        if normalized_access_type not in {
            PayUiAccessType.PAY_URL.value,
            PayUiAccessType.PAY_ADMIN.value,
        }:
            return None, "Unsupported pay link access type."

        row = PayUi.query.filter_by(env_id=normalized_env_id).first()
        if row is None:
            return None, "Pay UI link was not found for this environment."

        url = row.get_url(normalized_access_type)
        if not url:
            return None, "Requested Pay UI link is not configured for this environment."

        return {
            "env_id": normalized_env_id,
            "access_type": normalized_access_type,
            "access_url": url,
        }, None

    @classmethod
    def _resolve_binary_path(cls, configured_value, default_name):
        candidates = []
        if configured_value:
            candidates.append(Path(configured_value))

        project_root = current_app.config.get("PROJECT_ROOT")
        if project_root:
            root_path = Path(project_root)
            candidates.extend(
                [
                    root_path / default_name,
                    root_path / (default_name + ".exe"),
                    root_path / "bin" / default_name,
                    root_path / "bin" / (default_name + ".exe"),
                ]
            )

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @classmethod
    def _reserve_port(cls):
        start = int(current_app.config.get("TTYD_PORT_START", 46000))
        end = int(current_app.config.get("TTYD_PORT_END", 49000))
        for _ in range(3000):
            port = random.randint(start, end)
            if cls._port_available(port):
                return port
        raise RuntimeError("Failed to allocate a ttyd port.")

    @staticmethod
    def _port_available(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return sock.connect_ex(("127.0.0.1", port)) != 0

    @classmethod
    def _write_password_file(cls, env_id, access_type, password_value):
        temp_dir = Path(
            current_app.config.get("TTYD_PASS_FILE_DIR")
            or tempfile.gettempdir()
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_name = "env_access_{env}_{access}_{suffix}.txt".format(
            env=(env_id or "env").lower(),
            access=((access_type or "access").strip().lower()),
            suffix=uuid.uuid4().hex[:8],
        )
        path = temp_dir / file_name
        path.write_text(str(password_value), encoding="utf-8")
        return str(path)

    @classmethod
    def _build_terminal_url(cls, request_host, port):
        configured_host = (current_app.config.get("TTYD_PUBLIC_HOST") or "").strip()
        if configured_host:
            base_host = configured_host
        else:
            host_value = (request_host or "").strip() or "127.0.0.1"
            base_host = host_value.split(":", 1)[0]
        scheme = current_app.config.get("TTYD_PUBLIC_SCHEME", "http")
        return "{}://{}:{}".format(scheme, base_host, port)
