#!/usr/bin/env python3

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/record-published-compatibility.py"
SPEC = importlib.util.spec_from_file_location(
    "record_published_compatibility", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
record = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = record
SPEC.loader.exec_module(record)


HASHES = {
    "fabric": "1" * 64,
    "neoforge": "2" * 64,
    "forge": "3" * 64,
}


def published_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "publication": {
            "id": "v1.6.0",
            "release_version": "1.6.0",
            "build_minecraft_version": "26.2",
            "artifacts": {
                loader: {
                    "filename": (
                        "disable_compliance_notification-"
                        f"v1.6.0+{loader}-26.2.jar"
                    ),
                    "sha256": HASHES[loader],
                    "modrinth_version_id": f"modrinth-{loader}",
                    "curseforge_file_id": f"curseforge-{loader}",
                }
                for loader in sorted(record.EXPECTED_LOADERS)
            },
        },
        "runtime_verification": [
            {
                "minecraft_version": "26.2",
                "verified_on": "2026-07-16",
                "required_in_world_seconds": 120,
                "filtered_notifications": sorted(record.EXPECTED_NOTIFICATIONS),
                "loaders": {},
            }
        ],
    }


def gate_result(loader: str, version: str = "26.3") -> dict[str, object]:
    return {
        "schema_version": 1,
        "loader": loader,
        "minecraft_version": version,
        "minimum_in_world_seconds": 120,
        "requested_in_world_seconds": 150,
        "observed_in_world_seconds": 150.5,
        "filtered_notifications": sorted(record.EXPECTED_NOTIFICATIONS),
        "periodic_toast_absent": True,
        "passed": True,
    }


def artifact_verification(
    loader: str, version: str = "26.3"
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "publication": "v1.6.0",
        "loader": loader,
        "target_minecraft_version": version,
        "published_sha256": HASHES[loader],
        "passed": True,
        "extra_evidence": "allowed",
    }


def write_documents(
    directory: Path,
    *,
    target_version: str = "26.3",
) -> tuple[Path, list[Path], list[Path]]:
    data_path = directory / "published-release.json"
    data_path.write_text(json.dumps(published_data()), encoding="utf-8")
    result_paths = []
    artifact_paths = []
    for loader in sorted(record.EXPECTED_LOADERS):
        result_path = directory / f"{loader}-gate.json"
        result_path.write_text(
            json.dumps(gate_result(loader, target_version)), encoding="utf-8"
        )
        result_paths.append(result_path)
        artifact_path = directory / f"{loader}-artifact.json"
        artifact_path.write_text(
            json.dumps(artifact_verification(loader, target_version)),
            encoding="utf-8",
        )
        artifact_paths.append(artifact_path)
    return data_path, result_paths, artifact_paths


