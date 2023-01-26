package ee.mpthl.mc.disable_compliance_notification.forge;

import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;

@Mod(DisableComplianceNotification.MOD_ID)
public class DisableComplianceNotificationForge {
    public DisableComplianceNotificationForge() {
        DisableComplianceNotification.init();
        MinecraftForge.EVENT_BUS.register(this);
    }
}
