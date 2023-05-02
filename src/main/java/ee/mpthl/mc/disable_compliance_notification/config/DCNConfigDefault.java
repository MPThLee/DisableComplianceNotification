package ee.mpthl.mc.disable_compliance_notification.config;

public class DCNConfigDefault implements DCNConfigInterface {
    @Override
    public NotificationFilterMode getNotificationFilterMode() {
        return NotificationFilterMode.ONLY_COMPLIANCE;
    }
}
