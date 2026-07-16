#!/usr/bin/env python3
"""Plan compatibility gates for one exact published mod release.

The planner is deliberately independent from Gradle. It resolves dependency
coordinates through the importable functions in ``update-version.py``, binds the
result to the immutable publication identity, and schedules only runtime evidence
that is missing or stale for that exact resolved configuration.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MOJANG_VERSION_MANIFEST_URL = (
    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
)
USER_AGENT = "DisableComplianceNotification/compatibility-plan"
LOADERS = ("fabric", "neoforge", "forge")
EXPECTED_NOTIFICATIONS = {
    "compliance.playtime.hours",
    "compliance.playtime.greaterThan24Hours",
}
MINIMUM_GATE_SECONDS = 120
NUMERIC_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
PROPERTY_PATTERN = re.compile(r"^([^#!\s][^=:\s]*)\s*[=:]\s*(.*)$")
TARGET_UPDATE_KEYS = (
    "minecraft_version",
    "forge_version",
    "neoforge_version",
    "pack_format",
    "java_version",
    "fabric_loader_version",
    "fabric_api_version",
    "yacl_version",
    "modmenu_version",
)


class CompatibilityPlanError(RuntimeError):
    """Raised when a compatibility plan cannot be produced safely."""


@dataclass(frozen=True)
class SourceConfig:
    """Parsed source configuration and its original renderable text."""

    path: Path
    text: str
    properties: dict[str, str]


DependencyResolver = Callable[..., object]


def read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompatibilityPlanError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CompatibilityPlanError(f"invalid JSON in {label}: {path}") from exc
    if not isinstance(value, dict):
        raise CompatibilityPlanError(f"{label} must contain a JSON object")
    return value


def load_manifest(
    path: Path | None = None, *, timeout: float = 30
) -> dict[str, object]:
    """Load a Mojang version manifest or a repository test fixture."""

    if path is not None:
        return read_json_object(path, label="version manifest")

    request = Request(
        MOJANG_VERSION_MANIFEST_URL,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        raise CompatibilityPlanError(
            f"failed to fetch Mojang version manifest: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CompatibilityPlanError(
            "Mojang version manifest returned invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise CompatibilityPlanError(
            "Mojang version manifest must contain a JSON object"
        )
    return value


def validate_numeric_version(version: object, *, label: str) -> str:
    if not isinstance(version, str) or not NUMERIC_VERSION_PATTERN.fullmatch(
        version
    ):
        raise CompatibilityPlanError(f"{label} must be a numeric release version")
    return version


def numeric_version(version: str) -> tuple[int, ...]:
    validate_numeric_version(version, label="Minecraft version")
    return tuple(int(part) for part in version.split("."))


def compare_numeric_versions(left: str, right: str) -> int:
    left_parts = numeric_version(left)
    right_parts = numeric_version(right)
    width = max(len(left_parts), len(right_parts))
    normalized_left = left_parts + (0,) * (width - len(left_parts))
    normalized_right = right_parts + (0,) * (width - len(right_parts))
    if normalized_left < normalized_right:
        return -1
    if normalized_left > normalized_right:
        return 1
    if len(left_parts) < len(right_parts):
        return -1
    if len(left_parts) > len(right_parts):
        return 1
    return 0


def latest_release(manifest: Mapping[str, object]) -> str:
    latest = manifest.get("latest")
    if not isinstance(latest, Mapping):
        raise CompatibilityPlanError("version manifest is missing latest versions")
    return validate_numeric_version(
        latest.get("release"), label="latest Minecraft release"
    )


def enumerate_release_versions(
    manifest: Mapping[str, object], build_version: str
) -> list[str]:
    """Return every numeric release from the build through latest, oldest first."""

    build_version = validate_numeric_version(
        build_version, label="publication build Minecraft version"
    )
    latest = latest_release(manifest)
    if compare_numeric_versions(latest, build_version) < 0:
        raise CompatibilityPlanError(
            f"latest Minecraft release {latest} predates publication build "
            f"{build_version}"
        )

    entries = manifest.get("versions")
    if not isinstance(entries, list):
        raise CompatibilityPlanError("version manifest versions must be an array")

    releases = {build_version, latest}
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("type") != "release":
            continue
        version = entry.get("id")
        if not isinstance(version, str) or not NUMERIC_VERSION_PATTERN.fullmatch(
            version
        ):
            continue
        if (
            compare_numeric_versions(version, build_version) >= 0
            and compare_numeric_versions(version, latest) <= 0
        ):
            releases.add(version)

    max_width = max(len(numeric_version(version)) for version in releases)

    def sort_key(version: str) -> tuple[tuple[int, ...], int, str]:
        parts = numeric_version(version)
        return (
            parts + (0,) * (max_width - len(parts)),
            len(parts),
            version,
        )

    return sorted(releases, key=sort_key)


def parse_properties(text: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        match = PROPERTY_PATTERN.match(line)
        if match is None:
            raise CompatibilityPlanError(
                f"unsupported config.properties syntax on line {line_number}"
            )
        key, value = match.groups()
        if key in properties:
            raise CompatibilityPlanError(
                f"duplicate config.properties key: {key}"
            )
        properties[key] = value.strip()
    if not properties:
        raise CompatibilityPlanError("source config contains no properties")
    return properties


def load_source_config(path: Path) -> SourceConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CompatibilityPlanError(f"source config not found: {path}") from exc
    return SourceConfig(path=path, text=text, properties=parse_properties(text))


def render_properties(source: SourceConfig, properties: Mapping[str, str]) -> str:
    if set(properties) != set(source.properties):
        missing = sorted(set(source.properties) - set(properties))
        extra = sorted(set(properties) - set(source.properties))
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        raise CompatibilityPlanError(
            "resolved config keys differ from source config"
            + (": " + "; ".join(detail) if detail else "")
        )

    rendered_lines: list[str] = []
    for line in source.text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        match = PROPERTY_PATTERN.match(body)
        if match is None:
            rendered_lines.append(line)
            continue
        key = match.group(1)
        rendered_lines.append(f"{key}={properties[key]}{ending}")

    if source.text and not source.text.endswith(("\n", "\r")):
        return "".join(rendered_lines)
    return "".join(rendered_lines)


def load_publication(path: Path) -> dict[str, object]:
    data = read_json_object(path, label="published release")
    if data.get("schema_version") != 1:
        raise CompatibilityPlanError("unsupported published-release schema")
    publication = data.get("publication")
    if not isinstance(publication, dict):
        raise CompatibilityPlanError("publication must be an object")

    for key in ("id", "release_version", "source_commit"):
        value = publication.get(key)
        if not isinstance(value, str) or not value:
            raise CompatibilityPlanError(
                f"publication.{key} must be a non-empty string"
            )
    validate_numeric_version(
        publication.get("build_minecraft_version"),
        label="publication.build_minecraft_version",
    )

    artifacts = publication.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(LOADERS):
        raise CompatibilityPlanError(
            "publication artifacts must cover exactly: " + ", ".join(LOADERS)
        )
    for loader in LOADERS:
        artifact = artifacts.get(loader)
        digest = artifact.get("sha256") if isinstance(artifact, dict) else None
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(
            digest.lower()
        ):
            raise CompatibilityPlanError(
                f"publication artifact for {loader} has an invalid sha256"
            )

    records = data.get("runtime_verification", [])
    if not isinstance(records, list):
        raise CompatibilityPlanError("runtime_verification must be an array")
    return data


def publication_identity(data: Mapping[str, object]) -> dict[str, str]:
    publication = data.get("publication")
    if not isinstance(publication, Mapping):
        raise CompatibilityPlanError("publication must be an object")
    identity: dict[str, str] = {}
    for key in (
        "id",
        "tag",
        "release_version",
        "build_minecraft_version",
        "source_commit",
    ):
        value = publication.get(key)
        if key == "tag" and value is None:
            continue
        if not isinstance(value, str) or not value:
            raise CompatibilityPlanError(
                f"publication.{key} must be a non-empty string"
            )
        identity[key] = value
    return identity


def validate_source_identity(
    publication_data: Mapping[str, object], source: SourceConfig
) -> None:
    publication = publication_data.get("publication")
    if not isinstance(publication, Mapping):
        raise CompatibilityPlanError("publication must be an object")
    expected_minecraft = publication.get("build_minecraft_version")
    expected_mod = publication.get("release_version")
    actual_minecraft = source.properties.get("minecraft_version")
    actual_mod = source.properties.get("mod_version")
    if actual_minecraft != expected_minecraft:
        raise CompatibilityPlanError(
            "source config Minecraft version does not match the publication build: "
            f"{actual_minecraft!r} != {expected_minecraft!r}"
        )
    if actual_mod != expected_mod:
        raise CompatibilityPlanError(
            "source config mod version does not match the publication release: "
            f"{actual_mod!r} != {expected_mod!r}"
        )
    missing = [key for key in TARGET_UPDATE_KEYS if key not in source.properties]
    if missing:
        raise CompatibilityPlanError(
            "source config is missing target dependency keys: "
            + ", ".join(missing)
        )


@lru_cache(maxsize=1)
def _load_update_version_module():
    module_path = Path(__file__).with_name("update-version.py")
    module_name = "_disable_compliance_notification_update_version"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise CompatibilityPlanError(
            f"cannot import dependency resolver: {module_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _versions_to_updates(value: object, target: str) -> dict[str, str]:
    if isinstance(value, Mapping) and all(
        key in value for key in TARGET_UPDATE_KEYS
    ):
        updates = {key: str(value[key]) for key in TARGET_UPDATE_KEYS}
    else:
        field_names = {
            "minecraft_version": "minecraft",
            "forge_version": "forge",
            "neoforge_version": "neoforge",
            "pack_format": "pack_format",
            "java_version": "java_version",
            "fabric_loader_version": "fabric_loader",
            "fabric_api_version": "fabric_api",
            "yacl_version": "yacl",
            "modmenu_version": "modmenu",
        }
        raw: dict[str, str] = {}
        for property_name, field_name in field_names.items():
            if isinstance(value, Mapping):
                field_value = value.get(field_name)
            else:
                field_value = getattr(value, field_name, None)
            if field_value is None:
                raise CompatibilityPlanError(
                    f"dependency resolver result is missing {field_name}"
                )
            raw[property_name] = str(field_value)
        updates = raw

    updates["fabric_api_version"] = updates["fabric_api_version"].split("+", 1)[0]
    updates["yacl_version"] = re.sub(
        r"-(fabric|neoforge)$", "", updates["yacl_version"]
    )
    if updates["minecraft_version"] != target:
        raise CompatibilityPlanError(
            "dependency resolver returned the wrong Minecraft version: "
            f"{updates['minecraft_version']} != {target}"
        )
    if any(not value for value in updates.values()):
        raise CompatibilityPlanError("dependency resolver returned an empty version")
    return updates


def default_dependency_resolver(
    target: str, *, timeout: float, select_oldest: bool
) -> object:
    """Resolve versions using ``update-version.py`` without invoking Gradle."""

    module = _load_update_version_module()
    try:
        return module.load_versions(
            target,
            timeout=timeout,
            select_oldest=select_oldest,
        )
    except module.VersionUpdateError as exc:
        raise CompatibilityPlanError(
            f"failed to resolve dependencies for Minecraft {target}: {exc}"
        ) from exc


def resolve_target_config(
    source: SourceConfig,
    target: str,
    *,
    resolver: DependencyResolver = default_dependency_resolver,
    timeout: float = 30,
) -> dict[str, str]:
    """Resolve one target while retaining the publication's mod version."""

    target = validate_numeric_version(target, label="target Minecraft version")
    try:
        resolved = resolver(target, timeout=timeout, select_oldest=True)
    except CompatibilityPlanError:
        raise
    except Exception as exc:
        raise CompatibilityPlanError(
            f"failed to resolve dependencies for Minecraft {target}: {exc}"
        ) from exc
    updates = _versions_to_updates(resolved, target)
    properties = dict(source.properties)
    properties.update(updates)
    properties["mod_version"] = source.properties["mod_version"]
    return dict(sorted(properties.items()))


