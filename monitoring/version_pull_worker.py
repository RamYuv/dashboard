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

from webapp.models import EnvironmentHostMapping, CurrentDeploymentState
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
            name = pkg.get("package_name")
            if name:
                lookup[name] = package_key

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

        return lookup, packages

    def _load_mappings(self):
        mappings = (
            EnvironmentHostMapping.query
            .options(joinedload(EnvironmentHostMapping.server_type), joinedload(EnvironmentHostMapping.host))
            .order_by(EnvironmentHostMapping.env_id, EnvironmentHostMapping.environment_host_mapping_id)
            .all()
        )
        return mappings

    def refresh(self):
        """Run one version pull pass and persist discovered versions."""
        created = 0
        updated = 0
        skipped = 0

        mappings = self._load_mappings()
        for mapping in mappings:
            host = mapping.host
            if not host:
                skipped += 1
                continue
            hostname = (host.ip_address or "").strip() or (host.hostname or "").strip()
            username = mapping.deployment_user or ""
            password = mapping.deployment_password or ""

            server_type_key = mapping.server_type.server_type_key if mapping.server_type else None
            target_key = mapping.server_type.target_type if mapping.server_type else None
            target_def = get_target_definition(target_key)
            if not target_def:
                skipped += 1
                continue

            lookup, packages = self._build_package_lookup(target_def)

            versions_map, raw = self.version_fetcher.fetch_versions(
                hostname, username, password, server_type=server_type_key, host_label=host.hostname
            )

            # For each component found, try to resolve to a package_key
            for comp_name, comp_version in (versions_map or {}).items():
                package_key = lookup.get(comp_name)
                # If not found, and target only has one package, use it
                if package_key is None and len(packages) == 1:
                    package_key = next(iter(packages.keys()))
                if package_key is None:
                    # Cannot resolve component to a configured package; skip
                    skipped += 1
                    continue

                package_name = packages.get(package_key, {}).get("package_name") or package_key

                # Upsert CurrentDeploymentState for this mapping + package_key
                state = CurrentDeploymentState.query.filter_by(
                    env_scope_type="ENV",
                    env_id=mapping.env_id,
                    env_type=mapping.env_type,
                    environment_host_mapping_id=mapping.environment_host_mapping_id,
                    package_key=package_key,
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
                        source="PULL",
                        status="CURRENT",
                        notes=(raw or "")[:4000],
                    )
                    db.session.add(state)
                    created += 1
                else:
                    # Update only if version differs or source isn't PULL.
                    if (state.current_version or "") != (comp_version or "") or (state.source or "") != "PULL":
                        state.current_version = comp_version
                        state.source = "PULL"
                        state.package_name = package_name
                        # Clear provenance fields since this value now reflects
                        # an observed pull rather than a deployment request.
                        state.deployment_request_id = None
                        state.updated_by = None
                        state.notes = (raw or "")[:4000]
                        updated += 1

        try:
            db.session.commit()
        except Exception:
            logger.exception("Failed to commit version pull updates.")
            db.session.rollback()

        return {"created": created, "updated": updated, "skipped": skipped}
