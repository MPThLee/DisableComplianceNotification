#!/usr/bin/env python3
"""
make-template.py

A script that:
  1) Takes a Minecraft version (e.g., 1.20.2) and a mod version (e.g., 2.0.0).
  2) Generates a Markdown snippet (download links, etc.).
  3) Reads an existing DOWNLOAD.md file (or another specified file).
  4) Inserts/updates the new snippet at the top of the matching major section (## 1.20.x).

Note: This version of script is made by ChatGPT due to i was too lazy

USAGE EXAMPLES:
  python make-template.py --game 1.20.2 --version 2.0.0
  python make-template.py -g 1.19.4 -v v1.3.2 --file MyOtherFile.md
"""

import argparse
import asyncio
import re


def get_major_minor(game_ver: str) -> (str, str):
    """
    Parse the given game version string into:
      - major_heading: used in the '## {major_heading}' line, e.g. "1.20.x"
      - sub_heading:   used in the '### {sub_heading}' line, e.g. "1.20.2"

    Examples:
      "1.20.2" -> major="1.20.x", sub="1.20.2"
      "1.20"   -> major="1.20.x", sub="1.20.0"  (treat missing patch as ".0")
      "1.19.4" -> major="1.19.x", sub="1.19.4"

    This ensures consistent headings in your Markdown.
    """
    parts = game_ver.split(".")
    if len(parts) == 2:
        # e.g. "1.20" => treat as "1.20.0"
        major_str = f"{parts[0]}.{parts[1]}.x"  # -> "1.20.x"
        sub_str   = f"{parts[0]}.{parts[1]}.0"  # -> "1.20.0"
    elif len(parts) >= 3:
        # e.g. "1.20.1", "1.20.2"
        major_str = f"{parts[0]}.{parts[1]}.x"
        sub_str   = game_ver
    else:
        # Fallback if only "1" or something unusual
        major_str = f"{game_ver}.x"
        sub_str   = game_ver
    return major_str, sub_str


def make_download(game_ver: str, ver: str) -> str:
    """
    Generates the sub-version Markdown content for a given game version
    (e.g. "1.20.2") and mod version (e.g. "v2.0.0").

    This is just an example of what you might generate. Adjust as needed.
    """
    # Ensure that the mod version has a leading "v"
    ver = f"v{ver}" if not ver.startswith("v") else ver

    # The GitHub build workflow name might be "mc1.20.2" for game_ver=1.20.2
    branch = f"mc{game_ver}"

    # The generated text.  Adjust as necessary for your project:
    return f"""### {game_ver}

[GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/tag/{ver}) or Modrinth.

[Nightly.link for {game_ver}](https://nightly.link/MPThLee/DisableComplianceNotification/workflows/build/{branch})

#### NeoForge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{ver}/disable_compliance_notification-{ver}+neoforge-{game_ver}.jar)

Recommended with [Cloth Config](https://modrinth.com/mod/cloth-config).

#### Fabric

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{ver}/disable_compliance_notification-{ver}+fabric-{game_ver}.jar)

Recommended with [Cloth Config](https://modrinth.com/mod/cloth-config) and [Mod Menu](https://modrinth.com/mod/modmenu).

#### Forge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/{ver}/disable_compliance_notification-{ver}+forge-{game_ver}.jar)

Recommended with [Cloth Config](https://modrinth.com/mod/cloth-config)."""


