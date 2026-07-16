#!/usr/bin/env python3

import copy
import io
import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/create-published-release.py"
SPEC = importlib.util.spec_from_file_location("create_published_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
creator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = creator
SPEC.loader.exec_module(creator)

SYNC_MODULE_PATH = PROJECT_ROOT / "tools/sync-platform-compatibility.py"
SYNC_SPEC = importlib.util.spec_from_file_location(
    "create_release_sync_compatibility", SYNC_MODULE_PATH
)
assert SYNC_SPEC is not None and SYNC_SPEC.loader is not None
sync = importlib.util.module_from_spec(SYNC_SPEC)
sys.modules[SYNC_SPEC.name] = sync
SYNC_SPEC.loader.exec_module(sync)

MARKETPLACE_MODULE_PATH = PROJECT_ROOT / "tools/record-marketplace-sync.py"
MARKETPLACE_SPEC = importlib.util.spec_from_file_location(
    "create_release_marketplace_sync", MARKETPLACE_MODULE_PATH
)
assert MARKETPLACE_SPEC is not None and MARKETPLACE_SPEC.loader is not None
marketplace = importlib.util.module_from_spec(MARKETPLACE_SPEC)
sys.modules[MARKETPLACE_SPEC.name] = marketplace
MARKETPLACE_SPEC.loader.exec_module(marketplace)


SOURCE_COMMIT = "1" * 40
OLD_SOURCE_COMMIT = "0" * 40
HASHES = {
    "fabric": ("a" * 64, "1" * 128),
    "neoforge": ("b" * 64, "2" * 128),
    "forge": ("c" * 64, "3" * 128),
}
OLD_HASHES = {
    "fabric": ("d" * 64, "4" * 128),
    "neoforge": ("e" * 64, "5" * 128),
    "forge": ("f" * 64, "6" * 128),
}
MODRINTH_IDS = {
    "fabric": "newFab01",
    "neoforge": "newNeo01",
    "forge": "newFor01",
}
OLD_MODRINTH_IDS = {
    "fabric": "oldFab01",
    "neoforge": "oldNeo01",
    "forge": "oldFor01",
}
CURSEFORGE_IDS = {
    "fabric": 9000001,
    "neoforge": 9000002,
    "forge": 9000003,
}
OLD_CURSEFORGE_IDS = {
    "fabric": 8000001,
    "neoforge": 8000002,
    "forge": 8000003,
}


def properties(
    mod_version: str = "1.6.1",
    minecraft_version: str = "26.2",
) -> dict[str, str]:
    return {
        "archives_base_name": "disable_compliance_notification",
        "mod_version": mod_version,
        "minecraft_version": minecraft_version,
    }


def fragment(
    loader: str,
    *,
    mod_version: str = "1.6.1",
    minecraft_version: str = "26.2",
) -> dict[str, object]:
    filename = (
        "disable_compliance_notification-"
        f"v{mod_version}+{loader}-{minecraft_version}.jar"
    )
    return {
        "loader": loader,
        "filename": filename,
        "sha256": HASHES[loader][0],
        "sha512": HASHES[loader][1],
        "github_url": (
            "https://github.com/MPThLee/DisableComplianceNotification/"
            f"releases/download/v{mod_version}/{filename}"
        ),
        "modrinth_version_id": MODRINTH_IDS[loader],
        "curseforge_file_id": CURSEFORGE_IDS[loader],
    }


def gate_result(loader: str, minecraft_version: str = "26.2") -> dict[str, object]:
    return {
        "schema_version": 1,
        "loader": loader,
        "minecraft_version": minecraft_version,
        "minimum_in_world_seconds": 120,
        "requested_in_world_seconds": 150,
        "observed_in_world_seconds": 150.5,
        "filtered_notifications": [
            "compliance.playtime.greaterThan24Hours",
            "compliance.playtime.hours",
        ],
        "periodic_toast_absent": True,
        "passed": True,
    }


def parsed_inputs() -> tuple[
    dict[str, dict[str, object]], dict[str, dict[str, object]]
]:
    fragments = {
        loader: {
            "filename": fragment(loader)["filename"],
            "github_url": fragment(loader)["github_url"],
            "sha256": fragment(loader)["sha256"],
            "modrinth_version_id": fragment(loader)["modrinth_version_id"],
            "modrinth_sha512": fragment(loader)["sha512"],
            "curseforge_file_id": fragment(loader)["curseforge_file_id"],
            "curseforge_loader": creator.CURSEFORGE_LOADERS[loader],
        }
        for loader in creator.LOADERS
    }
    gates = {loader: gate_result(loader) for loader in creator.LOADERS}
    return fragments, gates


def old_artifact(loader: str) -> dict[str, object]:
    filename = (
        "disable_compliance_notification-"
        f"v1.6.0+{loader}-26.2.jar"
    )
    return {
        "filename": filename,
        "github_url": (
            "https://github.com/MPThLee/DisableComplianceNotification/"
            f"releases/download/v1.6.0/{filename}"
        ),
        "sha256": OLD_HASHES[loader][0],
        "modrinth_version_id": OLD_MODRINTH_IDS[loader],
        "modrinth_sha512": OLD_HASHES[loader][1],
        "curseforge_file_id": OLD_CURSEFORGE_IDS[loader],
        "curseforge_loader": creator.CURSEFORGE_LOADERS[loader],
    }


def old_runtime_record(minecraft_version: str) -> dict[str, object]:
    return {
        "minecraft_version": minecraft_version,
        "verified_on": "2026-07-16",
        "required_in_world_seconds": 120,
        "filtered_notifications": sorted(creator.EXPECTED_NOTIFICATIONS),
        "loaders": {
            loader: {
                "observed_in_world_seconds": 150.5,
                "periodic_toast_absent": True,
                "passed": True,
                "artifact_sha256": OLD_HASHES[loader][0],
            }
            for loader in creator.LOADERS
        },
    }


def old_publication() -> dict[str, object]:
    return {
        "schema_version": 1,
        "publication": {
            "id": "v1.6.0",
            "release_version": "1.6.0",
            "build_minecraft_version": "26.2",
            "source_commit": OLD_SOURCE_COMMIT,
            "tag": "v1.6.0",
            "github_repository": creator.GITHUB_REPOSITORY,
            "modrinth_project_id": creator.MODRINTH_PROJECT_ID,
            "curseforge_project_id": creator.CURSEFORGE_PROJECT_ID,
            "artifacts": {
                loader: old_artifact(loader) for loader in creator.LOADERS
            },
        },
        "runtime_verification": [
            old_runtime_record("26.2"),
            old_runtime_record("26.2.1"),
            old_runtime_record("26.3"),
        ],
        "desired_game_versions": ["26.2", "26.2.1", "26.3"],
        "marketplace_sync": {
            "publication": "v1.6.0",
            "game_versions": ["26.2", "26.2.1", "26.3"],
            "synced_on": "2026-07-16",
        },
    }


class CreatePublishedReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_config(
        self,
        mod_version: str = "1.6.1",
        minecraft_version: str = "26.2",
    ) -> Path:
        path = self.root / "config.properties"
        path.write_text(
            "\n".join(
                [
                    "archives_base_name=disable_compliance_notification",
                    f"mod_version={mod_version}",
                    f"minecraft_version={minecraft_version}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return path

    def write_inputs(
        self,
        *,
        mod_version: str = "1.6.1",
        minecraft_version: str = "26.2",
    ) -> tuple[list[Path], list[Path]]:
        fragment_paths = []
        gate_paths = []
        for loader in creator.LOADERS:
            fragment_path = self.root / f"{loader}-publication.json"
            fragment_path.write_text(
                json.dumps(
                    fragment(
                        loader,
                        mod_version=mod_version,
                        minecraft_version=minecraft_version,
                    )
                ),
                encoding="utf-8",
            )
            fragment_paths.append(fragment_path)
            gate_path = self.root / f"{loader}-gate.json"
            gate_path.write_text(
                json.dumps(gate_result(loader, minecraft_version)),
                encoding="utf-8",
            )
            gate_paths.append(gate_path)
        return fragment_paths, gate_paths

    def command(
        self,
        config: Path,
        fragments: list[Path],
        gates: list[Path],
        output: Path,
        *,
        tag: str = "v1.6.1",
        source_commit: str = SOURCE_COMMIT,
        published_on: str = "2026-08-01",
        previous_data: Path | None = None,
    ) -> list[str]:
        arguments = [
            "--config",
            str(config),
            "--tag",
            tag,
            "--source-commit",
            source_commit,
            "--output",
            str(output),
            "--published-on",
            published_on,
        ]
        if previous_data is not None:
            arguments.extend(["--previous-data", str(previous_data)])
        for path in fragments:
            arguments.extend(["--publication-fragment", str(path)])
        for path in gates:
            arguments.extend(["--gate-result", str(path)])
        return arguments

    def test_builds_new_flattened_publication_schema(self):
        fragments, gates = parsed_inputs()
        document = creator.create_document(
            properties=properties(),
            tag="v1.6.1",
            source_commit=SOURCE_COMMIT,
            fragments=fragments,
            gate_results=gates,
            verified_on="2026-08-01",
        )

        publication = document["publication"]
        self.assertEqual("v1.6.1", publication["id"])
        self.assertEqual("1.6.1", publication["release_version"])
        self.assertEqual("26.2", publication["build_minecraft_version"])
        self.assertEqual(SOURCE_COMMIT, publication["source_commit"])
        self.assertEqual(
            set(creator.LOADERS), set(publication["artifacts"])
        )
        self.assertEqual(
            HASHES["fabric"][1],
            publication["artifacts"]["fabric"]["modrinth_sha512"],
        )
        self.assertEqual(
            "NeoForge",
            publication["artifacts"]["neoforge"]["curseforge_loader"],
        )
        self.assertEqual(["26.2"], document["desired_game_versions"])
        self.assertNotIn("marketplace_sync", document)
        self.assertEqual(1, len(document["runtime_verification"]))
        runtime = document["runtime_verification"][0]
        self.assertEqual("26.2", runtime["minecraft_version"])
        self.assertEqual(
            HASHES["forge"][0],
            runtime["loaders"]["forge"]["artifact_sha256"],
        )
        parsed = sync.parse_release_data(document)
        self.assertEqual("v1.6.1", parsed.publication.publication_id)
        self.assertEqual(("26.2",), parsed.verified_minecraft_versions)
        current, message = marketplace.check_marketplace_sync(document)
        self.assertFalse(current)
        self.assertIn("no sync record", message)

    def test_262_2621_263_history_rolls_to_v161_base_only(self):
        config = self.write_config()
        fragment_paths, gate_paths = self.write_inputs()
        output = self.root / "published-release.json"
        previous = self.root / "previous-published-release.json"
        previous.write_text(json.dumps(old_publication()), encoding="utf-8")

        self.assertEqual(
            0,
            creator.main(
                self.command(
                    config,
                    fragment_paths,
                    gate_paths,
                    output,
                    previous_data=previous,
                )
            ),
        )

        updated = json.loads(output.read_text(encoding="utf-8"))
        publication = updated["publication"]
        self.assertEqual("v1.6.1", publication["id"])
        self.assertEqual("v1.6.1", publication["tag"])
        self.assertEqual("1.6.1", publication["release_version"])
        self.assertEqual(SOURCE_COMMIT, publication["source_commit"])
        self.assertEqual("26.2", publication["build_minecraft_version"])
        self.assertEqual(["26.2"], updated["desired_game_versions"])
        self.assertNotIn("marketplace_sync", updated)
        self.assertEqual(
            ["26.2"],
            [
                record["minecraft_version"]
                for record in updated["runtime_verification"]
            ],
        )
        old_modrinth_ids = set(OLD_MODRINTH_IDS.values())
        old_curseforge_ids = set(OLD_CURSEFORGE_IDS.values())
        for loader in creator.LOADERS:
            artifact = publication["artifacts"][loader]
            expected = fragment(loader)
            self.assertEqual(expected["filename"], artifact["filename"])
            self.assertEqual(expected["github_url"], artifact["github_url"])
            self.assertEqual(HASHES[loader][0], artifact["sha256"])
            self.assertEqual(HASHES[loader][1], artifact["modrinth_sha512"])
            self.assertEqual(
                MODRINTH_IDS[loader], artifact["modrinth_version_id"]
            )
            self.assertEqual(
                CURSEFORGE_IDS[loader], artifact["curseforge_file_id"]
            )
            self.assertNotIn(
                artifact["modrinth_version_id"], old_modrinth_ids
            )
            self.assertNotIn(
                artifact["curseforge_file_id"], old_curseforge_ids
            )

    def test_new_publication_rejects_reused_marketplace_ids(self):
        fragments, gates = parsed_inputs()
        previous = old_publication()
        cases = {
            "Modrinth": ("fabric", "modrinth_version_id", OLD_MODRINTH_IDS["forge"]),
            "CurseForge": ("neoforge", "curseforge_file_id", OLD_CURSEFORGE_IDS["fabric"]),
        }
        for label, (loader, field, value) in cases.items():
            with self.subTest(platform=label):
                changed = copy.deepcopy(fragments)
                changed[loader][field] = value
                document = creator.create_document(
                    properties=properties(),
                    tag="v1.6.1",
                    source_commit=SOURCE_COMMIT,
                    fragments=changed,
                    gate_results=gates,
                    verified_on="2026-08-01",
                )
                with self.assertRaisesRegex(
                    creator.PublicationCreationError, f"prior {label}"
                ):
                    creator.validate_against_previous(document, previous)

    def test_same_publication_rerun_requires_identical_coordinates_and_hashes(self):
        fragments, gates = parsed_inputs()
        document = creator.create_document(
            properties=properties(),
            tag="v1.6.1",
            source_commit=SOURCE_COMMIT,
            fragments=fragments,
            gate_results=gates,
            verified_on="2026-08-01",
        )
        creator.validate_against_previous(document, copy.deepcopy(document))

        cases = {
            "publication source": (
                ("publication", "source_commit"),
                OLD_SOURCE_COMMIT,
            ),
            "artifact hash": (
                ("publication", "artifacts", "fabric", "sha256"),
                "9" * 64,
            ),
            "marketplace coordinate": (
                (
                    "publication",
                    "artifacts",
                    "forge",
                    "modrinth_version_id",
                ),
                "driftedId",
            ),
        }
        for label, (path, value) in cases.items():
            with self.subTest(case=label):
                previous = copy.deepcopy(document)
                target = previous
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaisesRegex(
                    creator.PublicationCreationError, "rerun.*changed"
                ):
                    creator.validate_against_previous(document, previous)

    def test_fragment_loader_coverage_is_exact(self):
        paths, _ = self.write_inputs()
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "cover exactly every loader"
        ):
            creator.load_fragments(
                paths[:-1],
                archive_base_name="disable_compliance_notification",
                mod_version="1.6.1",
                minecraft_version="26.2",
                tag="v1.6.1",
            )

        duplicate = self.root / "duplicate.json"
        duplicate.write_text(paths[0].read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "duplicate publication fragment"
        ):
            creator.load_fragments(
                [*paths, duplicate],
                archive_base_name="disable_compliance_notification",
                mod_version="1.6.1",
                minecraft_version="26.2",
                tag="v1.6.1",
            )

        duplicate_field = self.root / "duplicate-field.json"
        duplicate_field.write_text(
            '{"loader":"fabric","loader":"forge"}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "duplicate JSON field"
        ):
            creator.load_fragments(
                [duplicate_field],
                archive_base_name="disable_compliance_notification",
                mod_version="1.6.1",
                minecraft_version="26.2",
                tag="v1.6.1",
            )

    def test_rejects_fragment_coordinate_and_identity_drift(self):
        base = fragment("fabric")
        cases = {
            "filename": ("filename", "wrong.jar"),
            "github_url": (
                "github_url",
                str(base["github_url"]).replace("/v1.6.1/", "/v1.6.0/"),
            ),
            "sha256": ("sha256", "a" * 63),
            "sha512": ("sha512", "1" * 127),
            "modrinth": ("modrinth_version_id", "unsafe/id"),
            "curseforge": ("curseforge_file_id", "9000001"),
        }
        for label, (field, value) in cases.items():
            with self.subTest(case=label):
                changed = copy.deepcopy(base)
                changed[field] = value
                path = self.root / f"{label}.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(creator.PublicationCreationError):
                    creator.load_fragments(
                        [path],
                        archive_base_name="disable_compliance_notification",
                        mod_version="1.6.1",
                        minecraft_version="26.2",
                        tag="v1.6.1",
                    )

    def test_gate_loader_coverage_is_exact(self):
        _, paths = self.write_inputs()
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "cover exactly every loader"
        ):
            creator.load_gate_results(paths[:-1], minecraft_version="26.2")

        duplicate = self.root / "duplicate-gate.json"
        duplicate.write_text(paths[0].read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "duplicate gate result"
        ):
            creator.load_gate_results(
                [*paths, duplicate], minecraft_version="26.2"
            )

    def test_rejects_incomplete_or_wrong_gate_evidence(self):
        base = gate_result("fabric")
        cases = {
            "version": ("minecraft_version", "26.3"),
            "failed": ("passed", False),
            "toast": ("periodic_toast_absent", False),
            "minimum": ("minimum_in_world_seconds", 119),
            "requested": ("requested_in_world_seconds", 119),
            "observed": ("observed_in_world_seconds", 119.9),
            "non_finite": ("observed_in_world_seconds", float("nan")),
            "notifications": (
                "filtered_notifications",
                ["compliance.playtime.hours"],
            ),
            "malformed_notifications": (
                "filtered_notifications",
                [{"not": "a notification"}, "compliance.playtime.hours"],
            ),
        }
        for label, (field, value) in cases.items():
            with self.subTest(case=label):
                changed = copy.deepcopy(base)
                changed[field] = value
                path = self.root / f"{label}-gate.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(creator.PublicationCreationError):
                    creator.load_gate_results([path], minecraft_version="26.2")

    def test_config_tag_and_source_commit_are_strict(self):
        invalid_configs = {
            "duplicate": (
                "archives_base_name=disable_compliance_notification\n"
                "mod_version=1.6.1\nmod_version=1.6.2\n"
                "minecraft_version=26.2\n"
            ),
            "missing": (
                "archives_base_name=disable_compliance_notification\n"
                "mod_version=1.6.1\n"
            ),
            "unsafe": (
                "archives_base_name=../../escape\n"
                "mod_version=1.6.1\nminecraft_version=26.2\n"
            ),
            "wrong_project": (
                "archives_base_name=another_mod\n"
                "mod_version=1.6.1\nminecraft_version=26.2\n"
            ),
        }
        for label, content in invalid_configs.items():
            with self.subTest(case=label):
                path = self.root / f"{label}.properties"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(creator.PublicationCreationError):
                    creator.read_config(path)

        fragments, gates = parsed_inputs()
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "does not match"
        ):
            creator.create_document(
                properties=properties(),
                tag="v1.6.0",
                source_commit=SOURCE_COMMIT,
                fragments=fragments,
                gate_results=gates,
                verified_on="2026-08-01",
            )
        with self.assertRaisesRegex(
            creator.PublicationCreationError, "source commit"
        ):
            creator.create_document(
                properties=properties(),
                tag="v1.6.1",
                source_commit="short",
                fragments=fragments,
                gate_results=gates,
                verified_on="2026-08-01",
            )

    def test_cli_failure_does_not_replace_existing_history(self):
        config = self.write_config()
        fragment_paths, gate_paths = self.write_inputs()
        output = self.root / "published-release.json"
        previous = old_publication()
        output.write_text(json.dumps(previous), encoding="utf-8")
        bad_gate = json.loads(gate_paths[0].read_text(encoding="utf-8"))
        bad_gate["passed"] = False
        gate_paths[0].write_text(json.dumps(bad_gate), encoding="utf-8")

        with redirect_stderr(io.StringIO()):
            self.assertEqual(
                1,
                creator.main(
                    self.command(
                        config,
                        fragment_paths,
                        gate_paths,
                        output,
                        previous_data=output,
                    )
                ),
            )
        self.assertEqual(
            previous, json.loads(output.read_text(encoding="utf-8"))
        )


if __name__ == "__main__":
    unittest.main()
