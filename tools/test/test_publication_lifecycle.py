#!/usr/bin/env python3

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]
TOOLS_ROOT = PROJECT_ROOT / "tools"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS_ROOT / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


planner = load_module("lifecycle_compatibility_plan", "compatibility_plan.py")
creator = load_module(
    "lifecycle_create_published_release",
    "create-published-release.py",
)
recorder = load_module(
    "lifecycle_record_published_compatibility",
    "record-published-compatibility.py",
)
marketplace = load_module(
    "lifecycle_record_marketplace_sync",
    "record-marketplace-sync.py",
)
sync = load_module(
    "lifecycle_sync_platform_compatibility",
    "sync-platform-compatibility.py",
)


LOADERS = ("fabric", "neoforge", "forge")
SOURCE_COMMITS = {
    "1.6.0": "a" * 40,
    "1.6.1": "b" * 40,
}
HASHES = {
    "1.6.0": {
        "fabric": "1" * 64,
        "neoforge": "2" * 64,
        "forge": "3" * 64,
    },
    "1.6.1": {
        "fabric": "4" * 64,
        "neoforge": "5" * 64,
        "forge": "6" * 64,
    },
}
MODRINTH_IDS = {
    "1.6.0": {
        "fabric": "old-fabric",
        "neoforge": "old-neoforge",
        "forge": "old-forge",
    },
    "1.6.1": {
        "fabric": "new-fabric",
        "neoforge": "new-neoforge",
        "forge": "new-forge",
    },
}
CURSEFORGE_IDS = {
    "1.6.0": {
        "fabric": 800001,
        "neoforge": 800002,
        "forge": 800003,
    },
    "1.6.1": {
        "fabric": 900001,
        "neoforge": 900002,
        "forge": 900003,
    },
}


def properties(
    mod_version: str,
    minecraft_version: str = "26.2",
) -> dict[str, str]:
    return {
        "archives_base_name": "disable_compliance_notification",
        "fabric_api_version": "0.145.4",
        "fabric_loader_version": "0.19.3",
        "fabric_mixin_processor_version": "0.17.1",
        "forge_version": "65.0.0",
        "java_version": "25",
        "maven_group": "dev.mpthlee.minecraft.disable_compliance_notification",
        "minecraft_version": minecraft_version,
        "mixin_processor_version": "0.8.7",
        "mod_version": mod_version,
        "modmenu_version": "20.0.1",
        "neoforge_version": "26.2.0.0-beta",
        "pack_format": "88.0",
        "yacl_version": "3.9.5+26.2",
    }


def fragments(mod_version: str) -> dict[str, dict[str, object]]:
    result = {}
    for index, loader in enumerate(LOADERS, start=1):
        filename = (
            "disable_compliance_notification-"
            f"v{mod_version}+{loader}-26.2.jar"
        )
        result[loader] = {
            "filename": filename,
            "github_url": (
                "https://github.com/MPThLee/DisableComplianceNotification/"
                f"releases/download/v{mod_version}/{filename}"
            ),
            "sha256": HASHES[mod_version][loader],
            "modrinth_version_id": MODRINTH_IDS[mod_version][loader],
            "modrinth_sha512": str(index) * 128,
            "curseforge_file_id": CURSEFORGE_IDS[mod_version][loader],
            "curseforge_loader": creator.CURSEFORGE_LOADERS[loader],
        }
    return result


def gates(version: str) -> dict[str, dict[str, object]]:
    return {
        loader: {
            "schema_version": 1,
            "loader": loader,
            "minecraft_version": version,
            "minimum_in_world_seconds": 120,
            "requested_in_world_seconds": 150,
            "observed_in_world_seconds": 150.5,
            "filtered_notifications": sorted(
                creator.EXPECTED_NOTIFICATIONS
            ),
            "periodic_toast_absent": True,
            "passed": True,
        }
        for loader in LOADERS
    }


def publication_document(mod_version: str) -> dict[str, object]:
    return creator.create_document(
        properties=properties(mod_version),
        tag=f"v{mod_version}",
        source_commit=SOURCE_COMMITS[mod_version],
        fragments=fragments(mod_version),
        gate_results=gates("26.2"),
        verified_on="2026-07-16",
    )


def resolver(target: str, *, timeout: float, select_oldest: bool):
    assert timeout > 0
    assert select_oldest is True
    return {
        "minecraft_version": target,
        "forge_version": f"{target}-forge",
        "neoforge_version": f"{target}-neoforge",
        "pack_format": f"{target}.0",
        "java_version": "26",
        "fabric_loader_version": "0.20.0",
        "fabric_api_version": f"1.0.0+{target}",
        "yacl_version": f"4.0.0+{target}-fabric",
        "modmenu_version": f"21.0.0+{target}",
    }


