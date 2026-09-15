# Compatibility

Automated checks of unchanged published jars. Mod **1.6.0+** only.

Last updated: 2026-09-15 04:33:18 UTC

| Mark | Meaning |
| :---: | --- |
| ✅ | All applicable checks pass |
| ⚠️ | Core passes; optional dependencies are not verified working |
| ❌ | Core runtime check failed |
| — | Not tested, unavailable, or incomplete |

Core checks run in-world for at least **150 seconds**. Stable Fabric also checks **Mod Menu + YACL**; NeoForge checks **YACL**. Forge uses its built-in config.

Dependency checks select the latest compatible versions **at test time**. Supported config screens are opened, and a setting is saved, reloaded, and restored; unavailable APIs are noted.

**Passed checks are kept.** ✅ combinations are not tested again for the same published jar. ⚠️ combinations retry only the optional check. Failed, unavailable, and incomplete checks may retry; a new mod release starts fresh.

## v1.6.0

Built for Minecraft **26.2**.

### Stable

| Minecraft | Fabric | NeoForge | Forge |
| --- | :---: | :---: | :---: |
| 26.2 | ✅ | — | ❌ |

<details>
<summary>Test details</summary>

| Minecraft | Loader | Core | Optional | Versions / notes |
| --- | --- | :---: | :---: | --- |
| 26.2 | Fabric | Pass | Pass | Loader 0.19.5; Fabric API 0.160.0+26.2; Mod Menu 20.0.2; YACL 3.9.6+26.2-fabric; Text Placeholder API 3.1.0-beta.1+26.2; Config passed |
| 26.2 | NeoForge | — | Incomplete | Loader 26.2.0.88; YACL 3.9.6+26.2-neoforge; NeoForge setup failed: neoFormRecompile |
| 26.2 | Forge | Fail | — | Loader 65.1.3; Runtime crash: Forge LootModifierManager was not initialized |

</details>

<details>
<summary>Snapshots &amp; release candidates</summary>

Core only. Optional config is not tested.

| Minecraft | Fabric | NeoForge | Forge |
| --- | :---: | :---: | :---: |
| 26.3-rc-3 | ✅ | — | — |

<details>
<summary>Test details</summary>

| Minecraft | Loader | Core | Optional | Versions / notes |
| --- | --- | :---: | :---: | --- |
| 26.3-rc-3 | Fabric | Pass | — | Loader 0.19.5; Fabric API 0.160.5+26.3 |
| 26.3-rc-3 | NeoForge | Unavailable | — | No neoforge loader for this Minecraft version |
| 26.3-rc-3 | Forge | Unavailable | — | No forge loader for this Minecraft version |

</details>

</details>
