#!/usr/bin/env python3

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/test/run_client_gate.py"
SPEC = importlib.util.spec_from_file_location("run_client_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


class ClientGateTest(unittest.TestCase):
    def test_options_enable_gate_pack_once_and_mark_it_compatible(self):
        original = (
            'resourcePacks:["vanilla","mod_resources","file/other.zip",'
            '"file/dcn-compliance-gate.zip"]\n'
            'incompatibleResourcePacks:["file/other.zip",'
            '"file/dcn-compliance-gate.zip"]\n'
            "lang:en_us\n"
        )

        rendered = gate.enable_gate_pack(original)

        self.assertEqual(1, rendered.count(gate.GATE_PACK_ID))
        self.assertIn(
            'resourcePacks:["vanilla","mod_resources","file/other.zip",'
            '"file/dcn-compliance-gate.zip"]',
            rendered,
        )
        self.assertIn('incompatibleResourcePacks:["file/other.zip"]', rendered)
        self.assertIn("lang:en_us", rendered)

    def test_options_can_be_created_from_an_empty_run_directory(self):
        rendered = gate.enable_gate_pack("")

        self.assertEqual(
            'resourcePacks:["file/dcn-compliance-gate.zip"]\n'
            "incompatibleResourcePacks:[]\n",
            rendered,
        )

    def test_gate_requires_both_real_filtered_notifications(self):
        state = gate.GateState()
        self.assertTrue(state.observe(gate.INITIALIZED_MARKER, observed_at=10.0))
        self.assertTrue(
            state.observe(
                f"{gate.RESOURCE_PACK_RELOAD_MARKER} vanilla, {gate.GATE_PACK_ID}",
                observed_at=10.5,
            )
        )
        self.assertFalse(
            state.observe(gate.FILTERED_NOTIFICATION_MARKERS["hourly"], observed_at=10.6)
        )
        self.assertTrue(state.observe(gate.INTEGRATED_SERVER_MARKER, observed_at=10.7))
        self.assertTrue(state.observe(f"Player {gate.PLAYER_JOINED_MARKER}", observed_at=10.8))
        self.assertTrue(state.observe(gate.WORLD_JOINED_MARKER, observed_at=11.0))
        self.assertTrue(
            state.observe(gate.FILTERED_NOTIFICATION_MARKERS["hourly"], observed_at=11.0)
        )
        (
            initialized_at,
            resource_pack_loaded,
            integrated_server_started,
            player_joined,
            world_joined_at,
            world_start_failed,
            filtered,
        ) = state.snapshot()
        self.assertEqual(10.0, initialized_at)
        self.assertTrue(resource_pack_loaded)
        self.assertTrue(integrated_server_started)
        self.assertTrue(player_joined)
        self.assertEqual(11.0, world_joined_at)
        self.assertFalse(world_start_failed)
        self.assertEqual({"hourly"}, filtered)

        self.assertTrue(
            state.observe(gate.FILTERED_NOTIFICATION_MARKERS["delayed"], observed_at=130.0)
        )
        self.assertEqual(
            {"hourly", "delayed"},
            state.snapshot()[6],
        )

    def test_gate_rejects_the_wrong_locale_and_missing_pack(self):
        state = gate.GateState()
        self.assertFalse(
            state.observe(
                "Initializing Disable Compliance Notification... "
                "[Locale ISO3 Country: USA]",
                observed_at=10.0,
            )
        )
        self.assertFalse(
            state.observe(
                f"{gate.RESOURCE_PACK_RELOAD_MARKER} vanilla, file/other.zip",
                observed_at=11.0,
            )
        )
        self.assertEqual(
            (None, False, False, False, None, False, set()),
            state.snapshot(),
        )

    def test_gate_detects_world_bootstrap_failure(self):
        state = gate.GateState()
        self.assertTrue(state.observe(gate.WORLD_START_FAILED_MARKER, observed_at=10.0))
        self.assertTrue(state.snapshot()[5])

    def test_generated_pack_uses_the_configured_pack_format_and_fixture(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "gate.zip"
            gate.create_gate_pack(PROJECT_ROOT, destination)

            with zipfile.ZipFile(destination) as archive:
                metadata = json.loads(archive.read("pack.mcmeta"))
                fixture = json.loads(
                    archive.read("assets/minecraft/regional_compliancies.json")
                )

        self.assertEqual([88, 0], metadata["pack"]["min_format"])
        self.assertEqual(88, metadata["pack"]["max_format"])
        self.assertEqual(2, fixture["KOR"][0]["delay"])
        self.assertEqual(1, fixture["KOR"][1]["period"])

    def test_cli_defaults_to_more_than_two_minutes(self):
        args = gate.parse_args(["fabric"])
        self.assertGreaterEqual(
            args.runtime_seconds,
            gate.MINIMUM_GATE_RUNTIME_SECONDS,
        )

    def test_runtime_shorter_than_two_minutes_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least 120 seconds"):
            gate.run_gate(PROJECT_ROOT, "fabric", 119, 300, False)

    def test_workspace_restores_files_and_removes_the_disposable_world(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            loader_dir = Path(temporary_directory) / "fabric"
            game_dir = loader_dir / "run"
            config_path = game_dir / "config/disable_compliance_notification.json5"
            options_path = game_dir / "options.txt"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('{notificationFilterMode:"DISABLE"}\n', encoding="utf-8")
            options_path.write_text('resourcePacks:["vanilla"]\n', encoding="utf-8")
            original_config = config_path.read_bytes()
            original_options = options_path.read_bytes()
            world_name = "dcn_compliance_gate_test"

            with gate.prepared_gate_workspace(PROJECT_ROOT, loader_dir, world_name):
                self.assertFalse(config_path.exists())
                self.assertIn(gate.GATE_PACK_ID, options_path.read_text(encoding="utf-8"))
                world_path = game_dir / "saves" / world_name
                world_path.mkdir(parents=True)
                (world_path / "level.dat").write_bytes(b"generated")

            self.assertEqual(original_config, config_path.read_bytes())
            self.assertEqual(original_options, options_path.read_bytes())
            self.assertFalse((game_dir / "saves" / world_name).exists())
            self.assertFalse(
                (game_dir / "resourcepacks" / gate.GATE_PACK_FILENAME).exists()
            )

    def test_dev_bootstrap_is_excluded_from_every_production_jar(self):
        exclusion = (
            "exclude 'dev/mpthlee/minecraft/disable_compliance_notification/test/**'"
        )
        for loader in ("fabric", "neoforge", "forge"):
            with self.subTest(loader=loader):
                build_script = (PROJECT_ROOT / loader / "build.gradle").read_text(
                    encoding="utf-8"
                )
                self.assertIn("../src/clientgate/java", build_script)
                self.assertIn(exclusion, build_script)

    def test_ci_runs_the_gate_for_every_loader(self):
        workflow = (PROJECT_ROOT / ".github/workflows/test.yml").read_text(
            encoding="utf-8"
        )
        for loader in ("fabric", "neoforge", "forge"):
            with self.subTest(loader=loader):
                self.assertIn(
                    f"./tools/test/run_client_gate.sh {loader} --xvfb",
                    workflow,
                )
        self.assertNotIn("run_client_smoke.sh", workflow)


if __name__ == "__main__":
    unittest.main()
