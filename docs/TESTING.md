# Testing the Compliance Notification Filter

The primary regression test is a real Fabric client launch with deterministic notification timing. It does not wait for Minecraft's regional timer or require a test resource pack.

## Fabric Client GameTest

Run the client test from the repository root:

```bash
./tools/test-gametest.sh fabric
```

Or invoke Loom directly:

```bash
cd fabric
./gradlew runClientGameTest
```

The test starts Minecraft with the mod and its mixin applied, creates an integrated singleplayer world, and waits for the player to join it. While in that world, it first verifies that a non-periodic system toast remains untouched, then constructs two due vanilla `PeriodicNotificationManager.NotificationTask` instances:

1. A compliance notification must be detected as filtered. After a client tick, no periodic toast may exist.
2. A non-compliance notification must be detected as unfiltered. After a client tick, one periodic toast must exist.

This covers both sides of the filter and executes vanilla's real notification path. Production filtering happens at `SystemToast.add`, whose signature and translation-component inputs are identical in the decompiled 26.1.2 and 26.2 clients. The test harness locates the toast manager through either the 26.1 getter or the 26.2 GUI accessor, but that compatibility reflection is test-only.

Expected log lines include:

```text
Detected Period Notification: (title='compliance.gametest.filtered.title', ...) [DCN-MODE: ONLY_COMPLIANCE, Filtered: true]
Detected Period Notification: (title='dcn.gametest.unfiltered.title', ...) [DCN-MODE: ONLY_COMPLIANCE, Filtered: false]
Deterministic periodic notification client gametest passed
```

Client GameTest logs are written to:

```text
fabric/build/run/clientGameTest/logs/latest.log
```

## Two-Minute Loader Gates

Run the production client gate for every loader:

```bash
./tools/test/run_client_gate.sh fabric
./tools/test/run_client_gate.sh neoforge
./tools/test/run_client_gate.sh forge
```

Pass `--xvfb` on a headless Linux host. Each gate generates a Minecraft-26.2-compatible resource pack from `tools/test/fixtures/compliance_gate`, enables it temporarily, and temporarily removes any existing DCN config so the default `ONLY_COMPLIANCE` mode is tested. A dev-only bootstrap creates and joins a disposable integrated singleplayer world; that bootstrap is excluded from production JARs. The generated save is deleted and the loader's original options, resource pack, and config are restored byte-for-byte afterward.

The default gate remains in the world for 150 seconds after the player joins. It only passes after both vanilla notification tasks have run and logged `Filtered: true`:

```text
compliance.playtime.hours
compliance.playtime.greaterThan24Hours
```

The first notification repeats every minute and the second has a two-minute delay. The gate also requires the exact `KOR` initialization marker, positive proof that Minecraft reloaded `file/dcn-compliance-gate.zip`, and an explicit `DCN compliance gate entered world` marker. Independently of the mod's filter log, the dev-only bootstrap polls Minecraft's real `ToastManager` throughout the interval and fails if a periodic toast is ever present. A client crash, startup timeout, early exit, main-menu-only run, incompatible test pack, missing mixin, unfiltered notification, or actual periodic-toast enqueue therefore fails the gate. Full console output and machine-readable evidence are retained at `<loader>/build/client-gate.log` and `<loader>/build/client-gate-result.json`.

## Other Checks

Build each production loader independently:

```bash
cd fabric && ./gradlew build
cd neoforge && ./gradlew build
cd forge && ./gradlew build
```

The Fabric build also runs the basic server GameTest. The client GameTest is a separate task because it launches a graphical client.

The build-tool and loader-metadata regression tests can be run without Gradle:

```bash
python3 -m unittest discover -s tools/test -p 'test_*.py'
```

## CI Coverage

`.github/workflows/test.yml` performs:

| Check | Fabric | NeoForge | Forge |
| --- | :---: | :---: | :---: |
| Compile and package | Yes | Yes | Yes |
| Load the client | Yes | Yes | Yes |
| Deterministic non-periodic, filtered, unfiltered, and enqueue assertions | Yes | No | No |
| Run at least two minutes inside a singleplayer world | Yes | Yes | Yes |
| Require both real compliance notifications to be filtered | Yes | Yes | Yes |
| Independently require no periodic toast in `ToastManager` | Yes | Yes | Yes |

The Fabric deterministic test normally finishes a few seconds after Minecraft starts. The separate production gates exercise the regional timer on all three loaders. CI retains client logs even when a task fails.

## Minecraft Compatibility Evidence

[`data/minecraft-compatibility.json`](../data/minecraft-compatibility.json) is the canonical, machine-readable compatibility record. It separates the open loader-metadata range from versions that have actually completed the runtime gates. The tooling tests require its release and Minecraft versions to match `config.properties`, require evidence for Fabric, NeoForge, and Forge, and reject gate records shorter than two minutes.

The scheduled Minecraft update workflow checks Mojang's release manifest but does not create a branch immediately. For a new or not-yet-attested release it resolves the candidate dependency set once, then applies that exact hashed patch in parallel Fabric, NeoForge, and Forge jobs. Each job builds and runs its two-minute in-world gate; Fabric also runs the deterministic client gametest. A read-only aggregation job accepts the three distinct evidence artifacts only after the whole matrix passes, validates the compatibility data, and exports a narrowly scoped tested patch. A separate publish job with write permission verifies and applies that exact patch. A failed dependency lookup, build, gate, or evidence check fails the workflow and uploads the available per-loader logs without changing repository branches. When the manifest has no newer release and current evidence is valid, all expensive jobs are skipped and the workflow succeeds.

Tagged releases additionally require the tag to equal `v<mod_version>` from `config.properties`. Fabric, NeoForge, and Forge run their in-world gates in parallel on the tagged commit before GitHub release creation or external publishing. Individual Gradle build steps allow up to one hour and retry once because Forge dependency preparation can be substantially slower and more sensitive to transient Maven failures than the other loaders.

GitHub runs scheduled workflows from the repository's default branch. When promoting a new maintained Minecraft branch, make that branch the default or apply the workflow update to the existing default branch before relying on the schedule.

## Legacy Resource-Pack Fixture

`misc/compliance.zip` remains as a legacy manual fixture. Automated gates use the source fixture under `tools/test/fixtures/compliance_gate` and generate `pack.mcmeta` from the current `pack_format` in `config.properties`, avoiding a stale binary pack when the Minecraft target changes.

## Troubleshooting

If the client test does not start, confirm that Java matches `java_version` in `config.properties` and inspect `fabric/build/run/clientGameTest/logs/latest.log`.

If a notification is detected but classified incorrectly, check the configured `NotificationFilterMode`. The deterministic test temporarily uses the default `ONLY_COMPLIANCE` mode and restores the prior configuration afterward.
