#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path


EXPECTED_LOADERS = {"fabric", "neoforge", "forge"}
EXPECTED_NOTIFICATIONS = {
    "compliance.playtime.hours",
    "compliance.playtime.greaterThan24Hours",
}
MINIMUM_GATE_SECONDS = 120
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")


class PublishedCompatibilityError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublishedCompatibilityError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PublishedCompatibilityError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PublishedCompatibilityError(f"expected a JSON object: {path}")
    return value


def version_key(version: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(version):
        raise PublishedCompatibilityError(
            f"unsupported Minecraft release version: {version}"
        )
    return tuple(int(part) for part in version.split("."))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_publication(
    data: dict[str, object],
) -> tuple[dict[str, object], dict[str, str]]:
    if data.get("schema_version") != 1:
        raise PublishedCompatibilityError("unsupported published-release schema")

    publication = data.get("publication")
    if not isinstance(publication, dict):
        raise PublishedCompatibilityError("publication must be an object")

    publication_id = publication.get("id")
    release_version = publication.get("release_version")
    build_minecraft_version = publication.get("build_minecraft_version")
    if not isinstance(publication_id, str) or not publication_id:
        raise PublishedCompatibilityError("publication.id must be a non-empty string")
    if not isinstance(release_version, str) or not release_version:
        raise PublishedCompatibilityError(
            "publication.release_version must be a non-empty string"
        )
    if not isinstance(build_minecraft_version, str):
        raise PublishedCompatibilityError(
            "publication.build_minecraft_version must be a string"
        )
    version_key(build_minecraft_version)

    artifacts = publication.get("artifacts")
    if not isinstance(artifacts, dict):
        raise PublishedCompatibilityError("publication.artifacts must be an object")
    if set(artifacts) != EXPECTED_LOADERS:
        raise PublishedCompatibilityError(
            "publication artifacts must cover exactly: "
            + ", ".join(sorted(EXPECTED_LOADERS))
        )

    hashes: dict[str, str] = {}
    for loader in sorted(EXPECTED_LOADERS):
        artifact = artifacts[loader]
        if not isinstance(artifact, dict):
            raise PublishedCompatibilityError(
                f"publication artifact for {loader} must be an object"
            )
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise PublishedCompatibilityError(
                f"publication artifact for {loader} has an invalid sha256"
            )
        hashes[loader] = digest.lower()

    return publication, hashes


def load_gate_results(
    paths: list[Path],
) -> tuple[str, dict[str, dict[str, object]]]:
    results: dict[str, dict[str, object]] = {}
    target_version: str | None = None

    for path in paths:
        result = read_json(path)
        loader = result.get("loader")
        if loader not in EXPECTED_LOADERS:
            raise PublishedCompatibilityError(f"unexpected loader in {path}: {loader}")
        loader_name = str(loader)
        if loader_name in results:
            raise PublishedCompatibilityError(
                f"duplicate gate result for {loader_name}"
            )
        if result.get("schema_version") != 1:
            raise PublishedCompatibilityError(
                f"unsupported gate-result schema in {path}"
            )

        minecraft_version = result.get("minecraft_version")
        if not isinstance(minecraft_version, str):
            raise PublishedCompatibilityError(
                f"gate result has no Minecraft version: {path}"
            )
        version_key(minecraft_version)
        if target_version is None:
            target_version = minecraft_version
        elif minecraft_version != target_version:
            raise PublishedCompatibilityError(
                f"gate result {path} targets {minecraft_version}, "
                f"expected {target_version}"
            )

        if result.get("passed") is not True:
            raise PublishedCompatibilityError(f"gate did not pass: {path}")
        minimum = result.get("minimum_in_world_seconds")
        requested = result.get("requested_in_world_seconds")
        observed = result.get("observed_in_world_seconds")
        if not _is_number(minimum) or minimum < MINIMUM_GATE_SECONDS:
            raise PublishedCompatibilityError(
                f"gate minimum is shorter than two minutes: {path}"
            )
        if not _is_number(requested) or requested < minimum:
            raise PublishedCompatibilityError(
                f"gate request is shorter than its minimum: {path}"
            )
        if not _is_number(observed) or observed < minimum:
            raise PublishedCompatibilityError(
                f"gate observation is shorter than two minutes: {path}"
            )
        filtered = result.get("filtered_notifications")
        if not isinstance(filtered, list) or set(filtered) != EXPECTED_NOTIFICATIONS:
            raise PublishedCompatibilityError(
                f"gate result does not contain both compliance notifications: {path}"
            )
        if result.get("periodic_toast_absent") is not True:
            raise PublishedCompatibilityError(
                f"gate result did not independently verify toast absence: {path}"
            )
        results[loader_name] = result

    if set(results) != EXPECTED_LOADERS:
        missing = EXPECTED_LOADERS - set(results)
        extra = set(results) - EXPECTED_LOADERS
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if extra:
            details.append("unexpected " + ", ".join(sorted(extra)))
        raise PublishedCompatibilityError(
            "gate results must cover exactly every loader"
            + (": " + "; ".join(details) if details else "")
        )
    assert target_version is not None
    return target_version, results


def load_artifact_verifications(
    paths: list[Path],
    *,
    publication_id: str,
    target_minecraft_version: str,
    published_hashes: dict[str, str],
) -> dict[str, dict[str, object]]:
    verifications: dict[str, dict[str, object]] = {}

    for path in paths:
        verification = read_json(path)
        loader = verification.get("loader")
        if loader not in EXPECTED_LOADERS:
            raise PublishedCompatibilityError(f"unexpected loader in {path}: {loader}")
        loader_name = str(loader)
        if loader_name in verifications:
            raise PublishedCompatibilityError(
                f"duplicate artifact verification for {loader_name}"
            )
        if verification.get("schema_version") != 1:
            raise PublishedCompatibilityError(
                f"unsupported artifact-verification schema in {path}"
            )
        if verification.get("publication") != publication_id:
            raise PublishedCompatibilityError(
                f"artifact verification has the wrong publication: {path}"
            )
        if (
            verification.get("target_minecraft_version")
            != target_minecraft_version
        ):
            raise PublishedCompatibilityError(
                f"artifact verification {path} targets "
                f"{verification.get('target_minecraft_version')}, "
                f"expected {target_minecraft_version}"
            )
        if verification.get("passed") is not True:
            raise PublishedCompatibilityError(
                f"published artifact verification did not pass: {path}"
            )

        digest = verification.get("published_sha256")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise PublishedCompatibilityError(
                f"artifact verification has an invalid sha256: {path}"
            )
        if digest.lower() != published_hashes[loader_name]:
            raise PublishedCompatibilityError(
                f"published artifact hash does not match the manifest for "
                f"{loader_name}"
            )
        verifications[loader_name] = verification

    if set(verifications) != EXPECTED_LOADERS:
        missing = EXPECTED_LOADERS - set(verifications)
        raise PublishedCompatibilityError(
            "artifact verifications must cover exactly every loader"
            + (
                ": missing " + ", ".join(sorted(missing))
                if missing
                else ""
            )
        )
    return verifications


def desired_game_versions(data: dict[str, object]) -> list[str]:
    publication = data.get("publication")
    if not isinstance(publication, dict):
        raise PublishedCompatibilityError("publication must be an object")
    build_version = publication.get("build_minecraft_version")
    if not isinstance(build_version, str):
        raise PublishedCompatibilityError(
            "publication.build_minecraft_version must be a string"
        )

    versions = {build_version}
    records = data.get("runtime_verification", [])
    if not isinstance(records, list):
        raise PublishedCompatibilityError("runtime_verification must be an array")
    for record in records:
        if not isinstance(record, dict):
            raise PublishedCompatibilityError(
                "runtime_verification entries must be objects"
            )
        version = record.get("minecraft_version")
        if not isinstance(version, str):
            raise PublishedCompatibilityError(
                "runtime verification has no Minecraft version"
            )
        versions.add(version)
    return sorted(versions, key=version_key)


def update_published_compatibility(
    data: dict[str, object],
    gate_results: dict[str, dict[str, object]],
    artifact_verifications: dict[str, dict[str, object]],
    *,
    target_minecraft_version: str,
    published_hashes: dict[str, str],
    verified_on: str,
) -> dict[str, object]:
    publication_before = copy.deepcopy(data.get("publication"))
    validate_publication(data)
    try:
        date.fromisoformat(verified_on)
    except ValueError as exc:
        raise PublishedCompatibilityError(
            f"invalid verification date: {verified_on}"
        ) from exc
    version_key(target_minecraft_version)

    if set(gate_results) != EXPECTED_LOADERS:
        raise PublishedCompatibilityError(
            "gate results must cover exactly every loader"
        )
    if set(artifact_verifications) != EXPECTED_LOADERS:
        raise PublishedCompatibilityError(
            "artifact verifications must cover exactly every loader"
        )
    if set(published_hashes) != EXPECTED_LOADERS:
        raise PublishedCompatibilityError(
            "published hashes must cover exactly every loader"
        )

    records = data.get("runtime_verification", [])
    if not isinstance(records, list):
        raise PublishedCompatibilityError("runtime_verification must be an array")
    for record in records:
        if not isinstance(record, dict):
            raise PublishedCompatibilityError(
                "runtime_verification entries must be objects"
            )
        version = record.get("minecraft_version")
        if not isinstance(version, str):
            raise PublishedCompatibilityError(
                "runtime verification has no Minecraft version"
            )
        version_key(version)

    new_record = {
        "minecraft_version": target_minecraft_version,
        "verified_on": verified_on,
        "required_in_world_seconds": MINIMUM_GATE_SECONDS,
        "filtered_notifications": sorted(EXPECTED_NOTIFICATIONS),
        "loaders": {
            loader: {
                "observed_in_world_seconds": gate_results[loader][
                    "observed_in_world_seconds"
                ],
                "periodic_toast_absent": True,
                "passed": True,
                "artifact_sha256": published_hashes[loader],
            }
            for loader in sorted(EXPECTED_LOADERS)
        },
    }
    updated_records = [
        record
        for record in records
        if record.get("minecraft_version") != target_minecraft_version
    ]
    updated_records.append(new_record)
    updated_records.sort(
        key=lambda record: version_key(str(record["minecraft_version"]))
    )
    data["runtime_verification"] = updated_records
    data["desired_game_versions"] = desired_game_versions(data)

    if data.get("publication") != publication_before:
        raise PublishedCompatibilityError(
            "publication identity changed while recording compatibility"
        )
    return data


def write_json(path: Path, data: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record compatibility evidence for already-published loader artifacts."
        )
    )
    parser.add_argument("--data", type=Path)
    parser.add_argument("--result", action="append", type=Path, default=[])
    parser.add_argument("--artifact", action="append", type=Path, default=[])
    parser.add_argument("--verified-on")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    project_root = Path(__file__).resolve().parent.parent
    data_path = args.data or project_root / "data/published-release.json"
    result_paths = args.result or [
        project_root / loader / "build/client-gate-result.json"
        for loader in sorted(EXPECTED_LOADERS)
    ]
    artifact_paths = args.artifact or [
        project_root
        / loader
        / "build/published-artifact-verification.json"
        for loader in sorted(EXPECTED_LOADERS)
    ]
    verified_on = args.verified_on or datetime.now(timezone.utc).date().isoformat()

    try:
        data = read_json(data_path)
        publication, published_hashes = validate_publication(data)
        target_version, gate_results = load_gate_results(result_paths)
        artifact_verifications = load_artifact_verifications(
            artifact_paths,
            publication_id=str(publication["id"]),
            target_minecraft_version=target_version,
            published_hashes=published_hashes,
        )
        update_published_compatibility(
            data,
            gate_results,
            artifact_verifications,
            target_minecraft_version=target_version,
            published_hashes=published_hashes,
            verified_on=verified_on,
        )
        write_json(data_path, data)
    except (KeyError, PublishedCompatibilityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Recorded Minecraft {target_version} compatibility for publication "
        f"{publication['id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
