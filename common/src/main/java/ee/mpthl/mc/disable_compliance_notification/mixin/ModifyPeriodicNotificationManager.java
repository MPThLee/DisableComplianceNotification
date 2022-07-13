package ee.mpthl.mc.disable_compliance_notification.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

// TODO: Nested Class `NotificationTask` doesn't exposed in 1.18.2 mojmap.
@Mixin(targets = "net.minecraft.client.PeriodicNotificationManager$NotificationTask")
public class ModifyPeriodicNotificationManager {
	private static final Logger LOGGER = LogManager.getLogger("ModifyPeriodicNotificationManager");
	// TODO: Make sure only remove Compliance Notification for future.
	// Note: PeriodicNotificationManager only used for regional compliance notification as of 1.18.2.
	@Inject(at = @At("HEAD"), cancellable = true, method = "Lnet/minecraft/client/PeriodicNotificationManager$NotificationTask;run()V")
	private void run(CallbackInfo info) {
		LOGGER.info("Cancel NotificationTask run call...");
		info.cancel();
	}
}