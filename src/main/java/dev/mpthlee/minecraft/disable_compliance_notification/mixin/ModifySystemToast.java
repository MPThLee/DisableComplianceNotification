package dev.mpthlee.minecraft.disable_compliance_notification.mixin;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import dev.mpthlee.minecraft.disable_compliance_notification.config.NotificationFilterMode;
import net.minecraft.client.gui.components.toasts.SystemToast;
import net.minecraft.client.gui.components.toasts.ToastManager;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.contents.TranslatableContents;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(SystemToast.class)
public abstract class ModifySystemToast {
    private static final Logger LOGGER = LogManager.getLogger("ModifySystemToast");

    @Inject(
            method = "add(Lnet/minecraft/client/gui/components/toasts/ToastManager;"
                    + "Lnet/minecraft/client/gui/components/toasts/SystemToast$SystemToastId;"
                    + "Lnet/minecraft/network/chat/Component;"
                    + "Lnet/minecraft/network/chat/Component;)V",
            at = @At("HEAD"),
            cancellable = true,
            remap = false
    )
    private static void filterPeriodicNotification(
            ToastManager toastManager,
            SystemToast.SystemToastId id,
            Component title,
            Component message,
            CallbackInfo ci
    ) {
        if (id != SystemToast.SystemToastId.PERIODIC_NOTIFICATION) {
            return;
        }

        String titleKey = componentKey(title);
        String messageKey = componentKey(message);
        NotificationFilterMode notificationMode = DisableComplianceNotification
                .getConfig()
                .getNotificationFilterMode();
        boolean isFiltered = notificationMode.isFiltered(titleKey, messageKey);

        LOGGER.info(
                "Detected Period Notification: (title='{}', message='{}') "
                        + "[DCN-MODE: {}, Filtered: {}]",
                titleKey,
                messageKey,
                notificationMode.toEnumString(),
                isFiltered
        );

        if (isFiltered) {
            ci.cancel();
        }
    }

    @Unique
    private static String componentKey(Component component) {
        if (component == null) {
            return "";
        }

        if (component.getContents() instanceof TranslatableContents translatable) {
            return translatable.getKey();
        }

        return component.getString();
    }
}
