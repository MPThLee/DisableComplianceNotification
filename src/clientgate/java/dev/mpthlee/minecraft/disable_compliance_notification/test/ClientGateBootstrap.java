package dev.mpthlee.minecraft.disable_compliance_notification.test;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.toasts.SystemToast;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import net.minecraft.network.chat.contents.TranslatableContents;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Supplier;

public final class ClientGateBootstrap {
    private static final Logger LOGGER = LogManager.getLogger("ClientGateBootstrap");
    private static final AtomicBoolean STARTED = new AtomicBoolean();
    private static final long WORLD_START_TIMEOUT_SECONDS = 180;
    private static final long MINIMUM_GATE_RUNTIME_SECONDS = 120;
    private static final long DEFAULT_GATE_RUNTIME_SECONDS = 150;
    private static final String TOAST_OBSERVED_MARKER =
            "DCN compliance gate observed a periodic toast in ToastManager";
    private static final String NO_TOAST_MARKER =
            "DCN compliance gate verified no periodic toast was present in ToastManager";

    private ClientGateBootstrap() {
    }

    public static void start() {
        if (!STARTED.compareAndSet(false, true)) {
            return;
        }

        Thread thread = new Thread(ClientGateBootstrap::createAndEnterWorld, "DCN client gate world starter");
        thread.setDaemon(true);
        thread.start();
    }

    private static void createAndEnterWorld() {
        try {
            Minecraft client = waitForClient();
            waitFor(client, () -> client.gui != null && client.gui.screen() != null && client.level == null);
            Thread.sleep(2_000);
            LOGGER.info(
                    "DCN client gate opening world from screen: {}",
                    runOnClient(client, () -> client.gui.screen().getClass().getName())
            );

            runOnClient(client, () -> {
                CreateWorldScreen.openFresh(
                        client,
                        () -> client.gui.setScreen(new TitleScreen())
                );
                return null;
            });

            String worldName = System.getProperty("dcn.client.gate.worldName");
            if (worldName == null || worldName.isBlank()) {
                throw new IllegalStateException("dcn.client.gate.worldName is required");
            }
            startWorldWhenReady(client, worldName);

            waitFor(client, () -> client.level != null && client.player != null);
            runOnClient(client, () -> {
                client.gui.toastManager().clear();
                return null;
            });
            LOGGER.info(
                    "DCN compliance gate entered world: {}",
                    System.getProperty("dcn.client.gate.worldName")
            );
            verifyNoPeriodicToast(client);
        } catch (Throwable throwable) {
            LOGGER.error("DCN compliance gate failed to enter a singleplayer world", throwable);
        }
    }

    private static void startWorldWhenReady(Minecraft client, String worldName) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WORLD_START_TIMEOUT_SECONDS);
        while (System.nanoTime() < deadline) {
            boolean started = runOnClient(client, () -> {
                if (!(client.gui.screen() instanceof CreateWorldScreen screen)) {
                    return false;
                }

                Button createButton = screen.children().stream()
                        .filter(Button.class::isInstance)
                        .map(Button.class::cast)
                        .filter(ClientGateBootstrap::isCreateWorldButton)
                        .findFirst()
                        .orElse(null);
                if (createButton == null) {
                    return false;
                }

                screen.getUiState().setName(worldName);
                createButton.onPress(null);
                return true;
            });
            if (started) {
                return;
            }
            Thread.sleep(100);
        }
        throw new IllegalStateException("Timed out waiting for the create-world screen and button");
    }

    private static void verifyNoPeriodicToast(Minecraft client) throws Exception {
        long runtimeSeconds = Long.getLong(
                "dcn.client.gate.runtimeSeconds",
                DEFAULT_GATE_RUNTIME_SECONDS
        );
        if (runtimeSeconds < MINIMUM_GATE_RUNTIME_SECONDS) {
            throw new IllegalStateException(
                    "dcn.client.gate.runtimeSeconds must be at least "
                            + MINIMUM_GATE_RUNTIME_SECONDS
            );
        }

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(runtimeSeconds);
        while (System.nanoTime() < deadline) {
            boolean periodicToastPresent = runOnClient(client, () ->
                    client.gui.toastManager().getToast(
                            SystemToast.class,
                            SystemToast.SystemToastId.PERIODIC_NOTIFICATION
                    ) != null
            );
            if (periodicToastPresent) {
                LOGGER.error(TOAST_OBSERVED_MARKER);
                return;
            }
            Thread.sleep(50);
        }
        LOGGER.info(NO_TOAST_MARKER);
    }

    private static boolean isCreateWorldButton(Button button) {
        return button.getMessage().getContents() instanceof TranslatableContents translatable
                && "selectWorld.create".equals(translatable.getKey());
    }

    private static Minecraft waitForClient() throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WORLD_START_TIMEOUT_SECONDS);
        while (System.nanoTime() < deadline) {
            Minecraft client = Minecraft.getInstance();
            if (client != null) {
                return client;
            }
            Thread.sleep(100);
        }
        throw new IllegalStateException("Timed out waiting for the Minecraft client singleton");
    }

    private static void waitFor(Minecraft client, Supplier<Boolean> condition) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WORLD_START_TIMEOUT_SECONDS);
        while (System.nanoTime() < deadline) {
            if (runOnClient(client, condition)) {
                return;
            }
            Thread.sleep(100);
        }
        throw new IllegalStateException("Timed out while creating the client-gate world");
    }

    private static <T> T runOnClient(Minecraft client, Supplier<T> action) throws Exception {
        CompletableFuture<T> future = new CompletableFuture<>();
        client.execute(() -> {
            try {
                future.complete(action.get());
            } catch (Throwable throwable) {
                future.completeExceptionally(throwable);
            }
        });
        return future.get(30, TimeUnit.SECONDS);
    }
}
