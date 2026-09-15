# Compatibility

Automated checks of unchanged published jars. Mod **1.6.0+** only.

Last updated: 2026-09-15 22:13:56 UTC

| Mark | Meaning |
| :---: | --- |
| ✅ | All applicable checks pass |
| ⚠️ | Core passes; optional dependencies are not verified working |
| ❌ | Core runtime check failed |
| — | Not tested, unavailable, or incomplete |

## v1.6.0

Built for Minecraft **26.2+**.

### Stable

| Minecraft | Fabric | NeoForge | Forge |
| --- | :---: | :---: | :---: |
| 26.3 | ❌ | ❌ | — |
| 26.2 | ✅ | ⚠️ | ✅ |

<details>
<summary>Test details</summary>

| Minecraft | Loader | Core | Optional | Versions |
| --- | --- | :---: | :---: | --- |
| 26.3 | Fabric | Fail | Unavailable | Loader 0.19.5 |
| 26.3 | NeoForge | Fail | Unavailable | Loader 26.3.0.1-beta |
| 26.3 | Forge | Unavailable | — | — |
| 26.2 | Fabric | Pass | Pass | Loader 0.19.5; YACL 3.9.6+26.2-fabric; Mod Menu 20.0.2 |
| 26.2 | NeoForge | Pass | Fail | Loader 26.2.0.88; YACL 3.9.6+26.2-neoforge |
| 26.2 | Forge | Pass | — | Loader 65.1.3 |

</details>

<details>
<summary>Snapshots &amp; release candidates</summary>

Core only. Optional config is not tested.

| Minecraft | Fabric | NeoForge | Forge |
| --- | :---: | :---: | :---: |
| 26.3-rc-3 | ✅ | — | — |

<details>
<summary>Test details</summary>

| Minecraft | Loader | Core | Optional | Versions |
| --- | --- | :---: | :---: | --- |
| 26.3-rc-3 | Fabric | Pass | — | Loader 0.19.5 |
| 26.3-rc-3 | NeoForge | Unavailable | — | — |
| 26.3-rc-3 | Forge | Unavailable | — | — |

</details>

</details>
