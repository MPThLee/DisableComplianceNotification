package ee.mpthl.mc.disable_compliance_notification;

import ee.mpthl.mc.disable_compliance_notification.config.NotificationMode;
import org.apache.logging.log4j.Logger;

public class SkipHelper {
    private SkipHelper() {}

    public static boolean checkSkip(Logger logger, String title, String message) {
        NotificationMode notificationMode = DisableComplianceNotification.CONFIG.getNotificationMode();
        boolean isComplianceMessage = title.startsWith("compliance") && message.startsWith("compliance.");

        logger.info("Detected Period Notification: {}, {}. [DCN-MODE: {}]", title, message, notificationMode);

        return (notificationMode == NotificationMode.DISABLE_COMPLETELY) // Disabled completely
                || (notificationMode.isCompliance() && isComplianceMessage) // Compliance messages
                || (notificationMode.isNonCompliance() && !isComplianceMessage); // Non-compliance messages
    }
}
