#!/usr/bin/env python3
"""Prepare a disposable checkout to test an unchanged published JAR."""

import argparse
import json
import re
import runpy
import shutil
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from compatibility_plan import _load_update_version_module, load_manifest

UPDATE = _load_update_version_module()
VERIFY = runpy.run_path(str(ROOT / "tools/verify-published-artifact.py"))
OPTIONAL_MODS = {"fabric": ("modmenu", "yacl"), "neoforge": ("yacl",), "forge": ()}


class Unavailable(RuntimeError):
    pass


def minecraft_entry(version):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", version):
        raise ValueError("Invalid Minecraft version")
    for entry in load_manifest()["versions"]:
        if entry["id"] == version:
            return entry
    raise Unavailable(f"Minecraft version not found: {version}")


def latest_mod(project, minecraft, loader):
    query = urlencode({"game_versions": json.dumps([minecraft]), "loaders": json.dumps([loader])})
    versions = UPDATE.url_json(f"https://api.modrinth.com/v2/project/{project}/version?{query}", timeout=30)
    versions = [v for v in versions if minecraft in v["game_versions"] and loader in v["loaders"]]
    if not versions:
        raise Unavailable(f"No compatible {project} release")
    return max(versions, key=lambda v: v["date_published"])


def download_mod(version, destination):
    files = version["files"]
    file = next((f for f in files if f.get("primary")), files[0])
    filename = file["filename"]
    if Path(filename).name != filename or not filename.endswith(".jar"):
        raise ValueError("Invalid dependency filename")
    path = destination / filename
    VERIFY["download_published"](file["url"], path, 30)
    expected = file["hashes"]["sha512"]
    if VERIFY["hash_file"](path, "sha512") != expected:
        raise ValueError("Dependency SHA-512 mismatch")
    return path, expected


