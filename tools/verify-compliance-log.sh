#!/bin/bash
set -e

RUN_DIR="${1:-.}"
REQUIRED_COUNT="${2:-2}"

LOG_PATTERNS=(
    "logs/latest.log"
    "logs/debug.log"
    "*.log"
)

SEARCH_PATTERN="Detected Period Notification:"
SUCCESS_PATTERN="Filtered: true"
HOURLY_PATTERN="compliance.playtime.hours"
DAILY_PATTERN="compliance.playtime.greaterThan24Hours"

echo "=== Compliance Notification Log Verification ==="
echo "Run directory: $RUN_DIR"
echo "Required filtered count: $REQUIRED_COUNT"
echo ""

find_log_file() {
    for pattern in "${LOG_PATTERNS[@]}"; do
        if compgen -G "$RUN_DIR/$pattern" > /dev/null 2>&1; then
            for f in $RUN_DIR/$pattern; do
                if [ -f "$f" ]; then
                    echo "$f"
                    return 0
                fi
            done
        fi
    done
    return 1
}

LOG_FILE=$(find_log_file)
if [ -z "$LOG_FILE" ]; then
    echo "ERROR: No log file found in $RUN_DIR"
    echo "Searched patterns: ${LOG_PATTERNS[*]}"
    exit 1
fi

echo "Using log file: $LOG_FILE"
echo ""

MATCHES=$(grep -n "$SEARCH_PATTERN" "$LOG_FILE" 2>/dev/null || true)

if [ -z "$MATCHES" ]; then
    echo "FAIL: No compliance notification detected in logs"
    echo ""
    echo "Expected log pattern: $SEARCH_PATTERN"
    echo ""
    echo "=== Last 50 lines of log ==="
    tail -50 "$LOG_FILE"
    exit 1
fi

echo "=== Detected Compliance Notifications ==="
echo "$MATCHES"
echo ""

FILTERED_MATCHES=$(echo "$MATCHES" | grep "$SUCCESS_PATTERN" || true)
FILTERED_COUNT=$(echo "$FILTERED_MATCHES" | grep -c . || true)
TOTAL_COUNT=$(echo "$MATCHES" | wc -l | tr -d ' ')

HOURLY_FILTERED=$(echo "$FILTERED_MATCHES" | grep -c "$HOURLY_PATTERN" || true)
DAILY_FILTERED=$(echo "$FILTERED_MATCHES" | grep -c "$DAILY_PATTERN" || true)

echo "Total notifications detected: $TOTAL_COUNT"
echo "Successfully filtered: $FILTERED_COUNT"
echo "  - Hourly (playtime.hours): $HOURLY_FILTERED"
echo "  - Daily (greaterThan24Hours): $DAILY_FILTERED"
echo ""

if [ "$FILTERED_COUNT" -ge "$REQUIRED_COUNT" ]; then
    echo "SUCCESS: $FILTERED_COUNT notifications filtered (required: $REQUIRED_COUNT)"
    if [ "$HOURLY_FILTERED" -gt 0 ] && [ "$DAILY_FILTERED" -gt 0 ]; then
        echo "VERIFIED: Both hourly and daily notifications were filtered"
    fi
    exit 0
elif [ "$FILTERED_COUNT" -gt 0 ]; then
    echo "PARTIAL: Only $FILTERED_COUNT notification(s) filtered (required: $REQUIRED_COUNT)"
    echo "Wait longer in-game to trigger more notifications"
    exit 1
else
    echo "FAIL: Notifications detected but none were filtered"
    echo "Check if NotificationFilterMode is set correctly"
    exit 1
fi
