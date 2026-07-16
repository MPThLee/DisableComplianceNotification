#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
WORKFLOW_PATH = PROJECT_ROOT / ".github/workflows/build.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.job_matches = list(
            re.finditer(r"^  ([a-z][a-z0-9_]*):\n", cls.workflow, re.MULTILINE)
        )

    @classmethod
    def job(cls, name: str) -> str:
        for index, match in enumerate(cls.job_matches):
            if match.group(1) != name:
                continue
            end = (
                cls.job_matches[index + 1].start()
                if index + 1 < len(cls.job_matches)
                else len(cls.workflow)
            )
            return cls.workflow[match.start():end]
        raise AssertionError(f"workflow job not found: {name}")

    def test_tag_runs_share_the_publication_state_concurrency_lock(self):
        preamble = self.workflow[: self.workflow.index("jobs:\n")]
        self.assertIn(
            "startsWith(github.ref, 'refs/tags/v') && "
            "'published-compatibility-state'",
            preamble,
        )
        self.assertIn("format('build-{0}', github.ref)", preamble)
        self.assertIn(
            "cancel-in-progress: "
            "${{ !startsWith(github.ref, 'refs/tags/v') }}",
            preamble,
        )

    def test_release_graph_records_state_before_parallel_platform_sync(self):
        names = [match.group(1) for match in self.job_matches]
        for name in (
            "build",
            "release",
            "publish",
            "create_publication",
            "record_publication",
            "sync_modrinth",
            "sync_curseforge",
            "record_marketplace_sync",
        ):
            self.assertIn(name, names)

        self.assertLess(names.index("publish"), names.index("create_publication"))
        self.assertLess(
            names.index("create_publication"), names.index("record_publication")
        )
        self.assertLess(
            names.index("record_publication"), names.index("sync_modrinth")
        )
        self.assertLess(
            names.index("record_publication"), names.index("sync_curseforge")
        )
        self.assertLess(
            names.index("sync_modrinth"), names.index("record_marketplace_sync")
        )
        self.assertLess(
            names.index("sync_curseforge"), names.index("record_marketplace_sync")
        )

        create = self.job("create_publication")
        record = self.job("record_publication")
        modrinth = self.job("sync_modrinth")
        curseforge = self.job("sync_curseforge")
        checkpoint = self.job("record_marketplace_sync")
        self.assertRegex(create, r"(?m)^      - publish$")
        self.assertRegex(record, r"(?m)^      - create_publication$")
        self.assertIn("needs: record_publication", modrinth)
        self.assertIn("needs: record_publication", curseforge)
        self.assertNotIn("sync_curseforge", modrinth)
        self.assertNotIn("sync_modrinth", curseforge)
        self.assertRegex(checkpoint, r"(?m)^      - sync_modrinth$")
        self.assertRegex(checkpoint, r"(?m)^      - sync_curseforge$")

    def test_publish_outputs_are_bound_to_all_fragments_and_release_gates(self):
        publish = self.job("publish")
        create = self.job("create_publication")

        self.assertIn("id: publish", publish)
        self.assertIn(
            "steps.publish.outputs.modrinth-version",
            publish,
        )
        self.assertIn(
            "steps.publish.outputs.curseforge-version",
            publish,
        )
        self.assertIn("publication-fragment-${{ matrix.loader }}", publish)
        self.assertIn("modrinth_version_id: $modrinth_version_id", publish)
        self.assertIn("curseforge_file_id: $curseforge_file_id", publish)

        self.assertIn("ref: ${{ github.sha }}", create)
        self.assertIn("path: tagged-source", create)
        self.assertIn(
            "ref: refs/heads/${{ github.event.repository.default_branch }}",
            create,
        )
        self.assertIn("path: previous-state", create)
        self.assertIn(
            "--previous-data previous-state/data/published-release.json",
            create,
        )
        for loader in ("fabric", "neoforge", "forge"):
            with self.subTest(loader=loader):
                self.assertIn(
                    f"name: tagged-gate-evidence-{loader}",
                    create,
                )
                self.assertIn(
                    "--publication-fragment "
                    f"tagged-source/publication-fragments/{loader}.json",
                    create,
                )
                self.assertIn(
                    "--gate-result "
                    f"tagged-source/tagged-gates/{loader}/"
                    "client-gate-result.json",
                    create,
                )
        self.assertIn("name: pending-published-release", create)
        self.assertIn(
            "path: generated-publication/published-release.json",
            create,
        )

    def test_canonical_record_is_cas_guarded_and_outputs_exact_state(self):
        create = self.job("create_publication")
        record = self.job("record_publication")

        self.assertIn(
            "previous_state_sha: "
            "${{ steps.previous.outputs.previous_state_sha }}",
            create,
        )
        self.assertIn(
            "ref: refs/heads/${{ github.event.repository.default_branch }}",
            record,
        )
        self.assertIn(
            "EXPECTED_BASE_SHA: "
            "${{ needs.create_publication.outputs.previous_state_sha }}",
            record,
        )
        self.assertIn(
            "STATE_BRANCH: ${{ github.event.repository.default_branch }}",
            record,
        )
        self.assertIn(
            "state_branch: ${{ steps.record.outputs.state_branch }}",
            record,
        )
        self.assertIn(
            "state_sha: ${{ steps.record.outputs.state_sha }}",
            record,
        )
        self.assertIn(
            "cp ../generated-publication/published-release.json "
            "data/published-release.json",
            record,
        )
        self.assertIn('case "$path" in', record)
        self.assertIn("data/published-release.json) ;;", record)
        self.assertIn(
            'git ls-remote --heads origin "refs/heads/$STATE_BRANCH"',
            record,
        )
        self.assertIn(
            "git diff --quiet -- data/published-release.json",
            record,
        )
        self.assertIn("[skip ci]", record)
        self.assertIn(
            'git push origin "HEAD:refs/heads/$STATE_BRANCH"',
            record,
        )
        self.assertNotIn('target_branch="mc', record)

    def test_platform_sync_uses_exact_state_and_separate_secrets(self):
        modrinth = self.job("sync_modrinth")
        curseforge = self.job("sync_curseforge")

        for block in (modrinth, curseforge):
            self.assertIn(
                "ref: ${{ needs.record_publication.outputs.state_sha }}",
                block,
            )
            self.assertIn("persist-credentials: false", block)
            self.assertIn(
                "--data data/published-release.json",
                block,
            )
            self.assertIn("Preflight new", block)
            self.assertNotIn("record-marketplace-sync.py", block)

        self.assertIn(
            "MODRINTH_TOKEN: ${{ secrets.MODRINTH_TOKEN }}",
            modrinth,
        )
        self.assertIn("--platform modrinth", modrinth)
        self.assertNotIn("CURSEFORGE_TOKEN", modrinth)
        self.assertIn(
            "CURSEFORGE_TOKEN: ${{ secrets.CURSEFORGE_TOKEN }}",
            curseforge,
        )
        self.assertIn("--platform curseforge", curseforge)
        self.assertNotIn("MODRINTH_TOKEN", curseforge)

    def test_checkpoint_records_only_the_cas_guarded_manifest(self):
        checkpoint = self.job("record_marketplace_sync")

        self.assertIn(
            "ref: ${{ needs.record_publication.outputs.state_sha }}",
            checkpoint,
        )
        self.assertIn(
            "STATE_BRANCH: "
            "${{ needs.record_publication.outputs.state_branch }}",
            checkpoint,
        )
        self.assertIn("record-marketplace-sync.py", checkpoint)
        self.assertIn("--data data/published-release.json", checkpoint)
        self.assertIn("--record", checkpoint)
        self.assertIn('case "$path" in', checkpoint)
        self.assertIn("data/published-release.json) ;;", checkpoint)
        self.assertIn(
            'git ls-remote --heads origin "refs/heads/$STATE_BRANCH"',
            checkpoint,
        )
        self.assertIn(
            "git diff --quiet -- data/published-release.json",
            checkpoint,
        )
        self.assertIn("[skip ci]", checkpoint)
        self.assertIn(
            'git push origin "HEAD:refs/heads/$STATE_BRANCH"',
            checkpoint,
        )

    def test_state_and_api_jobs_never_invoke_gradle(self):
        for name in (
            "create_publication",
            "record_publication",
            "sync_modrinth",
            "sync_curseforge",
            "record_marketplace_sync",
        ):
            with self.subTest(job=name):
                self.assertNotIn("./gradlew", self.job(name))

    def test_build_and_all_loader_gates_remain_bounded(self):
        build = self.job("build")
        self.assertIn('"forge"', build)
        self.assertIn('"neoforge"', build)
        self.assertIn('"fabric"', build)
        self.assertIn("timeout-minutes: 60", build)
        self.assertIn("./gradlew build --console=plain", build)
        self.assertIn(
            "Run tagged Fabric deterministic client gametest",
            build,
        )
        self.assertIn(
            "Run tagged ${{ matrix.loader }} two-minute gate",
            build,
        )
        self.assertIn(
            './tools/test/run_client_gate.sh "${{ matrix.loader }}" --xvfb',
            build,
        )


if __name__ == "__main__":
    unittest.main()