def insert_subversion_block(
        original_md: str,
        major_heading: str,
        sub_heading: str,
        new_block: str
) -> str:
    """
    Insert or update the sub_heading (e.g. "### 1.20.2") under the major_heading
    (e.g. "## 1.20.x") in original_md. The difference from simpler examples is:
    we insert new sub-versions at the TOP of the block, so the newest versions
    appear first.

    Steps:
      1) Locate the "## 1.20.x" heading (the major section).
         - If not found, create it at the end of the file and insert new_block there.
      2) Identify that section's text range.
      3) Check if "### 1.20.2" (for example) already exists.
         - If yes, replace it in place.
         - If no, insert it at the TOP, right after the "## 1.20.x" line.
      4) Reassemble the updated Markdown and return it.
    """
    # 1) Regex to find the EXACT line "## 1.20.x"
    major_heading_regex = re.compile(
        rf"^(##\s+{re.escape(major_heading)}\s*)$",
        re.MULTILINE
    )
    match_major = major_heading_regex.search(original_md)

    if not match_major:
        # If the major heading (e.g. "## 1.20.x") doesn't exist at all,
        # we append it to the end of the file, plus the new sub-block.
        insertion = f"\n\n## {major_heading}\n\n{new_block}\n"
        return original_md.rstrip() + insertion

    # 2) Identify the block from "## 1.20.x" until the next "## " (or end of file)
    major_start_index = match_major.start()
    next_major_heading_regex = re.compile(r"^##\s+", re.MULTILINE)
    match_next_major = next_major_heading_regex.search(
        original_md, pos=match_major.end()
    )
    if match_next_major:
        major_end_index = match_next_major.start()
    else:
        major_end_index = len(original_md)

    major_block = original_md[major_start_index:major_end_index]

    # 3) Regex to find if the sub-heading already exists
    #    e.g., "### 1.20.2"
    sub_heading_regex = re.compile(
        rf"(^###\s+{re.escape(sub_heading)}\s*([\s\S]*?))(?=^###\s+|^##\s+|$)",
        re.MULTILINE
    )
    existing_sub = sub_heading_regex.search(major_block)

    if existing_sub:
        # If this sub-version block is found, replace it entirely with new_block
        start_sub = existing_sub.start()
        end_sub = existing_sub.end()
        new_major_block = (
                major_block[:start_sub] + new_block + "\n" + major_block[end_sub:]
        )
    else:
        # Insert new_block at the TOP of the major section:
        # right after the heading line "## 1.20.x"
        lines = major_block.splitlines()
        if len(lines) <= 1:
            # If the major block has no content beyond "## 1.20.x"
            new_major_block = major_block.rstrip() + "\n\n" + new_block + "\n"
        else:
            # lines[0] should be "## 1.20.x"
            heading_line = lines[0]
            rest_lines   = lines[1:]  # Everything after heading
            # Rebuild so new_block is inserted right under the heading
            new_major_block = (
                    heading_line
                    + "\n\n"
                    + new_block
                    + "\n"
                    + "\n".join(rest_lines)
                    + "\n"
            )

    # Reconstruct the entire file around the modified major section
    updated_md = (
            original_md[:major_start_index]
            + new_major_block
            + original_md[major_end_index:]
    )
    return updated_md


async def main():
    """
    Main entry point. Parses command-line arguments, reads an existing markdown
    file, generates a sub-version block, and then inserts/updates that block
    in the correct place.
    """
    parser = argparse.ArgumentParser(
        prog='MakeVersionOutput',
        description='Make version output and insert it into a Markdown file.'
    )
    parser.add_argument(
        '-g', '--game',
        required=True,
        help="Minecraft version like 1.20 or 1.20.2 or 1.19.4"
    )
    parser.add_argument(
        '-v', '--version',
        required=True,
        help="Your mod version, e.g. 2.0.0 or v2.0.0"
    )
    parser.add_argument(
        '-f', '--file',
        default='DOWNLOAD.md',
        help="The Markdown file to update (default: DOWNLOAD.md)"
    )
    args = parser.parse_args()

    # 1) Generate the sub-version block text (like ### 1.20.2 plus download URLs).
    new_content = make_download(args.game, args.version)

    # 2) Compute major heading ("1.20.x") and sub-heading ("1.20.2").
    major_heading, sub_heading = get_major_minor(args.game)

    # 3) Read the existing markdown file (or create minimal content if missing).
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            original_md = f.read()
    except FileNotFoundError:
        # If the file doesn't exist, start with a minimal heading
        original_md = "# Download Links\n\n"

    # 4) Insert (or update) the new sub-version in the correct major section.
    updated_md = insert_subversion_block(
        original_md,
        major_heading,
        sub_heading,
        new_content
    )

    # 5) Write the updated markdown back to disk.
    with open(args.file, 'w', encoding='utf-8') as f:
        f.write(updated_md)


if __name__ == "__main__":
    asyncio.run(main())
