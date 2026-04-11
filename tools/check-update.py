#!/usr/bin/env python3
"""
check-update.py — Check for new Minecraft versions and update mod dependencies.

Fetches the Mojang version manifest and compares the latest release (or snapshot)
against minecraft_version in config.properties. With --apply, bumps the mod patch
version and runs update-version.py and make-template.py.

Usage:
    python3 tools/check-update.py              # check only
    python3 tools/check-update.py --apply      # check and apply
    python3 tools/check-update.py --snapshot   # track snapshots
"""

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


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="CheckUpdate",
        description="Check for new Minecraft versions and update dependencies",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the update (bump mod version, run update-version.py, make-template.py)",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Track snapshot versions instead of releases",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.properties",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="HTTP timeout in seconds (default: 30)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    config_path = (
        Path(args.config) if args.config else project_root / "config.properties"
    )

    if not config_path.is_file():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        manifest = fetch_manifest(timeout=args.timeout)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    version_type = "snapshot" if args.snapshot else "release"
    target = manifest.get("latest", {}).get(version_type)
    if not target:
        print(f"Error: latest {version_type} not found in manifest", file=sys.stderr)
        return 1

    current = read_property(config_path, "minecraft_version")
    if not current:
        print("Error: minecraft_version not found in config", file=sys.stderr)
        return 1

    if current == target:
        print(f"Up to date: {current}")
        set_output("has_update", "false")
        return 0

    print(f"Update available: {current} -> {target}")

    mod_version = read_property(config_path, "mod_version")
    if not mod_version:
        print("Error: mod_version not found in config", file=sys.stderr)
        return 1
    new_mod_version = bump_patch(mod_version)

    set_output("has_update", "true")
    set_output("new_version", target)
    set_output("old_version", current)
    set_output("mod_version", new_mod_version)

    if not args.apply:
        return 0

    # Bump mod version
    update_property(config_path, "mod_version", new_mod_version)
    print(f"Bumped mod version: {mod_version} -> {new_mod_version}")

    # Run update-version.py
    print(f"Running update-version.py --to {target}")
    ret = subprocess.run(
        [
            sys.executable,
            str(script_dir / "update-version.py"),
            "--to",
            target,
            "--config",
            str(config_path),
            "--oldest",
        ],
    )
    if ret.returncode != 0:
        print("Error: update-version.py failed", file=sys.stderr)
        return 1

    # Run make-template.py
    print("Running make-template.py")
    ret = subprocess.run(
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
    )
    if ret.returncode != 0:
        print("Error: make-template.py failed", file=sys.stderr)
        return 1

    print(f"Update applied: Minecraft {target}, mod v{new_mod_version}")
    return 0


def fetch_manifest(timeout: float) -> dict:
    req = Request(
        VERSION_MANIFEST_URL,
        headers={"User-Agent": "DisableComplianceNotification/check-update"},
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"failed to fetch version manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid JSON in version manifest") from exc


def read_property(path: Path, key: str) -> str | None:
    content = path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(key)}=(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def update_property(path: Path, key: str, value: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated = re.sub(
        rf"^{re.escape(key)}=.*$",
        f"{key}={value}",
        content,
        flags=re.MULTILINE,
    )
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(updated)


def bump_patch(version: str) -> str:
    """Increment the last component of a version string."""
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def set_output(name: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT if running in GitHub Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


if __name__ == "__main__":
    raise SystemExit(main())
