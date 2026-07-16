#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


INITIALIZED_MARKER = (
    "Initializing Disable Compliance Notification... [Locale ISO3 Country: KOR]"
)
RESOURCE_PACK_RELOAD_MARKER = "Reloading ResourceManager:"
INTEGRATED_SERVER_MARKER = "Starting integrated minecraft server version"
PLAYER_JOINED_MARKER = " joined the game"
WORLD_JOINED_MARKER = "DCN compliance gate entered world:"
WORLD_START_FAILED_MARKER = "DCN compliance gate failed to enter a singleplayer world"
PERIODIC_TOAST_OBSERVED_MARKER = (
    "DCN compliance gate observed a periodic toast in ToastManager"
)
NO_PERIODIC_TOAST_MARKER = (
    "DCN compliance gate verified no periodic toast was present in ToastManager"
)
FILTERED_NOTIFICATION_MARKERS = {
    "hourly": (
        "title='compliance.playtime.hours', "
        "message='compliance.playtime.message') "
        "[DCN-MODE: ONLY_COMPLIANCE, Filtered: true]"
    ),
    "delayed": (
        "title='compliance.playtime.greaterThan24Hours', "
        "message='compliance.playtime.message') "
        "[DCN-MODE: ONLY_COMPLIANCE, Filtered: true]"
    ),
}
FILTERED_NOTIFICATION_TRANSLATION_KEYS = {
    "hourly": "compliance.playtime.hours",
    "delayed": "compliance.playtime.greaterThan24Hours",
}
MINIMUM_GATE_RUNTIME_SECONDS = 120
DEFAULT_GATE_RUNTIME_SECONDS = 150
DEFAULT_STARTUP_TIMEOUT_SECONDS = 300
TOAST_EVIDENCE_GRACE_SECONDS = 10
GATE_PACK_FILENAME = "dcn-compliance-gate.zip"
GATE_PACK_ID = f"file/{GATE_PACK_FILENAME}"
GATE_RESULT_FILENAME = "client-gate-result.json"


def read_properties(path: Path) -> dict[str, str]:
    properties: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            properties[key] = value
    return properties


def pack_metadata(pack_format: str) -> dict[str, object]:
    parts = [int(part) for part in pack_format.split(".")]
    major = parts[0]
    minor = parts[1] if len(parts) > 1 else 0
    return {
        "pack": {
            "description": "DCN compliance gate (1 minute period, 2 minute delay)",
            "min_format": [major, minor],
            "max_format": major,
        }
    }


def _read_option_array(lines: list[str], key: str) -> list[str]:
    prefix = f"{key}:"
    for line in lines:
        if line.startswith(prefix):
            value = json.loads(line[len(prefix) :])
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(f"{key} must be a JSON string array")
            return value
    return []


def _replace_option(lines: list[str], key: str, value: list[str]) -> list[str]:
    rendered = f"{key}:{json.dumps(value, separators=(',', ':'))}"
    prefix = f"{key}:"
    replaced = False
    result: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            if not replaced:
                result.append(rendered)
                replaced = True
        else:
            result.append(line)
    if not replaced:
        result.append(rendered)
    return result


def enable_gate_pack(options_text: str) -> str:
    lines = options_text.splitlines()
    resource_packs = [
        pack for pack in _read_option_array(lines, "resourcePacks") if pack != GATE_PACK_ID
    ]
    resource_packs.append(GATE_PACK_ID)
    incompatible = [
        pack
        for pack in _read_option_array(lines, "incompatibleResourcePacks")
        if pack != GATE_PACK_ID
    ]
    lines = _replace_option(lines, "resourcePacks", resource_packs)
    lines = _replace_option(lines, "incompatibleResourcePacks", incompatible)
    return "\n".join(lines) + "\n"


