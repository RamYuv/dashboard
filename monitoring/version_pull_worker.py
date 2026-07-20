"""Worker to perform one version-pull pass and persist current deployment state.

This worker mirrors the EnvMonitorWorker flow used by the monitoring worker:
- load environment host mappings
- for each mapping, resolve the deployment package(s) for the server type
- fetch version information from the host
- upsert `CurrentDeploymentState` rows with source='PULL'

The worker is intentionally conservative: it only updates mappings that can
be resolved to a configured package for the target. It returns a summary
dictionary describing how many mappings were processed and how many state
rows were created/updated.
"""

import logging

from webapp.models import (
    CurrentDeploymentState,
    EnvironmentHostMapping,
    TCSDeploymentMode,
    TcsService,
)
from sqlalchemy.orm import joinedload
from .services.version_fetcher import VersionFetcher
from webapp.domain.deployment_targets import get_target_definition
from webapp import db

logger = logging.getLogger(__name__)


class VersionPullWorker:
    def __init__(self, app, version_fetcher=None):
        self.app = app
        self.version_fetcher = version_fetcher or VersionFetcher()

    def _build_package_lookup(self, target_def):
        packages = target_def.get("packages") or {}
        lookup = {}
        # map package_key and package_name aliases directly
        for package_key, pkg in packages.items():
            lookup[package_key] = package_key
            lookup[package_key.lower()] = package_key
            name = pkg.get("package_name")
            if name:
                lookup[name] = package_key
                lookup[name.lower()] = package_key

        # build server_type -> package list map; only map server_type alias
        # if it uniquely identifies a single package to avoid collisions
        server_type_map = {}
        for package_key, pkg in packages.items():
            server_type = pkg.get("server_type_key")
            if not server_type:
                continue
            server_type_map.setdefault(server_type, []).append(package_key)

        for server_type, pk_list in server_type_map.items():
            if len(pk_list) == 1:
                lookup[server_type] = pk_list[0]
                lookup[server_type.lower()] = pk_list[0]

        return lookup, packages

    def _load_mappings(self):
        mappings = (
            EnvironmentHostMapping.query
            .options(joinedload(EnvironmentHostMapping.server_type), joinedload(EnvironmentHostMapping.host))
            .order_by(EnvironmentHostMapping.env_id, EnvironmentHostMapping.environment_host_mapping_id)
            .all()
        )
        return mappings

    def _group_mappings_by_environment(self, mappings):
        grouped = []
        current_env_id = None
        current_group = None

        for mapping in mappings:
            env_id = getattr(mapping, "env_id", None)
            if env_id != current_env_id:
                current_env_id = env_id
                current_group = {"env_id": env_id, "mappings": []}
                grouped.append(current_group)
            current_group["mappings"].append(mapping)

        return grouped

    def _resolve_host_connection(self, mapping):
        host = mapping.host
        if not host:
            return None, None

        hostname = (host.ip_address or "").strip() or (host.hostname or "").strip() or None
        host_label = (host.hostname or "").strip() or hostname
        return hostname, host_label

    def _resolve_mapping_target(self, mapping):
        server_type_key = mapping.server_type.server_type_key if mapping.server_type else None
        target_key = mapping.server_type.target_key if mapping.server_type else None
        target_def = get_target_definition(target_key)
        if not target_def:
            return None

        lookup, packages = self._build_package_lookup(target_def)
        return {
            "server_type_key": server_type_key,
            "target_key": target_key,
            "lookup": lookup,
            "packages": packages,
        }

    def _upsert_version_rows(
        self,
        mapping,
        target_info,
        versions_map,
        raw_output,
        deployment_details,
    ):
        created = 0
        updated = 0
        skipped = 0

        server_type_key = target_info["server_type_key"]
        target_key = target_info["target_key"]
        lookup = target_info["lookup"]
        packages = target_info["packages"]
        deployment_mode_id = (deployment_details.get("mode") or "").strip() or None
        tcs_service_ids = deployment_details.get("service_types") or []

        if deployment_mode_id:
            deployment_mode = TCSDeploymentMode.query.get(deployment_mode_id)
            if deployment_mode is None:
                deployment_mode = TCSDeploymentMode(
                    tcs_deployment_mode_id=deployment_mode_id,
                    mode_name=deployment_mode_id,
                    is_active=True,
                )
                db.session.add(deployment_mode)
        for tcs_service_id in tcs_service_ids:
            service = TcsService.query.get(tcs_service_id)
            if service is None:
                service = TcsService(
                    tcs_service_id=tcs_service_id,
                    service_name=tcs_service_id,
                    is_active=True,
                )
                db.session.add(service)

        for comp_name, comp_version in (versions_map or {}).items():
            normalized_name = (comp_name or "").strip()
            package_key = lookup.get(normalized_name) or lookup.get(normalized_name.lower())
            if package_key is None and server_type_key:
                package_key = lookup.get(server_type_key) or lookup.get(server_type_key.lower())
            if package_key is None and len(packages) == 1:
                package_key = next(iter(packages.keys()))
            if package_key is None:
                skipped += 1
                continue

            package_name = packages.get(package_key, {}).get("package_name") or package_key
            resolved_mode_id = deployment_mode_id if target_key == "TCS_APP" else None
            resolved_service_ids = tcs_service_ids if target_key == "TCS_APP" else [None]
            if not resolved_service_ids:
                resolved_service_ids = [None]

            for resolved_service_id in resolved_service_ids:
                state = CurrentDeploymentState.query.filter_by(
                    env_scope_type="ENV",
                    env_id=mapping.env_id,
                    env_type=mapping.env_type,
                    environment_host_mapping_id=mapping.environment_host_mapping_id,
                    package_key=package_key,
                    tcs_service_id=resolved_service_id,
                ).first()

                if state is None:
                    state = CurrentDeploymentState(
                        env_scope_type="ENV",
                        env_id=mapping.env_id,
                        env_type=mapping.env_type,
                        environment_host_mapping_id=mapping.environment_host_mapping_id,
                        target_key=target_key,
                        package_key=package_key,
                        package_name=package_name,
                        current_version=comp_version,
                        tcs_service_id=resolved_service_id,
                        tcs_deployment_mode_id=resolved_mode_id,
                        source="PULL",
                        status="CURRENT",
                        notes=(raw_output or "")[:4000],
                    )
                    db.session.add(state)
                    created += 1
                    continue

                if (
                    (state.current_version or "") != (comp_version or "") or
                    (state.source or "") != "PULL" or
                    (state.tcs_deployment_mode_id or None) != resolved_mode_id or
                    (state.tcs_service_id or None) != resolved_service_id
                ):
                    state.current_version = comp_version
                    state.tcs_deployment_mode_id = resolved_mode_id
                    state.source = "PULL"
                    state.package_name = package_name
                    state.deployment_request_id = None
                    state.updated_by = None
                    state.notes = (raw_output or "")[:4000]
                    updated += 1

        return {"created": created, "updated": updated, "skipped": skipped}

    def _process_mapping(self, mapping):
        hostname, host_label = self._resolve_host_connection(mapping)
        if not hostname:
            return {"created": 0, "updated": 0, "skipped": 1}

        target_info = self._resolve_mapping_target(mapping)
        if not target_info:
            return {"created": 0, "updated": 0, "skipped": 1}

        parsed_output = self.version_fetcher.fetch_version_details(
            hostname,
            mapping.deployment_user or "",
            mapping.deploy_user_hzn or "",
            server_type=target_info["server_type_key"],
            host_label=host_label,
        )
        return self._upsert_version_rows(
            mapping,
            target_info,
            parsed_output.get("versions") or {},
            parsed_output.get("raw_output") or "",
            parsed_output.get("deployment_details") or {},
        )

    def refresh(self):
        """Run one version pull pass and persist discovered versions."""
        created = 0
        updated = 0
        skipped = 0

        mappings = self._load_mappings()
        environment_groups = self._group_mappings_by_environment(mappings)

        for environment_group in environment_groups:
            for mapping in environment_group["mappings"]:
                summary = self._process_mapping(mapping)
                created += summary["created"]
                updated += summary["updated"]
                skipped += summary["skipped"]

        try:
            db.session.commit()
        except Exception:
            logger.exception("Failed to commit version pull updates.")
            db.session.rollback()

        return {"created": created, "updated": updated, "skipped": skipped}
