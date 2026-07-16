#!/usr/bin/env python3

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/record-minecraft-compatibility.py"
SPEC = importlib.util.spec_from_file_location("record_minecraft_compatibility", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
record = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = record
SPEC.loader.exec_module(record)


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


class RecordMinecraftCompatibilityTest(unittest.TestCase):
    def test_all_loader_results_append_verified_candidate(self):
        original = {
            "schema_version": 1,
            "release_version": "1.6.0",
            "build_minecraft_version": "26.2",
            "metadata_compatibility": {
                "minimum_version": "26.2",
                "range_kind": "minimum_inclusive",
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
        results = {
            loader: gate_result(loader) for loader in record.EXPECTED_LOADERS
        }

        updated = record.update_compatibility_data(
            original,
            {"minecraft_version": "26.3", "mod_version": "1.6.1"},
            results,
            "2026-08-01",
        )

        self.assertEqual("1.6.1", updated["release_version"])
        self.assertEqual("26.3", updated["build_minecraft_version"])
        self.assertEqual(
            "26.3", updated["metadata_compatibility"]["minimum_version"]
        )
        self.assertEqual(
            ["26.2", "26.3"],
            [item["minecraft_version"] for item in updated["runtime_verification"]],
        )
        candidate = updated["runtime_verification"][-1]
        self.assertEqual(record.EXPECTED_LOADERS, set(candidate["loaders"]))
        self.assertEqual(150.5, candidate["loaders"]["fabric"]["observed_in_world_seconds"])
        self.assertIs(candidate["loaders"]["fabric"]["periodic_toast_absent"], True)

    def test_current_attestation_requires_matching_complete_evidence(self):
        data = json.loads(
            (PROJECT_ROOT / "data/minecraft-compatibility.json").read_text(
                encoding="utf-8"
            )
        )
        properties = record.read_properties(PROJECT_ROOT / "config.properties")

        self.assertTrue(record.current_version_is_verified(data, properties))
        data["runtime_verification"][0]["loaders"].pop("forge")
        self.assertFalse(record.current_version_is_verified(data, properties))

    def test_current_attestation_rejects_nonfinite_or_ambiguous_evidence(self):
        data = json.loads(
            (PROJECT_ROOT / "data/minecraft-compatibility.json").read_text(
                encoding="utf-8"
            )
        )
        properties = record.read_properties(PROJECT_ROOT / "config.properties")

        for field, value in (
            ("required_in_world_seconds", float("nan")),
            ("required_in_world_seconds", float("inf")),
        ):
            with self.subTest(field=field, value=value):
                candidate = json.loads(json.dumps(data))
                candidate["runtime_verification"][0][field] = value
                self.assertFalse(
                    record.current_version_is_verified(candidate, properties)
                )

        candidate = json.loads(json.dumps(data))
        candidate["runtime_verification"][0]["loaders"]["fabric"][
            "observed_in_world_seconds"
        ] = float("-inf")
        self.assertFalse(record.current_version_is_verified(candidate, properties))

        for notifications in (
            [
                "compliance.playtime.hours",
                "compliance.playtime.greaterThan24Hours",
                "compliance.playtime.hours",
            ],
            [
                "compliance.playtime.hours",
                {"unexpected": "value"},
            ],
        ):
            with self.subTest(notifications=notifications):
                candidate = json.loads(json.dumps(data))
                candidate["runtime_verification"][0][
                    "filtered_notifications"
                ] = notifications
                self.assertFalse(
                    record.current_version_is_verified(candidate, properties)
                )

    def test_result_loading_requires_every_loader_and_two_minutes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = []
            for loader in ("fabric", "neoforge"):
                path = Path(temporary_directory) / f"{loader}.json"
                path.write_text(json.dumps(gate_result(loader)), encoding="utf-8")
                paths.append(path)

            with self.assertRaisesRegex(
                record.CompatibilityRecordError, "missing gate results for: forge"
            ):
                record.load_gate_results(paths, "26.3")

            forge_path = Path(temporary_directory) / "forge.json"
            too_short = gate_result("forge")
            too_short["observed_in_world_seconds"] = 119.9
            forge_path.write_text(json.dumps(too_short), encoding="utf-8")
            with self.assertRaisesRegex(
                record.CompatibilityRecordError, "shorter than two minutes"
            ):
                record.load_gate_results([*paths, forge_path], "26.3")

    def test_result_loading_rejects_nonfinite_durations_and_notifications(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = []
            paths_by_loader = {}
            for loader in sorted(record.EXPECTED_LOADERS):
                path = directory / f"{loader}.json"
                path.write_text(
                    json.dumps(gate_result(loader)), encoding="utf-8"
                )
                paths.append(path)
                paths_by_loader[loader] = path

            for field, value in (
                ("minimum_in_world_seconds", float("nan")),
                ("requested_in_world_seconds", float("inf")),
                ("observed_in_world_seconds", float("-inf")),
            ):
                with self.subTest(field=field):
                    invalid = gate_result("forge")
                    invalid[field] = value
                    paths_by_loader["forge"].write_text(
                        json.dumps(invalid), encoding="utf-8"
                    )
                    with self.assertRaises(record.CompatibilityRecordError):
                        record.load_gate_results(paths, "26.3")

            for notifications in (
                [
                    "compliance.playtime.hours",
                    "compliance.playtime.greaterThan24Hours",
                    "compliance.playtime.hours",
                ],
                [
                    "compliance.playtime.hours",
                    {"unexpected": "value"},
                ],
            ):
                with self.subTest(notifications=notifications):
                    invalid = gate_result("forge")
                    invalid["filtered_notifications"] = notifications
                    paths_by_loader["forge"].write_text(
                        json.dumps(invalid), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(
                        record.CompatibilityRecordError,
                        "exactly both compliance notifications",
                    ):
                        record.load_gate_results(paths, "26.3")


if __name__ == "__main__":
    unittest.main()
