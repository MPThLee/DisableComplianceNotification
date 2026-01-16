package dev.mpthlee.minecraft.disable_compliance_notification.neoforge.config;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import net.neoforged.neoforge.client.gui.IConfigScreenFactory;
import net.neoforged.fml.ModList;
import net.neoforged.fml.ModLoadingContext;

public class Config {
    public static boolean isYACLInstalled() {
        return ModList.get().isLoaded("yet_another_config_lib_v3");
    }

    public static void registerConfigGui() {
        if (isYACLInstalled()) {
            ModLoadingContext.get().registerExtensionPoint(IConfigScreenFactory.class, () -> (
                    (client, parent) -> YACLConfig.createConfigScreen(parent)));
        }
    }

    public static void loadConfig() {
        if (isYACLInstalled()) {
            YACLConfig.HANDLER.load();
            DisableComplianceNotification.setConfig(YACLConfig.HANDLER.instance());
        }
    }
}
