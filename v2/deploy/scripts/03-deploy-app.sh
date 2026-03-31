#!/bin/bash
# Deploy image to Azure Web App and poll health endpoint until version matches.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login

ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
APP_VERSION=$(cat "$PROJECT_ROOT/backend/VERSION" | tr -d '[:space:]')
FULL_IMAGE="$ACR_LOGIN_SERVER/$IMAGE_NAME:$APP_VERSION"

echo "Deploying $FULL_IMAGE"
az webapp config container set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --container-image-name "$FULL_IMAGE" \
    --container-registry-url "https://$ACR_LOGIN_SERVER" \
    --output none

echo "Restarting web app..."
az webapp restart \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP"

HEALTH_URL="https://$APP_NAME.azurewebsites.net/api/health"
MAX_ATTEMPTS=30
INTERVAL=10

echo ""
echo "Polling for version $APP_VERSION at $HEALTH_URL"

for i in $(seq 1 $MAX_ATTEMPTS); do
    RESP=$(curl -s "$HEALTH_URL" 2>/dev/null || echo "{}")
    if echo "$RESP" | grep -q "$APP_VERSION"; then
        echo "  ✓ $RESP"
        echo ""
        echo "Deployment complete: https://$APP_NAME.azurewebsites.net"
        exit 0
    fi
    echo "  Attempt $i/$MAX_ATTEMPTS: $RESP — waiting ${INTERVAL}s..."
    sleep "$INTERVAL"
done

echo ""
echo "ERROR: Version $APP_VERSION not seen after $((MAX_ATTEMPTS * INTERVAL))s."
echo "Check logs: az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
exit 1
