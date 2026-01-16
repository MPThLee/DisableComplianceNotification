package dev.mpthlee.minecraft.disable_compliance_notification.forge.config;

import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigDefault;
import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigInterface;
import dev.mpthlee.minecraft.disable_compliance_notification.config.NotificationFilterMode;
import net.minecraftforge.common.ForgeConfigSpec;

public class ForgeConfig implements DCNConfigInterface {
    public static final ForgeConfigSpec SPEC;
    public static final ForgeConfig INSTANCE;

    private final ForgeConfigSpec.EnumValue<NotificationFilterMode> notificationFilterMode;

    static {
        ForgeConfigSpec.Builder builder = new ForgeConfigSpec.Builder();
        INSTANCE = new ForgeConfig(builder);
        SPEC = builder.build();
    }

    private ForgeConfig(ForgeConfigSpec.Builder builder) {
        builder.push("general");

        notificationFilterMode = builder
                .comment("Notification filter mode")
                .translation("config.disable_compliance_notification.filter_mode")
                .defineEnum("notificationFilterMode", new DCNConfigDefault().getNotificationFilterMode());

        builder.pop();
    }

    @Override
    public NotificationFilterMode getNotificationFilterMode() {
        return notificationFilterMode.get();
    }
}
