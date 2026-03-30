#!/bin/bash
# Build Docker image and push to Azure Container Registry.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login

ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
GIT_SHA=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "Logging in to ACR: $ACR_LOGIN_SERVER"
az acr login --name "$ACR_NAME"

echo ""
echo "Building Docker image..."
echo "  Context:    $PROJECT_ROOT"
echo "  Dockerfile: $PROJECT_ROOT/deploy/Dockerfile"
echo "  Tags:       $ACR_LOGIN_SERVER/$IMAGE_NAME:latest"
echo "              $ACR_LOGIN_SERVER/$IMAGE_NAME:$GIT_SHA"

docker build \
    --platform linux/amd64 \
    -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest" \
    -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:$GIT_SHA" \
    -f "$PROJECT_ROOT/deploy/Dockerfile" \
    "$PROJECT_ROOT"

echo ""
echo "Pushing images..."
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest"
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:$GIT_SHA"

echo ""
echo "Build and push complete."
echo "  Image: $ACR_LOGIN_SERVER/$IMAGE_NAME:latest"
echo "  SHA:   $ACR_LOGIN_SERVER/$IMAGE_NAME:$GIT_SHA"