def manifest() -> dict[str, object]:
    return {
        "latest": {"release": "26.3", "snapshot": "26.4-snapshot-1"},
        "versions": [
            {"id": "26.3", "type": "release"},
            {"id": "26.2.1", "type": "release"},
            {"id": "26.2", "type": "release"},
        ],
    }


class PublicationLifecycleTest(unittest.TestCase):
    def test_new_mod_release_reearns_every_later_minecraft_version(self):
        old = publication_document("1.6.0")
        old_source = planner.SourceConfig(
            path=Path("v1.6.0/config.properties"),
            text="",
            properties=properties("1.6.0"),
        )
        old_plan = planner.build_compatibility_plan(
            old,
            old_source,
            manifest(),
            resolver=resolver,
        )
        for target in old_plan["targets"]:
            if target["minecraft_version"] == "26.2":
                continue
            recorder.update_published_compatibility(
                old,
                gates(target["minecraft_version"]),
                {
                    loader: {
                        "loader": loader,
                        "passed": True,
                    }
                    for loader in LOADERS
                },
                target_minecraft_version=target["minecraft_version"],
                published_hashes=HASHES["1.6.0"],
                dependency_fingerprint_value=target[
                    "dependency_fingerprint"
                ],
                resolved_config=target["resolved_config"],
                verified_on="2026-07-16",
            )
        old["marketplace_sync"] = {
            "publication": "v1.6.0",
            "game_versions": ["26.2", "26.2.1", "26.3"],
            "synced_on": "2026-07-16",
        }
        old_before_rollover = copy.deepcopy(old)

        new = publication_document("1.6.1")
        creator.validate_against_previous(new, old)

        self.assertEqual(["26.2"], new["desired_game_versions"])
        self.assertNotIn("marketplace_sync", new)
        self.assertFalse(marketplace.check_marketplace_sync(new)[0])

        new_source = planner.SourceConfig(
            path=Path("v1.6.1/config.properties"),
            text="",
            properties=properties("1.6.1"),
        )
        new_plan = planner.build_compatibility_plan(
            new,
            new_source,
            manifest(),
            resolver=resolver,
        )
        matrix = new_plan["matrix"]["include"]
        self.assertEqual(6, len(matrix))
        self.assertEqual(
            {"26.2.1", "26.3"},
            {entry["minecraft_version"] for entry in matrix},
        )
        for target in ("26.2.1", "26.3"):
            self.assertEqual(
                set(LOADERS),
                {
                    entry["loader"]
                    for entry in matrix
                    if entry["minecraft_version"] == target
                },
            )

        for target in new_plan["targets"]:
            if target["minecraft_version"] == "26.2":
                continue
            recorder.update_published_compatibility(
                new,
                gates(target["minecraft_version"]),
                {
                    loader: {
                        "loader": loader,
                        "passed": True,
                    }
                    for loader in LOADERS
                },
                target_minecraft_version=target["minecraft_version"],
                published_hashes=HASHES["1.6.1"],
                dependency_fingerprint_value=target[
                    "dependency_fingerprint"
                ],
                resolved_config=target["resolved_config"],
                verified_on="2026-07-17",
            )

        parsed = sync.parse_release_data(new)
        self.assertEqual(
            ("26.2", "26.2.1", "26.3"),
            parsed.verified_minecraft_versions,
        )
        self.assertEqual(
            ["26.2", "26.2.1", "26.3"],
            new["desired_game_versions"],
        )
        for loader in LOADERS:
            self.assertEqual(
                MODRINTH_IDS["1.6.1"][loader],
                parsed.publication.artifacts[loader].modrinth_version_id,
            )
            self.assertEqual(
                CURSEFORGE_IDS["1.6.1"][loader],
                parsed.publication.artifacts[loader].curseforge_file_id,
            )
            self.assertEqual(
                MODRINTH_IDS["1.6.0"][loader],
                old_before_rollover["publication"]["artifacts"][loader][
                    "modrinth_version_id"
                ],
            )
            self.assertEqual(
                CURSEFORGE_IDS["1.6.0"][loader],
                old_before_rollover["publication"]["artifacts"][loader][
                    "curseforge_file_id"
                ],
            )


if __name__ == "__main__":
    unittest.main()
