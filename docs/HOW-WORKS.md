# How Does "Regional Compliance" Work?

As of versions 1.18.2–1.21.4, Mojang has implemented this system using `Locale.getDefault()` to detect the current locale and `getISO3Country()` for region code comparison. [^1]

The compliance format follows this structure, located in `assets/minecraft/regional_compliancies.json`:

```json
{
  "KOR": [
    {
      "delay": 1440,
      "period": 60,
      "title": "compliance.playtime.greaterThan24Hours",
      "message": "compliance.playtime.message"
    },
    {
      "period": 60,
      "title": "compliance.playtime.hours",
      "message": "compliance.playtime.message"
    }
  ]
}
```

The `period` value is measured in minutes. This means that every 60 minutes, the system will trigger the `compliance.playtime.hours` message.

Additionally, only the first applicable entry is displayed. This is where the `delay` parameter comes into play—it defines the waiting period before execution. If the specified game time has not yet been reached, the message will not be triggered, and the system will move to the next entry.

For instance, if you have played for 24 hours (60 × 24 = 1440 minutes), the displayed message will change to `compliance.playtime.greaterThan24Hours`.

# How Does This Mod Block It?

There are multiple ways to disable this system:

- **Intercepting `ResourceManager`**: Injecting code into `ResourceManager` to cancel the reading of compliance-related resources. [^2]
- **Modifying `PeriodicNotificationManager`**:
    1. Completely disabling all notifications.
    2. Selectively filtering notifications based on their type.

This mod specifically filters notifications by type. During testing, I discovered that some servers utilize (or exploit) this system. To mitigate this, I introduced configuration options that allow selective disabling of the compliance filter.

---

[^1]: If your device’s country setting is set to a non-supported region, this feature will be disabled by default.

[^2]: Since this system is based on resource packs, it can be modified by the user or server (via server resource pack requests).