package dev.mpthlee.minecraft.disable_compliance_notification.forge.config;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;

public class Config {
    public static void loadConfig() {
        DisableComplianceNotification.setConfig(ForgeConfig.INSTANCE);
    }
}
