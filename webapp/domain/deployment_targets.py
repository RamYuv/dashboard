"""Deployment target configuration and resolution helpers.

These helpers translate the JSON target configuration into the shapes used by
the deployment request form and the deployment execution workflow.
"""

import json
import logging
from pathlib import Path

from ..component_build_catalog import canonical_build_name


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "deployment_targets.json"

REQUIRED_TARGET_FIELDS = {"display_name"}
REQUIRED_PACKAGE_FIELDS = {"package_name", "server_type_key"}
LOGGER = logging.getLogger(__name__)
_TARGET_CACHE = {
    "mtime": None,
    "targets": {},
}


def _normalize_server_type_key(package):
    """Return the package's single deployment server type key."""
    return (package.get("server_type_key") or package.get("server_role_key") or "").strip()


def _normalize_server_type_list(server_types):
    if isinstance(server_types, str):
        server_types = [server_types]
    normalized = []
    for server_type in server_types or []:
        value = (server_type or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _package_key_from_server_type(server_type_key):
    return (server_type_key or "").strip().lower()


def _build_standard_packages(target_key, target):
    server_types = _normalize_server_type_list(target.get("server_types"))
    build_name = (target.get("build_name") or "").strip().lower()
    packages = {}
    for index, server_type_key in enumerate(server_types):
        package_key = _package_key_from_server_type(server_type_key)
        if not package_key:
            continue
        packages[package_key] = {
            "package_name": build_name or package_key,
            "server_type_key": server_type_key,
        }
    return packages


def _build_tool_packages(target):
    normalized_packages = {}
    for index, tool in enumerate(target.get("tools") or []):
        if not isinstance(tool, dict):
            continue
        build_name = (tool.get("build_name") or tool.get("tool_name") or "").strip().lower()
        server_types = _normalize_server_type_list(tool.get("server_types"))
        if not build_name or not server_types:
            continue
        normalized_packages[build_name] = {
            "package_name": build_name,
            "server_type_key": server_types[0],
        }
    return normalized_packages


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
        build_name = (target.get("build_name") or "").strip().lower()

        raw_packages = target.get("packages")
        if isinstance(raw_packages, dict) and raw_packages:
            packages = raw_packages
        elif (target_key or "").strip().upper() == "TOOLS":
            packages = _build_tool_packages(target)
        else:
            packages = _build_standard_packages(target_key, target)

        if not isinstance(packages, dict) or not packages:
            validation_errors.append(
                "Target '{}' must define at least one server or tool mapping.".format(target_key)
            )
            continue

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
            normalized_packages[package_key] = {
                "package_name": package.get("package_name") or package_key,
                "server_type_key": server_type_key,
            }

        if not normalized_packages:
            validation_errors.append(
                "Target '{}' has no valid packages after normalization.".format(target_key)
            )
            continue

        normalized[target_key] = {
            "display_name": target.get("display_name") or target_key,
            "build_name": build_name or canonical_build_name(
                target_key,
                selected_package_keys=list(normalized_packages.keys()),
                target_definition={"packages": normalized_packages},
            ),
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
                "build_name": target.get("build_name") or canonical_build_name(
                    target_key,
                    target_definition=target,
                ),
                "default_build_name": canonical_build_name(
                    target_key,
                    target_definition=target,
                ),
                "packages": [
                    {
                        "package_key": package_key,
                        "package_name": package.get("package_name") or package_key,
                        "server_type_key": package.get("server_type_key"),
                    }
                    for package_key, package in packages.items()
                ],
            }
        )
    return options


def get_target_definition(target_key):
    """Return the normalized config block for one target key."""
    return load_deployment_targets().get(target_key or "")
