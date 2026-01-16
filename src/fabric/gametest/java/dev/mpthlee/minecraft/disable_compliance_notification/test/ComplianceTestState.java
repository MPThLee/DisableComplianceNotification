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
    private static final AtomicInteger filteredCount = new AtomicInteger(0);
    private static final Set<String> filteredTitles = ConcurrentHashMap.newKeySet();
    private static TestLogAppender appender;

    private static final Pattern TITLE_PATTERN = Pattern.compile("title='([^']+)'");

    private static final Logger LOGGER = (Logger) LogManager.getLogger("ComplianceTestState");

    public static void startCapture() {
        filteredCount.set(0);
        filteredTitles.clear();
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

    public static int getUniqueFilteredTitleCount() {
        return filteredTitles.size();
    }

    public static Set<String> getFilteredTitles() {
        return Set.copyOf(filteredTitles);
    }

    private static class TestLogAppender extends AbstractAppender {
        protected TestLogAppender() {
            super("ComplianceTestAppender", null, null, true, Property.EMPTY_ARRAY);
        }

        @Override
        public void append(LogEvent event) {
            String message = event.getMessage().getFormattedMessage();

            System.out.println(message);

            if (message.contains("Filtered: true")) {
                filteredCount.incrementAndGet();

                Matcher matcher = TITLE_PATTERN.matcher(message);
                if (matcher.find()) {
                    filteredTitles.add(matcher.group(1));
                }
            }
        }
    }
}
