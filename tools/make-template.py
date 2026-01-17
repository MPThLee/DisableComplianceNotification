#!/usr/bin/env python3
"""
make-template.py

A script that:
  1) Takes a Minecraft version (e.g., 1.20.2) and a mod version (e.g., 2.0.0).
  2) Generates a Markdown snippet (download links, etc.).
  3) Reads an existing DOWNLOAD.md file (or another specified file).
  4) Inserts/updates the new snippet at the top of the matching major section (## 1.20.x).
  5) Also updates the new snippet in README.md

Note: This version of script is made by ChatGPT due to i was too lazy

USAGE EXAMPLES:
  python make-template.py --game 1.20.2 --version 2.0.0
  python make-template.py -g 1.19.4 -v v1.3.2 --download-file MyDownloads.md --readme-file MyReadme.md
"""

import argparse
import asyncio
import re
import os

# --------------------------------------------------------------
# 1) Common Helpers
# --------------------------------------------------------------


def read_file_or_default(path: str, default_text: str) -> str:
    """
    Reads 'path' if it exists, otherwise returns 'default_text'.
    """
    if not os.path.exists(path):
        return default_text
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str):
    """
    Overwrites 'path' with 'content'.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def ensure_leading_v(mod_ver: str) -> str:
    """
    Ensures the mod version has a leading 'v'.
    If it's already 'v1.4.6', we keep it.
    If it's '1.4.6', we change it to 'v1.4.6'.
    """
    return mod_ver if mod_ver.startswith("v") else f"v{mod_ver}"


# --------------------------------------------------------------
# 2) Updating DOWNLOAD.md
# --------------------------------------------------------------


def parse_major_minor(game_ver: str) -> tuple[str, str]:
    """
    Determines:
      - major_heading: e.g. '1.20.x' from '1.20.4'
      - sub_heading:   e.g. '1.20.4'
    If someone gives '1.20', treat as '1.20.0'.
    """
    parts = game_ver.split(".")
    if len(parts) == 2:  # e.g. '1.20'
        major = f"{parts[0]}.{parts[1]}.x"  # -> '1.20.x'
        sub = f"{parts[0]}.{parts[1]}.0"  # -> '1.20.0'
    elif len(parts) >= 3:  # e.g. '1.20.4'
        major = f"{parts[0]}.{parts[1]}.x"
        sub = game_ver
    else:
        # fallback if user typed '1'
        major = f"{game_ver}.x"
        sub = game_ver
    return major, sub


def build_download_block(game_ver: str, mod_ver: str) -> str:
    """
    Returns a Markdown snippet for DOWNLOAD.md, starting with '### {game_ver}'.
    """
    mod_ver = ensure_leading_v(mod_ver)
    branch = f"mc{game_ver}"

    return f"""### {game_ver}

[GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/tag/{mod_ver}) or Modrinth.

