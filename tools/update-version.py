#!/usr/bin/python3

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

DEFAULT_TIMEOUT = 20
USER_AGENT = "Gradle/8.1.1 (Windows 11;10.0;amd64) (Microsoft;17.0.7;17.0.7+7-LTS)"

FABRIC_LOADER_URL = "https://meta.fabricmc.net/v2/versions/loader"
FABRIC_API_METADATA_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml"
)
FORGE_METADATA_URL = (
    "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
)
NEOFORGE_METADATA_URL = (
    "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
)
MC_VERSION_URL = "https://mpthlee.github.io/minecraft-version-json/{mcv}/version.json"
MODRINTH_VERSION_URL = (
    "https://api.modrinth.com/v2/project/{modid}/version?game_versions={game_versions}"
)


@dataclass(frozen=True)
class Versions:
    minecraft: str
    forge: str
    neoforge: str
    pack_format: str
    java_version: str
    fabric_api: str
    fabric_loader: str
    yacl: str
    modmenu: str


class VersionUpdateError(RuntimeError):
    pass


def load_settings(path: Path) -> dict:
    if not path.is_file():
        raise VersionUpdateError(f"settings file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise VersionUpdateError(f"invalid JSON in settings file: {path}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise VersionUpdateError("settings file must contain a JSON object")
    return data


def resolve_config_path(settings: dict, override: str | None) -> Path:
    if override:
        return Path(override)
    value = settings.get("config_path") if settings else None
    return Path(value) if value else Path("config.properties")


def resolve_timeout(settings: dict, override: float | None) -> float:
    if override is not None:
        return override
    value = settings.get("timeout") if settings else None
    if value is None:
        return DEFAULT_TIMEOUT
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise VersionUpdateError("settings.timeout must be a number") from exc


def resolve_select_oldest(settings: dict, override: bool | None) -> bool:
    if override is not None:
        return override
    value = settings.get("select_oldest") if settings else None
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise VersionUpdateError("settings.select_oldest must be a boolean")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="UpdateVersion",
        description="Update dependency versions for a Minecraft version",
    )
    parser.add_argument(
        "-t", "--to", required=True, help="Target Minecraft version (e.g. 1.21.6)"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.properties (overrides settings file)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="HTTP timeout in seconds (overrides settings file)",
    )
    parser.add_argument(
        "--oldest",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Select oldest Fabric API/loader and Forge versions (overrides settings)",
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="Path to JSON settings file (optional)",
    )
    args = parser.parse_args()

    settings = load_settings(Path(args.settings)) if args.settings else {}

    config_path = resolve_config_path(settings, args.config)
    if not config_path.is_file():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        return 1

    timeout = resolve_timeout(settings, args.timeout)
    select_oldest = resolve_select_oldest(settings, args.oldest)

    try:
        versions = load_versions(args.to, timeout=timeout, select_oldest=select_oldest)
    except VersionUpdateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    updates = {
        "minecraft_version": versions.minecraft,
        "forge_version": versions.forge,
        "neoforge_version": versions.neoforge,
        "pack_format": versions.pack_format,
        "java_version": versions.java_version,
        "fabric_loader_version": versions.fabric_loader,
        "fabric_api_version": versions.fabric_api.split("+")[0],
        "yacl_version": re.sub(r"-(fabric|neoforge)$", "", versions.yacl),
        "modmenu_version": versions.modmenu,
    }

    try:
        changed = update_properties(config_path, updates)
    except VersionUpdateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if changed:
        print("Updated config.properties")
    else:
        print("No changes needed")

    return 0


def load_versions(mcv: str, timeout: float, select_oldest: bool) -> Versions:
    tasks = {
        "fabric": (fabric, (mcv, timeout, select_oldest)),
        "forge": (forge, (mcv, timeout, select_oldest)),
        "neoforge": (neoforge, (mcv, timeout, select_oldest)),
        "mc_version": (mc_version, (mcv, timeout)),
        "modmenu": (modrinth, (mcv, "modmenu", timeout)),
        "yacl": (modrinth, (mcv, "yacl", timeout)),
    }

    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_map = {
            executor.submit(func, *args): name for name, (func, args) in tasks.items()
        }
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                errors[name] = exc

    if errors:
        detail = ", ".join(f"{name}: {err}" for name, err in errors.items())
        raise VersionUpdateError(f"failed to load versions ({detail})")

    fabric_api, fabric_loader = results["fabric"]
    pack_format, java_version = results["mc_version"]

    return Versions(
        minecraft=mcv,
        forge=results["forge"],
        neoforge=results["neoforge"],
        pack_format=pack_format,
        java_version=java_version,
        fabric_api=fabric_api,
        fabric_loader=fabric_loader,
        yacl=results["yacl"],
        modmenu=results["modmenu"],
    )


