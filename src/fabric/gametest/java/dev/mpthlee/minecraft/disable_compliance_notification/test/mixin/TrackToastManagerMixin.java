package dev.mpthlee.minecraft.disable_compliance_notification.test.mixin;

import dev.mpthlee.minecraft.disable_compliance_notification.test.ComplianceTestState;
import net.minecraft.client.gui.components.toasts.Toast;
import net.minecraft.client.gui.components.toasts.ToastManager;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ToastManager.class)
public abstract class TrackToastManagerMixin {
    @Inject(
            method = "addToast(Lnet/minecraft/client/gui/components/toasts/Toast;)V",
            at = @At("HEAD"),
            remap = false
    )
    private void recordPeriodicToast(Toast toast, CallbackInfo ci) {
        ComplianceTestState.recordToast(toast);
    }
}
