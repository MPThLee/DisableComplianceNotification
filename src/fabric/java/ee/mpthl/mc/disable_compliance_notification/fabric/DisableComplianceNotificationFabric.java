package ee.mpthl.mc.disable_compliance_notification.fabric;

import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import net.fabricmc.api.ModInitializer;

public class DisableComplianceNotificationFabric implements ModInitializer {
    @Override
    public void onInitialize() {
        DisableComplianceNotification.init();
    }
}
