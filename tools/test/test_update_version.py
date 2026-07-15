#!/usr/bin/env python3

import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "update-version.py"
SPEC = importlib.util.spec_from_file_location("update_version", MODULE_PATH)
UPDATE_VERSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE_VERSION)


def maven_metadata(*versions: str) -> ET.Element:
    version_nodes = "".join(f"<version>{version}</version>" for version in versions)
    return ET.fromstring(
        f"<metadata><versioning><versions>{version_nodes}</versions></versioning></metadata>"
    )


class NeoForgeVersionSelectionTest(unittest.TestCase):
    VERSIONS = (
        "20.2.93",
        "21.0.0-beta",
        "21.11.42",
        "26.1.0.0-alpha.1+snapshot-1",
        "26.1.0.1-beta",
        "26.1.0.19-beta",
        "26.1.1.0-beta",
        "26.1.2.80",
        "26.2.0.0-beta",
        "26.2.0.16-beta",
    )

    def select(self, minecraft_version: str, oldest: bool) -> str:
        metadata = maven_metadata(*self.VERSIONS)
        with patch.object(UPDATE_VERSION, "url_xml", return_value=metadata):
            return UPDATE_VERSION.neoforge(minecraft_version, timeout=1, select_oldest=oldest)

    def test_legacy_version_prefix(self):
        self.assertEqual("20.2.93", self.select("1.20.2", oldest=True))

    def test_legacy_version_without_patch_uses_zero_patch_line(self):
        self.assertEqual("21.0.0-beta", self.select("1.21", oldest=True))
        self.assertEqual("21.0.0-beta", self.select("1.21", oldest=False))

    def test_calendar_release_does_not_select_patch_releases(self):
        self.assertEqual("26.1.0.1-beta", self.select("26.1", oldest=True))
        self.assertEqual("26.1.0.19-beta", self.select("26.1", oldest=False))

    def test_calendar_patch_release_uses_exact_prefix(self):
        self.assertEqual("26.1.2.80", self.select("26.1.2", oldest=True))

    def test_calendar_release_selects_its_zero_patch_line(self):
        self.assertEqual("26.2.0.0-beta", self.select("26.2", oldest=True))
        self.assertEqual("26.2.0.16-beta", self.select("26.2", oldest=False))


if __name__ == "__main__":
    unittest.main()
