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

detect_java

echo "=== Release Build ==="
echo "Java version: $JAVA_VERSION"
[ -n "$JAVA_HOME" ] && echo "JAVA_HOME: $JAVA_HOME"
echo ""

name="disable_compliance_notification"

echo "=== Fabric ==="
cd "$PROJECT_ROOT/fabric"

chmod +x ./gradlew
./gradlew build

version=$(./gradlew properties | grep ^version: | cut -d ':' -f2 | xargs)

echo "=== NeoForge ==="
cd "$PROJECT_ROOT/neoforge"

chmod +x ./gradlew
./gradlew build

cd "$PROJECT_ROOT"
mkdir -p release/
cp fabric/build/libs/$name-$version.jar release/
cp neoforge/build/libs/$name-$version.jar release/

echo ""
echo "=== Release files ==="
ls -la release/
