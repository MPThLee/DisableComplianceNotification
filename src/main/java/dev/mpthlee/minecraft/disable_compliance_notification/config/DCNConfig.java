package dev.mpthlee.minecraft.disable_compliance_notification.config;

public class DCNConfig implements DCNConfigInterface {
    public NotificationFilterMode notificationFilterMode = new DCNConfigDefault().getNotificationFilterMode();

    @Override
    public NotificationFilterMode getNotificationFilterMode() {
        return this.notificationFilterMode;
    }
}
