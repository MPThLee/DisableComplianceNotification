#!/usr/bin/env python3
"""Plan published-JAR checks and maintain COMPABILITY.md from their evidence."""

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from compatibility_plan import enumerate_release_versions, load_manifest

LOADERS = ("fabric", "neoforge", "forge")
NAMES = {"fabric": "Fabric", "neoforge": "NeoForge", "forge": "Forge"}
NOTIFICATIONS = {"compliance.playtime.hours", "compliance.playtime.greaterThan24Hours"}


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def load_state(state_path, report_path):
    if not state_path.exists() and report_path.exists():
        raise ValueError(f"Missing {state_path}; refusing to discard existing report history")
    return read(state_path, {"schema_version": 1, "releases": {}})


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def plan(publication, requested, manifest, state=None):
    release = publication["release_version"]
    if tuple(map(int, release.split("."))) < (1, 6, 0):
        raise ValueError("Compatibility reports start at mod 1.6.0")
    entries = {entry["id"]: entry for entry in manifest["versions"]}
    if requested:
        targets = list(dict.fromkeys(v.strip() for v in requested.split(",")))
    else:
        build_version = publication["build_minecraft_version"]
        targets = enumerate_release_versions(manifest, build_version)
        built_at = datetime.fromisoformat(entries[build_version]["releaseTime"])
        targets += [entry["id"] for entry in manifest["versions"]
                    if entry["type"] == "snapshot"
                    and datetime.fromisoformat(entry["releaseTime"]) > built_at]
    previous = (state or {}).get("releases", {}).get(release, {}).get("targets", {})
    matrix = []
    for target in targets:
        if target not in entries or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", target):
            raise ValueError(f"Unknown Minecraft version: {target}")
        entry = entries[target]
        stable = entry["type"] == "release" and re.fullmatch(r"\d+(?:\.\d+)*", target) is not None
        for loader in LOADERS:
            modes = ("core", "deps") if stable and loader != "forge" else ("core",)
            known = previous.get(target, {}).get("loaders", {}).get(loader, {})
            def passed(mode):
                evidence = known.get(mode, {})
                return evidence.get("status") == "passed" and evidence.get("artifact_sha256") == publication["artifacts"][loader]["sha256"]
            for mode in modes:
                if passed(mode) or (not requested and not stable and loader != "fabric"
                        and known.get(mode, {}).get("status") == "unavailable"
                        and known[mode].get("artifact_sha256") == publication["artifacts"][loader]["sha256"]):
                    continue
                matrix.append({"minecraft_version": target, "loader": loader, "mode": mode})
    return {"include": matrix}


def record(preparation, gate, outcome, run_url, log=""):
    if not preparation:
        raise ValueError("No publication-bound preparation result; refusing to invent a result")
    result = dict(preparation)
    result["run_url"] = run_url
    if result["status"] == "ready":
        started = re.search(r"> Task :runClient(?:\s|$)", log) is not None
        result["status"] = "failed" if outcome == "failure" and started else "error"
        result["reason"] = "Runtime check failed" if result["status"] == "failed" else "Runtime setup incomplete"
        if re.search(r"\bbuild/resources/main is not a valid mod file", log):
            result.update(status="error", reason="Test harness resources were rejected")
        if "Failed to create backend OpenGL" in log and "Failed to create backend Vulkan" in log:
            result.update(status="error", reason="Runner graphics initialization failed")
        if outcome == "success" and gate:
            valid = (
                gate.get("passed") is True and gate.get("periodic_toast_absent") is True
                and gate.get("loader") == result["loader"]
                and gate.get("minecraft_version") == result["minecraft_version"]
                and gate.get("requested_in_world_seconds", 0) >= 150
                and gate.get("observed_in_world_seconds", 0) >= 150
                and set(gate.get("filtered_notifications", [])) == NOTIFICATIONS
                and (result["mode"] != "deps" or gate.get("optional_config") in ("passed", "unavailable"))
            )
            if not valid:
                raise ValueError("Runtime evidence is incomplete or belongs to a different target")
            result.update(status="passed", observed_seconds=gate["observed_in_world_seconds"])
            result.pop("reason", None)
            if result["mode"] == "deps":
                result["config_interaction"] = gate["optional_config"]
    return result


def merge(state, results, publication):
    releases = state.setdefault("releases", {})
    for result in results:
        if result["publication"] != publication["release_version"]:
            raise ValueError("Result belongs to a different mod release")
        loader, mode = result["loader"], result["mode"]
        if loader not in LOADERS or mode not in ("core", "deps"):
            raise ValueError("Invalid result loader or mode")
        if result["artifact_sha256"] != publication["artifacts"][loader]["sha256"]:
            raise ValueError("Result belongs to a different published artifact")
        if result.get("channel") not in ("stable", "preview"):
            continue  # Manifest/network failure is not a compatibility finding.
        release = releases.setdefault(result["publication"], {"build_minecraft_version": publication["build_minecraft_version"], "targets": {}})
        target = release["targets"].setdefault(result["minecraft_version"], {
            "channel": result["channel"], "released_at": result.get("released_at", ""), "loaders": {},
        })
        tests = target["loaders"].setdefault(loader, {})
        old = tests.get(mode)
        if old and old.get("status") == "passed" and old.get("artifact_sha256") == result["artifact_sha256"]:
            continue  # Keep the original passing evidence, including dependency versions.
        if old and result["status"] == "error":
            continue  # Preserve known evidence on a transient infrastructure error.
        def meaningful(value):
            return {key: item for key, item in value.items() if key not in ("run_url", "observed_seconds", "checked_at")}
        if old is None or meaningful(old) != meaningful(result) or (not old.get("run_url") and result.get("run_url")):
            tests[mode] = result
    return state


