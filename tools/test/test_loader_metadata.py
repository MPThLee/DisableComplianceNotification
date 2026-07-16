#!/usr/bin/env python3

import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
COMPATIBILITY_PATH = PROJECT_ROOT / "data/minecraft-compatibility.json"


def read_properties() -> dict[str, str]:
    properties = {}
    for line in (PROJECT_ROOT / "config.properties").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            properties[key] = value
    return properties


def minecraft_range(template_path: Path) -> str:
    template = template_path.read_text(encoding="utf-8")
    match = re.search(
        r'modId\s*=\s*"minecraft".*?versionRange\s*=\s*"([^"]+)"',
        template,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Minecraft dependency not found in {template_path}")
    return match.group(1)


class LoaderMetadataTest(unittest.TestCase):
    def setUp(self):
        self.properties = read_properties()
        self.minecraft = self.properties["minecraft_version"]
        self.compatibility = json.loads(COMPATIBILITY_PATH.read_text(encoding="utf-8"))
        self.minimum = self.compatibility["metadata_compatibility"]["minimum_version"]

    def test_fabric_accepts_the_configured_version_and_later(self):
        metadata = (PROJECT_ROOT / "src/fabric/resources/fabric.mod.json").read_text(
            encoding="utf-8"
        )
        self.assertIn('"minecraft": ">=${minecraft_version}"', metadata)

    def test_forge_like_metadata_uses_an_open_ended_range(self):
        expected_template = "[${minecraft_version},)"
        paths = (
            PROJECT_ROOT / "src/forge/resources/META-INF/mods.toml",
            PROJECT_ROOT / "src/neoforge/resources/META-INF/neoforge.mods.toml",
        )

        for path in paths:
            with self.subTest(loader=path.parts[-4]):
                actual_template = minecraft_range(path)
                self.assertEqual(expected_template, actual_template)
                rendered = actual_template.replace("${minecraft_version}", self.minecraft)
                self.assertEqual(
                    f"[{self.minecraft},)",
                    rendered,
                )

    def test_repository_compatibility_minimum_is_open_ended(self):
        self.assertEqual(self.minimum, self.minecraft)
        self.assertEqual(
            "minimum_inclusive",
            self.compatibility["metadata_compatibility"]["range_kind"],
        )

        def numeric_version(candidate: str) -> tuple[int, ...]:
            return tuple(int(part) for part in candidate.split("."))

        major, minor = numeric_version(self.minimum)[:2]
        supported = (
            self.minimum,
            f"{self.minimum}.1",
            f"{major}.{minor + 1}",
            f"{major + 1}.0",
        )
        unsupported = (f"{major}.{minor - 1}", f"{major - 1}.0")

        for version in supported:
            self.assertGreaterEqual(numeric_version(version), numeric_version(self.minecraft))
        for version in unsupported:
            self.assertLess(numeric_version(version), numeric_version(self.minecraft))


if __name__ == "__main__":
    unittest.main()
