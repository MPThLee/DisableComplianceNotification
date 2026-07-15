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

The test starts Minecraft with the mod and its mixin applied, then constructs two due vanilla `PeriodicNotificationManager.NotificationTask` instances:

1. A compliance notification must be detected as filtered. After a client tick, no periodic toast may exist.
2. A non-compliance notification must be detected as unfiltered. After a client tick, one periodic toast must exist.

This covers both sides of the filter and executes the vanilla toast path that changed between Minecraft 26.1 and 26.2. The test harness locates the toast manager through either the 26.1 getter or the 26.2 GUI accessor, so the same test can be reused on both version branches.

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
```

The Fabric build also runs the basic server GameTest. The client GameTest is a separate task because it launches a graphical client.

The version-selection regression tests can be run without Gradle:

```bash
python3 tools/test/test_update_version.py
```

## CI Coverage

`.github/workflows/test.yml` performs:

| Check | Fabric | NeoForge |
| --- | :---: | :---: |
| Compile and package | Yes | Yes |
| Load the client | Yes | Yes |
| Apply the compliance mixin | Yes | Smoke test |
| Assert filtered and unfiltered toast behavior | Yes | No |

The Fabric client test normally finishes a few seconds after Minecraft starts. CI retains its client log even when the task fails.

## Legacy Resource-Pack Fixture

`misc/compliance.zip` is retained for optional, slow manual testing of Minecraft's resource reload and regional timer. It is no longer copied into automated GameTest runs. Its `pack.mcmeta` must be updated when Minecraft changes the resource-pack format before using it on a newer branch.

## Troubleshooting

If the client test does not start, confirm that Java matches `java_version` in `config.properties` and inspect `fabric/build/run/clientGameTest/logs/latest.log`.

If a notification is detected but classified incorrectly, check the configured `NotificationFilterMode`. The deterministic test temporarily uses the default `ONLY_COMPLIANCE` mode and restores the prior configuration afterward.
