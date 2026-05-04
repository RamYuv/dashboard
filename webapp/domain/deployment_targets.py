"""Deployment target configuration and resolution helpers.

These helpers translate the JSON target configuration into the shapes used by
the deployment request form and the deployment execution workflow.
"""

import json
import logging
from pathlib import Path

from ..models import EnvironmentHostMapping, ServerRole


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "deployment_targets.json"
TARGETS_WITH_ALL_OPTION = {"TCS_APP", "TCS_DB"}

LEGACY_TARGET_KEY_MAP = {
    "TCS": "TCS_APP",
    "DB": "TCS_DB",
    "PAYUI": "PAYGET",
    "PAYGET": "PAYGET",
    "TCS_PAYUI": "PAYGET",
    "TOOLS": "TOOLS",
}

TARGET_COMPONENT_TYPE_MAP = {
    "TCS_APP": "TCS_APP",
    "TCS_DB": "DB",
    "PAYGET": "PAYGET",
    "TCS_PAYUI": "PAYGET",
    "TOOLS": "TOOLS",
}

REQUIRED_TARGET_FIELDS = {"display_name", "component_name", "component_type", "packages"}
REQUIRED_PACKAGE_FIELDS = {"package_name", "server_role_key"}
LOGGER = logging.getLogger(__name__)


def load_deployment_targets():
    """Load and normalize deployment target definitions from JSON config."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _normalize_target_config(data)


def _normalize_target_config(raw_targets):
    """Validate and normalize raw target config into a consistent in-memory shape."""
    normalized = {}
    validation_errors = []
    for target_key, target in raw_targets.items():
        if not isinstance(target, dict):
            validation_errors.append(
                "Target '{}' must be a JSON object.".format(target_key)
            )
            continue
        if not REQUIRED_TARGET_FIELDS.issubset(set(target.keys())):
            validation_errors.append(
                "Target '{}' is missing required fields: {}.".format(
                    target_key,
                    ", ".join(sorted(REQUIRED_TARGET_FIELDS - set(target.keys()))),
                )
            )
            continue
        packages = target.get("packages")
        if not isinstance(packages, dict) or not packages:
            validation_errors.append(
                "Target '{}' must define at least one package.".format(target_key)
            )
            continue

        normalized_packages = {}
        seen_server_role_keys = set()
        for package_key, package in packages.items():
            if not isinstance(package, dict):
                validation_errors.append(
                    "Package '{}.{}' must be a JSON object.".format(target_key, package_key)
                )
                continue
            server_role_key = (
                package.get("server_role_key") or ""
            ).strip()
            package_keys = set(package.keys())
            if server_role_key:
                package_keys.add("server_role_key")

            if not REQUIRED_PACKAGE_FIELDS.issubset(package_keys):
                validation_errors.append(
                    "Package '{}.{}' is missing required fields: {}.".format(
                        target_key,
                        package_key,
                        ", ".join(sorted(REQUIRED_PACKAGE_FIELDS - package_keys)),
                    )
                )
                continue
            if not server_role_key:
                validation_errors.append(
                    "Package '{}.{}' must define a non-empty server_role_key.".format(
                        target_key,
                        package_key,
                    )
                )
                continue
            if package_key in normalized_packages:
                validation_errors.append(
                    "Target '{}' contains duplicate package key '{}'.".format(
                        target_key,
                        package_key,
                    )
                )
                continue
            if server_role_key in seen_server_role_keys and target_key != "TOOLS":
                validation_errors.append(
                    "Target '{}' reuses server_role_key '{}' across multiple packages.".format(
                        target_key,
                        server_role_key,
                    )
                )
                continue
            seen_server_role_keys.add(server_role_key)
            normalized_packages[package_key] = {
                "package_name": package.get("package_name") or package_key,
                "server_role_key": server_role_key,
                "deploy_order": package.get("deploy_order", 0),
            }

        if not normalized_packages:
            validation_errors.append(
                "Target '{}' has no valid packages after normalization.".format(target_key)
            )
            continue

        normalized[target_key] = {
            "display_name": target.get("display_name") or target_key,
            "component_name": target.get("component_name") or target_key.lower(),
            "component_type": target.get("component_type") or TARGET_COMPONENT_TYPE_MAP.get(target_key, target_key),
            "packages": normalized_packages,
        }
    for error in validation_errors:
        LOGGER.warning("Invalid deployment target config: %s", error)
    return normalized


def get_deployment_target_options():
    """Return UI-friendly deployment target metadata for form rendering."""
    options = []
    for target_key, target in load_deployment_targets().items():
        packages = target.get("packages") or {}
        options.append(
            {
                "target_key": target_key,
                "display_name": target.get("display_name") or target_key,
                "component_name": target.get("component_name") or "",
                "allow_all_packages": target_key in TARGETS_WITH_ALL_OPTION,
                "packages": [
                    {
                        "package_key": package_key,
                        "package_name": package.get("package_name") or package_key,
                        "server_role_key": package.get("server_role_key"),
                        "deploy_order": package.get("deploy_order", 0),
                    }
                    for package_key, package in packages.items()
                ],
            }
        )
    return options


def infer_target_key(deployment_data):
    """Resolve the canonical target key from modern or legacy payload fields."""
    target_key = (deployment_data.get("target_key") or "").strip()
    if target_key:
        return target_key

    legacy_component_type = (deployment_data.get("component_type") or "").strip().upper()
    return LEGACY_TARGET_KEY_MAP.get(legacy_component_type)


def derive_component_type(target_key, fallback=None):
    """Map a target key to the canonical component type stored in build records."""
    target_definition = get_target_definition(target_key) or {}
    return (
        target_definition.get("component_type") or
        TARGET_COMPONENT_TYPE_MAP.get(target_key) or
        fallback or
        target_key
    )


def get_target_definition(target_key):
    """Return the normalized config block for one target key."""
    return load_deployment_targets().get(target_key or "")


def target_supports_all_option(target_key):
    """Return whether the target allows selecting all packages at once."""
    return target_key in TARGETS_WITH_ALL_OPTION


def _build_package_lookup(packages):
    """Build a lookup that resolves package keys from key/name/server-role aliases."""
    lookup = {}
    for package_key, package in packages.items():
        package_name = package.get("package_name")
        server_role_key = package.get("server_role_key")
        lookup[package_key] = package_key
        if package_name:
            lookup[package_name] = package_key
        if server_role_key:
            lookup[server_role_key] = package_key
    return lookup


def get_selected_package_keys(target_key, deployment_data):
    """Resolve selected package keys from a deployment request payload."""
    target = get_target_definition(target_key)
    if not target:
        return []

    packages = target.get("packages") or {}
    if not packages:
        return []

    selected = deployment_data.get("selected_packages")
    if not selected:
        selected = deployment_data.get("selected_package")

    if not selected:
        return []

    if isinstance(selected, str):
        selected = [selected]

    if any((item or "").strip().lower() == "all" for item in selected):
        return list(packages.keys())

    lookup = _build_package_lookup(packages)
    resolved = []
    for item in selected:
        package_key = lookup.get(item)
        if package_key and package_key not in resolved:
            resolved.append(package_key)
    return resolved


def _find_environment_mapping(env_id, server_role_key):
    """Find the mapping for one server role inside one concrete environment."""
    if not env_id or not server_role_key:
        return None
    server_role = ServerRole.query.filter_by(role_key=server_role_key).first()
    if server_role is None:
        return None
    return EnvironmentHostMapping.query.filter_by(
        env_id=env_id,
        server_role_id=server_role.server_role_id,
    ).first()


def _find_shared_environment_mappings(env_type, server_role_key):
    """Find shared mappings for environment-type scoped tool deployments."""
    if not env_type or not server_role_key:
        return []
    server_role = ServerRole.query.filter_by(role_key=server_role_key).first()
    if server_role is None:
        return []
    return EnvironmentHostMapping.query.filter_by(
        env_type=env_type,
        is_shared=True,
        server_role_id=server_role.server_role_id,
    ).all()


def _resolve_package_mappings(env_id, requested_env_type, env_scope_type, server_role_key):
    """Resolve one package's host mappings for the requested deployment scope."""
    if env_scope_type == "ENV_TYPE":
        return _find_shared_environment_mappings(requested_env_type, server_role_key)

    exact_mapping = _find_environment_mapping(env_id, server_role_key)
    if exact_mapping is not None:
        return [exact_mapping]

    # Fall back to shared env-type mappings when an environment reuses
    # common hosts for the selected server role.
    return _find_shared_environment_mappings(requested_env_type, server_role_key)


