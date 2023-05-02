package ee.mpthl.mc.disable_compliance_notification.config;

import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import me.shedaniel.autoconfig.ConfigData;
import me.shedaniel.autoconfig.annotation.Config;
import me.shedaniel.autoconfig.annotation.ConfigEntry.Gui.EnumHandler;
import me.shedaniel.autoconfig.annotation.ConfigEntry.Gui.Tooltip;

@Config(name = DisableComplianceNotification.MOD_ID)
public class DCNConfig implements ConfigData, DCNConfigInterface {
    @Tooltip
    @EnumHandler
    public NotificationMode notificationMode = NotificationMode.ALL;

    @Override
    public NotificationMode getNotificationMode() {
        return this.notificationMode;
    }
}
