#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config.properties"

read_config() {
    grep "^$1=" "$CONFIG_FILE" | cut -d'=' -f2
}

JAVA_VERSION=$(read_config "java_version")

detect_java() {
    if [ -n "$JAVA_HOME" ]; then
        return
    elif command -v /usr/libexec/java_home &> /dev/null; then
        export JAVA_HOME="$(/usr/libexec/java_home -v $JAVA_VERSION 2>/dev/null || true)"
    elif [ -d "$HOME/.sdkman/candidates/java" ]; then
        local java_path=$(find "$HOME/.sdkman/candidates/java" -maxdepth 2 -name "java" -path "*$JAVA_VERSION*" 2>/dev/null | head -1)
        if [ -n "$java_path" ]; then
            export JAVA_HOME="$(dirname "$(dirname "$java_path")")"
        fi
    elif [ -d "/usr/lib/jvm" ]; then
        local jvm_dir=$(find /usr/lib/jvm -maxdepth 1 -type d -name "*$JAVA_VERSION*" 2>/dev/null | head -1)
        if [ -n "$jvm_dir" ]; then
            export JAVA_HOME="$jvm_dir"
        fi
    fi
}

usage() {
    echo "Usage: $0 <loader> [options]"
    echo ""
    echo "Loaders: fabric, neoforge, forge"
    echo ""
    echo "Options:"
    echo "  --xvfb       Use Xvfb for headless display (Linux)"
    echo "  --server     Run server gametest only (fabric only)"
    echo "  --help       Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 fabric              # Run Fabric client gametest"
    echo "  $0 fabric --xvfb       # Run Fabric client gametest headless"
    echo "  $0 fabric --server     # Run Fabric server gametest"
    echo "  $0 neoforge            # Run NeoForge client (manual /test)"
    echo "  $0 forge               # Run Forge client (manual /test)"
    echo ""
    echo "Note: NeoForge/Forge are client-only mods, so automated gametest"
    echo "      is only available for Fabric. Use runClient for manual testing."
}

LOADER=""
USE_XVFB=false
SERVER_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        fabric|neoforge|forge)
            LOADER="$1"
            shift
            ;;
        --xvfb)
            USE_XVFB=true
            shift
            ;;
        --server)
            SERVER_ONLY=true
            shift
            ;;
        --help|-h)
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

if [ ! -d "$LOADER_DIR" ]; then
    echo "Error: Loader directory not found: $LOADER_DIR"
    exit 1
fi

detect_java

echo "=== GameTest Runner ==="
echo "Loader: $LOADER"
echo "Java version: $JAVA_VERSION"
[ -n "$JAVA_HOME" ] && echo "JAVA_HOME: $JAVA_HOME"
echo ""

cd "$LOADER_DIR"

export _JAVA_OPTIONS="-Duser.country=KR -Duser.language=ko"

run_cmd() {
    if [ "$USE_XVFB" = true ]; then
        xvfb-run -a "$@"
    else
        "$@"
    fi
}

case "$LOADER" in
    fabric)
        if [ "$SERVER_ONLY" = true ]; then
            echo "Running Fabric server gametest..."
            run_cmd ./gradlew runGameTest
        else
            echo "Running Fabric client gametest..."
            run_cmd ./gradlew runClientGameTest
        fi
        ;;
    neoforge|forge)
        echo "Running $LOADER client..."
        echo "Note: This mod is client-only. Use /test command in-game for manual testing."
        run_cmd ./gradlew runClient
        ;;
esac
