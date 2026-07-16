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
        self.assertNotIn("Old release", updated)


if __name__ == "__main__":
    unittest.main()
