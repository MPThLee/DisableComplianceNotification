#!/usr/bin/env python3
"""Bind a future-version test candidate to an exact published mod artifact.

The verifier deliberately compares uncompressed ZIP entry bytes instead of whole
JAR bytes. Reproducible builds may change ZIP timestamps or ordering without
changing the executable artifact. Only loader metadata, the JAR manifest, and
pack metadata may differ between the published and candidate JARs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


LOADERS = ("fabric", "neoforge", "forge")
ARCHIVE_BASE_NAME = "disable_compliance_notification"
MOD_ID = "disable_compliance_notification"
DISPLAY_NAME = "Disable Compliance Notification"
GITHUB_REPOSITORY = "MPThLee/DisableComplianceNotification"
REPOSITORY_URL = f"https://github.com/{GITHUB_REPOSITORY}"
CURSEFORGE_LOADERS = {
    "fabric": "Fabric",
    "neoforge": "NeoForge",
    "forge": "Forge",
}
METADATA_PATHS = {
    "fabric": "fabric.mod.json",
    "neoforge": "META-INF/neoforge.mods.toml",
    "forge": "META-INF/mods.toml",
}
ALLOWED_DIFFERENCES = {
    loader: frozenset(
        {
            metadata_path,
            "META-INF/MANIFEST.MF",
            "pack.mcmeta",
        }
    )
    for loader, metadata_path in METADATA_PATHS.items()
}
TEST_BOOTSTRAP_MARKERS = (
    b"dev/mpthlee/minecraft/disable_compliance_notification/test/",
    b"disable_compliance_notification_test.mixins.json",
    b"ComplianceClientGameTest",
    b"ComplianceGameTest",
    b"TrackToastManagerMixin",
)
RELEASE_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
HEX_256_PATTERN = re.compile(r"[0-9a-f]{64}")
HEX_512_PATTERN = re.compile(r"[0-9a-f]{128}")
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
PUBLICATION_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")


class VerificationError(RuntimeError):
    """A published-artifact safety invariant was not satisfied."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a candidate against the exact published release artifact"
    )
    parser.add_argument("--loader", choices=LOADERS, required=True)
    parser.add_argument(
        "--target",
        "--target-minecraft-version",
        dest="target",
        required=True,
        help="exact Minecraft release",
    )
    parser.add_argument("--candidate-jar", type=Path, required=True)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data"
        / "published-release.json",
    )
    parser.add_argument(
        "--published-jar",
        type=Path,
        help="use this local published JAR instead of downloading the bound URL",
    )
    parser.add_argument("--output", type=Path, help="write the result JSON here")
    parser.add_argument("--timeout", type=float, default=60)
    return parser.parse_args(argv)


def require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must be a JSON object")
    return value


