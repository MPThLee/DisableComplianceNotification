# Disable Compliance Notification

This mod disables Compliance Notification for South Korean users.

## What is Compliance Notification?

As there's some Korean Gaming Laws, Game should notify play time to user each hour if it's online(able) game.\
Bedrock edition already implemented this with Xbox Notification(All platform except Playstation) and Playstation
Console-wide Notification.\
As of 1.18.2, Mojang decided to implemented this on Java Edition with own implementation.

![example](https://static.wikia.nocookie.net/minecraft_gamepedia/images/a/ac/Regional_compliancies_notification_1_hour.png)

> - Added gameplay timers and notices in compliance with gaming laws of South Korea to South Korean users, in order to

    remind these players to take occasional breaks from gameplay.

Image and quote reference: https://minecraft.wiki/w/Java_Edition_1.18.2#General

## Changelog

Older changelog is available on [CHANGELOG.md](./CHANGELOG.md).

### v1.6.0 (Minecraft 26.2+)

- Fixed the Minecraft 26.2 build after the client toast-manager API changed.
- Restored Forge (LexForge) with a native Forge client config.
- Moved filtering to the unobfuscated `SystemToast.add` API so the same artifact can remain usable on later Minecraft releases while that API stays compatible.
- Added deterministic toast assertions and 150-second in-world compliance gates for Fabric, NeoForge, and Forge.
- Replaced automatic Minecraft-version branch creation with repository-backed compatibility data and tests.

### v1.5.6+

- Updated to Minecraft 26.1 (and above)

## Platform Support

| Platform             | Status                       | Config GUI                     | Notes                                                                                                   |
| -------------------- | ---------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **Fabric**           | :white_check_mark: Supported | :white_check_mark: YACL        | Recommended with [YACL](https://modrinth.com/mod/yacl) and [Mod Menu](https://modrinth.com/mod/modmenu) |
| **NeoForge**         | :white_check_mark: Supported | :white_check_mark: YACL        | Recommended with [YACL](https://modrinth.com/mod/yacl)                                                  |
| **Forge (LexForge)** | :white_check_mark: Supported | :white_check_mark: ForgeConfig | Uses Forge's built-in client config; restored for Minecraft 26.2+                                      |

The v1.6.0 artifacts are built and runtime-tested on Minecraft 26.2. Their loader metadata accepts 26.2 and later, so the same artifacts may remain usable on 26.3, 27.x, and later releases while the intercepted toast API stays compatible. Later versions are not considered verified until all three loader gates pass and the result is recorded in [`data/minecraft-compatibility.json`](./data/minecraft-compatibility.json).

## Download

- [Modrinth](https://modrinth.com/mod/disable-compliance-notification)
- [GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/)

Older releases links are on [DOWNLOAD.md](./DOWNLOAD.md).

### Latest (v1.6.0 for Minecraft 26.2)

[GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/tag/v1.6.0) or Modrinth.

[Nightly.link for 26.2](https://nightly.link/MPThLee/DisableComplianceNotification/workflows/build/mc26.2)

#### Fabric

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.6.0/disable_compliance_notification-v1.6.0+fabric-26.2.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl) and [Mod Menu](https://modrinth.com/mod/modmenu).

#### NeoForge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.6.0/disable_compliance_notification-v1.6.0+neoforge-26.2.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl).

#### Forge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.6.0/disable_compliance_notification-v1.6.0+forge-26.2.jar)

Uses Forge's built-in client config.
