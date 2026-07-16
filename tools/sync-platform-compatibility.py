#!/usr/bin/env python3
"""Synchronize verified Minecraft versions to existing marketplace releases.

This tool intentionally updates metadata for immutable, already-published files.
The release coordinates and hashes come from ``data/published-release.json``;
runtime verification records in the same file are the only source of Minecraft
versions that may be advertised.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


EXPECTED_LOADERS = ("fabric", "neoforge", "forge")
EXPECTED_CURSEFORGE_LOADERS = {
    "fabric": "Fabric",
    "neoforge": "NeoForge",
    "forge": "Forge",
}
MODRINTH_BASE_URL = "https://api.modrinth.com/v2"
CURSEFORGE_BASE_URL = "https://minecraft.curseforge.com"
USER_AGENT = "DisableComplianceNotification/platform-compatibility-sync"
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
SHA512_PATTERN = re.compile(r"[0-9a-fA-F]{128}")


class PlatformSyncError(RuntimeError):
    """An expected validation or marketplace synchronization failure."""


@dataclass(frozen=True)
class Artifact:
    loader: str
    filename: str
    sha256: str
    modrinth_version_id: str
    modrinth_sha512: str
    curseforge_file_id: int
    curseforge_loader: str


@dataclass(frozen=True)
class Publication:
    publication_id: str
    release_version: str
    build_minecraft_version: str
    modrinth_project_id: str
    curseforge_project_id: str
    artifacts: dict[str, Artifact]


@dataclass(frozen=True)
class PublishedRelease:
    publication: Publication
    verified_minecraft_versions: tuple[str, ...]


@dataclass(frozen=True)
class SyncSummary:
    platform: str
    checked: int
    updated: int


@dataclass(frozen=True)
class ModrinthPlan:
    artifact: Artifact
    current_game_versions: tuple[str, ...]
    merged_game_versions: tuple[str, ...]

    @property
    def needs_update(self) -> bool:
        return self.current_game_versions != self.merged_game_versions


class JsonHttpClient:
    """Small stdlib-only JSON client whose errors never include request headers."""

    def __init__(
        self,
        timeout: float = 30,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        if timeout <= 0:
            raise PlatformSyncError("HTTP timeout must be greater than zero")
        self.timeout = timeout
        self.opener = opener

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> object:
        request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if headers:
            request_headers.update(headers)
        request = Request(
            url,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw_response = response.read()
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise PlatformSyncError(
                f"{method} {url} failed with HTTP {status}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PlatformSyncError(f"{method} {url} failed") from exc

        if not raw_response:
            return None
        try:
            return json.loads(raw_response)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PlatformSyncError(
                f"{method} {url} returned invalid JSON"
            ) from exc


def require_object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PlatformSyncError(f"{description} must be a JSON object")
    return value


def require_string(value: object, description: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlatformSyncError(f"{description} must be a non-empty string")
    return value.strip()


def require_version(value: object, description: str) -> str:
    version = require_string(value, description)
    if not VERSION_PATTERN.fullmatch(version):
        raise PlatformSyncError(f"{description} is not a numeric release version")
    return version


def version_key(version: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(version):
        raise PlatformSyncError(f"invalid Minecraft release version: {version}")
    return tuple(int(part) for part in version.split("."))


def compare_versions(left: str, right: str) -> int:
    left_key = version_key(left)
    right_key = version_key(right)
    width = max(len(left_key), len(right_key))
    padded_left = left_key + (0,) * (width - len(left_key))
    padded_right = right_key + (0,) * (width - len(right_key))
    return (padded_left > padded_right) - (padded_left < padded_right)


def parse_positive_integer(value: object, description: str) -> int:
    if isinstance(value, bool):
        raise PlatformSyncError(f"{description} must be a positive integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit():
        result = int(value)
    else:
        raise PlatformSyncError(f"{description} must be a positive integer")
    if result <= 0:
        raise PlatformSyncError(f"{description} must be a positive integer")
    return result


def parse_artifact(loader: str, value: object) -> Artifact:
    data = require_object(value, f"publication.artifacts.{loader}")
    filename = require_string(data.get("filename"), f"{loader} filename")
    if Path(filename).name != filename:
        raise PlatformSyncError(f"{loader} filename must not contain a path")

    sha256 = require_string(data.get("sha256"), f"{loader} sha256")
    if not SHA256_PATTERN.fullmatch(sha256):
        raise PlatformSyncError(f"{loader} sha256 must contain 64 hexadecimal digits")
    modrinth_sha512 = require_string(
        data.get("modrinth_sha512"), f"{loader} Modrinth sha512"
    )
    if not SHA512_PATTERN.fullmatch(modrinth_sha512):
        raise PlatformSyncError(
            f"{loader} Modrinth sha512 must contain 128 hexadecimal digits"
        )

    curseforge_loader = require_string(
        data.get("curseforge_loader"), f"{loader} CurseForge loader"
    )
    expected_curseforge_loader = EXPECTED_CURSEFORGE_LOADERS[loader]
    if curseforge_loader != expected_curseforge_loader:
        raise PlatformSyncError(
            f"{loader} CurseForge loader must be {expected_curseforge_loader}"
        )

    return Artifact(
        loader=loader,
        filename=filename,
        sha256=sha256.lower(),
        modrinth_version_id=require_string(
            data.get("modrinth_version_id"), f"{loader} Modrinth version ID"
        ),
        modrinth_sha512=modrinth_sha512.lower(),
        curseforge_file_id=parse_positive_integer(
            data.get("curseforge_file_id"), f"{loader} CurseForge file ID"
        ),
        curseforge_loader=curseforge_loader,
    )


def parse_release_data(value: object) -> PublishedRelease:
    root = require_object(value, "published release data")
    if root.get("schema_version") != 1:
        raise PlatformSyncError("unsupported published-release schema")

    publication_data = require_object(root.get("publication"), "publication")
    artifact_data = require_object(
        publication_data.get("artifacts"), "publication.artifacts"
    )
    if set(artifact_data) != set(EXPECTED_LOADERS):
        raise PlatformSyncError(
            "publication artifacts must contain exactly fabric, neoforge, and forge"
        )
    artifacts = {
        loader: parse_artifact(loader, artifact_data[loader])
        for loader in EXPECTED_LOADERS
    }

    filenames = [artifact.filename for artifact in artifacts.values()]
    modrinth_ids = [
        artifact.modrinth_version_id for artifact in artifacts.values()
    ]
    curseforge_ids = [
        artifact.curseforge_file_id for artifact in artifacts.values()
    ]
    for description, identifiers in (
        ("artifact filenames", filenames),
        ("Modrinth version IDs", modrinth_ids),
        ("CurseForge file IDs", curseforge_ids),
    ):
        if len(set(identifiers)) != len(identifiers):
            raise PlatformSyncError(f"{description} must be unique")

    publication = Publication(
        publication_id=require_string(
            publication_data.get("id"), "publication.id"
        ),
        release_version=require_version(
            publication_data.get("release_version"),
            "publication.release_version",
        ),
        build_minecraft_version=require_version(
            publication_data.get("build_minecraft_version"),
            "publication.build_minecraft_version",
        ),
        modrinth_project_id=require_string(
            publication_data.get("modrinth_project_id"),
            "publication.modrinth_project_id",
        ),
        curseforge_project_id=str(
            parse_positive_integer(
                publication_data.get("curseforge_project_id"),
                "publication.curseforge_project_id",
            )
        ),
        artifacts=artifacts,
    )

    records = root.get("runtime_verification")
    if not isinstance(records, list) or not records:
        raise PlatformSyncError("runtime_verification must be a non-empty array")

    verified_versions: list[str] = []
    for index, raw_record in enumerate(records):
        record = require_object(raw_record, f"runtime_verification[{index}]")
        minecraft_version = require_version(
            record.get("minecraft_version"),
            f"runtime_verification[{index}].minecraft_version",
        )
        loaders = require_object(
            record.get("loaders"),
            f"runtime_verification[{index}].loaders",
        )
        if set(loaders) != set(EXPECTED_LOADERS):
            raise PlatformSyncError(
                f"runtime_verification[{index}] must cover every loader"
            )
        for loader in EXPECTED_LOADERS:
            loader_result = require_object(
                loaders[loader],
                f"runtime_verification[{index}].loaders.{loader}",
            )
            if loader_result.get("passed") is not True:
                raise PlatformSyncError(
                    f"Minecraft {minecraft_version} is not verified for {loader}"
                )
        if compare_versions(
            minecraft_version, publication.build_minecraft_version
        ) < 0:
            raise PlatformSyncError(
                f"verified Minecraft version {minecraft_version} is older than "
                f"the publication build {publication.build_minecraft_version}"
            )
        verified_versions.append(minecraft_version)

    if len(set(verified_versions)) != len(verified_versions):
        raise PlatformSyncError(
            "runtime_verification contains duplicate Minecraft versions"
        )
    if publication.build_minecraft_version not in verified_versions:
        raise PlatformSyncError(
            "runtime_verification does not include the publication build version"
        )

    verified_versions.sort(key=version_key)
    return PublishedRelease(publication, tuple(verified_versions))


def load_release_data(path: Path) -> PublishedRelease:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlatformSyncError(f"published release data not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlatformSyncError(f"invalid JSON in published release data: {path}") from exc
    except OSError as exc:
        raise PlatformSyncError(f"could not read published release data: {path}") from exc
    return parse_release_data(value)


def join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if not base.startswith(("https://", "http://")):
        raise PlatformSyncError("marketplace base URL must use HTTP or HTTPS")
    return f"{base}/{path.lstrip('/')}"


def json_request_body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def modrinth_version_url(base_url: str, version_id: str) -> str:
    return join_url(base_url, f"version/{quote(version_id, safe='')}")


def expected_modrinth_version_number(
    publication: Publication, loader: str
) -> str:
    return (
        f"{publication.release_version}+{loader}-"
        f"{publication.build_minecraft_version}"
    )


def validate_modrinth_version(
    raw_version: object,
    publication: Publication,
    artifact: Artifact,
) -> tuple[str, ...]:
    version = require_object(
        raw_version, f"Modrinth version {artifact.modrinth_version_id}"
    )
    if version.get("id") != artifact.modrinth_version_id:
        raise PlatformSyncError(
            f"Modrinth returned the wrong version for {artifact.loader}"
        )
    if version.get("project_id") != publication.modrinth_project_id:
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} belongs to "
            "a different project"
        )
    expected_version = expected_modrinth_version_number(
        publication, artifact.loader
    )
    if version.get("version_number") != expected_version:
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} has unexpected "
            "version coordinates"
        )

    loaders = version.get("loaders")
    if (
        not isinstance(loaders, list)
        or len(loaders) != 1
        or loaders[0] != artifact.loader
    ):
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} has unexpected loaders"
        )

    files = version.get("files")
    if not isinstance(files, list):
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} has invalid files"
        )
    matching_files = [
        require_object(file, "Modrinth version file")
        for file in files
        if isinstance(file, dict) and file.get("filename") == artifact.filename
    ]
    if len(matching_files) != 1:
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} does not contain "
            f"exactly one {artifact.filename}"
        )
    hashes = require_object(
        matching_files[0].get("hashes"),
        f"Modrinth hashes for {artifact.filename}",
    )
    sha512 = hashes.get("sha512")
    if not isinstance(sha512, str) or sha512.lower() != artifact.modrinth_sha512:
        raise PlatformSyncError(
            f"Modrinth sha512 mismatch for {artifact.filename}"
        )
    sha256 = hashes.get("sha256")
    if (
        sha256 is not None
        and (not isinstance(sha256, str) or sha256.lower() != artifact.sha256)
    ):
        raise PlatformSyncError(
            f"Modrinth sha256 mismatch for {artifact.filename}"
        )

    game_versions = version.get("game_versions")
    if (
        not isinstance(game_versions, list)
        or not game_versions
        or any(
            not isinstance(game_version, str) or not game_version
            for game_version in game_versions
        )
        or len(set(game_versions)) != len(game_versions)
    ):
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} has invalid "
            "game_versions"
        )
    if publication.build_minecraft_version not in game_versions:
        raise PlatformSyncError(
            f"Modrinth version {artifact.modrinth_version_id} does not advertise "
            "its build Minecraft version"
        )
    return tuple(game_versions)


def merge_game_versions(
    current: tuple[str, ...],
    desired: tuple[str, ...],
) -> tuple[str, ...]:
    merged = list(current)
    for version in desired:
        if version not in merged:
            merged.append(version)
    return tuple(merged)


def sync_modrinth(
    release: PublishedRelease,
    token: str,
    client: JsonHttpClient,
    *,
    base_url: str = MODRINTH_BASE_URL,
) -> SyncSummary:
    if not token:
        raise PlatformSyncError("MODRINTH_TOKEN is not configured")

    publication = release.publication
    headers = {"Authorization": token}
    plans: list[ModrinthPlan] = []

    # Validate every immutable coordinate before allowing any mutation.
    for loader in EXPECTED_LOADERS:
        artifact = publication.artifacts[loader]
        raw_version = client.request_json(
            "GET",
            modrinth_version_url(base_url, artifact.modrinth_version_id),
            headers=headers,
        )
        current = validate_modrinth_version(
            raw_version, publication, artifact
        )
        plans.append(
            ModrinthPlan(
                artifact=artifact,
                current_game_versions=current,
                merged_game_versions=merge_game_versions(
                    current, release.verified_minecraft_versions
                ),
            )
        )

    updated = 0
    for plan in plans:
        if not plan.needs_update:
            continue
        client.request_json(
            "PATCH",
            modrinth_version_url(
                base_url, plan.artifact.modrinth_version_id
            ),
            headers={
                **headers,
                "Content-Type": "application/json",
            },
            body=json_request_body(
                {"game_versions": list(plan.merged_game_versions)}
            ),
        )
        updated += 1

    # Verify the final marketplace state, including the idempotent no-op path.
    desired = set(release.verified_minecraft_versions)
    for plan in plans:
        raw_version = client.request_json(
            "GET",
            modrinth_version_url(
                base_url, plan.artifact.modrinth_version_id
            ),
            headers=headers,
        )
        final_versions = set(
            validate_modrinth_version(
                raw_version, publication, plan.artifact
            )
        )
        missing = desired - final_versions
        if missing:
            raise PlatformSyncError(
                f"Modrinth version {plan.artifact.modrinth_version_id} "
                "did not retain all verified Minecraft versions"
            )

    return SyncSummary("modrinth", len(plans), updated)


def extract_curseforge_game_versions(raw_value: object) -> set[str]:
    values: object = raw_value
    if isinstance(raw_value, dict):
        values = raw_value.get("data")
    if not isinstance(values, list):
        raise PlatformSyncError(
            "CurseForge game-version response must be an array"
        )

    names: set[str] = set()
    for index, raw_version in enumerate(values):
        version = require_object(
            raw_version, f"CurseForge game version {index}"
        )
        name = require_string(
            version.get("name"), f"CurseForge game version {index} name"
        )
        names.add(name)
    return names


def make_multipart_boundary() -> str:
    return "----DisableComplianceNotification" + secrets.token_hex(16)


def encode_multipart_metadata(
    metadata: dict[str, object], boundary: str
) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,70}", boundary):
        raise PlatformSyncError("invalid multipart boundary")
    serialized = json.dumps(
        metadata, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return b"".join(
        (
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: form-data; name="metadata"\r\n',
            b"Content-Type: application/json\r\n",
            b"\r\n",
            serialized,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        )
    )


def curseforge_update_url(base_url: str, project_id: str) -> str:
    return join_url(
        base_url,
        f"api/projects/{quote(project_id, safe='')}/update-file",
    )


def sync_curseforge(
    release: PublishedRelease,
    token: str,
    client: JsonHttpClient,
    *,
    base_url: str = CURSEFORGE_BASE_URL,
    boundary_factory: Callable[[], str] = make_multipart_boundary,
) -> SyncSummary:
    if not token:
        raise PlatformSyncError("CURSEFORGE_TOKEN is not configured")

    publication = release.publication
    headers = {"X-Api-Token": token}
    available_versions = extract_curseforge_game_versions(
        client.request_json(
            "GET",
            join_url(base_url, "api/game/versions"),
            headers=headers,
        )
    )
    required_names = set(release.verified_minecraft_versions)
    required_names.update(
        artifact.curseforge_loader
        for artifact in publication.artifacts.values()
    )
    missing_names = required_names - available_versions
    if missing_names:
        raise PlatformSyncError(
            "CurseForge does not recognize required game version names: "
            + ", ".join(sorted(missing_names))
        )

    update_url = curseforge_update_url(
        base_url, publication.curseforge_project_id
    )
    updated = 0
    for loader in EXPECTED_LOADERS:
        artifact = publication.artifacts[loader]
        metadata: dict[str, object] = {
            "fileID": artifact.curseforge_file_id,
            "gameVersionNames": [
                artifact.curseforge_loader,
                *release.verified_minecraft_versions,
            ],
        }
        boundary = boundary_factory()
        response = client.request_json(
            "POST",
            update_url,
            headers={
                **headers,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            body=encode_multipart_metadata(metadata, boundary),
        )
        response_data = require_object(
            response,
            f"CurseForge update response for {artifact.filename}",
        )
        returned_id = parse_positive_integer(
            response_data.get("id"),
            f"CurseForge update response ID for {artifact.filename}",
        )
        if returned_id != artifact.curseforge_file_id:
            raise PlatformSyncError(
                f"CurseForge updated the wrong file for {artifact.loader}"
            )
        updated += 1

    return SyncSummary("curseforge", len(EXPECTED_LOADERS), updated)


def parse_args(argv: list[str]) -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description=(
            "Add runtime-verified Minecraft versions to an existing "
            "Modrinth or CurseForge release."
        )
    )
    parser.add_argument(
        "--platform",
        choices=("modrinth", "curseforge"),
        required=True,
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=project_root / "data/published-release.json",
    )
    parser.add_argument(
        "--modrinth-base-url",
        default=MODRINTH_BASE_URL,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--curseforge-base-url",
        default=CURSEFORGE_BASE_URL,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--timeout", type=float, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        release = load_release_data(args.data)
        client = JsonHttpClient(timeout=args.timeout)
        if args.platform == "modrinth":
            summary = sync_modrinth(
                release,
                os.environ.get("MODRINTH_TOKEN", ""),
                client,
                base_url=args.modrinth_base_url,
            )
        else:
            summary = sync_curseforge(
                release,
                os.environ.get("CURSEFORGE_TOKEN", ""),
                client,
                base_url=args.curseforge_base_url,
            )
    except PlatformSyncError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"{summary.platform}: checked {summary.checked} immutable releases; "
        f"updated {summary.updated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
