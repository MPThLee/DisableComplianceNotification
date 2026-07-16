#!/usr/bin/env python3

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/record-marketplace-sync.py"
SPEC = importlib.util.spec_from_file_location("record_marketplace_sync", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
record = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = record
SPEC.loader.exec_module(record)


def release_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "publication": {
            "id": "v1.6.0",
            "release_version": "1.6.0",
            "build_minecraft_version": "26.2",
            "artifacts": {},
        },
        "runtime_verification": [
            {
                "minecraft_version": "26.2",
                "verified_on": "2026-07-16",
                "loaders": {},
            }
        ],
        "desired_game_versions": ["26.2"],
        "marketplace_sync": {
            "publication": "v1.6.0",
            "game_versions": ["26.2"],
            "synced_on": "2026-07-16",
        },
    }


class RecordMarketplaceSyncTest(unittest.TestCase):
    def test_initial_checkpoint_is_current(self):
        current, message = record.check_marketplace_sync(release_data())

        self.assertTrue(current)
        self.assertIn("current for v1.6.0", message)

    def test_new_verified_version_is_pending_until_recorded(self):
        data = release_data()
        data["runtime_verification"].append(
            {"minecraft_version": "26.3", "loaders": {}}
        )
        data["desired_game_versions"] = ["26.2", "26.3"]

        current, message = record.check_marketplace_sync(data)

        self.assertFalse(current)
        self.assertEqual(
            "Marketplace sync pending for v1.6.0: 26.2, 26.3",
            message,
        )

    def test_record_preserves_publication_and_runtime_evidence(self):
        data = release_data()
        data["runtime_verification"].append(
            {"minecraft_version": "26.3", "loaders": {}}
        )
        data["desired_game_versions"] = ["26.2", "26.3"]
        publication_before = copy.deepcopy(data["publication"])
        runtime_before = copy.deepcopy(data["runtime_verification"])

        updated = record.record_marketplace_sync(data, "2026-08-01")

        self.assertEqual(publication_before, updated["publication"])
        self.assertEqual(runtime_before, updated["runtime_verification"])
        self.assertEqual(
            {
                "publication": "v1.6.0",
                "game_versions": ["26.2", "26.3"],
                "synced_on": "2026-08-01",
            },
            updated["marketplace_sync"],
        )
        self.assertTrue(record.check_marketplace_sync(updated)[0])

    def test_record_is_idempotent(self):
        data = release_data()

        first = copy.deepcopy(
            record.record_marketplace_sync(data, "2026-07-16")
        )
        second = record.record_marketplace_sync(data, "2026-07-16")

        self.assertEqual(first, second)

    def test_publication_rollover_is_pending_even_with_same_versions(self):
        data = release_data()
        data["publication"]["id"] = "v1.6.1"

        current, message = record.check_marketplace_sync(data)

        self.assertFalse(current)
        self.assertEqual(
            "Marketplace sync pending for v1.6.1: 26.2",
            message,
        )

    def test_cli_check_record_and_atomic_file_update(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_path = Path(temporary_directory) / "published-release.json"
            data = release_data()
            data["desired_game_versions"] = ["26.2", "26.3"]
            data_path.write_text(json.dumps(data), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    1,
                    record.main(["--check", "--data", str(data_path)]),
                )
            self.assertIn("pending", output.getvalue())

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    0,
                    record.main(
                        [
                            "--record",
                            "--data",
                            str(data_path),
                            "--synced-on",
                            "2026-08-01",
                        ]
                    ),
                )
            self.assertIn("Recorded marketplace sync", output.getvalue())
            self.assertEqual(
                ["26.2", "26.3"],
                json.loads(data_path.read_text(encoding="utf-8"))[
                    "marketplace_sync"
                ]["game_versions"],
            )
            self.assertEqual([], list(data_path.parent.glob("*.tmp")))
            self.assertEqual([], list(data_path.parent.glob(".*.tmp")))

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    record.main(["--check", "--data", str(data_path)]),
                )

    def test_invalid_schema_has_distinct_error_status(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_path = Path(temporary_directory) / "published-release.json"
            data = release_data()
            data["marketplace_sync"]["synced_on"] = "not-a-date"
            data_path.write_text(json.dumps(data), encoding="utf-8")

            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(
                    2,
                    record.main(["--check", "--data", str(data_path)]),
                )
            self.assertIn("ISO date", error.getvalue())

    def test_repository_checkpoint_is_valid_even_while_sync_is_pending(self):
        data = json.loads(
            (PROJECT_ROOT / "data/published-release.json").read_text(
                encoding="utf-8"
            )
        )

        current, message = record.check_marketplace_sync(data)
        self.assertIsInstance(current, bool)
        self.assertIn(data["publication"]["id"], message)


if __name__ == "__main__":
    unittest.main()
