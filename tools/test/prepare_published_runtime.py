#!/usr/bin/env python3
"""Prepare a disposable test checkout to run the unchanged published JAR."""

import argparse
import json
import re
import runpy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from compatibility_plan import _load_update_version_module

UPDATE = _load_update_version_module()
VERIFY = runpy.run_path(str(ROOT / "tools/verify-published-artifact.py"))


def resolve_target(version, loader):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", version):
        raise ValueError("Invalid Minecraft version")
    manifest = UPDATE.url_json(
        "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json", timeout=30
    )
    if not any(entry.get("id") == version for entry in manifest["versions"]):
        raise ValueError(f"Minecraft version not found: {version}")
    updates = {"minecraft_version": version}
    if loader == "fabric":
        updates["fabric_api_version"] = UPDATE.modrinth(version, "fabric-api", 30)
        loaders = UPDATE.url_json(UPDATE.FABRIC_LOADER_URL, timeout=30)
        candidates = [entry for entry in loaders if entry.get("stable")] or loaders
        updates["fabric_loader_version"] = candidates[0]["version"]
    else:
        updates[f"{loader}_version"] = getattr(UPDATE, loader)(version, 30, False)
    updates["pack_format"], updates["java_version"] = UPDATE.mc_version(version, 30)
    return updates


def prepare(project_root, data, loader, target=None):
    _, artifact = VERIFY["load_binding"](data, loader)
    updates = resolve_target(target, loader) if target else None
    destination = project_root / "published" / artifact["filename"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    VERIFY["download_published"](artifact["github_url"], destination, 30)
    for algorithm, key in (("sha256", "sha256"), ("sha512", "modrinth_sha512")):
        if VERIFY["hash_file"](destination, algorithm) != artifact[key]:
            raise ValueError(f"Published JAR {algorithm} mismatch")
    if updates:
        UPDATE.update_properties(project_root / "config.properties", updates)

    loader_root = project_root / loader
    # Prevent previously compiled production classes/resources shadowing the JAR.
    for directory in ("classes", "resources"):
        shutil.rmtree(loader_root / "build" / directory, ignore_errors=True)
    jar_path = json.dumps(f"../published/{artifact['filename']}")
    with (loader_root / "build.gradle").open("a") as build:
        build.write(f"""
// Published-artifact compatibility harness; compile no production sources.
sourceSets.main.java.setSrcDirs([file('../src/clientgate/java')])
sourceSets.main.resources.setSrcDirs([])
configurations.configureEach {{
    dependencies.removeAll {{ it.group in ['dev.isxander', 'com.terraformersmc'] }}
}}
dependencies.add('implementation', files({jar_path}))
""")
    print(f"Testing unchanged published JAR: {artifact['filename']} ({artifact['sha256']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loader", required=True, choices=("fabric", "neoforge", "forge"))
    parser.add_argument("--target", default=None)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--data", type=Path, default=ROOT / "data/published-release.json")
    args = parser.parse_args()
    try:
        prepare(args.project_root, args.data, args.loader, args.target)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
