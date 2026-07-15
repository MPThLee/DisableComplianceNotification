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

The test starts Minecraft with the mod and its mixin applied. It first verifies that a non-periodic system toast remains untouched, then constructs two due vanilla `PeriodicNotificationManager.NotificationTask` instances:

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
| Require a successful mod-initialization marker | Yes | Yes | Yes |
| Assert non-periodic, filtered, unfiltered, and single-enqueue behavior | Yes | No | No |

The Fabric client test normally finishes a few seconds after Minecraft starts. NeoForge and Forge smoke tests only accept the expected timeout after the mod has logged successful initialization; a timeout during dependency or asset setup is a failure. CI retains client logs even when a task fails.

## Legacy Resource-Pack Fixture

`misc/compliance.zip` is retained for optional, slow manual testing of Minecraft's resource reload and regional timer. It is no longer copied into automated GameTest runs. Its `pack.mcmeta` must be updated when Minecraft changes the resource-pack format before using it on a newer branch.

## Troubleshooting

If the client test does not start, confirm that Java matches `java_version` in `config.properties` and inspect `fabric/build/run/clientGameTest/logs/latest.log`.

If a notification is detected but classified incorrectly, check the configured `NotificationFilterMode`. The deterministic test temporarily uses the default `ONLY_COMPLIANCE` mode and restores the prior configuration afterward.
