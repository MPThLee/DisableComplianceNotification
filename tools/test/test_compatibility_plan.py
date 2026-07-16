#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import io
import json
import copy
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))
import compatibility_plan as planner  # noqa: E402

CLI_PATH = TOOLS_DIR / "plan-published-compatibility.py"
CLI_SPEC = importlib.util.spec_from_file_location(
    "plan_published_compatibility", CLI_PATH
)
assert CLI_SPEC is not None and CLI_SPEC.loader is not None
plan_cli = importlib.util.module_from_spec(CLI_SPEC)
sys.modules[CLI_SPEC.name] = plan_cli
CLI_SPEC.loader.exec_module(plan_cli)


LOADERS = ("fabric", "neoforge", "forge")
HASHES = {
    "fabric": "1" * 64,
    "neoforge": "2" * 64,
    "forge": "3" * 64,
}


def manifest(latest: str = "26.3") -> dict[str, object]:
    return {
        "latest": {
            "release": latest,
            "snapshot": "26.4-snapshot-1",
        },
        "versions": [
            {"id": "26.4-snapshot-1", "type": "snapshot"},
            {"id": "26.3", "type": "release"},
            {"id": "26.2.2-pre1", "type": "release"},
            {"id": "26.2.1", "type": "release"},
            {"id": "26.2", "type": "release"},
            {"id": "26.1.2", "type": "release"},
        ],
    }


def source_text(*, mod_version: str = "1.6.0") -> str:
    return f"""# publication source
archives_base_name=disable_compliance_notification
maven_group=dev.mpthlee.minecraft.disable_compliance_notification
java_version=25
mod_version={mod_version}
minecraft_version=26.2
pack_format=88.0
forge_version=65.0.0
neoforge_version=26.2.0.0-beta
fabric_loader_version=0.19.3
fabric_api_version=0.145.4
mixin_processor_version=0.8.7
fabric_mixin_processor_version=0.17.1
yacl_version=3.9.5+26.2
modmenu_version=20.0.1
"""


def make_source(
    root: Path, *, mod_version: str = "1.6.0"
) -> planner.SourceConfig:
    path = root / "config.properties"
    path.write_text(source_text(mod_version=mod_version), encoding="utf-8")
    return planner.load_source_config(path)


def publication_data(
    runtime_verification: list[dict[str, object]] | None = None,
    *,
    release_version: str = "1.6.0",
    publication_id: str = "v1.6.0",
    source_commit: str = "a" * 40,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "publication": {
            "id": publication_id,
            "tag": publication_id,
            "release_version": release_version,
            "build_minecraft_version": "26.2",
            "source_commit": source_commit,
            "artifacts": {
                loader: {
                    "sha256": HASHES[loader],
                    "filename": f"mod-{loader}.jar",
                }
                for loader in LOADERS
            },
        },
        "runtime_verification": runtime_verification or [],
    }


class FakeResolver:
    def __init__(self, *, revision: str = "a"):
        self.revision = revision
        self.calls: list[tuple[str, float, bool]] = []

    def __call__(
        self, target: str, *, timeout: float, select_oldest: bool
    ) -> dict[str, str]:
        self.calls.append((target, timeout, select_oldest))
        suffix = target.replace(".", "")
        return {
            "minecraft_version": target,
            "forge_version": f"{suffix}.0-{self.revision}",
            "neoforge_version": f"{suffix}.0.0-{self.revision}",
            "pack_format": f"{90 + len(target)}.0",
            "java_version": "26",
            "fabric_loader_version": f"0.20.{len(target)}",
            "fabric_api_version": f"0.150.{suffix}+{target}",
            "yacl_version": f"4.0.{suffix}+{target}-fabric",
            "modmenu_version": f"21.0.{suffix}",
        }


