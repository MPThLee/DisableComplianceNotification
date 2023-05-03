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

Image and quote reference: https://minecraft.fandom.com/wiki/Java_Edition_1.18.2#General

## Changelog

Older changelog is available on [CHANGELOG.md](./CHANGELOG.md).

### v1.3.0 (Latest)

- Handle periodic notification correctly.
    - As of previous version, It will reject **ALL** notifications whatever it is.
        - It's fixed by following Mojang's implementation with some additional if expression.
        - Note: Some mod uses Minecraft's Periodic Notification. This will mitigate the issues.
- Add support for filter message selection.
    - Filter all notification
    - Filter Compliance notification only
    - Filter Non-Compliance notification only
    - Disable filter
- Configuration support (for filter message.)
    - Requires [Cloth Config](https://modrinth.com/mod/cloth-config). But it's optional.
        - Additionally, Fabric build also has optional dependency for [Mod Menu](https://modrinth.com/mod/modmenu)
    - Default (and without Cloth Config) is "Filter only compliance notification".
- For Fabric: Fabric API is not mandatory as of this version.
- Versioning rules are changed.
    - Release version is changed to `v[mod_version]+[loader]-[minecraft_version]`.
    - Metadata version is changed to `[mod_version]`

## Download

- [Modrinth](https://modrinth.com/mod/disable-compliance-notification)
- [GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/)

- [CurseForge](https://www.curseforge.com/minecraft/mc-mods/disable-compliance-notification)
    - Page exist but some of versions are not approved by moderator. Download this from Modrinth or GitHub Release.

Older releases links are on [DOWNLOAD.md](./DOWNLOAD.md).

### Latest (v1.3.0 for Minecraft 1.19.4)

[GitHub Release](https://github.com/MPThLee/DisableComplianceNotification/releases/tag/v1.3.0) or Modrinth.

[Nightly.link for 1.19.4](https://nightly.link/MPThLee/DisableComplianceNotification/workflows/build/mc1.19.4)

#### Forge

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.3.0/disable_compliance_notification-v1.3.0+forge-1.19.4.jar)

Recommended with [Cloth Config](https://modrinth.com/mod/cloth-config).

#### Fabric

[Download Directly via GitHub](https://github.com/MPThLee/DisableComplianceNotification/releases/download/v1.3.0/disable_compliance_notification-v1.3.0+fabric-1.19.4.jar)

Recommended with [Cloth Config](https://modrinth.com/mod/cloth-config) and [Mod Menu](https://modrinth.com/mod/modmenu).
