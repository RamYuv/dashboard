"""Remote command execution helpers for monitoring workflows."""

from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class RemoteCommandResult:
    """Normalized result for one remote command execution."""

    host: str
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    ok: bool = False

    @property
    def combined_output(self):
        return "\n".join(part for part in [self.stdout.strip(), self.stderr.strip()] if part)


class FabricRemoteExecutor:
    """Thin wrapper around Fabric so monitoring code is not coupled to its API."""

    def __init__(self, connect_timeout=10, command_timeout=30):
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout

    def _get_connection_class(self):
        try:
            from fabric import Connection
        except ImportError:
            return None
        return Connection

    def run(self, host, username, password, command):
        """Execute one command on the remote host and normalize the outcome."""
        connection_class = self._get_connection_class()
        if connection_class is None:
            message = "Fabric is not installed. Unable to execute remote command."
            logger.warning("%s host=%s command=%s", message, host, command)
            return RemoteCommandResult(
                host=host,
                command=command,
                stderr=message,
                ok=False,
            )

        connect_kwargs = {}
        if password:
            connect_kwargs["password"] = password

        try:
            connection = connection_class(
                host=host,
                user=username or None,
                connect_timeout=self.connect_timeout,
                connect_kwargs={
                    **connect_kwargs,
                    "look_for_keys": False,
                    "allow_agent": False,
                },
            )
            with connection:
                result = connection.run(
                    command,
                    hide=True,
                    warn=True,
                    timeout=self.command_timeout,
                )
            return RemoteCommandResult(
                host=host,
                command=command,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exit_code=result.exited,
                ok=bool(result.ok),
            )
        except Exception as exc:
            logger.exception(
                "Remote command execution failed for host %s command %s.",
                host,
                command,
            )
            return RemoteCommandResult(
                host=host,
                command=command,
                stderr=str(exc),
                ok=False,
            )
