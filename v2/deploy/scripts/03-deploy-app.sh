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

# IMPORTANT: We stop → set image → start (instead of `webapp restart`) to avoid
# Litestream split-brain. Azure App Service's normal "restart" lifecycle keeps
# the old container alive during warm-up of the new one. With Litestream
# replicating SQLite to blob, two containers running simultaneously will each
# pick a different generation ID (because `litestream restore` does not
# preserve generation tracking on disk) and write to the same blob path in
# parallel — which silently splits the data. Stopping the app first guarantees
# the old container has fully released its Litestream lease before the new
# one starts. See deploy/scripts/README.md for details.
echo "Stopping web app to prevent Litestream split-brain..."
az webapp stop \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

# Wait for the container to fully stop. App Service reports "Stopped" almost
# immediately, but the container can take 10–30s to actually release. Poll
# the health endpoint until it stops responding.
echo "Waiting for container to fully stop..."
HEALTH_URL_PRE="https://$APP_NAME.azurewebsites.net/api/health"
for i in {1..18}; do
    if ! curl -sf -m 3 "$HEALTH_URL_PRE" >/dev/null 2>&1; then
        echo "  Container is no longer responding — proceeding."
        break
    fi
    sleep 5
done
# Extra safety margin so any in-flight Litestream WAL flush can complete.
sleep 10

az webapp config container set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --container-image-name "$FULL_IMAGE" \
    --container-registry-url "https://$ACR_LOGIN_SERVER" \
    --output none

echo "Starting web app..."
az webapp start \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

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
