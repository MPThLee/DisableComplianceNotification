#!/usr/bin/env python3
"""Detect a newer Minecraft release and optionally prepare a candidate update.

The GitHub workflow calls this tool in two phases: detection first, then ``--apply``
in a disposable Actions checkout. Repository changes are committed only after every
loader build and in-world gate passes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


VERSION_MANIFEST_URL = (
    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
)


class UpdateCheckError(RuntimeError):
    pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="CheckUpdate",
        description="Detect and prepare a test candidate for a newer Minecraft release",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="prepare the candidate in the current checkout",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="select the latest snapshot instead of the latest release",
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--manifest-file",
        type=Path,
        help="read a repository fixture instead of fetching Mojang (for tests)",
    )
    parser.add_argument(
        "--target-version",
        help="use an already-detected exact candidate (requires --apply)",
    )
    parser.add_argument("--timeout", type=float, default=30)
    return parser.parse_args(argv)


def load_manifest(path: Path | None, timeout: float) -> dict[str, object]:
    if path is not None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise UpdateCheckError(f"manifest file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise UpdateCheckError(f"invalid JSON in manifest file: {path}") from exc
    else:
        value = fetch_manifest(timeout)
    if not isinstance(value, dict):
        raise UpdateCheckError("version manifest must contain a JSON object")
    return value


def fetch_manifest(timeout: float) -> dict[str, object]:
    request = Request(
        VERSION_MANIFEST_URL,
        headers={"User-Agent": "DisableComplianceNotification/check-update"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        raise UpdateCheckError(f"failed to fetch version manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpdateCheckError("invalid JSON in Mojang version manifest") from exc
    if not isinstance(value, dict):
        raise UpdateCheckError("Mojang version manifest must contain a JSON object")
    return value


def select_target(manifest: dict[str, object], snapshot: bool) -> str:
    latest = manifest.get("latest")
    if not isinstance(latest, dict):
        raise UpdateCheckError("version manifest is missing latest versions")
    version_type = "snapshot" if snapshot else "release"
    target = latest.get(version_type)
    if not isinstance(target, str) or not target:
        raise UpdateCheckError(f"latest {version_type} not found in manifest")
    return target


def numeric_version(version: str) -> tuple[int, ...] | None:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        return None
    return tuple(int(part) for part in version.split("."))


def is_newer(target: str, current: str, manifest: dict[str, object]) -> bool:
    if target == current:
        return False

    versions = manifest.get("versions")
    if isinstance(versions, list):
        ordered_ids = [
            item.get("id")
            for item in versions
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        if target in ordered_ids and current in ordered_ids:
            return ordered_ids.index(target) < ordered_ids.index(current)

    target_numeric = numeric_version(target)
    current_numeric = numeric_version(current)
    if target_numeric is not None and current_numeric is not None:
        width = max(len(target_numeric), len(current_numeric))
        return target_numeric + (0,) * (width - len(target_numeric)) > current_numeric + (
            0,
        ) * (width - len(current_numeric))

    raise UpdateCheckError(
        f"cannot determine manifest order for current={current}, target={target}"
    )


def read_property(path: Path, key: str) -> str | None:
    content = path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(key)}=(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def update_property(path: Path, key: str, value: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        rf"^{re.escape(key)}=.*$",
        f"{key}={value}",
        content,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise UpdateCheckError(f"expected exactly one {key} property in {path}")
    path.write_text(updated, encoding="utf-8", newline="\n")


def bump_patch(version: str) -> str:
    parts = version.split(".")
    if not parts or not all(part.isdigit() for part in parts):
        raise UpdateCheckError(f"cannot bump non-numeric mod version: {version}")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def run_candidate_update(
    script_dir: Path,
    project_root: Path,
    config_path: Path,
    target: str,
    new_mod_version: str,
) -> None:
    update_property(config_path, "mod_version", new_mod_version)
    subprocess.run(
        [
            sys.executable,
            str(script_dir / "update-version.py"),
            "--to",
            target,
            "--config",
            str(config_path),
            "--oldest",
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(script_dir / "make-template.py"),
            "--game",
            target,
            "--version",
            f"v{new_mod_version}",
            "--download-file",
            str(project_root / "DOWNLOAD.md"),
            "--readme-file",
            str(project_root / "README.md"),
        ],
        check=True,
    )


def set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    config_path = args.config or project_root / "config.properties"
    if not config_path.is_file():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        if args.target_version:
            if not args.apply:
                raise UpdateCheckError("--target-version requires --apply")
            manifest: dict[str, object] = {}
            target = args.target_version
        else:
            manifest = load_manifest(args.manifest_file, args.timeout)
            target = select_target(manifest, args.snapshot)
        current = read_property(config_path, "minecraft_version")
        mod_version = read_property(config_path, "mod_version")
        if not current or not mod_version:
            raise UpdateCheckError(
                "config must contain minecraft_version and mod_version"
            )

        if not is_newer(target, current, manifest):
            message = (
                f"Up to date: {current}"
                if current == target
                else f"No upgrade: current {current}, manifest target {target}"
            )
            print(message)
            set_output("has_update", "false")
            return 0

        new_mod_version = bump_patch(mod_version)
        print(f"Candidate available: Minecraft {current} -> {target}")
        set_output("has_update", "true")
        set_output("new_version", target)
        set_output("old_version", current)
        set_output("mod_version", new_mod_version)

        if args.apply:
            run_candidate_update(
                script_dir,
                project_root,
                config_path,
                target,
                new_mod_version,
            )
            print(
                f"Prepared Minecraft {target}, mod v{new_mod_version}; "
                "the candidate must pass every loader gate before it is committed"
            )
        return 0
    except (OSError, subprocess.CalledProcessError, UpdateCheckError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
