package ee.mpthl.mc.disable_compliance_notification.fabric;

import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import ee.mpthl.mc.disable_compliance_notification.fabric.config.Config;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.api.EnvType;
import net.fabricmc.api.Environment;
import net.fabricmc.api.ModInitializer;

@Environment(EnvType.CLIENT)
public class DisableComplianceNotificationFabric implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        DisableComplianceNotification.init();

        Config.loadConfig();
    }
}
