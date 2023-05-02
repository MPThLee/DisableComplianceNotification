package ee.mpthl.mc.disable_compliance_notification.config;

public class DCNConfigDefault implements DCNConfigInterface {
    @Override
    public NotificationMode getNotificationMode() {
        return NotificationMode.ALL;
    }
}
