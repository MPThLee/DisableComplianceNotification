#!/usr/bin/env python3

from __future__ import annotations

import argparse
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


class CompatibilityRecordError(RuntimeError):
    pass


def read_properties(path: Path) -> dict[str, str]:
    properties: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            properties[key] = value
    return properties


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompatibilityRecordError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CompatibilityRecordError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CompatibilityRecordError(f"expected a JSON object: {path}")
    return value


def load_gate_results(
    paths: list[Path], expected_minecraft_version: str
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for path in paths:
        result = read_json(path)
        loader = result.get("loader")
        if loader not in EXPECTED_LOADERS:
            raise CompatibilityRecordError(f"unexpected loader in {path}: {loader}")
        if loader in results:
            raise CompatibilityRecordError(f"duplicate gate result for {loader}")
        if result.get("schema_version") != 1:
            raise CompatibilityRecordError(f"unsupported gate-result schema in {path}")
        if result.get("minecraft_version") != expected_minecraft_version:
            raise CompatibilityRecordError(
                f"gate result {path} targets {result.get('minecraft_version')}, "
                f"expected {expected_minecraft_version}"
            )
        if result.get("passed") is not True:
            raise CompatibilityRecordError(f"gate did not pass: {path}")

        minimum = result.get("minimum_in_world_seconds")
        requested = result.get("requested_in_world_seconds")
        observed = result.get("observed_in_world_seconds")
        if not isinstance(minimum, (int, float)) or minimum < MINIMUM_GATE_SECONDS:
            raise CompatibilityRecordError(f"gate minimum is shorter than two minutes: {path}")
        if not isinstance(requested, (int, float)) or requested < minimum:
            raise CompatibilityRecordError(f"gate request is shorter than its minimum: {path}")
        if not isinstance(observed, (int, float)) or observed < minimum:
            raise CompatibilityRecordError(f"gate observation is shorter than two minutes: {path}")
        if set(result.get("filtered_notifications", [])) != EXPECTED_NOTIFICATIONS:
            raise CompatibilityRecordError(
                f"gate result does not contain both compliance notifications: {path}"
            )
        results[str(loader)] = result

    missing = EXPECTED_LOADERS - set(results)
    if missing:
        raise CompatibilityRecordError(
            "missing gate results for: " + ", ".join(sorted(missing))
        )
    return results


def version_key(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise CompatibilityRecordError(f"unsupported Minecraft release version: {version}")
    return tuple(int(part) for part in version.split("."))


def current_version_is_verified(
    data: dict[str, object], properties: dict[str, str]
) -> bool:
    minecraft_version = properties.get("minecraft_version")
    release_version = properties.get("mod_version")
    metadata = data.get("metadata_compatibility")
    records = data.get("runtime_verification")
    if (
        data.get("schema_version") != 1
        or not minecraft_version
        or not release_version
        or data.get("release_version") != release_version
        or data.get("build_minecraft_version") != minecraft_version
        or not isinstance(metadata, dict)
        or metadata.get("minimum_version") != minecraft_version
        or metadata.get("range_kind") != "minimum_inclusive"
        or not isinstance(records, list)
    ):
        return False

    matching = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("minecraft_version") == minecraft_version
    ]
    if len(matching) != 1:
        return False
    record = matching[0]
    try:
        date.fromisoformat(str(record["verified_on"]))
    except (KeyError, ValueError):
        return False
    required = record.get("required_in_world_seconds")
    filtered_notifications = record.get("filtered_notifications")
    loaders = record.get("loaders")
    if (
        not isinstance(required, (int, float))
        or required < MINIMUM_GATE_SECONDS
        or not isinstance(filtered_notifications, list)
        or set(filtered_notifications) != EXPECTED_NOTIFICATIONS
        or not isinstance(loaders, dict)
        or set(loaders) != EXPECTED_LOADERS
    ):
        return False
    for result in loaders.values():
        if (
            not isinstance(result, dict)
            or result.get("passed") is not True
            or not isinstance(result.get("observed_in_world_seconds"), (int, float))
            or result["observed_in_world_seconds"] < required
        ):
            return False
    return True


def update_compatibility_data(
    data: dict[str, object],
    properties: dict[str, str],
    gate_results: dict[str, dict[str, object]],
    verified_on: str,
) -> dict[str, object]:
    if data.get("schema_version") != 1:
        raise CompatibilityRecordError("unsupported compatibility-data schema")
    try:
        date.fromisoformat(verified_on)
    except ValueError as exc:
        raise CompatibilityRecordError(f"invalid verification date: {verified_on}") from exc

    minecraft_version = properties.get("minecraft_version")
    release_version = properties.get("mod_version")
    if not minecraft_version or not release_version:
        raise CompatibilityRecordError(
            "config must contain minecraft_version and mod_version"
        )
    if set(gate_results) != EXPECTED_LOADERS:
        raise CompatibilityRecordError("gate results must cover every loader")

    records = data.get("runtime_verification")
    if not isinstance(records, list):
        raise CompatibilityRecordError("runtime_verification must be an array")

    new_record = {
        "minecraft_version": minecraft_version,
        "verified_on": verified_on,
        "required_in_world_seconds": MINIMUM_GATE_SECONDS,
        "filtered_notifications": sorted(EXPECTED_NOTIFICATIONS),
        "loaders": {
            loader: {
                "observed_in_world_seconds": gate_results[loader][
                    "observed_in_world_seconds"
                ],
                "passed": True,
            }
            for loader in sorted(EXPECTED_LOADERS)
        },
    }
    updated_records = [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("minecraft_version") != minecraft_version
    ]
    updated_records.append(new_record)
    updated_records.sort(key=lambda record: version_key(str(record["minecraft_version"])))

    data["release_version"] = release_version
    data["build_minecraft_version"] = minecraft_version
    metadata = data.get("metadata_compatibility")
    if not isinstance(metadata, dict):
        raise CompatibilityRecordError("metadata_compatibility must be an object")
    metadata["minimum_version"] = minecraft_version
    metadata["range_kind"] = "minimum_inclusive"
    data["runtime_verification"] = updated_records
    return data


def write_json(path: Path, data: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record successful all-loader Minecraft compatibility gates."
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--result", action="append", type=Path, default=[])
    parser.add_argument("--verified-on")
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="exit successfully only when the configured version has full stored evidence",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    project_root = Path(__file__).resolve().parent.parent
    config_path = args.config or project_root / "config.properties"
    data_path = args.data or project_root / "data/minecraft-compatibility.json"
    result_paths = args.result or [
        project_root / loader / "build/client-gate-result.json"
        for loader in sorted(EXPECTED_LOADERS)
    ]
    verified_on = args.verified_on or datetime.now(timezone.utc).date().isoformat()

    try:
        properties = read_properties(config_path)
        minecraft_version = properties["minecraft_version"]
        data = read_json(data_path)
        if args.check_current:
            if current_version_is_verified(data, properties):
                print(f"Minecraft {minecraft_version} has complete stored gate evidence")
                return 0
            print(
                f"Minecraft {minecraft_version} does not have complete stored gate evidence",
                file=sys.stderr,
            )
            return 1
        gate_results = load_gate_results(result_paths, minecraft_version)
        data = update_compatibility_data(
            data, properties, gate_results, verified_on
        )
        write_json(data_path, data)
    except (CompatibilityRecordError, KeyError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Recorded Minecraft {minecraft_version} compatibility for "
        + ", ".join(sorted(gate_results))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
