package dev.mpthlee.minecraft.disable_compliance_notification.test;

import dev.mpthlee.minecraft.disable_compliance_notification.DisableComplianceNotification;
import dev.mpthlee.minecraft.disable_compliance_notification.config.DCNConfigDefault;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.minecraft.client.Minecraft;
import net.minecraft.client.PeriodicNotificationManager.Notification;
import net.minecraft.client.gui.components.toasts.SystemToast;
import net.minecraft.client.gui.components.toasts.ToastManager;
import net.minecraft.network.chat.Component;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.lang.reflect.Constructor;
import java.util.List;
import java.util.TimerTask;

@SuppressWarnings("UnstableApiUsage")
public class ComplianceClientGameTest implements FabricClientGameTest {

    private static final Logger LOGGER = LogManager.getLogger("ComplianceClientGameTest");
    private static final String FILTERED_TITLE = "compliance.gametest.filtered.title";
    private static final String FILTERED_MESSAGE = "compliance.gametest.filtered.message";
    private static final String UNFILTERED_TITLE = "dcn.gametest.unfiltered.title";
    private static final String UNFILTERED_MESSAGE = "dcn.gametest.unfiltered.message";

    @Override
    public void runTest(ClientGameTestContext context) {
        LOGGER.info("Starting deterministic periodic notification client gametest");

        var previousConfig = DisableComplianceNotification.getConfig();
        DisableComplianceNotification.setConfig(new DCNConfigDefault());
        ComplianceTestState.startCapture();

        try {
            context.runOnClient(client -> {
                ToastManager toastManager = getToastManager(client);
                toastManager.clear();

                try {
                    SystemToast.add(
                            toastManager,
                            SystemToast.SystemToastId.PACK_COPY_FAILURE,
                            Component.translatable(FILTERED_TITLE),
                            Component.translatable(FILTERED_MESSAGE)
                    );
                    assertTrue(toastManager.getToast(
                            SystemToast.class,
                            SystemToast.SystemToastId.PACK_COPY_FAILURE
                    ) != null, "a non-periodic toast must remain untouched");
                    toastManager.clear();

                    createDueNotificationTask(FILTERED_TITLE, FILTERED_MESSAGE).run();
                } catch (RuntimeException | Error throwable) {
                    toastManager.clear();
                    throw throwable;
                }
            });

            context.waitTick();

            context.runOnClient(client -> {
                ToastManager toastManager = getToastManager(client);

                try {
                    assertEquals(1, ComplianceTestState.getDetectedCount(),
                            "the filtered notification should be detected once");
                    assertEquals(1, ComplianceTestState.getFilteredCount(),
                            "the compliance notification should be filtered");
                    assertEquals(0, ComplianceTestState.getPeriodicToastEnqueueCount(),
                            "the filtered notification must not enqueue a toast");
                    assertTrue(ComplianceTestState.getFilteredTitles().contains(FILTERED_TITLE),
                            "the filtered title should be captured");
                    assertTrue(toastManager.getToast(
                            SystemToast.class,
                            SystemToast.SystemToastId.PERIODIC_NOTIFICATION
                    ) == null, "a filtered notification must not enqueue a toast");

                    toastManager.clear();
                    createDueNotificationTask(UNFILTERED_TITLE, UNFILTERED_MESSAGE).run();
                } catch (RuntimeException | Error throwable) {
                    toastManager.clear();
                    throw throwable;
                }
            });

            context.waitTick();

            context.runOnClient(client -> {
                ToastManager toastManager = getToastManager(client);

                try {
                    assertEquals(2, ComplianceTestState.getDetectedCount(),
                            "both periodic notifications should be detected");
                    assertEquals(1, ComplianceTestState.getUnfilteredCount(),
                            "the non-compliance notification should remain unfiltered");
                    assertEquals(1, ComplianceTestState.getPeriodicToastEnqueueCount(),
                            "the unfiltered notification must enqueue exactly one toast");
                    assertTrue(ComplianceTestState.getUnfilteredTitles().contains(UNFILTERED_TITLE),
                            "the unfiltered title should be captured");
                    assertTrue(toastManager.getToast(
                            SystemToast.class,
                            SystemToast.SystemToastId.PERIODIC_NOTIFICATION
                    ) != null, "an unfiltered notification should enqueue a periodic toast");
                } finally {
                    toastManager.clear();
                }
            });

            LOGGER.info("Deterministic periodic notification client gametest passed");
        } finally {
            ComplianceTestState.stopCapture();
            DisableComplianceNotification.setConfig(previousConfig);
        }
    }

    private static TimerTask createDueNotificationTask(String title, String message) {
        try {
            Class<?> notificationTaskClass = Class.forName(
                    "net.minecraft.client.PeriodicNotificationManager$NotificationTask");
            Constructor<?> constructor = notificationTaskClass.getDeclaredConstructor(
                    List.class, long.class, long.class);
            constructor.setAccessible(true);

            return (TimerTask) constructor.newInstance(
                    List.of(new Notification(1L, 1L, title, message)),
                    1L,
                    1L
            );
        } catch (ReflectiveOperationException exception) {
            throw new AssertionError("Unable to construct a due periodic notification task", exception);
        }
    }

    private static ToastManager getToastManager(Minecraft client) {
        try {
            try {
                return (ToastManager) Minecraft.class
                        .getMethod("getToastManager")
                        .invoke(client);
            } catch (NoSuchMethodException ignored) {
                Object gui = Minecraft.class.getField("gui").get(client);
                return (ToastManager) gui.getClass()
                        .getMethod("toastManager")
                        .invoke(gui);
            }
        } catch (ReflectiveOperationException exception) {
            throw new AssertionError("Unable to access Minecraft's toast manager", exception);
        }
    }

    private static void assertEquals(int expected, int actual, String message) {
        if (expected != actual) {
            throw new AssertionError(message + ": expected " + expected + ", got " + actual);
        }
    }

    private static void assertTrue(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
