package dev.mpthlee.minecraft.disable_compliance_notification.test;

import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.fabricmc.fabric.api.client.gametest.v1.context.TestSingleplayerContext;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

@SuppressWarnings("UnstableApiUsage")
public class ComplianceClientGameTest implements FabricClientGameTest {

    private static final Logger LOGGER = LogManager.getLogger("ComplianceClientGameTest");
    private static final int WAIT_TICKS = 20 * 60 * 2 + 30;
    private static final int REQUIRED_FILTERED_COUNT = 2;
    private static final int REQUIRED_UNIQUE_TITLES = 1;

    @Override
    public void runTest(ClientGameTestContext context) {
        LOGGER.info("Starting client gametest");
        LOGGER.info("Expecting at least {} filtered notifications with {} unique titles",
                REQUIRED_FILTERED_COUNT, REQUIRED_UNIQUE_TITLES);

        ComplianceTestState.startCapture();

        context.runOnClient(client -> {
            LOGGER.info("Enabling compliance resourcepack...");
            var packRepo = client.getResourcePackRepository();
            packRepo.reload();

            var compliancePack = packRepo.getPack("file/compliance.zip");
            if (compliancePack != null) {
                LOGGER.info("Found compliance.zip, enabling it");
                packRepo.setSelected(java.util.List.of(compliancePack.getId()));
                client.reloadResourcePacks();
            } else {
                LOGGER.warn("compliance.zip not found in resourcepacks!");
                packRepo.getAvailablePacks().forEach(p -> LOGGER.info("Available pack: {}", p.getId()));
            }
        });

        context.waitTicks(20);

        LOGGER.info("Creating singleplayer world...");

        try (TestSingleplayerContext singleplayer = context.worldBuilder().create()) {
            singleplayer.getClientLevel().waitForChunksRender();
            LOGGER.info("World loaded, waiting {} ticks ({} seconds)", WAIT_TICKS, WAIT_TICKS / 20);

            for (int i = 0; i < WAIT_TICKS; i++) {
                context.waitTick();

                int filteredCount = ComplianceTestState.getFilteredCount();
                int uniqueTitles = ComplianceTestState.getUniqueFilteredTitleCount();

                if (filteredCount >= REQUIRED_FILTERED_COUNT && uniqueTitles >= REQUIRED_UNIQUE_TITLES) {
                    LOGGER.info("SUCCESS at tick {}: {} notifications filtered, {} unique titles: {}",
                            i, filteredCount, uniqueTitles, ComplianceTestState.getFilteredTitles());
                    ComplianceTestState.stopCapture();
                    return;
                }

                if (i % 600 == 0) {
                    LOGGER.info("Progress: {} sec | filtered: {}, unique titles: {}",
                            i / 20, filteredCount, uniqueTitles);
                }
            }

            ComplianceTestState.stopCapture();

            int filteredCount = ComplianceTestState.getFilteredCount();
            int uniqueTitles = ComplianceTestState.getUniqueFilteredTitleCount();

            if (filteredCount >= REQUIRED_FILTERED_COUNT && uniqueTitles >= REQUIRED_UNIQUE_TITLES) {
                LOGGER.info("SUCCESS: {} notifications filtered, {} unique titles: {}",
                        filteredCount, uniqueTitles, ComplianceTestState.getFilteredTitles());
            } else {
                throw new AssertionError(String.format(
                        "FAILED: Expected at least %d filtered with %d unique titles, got %d filtered with %d unique titles: %s",
                        REQUIRED_FILTERED_COUNT, REQUIRED_UNIQUE_TITLES,
                        filteredCount, uniqueTitles, ComplianceTestState.getFilteredTitles()));
            }
        }
    }
}
