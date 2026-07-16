#!/usr/bin/env python3

import json
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
COMPATIBILITY_PATH = PROJECT_ROOT / "data/minecraft-compatibility.json"
EXPECTED_LOADERS = {"fabric", "neoforge", "forge"}
EXPECTED_NOTIFICATIONS = {
    "compliance.playtime.hours",
    "compliance.playtime.greaterThan24Hours",
}


def read_properties() -> dict[str, str]:
    properties = {}
    for line in (PROJECT_ROOT / "config.properties").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            properties[key] = value
    return properties


class MinecraftCompatibilityDataTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(COMPATIBILITY_PATH.read_text(encoding="utf-8"))
        self.properties = read_properties()

    def test_release_and_build_versions_match_the_project(self):
        self.assertEqual(1, self.data["schema_version"])
        self.assertEqual(self.properties["mod_version"], self.data["release_version"])
        self.assertEqual(
            self.properties["minecraft_version"],
            self.data["build_minecraft_version"],
        )
        self.assertEqual(
            self.properties["minecraft_version"],
            self.data["metadata_compatibility"]["minimum_version"],
        )

    def test_runtime_evidence_covers_every_loader_for_the_build_version(self):
        records = self.data["runtime_verification"]
        records_by_version = {
            record["minecraft_version"]: record for record in records
        }
        self.assertEqual(len(records), len(records_by_version))
        self.assertIn(self.properties["minecraft_version"], records_by_version)

        for version, record in records_by_version.items():
            with self.subTest(minecraft_version=version):
                date.fromisoformat(record["verified_on"])
                self.assertGreaterEqual(record["required_in_world_seconds"], 120)
                self.assertEqual(
                    EXPECTED_NOTIFICATIONS,
                    set(record["filtered_notifications"]),
                )
                self.assertEqual(EXPECTED_LOADERS, set(record["loaders"]))

                for loader, result in record["loaders"].items():
                    with self.subTest(minecraft_version=version, loader=loader):
                        self.assertIs(result["passed"], True)
                        self.assertGreaterEqual(
                            result["observed_in_world_seconds"],
                            record["required_in_world_seconds"],
                        )

    def test_future_metadata_examples_are_not_reported_as_runtime_verified(self):
        minimum = self.data["metadata_compatibility"]["minimum_version"]
        verified = {
            record["minecraft_version"] for record in self.data["runtime_verification"]
        }
        major, minor = (int(part) for part in minimum.split(".")[:2])
        next_release = f"{major}.{minor + 1}"

        self.assertIn(minimum, verified)
        self.assertNotIn(next_release, verified)


if __name__ == "__main__":
    unittest.main()
