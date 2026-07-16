#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path


VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")


class MarketplaceSyncError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MarketplaceSyncError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MarketplaceSyncError(f"invalid JSON: {path}") from exc
    except OSError as exc:
        raise MarketplaceSyncError(f"could not read: {path}") from exc
    if not isinstance(value, dict):
        raise MarketplaceSyncError(f"expected a JSON object: {path}")
    return value


def version_key(version: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(version):
        raise MarketplaceSyncError(
            f"unsupported Minecraft release version: {version}"
        )
    return tuple(int(part) for part in version.split("."))


def validate_versions(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise MarketplaceSyncError(f"{field} must be a non-empty array")
    if any(not isinstance(version, str) for version in value):
        raise MarketplaceSyncError(f"{field} must contain only strings")

    versions = list(value)
    for version in versions:
        version_key(version)
    if len(set(versions)) != len(versions):
        raise MarketplaceSyncError(f"{field} must not contain duplicates")
    if versions != sorted(versions, key=version_key):
        raise MarketplaceSyncError(
            f"{field} must be sorted by numeric Minecraft version"
        )
    return versions


def current_target(data: dict[str, object]) -> tuple[str, list[str]]:
    if data.get("schema_version") != 1:
        raise MarketplaceSyncError("unsupported published-release schema")

    publication = data.get("publication")
    if not isinstance(publication, dict):
        raise MarketplaceSyncError("publication must be an object")
    publication_id = publication.get("id")
    if not isinstance(publication_id, str) or not publication_id:
        raise MarketplaceSyncError("publication.id must be a non-empty string")

    desired_versions = validate_versions(
        data.get("desired_game_versions"), "desired_game_versions"
    )
    return publication_id, desired_versions


def validate_sync_record(value: object) -> tuple[str, list[str], str]:
    if not isinstance(value, dict):
        raise MarketplaceSyncError("marketplace_sync must be an object")

    publication_id = value.get("publication")
    if not isinstance(publication_id, str) or not publication_id:
        raise MarketplaceSyncError(
            "marketplace_sync.publication must be a non-empty string"
        )
    versions = validate_versions(
        value.get("game_versions"), "marketplace_sync.game_versions"
    )
    synced_on = value.get("synced_on")
    if not isinstance(synced_on, str):
        raise MarketplaceSyncError("marketplace_sync.synced_on must be a date")
    try:
        date.fromisoformat(synced_on)
    except ValueError as exc:
        raise MarketplaceSyncError(
            "marketplace_sync.synced_on must be an ISO date"
        ) from exc
    return publication_id, versions, synced_on


def check_marketplace_sync(data: dict[str, object]) -> tuple[bool, str]:
    publication_id, desired_versions = current_target(data)
    if "marketplace_sync" not in data:
        return (
            False,
            f"Marketplace sync pending for {publication_id}: no sync record",
        )

    synced_publication, synced_versions, _ = validate_sync_record(
        data["marketplace_sync"]
    )
    if (
        synced_publication == publication_id
        and synced_versions == desired_versions
    ):
        return (
            True,
            f"Marketplace sync is current for {publication_id}: "
            + ", ".join(desired_versions),
        )

    return (
        False,
        f"Marketplace sync pending for {publication_id}: "
        + ", ".join(desired_versions),
    )


def record_marketplace_sync(
    data: dict[str, object], synced_on: str
) -> dict[str, object]:
    publication_id, desired_versions = current_target(data)
    try:
        date.fromisoformat(synced_on)
    except ValueError as exc:
        raise MarketplaceSyncError(f"invalid sync date: {synced_on}") from exc

    if "marketplace_sync" in data:
        validate_sync_record(data["marketplace_sync"])

    data["marketplace_sync"] = {
        "publication": publication_id,
        "game_versions": desired_versions,
        "synced_on": synced_on,
    }
    return data


def write_json_atomic(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(
                temporary_path,
                stat.S_IMODE(path.stat().st_mode),
            )
        os.replace(temporary_path, path)
    except OSError as exc:
        raise MarketplaceSyncError(f"could not update: {path}") from exc
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or record marketplace compatibility synchronization."
    )
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--check",
        action="store_true",
        help="succeed only when the stored marketplace sync is current",
    )
    operation.add_argument(
        "--record",
        action="store_true",
        help="record the current publication and desired game versions as synced",
    )
    parser.add_argument("--data", type=Path)
    parser.add_argument(
        "--synced-on",
        help="ISO date to record; defaults to the current UTC date",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    project_root = Path(__file__).resolve().parent.parent
    data_path = args.data or project_root / "data/published-release.json"

    try:
        data = read_json(data_path)
        if args.check:
            if args.synced_on is not None:
                raise MarketplaceSyncError(
                    "--synced-on can only be used with --record"
                )
            current, message = check_marketplace_sync(data)
            print(message)
            return 0 if current else 1

        synced_on = (
            args.synced_on
            or datetime.now(timezone.utc).date().isoformat()
        )
        record_marketplace_sync(data, synced_on)
        write_json_atomic(data_path, data)
        print(
            f"Recorded marketplace sync for "
            f"{data['marketplace_sync']['publication']}: "
            + ", ".join(data["marketplace_sync"]["game_versions"])
        )
        return 0
    except MarketplaceSyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
