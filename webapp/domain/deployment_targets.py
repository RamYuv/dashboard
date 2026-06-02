"""Deployment target configuration and resolution helpers.

These helpers translate the JSON target configuration into the shapes used by
the deployment request form and the deployment execution workflow.
"""

import json
import logging
from pathlib import Path

from ..models import EnvironmentHostMapping, ServerType


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "deployment_targets.json"
SUPPORTED_ENV_SCOPES = {"ENV"}

REQUIRED_TARGET_FIELDS = {"display_name", "packages"}
REQUIRED_PACKAGE_FIELDS = {"package_name", "server_type_key"}
LOGGER = logging.getLogger(__name__)
_TARGET_CACHE = {
    "mtime": None,
    "targets": {},
}


def _normalize_supported_scopes(raw_scopes, default_scopes=None):
    """Normalize target/package deployment scopes."""
    default_scopes = list(default_scopes or ["ENV"])
    if raw_scopes is None:
        return default_scopes

    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]

    normalized = []
    for scope in raw_scopes:
        value = (scope or "").strip().upper()
        if value in SUPPORTED_ENV_SCOPES and value not in normalized:
            normalized.append(value)
    return normalized or default_scopes


def _normalize_server_type_key(package):
    """Return the package's single deployment server type key."""
    return (package.get("server_type_key") or package.get("server_role_key") or "").strip()


