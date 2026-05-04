"""Monitoring refresh workflow.

The worker performs one complete refresh cycle:
- load environment/server-role mappings from the database
- fetch VM status for each mapped host
- aggregate VM-level status into environment-level status
- merge live status with dummy/demo snapshot when live data is incomplete
- persist the latest snapshot into monitor state/cache

This module does not own scheduling. It only performs a single refresh when
``refresh()`` is called by the embedded background service or the standalone
worker process.
"""

from monitoring.services.health_service import build_dummy_environment_snapshot
from webapp.models import EnvironmentHostMapping


class EnvMonitorWorker:
    """Execute one monitoring refresh cycle against all configured mappings."""

    def __init__(self, app, environments, monitor_state, event_broker, status_fetcher, status_aggregator):
        self.app = app
        self.environments = environments or []
        self.monitor_state = monitor_state
        self.event_broker = event_broker
        self.status_fetcher = status_fetcher
        self.status_aggregator = status_aggregator

    def _load_environment_mappings(self):
        """Load environment-to-server-role mappings and fetch raw VM status."""
        mappings = (
            EnvironmentHostMapping.query
            .order_by(EnvironmentHostMapping.env_id, EnvironmentHostMapping.environment_host_mapping_id)
            .all()
        )

        vm_statuses = {}
        env_index = {}

        for mapping in mappings:
            env_id = mapping.env_id
            server_role = mapping.server_role.role_key if mapping.server_role else "unknown"
            vm_id = "{0}:{1}".format(env_id, server_role)

            env_entry = env_index.setdefault(env_id, {
                "env_id": env_id,
                "env_type": mapping.environment.env_type if mapping.environment else None,
                "vms": [],
            })
            env_entry["vms"].append(vm_id)

            host = mapping.host.hostname if mapping.host else None
            username = mapping.deployment_user or ""
            password = mapping.deployment_password or ""
            vm_statuses[vm_id] = self.status_fetcher.fetch_vm_status(host, username, password)

        return list(env_index.values()), vm_statuses

    def _has_meaningful_live_data(self, env_status):
        """Return True when live status contains real component details/counts."""
        if not env_status:
            return False

        component_summary = env_status.get("component_summary") or {}
        total_components = (
            int(component_summary.get("running", 0) or 0) +
            int(component_summary.get("notrunning", 0) or 0) +
            int(component_summary.get("unknown", 0) or 0)
        )
        if total_components > 0:
            return True

        vm_details = env_status.get("vm_details") or {}
        for vm_status in vm_details.values():
            if (vm_status or {}).get("component_data"):
                return True

        return False

    def _merge_with_dummy_snapshot(self, live_snapshot):
        """Prefer dummy snapshot when live data exists but contains no detail."""
        merged_snapshot = dict(build_dummy_environment_snapshot())

        for env_id, live_status in (live_snapshot or {}).items():
            dummy_status = merged_snapshot.get(env_id)
            if dummy_status and not self._has_meaningful_live_data(live_status):
                continue
            merged_snapshot[env_id] = live_status

        return merged_snapshot

    def refresh(self):
        """Run one end-to-end monitoring refresh and persist the snapshot."""
        if self.monitor_state is None:
            return {}

        with self.app.app_context():
            previous_snapshot = self.monitor_state.previous()
            environments, vm_statuses = self._load_environment_mappings()

            if environments:
                live_snapshot = self.status_aggregator.aggregate_env_statuses(vm_statuses, environments)
                snapshot = self._merge_with_dummy_snapshot(live_snapshot)
            else:
                snapshot = build_dummy_environment_snapshot()

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
