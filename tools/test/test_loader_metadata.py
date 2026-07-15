#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


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

    def test_26_2_and_later_contract(self):
        self.assertEqual("26.2", self.minecraft)
        supported = ("26.2", "26.2.1", "26.3", "27.0", "30.4")
        unsupported = ("26.1.2", "26.1", "25.5")

        def numeric_version(candidate: str) -> tuple[int, ...]:
            return tuple(int(part) for part in candidate.split("."))

        for version in supported:
            self.assertGreaterEqual(numeric_version(version), numeric_version(self.minecraft))
        for version in unsupported:
            self.assertLess(numeric_version(version), numeric_version(self.minecraft))


if __name__ == "__main__":
    unittest.main()
