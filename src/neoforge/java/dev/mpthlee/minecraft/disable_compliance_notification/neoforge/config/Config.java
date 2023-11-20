package dev.mpthlee.minecraft.disable_compliance_notification.neoforge.config;

import dev.mpthlee.minecraft.disable_compliance_notification.config.ConfigHelper;
import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfig;
import me.shedaniel.autoconfig.AutoConfig;
import net.neoforged.neoforge.client.ConfigScreenHandler.ConfigScreenFactory;
import net.neoforged.fml.ModList;
import net.neoforged.fml.ModLoadingContext;

public class Config {
    public static boolean isClothConfigInstalled() {
        return ModList.get().isLoaded("cloth_config");
    }

    public static void registerConfigGui() {
        if (isClothConfigInstalled()) {
            ModLoadingContext.get().registerExtensionPoint(ConfigScreenFactory.class, () -> new ConfigScreenFactory(
                    (client, parent) -> AutoConfig.getConfigScreen(DCNConfig.class, parent).get()));
        }
    }

    public static void loadConfig() {
        if (isClothConfigInstalled()) {
            ConfigHelper.loadConfig();
        }
    }
}
