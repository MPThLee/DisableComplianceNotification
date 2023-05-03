package ee.mpthl.mc.disable_compliance_notification;

import ee.mpthl.mc.disable_compliance_notification.config.DCNConfigDefault;
import ee.mpthl.mc.disable_compliance_notification.config.DCNConfigInterface;
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

    public static DCNConfigInterface getConfig() {
        return config;
    }

    public static void setConfig(DCNConfigInterface config) {
        DisableComplianceNotification.config = config;
    }
}
