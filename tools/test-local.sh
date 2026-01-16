#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    echo "Usage: $0 <loader> [options]"
    echo ""
    echo "Loaders: fabric, neoforge, forge"
    echo ""
    echo "Options:"
    echo "  --build          Build the mod before testing (default: false)"
    echo "  --timeout <sec>  Timeout in seconds (default: 200, ~3.3 min for both notifications)"
    echo "  --verify-only    Only verify existing logs, don't run client"
    echo "  --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 fabric --build"
    echo "  $0 neoforge --timeout 300"
    echo "  $0 fabric --verify-only"
}

LOADER=""
BUILD=false
TIMEOUT=200
VERIFY_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        fabric|neoforge|forge)
            LOADER="$1"
            shift
            ;;
        --build)
            BUILD=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ -z "$LOADER" ]; then
    echo "Error: loader is required"
    usage
    exit 1
fi

LOADER_DIR="$PROJECT_ROOT/$LOADER"
RUN_DIR="$LOADER_DIR/run"

if [ ! -d "$LOADER_DIR" ]; then
    echo "Error: Loader directory not found: $LOADER_DIR"
    exit 1
fi

echo "=== Local Compliance Test ==="
echo "Loader: $LOADER"
echo "Project: $PROJECT_ROOT"
echo ""

if [ "$VERIFY_ONLY" = true ]; then
    echo "Verifying existing logs..."
    "$SCRIPT_DIR/verify-compliance-log.sh" "$RUN_DIR"
    exit $?
fi

if [ "$BUILD" = true ]; then
    echo "Building mod..."
    cd "$LOADER_DIR"
    ./gradlew build
    echo ""
fi

echo "Preparing test environment..."
mkdir -p "$RUN_DIR/mods"
mkdir -p "$RUN_DIR/resourcepacks"

MOD_JAR=$(find "$LOADER_DIR/build/libs" -name "*.jar" ! -name "*-dev*" ! -name "*-sources*" ! -name "*-javadoc*" 2>/dev/null | head -1)
if [ -z "$MOD_JAR" ]; then
    echo "Error: No mod JAR found. Run with --build first."
    exit 1
fi

cp "$MOD_JAR" "$RUN_DIR/mods/"
cp "$PROJECT_ROOT/misc/compliance.zip" "$RUN_DIR/resourcepacks/"

echo "Mod JAR: $MOD_JAR"
echo "Resourcepack: compliance.zip"
echo ""

echo "=== MANUAL TEST INSTRUCTIONS ==="
echo ""
echo "1. Run the client:"
echo "   cd $LOADER_DIR && ./gradlew runClient"
echo ""
echo "2. In-game setup:"
echo "   - Go to Options > Resource Packs"
echo "   - Enable 'compliance.zip' (or 'compliance')"
echo "   - Create/load a singleplayer world"
echo ""
echo "3. Wait for ~2 minutes in-game"
echo "   (The test resourcepack triggers notifications every 1 minute)"
echo ""
echo "4. After seeing the notification (or waiting 2+ mins), exit the game"
echo ""
echo "5. Verify the logs:"
echo "   $SCRIPT_DIR/verify-compliance-log.sh $RUN_DIR"
echo ""
echo "=== OR RUN WITH TIMEOUT ==="
echo ""
echo "Starting client with $TIMEOUT second timeout..."
echo "(You still need to manually enable resourcepack and enter a world)"
echo ""

cd "$LOADER_DIR"

if command -v timeout &> /dev/null; then
    timeout --signal=SIGTERM $TIMEOUT ./gradlew runClient || true
elif command -v gtimeout &> /dev/null; then
    gtimeout --signal=SIGTERM $TIMEOUT ./gradlew runClient || true
else
    echo "Note: 'timeout' command not found. Running without timeout."
    echo "Press Ctrl+C to stop the client when done testing."
    ./gradlew runClient || true
fi

echo ""
echo "Client stopped. Verifying logs..."
"$SCRIPT_DIR/verify-compliance-log.sh" "$RUN_DIR"
