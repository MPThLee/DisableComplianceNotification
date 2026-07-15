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

### Unreleased (Minecraft 26.2+)

- Restored Forge (LexForge) with a native Forge client config.
- Moved filtering to the unobfuscated `SystemToast.add` API so the same artifact can remain usable on later Minecraft releases while that API stays compatible.

### v1.5.6+

- Updated to Minecraft 26.1 (and above)

## Platform Support

| Platform             | Status                       | Config GUI                     | Notes                                                                                                   |
| -------------------- | ---------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------- |
| **Fabric**           | :white_check_mark: Supported | :white_check_mark: YACL        | Recommended with [YACL](https://modrinth.com/mod/yacl) and [Mod Menu](https://modrinth.com/mod/modmenu) |
| **NeoForge**         | :white_check_mark: Supported | :white_check_mark: YACL        | Recommended with [YACL](https://modrinth.com/mod/yacl)                                                  |
| **Forge (LexForge)** | :white_check_mark: Supported | :white_check_mark: ForgeConfig | Uses Forge's built-in client config; restored for Minecraft 26.2+                                      |

Minecraft metadata accepts 26.2 and later. The production mixin avoids the version-specific internals that changed between 26.1 and 26.2, but a future Minecraft release can still require a new build if Mojang changes the intercepted toast API.

## Download

- [Modrinth](https://modrinth.com/mod/disable-compliance-notification)
- [GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/)

Older releases links are on [DOWNLOAD.md](./DOWNLOAD.md).

### Latest (v1.5.9 for Minecraft 26.2)

[GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/tag/v1.5.9) or Modrinth.

[Nightly.link for 26.2](https://nightly.link/MPThLee/DisableComplianceNotification/workflows/build/mc26.2)

#### Fabric

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.5.9/disable_compliance_notification-v1.5.9+fabric-26.2.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl) and [Mod Menu](https://modrinth.com/mod/modmenu).

#### NeoForge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.5.9/disable_compliance_notification-v1.5.9+neoforge-26.2.jar)

Recommended with [YACL](https://modrinth.com/mod/yacl).
