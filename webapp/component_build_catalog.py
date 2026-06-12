"""Helpers for normalizing ComponentBuild rows into one row per build version."""

from os.path import commonprefix


def _normalize_text(value, case=None):
    text = (value or "").strip()
    if not text:
        return ""
    if case == "upper":
        return text.upper()
    if case == "lower":
        return text.lower()
    return text


def _package_lookup(target_definition):
    packages = (target_definition or {}).get("packages") or {}
    lookup = {}
    for package_key, package in packages.items():
        canonical_key = _normalize_text(package_key, case="lower")
        if not canonical_key:
            continue
        lookup[canonical_key] = canonical_key
        package_name = _normalize_text(package.get("package_name"), case="lower")
        server_type_key = _normalize_text(package.get("server_type_key"), case="lower")
        if package_name:
            lookup[package_name] = canonical_key
        if server_type_key:
            lookup[server_type_key] = canonical_key
    return lookup


def normalize_package_keys(selected_package_keys, target_definition=None):
    """Return canonical, unique package keys."""
    lookup = _package_lookup(target_definition)
    normalized = []
    for package_key in selected_package_keys or []:
        raw_key = _normalize_text(package_key, case="lower")
        if not raw_key:
            continue
        canonical_key = lookup.get(raw_key, raw_key)
        if canonical_key not in normalized:
            normalized.append(canonical_key)
    return normalized


def _derive_target_build_name(target_definition, package_keys=None):
    configured_build_name = _normalize_text((target_definition or {}).get("build_name"), case="lower")
    if configured_build_name:
        return configured_build_name

    packages = (target_definition or {}).get("packages") or {}
    selected_keys = normalize_package_keys(package_keys, target_definition=target_definition)
    if not selected_keys:
        selected_keys = list(packages.keys())

    package_names = []
    for package_key in selected_keys:
        package = packages.get(package_key) or {}
        package_name = _normalize_text(package.get("package_name"), case="lower")
        if package_name and package_name not in package_names:
            package_names.append(package_name)

    if not package_names:
        return ""
    if len(package_names) == 1:
        return package_names[0]

    shared_prefix = _normalize_text(commonprefix(package_names), case="lower").rstrip("_- ")
    return shared_prefix or package_names[0]


def canonical_build_name(target_key, selected_package_keys=None, explicit_name=None, target_definition=None):
    """Return the normalized build-name bucket for a version row."""
    target_key = _normalize_text(target_key, case="upper")
    package_keys = normalize_package_keys(selected_package_keys, target_definition=target_definition)
    if target_key == "TOOLS":
        if package_keys:
            return package_keys[0]
        explicit_name = _normalize_text(explicit_name, case="lower")
        if explicit_name:
            return explicit_name
    derived_name = _derive_target_build_name(target_definition, package_keys=package_keys)
    if derived_name:
        return derived_name
    explicit_name = _normalize_text(explicit_name, case="lower")
    if explicit_name:
        return explicit_name
    return _normalize_text(target_key, case="lower")


def _package_entry(package_key, target_definition=None):
    packages = (target_definition or {}).get("packages") or {}
    package = packages.get(package_key) or {}
    return {
        "package_key": package_key,
        "package_name": package.get("package_name") or package_key,
        "server_type_key": package.get("server_type_key"),
    }


def build_package_entries(
    target_key,
    target_definition=None,
    selected_package_keys=None,
    build_name=None,
    artifact_name=None,
    build_metadata=None,
):
    """Return normalized package metadata entries for a build row."""
    packages_by_key = {}
    for package_key in normalize_package_keys(selected_package_keys, target_definition=target_definition):
        entry = _package_entry(package_key, target_definition=target_definition)
        packages_by_key[package_key] = entry

    metadata_packages = (build_metadata or {}).get("packages") or []
    for package_data in metadata_packages:
        if not isinstance(package_data, dict):
            continue
        package_key = normalize_package_keys(
            [package_data.get("package_key") or package_data.get("package_name") or package_data.get("server_type_key")],
            target_definition=target_definition,
        )
        if package_key:
            package_key = package_key[0]
        else:
            package_key = _normalize_text(package_data.get("package_key"), case="lower")
        if not package_key:
            continue
        entry = _package_entry(package_key, target_definition=target_definition)
        entry["package_name"] = package_data.get("package_name") or entry["package_name"]
        entry["server_type_key"] = package_data.get("server_type_key") or entry.get("server_type_key")
        if package_data.get("artifact_name"):
            entry["artifact_name"] = package_data.get("artifact_name")
        if package_data.get("artifact_path"):
            entry["artifact_path"] = package_data.get("artifact_path")
        if package_data.get("checksum"):
            entry["checksum"] = package_data.get("checksum")
        if package_data.get("artifact_size_bytes") is not None:
            entry["artifact_size_bytes"] = package_data.get("artifact_size_bytes")
        packages_by_key[package_key] = entry

    inferred_package_keys = normalize_package_keys([build_name], target_definition=target_definition)
    if inferred_package_keys:
        package_key = inferred_package_keys[0]
        entry = packages_by_key.get(package_key) or _package_entry(package_key, target_definition=target_definition)
        packages_by_key[package_key] = entry

    if packages_by_key:
        return [packages_by_key[key] for key in sorted(packages_by_key.keys())]

    fallback_name = _normalize_text(build_name, case="lower")
    if target_key == "TOOLS" and fallback_name:
        return [_package_entry(fallback_name, target_definition=target_definition)]
    return []

