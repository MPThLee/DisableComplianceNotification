#!/usr/bin/env python3

import importlib.util
import re
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/check-update.py"
FIXTURE_PATH = PROJECT_ROOT / "tools/test/fixtures/minecraft/version_manifest_v2.json"
SPEC = importlib.util.spec_from_file_location("check_update", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
check_update = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_update
SPEC.loader.exec_module(check_update)


class CheckUpdateTest(unittest.TestCase):
    def setUp(self):
        self.manifest = check_update.load_manifest(FIXTURE_PATH, timeout=1)

    def test_repository_fixture_selects_release_and_snapshot(self):
        self.assertEqual("26.3", check_update.select_target(self.manifest, False))
        self.assertEqual(
            "26.4-snapshot-1",
            check_update.select_target(self.manifest, True),
        )

    def test_manifest_order_detects_upgrade_without_downgrade(self):
        self.assertTrue(check_update.is_newer("26.3", "26.2", self.manifest))
        self.assertFalse(check_update.is_newer("26.2", "26.3", self.manifest))
        self.assertFalse(check_update.is_newer("26.3", "26.3", self.manifest))

    def test_numeric_fallback_handles_unlisted_calendar_releases(self):
        self.assertTrue(check_update.is_newer("27.0", "26.3", {}))
        self.assertFalse(check_update.is_newer("26.2", "26.2.1", {}))

    def test_mod_release_patch_is_bumped_for_a_candidate_branch(self):
        self.assertEqual("1.6.1", check_update.bump_patch("1.6.0"))
        with self.assertRaises(check_update.UpdateCheckError):
            check_update.bump_patch("1.6.0-beta")

    def test_malformed_manifest_is_rejected(self):
        with self.assertRaisesRegex(
            check_update.UpdateCheckError, "missing latest versions"
        ):
            check_update.select_target({}, False)

        with self.assertRaisesRegex(
            check_update.UpdateCheckError, "invalid Minecraft release version"
        ):
            check_update.select_target(
                {"latest": {"release": "$(unsafe)", "snapshot": "26w01a"}},
                False,
            )

    def test_periodic_workflow_tests_every_loader_before_pushing(self):
        workflow = (
            PROJECT_ROOT / ".github/workflows/check-update.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('cron: "0 */6 * * *"', workflow)
        self.assertIn("Reject failed loader verification", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("contents: write", workflow)
        probe_position = workflow.index("  probe:\n")
        verify_position = workflow.index("  verify:\n")
        finalize_position = workflow.index("  finalize:\n")
        publish_position = workflow.index("  publish:\n")
        self.assertLess(probe_position, verify_position)
        self.assertLess(verify_position, finalize_position)
        self.assertLess(finalize_position, publish_position)
        probe = workflow[probe_position:verify_position]
        verify = workflow[verify_position:finalize_position]
        finalize = workflow[finalize_position:publish_position]
        publish = workflow[publish_position:]
        for section_name, section in (
            ("probe", probe),
            ("verify", verify),
            ("finalize", finalize),
        ):
            with self.subTest(section=section_name):
                self.assertNotIn("contents: write", section)
                self.assertNotIn("git push", section)
        for section in (verify, finalize, publish):
            self.assertIn(
                "needs.probe.outputs.needs_publish == 'true'",
                section,
            )
        self.assertIn("contents: write", publish)
        self.assertIn("git push", publish)
        self.assertIn(
            'remote_base=$(git ls-remote --heads origin "refs/heads/$BASE_BRANCH"',
            publish,
        )
        self.assertIn('if [ "$remote_base" != "$BASE_SHA" ]', publish)
        for uses_line in re.findall(r"^\s*uses:\s*(.+)$", workflow, re.MULTILINE):
            with self.subTest(action=uses_line):
                self.assertRegex(uses_line, r"@[0-9a-f]{40}(?:\s+#.*)?$")

        self.assertIn("fail-fast: false", verify)
        self.assertIn("timeout-minutes: 90", verify)
        self.assertIn("timeout-minutes: 60", verify)
        for loader in ("fabric", "neoforge", "forge"):
            with self.subTest(loader=loader):
                self.assertIn(f"          - {loader}\n", verify)
        self.assertIn(
            './tools/test/run_client_gate.sh "${{ matrix.loader }}" --xvfb',
            verify,
        )
        self.assertIn("Run Fabric deterministic client gametest", verify)
        self.assertIn("Upload passing ${{ matrix.loader }} gate evidence", verify)
        self.assertIn('candidate-evidence/$LOADER/build', verify)
        self.assertIn("Create candidate source patch", probe)
        self.assertIn("Upload candidate source patch", probe)

        reject_position = finalize.index("- name: Reject failed loader verification")
        evidence_position = finalize.index("- name: Download all passing gate evidence")
        record_position = finalize.index(
            "- name: Record passing compatibility evidence"
        )
        candidate_tests_position = finalize.index(
            "- name: Validate candidate tooling and metadata"
        )
        patch_position = finalize.index("- name: Create tested candidate patch")
        artifact_position = finalize.index("- name: Upload tested candidate patch")
        self.assertLess(reject_position, evidence_position)
        self.assertLess(evidence_position, record_position)
        for loader in ("fabric", "neoforge", "forge"):
            self.assertIn(
                f"--result {loader}/build/client-gate-result.json",
                finalize,
            )
        self.assertLess(record_position, candidate_tests_position)
        self.assertLess(candidate_tests_position, patch_position)
        self.assertLess(patch_position, artifact_position)

    def test_release_workflow_validates_tags_and_gates_every_loader(self):
        workflow = (PROJECT_ROOT / ".github/workflows/build.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Validate release tag matches config version", workflow)
        self.assertIn("fail-fast: false", workflow)
        self.assertIn('expected_tag="v$MOD_VERSION"', workflow)
        self.assertIn('if [ "$RELEASE_TAG" != "$expected_tag" ]', workflow)
        self.assertIn(
            "Run tagged ${{ matrix.loader }} two-minute gate",
            workflow,
        )
        self.assertIn(
            './tools/test/run_client_gate.sh "${{ matrix.loader }}" --xvfb',
            workflow,
        )
        self.assertIn("Run tagged Fabric deterministic client gametest", workflow)
        self.assertIn("timeout-minutes: 60", workflow)
        self.assertIn("retrying once after 15 seconds", workflow)
        self.assertIn("Expected exactly one $LOADER production jar", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertNotIn("pierotofy/set-swap-space", workflow)

    def test_workflow_actions_use_pinned_node24_releases(self):
        expected = {
            "actions/checkout": (
                "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
                "v7.0.0",
            ),
            "actions/setup-java": (
                "0f481fcb613427c0f801b606911222b5b6f3083a",
                "v5.5.0",
            ),
            "actions/upload-artifact": (
                "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
                "v7.0.1",
            ),
            "actions/download-artifact": (
                "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
                "v8.0.1",
            ),
            "actions/setup-python": (
                "ece7cb06caefa5fff74198d8649806c4678c61a1",
                "v6.3.0",
            ),
            "actions/github-script": (
                "3a2844b7e9c422d3c10d287c895573f7108da1b3",
                "v9.0.0",
            ),
            "softprops/action-gh-release": (
                "3d0d9888cb7fd7b750713d6e236d1fcb99157228",
                "v3.0.2",
            ),
            "Kira-NT/mc-publish": (
                "52307b03863581dec6b652b83e597aec02ebb075",
                "v3.3.1",
            ),
        }
        workflows = PROJECT_ROOT / ".github/workflows"
        found = set()
        pattern = re.compile(
            r"^\s*uses:\s*([\w.-]+/[\w.-]+)@([0-9a-f]{40})\s+#\s+(v\S+)$",
            re.MULTILINE,
        )

        for path in workflows.glob("*.yml"):
            content = path.read_text(encoding="utf-8")
            for action, expected_pin in expected.items():
                if f"uses: {action}@" not in content:
                    continue
                found.add(action)
                matches = [
                    (sha, version)
                    for matched_action, sha, version in pattern.findall(content)
                    if matched_action == action
                ]
                with self.subTest(workflow=path.name, action=action):
                    self.assertTrue(matches)
                    self.assertTrue(all(match == expected_pin for match in matches))

        self.assertEqual(set(expected), found)


if __name__ == "__main__":
    unittest.main()
