#!/usr/bin/env python3

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/verify-published-artifact.py"
DATA_PATH = PROJECT_ROOT / "data/published-release.json"
SPEC = importlib.util.spec_from_file_location("verify_published_artifact", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)


def fabric_metadata(version: str, minecraft: str, mod_id: str = "disable_compliance_notification") -> bytes:
    return json.dumps(
        {
            "schemaVersion": 1,
            "id": mod_id,
            "version": version,
            "name": "Disable Compliance Notification",
            "contact": {
                "homepage": "https://github.com/MPThLee/DisableComplianceNotification",
                "sources": "https://github.com/MPThLee/DisableComplianceNotification",
            },
            "environment": "client",
            "depends": {
                "fabricloader": ">=0.19.3",
                "minecraft": f">={minecraft}",
                "java": ">=25",
            },
        },
        sort_keys=True,
    ).encode()


def forge_metadata(loader: str, version: str, minecraft: str) -> bytes:
    loader_id = "neoforge" if loader == "neoforge" else "forge"
    loader_fields = (
        'type = "required"\n' if loader == "neoforge" else "mandatory = true\n"
    )
    return f'''modLoader = "javafml"
loaderVersion = "[1,)"
issueTrackerURL = "https://github.com/MPThLee/DisableComplianceNotification/issues"
license = "MIT"

[[mods]]
modId = "disable_compliance_notification"
version = "{version}"
displayName = "Disable Compliance Notification"

[[dependencies.disable_compliance_notification]]
modId = "{loader_id}"
{loader_fields}versionRange = "[1,)"
side = "CLIENT"

[[dependencies.disable_compliance_notification]]
modId = "minecraft"
{loader_fields}versionRange = "[{minecraft},)"
side = "CLIENT"
'''.encode()


def archive_entries(loader: str, version: str, minecraft: str) -> dict[str, bytes]:
    metadata_path = verifier.METADATA_PATHS[loader]
    metadata = (
        fabric_metadata(version, minecraft)
        if loader == "fabric"
        else forge_metadata(loader, version, minecraft)
    )
    entries = {
        "META-INF/MANIFEST.MF": (
            f"Manifest-Version: 1.0\r\nImplementation-Version: {version}\r\n\r\n"
        ).encode(),
        metadata_path: metadata,
        "dev/mpthlee/minecraft/disable_compliance_notification/Production.class": (
            b"\xca\xfe\xba\xbeproduction-bytecode"
        ),
        "disable_compliance_notification.mixins.json": b'{"required":true}',
    }
    if loader != "fabric":
        entries["pack.mcmeta"] = (
            b'{"pack":{"description":"Disable Compliance Notification"}}'
        )
    return entries