def current_record(
    data: dict[str, object],
    version: str,
    fingerprint: str,
) -> dict[str, object]:
    publication = data["publication"]
    assert isinstance(publication, dict)
    artifacts = publication["artifacts"]
    assert isinstance(artifacts, dict)
    return {
        "minecraft_version": version,
        "publication": publication["id"],
        "source_commit": publication["source_commit"],
        "dependency_fingerprint": fingerprint,
        "verified_on": "2026-07-16",
        "required_in_world_seconds": 120,
        "filtered_notifications": [
            "compliance.playtime.greaterThan24Hours",
            "compliance.playtime.hours",
        ],
        "loaders": {
            loader: {
                "observed_in_world_seconds": 150.0,
                "periodic_toast_absent": True,
                "passed": True,
                "artifact_sha256": artifacts[loader]["sha256"],
            }
            for loader in LOADERS
        },
    }


class CompatibilityPlanTest(unittest.TestCase):
    def test_enumerates_every_numeric_release_oldest_to_newest(self):
        self.assertEqual(
            ["26.2", "26.2.1", "26.3"],
            planner.enumerate_release_versions(manifest(), "26.2"),
        )

    def test_manifest_fixture_loader_and_numeric_validation(self):
        fixture = (
            PROJECT_ROOT
            / "tools/test/fixtures/minecraft/version_manifest_v2.json"
        )
        loaded = planner.load_manifest(fixture, timeout=1)
        self.assertEqual("26.3", planner.latest_release(loaded))
        with self.assertRaisesRegex(
            planner.CompatibilityPlanError, "numeric release"
        ):
            planner.enumerate_release_versions(
                {
                    "latest": {"release": "26.3-rc1"},
                    "versions": [],
                },
                "26.2",
            )

    def test_missing_and_legacy_records_schedule_every_target_loader(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            data = publication_data(
                [
                    {
                        "minecraft_version": "26.2",
                        "required_in_world_seconds": 120,
                        "loaders": {},
                    }
                ]
            )
            resolver = FakeResolver()

            plan = planner.build_compatibility_plan(
                data,
                source,
                manifest(),
                resolver=resolver,
                timeout=7,
            )

        expected_pairs = [
            (version, loader)
            for version in ("26.2", "26.2.1", "26.3")
            for loader in LOADERS
        ]
        actual_pairs = [
            (entry["minecraft_version"], entry["loader"])
            for entry in plan["matrix"]["include"]
        ]
        self.assertEqual(expected_pairs, actual_pairs)
        self.assertEqual(
            [
                ("26.2.1", 7, True),
                ("26.3", 7, True),
            ],
            resolver.calls,
        )
        self.assertTrue(plan["has_work"])
        self.assertEqual("v1.6.0", plan["publication_id"])
        self.assertEqual("a" * 40, plan["source_commit"])
        for target in plan["targets"]:
            self.assertEqual("1.6.0", target["resolved_config"]["mod_version"])
            self.assertRegex(
                target["dependency_fingerprint"], r"^[0-9a-f]{64}$"
            )
        self.assertEqual(
            source.properties,
            plan["targets"][0]["resolved_config"],
        )
        self.assertEqual(
            "25",
            plan["matrix"]["include"][0]["java_version"],
        )
        patch_target = plan["targets"][1]
        self.assertEqual(
            "0.150.2621",
            patch_target["resolved_config"]["fabric_api_version"],
        )
        self.assertEqual(
            "4.0.2621+26.2.1",
            patch_target["resolved_config"]["yacl_version"],
        )

    def test_matching_fingerprints_yield_an_empty_matrix(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            data = publication_data()
            first = planner.build_compatibility_plan(
                data,
                source,
                manifest(),
                resolver=FakeResolver(),
            )
            data["runtime_verification"] = [
                current_record(
                    data,
                    target["minecraft_version"],
                    target["dependency_fingerprint"],
                )
                for target in first["targets"]
            ]

            current = planner.build_compatibility_plan(
                data,
                source,
                manifest(),
                resolver=FakeResolver(),
            )

        self.assertFalse(current["has_work"])
        self.assertEqual({"include": []}, current["matrix"])
        self.assertTrue(
            all(target["status"] == "verified" for target in current["targets"])
        )

    def test_one_stale_loader_schedules_a_complete_three_loader_proof(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            data = publication_data()
            baseline = planner.build_compatibility_plan(
                data,
                source,
                manifest(latest="26.2"),
                resolver=FakeResolver(),
            )
            record = current_record(
                data,
                "26.2",
                baseline["targets"][0]["dependency_fingerprint"],
            )
            record["loaders"]["forge"]["passed"] = False
            data["runtime_verification"] = [record]

            plan = planner.build_compatibility_plan(
                data,
                source,
                manifest(latest="26.2"),
                resolver=FakeResolver(),
            )

        self.assertEqual(
            [
                ("26.2", "fabric"),
                ("26.2", "neoforge"),
                ("26.2", "forge"),
            ],
            [
                (entry["minecraft_version"], entry["loader"])
                for entry in plan["matrix"]["include"]
            ],
        )

    def test_changed_dependency_resolution_invalidates_previous_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            data = publication_data()
            original = planner.build_compatibility_plan(
                data,
                source,
                {
                    "latest": {"release": "26.2.1"},
                    "versions": [
                        {"id": "26.2.1", "type": "release"},
                        {"id": "26.2", "type": "release"},
                    ],
                },
                resolver=FakeResolver(revision="a"),
            )
            data["runtime_verification"] = [
                current_record(
                    data,
                    target["minecraft_version"],
                    target["dependency_fingerprint"],
                )
                for target in original["targets"]
            ]

            changed = planner.build_compatibility_plan(
                data,
                source,
                {
                    "latest": {"release": "26.2.1"},
                    "versions": [
                        {"id": "26.2.1", "type": "release"},
                        {"id": "26.2", "type": "release"},
                    ],
                },
                resolver=FakeResolver(revision="b"),
            )

        self.assertNotEqual(
            original["targets"][1]["dependency_fingerprint"],
            changed["targets"][1]["dependency_fingerprint"],
        )
        self.assertEqual(
            [], changed["targets"][0]["pending_loaders"]
        )
        self.assertEqual(
            list(LOADERS), changed["targets"][1]["pending_loaders"]
        )

    def test_incomplete_evidence_schedules_all_loaders(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            data = publication_data()
            baseline = planner.build_compatibility_plan(
                data,
                source,
                manifest(latest="26.2"),
                resolver=FakeResolver(),
            )
            complete = current_record(
                data,
                "26.2",
                baseline["targets"][0]["dependency_fingerprint"],
            )
            invalid_records = []

            too_short = copy.deepcopy(complete)
            too_short["required_in_world_seconds"] = 119
            invalid_records.append(too_short)

            wrong_notifications = copy.deepcopy(complete)
            wrong_notifications["filtered_notifications"] = [
                "compliance.playtime.hours",
                "compliance.playtime.hours",
            ]
            invalid_records.append(wrong_notifications)

            invalid_date = copy.deepcopy(complete)
            invalid_date["verified_on"] = "not-a-date"
            invalid_records.append(invalid_date)

            wrong_hash = copy.deepcopy(complete)
            wrong_hash["loaders"]["fabric"]["artifact_sha256"] = "f" * 64
            invalid_records.append(wrong_hash)

            short_observation = copy.deepcopy(complete)
            short_observation["loaders"]["neoforge"][
                "observed_in_world_seconds"
            ] = 119.9
            invalid_records.append(short_observation)

            for record in invalid_records:
                with self.subTest(record=record):
                    data["runtime_verification"] = [record]
                    plan = planner.build_compatibility_plan(
                        data,
                        source,
                        manifest(latest="26.2"),
                        resolver=FakeResolver(),
                    )
                    self.assertEqual(
                        list(LOADERS),
                        plan["targets"][0]["pending_loaders"],
                    )

    def test_fingerprint_is_deterministic_and_order_independent(self):
        first = planner.compute_dependency_fingerprint({"b": "2", "a": "1"})
        second = planner.compute_dependency_fingerprint({"a": "1", "b": "2"})
        self.assertEqual(first, second)

    def test_default_resolver_imports_update_version_and_selects_oldest(self):
        calls: list[tuple[str, float, bool]] = []

        class FakeVersionUpdateError(RuntimeError):
            pass

        fake_module = SimpleNamespace(
            VersionUpdateError=FakeVersionUpdateError,
            load_versions=lambda target, *, timeout, select_oldest: (
                calls.append((target, timeout, select_oldest)) or object()
            ),
        )
        with patch.object(
            planner, "_load_update_version_module", return_value=fake_module
        ):
            planner.default_dependency_resolver(
                "26.3", timeout=9, select_oldest=True
            )
        self.assertEqual([("26.3", 9, True)], calls)

    def test_rejects_source_config_from_a_different_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = make_source(Path(temporary_directory), mod_version="1.6.1")
            with self.assertRaisesRegex(
                planner.CompatibilityPlanError, "mod version does not match"
            ):
                planner.build_compatibility_plan(
                    publication_data(),
                    source,
                    manifest(),
                    resolver=FakeResolver(),
                )

    def test_cli_writes_overall_and_per_target_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            publication_path = root / "published-release.json"
            publication_path.write_text(
                json.dumps(publication_data()), encoding="utf-8"
            )
            manifest_path = root / "version_manifest_v2.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            output_dir = root / "plan"
            github_output = root / "github-output.txt"

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = plan_cli.main(
                    [
                        "--publication-data",
                        str(publication_path),
                        "--source-config",
                        str(source.path),
                        "--manifest-file",
                        str(manifest_path),
                        "--output-dir",
                        str(output_dir),
                        "--github-output",
                        str(github_output),
                    ],
                    resolver=FakeResolver(),
                )

            self.assertEqual(0, status, stderr.getvalue())
            overall = json.loads((output_dir / "plan.json").read_text())
            self.assertEqual(
                ["26.2", "26.2.1", "26.3"],
                overall["minecraft_versions"],
            )
            target_plan = json.loads(
                (output_dir / "targets/26.2.1/plan.json").read_text()
            )
            self.assertEqual("v1.6.0", target_plan["publication_id"])
            self.assertEqual("a" * 40, target_plan["source_commit"])
            rendered = planner.parse_properties(
                (
                    output_dir / "targets/26.2.1/config.properties"
                ).read_text()
            )
            self.assertEqual("1.6.0", rendered["mod_version"])
            self.assertEqual("26.2.1", rendered["minecraft_version"])
            outputs = github_output.read_text()
            self.assertIn("has_work=true", outputs)
            self.assertIn("matrix={\"include\":[", outputs)
            self.assertEqual(overall["matrix"], json.loads(stdout.getvalue()))

    def test_cli_no_update_is_successful_with_an_empty_matrix(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = make_source(root)
            data = publication_data()
            baseline = planner.build_compatibility_plan(
                data,
                source,
                manifest(latest="26.2"),
                resolver=FakeResolver(),
            )
            data["runtime_verification"] = [
                current_record(
                    data,
                    "26.2",
                    baseline["targets"][0]["dependency_fingerprint"],
                )
            ]
            publication_path = root / "published-release.json"
            publication_path.write_text(json.dumps(data), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest(latest="26.2")), encoding="utf-8"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
                status = plan_cli.main(
                    [
                        "--publication-data",
                        str(publication_path),
                        "--source-config",
                        str(source.path),
                        "--manifest-file",
                        str(manifest_path),
                        "--output-dir",
                        str(root / "plan"),
                    ],
                    resolver=FakeResolver(),
                )

        self.assertEqual(0, status)
        self.assertEqual({"include": []}, json.loads(stdout.getvalue()))


if __name__ == "__main__":
    unittest.main()
