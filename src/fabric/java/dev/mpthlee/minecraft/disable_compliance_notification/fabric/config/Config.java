package dev.mpthlee.minecraft.disable_compliance_notification.fabric.config;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import net.fabricmc.loader.api.FabricLoader;

public class Config {
    public static boolean isYACLInstalled() {
        return FabricLoader.getInstance().isModLoaded("yet_another_config_lib_v3");
    }

    public static void loadConfig() {
        if (isYACLInstalled()) {
            YACLConfig.HANDLER.load();
            DisableComplianceNotification.setConfig(YACLConfig.HANDLER.instance());
        }
    }
}