def compute_dependency_fingerprint(
    resolved_config: Mapping[str, str],
) -> str:
    """Hash the complete resolved properties map in a stable representation."""

    normalized: dict[str, str] = {}
    for key, value in resolved_config.items():
        if not isinstance(key, str) or not key:
            raise CompatibilityPlanError(
                "resolved config contains an invalid property name"
            )
        if not isinstance(value, str):
            raise CompatibilityPlanError(
                f"resolved config property {key} must be a string"
            )
        normalized[key] = value
    payload = {
        "schema_version": 1,
        "resolved_config": dict(sorted(normalized.items())),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _runtime_records_by_version(
    publication_data: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    value = publication_data.get("runtime_verification", [])
    if not isinstance(value, list):
        raise CompatibilityPlanError("runtime_verification must be an array")
    records: dict[str, Mapping[str, object]] = {}
    for record in value:
        if not isinstance(record, Mapping):
            raise CompatibilityPlanError(
                "runtime_verification entries must be objects"
            )
        version = validate_numeric_version(
            record.get("minecraft_version"),
            label="runtime verification Minecraft version",
        )
        if version in records:
            raise CompatibilityPlanError(
                f"duplicate runtime verification for Minecraft {version}"
            )
        records[version] = record
    return records


def _number_at_least(value: object, minimum: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value >= minimum
    )


def stale_loaders_for_target(
    publication_data: Mapping[str, object],
    record: Mapping[str, object] | None,
    dependency_fingerprint: str,
) -> list[str]:
    """Return loaders whose exact-publication runtime proof is missing or stale."""

    if (
        record is None
        or record.get("dependency_fingerprint") != dependency_fingerprint
    ):
        return list(LOADERS)

    publication = publication_data.get("publication")
    if not isinstance(publication, Mapping):
        raise CompatibilityPlanError("publication must be an object")
    publication_id = publication.get("id")
    source_commit = publication.get("source_commit")
    if record.get("publication", publication_id) != publication_id:
        return list(LOADERS)
    if record.get("source_commit", source_commit) != source_commit:
        return list(LOADERS)

    required_seconds = record.get("required_in_world_seconds")
    filtered_notifications = record.get("filtered_notifications")
    if (
        not _number_at_least(required_seconds, MINIMUM_GATE_SECONDS)
        or not isinstance(filtered_notifications, list)
        or len(filtered_notifications) != len(EXPECTED_NOTIFICATIONS)
        or not all(
            isinstance(notification, str)
            for notification in filtered_notifications
        )
        or set(filtered_notifications) != EXPECTED_NOTIFICATIONS
    ):
        return list(LOADERS)
    verified_on = record.get("verified_on")
    if verified_on is not None:
        if not isinstance(verified_on, str):
            return list(LOADERS)
        try:
            date.fromisoformat(verified_on)
        except ValueError:
            return list(LOADERS)
    loaders = record.get("loaders")
    artifacts = publication.get("artifacts")
    if not isinstance(loaders, Mapping) or not isinstance(artifacts, Mapping):
        return list(LOADERS)

    for loader in LOADERS:
        evidence = loaders.get(loader)
        artifact = artifacts.get(loader)
        expected_hash = (
            artifact.get("sha256") if isinstance(artifact, Mapping) else None
        )
        if (
            not isinstance(evidence, Mapping)
            or evidence.get("passed") is not True
            or evidence.get("periodic_toast_absent") is not True
            or evidence.get("artifact_sha256") != expected_hash
            or not _number_at_least(
                evidence.get("observed_in_world_seconds"),
                float(required_seconds),
            )
        ):
            return list(LOADERS)
    return []


def build_compatibility_plan(
    publication_data: Mapping[str, object],
    source: SourceConfig,
    manifest: Mapping[str, object],
    *,
    resolver: DependencyResolver = default_dependency_resolver,
    timeout: float = 30,
) -> dict[str, object]:
    """Resolve all releases and return a publication-bound compatibility plan."""

    validate_source_identity(publication_data, source)
    identity = publication_identity(publication_data)
    build_version = identity["build_minecraft_version"]
    versions = enumerate_release_versions(manifest, build_version)
    latest = latest_release(manifest)
    records = _runtime_records_by_version(publication_data)

    targets: list[dict[str, object]] = []
    matrix_include: list[dict[str, str]] = []
    for version in versions:
        if version == build_version:
            resolved_config = dict(sorted(source.properties.items()))
        else:
            resolved_config = resolve_target_config(
                source,
                version,
                resolver=resolver,
                timeout=timeout,
            )
        fingerprint = compute_dependency_fingerprint(resolved_config)
        pending_loaders = stale_loaders_for_target(
            publication_data,
            records.get(version),
            fingerprint,
        )
        config_file = f"targets/{version}/config.properties"
        target_plan_file = f"targets/{version}/plan.json"
        target = {
            "minecraft_version": version,
            "dependency_fingerprint": fingerprint,
            "resolved_config": resolved_config,
            "config_file": config_file,
            "target_plan_file": target_plan_file,
            "pending_loaders": pending_loaders,
            "status": "pending" if pending_loaders else "verified",
        }
        targets.append(target)
        for loader in pending_loaders:
            matrix_include.append(
                {
                    "publication": identity["id"],
                    "source_commit": identity["source_commit"],
                    "minecraft_version": version,
                    "loader": loader,
                    "java_version": resolved_config["java_version"],
                    "dependency_fingerprint": fingerprint,
                    "config_file": config_file,
                    "target_plan_file": target_plan_file,
                }
            )

    return {
        "schema_version": 1,
        "publication_id": identity["id"],
        "source_commit": identity["source_commit"],
        "publication": identity,
        "source_config": source.path.as_posix(),
        "latest_minecraft_version": latest,
        "minecraft_versions": versions,
        "loaders": list(LOADERS),
        "targets": targets,
        "matrix": {"include": matrix_include},
        "has_work": bool(matrix_include),
    }


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_plan_bundle(
    plan: Mapping[str, object],
    source: SourceConfig,
    output_dir: Path,
) -> Path:
    """Write the overall plan plus a resolved config and plan for each target."""

    targets = plan.get("targets")
    publication = plan.get("publication")
    if not isinstance(targets, list) or not isinstance(publication, Mapping):
        raise CompatibilityPlanError("invalid compatibility plan")

    for target in targets:
        if not isinstance(target, Mapping):
            raise CompatibilityPlanError("plan targets must be objects")
        version = validate_numeric_version(
            target.get("minecraft_version"),
            label="planned Minecraft version",
        )
        resolved_config = target.get("resolved_config")
        config_file = target.get("config_file")
        target_plan_file = target.get("target_plan_file")
        if (
            not isinstance(resolved_config, Mapping)
            or not isinstance(config_file, str)
            or not isinstance(target_plan_file, str)
        ):
            raise CompatibilityPlanError(
                f"invalid target plan for Minecraft {version}"
            )

        config_path = output_dir / config_file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            render_properties(source, resolved_config),
            encoding="utf-8",
            newline="\n",
        )
        target_matrix = [
            entry
            for entry in plan["matrix"]["include"]
            if entry["minecraft_version"] == version
        ]
        target_plan = {
            "schema_version": 1,
            "publication_id": plan["publication_id"],
            "source_commit": plan["source_commit"],
            "publication": dict(publication),
            "minecraft_version": version,
            "dependency_fingerprint": target["dependency_fingerprint"],
            "resolved_config": dict(resolved_config),
            "config_file": "config.properties",
            "pending_loaders": list(target["pending_loaders"]),
            "status": target["status"],
            "matrix": {"include": target_matrix},
        }
        _write_json(output_dir / target_plan_file, target_plan)

    plan_path = output_dir / "plan.json"
    _write_json(plan_path, plan)
    return plan_path
