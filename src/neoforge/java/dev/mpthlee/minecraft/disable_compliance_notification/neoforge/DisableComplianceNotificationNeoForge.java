package dev.mpthlee.minecraft.disable_compliance_notification.neoforge;

import dev.mpthlee.minecraft.disable_compliance_notification.neoforge.config.Config;
import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

@Mod(value = DisableComplianceNotification.MOD_ID, dist = Dist.CLIENT)
public class DisableComplianceNotificationNeoForge {
    private static final Logger LOGGER = LogManager.getLogger("DisableComplianceNotificationNeoForge");

    public DisableComplianceNotificationNeoForge(IEventBus modEventBus) {
        DisableComplianceNotification.init();

        // Config GUI
        modEventBus.addListener(this::configSetup);
        Config.registerConfigGui();
        startClientGameTestIfRequested();
    }

    public void configSetup(FMLCommonSetupEvent event) {
        event.enqueueWork(Config::loadConfig);
    }

    private static void startClientGameTestIfRequested() {
        if (!Boolean.getBoolean("dcn.client.gametest")) {
            return;
        }

        try {
            Class.forName("dev.mpthlee.minecraft.disable_compliance_notification.test.neoforge.NeoForgeClientGameTestBootstrap")
                    .getMethod("start")
                    .invoke(null);
        } catch (ReflectiveOperationException exception) {
            LOGGER.error("NeoForge client GameTest was requested but the test bootstrap is unavailable", exception);
            throw new IllegalStateException("NeoForge client GameTest bootstrap is unavailable", exception);
        }
    }
}