def write_jar(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def synthetic_publication() -> dict[str, object]:
    artifacts = {}
    for index, loader in enumerate(verifier.LOADERS, start=1):
        filename = (
            "disable_compliance_notification-"
            f"v1.6.0+{loader}-26.2.jar"
        )
        artifacts[loader] = {
            "filename": filename,
            "github_url": (
                "https://github.com/MPThLee/DisableComplianceNotification/"
                f"releases/download/v1.6.0/{filename}"
            ),
            "sha256": str(index) * 64,
            "modrinth_version_id": f"synthetic-{loader}",
            "modrinth_sha512": str(index) * 128,
            "curseforge_file_id": 9000000 + index,
            "curseforge_loader": verifier.CURSEFORGE_LOADERS[loader],
        }
    return {
        "schema_version": 1,
        "publication": {
            "id": "v1.6.0",
            "release_version": "1.6.0",
            "build_minecraft_version": "26.2",
            "source_commit": "1" * 40,
            "tag": "v1.6.0",
            "github_repository": "MPThLee/DisableComplianceNotification",
            "modrinth_project_id": "vAYtksKy",
            "curseforge_project_id": 644324,
            "artifacts": artifacts,
        },
    }


class PublishedReleaseDataTest(unittest.TestCase):
    def test_workflow_target_option_is_supported(self):
        arguments = verifier.parse_args(
            [
                "--loader",
                "fabric",
                "--target-minecraft-version",
                "26.3",
                "--candidate-jar",
                "candidate.jar",
            ]
        )
        self.assertEqual("26.3", arguments.target)

    def test_repository_data_has_self_consistent_immutable_coordinates(self):
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(1, data["schema_version"])
        publication = data["publication"]
        release_version = publication["release_version"]
        build_version = publication["build_minecraft_version"]
        tag = f"v{release_version}"
        self.assertEqual(tag, publication["id"])
        self.assertEqual(tag, publication["tag"])
        self.assertRegex(publication["source_commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(release_version, r"^\d+(?:\.\d+)*$")
        self.assertRegex(build_version, r"^\d+(?:\.\d+)*$")
        self.assertEqual(
            "vAYtksKy", publication["modrinth_project_id"]
        )
        self.assertEqual(644324, publication["curseforge_project_id"])
        self.assertEqual(set(verifier.LOADERS), set(publication["artifacts"]))

        modrinth_ids = set()
        curseforge_ids = set()
        filenames = set()
        for loader in verifier.LOADERS:
            with self.subTest(loader=loader):
                artifact = publication["artifacts"][loader]
                filename = (
                    "disable_compliance_notification-"
                    f"v{release_version}+{loader}-{build_version}.jar"
                )
                self.assertEqual(filename, artifact["filename"])
                self.assertRegex(
                    artifact["modrinth_version_id"], r"^[A-Za-z0-9_-]+$"
                )
                self.assertIsInstance(artifact["curseforge_file_id"], int)
                self.assertGreater(artifact["curseforge_file_id"], 0)
                self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
                self.assertRegex(
                    artifact["modrinth_sha512"], r"^[0-9a-f]{128}$"
                )
                self.assertEqual(
                    (
                        "https://github.com/MPThLee/DisableComplianceNotification/"
                        f"releases/download/{tag}/{filename}"
                    ),
                    artifact["github_url"],
                )
                filenames.add(filename)
                modrinth_ids.add(artifact["modrinth_version_id"])
                curseforge_ids.add(artifact["curseforge_file_id"])

        self.assertEqual(len(verifier.LOADERS), len(filenames))
        self.assertEqual(len(verifier.LOADERS), len(modrinth_ids))
        self.assertEqual(len(verifier.LOADERS), len(curseforge_ids))


class PublishedArtifactVerifierTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(
        self,
        loader: str,
        *,
        target: str = "26.3",
        published_entries: dict[str, bytes] | None = None,
        candidate_entries: dict[str, bytes] | None = None,
    ) -> tuple[Path, Path, Path, dict[str, object]]:
        published_entries = published_entries or archive_entries(loader, "1.6.0", "26.2")
        candidate_entries = candidate_entries or archive_entries(loader, "1.6.1", target)
        filename = f"disable_compliance_notification-v1.6.0+{loader}-26.2.jar"
        published = self.root / filename
        candidate = (
            self.root
            / f"disable_compliance_notification-v1.6.1+{loader}-{target}.jar"
        )
        write_jar(published, published_entries)
        write_jar(candidate, candidate_entries)

        data = synthetic_publication()
        artifact = data["publication"]["artifacts"][loader]
        artifact["sha256"] = hashlib.sha256(published.read_bytes()).hexdigest()
        artifact["modrinth_sha512"] = hashlib.sha512(
            published.read_bytes()
        ).hexdigest()
        data_path = self.root / f"{loader}-published-release.json"
        data_path.write_text(json.dumps(data), encoding="utf-8")
        return published, candidate, data_path, data

    def test_all_loaders_accept_only_allowlisted_metadata_differences(self):
        for loader in verifier.LOADERS:
            with self.subTest(loader=loader):
                published, candidate, data_path, data = self.prepare(loader)
                result = verifier.verify(
                    loader=loader,
                    target="26.3",
                    candidate_jar=candidate,
                    data_path=data_path,
                    published_jar=published,
                )
                self.assertIs(result["passed"], True)
                self.assertEqual(
                    "v1.6.0",
                    result["publication"],
                )
                self.assertEqual(loader, result["loader"])
                self.assertEqual("26.3", result["target_minecraft_version"])
                self.assertEqual(
                    data["publication"]["artifacts"][loader]["sha256"],
                    result["published_sha256"],
                )

    def test_downloads_the_exact_bound_asset_when_local_jar_is_omitted(self):
        published, candidate, data_path, _ = self.prepare("fabric")
        calls = []

        def fake_download(url: str, destination: Path, timeout: float) -> None:
            calls.append((url, timeout))
            destination.write_bytes(published.read_bytes())

        result = verifier.verify(
            loader="fabric",
            target="26.3",
            candidate_jar=candidate,
            data_path=data_path,
            downloader=fake_download,
        )
        self.assertIs(result["passed"], True)
        self.assertEqual(1, len(calls))
        self.assertIn("/releases/download/v1.6.0/", calls[0][0])

    def test_rejects_published_hash_drift(self):
        published, candidate, data_path, data = self.prepare("fabric")
        data["publication"]["artifacts"]["fabric"]["sha256"] = "0" * 64
        data_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(verifier.VerificationError, "SHA-256"):
            verifier.verify(
                loader="fabric",
                target="26.3",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )

    def test_rejects_executable_byte_differences(self):
        published_entries = archive_entries("forge", "1.6.0", "26.2")
        candidate_entries = archive_entries("forge", "1.6.1", "26.3")
        candidate_entries[
            "dev/mpthlee/minecraft/disable_compliance_notification/Production.class"
        ] += b"-changed"
        published, candidate, data_path, _ = self.prepare(
            "forge",
            published_entries=published_entries,
            candidate_entries=candidate_entries,
        )
        with self.assertRaisesRegex(verifier.VerificationError, "content bytes differ"):
            verifier.verify(
                loader="forge",
                target="26.3",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )

    def test_rejects_added_content_even_when_existing_bytes_match(self):
        candidate_entries = archive_entries("neoforge", "1.6.1", "26.3")
        candidate_entries["unexpected.txt"] = b"not production content"
        published, candidate, data_path, _ = self.prepare(
            "neoforge", candidate_entries=candidate_entries
        )
        with self.assertRaisesRegex(verifier.VerificationError, "entry set differs"):
            verifier.verify(
                loader="neoforge",
                target="26.3",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )

    def test_rejects_test_bootstrap_content(self):
        candidate_entries = archive_entries("fabric", "1.6.1", "26.3")
        candidate_entries[
            "dev/mpthlee/minecraft/disable_compliance_notification/test/Gate.class"
        ] = b"test"
        published, candidate, data_path, _ = self.prepare(
            "fabric", candidate_entries=candidate_entries
        )
        with self.assertRaisesRegex(verifier.VerificationError, "test bootstrap"):
            verifier.verify(
                loader="fabric",
                target="26.3",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )

    def test_rejects_manifest_identity_changes_hidden_in_allowed_metadata(self):
        candidate_entries = archive_entries("fabric", "1.6.1", "26.3")
        candidate_entries["fabric.mod.json"] = fabric_metadata(
            "1.6.1", "26.3", mod_id="different_mod"
        )
        published, candidate, data_path, _ = self.prepare(
            "fabric", candidate_entries=candidate_entries
        )
        with self.assertRaisesRegex(verifier.VerificationError, "manifest identity"):
            verifier.verify(
                loader="fabric",
                target="26.3",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )

    def test_rejects_closed_published_minecraft_ranges(self):
        published_entries = archive_entries("forge", "1.6.0", "26.2")
        published_entries["META-INF/mods.toml"] = published_entries[
            "META-INF/mods.toml"
        ].replace(b'[26.2,)', b'[26.2,26.3]')
        published, candidate, data_path, _ = self.prepare(
            "forge", published_entries=published_entries
        )
        with self.assertRaisesRegex(verifier.VerificationError, "open-ended"):
            verifier.verify(
                loader="forge",
                target="26.3",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )

    def test_rejects_targets_below_the_published_minimum(self):
        published, candidate, data_path, _ = self.prepare("fabric", target="26.1")
        with self.assertRaisesRegex(verifier.VerificationError, "does not cover"):
            verifier.verify(
                loader="fabric",
                target="26.1",
                candidate_jar=candidate,
                data_path=data_path,
                published_jar=published,
            )


if __name__ == "__main__":
    unittest.main()