class RecordPublishedCompatibilityTest(unittest.TestCase):
    def test_updates_evidence_without_changing_publication_identity(self):
        data = published_data()
        publication_before = copy.deepcopy(data["publication"])
        gates = {
            loader: gate_result(loader) for loader in record.EXPECTED_LOADERS
        }
        artifacts = {
            loader: artifact_verification(loader)
            for loader in record.EXPECTED_LOADERS
        }

        updated = record.update_published_compatibility(
            data,
            gates,
            artifacts,
            target_minecraft_version="26.3",
            published_hashes=HASHES,
            verified_on="2026-08-01",
        )

        self.assertEqual(publication_before, updated["publication"])
        self.assertEqual(
            ["26.2", "26.3"],
            [item["minecraft_version"] for item in updated["runtime_verification"]],
        )
        self.assertEqual(["26.2", "26.3"], updated["desired_game_versions"])
        candidate = updated["runtime_verification"][-1]
        self.assertEqual(record.EXPECTED_LOADERS, set(candidate["loaders"]))
        self.assertEqual(
            HASHES["fabric"], candidate["loaders"]["fabric"]["artifact_sha256"]
        )
        self.assertEqual(
            150.5,
            candidate["loaders"]["forge"]["observed_in_world_seconds"],
        )

    def test_replaces_same_version_and_sorts_versions_numerically(self):
        data = published_data()
        data["runtime_verification"].extend(
            [
                {"minecraft_version": "27.1"},
                {"minecraft_version": "26.10"},
                {"minecraft_version": "26.3", "old": True},
            ]
        )
        gates = {
            loader: gate_result(loader) for loader in record.EXPECTED_LOADERS
        }
        artifacts = {
            loader: artifact_verification(loader)
            for loader in record.EXPECTED_LOADERS
        }

        updated = record.update_published_compatibility(
            data,
            gates,
            artifacts,
            target_minecraft_version="26.3",
            published_hashes=HASHES,
            verified_on="2026-08-01",
        )

        self.assertEqual(
            ["26.2", "26.3", "26.10", "27.1"],
            [item["minecraft_version"] for item in updated["runtime_verification"]],
        )
        self.assertNotIn("old", updated["runtime_verification"][1])

    def test_gate_loading_requires_exact_coverage_and_matching_target(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = []
            for loader in ("fabric", "neoforge"):
                path = directory / f"{loader}.json"
                path.write_text(json.dumps(gate_result(loader)), encoding="utf-8")
                paths.append(path)

            with self.assertRaisesRegex(
                record.PublishedCompatibilityError, "missing forge"
            ):
                record.load_gate_results(paths)

            forge_path = directory / "forge.json"
            forge_path.write_text(
                json.dumps(gate_result("forge", "27.1")), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                record.PublishedCompatibilityError, "expected 26.3"
            ):
                record.load_gate_results([*paths, forge_path])

            too_short = gate_result("forge")
            too_short["observed_in_world_seconds"] = 119.9
            forge_path.write_text(json.dumps(too_short), encoding="utf-8")
            with self.assertRaisesRegex(
                record.PublishedCompatibilityError, "shorter than two minutes"
            ):
                record.load_gate_results([*paths, forge_path])

    def test_artifact_loading_rejects_hash_and_publication_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = []
            paths_by_loader = {}
            for loader in sorted(record.EXPECTED_LOADERS):
                path = directory / f"{loader}.json"
                path.write_text(
                    json.dumps(artifact_verification(loader)), encoding="utf-8"
                )
                paths.append(path)
                paths_by_loader[loader] = path

            wrong_hash = artifact_verification("fabric")
            wrong_hash["published_sha256"] = "a" * 64
            paths_by_loader["fabric"].write_text(
                json.dumps(wrong_hash), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                record.PublishedCompatibilityError, "does not match"
            ):
                record.load_artifact_verifications(
                    paths,
                    publication_id="v1.6.0",
                    target_minecraft_version="26.3",
                    published_hashes=HASHES,
                )

            paths_by_loader["fabric"].write_text(
                json.dumps(artifact_verification("fabric")), encoding="utf-8"
            )
            wrong_publication = artifact_verification("forge")
            wrong_publication["publication"] = "v1.6.1"
            paths_by_loader["forge"].write_text(
                json.dumps(wrong_publication), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                record.PublishedCompatibilityError, "wrong publication"
            ):
                record.load_artifact_verifications(
                    paths,
                    publication_id="v1.6.0",
                    target_minecraft_version="26.3",
                    published_hashes=HASHES,
                )

    def test_cli_accepts_repeated_results_and_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            data_path, result_paths, artifact_paths = write_documents(directory)
            arguments = ["--data", str(data_path), "--verified-on", "2026-08-01"]
            for path in result_paths:
                arguments.extend(["--result", str(path)])
            for path in artifact_paths:
                arguments.extend(["--artifact", str(path)])

            self.assertEqual(0, record.main(arguments))

            updated = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertEqual(["26.2", "26.3"], updated["desired_game_versions"])
            self.assertEqual(
                HASHES["neoforge"],
                updated["runtime_verification"][-1]["loaders"]["neoforge"][
                    "artifact_sha256"
                ],
            )


if __name__ == "__main__":
    unittest.main()
