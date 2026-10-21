#!/usr/bin/env python3
"""Regression coverage for the published compatibility job's runtime selection."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "prepare_published_runtime", Path(__file__).with_name("prepare_published_runtime.py")
)
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class PublishedRuntimeSelectionTest(unittest.TestCase):
    def test_snapshot_api_uses_latest_loader_even_when_not_marked_stable(self):
        target = "26.4-snapshot-5"
        api = {"version_number": "0.160.0+26.4-snapshot-5"}
        loaders = [
            {"version": "0.20.1", "stable": False},
            {"version": "0.20.0", "stable": False},
            {"version": "0.19.5", "stable": True},
        ]
        binding = {"publication": {"release_version": "1.6.0", "build_minecraft_version": "26.2"}}
        artifact = {"filename": "published.jar", "github_url": "https://example.test/mod.jar",
                    "sha256": "digest", "modrinth_sha512": "digest"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fabric").mkdir()
            (root / "fabric/build.gradle").write_text("")
            (root / "config.properties").write_text("minecraft_version=26.2\nfabric_loader_version=0.19.3\nfabric_api_version=old\npack_format=88\njava_version=25\n")
            with patch.dict(RUNTIME.VERIFY, {
                "load_binding": lambda *args: (binding, artifact),
                "download_published": lambda *args: None,
                "hash_file": lambda *args: "digest",
            }), patch.object(RUNTIME, "minecraft_entry", return_value={"type": "snapshot"}), \
                patch.object(RUNTIME, "latest_mod", return_value=api), \
                patch.object(RUNTIME.UPDATE, "url_json", return_value=loaders), \
                patch.object(RUNTIME.UPDATE, "mc_version", return_value=("99", "25")):
                result = RUNTIME.prepare(root, root / "data.json", "fabric", target)
            self.assertEqual("ready", result["status"])
            self.assertEqual("0.20.1", result["runtime"]["fabric_loader_version"])
            self.assertIn("fabric_loader_version=0.20.1", (root / "config.properties").read_text())

    def test_mod_selection_requires_exact_game_version_and_loader(self):
        versions = [
            {"id": "correct", "game_versions": ["26.2"], "loaders": ["fabric"], "date_published": "2026-06-01"},
            {"id": "wrong-game", "game_versions": ["26.2.1"], "loaders": ["fabric"], "date_published": "2026-07-01"},
            {"id": "wrong-loader", "game_versions": ["26.2"], "loaders": ["neoforge"], "date_published": "2026-08-01"},
        ]
        with patch.object(RUNTIME.UPDATE, "url_json", return_value=versions):
            self.assertEqual("correct", RUNTIME.latest_mod("fabric-api", "26.2", "fabric")["id"])
            with self.assertRaises(RUNTIME.Unavailable):
                RUNTIME.latest_mod("fabric-api", "26.3", "fabric")


if __name__ == "__main__":
    unittest.main()
