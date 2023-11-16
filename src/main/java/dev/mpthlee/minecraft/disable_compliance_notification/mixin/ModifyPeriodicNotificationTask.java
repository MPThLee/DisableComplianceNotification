package dev.mpthlee.minecraft.disable_compliance_notification.mixin;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import dev.mpthlee.minecraft.disable_compliance_notification.config.NotificationFilterMode;
import net.minecraft.client.Minecraft;
import net.minecraft.client.PeriodicNotificationManager.Notification;
import net.minecraft.client.gui.components.toasts.SystemToast;
import net.minecraft.network.chat.Component;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
//import net.minecraft.client.PeriodicNotificationManager.NotificationTask;

import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

// TODO: Nested Class `NotificationTask` doesn't exposed in 1.18.2 mojmap.
@Mixin(targets = "net.minecraft.client.PeriodicNotificationManager$NotificationTask")
public class ModifyPeriodicNotificationTask {
    private static final Logger LOGGER = LogManager.getLogger("ModifyPeriodicNotificationManager");
    @Shadow
    @Final
    private AtomicLong elapsed;
    @Shadow
    @Final
    private long period;
    @Shadow
    @Final
    private List<Notification> notifications;
    @Shadow
    @Final
    private Minecraft minecraft;

    private static boolean checkFiltered(String title, String message) {
        NotificationFilterMode notificationMode = DisableComplianceNotification.getConfig().getNotificationFilterMode();
        boolean isFiltered = notificationMode.isFiltered(title, message);

        LOGGER.info("Detected Period Notification: {}, {}. [DCN-MODE: {}, Filtered: {}]", title, message, notificationMode.toEnumString(), isFiltered);
        return isFiltered;
    }

    // This follows original implementation of NotificationTask.run() method.
    // As this need to block specific "notification", it should inject the code.
    // So, I'm using original implementation with some custom expression..
    // Note: PeriodicNotificationManager only used for regional compliance notification as of 1.18.2.
    @Inject(
            method = "run()V",
            at = @At("HEAD"),
            cancellable = true,
            remap = false
    )
    public void run(CallbackInfo ci) {
        long previousElapsedTime = this.elapsed.getAndAdd(this.period);
        long currentElapsedTime = this.elapsed.get();

        for (Notification n : this.notifications) {
            // Get title and message earlier for comparison
            String title = n.title();
            String message = n.message();

            // Original method
            if (previousElapsedTime >= n.delay()) {
                long elapsedPeriod = previousElapsedTime / n.period();
                long currentPeriod = currentElapsedTime / n.period();

                if (elapsedPeriod != currentPeriod) {
                    // Check if the notification is disabled.
                    if (checkFiltered(title, message)) {
                        ci.cancel();
                        return;
                    }

                    this.minecraft.execute(() -> SystemToast.add(
                            Minecraft.getInstance().getToasts(),
                            SystemToast.SystemToastIds.PERIODIC_NOTIFICATION,
                            Component.translatable(title, elapsedPeriod),
                            Component.translatable(message, elapsedPeriod)
                    ));

                    // for safety.
                    ci.cancel();
                    return;
                }
            }
        }

        // for safety.
        ci.cancel();
    }
}
