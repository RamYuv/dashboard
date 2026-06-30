"""Environment-level status aggregation helpers for monitoring refresh flows."""

import logging
from typing import Any, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EnvStatusAggregator:
    """Collapse VM-level health into environment-level status summaries and deltas."""

    def __init__(self):
        pass

    def _calculate_env_color(self, vm_colors: List[str]) -> str:
        """Derive one overall environment color from a list of VM colors."""
        normalized_colors = [str(vm_color or "Black") for vm_color in vm_colors]
        if not normalized_colors:
            return "Black"

        if "Red" in normalized_colors:
            return "Red"

        has_green = "Green" in normalized_colors
        has_yellow = "Yellow" in normalized_colors
        has_black = "Black" in normalized_colors

        # If one server in an environment is healthy while another is idle,
        # the environment is partially down and should be surfaced as critical.
        if has_green and has_yellow:
            return "Red"

        if has_black:
            return "Black"
        if has_yellow:
            return "Yellow"
        return "Green"

    def _summarize_components(self, vm_details: Dict[str, Any]) -> Dict[str, int]:
        """Count component run states across all VM details in one environment."""
        component_counts = {"running": 0, "notrunning": 0, "unknown": 0}
        for vm_status in vm_details.values():
            component_data = vm_status.get("component_data", {})
            for comp in component_data.values():
                run_status = comp.get("run_status", "Unknown")
                if run_status == "Running":
                    component_counts["running"] += 1
                elif run_status == "NotRunning":
                    component_counts["notrunning"] += 1
                else:
                    component_counts["unknown"] += 1
        return component_counts

    def aggregate_env_statuses(self, vm_statuses: Dict[str, Any], environments: List[Dict]) -> Dict[str, Any]:
        """Build environment snapshots from raw VM health responses."""
        env_statuses = {}
        timestamp = datetime.now(timezone.utc).isoformat()
        for env in environments:
            env_id = env.get("env_id")
            vm_ids = env.get("vms", [])
            vm_details = {}
            vm_colors = []
            for vm_id in vm_ids:
                if vm_id in vm_statuses:
                    vm_status = vm_statuses[vm_id]
                    vm_details[vm_id] = vm_status
                    vm_colors.append(vm_status.get("vm_color", "Black"))
            env_statuses[env_id] = {
                "env_color": self._calculate_env_color(vm_colors) if vm_colors else "Black",
                "env_type": env.get("env_type"),
                "timestamp": timestamp,
                "vm_count": len(vm_ids),
                "component_summary": self._summarize_components(vm_details),
                "vm_details": vm_details,
            }
        return env_statuses

    def calculate_status_delta(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compute changed environments between two snapshots for event publishing."""
        deltas = {}
        changed_envs = []
        color_changes = {}
        component_changes = {}
        for env_id, new_env_status in new_state.items():
            old_env_status = old_state.get(env_id, {})
            new_color = new_env_status.get("env_color")
            old_color = old_env_status.get("env_color")
            if new_color != old_color:
                changed_envs.append(env_id)
                color_changes[env_id] = {"old_color": old_color, "new_color": new_color}
                deltas[env_id] = {"old": old_env_status, "new": new_env_status}
            else:
                new_summary = new_env_status.get("component_summary", {})
                old_summary = old_env_status.get("component_summary", {})
                if new_summary != old_summary:
                    if env_id not in changed_envs:
                        changed_envs.append(env_id)
                    component_changes[env_id] = {"old": old_summary, "new": new_summary}
                    if env_id not in deltas:
                        deltas[env_id] = {"old": old_env_status, "new": new_env_status}
        return {
            "changed_envs": changed_envs,
            "env_deltas": deltas,
            "color_changes": color_changes,
            "component_changes": component_changes,
        }

    def assign_env_status(self, vm_statuses: Dict[str, Any]) -> Dict[str, Any]:
        """Build a single synthesized environment status from VM details only."""
        if not vm_statuses:
            return {
                "env_color": "Black",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component_summary": {"running": 0, "notrunning": 0, "unknown": 0},
                "vm_details": {},
            }
        return {
            "env_color": self._calculate_env_color([status.get("vm_color", "Black") for status in vm_statuses.values()]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component_summary": self._summarize_components(vm_statuses),
            "vm_details": vm_statuses,
        }
