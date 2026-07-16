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

    def test_compatibility_updates_do_not_create_synthetic_mod_releases(self):
        compatibility = check_update.parse_args(
            ["--apply", "--target-version", "26.3"]
        )
        release = check_update.parse_args(
            [
                "--apply",
                "--target-version",
                "26.3",
                "--bump-mod-version",
            ]
        )

        self.assertFalse(compatibility.bump_mod_version)
        self.assertTrue(release.bump_mod_version)

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

    def test_periodic_workflow_is_publication_centric_and_api_retryable(self):
        workflow = (
            PROJECT_ROOT / ".github/workflows/check-update.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('cron: "0 */6 * * *"', workflow)
        self.assertIn("group: published-compatibility-state", workflow)
        jobs_start = workflow.index("jobs:\n") + len("jobs:\n")
        jobs_workflow = workflow[jobs_start:]
        names = re.findall(
            r"^  ([a-z][a-z0-9_]*):\n",
            jobs_workflow,
            re.MULTILINE,
        )
        expected_jobs = (
            "probe",
            "verify",
            "aggregate",
            "publish_evidence",
            "sync_modrinth",
            "sync_curseforge",
            "record_marketplace_sync",
        )
        self.assertEqual(list(expected_jobs), names)

        positions = {
            name: workflow.index(f"  {name}:\n") for name in expected_jobs
        }

        def job(name: str) -> str:
            start = positions[name]
            later = [
                position
                for position in positions.values()
                if position > start
            ]
            end = min(later) if later else len(workflow)
            return workflow[start:end]

        probe = job("probe")
        verify = job("verify")
        aggregate = job("aggregate")
        publish = job("publish_evidence")
        sync_modrinth = job("sync_modrinth")
        sync_curseforge = job("sync_curseforge")
        checkpoint = job("record_marketplace_sync")

        self.assertLess(positions["probe"], positions["verify"])
        self.assertLess(positions["verify"], positions["aggregate"])
        self.assertLess(positions["aggregate"], positions["publish_evidence"])
        for platform in ("sync_modrinth", "sync_curseforge"):
            self.assertLess(positions["publish_evidence"], positions[platform])
            self.assertLess(positions[platform], positions["record_marketplace_sync"])

        for section_name, section in (
            ("probe", probe),
            ("verify", verify),
            ("aggregate", aggregate),
            ("sync_modrinth", sync_modrinth),
            ("sync_curseforge", sync_curseforge),
        ):
            with self.subTest(section=section_name):
                self.assertNotIn("contents: write", section)
                self.assertNotIn("git push", section)

        self.assertIn("contents: write", publish)
        self.assertIn("git push", publish)
        self.assertIn("contents: write", checkpoint)
        self.assertIn("git push", checkpoint)

        self.assertIn("github.event.repository.default_branch", probe)
        self.assertIn("data/published-release.json", probe)
        self.assertIn(".publication.source_commit", probe)
        self.assertIn("record-marketplace-sync.py --check", probe)
        self.assertIn('1) echo "pending=true"', probe)
        self.assertIn(
            "if: steps.marketplace.outputs.pending == 'false'",
            probe,
        )
        self.assertIn("plan-published-compatibility.py", probe)
        self.assertIn(
            "--source-config publication-source/config.properties",
            probe,
        )
        self.assertNotIn("./gradlew", probe)
        self.assertNotIn("git branch -r", probe)
        self.assertNotIn("check-update.py --apply", workflow)

        for uses_line in re.findall(r"^\s*uses:\s*(.+)$", workflow, re.MULTILINE):
            with self.subTest(action=uses_line):
                self.assertRegex(uses_line, r"@[0-9a-f]{40}(?:\s+#.*)?$")

        self.assertIn(
            "matrix: ${{ fromJSON(needs.probe.outputs.matrix) }}",
            verify,
        )
        self.assertIn("fail-fast: false", verify)
        self.assertIn("timeout-minutes: 90", verify)
        self.assertIn("timeout-minutes: 60", verify)
        self.assertIn("ref: ${{ matrix.source_commit }}", verify)
        self.assertIn("candidate/config.properties", verify)
        self.assertIn("./gradlew clean build", verify)
        self.assertIn(
            "--project-root candidate",
            verify,
        )
        self.assertIn("Run Fabric deterministic client gametest", verify)
        self.assertIn("Gate candidate in-world for at least two minutes", verify)
        self.assertIn("Upload passing publication-bound evidence", verify)
        artifact_binding_position = verify.index(
            "- name: Bind candidate to the exact published artifact"
        )
        client_gate_position = verify.index(
            "- name: Gate candidate in-world for at least two minutes"
        )
        self.assertLess(artifact_binding_position, client_gate_position)
        self.assertIn("verify-published-artifact.py", verify)
        self.assertIn("published-artifact-verification.json", verify)

        self.assertIn("Reject failed target or loader verification", aggregate)
        self.assertIn(
            '.targets[] | select(.status == "pending")',
            aggregate,
        )
        self.assertIn("--target-plan", aggregate)
        for loader in ("fabric", "neoforge", "forge"):
            self.assertIn(
                f'--result "compatibility-evidence/$target/{loader}/'
                'client-gate-result.json"',
                aggregate,
            )
            self.assertIn(
                f'--artifact "compatibility-evidence/$target/{loader}/'
                'published-artifact-verification.json"',
                aggregate,
            )
        self.assertIn("data/published-release.json) ;;", aggregate)
        self.assertNotIn("data/minecraft-compatibility.json", aggregate)

        self.assertIn(
            "published_sha: ${{ steps.publish.outputs.published_sha }}",
            publish,
        )
        self.assertIn(
            'git ls-remote --heads origin "refs/heads/$STATE_BRANCH"',
            publish,
        )
        self.assertIn(
            'if [ "$(git diff --cached --name-only)" != '
            '"data/published-release.json" ]',
            publish,
        )
        self.assertIn("[skip ci]", publish)
        self.assertNotIn('target_branch="mc', publish)

        for section in (sync_modrinth, sync_curseforge):
            self.assertIn(
                "needs.publish_evidence.result == 'success'",
                section,
            )
            self.assertIn(
                "needs.publish_evidence.result == 'skipped'",
                section,
            )
            self.assertIn(
                "needs.probe.outputs.has_work == 'false'",
                section,
            )
            self.assertIn(
                "needs.probe.outputs.marketplace_pending == 'true'",
                section,
            )
            self.assertIn("persist-credentials: false", section)
            self.assertIn(
                "needs.publish_evidence.outputs.published_sha || "
                "needs.probe.outputs.base_sha",
                section,
            )
            self.assertIn("sync-platform-compatibility.py", section)
            self.assertNotIn("./gradlew", section)
        self.assertIn("MODRINTH_TOKEN", sync_modrinth)
        self.assertNotIn("CURSEFORGE_TOKEN", sync_modrinth)
        self.assertIn("CURSEFORGE_TOKEN", sync_curseforge)
        self.assertNotIn("MODRINTH_TOKEN", sync_curseforge)
        self.assertIn("${{ github.run_attempt }}", workflow)

        self.assertIn("needs.sync_modrinth.result == 'success'", checkpoint)
        self.assertIn("needs.sync_curseforge.result == 'success'", checkpoint)
        self.assertIn("record-marketplace-sync.py --record", checkpoint)
        self.assertIn("data/published-release.json", checkpoint)
        self.assertIn("[skip ci]", checkpoint)
        self.assertNotIn("./gradlew", checkpoint)

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

    def test_every_ci_gradle_build_has_a_one_hour_step_timeout(self):
        workflows = [
            PROJECT_ROOT / ".github/workflows/build.yml",
            PROJECT_ROOT / ".github/workflows/test.yml",
            PROJECT_ROOT / ".github/workflows/check-update.yml",
        ]
        build_count = 0
        for path in workflows:
            content = path.read_text(encoding="utf-8")
            blocks = re.findall(
                r"^      - name: Build[^\n]*\n(.*?)(?=^      - name: |\Z)",
                content,
                re.MULTILINE | re.DOTALL,
            )
            build_count += len(blocks)
            for block in blocks:
                with self.subTest(workflow=path.name):
                    self.assertIn("timeout-minutes: 60", block)
                    self.assertIn("retrying once after 15 seconds", block)

        self.assertEqual(5, build_count)

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