def prepare(project_root, data, loader, target=None, mode="core", result=None):
    binding, artifact = VERIFY["load_binding"](data, loader)
    publication = binding["publication"]
    if tuple(map(int, publication["release_version"].split("."))) < (1, 6, 0):
        raise ValueError("Published compatibility checks require mod 1.6.0 or later")
    if target is None:
        config = (project_root / "config.properties").read_text()
        target = re.search(r"^minecraft_version=(.+)$", config, re.M).group(1)
    record = {
        "publication": publication["release_version"], "build_minecraft_version": publication["build_minecraft_version"],
        "artifact_sha256": artifact["sha256"], "minecraft_version": target,
        "loader": loader, "mode": mode, "dependencies": {}, "status": "error",
    }
    try:
        entry = minecraft_entry(target)
        stable = entry["type"] == "release" and re.fullmatch(r"\d+(?:\.\d+)*", target) is not None
        record.update(channel="stable" if stable else "preview", released_at=entry.get("releaseTime", ""))
        if mode == "deps" and (not stable or not OPTIONAL_MODS[loader]):
            raise Unavailable("Optional dependency checks apply to stable Fabric/NeoForge only")
        updates = {"minecraft_version": target}
        if loader == "fabric":
            api = latest_mod("fabric-api", target, loader)
            updates["fabric_api_version"] = api["version_number"]
            loaders = UPDATE.url_json(UPDATE.FABRIC_LOADER_URL, timeout=30)
            candidates = [v for v in loaders if v.get("stable")] or loaders
            if not candidates:
                raise Unavailable("No Fabric loader available")
            updates["fabric_loader_version"] = candidates[0]["version"]
        else:
            try:
                updates[f"{loader}_version"] = getattr(UPDATE, loader)(target, 30, False)
            except UPDATE.VersionUpdateError as exc:
                if "version not found for" in str(exc):
                    raise Unavailable(f"No {loader} loader for this Minecraft version") from exc
                raise
        record["runtime"] = dict(updates)
        updates["pack_format"], updates["java_version"] = UPDATE.mc_version(target, 30)
        destination = project_root / "published"
        destination.mkdir(parents=True, exist_ok=True)
        jar = destination / artifact["filename"]
        VERIFY["download_published"](artifact["github_url"], jar, 30)
        for algorithm, key in (("sha256", "sha256"), ("sha512", "modrinth_sha512")):
            if VERIFY["hash_file"](jar, algorithm) != artifact[key]:
                raise ValueError(f"Published JAR {algorithm} mismatch")
        jars = [jar]
        installed = set()

        def install(version, label):
            if version["project_id"] in installed:
                return
            installed.add(version["project_id"])
            path, digest = download_mod(version, destination)
            jars.append(path)
            record["dependencies"][label] = {"version": version["version_number"], "id": version["id"], "sha512": digest}
            for dependency in version.get("dependencies", []):
                if dependency["dependency_type"] != "required":
                    continue
                project = dependency.get("project_id")
                if project == "P7dR8mSH":  # Fabric API is supplied by the test runtime.
                    continue
                if dependency.get("version_id"):
                    child = UPDATE.url_json(f"https://api.modrinth.com/v2/version/{dependency['version_id']}", timeout=30)
                elif project:
                    child = latest_mod(project, target, loader)
                else:
                    raise Unavailable("Required dependency cannot be resolved")
                if target not in child["game_versions"] or loader not in child["loaders"]:
                    raise Unavailable("Required dependency does not support this runtime")
                project_info = UPDATE.url_json(f"https://api.modrinth.com/v2/project/{child['project_id']}", timeout=30)
                install(child, project_info["title"])

        if mode == "deps":
            for project in OPTIONAL_MODS[loader]:
                install(latest_mod(project, target, loader), project)
        UPDATE.update_properties(project_root / "config.properties", updates)
        loader_root = project_root / loader
        for directory in ("classes", "resources"):
            shutil.rmtree(loader_root / "build" / directory, ignore_errors=True)
        paths = ", ".join(json.dumps(f"../published/{p.name}") for p in jars)
        # FML needs a separate test-mod descriptor to load the instrumentation.
        if loader in ("forge", "neoforge"):
            resources = loader_root / "build/clientgate-resources/META-INF"
            resources.mkdir(parents=True, exist_ok=True)
            descriptor = "mods.toml" if loader == "forge" else "neoforge.mods.toml"
            (resources / descriptor).write_text(
                'modLoader="lowcodefml"\nloaderVersion="[1,)"\nlicense="MIT"\n'
                '[[mods]]\nmodId="dcn_client_gate"\nversion="1"\ndisplayName="DCN client gate"\n'
            )
        with (loader_root / "build.gradle").open("a") as build:
            build.write(f"""
// Compatibility runtime: compile test instrumentation, never the published mod.
sourceSets.main.java.setSrcDirs([file('../src/clientgate/java')])
sourceSets.main.resources.setSrcDirs([])
configurations.configureEach {{
    dependencies.removeAll {{ it.group in ['dev.isxander', 'com.terraformersmc'] }}
}}
dependencies.add('implementation', files({paths}))
""")
            if loader in ("forge", "neoforge"):
                build.write("sourceSets.main.resources.srcDir('build/clientgate-resources')\n")
        record["status"] = "ready"
        return record
    except Unavailable as exc:
        record.update(status="unavailable", reason=str(exc))
        raise
    except Exception as exc:
        record.update(status="error", reason=str(exc))
        raise
    finally:
        if result:
            result.parent.mkdir(parents=True, exist_ok=True)
            result.write_text(json.dumps(record, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loader", required=True, choices=tuple(OPTIONAL_MODS))
    parser.add_argument("--target")
    parser.add_argument("--mode", choices=("core", "deps"), default="core")
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--data", type=Path, default=ROOT / "data/published-release.json")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        prepare(args.project_root, args.data, args.loader, args.target, args.mode, args.result)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
