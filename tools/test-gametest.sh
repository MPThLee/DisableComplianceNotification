#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/fabric"

export _JAVA_OPTIONS="-Duser.country=KR -Duser.language=ko"

if [[ "$1" == "--xvfb" ]]; then
    shift
    exec xvfb-run -a ./gradlew runClientGameTest "$@"
else
    exec ./gradlew runClientGameTest "$@"
fi
