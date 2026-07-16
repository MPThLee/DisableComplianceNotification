#!/usr/bin/env python3

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/make-template.py"
SPEC = importlib.util.spec_from_file_location("make_template", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
make_template = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = make_template
SPEC.loader.exec_module(make_template)


class MakeTemplateTest(unittest.TestCase):
    def test_calendar_version_heading_is_preserved(self):
        self.assertEqual(
            ("26.2.x", "26.2"),
            make_template.parse_major_minor("26.2"),
        )

    def test_existing_calendar_release_block_is_replaced_not_duplicated(self):
        original = "# Downloads\n\n## 26.2.x\n\n### 26.2\n\nOld release\n"
        block = make_template.build_download_block("26.2", "v1.6.0")

        updated = make_template.insert_version_in_download(
            original,
            *make_template.parse_major_minor("26.2"),
            block,
        )

        self.assertEqual(1, updated.count("### 26.2\n"))
        self.assertIn("releases/tag/v1.6.0", updated)
        self.assertIn("#### Forge", updated)
        self.assertNotIn("built-in client config", updated)
        self.assertNotIn("Old release", updated)

    def test_generated_release_docs_keep_recommendations_without_a_forge_note(self):
        download = make_template.build_download_block("26.3", "1.6.1")
        latest = make_template.build_latest_block("26.3", "1.6.1")

        self.assertTrue(
            latest.startswith(
                "### Latest (v1.6.1 for Minecraft 26.3 and later)\n"
            )
        )
        for block in (download, latest):
            with self.subTest(block=block.splitlines()[0]):
                self.assertEqual(2, block.count("Recommended with [YACL]"))
                self.assertEqual(1, block.count("and [Mod Menu]"))
                self.assertIn("#### NeoForge", block)
                self.assertIn("#### Forge", block)
                self.assertIn("+forge-26.3.jar", block)
                self.assertNotIn("built-in client config", block)

    def test_current_release_docs_match_the_generator(self):
        properties = {}
        for line in (PROJECT_ROOT / "config.properties").read_text(
            encoding="utf-8"
        ).splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                properties[key] = value

        game_version = properties["minecraft_version"]
        mod_version = properties["mod_version"]
        generated_download = make_template.build_download_block(
            game_version, mod_version
        )
        generated_latest = make_template.build_latest_block(
            game_version, mod_version
        )

        self.assertIn(
            generated_download,
            (PROJECT_ROOT / "DOWNLOAD.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            generated_latest.rstrip(),
            (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