def require_string(mapping: dict[str, object], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{label}.{key} must be a non-empty string")
    return value


def require_integer(mapping: dict[str, object], key: str, label: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise VerificationError(f"{label}.{key} must be a positive integer")
    return value


def release_version(value: str, label: str) -> str:
    if RELEASE_VERSION_PATTERN.fullmatch(value) is None:
        raise VerificationError(f"{label} is not a numeric release version: {value}")
    return value


def version_tuple(value: str) -> tuple[int, ...]:
    release_version(value, "Minecraft version")
    return tuple(int(part) for part in value.split("."))


def version_at_least(candidate: str, minimum: str) -> bool:
    candidate_parts = version_tuple(candidate)
    minimum_parts = version_tuple(minimum)
    width = max(len(candidate_parts), len(minimum_parts))
    return candidate_parts + (0,) * (width - len(candidate_parts)) >= (
        minimum_parts + (0,) * (width - len(minimum_parts))
    )


def load_binding(path: Path, loader: str) -> tuple[dict[str, object], dict[str, object]]:
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VerificationError(f"published release data not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON in published release data: {path}") from exc

    root = require_mapping(root, "published release data")
    if root.get("schema_version") != 1:
        raise VerificationError("published release data must use schema_version 1")

    publication = require_mapping(root.get("publication"), "publication")
    publication_id = require_string(publication, "id", "publication")
    if PUBLICATION_ID_PATTERN.fullmatch(publication_id) is None:
        raise VerificationError("publication.id is invalid")

    version = release_version(
        require_string(publication, "release_version", "publication"),
        "publication.release_version",
    )
    tag = require_string(publication, "tag", "publication")
    if tag != f"v{version}":
        raise VerificationError(
            "publication.tag must be v followed by publication.release_version"
        )
    commit = require_string(publication, "source_commit", "publication")
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise VerificationError("publication.source_commit must be a full Git commit")
    build_minecraft_version = release_version(
        require_string(publication, "build_minecraft_version", "publication"),
        "publication.build_minecraft_version",
    )

    repository = require_string(publication, "github_repository", "publication")
    if repository != GITHUB_REPOSITORY:
        raise VerificationError("publication.github_repository is not this project")
    if ID_PATTERN.fullmatch(
        require_string(publication, "modrinth_project_id", "publication")
    ) is None:
        raise VerificationError("publication.modrinth_project_id is invalid")
    require_integer(publication, "curseforge_project_id", "publication")

    artifacts = require_mapping(publication.get("artifacts"), "publication.artifacts")
    if set(artifacts) != set(LOADERS):
        raise VerificationError(
            "published release data must bind exactly fabric, neoforge, and forge"
        )
    artifact = require_mapping(
        artifacts.get(loader), f"publication.artifacts.{loader}"
    )
    filename = require_string(
        artifact, "filename", f"publication.artifacts.{loader}"
    )
    expected_filename = (
        f"{ARCHIVE_BASE_NAME}-v{version}+{loader}-{build_minecraft_version}.jar"
    )
    if filename != expected_filename:
        raise VerificationError(
            f"publication.artifacts.{loader}.filename does not match the bound release"
        )

    url = require_string(
        artifact, "github_url", f"publication.artifacts.{loader}"
    )
    sha256 = require_string(
        artifact, "sha256", f"publication.artifacts.{loader}"
    )
    if HEX_256_PATTERN.fullmatch(sha256) is None:
        raise VerificationError(
            f"publication.artifacts.{loader}.sha256 is invalid"
        )
    parsed_url = urlparse(url)
    expected_path = f"/{repository}/releases/download/{tag}/{filename}"
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc != "github.com"
        or unquote(parsed_url.path) != expected_path
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise VerificationError(
            f"publication.artifacts.{loader}.github_url is not the exact public "
            "release asset URL"
        )

    if ID_PATTERN.fullmatch(
        require_string(
            artifact,
            "modrinth_version_id",
            f"publication.artifacts.{loader}",
        )
    ) is None:
        raise VerificationError(
            f"publication.artifacts.{loader}.modrinth_version_id is invalid"
        )
    sha512 = require_string(
        artifact, "modrinth_sha512", f"publication.artifacts.{loader}"
    )
    if HEX_512_PATTERN.fullmatch(sha512) is None:
        raise VerificationError(
            f"publication.artifacts.{loader}.modrinth_sha512 is invalid"
        )

    require_integer(
        artifact, "curseforge_file_id", f"publication.artifacts.{loader}"
    )
    if (
        require_string(
            artifact,
            "curseforge_loader",
            f"publication.artifacts.{loader}",
        )
        != CURSEFORGE_LOADERS[loader]
    ):
        raise VerificationError(
            f"publication.artifacts.{loader}.curseforge_loader is invalid"
        )
    return root, artifact


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise VerificationError(f"could not hash JAR: {path}") from exc
    return digest.hexdigest()


def download_published(url: str, destination: Path, timeout: float) -> None:
    request = Request(
        url,
        headers={
            "User-Agent": "DisableComplianceNotification/published-artifact-verifier"
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response, destination.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise VerificationError(f"failed to download published artifact: {exc}") from exc


def read_archive(path: Path, label: str) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(path)
    except (FileNotFoundError, zipfile.BadZipFile, OSError) as exc:
        raise VerificationError(f"{label} is not a readable JAR: {path}") from exc

    entries: dict[str, bytes] = {}
    try:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            pure_name = PurePosixPath(name)
            if (
                pure_name.is_absolute()
                or ".." in pure_name.parts
                or "\\" in name
                or name in entries
            ):
                raise VerificationError(f"{label} contains an unsafe entry: {name}")
            entries[name] = archive.read(info)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise VerificationError(f"failed to read {label}: {path}") from exc
    finally:
        archive.close()
    return entries


def reject_test_bootstrap(entries: dict[str, bytes], label: str) -> None:
    for name, content in entries.items():
        name_bytes = name.encode("utf-8", errors="replace")
        for marker in TEST_BOOTSTRAP_MARKERS:
            if marker in name_bytes or marker in content:
                raise VerificationError(
                    f"{label} contains test bootstrap marker {marker.decode()!r} in {name}"
                )


def parse_assignment(text: str, key: str, label: str) -> str:
    matches = re.findall(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]+)"\s*$',
        text,
    )
    if len(matches) != 1:
        raise VerificationError(f"{label} must contain exactly one {key} assignment")
    return matches[0]


def toml_blocks(text: str, header: str) -> list[str]:
    pattern = re.compile(
        rf"(?ms)^\[\[{re.escape(header)}\]\]\s*$"
        rf"(.*?)(?=^\[\[|^\[[^\[]|\Z)"
    )
    return pattern.findall(text)


def parse_toml_identity(
    content: bytes,
    mod_id: str,
    label: str,
) -> tuple[dict[str, str], str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"{label} loader metadata is not UTF-8") from exc

    mod_blocks = toml_blocks(text, "mods")
    if len(mod_blocks) != 1:
        raise VerificationError(f"{label} must contain exactly one [[mods]] block")
    mod_block = mod_blocks[0]
    identity = {
        "mod_id": parse_assignment(mod_block, "modId", label),
        "version": parse_assignment(mod_block, "version", label),
        "display_name": parse_assignment(mod_block, "displayName", label),
    }

    minecraft_ranges = []
    for block in toml_blocks(text, f"dependencies.{mod_id}"):
        if parse_assignment(block, "modId", label) == "minecraft":
            minecraft_ranges.append(parse_assignment(block, "versionRange", label))
    if len(minecraft_ranges) != 1:
        raise VerificationError(
            f"{label} must contain exactly one Minecraft dependency"
        )
    return identity, minecraft_ranges[0]


def parse_metadata(
    entries: dict[str, bytes],
    loader: str,
    label: str,
) -> tuple[str, str]:
    metadata_path = METADATA_PATHS[loader]
    if metadata_path not in entries:
        raise VerificationError(f"{label} is missing {metadata_path}")

    if loader == "fabric":
        try:
            metadata = json.loads(entries[metadata_path])
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VerificationError(f"{label} has invalid fabric.mod.json") from exc
        metadata = require_mapping(metadata, f"{label} fabric.mod.json")
        actual_mod_id = metadata.get("id")
        actual_name = metadata.get("name")
        actual_version = metadata.get("version")
        contact = require_mapping(
            metadata.get("contact"), f"{label} fabric.mod.json contact"
        )
        if (
            contact.get("homepage") != REPOSITORY_URL
            or contact.get("sources") != REPOSITORY_URL
        ):
            raise VerificationError(f"{label} has the wrong project repository identity")
        depends = require_mapping(
            metadata.get("depends"), f"{label} fabric.mod.json depends"
        )
        minecraft_range = depends.get("minecraft")
        if not isinstance(minecraft_range, str):
            raise VerificationError(
                f"{label} has no string Minecraft dependency constraint"
            )
    else:
        parsed, minecraft_range = parse_toml_identity(
            entries[metadata_path], MOD_ID, label
        )
        actual_mod_id = parsed["mod_id"]
        actual_name = parsed["display_name"]
        actual_version = parsed["version"]
        try:
            metadata_text = entries[metadata_path].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise VerificationError(f"{label} loader metadata is not UTF-8") from exc
        issue_url = parse_assignment(metadata_text, "issueTrackerURL", label)
        if issue_url != f"{REPOSITORY_URL}/issues":
            raise VerificationError(f"{label} has the wrong project issue tracker")

    if actual_mod_id != MOD_ID or actual_name != DISPLAY_NAME:
        raise VerificationError(f"{label} has the wrong project manifest identity")
    if not isinstance(actual_version, str) or RELEASE_VERSION_PATTERN.fullmatch(
        actual_version
    ) is None:
        raise VerificationError(f"{label} has an invalid mod version")
    return actual_version, minecraft_range


def open_range_minimum(loader: str, constraint: str, label: str) -> str:
    if loader == "fabric":
        match = re.fullmatch(r">=(\d+(?:\.\d+)*)", constraint)
    else:
        match = re.fullmatch(r"\[(\d+(?:\.\d+)*),\)", constraint)
    if match is None:
        raise VerificationError(
            f"{label} Minecraft dependency must be an open-ended minimum range"
        )
    return match.group(1)


def candidate_version_from_filename(
    path: Path,
    loader: str,
    target: str,
) -> str:
    pattern = re.compile(
        rf"{re.escape(ARCHIVE_BASE_NAME)}-v"
        rf"(?P<version>\d+(?:\.\d+)*)\+{re.escape(loader)}-"
        rf"{re.escape(target)}\.jar"
    )
    match = pattern.fullmatch(path.name)
    if match is None:
        raise VerificationError(
            "candidate JAR filename does not identify its loader and target version"
        )
    return match.group("version")


def compare_archives(
    published: dict[str, bytes],
    candidate: dict[str, bytes],
    loader: str,
) -> None:
    published_names = set(published)
    candidate_names = set(candidate)
    if published_names != candidate_names:
        missing = sorted(published_names - candidate_names)
        added = sorted(candidate_names - published_names)
        raise VerificationError(
            f"candidate JAR entry set differs (missing={missing}, added={added})"
        )

    unexpected = [
        name
        for name in sorted(published_names)
        if published[name] != candidate[name]
        and name not in ALLOWED_DIFFERENCES[loader]
    ]
    if unexpected:
        raise VerificationError(
            "candidate executable/content bytes differ in: " + ", ".join(unexpected)
        )


def verify(
    *,
    loader: str,
    target: str,
    candidate_jar: Path,
    data_path: Path,
    published_jar: Path | None = None,
    timeout: float = 60,
    downloader: Callable[[str, Path, float], None] = download_published,
) -> dict[str, object]:
    if loader not in LOADERS:
        raise VerificationError(f"unsupported loader: {loader}")
    release_version(target, "target")
    root, artifact = load_binding(data_path, loader)
    publication = require_mapping(root["publication"], "publication")

    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    if published_jar is None:
        temporary_directory = tempfile.TemporaryDirectory(
            prefix="disable-compliance-published-"
        )
        published_jar = Path(temporary_directory.name) / str(artifact["filename"])
        downloader(str(artifact["github_url"]), published_jar, timeout)
    try:
        if published_jar.name != artifact["filename"]:
            raise VerificationError(
                "published JAR filename does not match the immutable binding"
            )
        published_sha256 = hash_file(published_jar, "sha256")
        if published_sha256 != artifact["sha256"]:
            raise VerificationError("published JAR SHA-256 does not match the binding")
        published_sha512 = hash_file(published_jar, "sha512")
        if published_sha512 != artifact["modrinth_sha512"]:
            raise VerificationError(
                "published JAR SHA-512 does not match the Modrinth binding"
            )

        published_entries = read_archive(published_jar, "published JAR")
        candidate_entries = read_archive(candidate_jar, "candidate JAR")
        reject_test_bootstrap(published_entries, "published JAR")
        reject_test_bootstrap(candidate_entries, "candidate JAR")

        published_version, published_range = parse_metadata(
            published_entries, loader, "published JAR"
        )
        candidate_version, candidate_range = parse_metadata(
            candidate_entries, loader, "candidate JAR"
        )
        if published_version != publication["release_version"]:
            raise VerificationError(
                "published JAR manifest version does not match the bound release"
            )
        expected_candidate_version = candidate_version_from_filename(
            candidate_jar, loader, target
        )
        if candidate_version != expected_candidate_version:
            raise VerificationError(
                "candidate JAR manifest version does not match its filename"
            )

        published_minimum = open_range_minimum(
            loader, published_range, "published JAR"
        )
        if published_minimum != publication["build_minecraft_version"]:
            raise VerificationError(
                "published JAR minimum does not match its build Minecraft version"
            )
        if not version_at_least(target, published_minimum):
            raise VerificationError(
                f"published JAR metadata does not cover Minecraft {target}"
            )
        candidate_minimum = open_range_minimum(
            loader, candidate_range, "candidate JAR"
        )
        if candidate_minimum != target:
            raise VerificationError(
                "candidate JAR Minecraft minimum does not match the target"
            )

        compare_archives(published_entries, candidate_entries, loader)
        return {
            "schema_version": 1,
            "publication": publication["id"],
            "publication_binding": {
                "release_version": publication["release_version"],
                "source_commit": publication["source_commit"],
                "github_url": artifact["github_url"],
                "modrinth_project_id": publication["modrinth_project_id"],
                "modrinth_version_id": artifact["modrinth_version_id"],
                "curseforge_project_id": publication["curseforge_project_id"],
                "curseforge_file_id": artifact["curseforge_file_id"],
            },
            "loader": loader,
            "target_minecraft_version": target,
            "published_sha256": published_sha256,
            "candidate_sha256": hash_file(candidate_jar, "sha256"),
            "passed": True,
        }
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = verify(
            loader=args.loader,
            target=args.target,
            candidate_jar=args.candidate_jar,
            data_path=args.data,
            published_jar=args.published_jar,
            timeout=args.timeout,
        )
    except VerificationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
