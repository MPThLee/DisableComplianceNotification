#!/usr/bin/env python3
"""Create the immutable publication manifest for a newly released mod version.

This tool intentionally replaces publication history instead of merging it. A new
tag has new marketplace version/file IDs and may advertise only the Minecraft
version whose production artifacts passed every release gate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


LOADERS = ("fabric", "neoforge", "forge")
EXPECTED_NOTIFICATIONS = {
    "compliance.playtime.hours",
    "compliance.playtime.greaterThan24Hours",
}
CURSEFORGE_LOADERS = {
    "fabric": "Fabric",
    "neoforge": "NeoForge",
    "forge": "Forge",
}
GITHUB_REPOSITORY = "MPThLee/DisableComplianceNotification"
ARCHIVE_BASE_NAME = "disable_compliance_notification"
MODRINTH_PROJECT_ID = "vAYtksKy"
CURSEFORGE_PROJECT_ID = 644324
MINIMUM_GATE_SECONDS = 120
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
SHA512_PATTERN = re.compile(r"[0-9a-f]{128}")
MODRINTH_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
FRAGMENT_KEYS = {
    "loader",
    "filename",
    "sha256",
    "sha512",
    "github_url",
    "modrinth_version_id",
    "curseforge_file_id",
}
PUBLICATION_COORDINATE_KEYS = (
    "release_version",
    "build_minecraft_version",
    "source_commit",
    "tag",
    "github_repository",
    "modrinth_project_id",
    "curseforge_project_id",
)
ARTIFACT_COORDINATE_KEYS = (
    "filename",
    "github_url",
    "sha256",
    "modrinth_version_id",
    "modrinth_sha512",
    "curseforge_file_id",
    "curseforge_loader",
)


class PublicationCreationError(RuntimeError):
    """An input cannot safely identify a complete new publication."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create data/published-release.json for a new tagged release"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--publication-fragment",
        action="append",
        type=Path,
        required=True,
        help="repeat once for each loader",
    )
    parser.add_argument(
        "--gate-result",
        action="append",
        type=Path,
        required=True,
        help="repeat once for each loader",
    )
    parser.add_argument(
        "--published-on",
        help="UTC publication date in YYYY-MM-DD form (defaults to today)",
    )
    parser.add_argument(
        "--previous-data",
        type=Path,
        help=(
            "previous published-release.json used to prevent marketplace ID "
            "reuse and immutable publication drift"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PublicationCreationError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> object:
    raise PublicationCreationError(f"invalid non-finite JSON number: {value}")


def read_json(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_json_object,
            parse_constant=reject_json_constant,
        )
    except FileNotFoundError as exc:
        raise PublicationCreationError(f"{description} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PublicationCreationError(f"invalid JSON in {description}: {path}") from exc
    except OSError as exc:
        raise PublicationCreationError(f"could not read {description}: {path}") from exc
    if not isinstance(value, dict):
        raise PublicationCreationError(f"{description} must contain a JSON object")
    return value


def read_config(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise PublicationCreationError(f"config not found: {path}") from exc
    except OSError as exc:
        raise PublicationCreationError(f"could not read config: {path}") from exc

    properties: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise PublicationCreationError(
                f"invalid config line {line_number}: expected key=value"
            )
        key, value = (part.strip() for part in line.split("=", 1))
        if not key or not value:
            raise PublicationCreationError(
                f"invalid config line {line_number}: empty key or value"
            )
        if key in properties:
            raise PublicationCreationError(f"duplicate config property: {key}")
        properties[key] = value

    for key in ("archives_base_name", "mod_version", "minecraft_version"):
        if key not in properties:
            raise PublicationCreationError(f"config is missing {key}")
    if not VERSION_PATTERN.fullmatch(properties["mod_version"]):
        raise PublicationCreationError("config mod_version is not numeric")
    if not VERSION_PATTERN.fullmatch(properties["minecraft_version"]):
        raise PublicationCreationError("config minecraft_version is not numeric")
    if not re.fullmatch(r"[a-z0-9_]+", properties["archives_base_name"]):
        raise PublicationCreationError("config archives_base_name is unsafe")
    if properties["archives_base_name"] != ARCHIVE_BASE_NAME:
        raise PublicationCreationError(
            f"config archives_base_name must be {ARCHIVE_BASE_NAME}"
        )
    return properties


def require_string(
    value: object,
    description: str,
    *,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value:
        raise PublicationCreationError(f"{description} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise PublicationCreationError(f"{description} has an invalid format")
    return value


def require_positive_integer(value: object, description: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise PublicationCreationError(f"{description} must be a positive integer")
    return value


def expected_filename(
    archive_base_name: str,
    mod_version: str,
    minecraft_version: str,
    loader: str,
) -> str:
    return (
        f"{archive_base_name}-v{mod_version}+{loader}-{minecraft_version}.jar"
    )


def validate_github_url(url: str, tag: str, filename: str, loader: str) -> None:
    parsed = urlparse(url)
    expected_path = (
        f"/{GITHUB_REPOSITORY}/releases/download/{tag}/{filename}"
    )
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or unquote(parsed.path) != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise PublicationCreationError(
            f"{loader} github_url is not the exact tagged release asset URL"
        )


def load_fragments(
    paths: list[Path],
    *,
    archive_base_name: str,
    mod_version: str,
    minecraft_version: str,
    tag: str,
) -> dict[str, dict[str, object]]:
    fragments: dict[str, dict[str, object]] = {}
    for path in paths:
        fragment = read_json(path, "publication fragment")
        if set(fragment) != FRAGMENT_KEYS:
            missing = sorted(FRAGMENT_KEYS - set(fragment))
            extra = sorted(set(fragment) - FRAGMENT_KEYS)
            raise PublicationCreationError(
                f"publication fragment {path} has unexpected fields "
                f"(missing={missing}, extra={extra})"
            )

        loader = fragment.get("loader")
        if loader not in LOADERS:
            raise PublicationCreationError(
                f"publication fragment {path} has an invalid loader"
            )
        loader_name = str(loader)
        if loader_name in fragments:
            raise PublicationCreationError(
                f"duplicate publication fragment for {loader_name}"
            )

        filename = require_string(
            fragment.get("filename"), f"{loader_name} filename"
        )
        if filename != expected_filename(
            archive_base_name, mod_version, minecraft_version, loader_name
        ):
            raise PublicationCreationError(
                f"{loader_name} filename does not match the tagged build"
            )
        sha256 = require_string(
            fragment.get("sha256"),
            f"{loader_name} sha256",
            pattern=SHA256_PATTERN,
        )
        sha512 = require_string(
            fragment.get("sha512"),
            f"{loader_name} sha512",
            pattern=SHA512_PATTERN,
        )
        github_url = require_string(
            fragment.get("github_url"), f"{loader_name} github_url"
        )
        validate_github_url(github_url, tag, filename, loader_name)
        modrinth_version_id = require_string(
            fragment.get("modrinth_version_id"),
            f"{loader_name} Modrinth version ID",
            pattern=MODRINTH_ID_PATTERN,
        )
        curseforge_file_id = require_positive_integer(
            fragment.get("curseforge_file_id"),
            f"{loader_name} CurseForge file ID",
        )

        fragments[loader_name] = {
            "filename": filename,
            "github_url": github_url,
            "sha256": sha256,
            "modrinth_version_id": modrinth_version_id,
            "modrinth_sha512": sha512,
            "curseforge_file_id": curseforge_file_id,
            "curseforge_loader": CURSEFORGE_LOADERS[loader_name],
        }

    if set(fragments) != set(LOADERS):
        missing = sorted(set(LOADERS) - set(fragments))
        extra = sorted(set(fragments) - set(LOADERS))
        raise PublicationCreationError(
            "publication fragments must cover exactly every loader "
            f"(missing={missing}, extra={extra})"
        )

    for field in (
        "filename",
        "github_url",
        "sha256",
        "modrinth_sha512",
        "modrinth_version_id",
        "curseforge_file_id",
    ):
        values = [fragments[loader][field] for loader in LOADERS]
        if len(set(values)) != len(values):
            raise PublicationCreationError(
                f"publication fragments contain duplicate {field} values"
            )
    return fragments


def is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def load_gate_results(
    paths: list[Path],
    *,
    minecraft_version: str,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for path in paths:
        result = read_json(path, "gate result")
        if result.get("schema_version") != 1:
            raise PublicationCreationError(
                f"gate result {path} must use schema_version 1"
            )
        loader = result.get("loader")
        if loader not in LOADERS:
            raise PublicationCreationError(f"gate result {path} has an invalid loader")
        loader_name = str(loader)
        if loader_name in results:
            raise PublicationCreationError(f"duplicate gate result for {loader_name}")
        if result.get("minecraft_version") != minecraft_version:
            raise PublicationCreationError(
                f"{loader_name} gate does not target Minecraft {minecraft_version}"
            )
        if result.get("passed") is not True:
            raise PublicationCreationError(f"{loader_name} gate did not pass")
        if result.get("periodic_toast_absent") is not True:
            raise PublicationCreationError(
                f"{loader_name} gate did not verify periodic toast absence"
            )

        minimum = result.get("minimum_in_world_seconds")
        requested = result.get("requested_in_world_seconds")
        observed = result.get("observed_in_world_seconds")
        if not is_number(minimum) or minimum < MINIMUM_GATE_SECONDS:
            raise PublicationCreationError(
                f"{loader_name} gate minimum is shorter than two minutes"
            )
        if not is_number(requested) or requested < minimum:
            raise PublicationCreationError(
                f"{loader_name} gate requested runtime is too short"
            )
        if not is_number(observed) or observed < minimum:
            raise PublicationCreationError(
                f"{loader_name} gate observed runtime is too short"
            )
        filtered = result.get("filtered_notifications")
        if (
            not isinstance(filtered, list)
            or any(not isinstance(item, str) for item in filtered)
            or len(filtered) != len(EXPECTED_NOTIFICATIONS)
            or set(filtered) != EXPECTED_NOTIFICATIONS
        ):
            raise PublicationCreationError(
                f"{loader_name} gate did not filter exactly both notifications"
            )
        results[loader_name] = result

    if set(results) != set(LOADERS):
        missing = sorted(set(LOADERS) - set(results))
        extra = sorted(set(results) - set(LOADERS))
        raise PublicationCreationError(
            "gate results must cover exactly every loader "
            f"(missing={missing}, extra={extra})"
        )
    return results


def create_document(
    *,
    properties: dict[str, str],
    tag: str,
    source_commit: str,
    fragments: dict[str, dict[str, object]],
    gate_results: dict[str, dict[str, object]],
    verified_on: str,
) -> dict[str, object]:
    mod_version = properties["mod_version"]
    minecraft_version = properties["minecraft_version"]
    if tag != f"v{mod_version}":
        raise PublicationCreationError(
            f"release tag {tag} does not match config version v{mod_version}"
        )
    require_string(source_commit, "source commit", pattern=COMMIT_PATTERN)
    try:
        parsed_date = date.fromisoformat(verified_on)
    except ValueError as exc:
        raise PublicationCreationError(
            f"verification date is invalid: {verified_on}"
        ) from exc
    if parsed_date.isoformat() != verified_on:
        raise PublicationCreationError(
            f"verification date is invalid: {verified_on}"
        )
    if set(fragments) != set(LOADERS):
        raise PublicationCreationError("publication fragments are incomplete")
    if set(gate_results) != set(LOADERS):
        raise PublicationCreationError("gate results are incomplete")

    artifacts = {loader: fragments[loader] for loader in LOADERS}
    runtime_loaders = {
        loader: {
            "observed_in_world_seconds": gate_results[loader][
                "observed_in_world_seconds"
            ],
            "periodic_toast_absent": True,
            "passed": True,
            "artifact_sha256": fragments[loader]["sha256"],
        }
        for loader in LOADERS
    }
    return {
        "schema_version": 1,
        "publication": {
            "id": tag,
            "release_version": mod_version,
            "build_minecraft_version": minecraft_version,
            "source_commit": source_commit,
            "tag": tag,
            "github_repository": GITHUB_REPOSITORY,
            "modrinth_project_id": MODRINTH_PROJECT_ID,
            "curseforge_project_id": CURSEFORGE_PROJECT_ID,
            "artifacts": artifacts,
        },
        "runtime_verification": [
            {
                "minecraft_version": minecraft_version,
                "verified_on": verified_on,
                "required_in_world_seconds": MINIMUM_GATE_SECONDS,
                "filtered_notifications": sorted(EXPECTED_NOTIFICATIONS),
                "loaders": runtime_loaders,
            }
        ],
        "desired_game_versions": [minecraft_version],
    }


def require_object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PublicationCreationError(f"{description} must be a JSON object")
    return value


def previous_publication(
    value: dict[str, object],
) -> tuple[str, dict[str, object], dict[str, dict[str, object]]]:
    if value.get("schema_version") != 1:
        raise PublicationCreationError(
            "previous publication must use schema_version 1"
        )
    publication = require_object(
        value.get("publication"), "previous publication"
    )
    publication_id = require_string(
        publication.get("id"), "previous publication ID"
    )
    raw_artifacts = require_object(
        publication.get("artifacts"), "previous publication artifacts"
    )
    if set(raw_artifacts) != set(LOADERS):
        raise PublicationCreationError(
            "previous publication artifacts must cover exactly every loader"
        )

    artifacts: dict[str, dict[str, object]] = {}
    for loader in LOADERS:
        artifacts[loader] = require_object(
            raw_artifacts[loader],
            f"previous {loader} publication artifact",
        )
        require_string(
            artifacts[loader].get("modrinth_version_id"),
            f"previous {loader} Modrinth version ID",
            pattern=MODRINTH_ID_PATTERN,
        )
        require_positive_integer(
            artifacts[loader].get("curseforge_file_id"),
            f"previous {loader} CurseForge file ID",
        )
    return publication_id, publication, artifacts


def validate_against_previous(
    document: dict[str, object],
    previous: dict[str, object],
) -> None:
    previous_id, previous_coordinates, previous_artifacts = previous_publication(
        previous
    )
    publication = require_object(document.get("publication"), "publication")
    publication_id = require_string(publication.get("id"), "publication ID")
    artifacts = require_object(
        publication.get("artifacts"), "publication artifacts"
    )

    if previous_id == publication_id:
        for key in PUBLICATION_COORDINATE_KEYS:
            if previous_coordinates.get(key) != publication.get(key):
                raise PublicationCreationError(
                    f"rerun of {publication_id} changed publication coordinate {key}"
                )
        for loader in LOADERS:
            artifact = require_object(
                artifacts.get(loader), f"{loader} publication artifact"
            )
            for key in ARTIFACT_COORDINATE_KEYS:
                if previous_artifacts[loader].get(key) != artifact.get(key):
                    raise PublicationCreationError(
                        f"rerun of {publication_id} changed {loader} artifact "
                        f"coordinate {key}"
                    )
        return

    previous_modrinth_ids = {
        require_string(
            artifact.get("modrinth_version_id"),
            f"previous {loader} Modrinth version ID",
            pattern=MODRINTH_ID_PATTERN,
        )
        for loader, artifact in previous_artifacts.items()
    }
    previous_curseforge_ids = {
        require_positive_integer(
            artifact.get("curseforge_file_id"),
            f"previous {loader} CurseForge file ID",
        )
        for loader, artifact in previous_artifacts.items()
    }
    for loader in LOADERS:
        artifact = require_object(
            artifacts.get(loader), f"{loader} publication artifact"
        )
        modrinth_id = require_string(
            artifact.get("modrinth_version_id"),
            f"{loader} Modrinth version ID",
            pattern=MODRINTH_ID_PATTERN,
        )
        if modrinth_id in previous_modrinth_ids:
            raise PublicationCreationError(
                f"{publication_id} reuses prior Modrinth version ID {modrinth_id}"
            )
        curseforge_id = require_positive_integer(
            artifact.get("curseforge_file_id"),
            f"{loader} CurseForge file ID",
        )
        if curseforge_id in previous_curseforge_ids:
            raise PublicationCreationError(
                f"{publication_id} reuses prior CurseForge file ID {curseforge_id}"
            )


def write_json(path: Path, value: dict[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
    except OSError as exc:
        raise PublicationCreationError(f"could not prepare output: {path}") from exc
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    except OSError as exc:
        raise PublicationCreationError(f"could not write output: {path}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        properties = read_config(args.config)
        mod_version = properties["mod_version"]
        minecraft_version = properties["minecraft_version"]
        if args.tag != f"v{mod_version}":
            raise PublicationCreationError(
                f"release tag {args.tag} does not match config version v{mod_version}"
            )
        if COMMIT_PATTERN.fullmatch(args.source_commit) is None:
            raise PublicationCreationError(
                "source commit must be a full lowercase Git SHA"
            )
        fragments = load_fragments(
            args.publication_fragment,
            archive_base_name=properties["archives_base_name"],
            mod_version=mod_version,
            minecraft_version=minecraft_version,
            tag=args.tag,
        )
        gates = load_gate_results(
            args.gate_result,
            minecraft_version=minecraft_version,
        )
        published_on = (
            args.published_on
            if args.published_on is not None
            else datetime.now(timezone.utc).date().isoformat()
        )
        document = create_document(
            properties=properties,
            tag=args.tag,
            source_commit=args.source_commit,
            fragments=fragments,
            gate_results=gates,
            verified_on=published_on,
        )
        if args.previous_data is not None:
            previous = read_json(args.previous_data, "previous publication data")
            validate_against_previous(document, previous)
        write_json(args.output, document)
    except (KeyError, PublicationCreationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Created publication manifest for {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
