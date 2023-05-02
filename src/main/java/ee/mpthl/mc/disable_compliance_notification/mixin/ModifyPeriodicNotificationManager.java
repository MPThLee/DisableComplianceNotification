package ee.mpthl.mc.disable_compliance_notification.mixin;

import ee.mpthl.mc.disable_compliance_notification.DisableComplianceNotification;
import ee.mpthl.mc.disable_compliance_notification.SkipHelper;
import ee.mpthl.mc.disable_compliance_notification.config.DCNConfigInterface;
import ee.mpthl.mc.disable_compliance_notification.config.NotificationMode;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.toasts.SystemToast;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import java.util.concurrent.atomic.AtomicLong;
import net.minecraft.client.PeriodicNotificationManager.Notification;


import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

// TODO: Nested Class `NotificationTask` doesn't exposed in 1.18.2 mojmap.
@Mixin(targets = "net.minecraft.client.PeriodicNotificationManager$NotificationTask")
public class ModifyPeriodicNotificationManager {
	@Shadow @Final private AtomicLong elapsed;
	@Shadow @Final private long period;
	@Shadow @Final private List<Notification> notifications;
	@Shadow @Final private Minecraft minecraft;
	private static final Logger LOGGER = LogManager.getLogger("ModifyPeriodicNotificationManager");

	// This follows original implementation of NotificationTask.run() method.
	// As this need to block specific "notification", it should inject the code.
	// So, I override the original implementation. with just one more if expression.
	// Note: PeriodicNotificationManager only used for regional compliance notification as of 1.18.2.
	@Inject(
			method = "run()V",
			at = @At("HEAD"),
			cancellable = true
    )
    public void run(CallbackInfo ci) {
		long previousElapsedTime = this.elapsed.getAndAdd(this.period);
		long currentElapsedTime = this.elapsed.get();

		for (Notification n: this.notifications) {
			// Get title and message earlier for comparison
			String title = n.title();
			String message = n.message();

			// Original method
			if (previousElapsedTime >= n.delay()) {
				long elapsedPeriod = previousElapsedTime / n.period();
				long currentPeriod = currentElapsedTime / n.period();

				if (elapsedPeriod != currentPeriod) {
					// Check if the notification is disabled.
					if (SkipHelper.checkSkip(LOGGER, title, message)) {
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
