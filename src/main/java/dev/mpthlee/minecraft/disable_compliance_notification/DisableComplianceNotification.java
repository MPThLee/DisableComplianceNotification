package dev.mpthlee.minecraft.disable_compliance_notification;

import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigDefault;
import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigInterface;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Locale;

public class DisableComplianceNotification {
    public static final String MOD_ID = "disable_compliance_notification";
    private static final Logger LOGGER = LogManager.getLogger("");
    private static DCNConfigInterface config = new DCNConfigDefault();

    private DisableComplianceNotification() {
    }

    public static void init() {
        String locale = Locale.getDefault().getISO3Country();
        LOGGER.info("Initializing Disable Compliance Notification... [Locale ISO3 Country: {}]", locale);
    }

    public static void startClientGateIfRequested() {
        if (!Boolean.getBoolean("dcn.client.gate")) {
            return;
        }

        try {
            Class.forName("dev.mpthlee.minecraft.disable_compliance_notification.test.ClientGateBootstrap")
                    .getMethod("start")
                    .invoke(null);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("DCN client-gate bootstrap is unavailable", exception);
        }
    }

    public static DCNConfigInterface getConfig() {
        return config;
    }

    public static void setConfig(DCNConfigInterface config) {
        DisableComplianceNotification.config = config;
    }
}
