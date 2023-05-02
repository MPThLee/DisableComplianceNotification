package ee.mpthl.mc.disable_compliance_notification.fabric.config;

import ee.mpthl.mc.disable_compliance_notification.config.ConfigHelper;
import net.fabricmc.loader.api.FabricLoader;

public class Config {
    public static boolean isClothConfigInstalled() {
        return FabricLoader.getInstance().isModLoaded("cloth-config2");
    }

    public static void loadConfig() {
        if (isClothConfigInstalled()) {
            ConfigHelper.loadConfig();
        }
    }
}
