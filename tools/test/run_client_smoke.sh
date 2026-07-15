#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <forge|neoforge> [timeout-seconds]" >&2
    exit 2
fi

loader="$1"
timeout_seconds="${2:-180}"

case "$loader" in
    forge|neoforge) ;;
    *)
        echo "Unsupported smoke-test loader: $loader" >&2
        exit 2
        ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$(dirname "$script_dir")")"
loader_dir="$project_root/$loader"
output_file="$loader_dir/build/client-smoke.log"
game_log="$loader_dir/run/logs/latest.log"

mkdir -p "$loader_dir/build"
rm -f "$output_file" "$game_log"

set +e
(
    cd "$loader_dir"
    timeout "$timeout_seconds" xvfb-run -a ./gradlew runClient --console=plain
) 2>&1 | tee "$output_file"
exit_code=${PIPESTATUS[0]}
set -e

initialized=false
if grep -Fq "Initializing Disable Compliance Notification" "$output_file"; then
    initialized=true
elif [ -f "$game_log" ] && grep -Fq "Initializing Disable Compliance Notification" "$game_log"; then
    initialized=true
fi

if [ "$initialized" != true ]; then
    echo "$loader client never initialized Disable Compliance Notification" >&2
    exit 1
fi

case "$exit_code" in
    0)
        echo "$loader client initialized and exited cleanly"
        ;;
    124)
        echo "$loader client initialized and remained stable until the expected timeout"
        ;;
    *)
        echo "$loader client exited unexpectedly with code $exit_code" >&2
        exit "$exit_code"
        ;;
esac
