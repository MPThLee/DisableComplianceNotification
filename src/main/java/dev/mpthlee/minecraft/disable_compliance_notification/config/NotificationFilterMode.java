package dev.mpthlee.minecraft.disable_compliance_notification.config;

import net.minecraft.network.chat.Component;

public enum NotificationFilterMode {
    DISABLE, // Disable Notification Filter
    ONLY_COMPLIANCE, // Filter Only Compliance 
    ONLY_NON_COMPLIANCE, // Filter only non-compliance notifications
    ALL; // Enable both compliance and non-compliance notifications


    public boolean isFiltered(String title, String message) {
        boolean isComplianceMessage = title.startsWith("compliance") && message.startsWith("compliance.");

        return switch (this) {
            case DISABLE -> false;
            case ONLY_COMPLIANCE -> isComplianceMessage;
            case ONLY_NON_COMPLIANCE -> !isComplianceMessage;
            case ALL -> true;
        };
    }

    public String toEnumString() {
        return super.toString();
    }
    @Override
    public String toString() {
        return Component.translatable("config.disable_compliance_notification.filter_mode." + super.toString()).getString();
    }
}