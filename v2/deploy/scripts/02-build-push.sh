#!/bin/bash
# Build Docker image and push to Azure Container Registry.
# Automatically bumps the patch version before building.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

VERSION_FILE="$PROJECT_ROOT/backend/VERSION"

check_azure_login
require_frontend_auth_config

# Bump patch version
OLD_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
IFS='.' read -r MAJOR MINOR PATCH <<< "$OLD_VERSION"
PATCH=$((PATCH + 1))
APP_VERSION="$MAJOR.$MINOR.$PATCH"
echo "$APP_VERSION" > "$VERSION_FILE"
echo "Version: $OLD_VERSION → $APP_VERSION"

ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
IMAGE="$ACR_LOGIN_SERVER/$IMAGE_NAME:$APP_VERSION"

# Deps base image (OS packages + venv incl. PyTorch), tagged by a hash of
# everything that goes into it. Rebuilt only when that tag is missing.
DEPS_INPUTS=(
    "$PROJECT_ROOT/deploy/Dockerfile.deps"
    "$PROJECT_ROOT/backend/pyproject.toml"
    "$PROJECT_ROOT/backend/uv.lock"
)
if command -v sha256sum &>/dev/null; then
    DEPS_HASH=$(cat "${DEPS_INPUTS[@]}" | sha256sum | cut -c1-16)
else
    DEPS_HASH=$(cat "${DEPS_INPUTS[@]}" | shasum -a 256 | cut -c1-16)
fi
DEPS_TAG="$DEPS_IMAGE_NAME:$DEPS_HASH"
DEPS_IMAGE="$ACR_LOGIN_SERVER/$DEPS_TAG"

BUILD_ARGS=(
    --build-arg "DEPS_IMAGE=$DEPS_IMAGE"
    --build-arg "VITE_AUTH_ENABLED=$VITE_AUTH_ENABLED"
    --build-arg "VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID"
    --build-arg "VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID"
    --build-arg "VITE_APP_VERSION=$APP_VERSION"
)

if command -v docker &>/dev/null && docker info &>/dev/null; then
    BUILDER=docker
    azs acr login --name "$ACR_NAME"
else
    BUILDER=acr
fi

# Only versioned tags are pushed, never :latest. The registry may carry an
# App Service continuous-deployment webhook on :latest, and a CD-triggered
# restart overlaps old and new containers -- the Litestream split-brain that
# 03-deploy-app.sh's stop -> set -> start sequence exists to prevent.
build_and_push() {
    local image_ref="$1" dockerfile="$2"; shift 2
    if [ "$BUILDER" = docker ]; then
        docker build --network host --platform linux/amd64 "$@" \
            -t "$ACR_LOGIN_SERVER/$image_ref" -f "$dockerfile" "$PROJECT_ROOT"
        docker push "$ACR_LOGIN_SERVER/$image_ref"
    else
        azs acr build --registry "$ACR_NAME" --platform linux/amd64 "$@" \
            --image "$image_ref" --file "$dockerfile" "$PROJECT_ROOT"
    fi
}

echo ""
echo "Builder: $BUILDER"
echo "Deps image: $DEPS_IMAGE"
# DEPS_REBUILD=1 forces a rebuild of the same tag, e.g. to pick up base-image
# or apt security fixes that the hash doesn't see.
if [ "${DEPS_REBUILD:-0}" != 1 ] && azs acr repository show --name "$ACR_NAME" --image "$DEPS_TAG" --output none 2>/dev/null; then
    echo "  Already in registry -- reusing (no PyTorch reinstall)."
else
    echo "  Not found -- building it (slow: installs PyTorch). Only happens when"
    echo "  Dockerfile.deps, pyproject.toml or uv.lock change."
    build_and_push "$DEPS_TAG" "$PROJECT_ROOT/deploy/Dockerfile.deps"
fi

echo ""
echo "Building $IMAGE"
build_and_push "$IMAGE_NAME:$APP_VERSION" "$PROJECT_ROOT/deploy/Dockerfile" "${BUILD_ARGS[@]}"

echo ""
echo "Build and push complete."
echo "  Image: $IMAGE"
echo "  Deps:  $DEPS_IMAGE"
