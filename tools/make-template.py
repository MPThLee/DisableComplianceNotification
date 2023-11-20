#!/usr/bin/python3

import argparse
import asyncio


async def main():
    parser = argparse.ArgumentParser(
        prog='MakeVersionOutput',
        description='Make version output')
    parser.add_argument('-g', '--game', required=True)
    parser.add_argument('-v', '--version', required=True)
    args = parser.parse_args()

    print(make_download(args.game, args.version))


def make_download(game_ver, ver):
    ver = f"v{ver}" if not ver.startswith("v") else ver
    branch = f"mc{game_ver}"
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


if __name__ == "__main__":
    asyncio.run(main())
