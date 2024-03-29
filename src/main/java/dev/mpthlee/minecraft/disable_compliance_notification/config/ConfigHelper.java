package dev.mpthlee.minecraft.disable_compliance_notification.config;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import me.shedaniel.autoconfig.AutoConfig;
import me.shedaniel.autoconfig.serializer.Toml4jConfigSerializer;

public class ConfigHelper {
    private ConfigHelper() {}

    public static void loadConfig() {
        DisableComplianceNotification.setConfig(AutoConfig.register(DCNConfig.class, Toml4jConfigSerializer::new).getConfig());
    }
}
