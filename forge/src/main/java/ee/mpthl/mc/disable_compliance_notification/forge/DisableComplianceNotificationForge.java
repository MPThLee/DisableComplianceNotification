package ee.mpthl.mc.disable_compliance_notification.forge;

import dev.architectury.platform.forge.EventBuses;
import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;

@Mod(DisableComplianceNotification.MOD_ID)
public class DisableComplianceNotificationForge {
    public DisableComplianceNotificationForge() {
        // Submit our event bus to let architectury register our content on the right time
        EventBuses.registerModEventBus(DisableComplianceNotification.MOD_ID, FMLJavaModLoadingContext.get().getModEventBus());
        DisableComplianceNotification.init();
    }
}
