package dev.mpthlee.minecraft.disable_compliance_notification.forge;

import dev.mpthlee.minecraft.disable_compliance_notification.forge.config.Config;
import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.api.distmarker.OnlyIn;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;

@Mod(DisableComplianceNotification.MOD_ID)
@OnlyIn(Dist.CLIENT)
public class DisableComplianceNotificationForge {
    public DisableComplianceNotificationForge() {
        DisableComplianceNotification.init();
        MinecraftForge.EVENT_BUS.register(this);

        // Config GUI
        FMLJavaModLoadingContext.get().getModEventBus().addListener(DisableComplianceNotificationForge::configSetup);
        Config.registerConfigGui();
    }

    public static void configSetup(FMLCommonSetupEvent event) {
        event.enqueueWork(Config::loadConfig);
    }
}
