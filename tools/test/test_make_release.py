#!/usr/bin/env python3

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


class MakeReleaseTest(unittest.TestCase):
    def test_release_bundle_builds_and_copies_every_loader(self):
        script = (PROJECT_ROOT / "tools/make-release.sh").read_text(encoding="utf-8")

        self.assertGreaterEqual(
            script.count("for loader in fabric neoforge forge"),
            2,
        )
        self.assertIn(
            "$ARCHIVES_BASE_NAME-v$MOD_VERSION+$loader-$MINECRAFT_VERSION.jar",
            script,
        )
        self.assertIn('cp "$artifact" release/', script)
        self.assertNotIn("version=$(./gradlew properties", script)


if __name__ == "__main__":
    unittest.main()
