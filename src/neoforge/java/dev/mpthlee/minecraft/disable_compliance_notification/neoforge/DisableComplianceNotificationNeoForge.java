package dev.mpthlee.minecraft.disable_compliance_notification.neoforge;

import dev.mpthlee.minecraft.disable_compliance_notification.neoforge.config.Config;
import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent;

@Mod(value = DisableComplianceNotification.MOD_ID, dist = Dist.CLIENT)
public class DisableComplianceNotificationNeoForge {
    public DisableComplianceNotificationNeoForge(IEventBus modEventBus) {
        DisableComplianceNotification.init();

        // Config GUI
        modEventBus.addListener(this::configSetup);
        Config.registerConfigGui();
        DisableComplianceNotification.startClientGateIfRequested();
    }

    public void configSetup(FMLCommonSetupEvent event) {
        event.enqueueWork(Config::loadConfig);
    }
}
