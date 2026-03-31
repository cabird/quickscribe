#!/bin/bash
# Build Docker image and push to Azure Container Registry.
# Automatically bumps the patch version before building.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

VERSION_FILE="$PROJECT_ROOT/backend/VERSION"

# Bump patch version
OLD_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
IFS='.' read -r MAJOR MINOR PATCH <<< "$OLD_VERSION"
PATCH=$((PATCH + 1))
APP_VERSION="$MAJOR.$MINOR.$PATCH"
echo "$APP_VERSION" > "$VERSION_FILE"
echo "Version: $OLD_VERSION → $APP_VERSION"

check_azure_login

ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"

echo ""
echo "Logging in to ACR: $ACR_LOGIN_SERVER"
az acr login --name "$ACR_NAME"

echo ""
echo "Building Docker image..."
echo "  Context:    $PROJECT_ROOT"
echo "  Dockerfile: $PROJECT_ROOT/deploy/Dockerfile"
echo "  Version:    $APP_VERSION"

docker build \
    --network host \
    --platform linux/amd64 \
    -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:$APP_VERSION" \
    -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest" \
    -f "$PROJECT_ROOT/deploy/Dockerfile" \
    "$PROJECT_ROOT"

echo ""
echo "Pushing images..."
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:$APP_VERSION"
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest"

echo ""
echo "Build and push complete."
echo "  Image: $ACR_LOGIN_SERVER/$IMAGE_NAME:$APP_VERSION"
