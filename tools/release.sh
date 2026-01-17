#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/config.properties"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

print_error() {
    echo -e "${RED}Error:${NC} $1"
}

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Automated release script for DisableComplianceNotification mod.

OPTIONS:
    -g, --game VERSION      Minecraft version (e.g., 1.21.6) [required]
    -v, --version VERSION   Mod version (e.g., 1.5.0) [required]
    -p, --push              Push branch and tag to remote
    -n, --no-test           Skip build and test step
    --no-update-version     Skip update-version.py (dependency version fetch)
    -h, --help              Show this help message

WORKFLOW:
    1. Create mc<minecraft_version> branch
    2. Update mod_version in config.properties
    3. Fetch dependency versions via update-version.py (unless --no-update-version)
    4. Build and test (fabric, neoforge)
    5. Update DOWNLOAD.md and README.md via make-template.py
    6. Commit changes
    7. Tag release (v<mod_version>)
    8. Push to remote (if --push specified)

EXAMPLES:
    $(basename "$0") -g 1.21.6 -v 1.5.0
    $(basename "$0") -g 1.21.6 -v 1.5.0 --push
    $(basename "$0") -g 1.21.6 -v 1.5.0 --no-test --push
EOF
    exit 0
}

# Parse arguments
GAME_VERSION=""
MOD_VERSION=""
PUSH_REMOTE=false
SKIP_TEST=false
SKIP_UPDATE_VERSION=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--game)
            GAME_VERSION="$2"
            shift 2
            ;;
        -v|--version)
            MOD_VERSION="$2"
            shift 2
            ;;
        -p|--push)
            PUSH_REMOTE=true
            shift
            ;;
        -n|--no-test)
            SKIP_TEST=true
            shift
            ;;
        --no-update-version)
            SKIP_UPDATE_VERSION=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$GAME_VERSION" ] || [ -z "$MOD_VERSION" ]; then
    print_error "Both --game and --version are required"
    usage
fi

# Ensure mod version has 'v' prefix for tag
MOD_VERSION_TAG="v${MOD_VERSION#v}"
MOD_VERSION_CLEAN="${MOD_VERSION#v}"

BRANCH_NAME="mc${GAME_VERSION}"

cd "$PROJECT_ROOT"

# Read current config
read_config() {
    grep "^$1=" "$CONFIG_FILE" | cut -d'=' -f2
}

JAVA_VERSION=$(read_config "java_version")

# Detect Java
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

echo ""
echo "============================================"
echo "  DisableComplianceNotification Release"
echo "============================================"
echo ""
echo "  Minecraft Version: $GAME_VERSION"
echo "  Mod Version:       $MOD_VERSION_TAG"
echo "  Branch:            $BRANCH_NAME"
echo "  Java Version:      $JAVA_VERSION"
[ -n "$JAVA_HOME" ] && echo "  JAVA_HOME:         $JAVA_HOME"
echo ""
echo "============================================"
echo ""

# Confirm
read -p "Proceed with release? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Step 1: Create branch
print_step "Step 1/8: Creating branch '$BRANCH_NAME'"
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    print_warning "Branch '$BRANCH_NAME' already exists. Switching to it."
    git checkout "$BRANCH_NAME"
else
    git checkout -b "$BRANCH_NAME"
fi

# Step 2: Update mod_version in config.properties
print_step "Step 2/8: Updating mod_version in config.properties"
sed -i.bak "s/^mod_version=.*/mod_version=$MOD_VERSION_CLEAN/" "$CONFIG_FILE"
rm -f "$CONFIG_FILE.bak"
echo "  Updated mod_version=$MOD_VERSION_CLEAN"

# Step 3: Fetch dependency versions via update-version.py
if [ "$SKIP_UPDATE_VERSION" = false ]; then
    print_step "Step 3/8: Fetching dependency versions via update-version.py"
    python3 "$SCRIPT_DIR/update-version.py" --to "$GAME_VERSION" --config "$CONFIG_FILE" --oldest
    echo "  Dependency versions updated!"
else
    print_step "Step 3/8: Skipping update-version.py (--no-update-version)"
    # Still need to update minecraft_version manually
    sed -i.bak "s/^minecraft_version=.*/minecraft_version=$GAME_VERSION/" "$CONFIG_FILE"
    rm -f "$CONFIG_FILE.bak"
    echo "  Updated minecraft_version=$GAME_VERSION (manual)"
fi

# Step 4: Build and test
if [ "$SKIP_TEST" = false ]; then
    print_step "Step 4/8: Building and testing"
    
    echo "  Building Fabric..."
    cd "$PROJECT_ROOT/fabric"
    chmod +x ./gradlew
    ./gradlew build
    
    echo "  Building NeoForge..."
    cd "$PROJECT_ROOT/neoforge"
    chmod +x ./gradlew
    ./gradlew build
    
    cd "$PROJECT_ROOT"
    echo "  Build successful!"
else
    print_step "Step 4/8: Skipping build and test (--no-test)"
fi

# Step 5: Update templates
print_step "Step 5/8: Updating DOWNLOAD.md and README.md"
cd "$PROJECT_ROOT"
python3 "$SCRIPT_DIR/make-template.py" \
    --game "$GAME_VERSION" \
    --version "$MOD_VERSION_TAG" \
    --download-file "$PROJECT_ROOT/DOWNLOAD.md" \
    --readme-file "$PROJECT_ROOT/README.md"
echo "  Templates updated!"

# Step 6: Commit changes
print_step "Step 6/8: Committing changes"
git add -A
git commit -m "Release $MOD_VERSION_TAG for Minecraft $GAME_VERSION" || print_warning "Nothing to commit"

# Step 7: Create tag
print_step "Step 7/8: Creating tag '$MOD_VERSION_TAG'"
if git rev-parse "$MOD_VERSION_TAG" >/dev/null 2>&1; then
    print_warning "Tag '$MOD_VERSION_TAG' already exists. Skipping tag creation."
else
    git tag -a "$MOD_VERSION_TAG" -m "Release $MOD_VERSION_TAG for Minecraft $GAME_VERSION"
    echo "  Tag created!"
fi

# Step 8: Push if requested
if [ "$PUSH_REMOTE" = true ]; then
    print_step "Step 8/8: Pushing to remote..."
    git push -u origin "$BRANCH_NAME"
    git push origin "$MOD_VERSION_TAG"
    echo "  Pushed branch and tag to remote!"
fi

echo ""
echo "============================================"
echo -e "  ${GREEN}Release preparation complete!${NC}"
echo "============================================"
echo ""
echo "  Branch: $BRANCH_NAME"
echo "  Tag:    $MOD_VERSION_TAG"
echo ""

if [ "$PUSH_REMOTE" = false ]; then
    echo "To push to remote, run:"
    echo "  git push -u origin $BRANCH_NAME"
    echo "  git push origin $MOD_VERSION_TAG"
    echo ""
fi

echo "Release artifacts in:"
echo "  fabric/build/libs/"
echo "  neoforge/build/libs/"
echo ""
