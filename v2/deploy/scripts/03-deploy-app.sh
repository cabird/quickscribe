#!/bin/bash
# Deploy latest image to Azure Web App and poll health endpoint.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login

ACR_LOGIN_SERVER="$ACR_NAME.azurecr.io"
FULL_IMAGE="$ACR_LOGIN_SERVER/$IMAGE_NAME:latest"

echo "Updating container image to: $FULL_IMAGE"
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
echo "Polling health endpoint: $HEALTH_URL"
echo "  Max wait: $((MAX_ATTEMPTS * INTERVAL))s"

for i in $(seq 1 $MAX_ATTEMPTS); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo "  Attempt $i: HTTP $STATUS — healthy!"
        echo ""
        echo "Deployment complete: https://$APP_NAME.azurewebsites.net"
        exit 0
    fi
    echo "  Attempt $i/$MAX_ATTEMPTS: HTTP $STATUS — waiting ${INTERVAL}s..."
    sleep "$INTERVAL"
done

echo ""
echo "ERROR: Health check did not pass after $((MAX_ATTEMPTS * INTERVAL))s."
echo "Check logs: az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
exit 1
