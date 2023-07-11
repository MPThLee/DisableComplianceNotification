package dev.mpthlee.minecraft.disable_compliance_notification.config;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import me.shedaniel.autoconfig.ConfigData;
import me.shedaniel.autoconfig.annotation.Config;
import me.shedaniel.autoconfig.annotation.ConfigEntry.Gui.EnumHandler;
import me.shedaniel.autoconfig.annotation.ConfigEntry.Gui.Tooltip;

@Config(name = DisableComplianceNotification.MOD_ID)
public class DCNConfig implements ConfigData, DCNConfigInterface {
    @Tooltip
    @EnumHandler(option = EnumHandler.EnumDisplayOption.BUTTON)
    public NotificationFilterMode notificationFilterMode = new DCNConfigDefault().getNotificationFilterMode();

    @Override
    public NotificationFilterMode getNotificationFilterMode() {
        return this.notificationFilterMode;
    }
}