def create_gate_pack(project_root: Path, destination: Path) -> None:
    properties = read_properties(project_root / "config.properties")
    fixture = (
        project_root
        / "tools/test/fixtures/compliance_gate/regional_compliancies.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "pack.mcmeta",
            json.dumps(pack_metadata(properties["pack_format"]), indent=2) + "\n",
        )
        archive.write(
            fixture,
            "assets/minecraft/regional_compliancies.json",
        )
    temporary.replace(destination)


def remove_generated_world(
    world_path: Path,
    stable_absence_seconds: float = 2.0,
    timeout_seconds: float = 15.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    absent_since: float | None = None
    while time.monotonic() < deadline:
        if world_path.exists():
            shutil.rmtree(world_path)
            absent_since = None
        elif absent_since is None:
            absent_since = time.monotonic()
        elif time.monotonic() - absent_since >= stable_absence_seconds:
            return
        time.sleep(0.05)
    raise RuntimeError(f"generated gate world kept reappearing: {world_path}")


@contextmanager
def prepared_gate_workspace(
    project_root: Path, loader_dir: Path, world_name: str
) -> Iterator[None]:
    game_dir = loader_dir / "run"
    options_path = game_dir / "options.txt"
    pack_path = game_dir / "resourcepacks" / GATE_PACK_FILENAME
    original_options = options_path.read_bytes() if options_path.exists() else None
    original_pack = pack_path.read_bytes() if pack_path.exists() else None
    config_paths = (
        game_dir / "config/disable_compliance_notification.json5",
        game_dir / "config/disable_compliance_notification-client.toml",
    )
    original_configs = {
        path: path.read_bytes() if path.exists() else None for path in config_paths
    }
    world_path = game_dir / "saves" / world_name
    if world_path.exists():
        raise RuntimeError(f"refusing to replace existing gate world: {world_path}")

    game_dir.mkdir(parents=True, exist_ok=True)
    options_text = (
        original_options.decode("utf-8") if original_options is not None else ""
    )
    options_path.write_text(enable_gate_pack(options_text), encoding="utf-8")
    create_gate_pack(project_root, pack_path)
    for config_path in config_paths:
        config_path.unlink(missing_ok=True)

    try:
        yield
    finally:
        if original_options is None:
            options_path.unlink(missing_ok=True)
        else:
            options_path.write_bytes(original_options)

        if original_pack is None:
            pack_path.unlink(missing_ok=True)
        else:
            pack_path.write_bytes(original_pack)

        for config_path, original_config in original_configs.items():
            if original_config is None:
                config_path.unlink(missing_ok=True)
            else:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_bytes(original_config)
        remove_generated_world(world_path)


@dataclass
class GateState:
    initialized_at: float | None = None
    resource_pack_loaded: bool = False
    integrated_server_started: bool = False
    player_joined: bool = False
    world_joined_at: float | None = None
    world_start_failed: bool = False
    periodic_toast_observed: bool = False
    no_periodic_toast_verified: bool = False
    filtered_notifications: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, line: str, observed_at: float | None = None) -> bool:
        now = time.monotonic() if observed_at is None else observed_at
        milestone = False
        with self.lock:
            if self.initialized_at is None and INITIALIZED_MARKER in line:
                self.initialized_at = now
                milestone = True
            if (
                not self.resource_pack_loaded
                and RESOURCE_PACK_RELOAD_MARKER in line
                and GATE_PACK_ID in line
            ):
                self.resource_pack_loaded = True
                milestone = True
            if not self.integrated_server_started and INTEGRATED_SERVER_MARKER in line:
                self.integrated_server_started = True
                milestone = True
            if not self.player_joined and PLAYER_JOINED_MARKER in line:
                self.player_joined = True
                milestone = True
            if self.world_joined_at is None and WORLD_JOINED_MARKER in line:
                self.world_joined_at = now
                milestone = True
            if not self.world_start_failed and WORLD_START_FAILED_MARKER in line:
                self.world_start_failed = True
                milestone = True
            if (
                not self.periodic_toast_observed
                and PERIODIC_TOAST_OBSERVED_MARKER in line
            ):
                self.periodic_toast_observed = True
                milestone = True
            if (
                not self.no_periodic_toast_verified
                and NO_PERIODIC_TOAST_MARKER in line
            ):
                self.no_periodic_toast_verified = True
                milestone = True
            if self.world_joined_at is not None:
                for name, marker in FILTERED_NOTIFICATION_MARKERS.items():
                    if marker in line and name not in self.filtered_notifications:
                        self.filtered_notifications.add(name)
                        milestone = True
        return milestone

    def snapshot(
        self,
    ) -> tuple[
        float | None,
        bool,
        bool,
        bool,
        float | None,
        bool,
        bool,
        bool,
        set[str],
    ]:
        with self.lock:
            return (
                self.initialized_at,
                self.resource_pack_loaded,
                self.integrated_server_started,
                self.player_joined,
                self.world_joined_at,
                self.world_start_failed,
                self.periodic_toast_observed,
                self.no_periodic_toast_verified,
                set(self.filtered_notifications),
            )


