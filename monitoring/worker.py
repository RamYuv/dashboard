"""Monitoring refresh workflow.

The worker performs one complete refresh cycle:
- load environment/server-type mappings from the database
- fetch VM status for each mapped host
- aggregate VM-level status into environment-level status
- persist the latest snapshot into monitor state/cache

This module does not own scheduling. It only performs a single refresh when
``refresh()`` is called by the embedded background service or the standalone
worker process.
"""

from webapp.models import EnvironmentHostMapping
from sqlalchemy.orm import joinedload


class EnvMonitorWorker:
    """Execute one monitoring refresh cycle against all configured mappings."""

    def __init__(self, app, environments, monitor_state, event_broker, status_fetcher, status_aggregator):
        self.app = app
        self.environments = environments or []
        self.monitor_state = monitor_state
        self.event_broker = event_broker
        self.status_fetcher = status_fetcher
        self.status_aggregator = status_aggregator

    def _included_server_types(self):
        raw_value = self.app.config.get(
            "MONITOR_INCLUDED_SERVER_TYPES",
            self.app.config.get("MONITOR_INCLUDED_SERVER_ROLES", ""),
        )
        included = []
        for item in str(raw_value).split(","):
            server_type_key = (item or "").strip()
            if server_type_key and server_type_key not in included:
                included.append(server_type_key)
        return included

    def _include_shared_mappings(self):
        return bool(self.app.config.get("MONITOR_INCLUDE_SHARED_MAPPINGS", False))

    def _should_monitor_mapping(self, mapping, included_server_types):
        if mapping is None:
            return False
        if not self._include_shared_mappings() and getattr(mapping, "is_shared", False):
            return False
        if not getattr(mapping, "env_id", None):
            return False
        server_type = mapping.server_type.server_type_key if mapping.server_type else None
        return bool(server_type and server_type in included_server_types)

    def _load_environment_mappings(self):
        """Load environment-to-server-type mappings and fetch raw VM status."""
        included_server_types = self._included_server_types()
        mappings = (
            EnvironmentHostMapping.query
            .options(
                joinedload(EnvironmentHostMapping.server_type),
                joinedload(EnvironmentHostMapping.environment),
                joinedload(EnvironmentHostMapping.host),
            )
            .order_by(EnvironmentHostMapping.env_id, EnvironmentHostMapping.environment_host_mapping_id)
            .all()
        )

        vm_statuses = {}
        env_index = {}
        host_status_cache = {}

        for mapping in mappings:
            if not self._should_monitor_mapping(mapping, included_server_types):
                continue

            env_id = mapping.env_id
            server_type = mapping.server_type.server_type_key if mapping.server_type else "unknown"
            vm_id = "{0}:{1}".format(env_id, server_type)

            env_entry = env_index.setdefault(env_id, {
                "env_id": env_id,
                "env_type": mapping.environment.env_type if mapping.environment else None,
                "vms": [],
            })
            env_entry["vms"].append(vm_id)

            host = None
            host_label = None
            if mapping.host:
                host = (mapping.host.ip_address or "").strip() or (mapping.host.hostname or "").strip() or None
                host_label = (mapping.host.hostname or "").strip() or host
            username = mapping.deployment_user or ""
            password = mapping.deployment_password or ""
            fetch_key = (host, username, password, server_type)
            if fetch_key not in host_status_cache:
                fetched_status = self.status_fetcher.fetch_vm_status(
                    host,
                    username,
                    password,
                    server_type=server_type,
                    host_label=host_label,
                )
                host_status_cache[fetch_key] = fetched_status
            vm_statuses[vm_id] = host_status_cache[fetch_key]

        return list(env_index.values()), vm_statuses

    def refresh(self):
        """Run one end-to-end monitoring refresh and persist the snapshot."""
        if self.monitor_state is None:
            return {}

        with self.app.app_context():
            previous_snapshot = self.monitor_state.previous()
            environments, vm_statuses = self._load_environment_mappings()

            if environments:
                snapshot = self.status_aggregator.aggregate_env_statuses(vm_statuses, environments)
            else:
                snapshot = {}

            delta = self.status_aggregator.calculate_status_delta(previous_snapshot, snapshot)

            self.monitor_state.update(snapshot, delta=delta)
            self.event_broker.publish(
                "environment_health_refreshed",
                {
                    "count": len(snapshot),
                    "changed_envs": delta.get("changed_envs", []),
                },
            )
            return snapshot