def resolve_request_targets(env_id, deployment_data):
    """Expand a deployment request into concrete package/server-role deployment targets."""
    target_key = infer_target_key(deployment_data)
    target = get_target_definition(target_key)
    if not target:
        return []

    env_scope_type = (deployment_data.get("env_scope_type") or "ENV").strip().upper()
    requested_env_type = (deployment_data.get("requested_env_type") or "").strip().upper()

    packages = target.get("packages") or {}
    selected_package_keys = get_selected_package_keys(target_key, deployment_data)
    resolved_targets = []

    for package_key in selected_package_keys:
        package = packages.get(package_key)
        if not package:
            continue

        server_role_key = package.get("server_role_key")
        mappings = _resolve_package_mappings(
            env_id,
            requested_env_type,
            env_scope_type,
            server_role_key,
        )

        for mapping in mappings or [None]:
            host = mapping.host if mapping is not None else None
            resolved_targets.append(
                {
                    "package_key": package_key,
                    "package_name": package.get("package_name") or package_key,
                    "server_role_key": server_role_key,
                    "environment_host_mapping_id": (
                        mapping.environment_host_mapping_id if mapping is not None else None
                    ),
                    "env_scope_type": env_scope_type,
                    "requested_env_type": requested_env_type or (mapping.env_type if mapping is not None else None),
                    "host_id": host.host_id if host is not None else None,
                    "host_name": host.hostname if host is not None else None,
                    "deploy_order": package.get("deploy_order", 0),
                }
            )

    return sorted(resolved_targets, key=lambda item: (item["deploy_order"], item["package_key"]))