def _process_groups_from_table(root_pid: int, process_table: str) -> set[int]:
    processes: dict[int, tuple[int, int]] = {}
    for line in process_table.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            pid, parent_pid, process_group_id = (int(field) for field in fields)
        except ValueError:
            continue
        processes[pid] = (parent_pid, process_group_id)

    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (parent_pid, _) in processes.items():
            if parent_pid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return {
        process_group_id
        for pid, (_, process_group_id) in processes.items()
        if pid in descendants and process_group_id > 0
    } | {root_pid}


def _descendant_process_groups(root_pid: int) -> set[int]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,pgid="],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return {root_pid}
    return _process_groups_from_table(root_pid, result.stdout)


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    process_group_ids = _descendant_process_groups(process.pid)

    def group_exists(process_group_id: int) -> bool:
        process.poll()
        try:
            os.killpg(process_group_id, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    for sent_signal, timeout in (
        (signal.SIGINT, 10),
        (signal.SIGTERM, 5),
        (signal.SIGKILL, 5),
    ):
        process_group_ids.update(_descendant_process_groups(process.pid))
        active_groups = {
            process_group_id
            for process_group_id in process_group_ids
            if group_exists(process_group_id)
        }
        if not active_groups:
            break
        for process_group_id in sorted(active_groups, reverse=True):
            try:
                os.killpg(process_group_id, sent_signal)
            except ProcessLookupError:
                continue
        deadline = time.monotonic() + timeout
        while (
            any(group_exists(group_id) for group_id in active_groups)
            and time.monotonic() < deadline
        ):
            time.sleep(0.1)

    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def _tail(path: Path, line_count: int = 40) -> str:
    if not path.exists():
        return ""
    return "".join(path.read_text(encoding="utf-8", errors="replace").splitlines(True)[-line_count:])


def write_gate_result(
    path: Path,
    loader: str,
    minecraft_version: str,
    requested_runtime_seconds: int,
    observed_runtime_seconds: float,
    filtered: set[str],
    periodic_toast_absent: bool,
) -> dict[str, object]:
    result = {
        "schema_version": 1,
        "loader": loader,
        "minecraft_version": minecraft_version,
        "minimum_in_world_seconds": MINIMUM_GATE_RUNTIME_SECONDS,
        "requested_in_world_seconds": requested_runtime_seconds,
        "observed_in_world_seconds": round(observed_runtime_seconds, 1),
        "filtered_notifications": sorted(
            FILTERED_NOTIFICATION_TRANSLATION_KEYS[name] for name in filtered
        ),
        "periodic_toast_absent": periodic_toast_absent,
        "passed": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return result


def run_gate(
    project_root: Path,
    loader: str,
    runtime_seconds: int,
    startup_timeout_seconds: int,
    use_xvfb: bool,
) -> dict[str, object]:
    if runtime_seconds < MINIMUM_GATE_RUNTIME_SECONDS:
        raise ValueError(
            f"runtime must be at least {MINIMUM_GATE_RUNTIME_SECONDS} seconds"
        )

    loader_dir = project_root / loader
    if not (loader_dir / "gradlew").is_file():
        raise ValueError(f"loader Gradle wrapper not found: {loader_dir / 'gradlew'}")
    if use_xvfb and shutil.which("xvfb-run") is None:
        raise ValueError("--xvfb requested, but xvfb-run is unavailable")

    command = ["./gradlew", "runClient", "--console=plain"]
    if use_xvfb:
        command = ["xvfb-run", "-a", *command]

    output_path = loader_dir / "build/client-gate.log"
    result_path = loader_dir / "build" / GATE_RESULT_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    result_path.unlink(missing_ok=True)
    environment = os.environ.copy()
    java_options = environment.get("_JAVA_OPTIONS", "")
    required_options = ("-Duser.country=KR", "-Duser.language=ko")
    for option in required_options:
        if option not in java_options:
            java_options = f"{java_options} {option}".strip()
    environment["_JAVA_OPTIONS"] = java_options
    world_name = f"dcn_compliance_gate_{os.getpid()}_{int(time.time())}"
    environment["_JAVA_OPTIONS"] = (
        f"{environment['_JAVA_OPTIONS']} -Ddcn.client.gate=true "
        f"-Ddcn.client.gate.worldName={world_name} "
        f"-Ddcn.client.gate.runtimeSeconds={runtime_seconds}"
    )

    state = GateState()
    process: subprocess.Popen[str] | None = None
    reader: threading.Thread | None = None
    started_at = time.monotonic()

    print(
        f"Starting {loader} compliance gate: {runtime_seconds}s inside a singleplayer world; "
        f"log={output_path.relative_to(project_root)}",
        flush=True,
    )

    with prepared_gate_workspace(project_root, loader_dir, world_name):
        try:
            with output_path.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    command,
                    cwd=loader_dir,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
                assert process.stdout is not None

                def copy_output() -> None:
                    assert process is not None and process.stdout is not None
                    for line in process.stdout:
                        output.write(line)
                        output.flush()
                        if state.observe(line):
                            print(line.rstrip(), flush=True)

                reader = threading.Thread(target=copy_output, daemon=True)
                reader.start()
                next_status_at = time.monotonic() + 30
                failure: str | None = None

                while True:
                    now = time.monotonic()
                    (
                        initialized_at,
                        resource_pack_loaded,
                        integrated_server_started,
                        player_joined,
                        world_joined_at,
                        world_start_failed,
                        periodic_toast_observed,
                        no_periodic_toast_verified,
                        filtered,
                    ) = state.snapshot()
                    return_code = process.poll()
                    if return_code is not None:
                        failure = (
                            f"client exited with code {return_code} before the gate completed"
                        )
                        break
                    if world_start_failed:
                        failure = "dev bootstrap failed to enter a singleplayer world"
                        break
                    if periodic_toast_observed:
                        failure = "ToastManager contained a periodic toast after world entry"
                        break
                    if world_joined_at is None:
                        if now - started_at >= startup_timeout_seconds:
                            if initialized_at is None:
                                failure = (
                                    "mod did not initialize within "
                                    f"{startup_timeout_seconds} seconds"
                                )
                            else:
                                failure = (
                                    "client did not enter a singleplayer world within "
                                    f"{startup_timeout_seconds} seconds"
                                )
                            break
                    else:
                        world_runtime = now - world_joined_at
                        toast_evidence_timed_out = (
                            world_runtime
                            >= runtime_seconds + TOAST_EVIDENCE_GRACE_SECONDS
                        )
                        if world_runtime >= runtime_seconds and (
                            no_periodic_toast_verified or toast_evidence_timed_out
                        ):
                            missing = set(FILTERED_NOTIFICATION_MARKERS) - filtered
                            if initialized_at is None:
                                failure = "exact KOR mod-initialization marker was not observed"
                            elif not resource_pack_loaded:
                                failure = "generated compliance resource pack was not loaded"
                            elif not integrated_server_started:
                                failure = "integrated server start was not observed"
                            elif not player_joined:
                                failure = "player join was not observed"
                            elif not no_periodic_toast_verified:
                                failure = (
                                    "independent ToastManager absence marker was not observed"
                                )
                            elif missing:
                                failure = "missing filtered notifications: " + ", ".join(
                                    sorted(missing)
                                )
                            break

                    if now >= next_status_at:
                        runtime = 0 if world_joined_at is None else int(now - world_joined_at)
                        print(
                            f"{loader} gate status: initialized={initialized_at is not None}, "
                            f"pack_loaded={resource_pack_loaded}, "
                            f"server_started={integrated_server_started}, "
                            f"player_joined={player_joined}, "
                            f"world_joined={world_joined_at is not None}, "
                            f"toast_absent={no_periodic_toast_verified}, "
                            f"runtime={runtime}/{runtime_seconds}s, "
                            f"filtered={len(filtered)}/{len(FILTERED_NOTIFICATION_MARKERS)}",
                            flush=True,
                        )
                        next_status_at = now + 30
                    time.sleep(0.25)

                _terminate_process_group(process)
                reader.join(timeout=10)

                (
                    initialized_at,
                    resource_pack_loaded,
                    integrated_server_started,
                    player_joined,
                    world_joined_at,
                    world_start_failed,
                    periodic_toast_observed,
                    no_periodic_toast_verified,
                    filtered,
                ) = state.snapshot()
                world_runtime = (
                    0 if world_joined_at is None else time.monotonic() - world_joined_at
                )
                if failure is not None:
                    raise RuntimeError(
                        f"{loader} compliance gate failed: {failure}\n"
                        f"Last log lines:\n{_tail(output_path)}"
                    )
                print(
                    f"{loader} compliance gate passed after {world_runtime:.1f}s in-world: "
                    f"filtered {', '.join(sorted(filtered))}",
                    flush=True,
                )
                properties = read_properties(project_root / "config.properties")
                return write_gate_result(
                    result_path,
                    loader,
                    properties["minecraft_version"],
                    runtime_seconds,
                    world_runtime,
                    filtered,
                    no_periodic_toast_verified and not periodic_toast_observed,
                )
        finally:
            if process is not None:
                _terminate_process_group(process)
            if reader is not None:
                reader.join(timeout=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Minecraft client long enough to verify both real compliance "
            "notifications are filtered."
        )
    )
    parser.add_argument("loader", choices=("fabric", "neoforge", "forge"))
    parser.add_argument(
        "--project-root",
        type=Path,
        help=(
            "repository checkout containing config.properties and loader directories "
            "(defaults to this script's repository)"
        ),
    )
    parser.add_argument(
        "--runtime-seconds",
        type=int,
        default=DEFAULT_GATE_RUNTIME_SECONDS,
        help=(
            "seconds to keep the client running after entering a singleplayer world "
            f"(default: {DEFAULT_GATE_RUNTIME_SECONDS}, minimum: "
            f"{MINIMUM_GATE_RUNTIME_SECONDS})"
        ),
    )
    parser.add_argument(
        "--startup-timeout-seconds",
        type=int,
        default=DEFAULT_STARTUP_TIMEOUT_SECONDS,
        help="maximum seconds allowed for Gradle and Minecraft startup",
    )
    parser.add_argument(
        "--xvfb",
        action="store_true",
        help="launch the client through xvfb-run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    project_root = (
        args.project_root.resolve()
        if args.project_root is not None
        else Path(__file__).resolve().parents[2]
    )
    try:
        run_gate(
            project_root,
            args.loader,
            args.runtime_seconds,
            args.startup_timeout_seconds,
            args.xvfb,
        )
    except KeyboardInterrupt:
        print("client compliance gate interrupted", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exception:
        print(exception, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