def mark(target, loader):
    checks = target["loaders"].get(loader, {})
    core = checks.get("core", {}).get("status")
    if core == "failed":
        return "❌"
    if core != "passed":
        return "—"
    if target["channel"] == "preview" or loader == "forge":
        return "✅"
    deps = checks.get("deps", {})
    return "✅" if deps.get("status") == "passed" and deps.get("artifact_sha256") == checks["core"].get("artifact_sha256") else "⚠️"


def cell(value):
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ")


def detail_rows(targets):
    lines = ["| Minecraft | Loader | Core | Optional | Versions |", "| --- | --- | :---: | :---: | --- |"]
    labels = {"passed": "Pass", "failed": "Fail", "unavailable": "Unavailable", "error": "Incomplete"}
    for version, target in targets:
        for loader in LOADERS:
            checks = target["loaders"].get(loader, {})
            if not checks:
                continue
            core, deps = checks.get("core", {}), checks.get("deps", {})
            versions = []
            runtime = core.get("runtime") or deps.get("runtime", {})
            key = "fabric_loader_version" if loader == "fabric" else f"{loader}_version"
            if runtime.get(key):
                versions.append(f"Loader {runtime[key]}")
            for project, name in (("yacl", "YACL"), ("modmenu", "Mod Menu")):
                dependency = deps.get("dependencies", {}).get(project)
                if dependency:
                    versions.append(f"{name} {dependency['version']}")
            rendered = "; ".join(cell(version) for version in versions) or "—"
            lines.append(f"| {cell(version)} | {NAMES[loader]} | {labels.get(core.get('status'), '—')} | {labels.get(deps.get('status'), '—')} | {rendered} |")
    return lines


def render(state):
    lines = ["# Compatibility", "", "Automated checks of unchanged published jars. Mod **1.6.0+** only.", "",
        "Last updated: {updated_at}", "", "| Mark | Meaning |", "| :---: | --- |",
        "| ✅ | All applicable checks pass |", "| ⚠️ | Core passes; optional dependencies are not verified working |",
        "| ❌ | Core runtime check failed |", "| — | Not tested, unavailable, or incomplete |"]
    for version in sorted(state.get("releases", {}), key=lambda v: tuple(map(int, v.split("."))), reverse=True):
        if tuple(map(int, version.split("."))) < (1, 6, 0):
            continue
        release = state["releases"][version]
        lines += ["", f"## v{version}", "", f"Built for Minecraft **{release['build_minecraft_version']}+**.", ""]
        targets = sorted(release["targets"].items(), key=lambda item: (item[1].get("released_at", ""), item[0]), reverse=True)
        stable = [(v, t) for v, t in targets if t["channel"] == "stable"]
        preview = [(v, t) for v, t in targets if t["channel"] == "preview"]
        def table(rows):
            return ["| Minecraft | Fabric | NeoForge | Forge |", "| --- | :---: | :---: | :---: |"] + [
                f"| {cell(v)} | " + " | ".join(mark(t, loader) for loader in LOADERS) + " |" for v, t in rows]
        lines += ["### Stable", ""] + (table(stable) if stable else ["No stable results yet."])
        if stable:
            lines += ["", "<details>", "<summary>Test details</summary>", ""] + detail_rows(stable) + ["", "</details>"]
        if preview:
            lines += ["", "<details>", "<summary>Snapshots &amp; release candidates</summary>", "", "Core only. Optional config is not tested.", ""]
            lines += table(preview) + ["", "<details>", "<summary>Test details</summary>", ""] + detail_rows(preview) + ["", "</details>", "", "</details>"]
    return "\n".join(lines) + "\n"


def save_report(state, state_path, report_path):
    template = render(state)
    old = report_path.read_text() if report_path.exists() else ""
    previous_time = re.search(r"^Last updated: (.+)$", old, re.M)
    timestamp = previous_time.group(1) if previous_time else ""
    content = template.replace("{updated_at}", timestamp)
    if content != old:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        content = template.replace("{updated_at}", timestamp)
        report_path.write_text(content)
    write(state_path, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "record", "render"))
    parser.add_argument("--data", type=Path, default=ROOT / "data/published-release.json")
    parser.add_argument("--target", default="")
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--outcome", default="skipped")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--state", type=Path, default=ROOT / "data/compatibility-results.json")
    parser.add_argument("--report", type=Path, default=ROOT / "COMPABILITY.md")
    args = parser.parse_args()
    publication = read(args.data)["publication"]
    if args.command == "plan":
        state = load_state(args.state, args.report)
        planned = plan(publication, args.target, load_manifest(), state)
        matrix = json.dumps(planned, separators=(",", ":"))
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write(f"matrix={matrix}\n")
                output.write(f"has_work={str(bool(planned['include'])).lower()}\n")
        print(matrix)
    elif args.command == "record":
        log = args.log.read_text(errors="replace") if args.log and args.log.exists() else ""
        write(args.output, record(read(args.preparation), read(args.gate), args.outcome, args.run_url, log))
    else:
        state = load_state(args.state, args.report)
        if args.results:
            state = merge(state, [read(path) for path in sorted(args.results.rglob("result.json"))], publication)
        save_report(state, args.state, args.report)


if __name__ == "__main__":
    main()
