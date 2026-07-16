#!/usr/bin/env python3
"""Create a dependency-aware runtime-test plan for a published release."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from compatibility_plan import (
    CompatibilityPlanError,
    DependencyResolver,
    build_compatibility_plan,
    load_manifest,
    load_publication,
    load_source_config,
    write_plan_bundle,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description=(
            "Plan every missing or stale loader gate from a publication's "
            "Minecraft build version through Mojang's latest release."
        )
    )
    parser.add_argument(
        "--publication-data",
        type=Path,
        default=project_root / "data/published-release.json",
        help="immutable published-release binding",
    )
    parser.add_argument(
        "--source-config",
        type=Path,
        default=project_root / "config.properties",
        help="config.properties used by the published release",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        help="use a Mojang manifest fixture instead of the network",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "build/compatibility-plan",
        help="directory for plan.json and per-target files",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="write matrix, has_work, and plan_path outputs to this file",
    )
    parser.add_argument("--timeout", type=float, default=30)
    return parser.parse_args(argv)


def write_github_outputs(path: Path, plan: dict[str, object], plan_path: Path) -> None:
    matrix = json.dumps(plan["matrix"], sort_keys=True, separators=(",", ":"))
    lines = [
        f"matrix={matrix}",
        f"has_work={'true' if plan['has_work'] else 'false'}",
        f"plan_path={plan_path.as_posix()}",
        f"publication={plan['publication_id']}",
        f"source_commit={plan['source_commit']}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def main(
    argv: list[str] | None = None,
    *,
    resolver: DependencyResolver | None = None,
) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    github_output = args.github_output
    if github_output is None and os.environ.get("GITHUB_OUTPUT"):
        github_output = Path(os.environ["GITHUB_OUTPUT"])

    try:
        publication_data = load_publication(args.publication_data)
        source = load_source_config(args.source_config)
        manifest = load_manifest(args.manifest_file, timeout=args.timeout)
        keyword_arguments: dict[str, object] = {"timeout": args.timeout}
        if resolver is not None:
            keyword_arguments["resolver"] = resolver
        plan = build_compatibility_plan(
            publication_data,
            source,
            manifest,
            **keyword_arguments,
        )
        plan_path = write_plan_bundle(plan, source, args.output_dir)
        if github_output is not None:
            write_github_outputs(github_output, plan, plan_path)
    except (CompatibilityPlanError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(plan["matrix"], sort_keys=True, separators=(",", ":")))
    if not plan["has_work"]:
        print("Published compatibility evidence is current.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
