package ee.mpthl.mc.disable_compliance_notification;

import ee.mpthl.mc.disable_compliance_notification.config.DCNConfigDefault;
import ee.mpthl.mc.disable_compliance_notification.config.DCNConfigInterface;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class DisableComplianceNotification {
    public static final String MOD_ID = "disable_compliance_notification";
    private static final Logger LOGGER = LogManager.getLogger("");
    public static DCNConfigInterface CONFIG = new DCNConfigDefault();
    private DisableComplianceNotification() {
    }

    public static void init() {
        LOGGER.info("Initializing Disable Compliance Notification");
    }
}
