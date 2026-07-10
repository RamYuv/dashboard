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

from concurrent.futures import ThreadPoolExecutor, as_completed

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

    def _should_monitor_mapping(self, mapping, included_server_types):
        if mapping is None:
            return False
        if not getattr(mapping, "env_id", None):
            return False
        server_type = mapping.server_type.server_type_key if mapping.server_type else None
        return bool(server_type and server_type in included_server_types)

    def _load_environment_mappings(self):
        """Load environment-to-server-type mappings and fetch raw VM status."""
        included_server_types = self._included_server_types()
        max_workers = max(1, int(self.app.config.get("MONITOR_FETCH_THREADS", 4) or 1))
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
        fetch_plans = []
        fetch_targets = {}

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
            password = mapping.deploy_user_hzn or ""
            fetch_key = (host, username, password, server_type)
            fetch_targets.setdefault(fetch_key, {
                "host": host,
                "username": username,
                "password": password,
                "server_type": server_type,
                "host_label": host_label,
            })
            fetch_plans.append((vm_id, fetch_key))

        host_status_cache = self._fetch_host_statuses(fetch_targets, max_workers)
        for vm_id, fetch_key in fetch_plans:
            vm_statuses[vm_id] = host_status_cache.get(fetch_key, {})

        return list(env_index.values()), vm_statuses

    def _fetch_host_statuses(self, fetch_targets, max_workers):
        if not fetch_targets:
            return {}

        host_status_cache = {}
        if max_workers <= 1 or len(fetch_targets) == 1:
            for fetch_key, target in fetch_targets.items():
                host_status_cache[fetch_key] = self.status_fetcher.fetch_vm_status(
                    target["host"],
                    target["username"],
                    target["password"],
                    server_type=target["server_type"],
                    host_label=target["host_label"],
                )
            return host_status_cache

        with ThreadPoolExecutor(max_workers=min(max_workers, len(fetch_targets))) as executor:
            future_map = {
                executor.submit(
                    self.status_fetcher.fetch_vm_status,
                    target["host"],
                    target["username"],
                    target["password"],
                    server_type=target["server_type"],
                    host_label=target["host_label"],
                ): fetch_key
                for fetch_key, target in fetch_targets.items()
            }
            for future in as_completed(future_map):
                host_status_cache[future_map[future]] = future.result()

        return host_status_cache

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
