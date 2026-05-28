"""Remote command execution helpers for monitoring workflows."""

from abc import ABCMeta, abstractmethod
import logging


logger = logging.getLogger(__name__)


class RemoteCommandResult:
    """Normalized result for one remote command execution."""

    def __init__(
        self,
        host,
        command,
        stdout="",
        stderr="",
        exit_code=None,
        ok=False,
    ):
        self.host = host
        self.command = command
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.exit_code = exit_code
        self.ok = bool(ok)

    @property
    def combined_output(self):
        return "\n".join(part for part in [self.stdout.strip(), self.stderr.strip()] if part)


class BaseRemoteExecutor(object):
    """Executor interface for remote command and file operations."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self, host, username, password, command):
        """Execute a command on a remote host."""

    @abstractmethod
    def sudo(self, host, username, password, command):
        """Execute a privileged command on a remote host."""

    @abstractmethod
    def put(self, host, username, password, local_path, remote_path):
        """Upload a local file to a remote host."""

    @abstractmethod
    def get(self, host, username, password, remote_path, local_path):
        """Download a remote file to a local path."""


class FabricRemoteExecutor(BaseRemoteExecutor):
    """Fabric-backed executor for monitoring and deployment remote operations."""

    def __init__(self, connect_timeout=10, command_timeout=30):
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout

    def _get_connection_class(self):
        try:
            from fabric import Connection
        except ImportError:
            return None
        return Connection

    def _build_connect_kwargs(self, password):
        """Build Fabric connection kwargs in one place for reuse and testing."""
        connect_kwargs = {
            "look_for_keys": False,
            "allow_agent": False,
        }
        if password:
            connect_kwargs["password"] = password
        return connect_kwargs

    def _build_missing_fabric_result(self, host, operation, target, command=None):
        message = "Fabric is not installed. Unable to execute remote operation."
        logger.warning("%s host=%s operation=%s target=%s", message, host, operation, target)
        return RemoteCommandResult(
            host=host,
            command=command or "%s %s" % (operation, target),
            stderr=message,
            ok=False,
        )

    def _connect(self, connection_class, host, username, password):
        return connection_class(
            host=host,
            user=username or None,
            connect_timeout=self.connect_timeout,
            connect_kwargs=self._build_connect_kwargs(password),
        )

    def run(self, host, username, password, command):
        """Execute one command on the remote host and normalize the outcome."""
        connection_class = self._get_connection_class()
        if connection_class is None:
            return self._build_missing_fabric_result(
                host=host,
                operation="run",
                target=command,
                command=command,
            )

        try:
            connection = self._connect(connection_class, host, username, password)
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

    def sudo(self, host, username, password, command):
        """Execute one sudo command on the remote host and normalize the outcome."""
        connection_class = self._get_connection_class()
        if connection_class is None:
            return self._build_missing_fabric_result(
                host=host,
                operation="sudo",
                target=command,
                command=command,
            )

        try:
            connection = self._connect(connection_class, host, username, password)
            with connection:
                result = connection.sudo(
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
                "Remote sudo execution failed for host %s command %s.",
                host,
                command,
            )
            return RemoteCommandResult(
                host=host,
                command=command,
                stderr=str(exc),
                ok=False,
            )

    def put(self, host, username, password, local_path, remote_path):
        """Upload one file to the remote host."""
        connection_class = self._get_connection_class()
        if connection_class is None:
            return self._build_missing_fabric_result(
                host=host,
                operation="put",
                target=remote_path,
                command="put %s %s" % (local_path, remote_path),
            )

        try:
            connection = self._connect(connection_class, host, username, password)
            with connection:
                connection.put(local=local_path, remote=remote_path)
            return RemoteCommandResult(
                host=host,
                command="put %s %s" % (local_path, remote_path),
                stdout=remote_path,
                ok=True,
            )
        except Exception as exc:
            logger.exception(
                "Remote upload failed for host %s local_path %s remote_path %s.",
                host,
                local_path,
                remote_path,
            )
            return RemoteCommandResult(
                host=host,
                command="put %s %s" % (local_path, remote_path),
                stderr=str(exc),
                ok=False,
            )

    def get(self, host, username, password, remote_path, local_path):
        """Download one file from the remote host."""
        connection_class = self._get_connection_class()
        if connection_class is None:
            return self._build_missing_fabric_result(
                host=host,
                operation="get",
                target=remote_path,
                command="get %s %s" % (remote_path, local_path),
            )

        try:
            connection = self._connect(connection_class, host, username, password)
            with connection:
                connection.get(remote=remote_path, local=local_path)
            return RemoteCommandResult(
                host=host,
                command="get %s %s" % (remote_path, local_path),
                stdout=local_path,
                ok=True,
            )
        except Exception as exc:
            logger.exception(
                "Remote download failed for host %s remote_path %s local_path %s.",
                host,
                remote_path,
                local_path,
            )
            return RemoteCommandResult(
                host=host,
                command="get %s %s" % (remote_path, local_path),
                stderr=str(exc),
                ok=False,
            )
