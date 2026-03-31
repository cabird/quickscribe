#!/bin/bash
# Build Docker image and push to Azure Container Registry.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login

ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
APP_VERSION=$(cat "$PROJECT_ROOT/backend/VERSION" | tr -d '[:space:]')

echo "Logging in to ACR: $ACR_LOGIN_SERVER"
az acr login --name "$ACR_NAME"

echo ""
echo "Building Docker image..."
echo "  Context:    $PROJECT_ROOT"
echo "  Dockerfile: $PROJECT_ROOT/deploy/Dockerfile"
echo "  Version:    $APP_VERSION"
echo "  Tags:       $ACR_LOGIN_SERVER/$IMAGE_NAME:$APP_VERSION"
echo "              $ACR_LOGIN_SERVER/$IMAGE_NAME:latest"

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
