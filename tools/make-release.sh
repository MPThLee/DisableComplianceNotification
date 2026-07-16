#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config.properties"

read_config() {
    grep "^$1=" "$CONFIG_FILE" | cut -d'=' -f2
}

JAVA_VERSION=$(read_config "java_version")
MOD_VERSION=$(read_config "mod_version")
MINECRAFT_VERSION=$(read_config "minecraft_version")
ARCHIVES_BASE_NAME=$(read_config "archives_base_name")

detect_java() {
    if [ -n "${JAVA_HOME:-}" ]; then
        return
    elif command -v /usr/libexec/java_home &> /dev/null; then
        JAVA_HOME="$(/usr/libexec/java_home -v "$JAVA_VERSION" 2>/dev/null || true)"
        export JAVA_HOME
    elif [ -d "${HOME:-}/.sdkman/candidates/java" ]; then
        local java_path
        java_path=$(find "$HOME/.sdkman/candidates/java" -maxdepth 2 -name "java" -path "*$JAVA_VERSION*" 2>/dev/null | head -1)
        if [ -n "$java_path" ]; then
            JAVA_HOME="$(dirname "$(dirname "$java_path")")"
            export JAVA_HOME
        fi
    elif [ -d "/usr/lib/jvm" ]; then
        local jvm_dir
        jvm_dir=$(find /usr/lib/jvm -maxdepth 1 -type d -name "*$JAVA_VERSION*" 2>/dev/null | head -1)
        if [ -n "$jvm_dir" ]; then
            JAVA_HOME="$jvm_dir"
            export JAVA_HOME
        fi
    fi
}

detect_java

echo "=== Release Build ==="
echo "Java version: $JAVA_VERSION"
[ -n "${JAVA_HOME:-}" ] && echo "JAVA_HOME: $JAVA_HOME"
echo ""

for loader in fabric neoforge forge; do
    echo "=== ${loader} ==="
    cd "$PROJECT_ROOT/$loader"
    chmod +x ./gradlew
    ./gradlew clean build --console=plain
done

cd "$PROJECT_ROOT"
mkdir -p release/
for loader in fabric neoforge forge; do
    artifact="$loader/build/libs/$ARCHIVES_BASE_NAME-v$MOD_VERSION+$loader-$MINECRAFT_VERSION.jar"
    if [ ! -f "$artifact" ]; then
        echo "Missing release artifact: $artifact" >&2
        exit 1
    fi
    cp "$artifact" release/
done

echo ""
echo "=== Release files ==="
ls -la release/