[Nightly.link for {game_ver}](https://nightly.link/MPThLee/DisableComplianceNotification/workflows/build/{branch})

#### Fabric

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{mod_ver}/disable_compliance_notification-{mod_ver}+fabric-{game_ver}.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl) and [Mod Menu](https://modrinth.com/mod/modmenu).

#### NeoForge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{mod_ver}/disable_compliance_notification-{mod_ver}+neoforge-{game_ver}.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl)."""


def insert_version_in_download(
    original_md: str, major_h: str, sub_h: str, new_block: str
) -> str:
    """
    Insert/replace '### sub_h' under '## major_h' at the TOP of that block.

    Steps:
      1) Look for '## major_h'. If not found, create it at end of file.
      2) Inside that block, see if '### sub_h' exists -> if yes, replace.
      3) If no, prepend new_block right after '## major_h'.
    """

    # Regex to find exactly "## 1.20.x" line
    pattern_major = re.compile(rf"^(##\s+{re.escape(major_h)}\s*)$", re.MULTILINE)
    match_major = pattern_major.search(original_md)

    if not match_major:
        # No major heading => append at end
        return original_md.rstrip() + f"\n\n## {major_h}\n\n{new_block}\n"

    major_start = match_major.start()
    # find next '## ' or end of file
    pattern_next_major = re.compile(r"^##\s+", re.MULTILINE)
    match_next = pattern_next_major.search(original_md, pos=match_major.end())
    major_end = match_next.start() if match_next else len(original_md)

    major_block = original_md[major_start:major_end]

    # Check if sub_h block exists
    pattern_sub = re.compile(
        rf"(^###\s+{re.escape(sub_h)}\s*([\s\S]*?))(?=^###\s+|^##\s+|$)", re.MULTILINE
    )
    m_sub = pattern_sub.search(major_block)

    if m_sub:
        # Replace existing sub-block
        start_sub, end_sub = m_sub.span()
        new_major_block = (
            major_block[:start_sub] + new_block + "\n" + major_block[end_sub:]
        )
    else:
        # Insert at top (just after "## 1.20.x" line)
        lines = major_block.splitlines()
        if len(lines) <= 1:
            # There's nothing but the heading line
            new_major_block = major_block.rstrip() + "\n\n" + new_block + "\n"
        else:
            heading_line = lines[0]
            rest_lines = lines[1:]
            new_major_block = (
                heading_line + "\n\n" + new_block + "\n" + "\n".join(rest_lines) + "\n"
            )

    updated_md = original_md[:major_start] + new_major_block + original_md[major_end:]
    return updated_md


# --------------------------------------------------------------
# 3) Updating README.md
# --------------------------------------------------------------


def build_latest_block(game_ver: str, mod_ver: str) -> str:
    """
    Builds a snippet for the README's '### Latest (...)' block.
    Typically simpler or slightly different from DOWNLOAD.md.
    """
    mod_ver = ensure_leading_v(mod_ver)
    return f"""### Latest ({mod_ver} for Minecraft {game_ver})

[GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/tag/{mod_ver}) or Modrinth.

[Nightly.link for {game_ver}](https://nightly.link/MPThLee/DisableComplianceNotification/workflows/build/mc{game_ver})

#### Fabric

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{mod_ver}/disable_compliance_notification-{mod_ver}+fabric-{game_ver}.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl) and [Mod Menu](https://modrinth.com/mod/modmenu).

#### NeoForge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{mod_ver}/disable_compliance_notification-{mod_ver}+neoforge-{game_ver}.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl).
"""


def replace_latest_in_readme(original_md: str, new_block: str) -> str:
    """
    Replaces everything from:
      ### Latest (v... for Minecraft ...)
    up to the next heading or EOF, with new_block.
    If not found, appends at the end.
    """
    pattern = re.compile(
        r"(?P<block>"
        r"^###\s+Latest\s*\(.*?\)"  # line begins with '### Latest ('
        r"(?:[\r\n]+.*?)"  # consume lines
        r"(?=^#{1,6}\s+|\Z)"  # until next heading or end
        r")",
        re.MULTILINE | re.DOTALL,
    )

    m = pattern.search(original_md)
    if not m:
        return original_md.rstrip() + "\n\n" + new_block + "\n"

    start, end = m.span("block")
    return original_md[:start] + new_block + "\n" + original_md[end:]


# --------------------------------------------------------------
# 4) Main
# --------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(
        description="Updates DOWNLOAD.md and README.md for a new release."
    )
    parser.add_argument(
        "-g", "--game", required=True, help="Minecraft version (e.g. 1.20.4)"
    )
    parser.add_argument(
        "-v", "--version", required=True, help="Mod version (e.g. 1.4.6 or v1.4.6)"
    )
    parser.add_argument(
        "--download-file",
        default="DOWNLOAD.md",
        help="Path to DOWNLOAD.md (default: DOWNLOAD.md)",
    )
    parser.add_argument(
        "--readme-file",
        default="README.md",
        help="Path to README.md (default: README.md)",
    )
    args = parser.parse_args()

    # 1) Build the block for DOWNLOAD.md
    major_h, sub_h = parse_major_minor(args.game)
    download_block = build_download_block(args.game, args.version)

    # 2) Read or init DOWNLOAD.md, update, write back
    original_download = read_file_or_default(args.download_file, "# Download Links\n\n")
    updated_download = insert_version_in_download(
        original_md=original_download,
        major_h=major_h,
        sub_h=sub_h,
        new_block=download_block,
    )
    write_file(args.download_file, updated_download)

    # 3) Build the "Latest" snippet for README
    latest_block = build_latest_block(args.game, args.version)

    # 4) Read or init README.md, update, write back
    original_readme = read_file_or_default(args.readme_file, "# README\n\n")
    updated_readme = replace_latest_in_readme(original_readme, latest_block)
    write_file(args.readme_file, updated_readme)


if __name__ == "__main__":
    asyncio.run(main())