def load_deployment_targets():
    """Load and normalize deployment target definitions from JSON config."""
    try:
        config_mtime = CONFIG_PATH.stat().st_mtime
    except (OSError, ValueError):
        return {}
    if _TARGET_CACHE["mtime"] == config_mtime:
        return _TARGET_CACHE["targets"]

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    normalized = _normalize_target_config(data)
    _TARGET_CACHE["mtime"] = config_mtime
    _TARGET_CACHE["targets"] = normalized
    return normalized


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

        target_supported_scopes = _normalize_supported_scopes(
            target.get("supported_scopes"),
            default_scopes=["ENV"],
        )

        normalized_packages = {}
        for package_key, package in packages.items():
            if not isinstance(package, dict):
                validation_errors.append(
                    "Package '{}.{}' must be a JSON object.".format(target_key, package_key)
                )
                continue
            server_type_key = _normalize_server_type_key(package)
            package_keys = set(package.keys())
            if server_type_key:
                package_keys.add("server_type_key")

            if not REQUIRED_PACKAGE_FIELDS.issubset(package_keys):
                validation_errors.append(
                    "Package '{}.{}' is missing required fields: {}.".format(
                        target_key,
                        package_key,
                        ", ".join(sorted(REQUIRED_PACKAGE_FIELDS - package_keys)),
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
            package_supported_scopes = _normalize_supported_scopes(
                package.get("supported_scopes"),
                default_scopes=target_supported_scopes,
            )
            normalized_packages[package_key] = {
                "package_name": package.get("package_name") or package_key,
                "server_type_key": server_type_key,
                "deploy_order": package.get("deploy_order", 0),
                "supported_scopes": package_supported_scopes,
            }

        if not normalized_packages:
            validation_errors.append(
                "Target '{}' has no valid packages after normalization.".format(target_key)
            )
            continue

        normalized[target_key] = {
            "display_name": target.get("display_name") or target_key,
            "allow_multiple_packages": bool(target.get("allow_multiple_packages")),
            "packages": normalized_packages,
            "supported_scopes": target_supported_scopes,
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
                "allow_multiple_packages": bool(target.get("allow_multiple_packages")),
                "supported_scopes": target.get("supported_scopes") or ["ENV"],
                "packages": [
                    {
                        "package_key": package_key,
                        "package_name": package.get("package_name") or package_key,
                        "server_type_key": package.get("server_type_key"),
                        "deploy_order": package.get("deploy_order", 0),
                        "supported_scopes": package.get("supported_scopes") or ["ENV"],
                    }
                    for package_key, package in packages.items()
                ],
            }
        )
    return options
def get_target_definition(target_key):
    """Return the normalized config block for one target key."""
    return load_deployment_targets().get(target_key or "")


def target_supports_all_option(target_key):
    """Return whether the target allows selecting all packages at once."""
    return target_supports_multiple_packages(target_key)


def target_supports_multiple_packages(target_key):
    """Return whether the target allows selecting multiple packages."""
    target = get_target_definition(target_key) or {}
    return bool(target.get("allow_multiple_packages"))


def target_supports_scope(target_key, env_scope_type):
    """Return whether a target supports the requested deployment scope."""
    target = get_target_definition(target_key) or {}
    supported_scopes = target.get("supported_scopes") or ["ENV"]
    return (env_scope_type or "").strip().upper() in supported_scopes


def package_supports_scope(target_key, package_key, env_scope_type):
    """Return whether one package supports the requested deployment scope."""
    target = get_target_definition(target_key) or {}
    package = (target.get("packages") or {}).get(package_key) or {}
    supported_scopes = package.get("supported_scopes") or target.get("supported_scopes") or ["ENV"]
    return (env_scope_type or "").strip().upper() in supported_scopes


def packages_support_scope(target_key, package_keys, env_scope_type):
    """Return whether all selected packages support the requested deployment scope."""
    return all(
        package_supports_scope(target_key, package_key, env_scope_type)
        for package_key in (package_keys or [])
    )


def _build_package_lookup(packages):
    """Build a lookup that resolves package keys from key/name/server-type aliases."""
    lookup = {}
    for package_key, package in packages.items():
        package_name = package.get("package_name")
        server_type_key = package.get("server_type_key")
        lookup[package_key] = package_key
        if package_name:
            lookup[package_name] = package_key
        if server_type_key:
            lookup[server_type_key] = package_key
    return lookup


def get_selected_package_keys(target_key, deployment_data):
    """Resolve selected package keys from a deployment request payload."""
    target = get_target_definition(target_key)
    if not target:
        return []

    packages = target.get("packages") or {}
    if not packages:
        return []

    selected = deployment_data.get("package_keys")
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


def _find_environment_mapping(env_id, server_type_key):
    """Find the mapping for one server type inside one concrete environment."""
    if not env_id or not server_type_key:
        return None
    server_type = ServerType.query.filter_by(server_type_key=server_type_key).first()
    if server_type is None:
        return None
    return EnvironmentHostMapping.query.filter_by(
        env_id=env_id,
        server_type_id=server_type.server_type_id,
    ).first()


def _resolve_package_mappings(env_id, requested_env_type, env_scope_type, server_type_key):
    """Resolve one package's host mappings for the requested deployment scope."""
    exact_mapping = _find_environment_mapping(env_id, server_type_key)
    if exact_mapping is not None:
        return [exact_mapping]
    return []


def resolve_request_targets(env_id, deployment_data):
    """Expand a deployment request into concrete package/server-type deployment targets."""
    target_key = (deployment_data.get("target_key") or "").strip().upper()
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

        if env_scope_type not in (package.get("supported_scopes") or target.get("supported_scopes") or ["ENV"]):
            resolved_targets.append(
                {
                    "package_key": package_key,
                    "package_name": package.get("package_name") or package_key,
                    "server_type_key": package.get("server_type_key"),
                    "environment_host_mapping_id": None,
                    "env_scope_type": env_scope_type,
                    "requested_env_type": requested_env_type,
                    "host_id": None,
                    "host_name": None,
                    "deploy_order": package.get("deploy_order", 0),
                    "supported_scopes": package.get("supported_scopes") or ["ENV"],
                    "resolution_error": "Package does not support {} scope.".format(env_scope_type),
                }
            )
            continue

        resolved_server_type_key = package.get("server_type_key")
        mappings = _resolve_package_mappings(
            env_id,
            requested_env_type,
            env_scope_type,
            resolved_server_type_key,
        )

        for mapping in mappings or [None]:
            host = mapping.host if mapping is not None else None
            mapping_server_type_key = (
                mapping.server_type.server_type_key
                if mapping is not None and mapping.server_type is not None
                else resolved_server_type_key
            )
            resolved_targets.append(
                {
                    "package_key": package_key,
                    "package_name": package.get("package_name") or package_key,
                    "server_type_key": mapping_server_type_key,
                    "environment_host_mapping_id": (
                        mapping.environment_host_mapping_id if mapping is not None else None
                    ),
                    "env_scope_type": env_scope_type,
                    "requested_env_type": requested_env_type or (mapping.env_type if mapping is not None else None),
                    "host_id": host.host_id if host is not None else None,
                    "host_name": host.hostname if host is not None else None,
                    "deploy_order": package.get("deploy_order", 0),
                    "supported_scopes": package.get("supported_scopes") or ["ENV"],
                    "resolution_error": None if mapping is not None else "No matching environment host mapping found.",
                }
            )

    return sorted(resolved_targets, key=lambda item: (item["deploy_order"], item["package_key"]))
