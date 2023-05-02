package ee.mpthl.mc.disable_compliance_notification.config;

public enum NotificationMode {
    DISABLE_COMPLETELY, // Disable all period notifications
    ONLY_COMPLIANCE, // Enable only compliance notifications
    ONLY_NON_COMPLIANCE, // Enable only non-compliance notifications
    ALL; // Enable both compliance and non-compliance notifications

    public boolean isDisabled() {
        return this == DISABLE_COMPLETELY;
    }

    public boolean isCompliance() {
        return this == ONLY_COMPLIANCE || this == ALL;
    }

    public boolean isNonCompliance() {
        return this == ONLY_NON_COMPLIANCE || this == ALL;
    }
}