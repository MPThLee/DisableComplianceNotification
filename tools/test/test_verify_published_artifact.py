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


EXPECTED_PUBLICATION = {
    "fabric": {
        "modrinth": "DGk6zAdg",
        "curseforge": 8441666,
        "sha256": "6af75d89c831c3fdd12927bcc592271845c2f1dc8e84daf13770866a3a1d1959",
        "sha512": "8025f51771d3a2fda2005f6d5c166bf0564a2d5283ae9e447412fd39f303168c0038a09acfc9a07fab7e907df9c50c0bd62aa77dec39dc32cbda20580a9cb51a",
    },
    "neoforge": {
        "modrinth": "QskurR3v",
        "curseforge": 8441667,
        "sha256": "d81e67efa7cac1858b1451660cd10513990a4c078d6cf0ba3fc8f6f020483501",
        "sha512": "77066dea89f1dbbf095968b344147634c62288c27bc0265974241d159d4f6fc5e68558504c2be6fd78e494c8887b72bd680f162df5b08a778a26abf9abedbd21",
    },
    "forge": {
        "modrinth": "XCIQCPjS",
        "curseforge": 8441668,
        "sha256": "f81737ce8cf5581f872ca2c265bbccba55fdbfe2503662b1a98b022964904064",
        "sha512": "39ac2503b94b2905e12ed73905f845dee06b9febffa469514f35d14bc4f91aaabae517867080327a501392c64fb61092f64254594d695015113e03c0793a0328",
    },
}


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

    def test_repository_data_binds_exact_v160_publications(self):
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(1, data["schema_version"])
        self.assertEqual(
            "v1.6.0",
            data["publication"]["id"],
        )
        self.assertEqual("1.6.0", data["publication"]["release_version"])
        self.assertEqual("v1.6.0", data["publication"]["tag"])
        self.assertEqual(
            "0484b2f7249e30dd834d30f11bd582ccfc82b83f",
            data["publication"]["source_commit"],
        )
        self.assertEqual(
            "26.2", data["publication"]["build_minecraft_version"]
        )
        self.assertEqual(
            "vAYtksKy", data["publication"]["modrinth_project_id"]
        )
        self.assertEqual(644324, data["publication"]["curseforge_project_id"])

        for loader, expected in EXPECTED_PUBLICATION.items():
            with self.subTest(loader=loader):
                artifact = data["publication"]["artifacts"][loader]
                self.assertEqual(
                    expected["modrinth"], artifact["modrinth_version_id"]
                )
                self.assertEqual(
                    expected["curseforge"], artifact["curseforge_file_id"]
                )
                self.assertEqual(expected["sha256"], artifact["sha256"])
                self.assertEqual(expected["sha512"], artifact["modrinth_sha512"])
                self.assertEqual(
                    (
                        "https://github.com/MPThLee/DisableComplianceNotification/"
                        "releases/download/v1.6.0/"
                        f"disable_compliance_notification-v1.6.0+{loader}-26.2.jar"
                    ),
                    artifact["github_url"],
                )


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

        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
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
