package dev.mpthlee.minecraft.disable_compliance_notification.test;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ComplianceTestState {
    private static final AtomicInteger detectedCount = new AtomicInteger(0);
    private static final AtomicInteger filteredCount = new AtomicInteger(0);
    private static final AtomicInteger unfilteredCount = new AtomicInteger(0);
    private static final Set<String> filteredTitles = ConcurrentHashMap.newKeySet();
    private static final Set<String> unfilteredTitles = ConcurrentHashMap.newKeySet();
    private static TestLogAppender appender;

    private static final Pattern TITLE_PATTERN = Pattern.compile("title='([^']+)'");

    public static void startCapture() {
        stopCapture();
        detectedCount.set(0);
        filteredCount.set(0);
        unfilteredCount.set(0);
        filteredTitles.clear();
        unfilteredTitles.clear();
        appender = new TestLogAppender();
        appender.start();

        Logger logger = (Logger) LogManager.getLogger("ModifyPeriodicNotificationManager");
        logger.addAppender(appender);
    }

    public static void stopCapture() {
        if (appender != null) {
            Logger logger = (Logger) LogManager.getLogger("ModifyPeriodicNotificationManager");
            logger.removeAppender(appender);
            appender.stop();
            appender = null;
        }
    }

    public static int getFilteredCount() {
        return filteredCount.get();
    }

    public static int getDetectedCount() {
        return detectedCount.get();
    }

    public static int getUnfilteredCount() {
        return unfilteredCount.get();
    }

    public static Set<String> getFilteredTitles() {
        return Set.copyOf(filteredTitles);
    }

    public static Set<String> getUnfilteredTitles() {
        return Set.copyOf(unfilteredTitles);
    }

    private static class TestLogAppender extends AbstractAppender {
        protected TestLogAppender() {
            super("ComplianceTestAppender", null, null, true, Property.EMPTY_ARRAY);
        }

        @Override
        public void append(LogEvent event) {
            String message = event.getMessage().getFormattedMessage();

            System.out.println(message);

            if (!message.contains("Detected Period Notification:")) {
                return;
            }

            detectedCount.incrementAndGet();

            Matcher matcher = TITLE_PATTERN.matcher(message);
            String title = matcher.find() ? matcher.group(1) : null;

            if (message.contains("Filtered: true")) {
                filteredCount.incrementAndGet();

                if (title != null) {
                    filteredTitles.add(title);
                }
            } else if (message.contains("Filtered: false")) {
                unfilteredCount.incrementAndGet();

                if (title != null) {
                    unfilteredTitles.add(title);
                }
            }
        }
    }
}
