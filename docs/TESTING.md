# Testing the Compliance Notification Filter

This document describes how to test that the mod correctly filters compliance notifications.

## Test Resource Pack

The `misc/compliance.zip` resource pack modifies the notification timing for testing:

| Setting | Original | Test Pack |
|---------|----------|-----------|
| Period | 60 minutes | 1 minute |
| Delay (24h message) | 1440 minutes | 2 minutes |
| Regions | KOR only | KOR, USA, GBR |

This allows notifications to trigger within 2-3 minutes instead of 1-24 hours.

## Expected Notifications

With the test resource pack, you should see **two different notifications**:

| Time | Notification | Message Key |
|------|--------------|-------------|
| ~1 min | Hourly playtime | `compliance.playtime.hours` |
| ~2 min | 24h+ playtime | `compliance.playtime.greaterThan24Hours` |

**Test is successful when both notifications are filtered.**

## Local Testing

### GUI Test (Recommended for Compliance Testing)

```bash
./tools/test-local.sh fabric --build
```

Then manually:
1. Enable compliance.zip resourcepack
2. Create/join a world
3. Wait 2.5-3 minutes
4. Exit and verify: `./tools/test-local.sh fabric --verify-only`

### Headless Test (Experimental)

Uses [HeadlessMC](https://github.com/headlesshq/headlessmc) with [hmc-specifics](https://github.com/headlesshq/hmc-specifics):

```bash
./tools/test-headless.sh fabric --build --timeout 200
```

**Note**: Requires manual interaction via HeadlessMC console to join a world:
```
gui              # Show current screen buttons
click 1          # Click Singleplayer
click 1          # Click first world / Create New
click 1          # Enter world
```

### Manual Test Steps

1. Build the mod:
   ```bash
   cd fabric  # or neoforge/forge
   ./gradlew build
   ```

2. Prepare test environment:
   ```bash
   mkdir -p run/mods run/resourcepacks
   cp build/libs/*.jar run/mods/
   cp ../misc/compliance.zip run/resourcepacks/
   ```

3. Run the client:
   ```bash
   ./gradlew runClient
   ```

4. In-game:
   - Go to **Options > Resource Packs**
   - Enable **compliance.zip**
   - Create or load a singleplayer world
   - Wait **2.5-3 minutes** (to trigger both hourly and 24h notifications)

5. Verify the mod filtered the notification:
   ```bash
   ../tools/verify-compliance-log.sh run
   ```

### Expected Log Output

When working correctly, the log should contain **both** messages:
```
[ModifyPeriodicNotificationManager] Detected Period Notification: (title='compliance.playtime.hours', message='compliance.playtime.message') [DCN-MODE: COMPLIANCE_ONLY, Filtered: true]
[ModifyPeriodicNotificationManager] Detected Period Notification: (title='compliance.playtime.greaterThan24Hours', message='compliance.playtime.message') [DCN-MODE: COMPLIANCE_ONLY, Filtered: true]
```

Key indicators:
- `Detected Period Notification:` - The mixin intercepted a notification
- `Filtered: true` - The notification was successfully blocked
- Both `playtime.hours` and `greaterThan24Hours` - Both notification types were tested

### Verify Only (After Manual Test)

If you've already run the client manually:
```bash
./tools/test-local.sh fabric --verify-only
```

## CI Testing

The GitHub Actions workflow (`.github/workflows/test.yml`) uses [mc-runtime-test](https://github.com/headlesshq/mc-runtime-test) with Fabric's GameTest framework.

### What CI Tests

| Test | Fabric CI | NeoForge CI | Local |
|------|:---------:|:-----------:|:-----:|
| Mod compiles | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Mod loads without crash | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Mixins apply correctly | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| GameTest waits 3 min | :white_check_mark: | :x: | :white_check_mark: |

### How Fabric CI Works

1. Builds mod with `./gradlew build` (runs server-side GameTest)
2. mc-runtime-test runs client with `-DMcRuntimeGameTest=true`
3. GameTest keeps game running for 3 minutes
4. Compliance notifications trigger during this time
5. Logs verified for filtering

### How NeoForge CI Works

mc-runtime-test runs for basic mod loading verification (no long wait).

### GameTest Source Location

GameTest sources are in `src/gametest/`:
```
src/gametest/
├── java/dev/mpthlee/.../test/ComplianceGameTest.java
└── resources/fabric.mod.json
```

## Troubleshooting

### "No compliance notification detected in logs"

1. **Resource pack not enabled**: Ensure compliance.zip is active in-game
2. **Wrong locale**: Set system locale to KR, US, or GB
3. **Not enough time**: Wait at least 2.5-3 minutes in-game for both notifications
4. **Wrong log file**: Check `run/logs/latest.log`

### "Notifications detected but none were filtered"

Check the mod configuration:
- Default mode is `COMPLIANCE_ONLY` which should filter compliance notifications
- If set to `DISABLED`, notifications won't be filtered

### Locale Issues

The compliance system uses `Locale.getDefault().getISO3Country()`. To test with a specific locale:

```bash
# Run with Korean locale
./gradlew runClient -Duser.country=KR -Duser.language=ko

# Or US locale
./gradlew runClient -Duser.country=US -Duser.language=en
```
