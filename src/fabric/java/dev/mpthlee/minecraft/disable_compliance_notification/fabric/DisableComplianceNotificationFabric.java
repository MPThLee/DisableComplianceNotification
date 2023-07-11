package java.dev.mpthlee.minecraft.disable_compliance_notification.fabric;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import java.dev.mpthlee.minecraft.disable_compliance_notification.fabric.config.Config;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.api.EnvType;
import net.fabricmc.api.Environment;

@Environment(EnvType.CLIENT)
public class DisableComplianceNotificationFabric implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        DisableComplianceNotification.init();

        Config.loadConfig();
    }
}
