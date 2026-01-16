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

### Quick Test

```bash
# Build and prepare test environment for Fabric
./tools/test-local.sh fabric --build

# For NeoForge
./tools/test-local.sh neoforge --build

# For Forge
./tools/test-local.sh forge --build
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

The GitHub Actions workflow (`.github/workflows/test.yml`) automatically:

1. Builds the mod for each loader (Fabric, NeoForge)
2. Sets up the test environment with the compliance resource pack
3. Runs the Minecraft client via [mc-runtime-test](https://github.com/headlesshq/mc-runtime-test)
4. Verifies log output for notification filtering

### Limitations

The CI test has limited runtime, which may not be enough for compliance notifications to trigger naturally. The CI primarily verifies:
- Mod loads without errors
- Mixin is registered correctly
- No crashes occur

For full notification filtering verification, use local testing.

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
