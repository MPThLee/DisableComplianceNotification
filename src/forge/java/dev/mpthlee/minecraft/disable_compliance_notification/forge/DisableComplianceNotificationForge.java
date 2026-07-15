package dev.mpthlee.minecraft.disable_compliance_notification.forge;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import dev.mpthlee.minecraft.disable_compliance_notification.forge.config.Config;
import dev.mpthlee.minecraft.disable_compliance_notification.forge.config.ForgeConfig;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.config.ModConfig;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;

@Mod(DisableComplianceNotification.MOD_ID)
public final class DisableComplianceNotificationForge {
    public DisableComplianceNotificationForge(FMLJavaModLoadingContext context) {
        DisableComplianceNotification.init();

        context.registerConfig(ModConfig.Type.CLIENT, ForgeConfig.SPEC);
        FMLCommonSetupEvent.getBus(context.getModBusGroup()).addListener(this::onCommonSetup);
        DisableComplianceNotification.startClientGateIfRequested();
    }

    private void onCommonSetup(final FMLCommonSetupEvent event) {
        event.enqueueWork(Config::loadConfig);
    }
}
