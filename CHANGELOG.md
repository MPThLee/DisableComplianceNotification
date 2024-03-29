# CHANGELOG

## v1.4.2

- Package name is changed; From `ee.mpthl.mc.disable_compliance_notification` to `dev.mpthlee.minecraft.disable_compliance_notification`
- NeoForge support and version is 47.1.79
- Forge version is 47.1.3

## v1.4.1

- Minecraft 1.20.1 support

## v1.4.0

- Minecraft 1.20 support

## v1.3.0

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
- Set to Client-only mod in manifest too. (It was only for client however)
- For Fabric: Fabric API is not mandatory anymore as of this version.
- Versioning rules are changed.
    - Release version is changed to `v[mod_version]+[loader]-[minecraft_version]`.
    - Metadata version is changed to `[mod_version]`

## v1.2.2

- 1.19.4 support

## v1.2.1

- 1.19.3 support

## v1.2.0

- 1.19.2 support
- Build without architectury
- Native quilt support is dropped. use fabric version with QFAPI.

## v1.1.1

- 1.19.1 support

## v1.1.0

- 1.19 support

## v1.0.0

- 1.18.2 support