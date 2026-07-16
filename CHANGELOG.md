# CHANGELOG

## v1.6.0 (Latest)

- Fixed the Minecraft 26.2 build after `Minecraft#getToastManager()` was removed.
- Moved production filtering to the `SystemToast.add` boundary, avoiding the version-specific toast-manager accessor that changed between Minecraft 26.1 and 26.2.
- Restored Forge (LexForge) support with its native client configuration, alongside Fabric and NeoForge.
- Declared an open Minecraft compatibility range starting at 26.2 for all three loaders. Minecraft 26.2 is runtime-verified; later releases remain provisional until their gates pass.
- Added deterministic Fabric toast-enqueue assertions and 150-second integrated singleplayer gates for Fabric, NeoForge, and Forge.
- Added generated compliance-resource-pack fixtures, exact post-world timer checks, and cleanup/restoration checks for client gate runs.
- Added Forge build, test, artifact, release, and publishing coverage to GitHub Actions.
- Replaced scheduled Minecraft-version branch creation with repository-backed compatibility evidence and deterministic CI validation.

## v1.5.x

- Updated to Minecraft 1.21.6 (and above)
- Migrated from Cloth Config to YACL (Yet Another Config Lib) for Fabric and NeoForge
- Dropped LexForge support - Related library and its API are no longer maintained (unable to maintain further)

## v1.4.x

- Updated to match corresponding versions.
- If `-beta` appears in the version, it indicates that dependencies are in beta.

## v1.4.2

- Package name is changed; From `ee.mpthl.mc.disable_compliance_notification` to `dev.mpthlee.minecraft.disable_compliance_notification`
- NeoForge support and version is 47.1.79
- Forge version is 47.1.3

## v1.4.1

- Minecraft 1.20.1 support

## v1.4.0

- Minecraft 1.20 support

## v1.3.1 Variants

- Backported to 1.19.x versions due to incorrect build.

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
