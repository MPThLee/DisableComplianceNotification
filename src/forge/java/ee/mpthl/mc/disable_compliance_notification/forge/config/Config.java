package ee.mpthl.mc.disable_compliance_notification.forge.config;

import ee.mpthl.mc.disable_compliance_notification.config.ConfigHelper;
import ee.mpthl.mc.disable_compliance_notification.config.DCNConfig;
import me.shedaniel.autoconfig.AutoConfig;
import net.minecraftforge.client.ConfigScreenHandler.ConfigScreenFactory;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.ModLoadingContext;

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
