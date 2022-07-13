package ee.mpthl.mc.disable_compliance_notification.quilt;

import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import org.quiltmc.loader.api.ModContainer;
import org.quiltmc.qsl.base.api.entrypoint.ModInitializer;

public class DisableComplianceNotificationQuilt implements ModInitializer {
    @Override
    public void onInitialize(ModContainer mod) {
        DisableComplianceNotification.init();
    }
}
