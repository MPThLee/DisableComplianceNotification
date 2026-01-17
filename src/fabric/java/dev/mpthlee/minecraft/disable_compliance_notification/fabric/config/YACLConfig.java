package dev.mpthlee.minecraft.disable_compliance_notification.fabric.config;

import dev.isxander.yacl3.api.*;
import dev.isxander.yacl3.api.controller.EnumControllerBuilder;
import dev.isxander.yacl3.config.v2.api.ConfigClassHandler;
import dev.isxander.yacl3.config.v2.api.SerialEntry;
import dev.isxander.yacl3.config.v2.api.serializer.GsonConfigSerializerBuilder;
import dev.isxander.yacl3.platform.YACLPlatform;
import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigDefault;
import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigInterface;
import dev.mpthlee.minecraft.disable_compliance_notification.config.NotificationFilterMode;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

public class YACLConfig implements DCNConfigInterface {
    public static final ConfigClassHandler<YACLConfig> HANDLER = ConfigClassHandler.createBuilder(YACLConfig.class)
            .id(YACLPlatform.rl(DisableComplianceNotification.MOD_ID, "config"))
            .serializer(config -> GsonConfigSerializerBuilder.create(config)
                    .setPath(YACLPlatform.getConfigDir().resolve(DisableComplianceNotification.MOD_ID + ".json5"))
                    .setJson5(true)
                    .build())
            .build();

    @SerialEntry
    public NotificationFilterMode notificationFilterMode = NotificationFilterMode.ONLY_COMPLIANCE;

    @Override
    public NotificationFilterMode getNotificationFilterMode() {
        return this.notificationFilterMode;
    }

    public static Screen createConfigScreen(Screen parent) {
        DCNConfigDefault defaults = new DCNConfigDefault();

        return YetAnotherConfigLib.createBuilder()
                .title(Component.translatable("config.disable_compliance_notification.title"))
                .category(ConfigCategory.createBuilder()
                        .name(Component.translatable("config.disable_compliance_notification.category.general"))
                        .option(Option.<NotificationFilterMode>createBuilder()
                                .name(Component.translatable("config.disable_compliance_notification.filter_mode"))
                                .description(OptionDescription.of(
                                        Component.translatable("config.disable_compliance_notification.filter_mode.description")))
                                .binding(
                                        defaults.getNotificationFilterMode(),
                                        () -> HANDLER.instance().notificationFilterMode,
                                        newVal -> HANDLER.instance().notificationFilterMode = newVal
                                )
                                .controller(opt -> EnumControllerBuilder.create(opt)
                                        .enumClass(NotificationFilterMode.class)
                                        .formatValue(NotificationFilterMode::getDisplayName))
                                .build())
                        .build())
                .save(HANDLER::save)
                .build()
                .generateScreen(parent);
    }
}
