package dev.mpthlee.minecraft.disable_compliance_notification.forge.config;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;

public final class Config {
    private Config() {
    }

    public static void loadConfig() {
        DisableComplianceNotification.setConfig(ForgeConfig.INSTANCE);
    }
}