def fabric(mcv: str, timeout: float, select_oldest: bool) -> tuple[str, str]:
    loader_resp = url_json(FABRIC_LOADER_URL, timeout=timeout)
    loader_versions = [entry for entry in loader_resp if isinstance(entry, dict)]
    stable_versions = [
        entry for entry in loader_versions if entry.get("stable") is True
    ]
    loader_candidates = stable_versions or loader_versions
    if not loader_candidates:
        raise VersionUpdateError("fabric loader versions not found")

    loader_entry = loader_candidates[-1] if select_oldest else loader_candidates[0]
    loader_version = loader_entry.get("version")
    if not loader_version:
        raise VersionUpdateError("fabric loader version missing in response")

    maven_resp = url_xml(FABRIC_API_METADATA_URL, timeout=timeout)
    api_versions = parse_maven_versions(maven_resp)
    api_candidates = [version for version in api_versions if f"+{mcv}" in version]
    if not api_candidates:
        raise VersionUpdateError(f"fabric api version not found for {mcv}")

    api_version = api_candidates[0] if select_oldest else api_candidates[-1]
    return api_version, loader_version


def forge(mcv: str, timeout: float, select_oldest: bool) -> str:
    maven_resp = url_xml(FORGE_METADATA_URL, timeout=timeout)
    versions = parse_maven_versions(maven_resp)
    candidates = [version for version in versions if f"{mcv}-" in version]
    if not candidates:
        raise VersionUpdateError(f"forge version not found for {mcv}")

    choice = candidates[0] if select_oldest else candidates[-1]
    return choice.split("-", 1)[1]


def neoforge(mcv: str, timeout: float, select_oldest: bool) -> str:
    maven_resp = url_xml(NEOFORGE_METADATA_URL, timeout=timeout)
    versions = parse_maven_versions(maven_resp)
    candidates = [version for version in versions if f"{mcv[2:]}." in version]
    if not candidates:
        raise VersionUpdateError(f"neoforge version not found for {mcv}")

    return candidates[0] if select_oldest else candidates[-1]


def modrinth(mcv: str, modid: str, timeout: float) -> str:
    game_versions = quote(json.dumps([mcv]))
    url = MODRINTH_VERSION_URL.format(modid=modid, game_versions=game_versions)
    resp = url_json(url, timeout=timeout)
    if not isinstance(resp, list) or not resp:
        raise VersionUpdateError(f"modrinth versions not found for {modid} {mcv}")

    entries = sorted(
        resp, key=lambda entry: entry.get("date_published", ""), reverse=True
    )
    for entry in entries:
        if entry.get("version_type") == "release" and entry.get("version_number"):
            return entry["version_number"]

    for entry in entries:
        if entry.get("version_number"):
            return entry["version_number"]

    raise VersionUpdateError(f"modrinth version number missing for {modid} {mcv}")


def mc_version(mcv: str, timeout: float) -> tuple[str, str]:
    resp = url_json(MC_VERSION_URL.format(mcv=mcv), timeout=timeout)
    pack_ver = resp.get("pack_version")

    if isinstance(pack_ver, dict):
        if "resource_major" in pack_ver:
            major = pack_ver.get("resource_major", 0)
            minor = pack_ver.get("resource_minor", 0)
            pack_ver = f"{major}.{minor}"
        elif "resource" in pack_ver:
            pack_ver = f"{pack_ver.get('resource', 0)}.0"
        else:
            raise VersionUpdateError("unknown pack_version format in response")
    elif pack_ver is not None:
        pack_ver = f"{pack_ver}.0"
    else:
        raise VersionUpdateError("pack_version missing in Minecraft version response")

    java_ver = resp.get("java_version")
    if java_ver is None:
        java_version = "8"
    else:
        try:
            java_version = str(int(java_ver))
        except (TypeError, ValueError):
            java_version = "8"

    return pack_ver, java_version


def update_properties(path: Path, updates: dict[str, str]) -> bool:
    content = path.read_text(encoding="utf-8")
    updated = content
    missing = []

    for key, value in updates.items():
        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        updated, count = re.subn(pattern, replacement, updated, flags=re.M)
        if count == 0:
            missing.append(key)

    if missing:
        missing_keys = ", ".join(missing)
        raise VersionUpdateError(f"missing keys in {path}: {missing_keys}")

    if updated != content:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        return True

    return False


def parse_maven_versions(root: ET.Element) -> list[str]:
    return [
        node.text for node in root.findall("versioning/versions/version") if node.text
    ]


def url_xml(url: str, timeout: float) -> ET.Element:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    return ET.fromstring(fetch_bytes(req, timeout=timeout))


def url_json(url: str, timeout: float):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    raw = fetch_bytes(req, timeout=timeout)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VersionUpdateError(f"invalid JSON response from {url}") from exc


def fetch_bytes(req: Request, timeout: float) -> bytes:
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise VersionUpdateError(f"request failed for {req.full_url}: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
