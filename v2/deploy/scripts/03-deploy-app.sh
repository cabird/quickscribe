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

# Refuse to stop the app for an image that was never pushed (e.g. 02 failed).
if ! azs acr repository show --name "$ACR_NAME" --image "$IMAGE_NAME:$APP_VERSION" --output none 2>/dev/null; then
    echo "ERROR: $FULL_IMAGE not found in $ACR_NAME. Run 02-build-push.sh first."
    exit 1
fi

APP_STOPPED=false
on_exit() {
    if [ "$APP_STOPPED" = true ]; then
        echo ""
        echo "!!! Deploy aborted with $APP_NAME STOPPED. Fix and rerun, or:"
        echo "!!!   az webapp start --name $APP_NAME --resource-group $RESOURCE_GROUP${SUBSCRIPTION:+ --subscription $SUBSCRIPTION}"
    fi
}
trap on_exit EXIT

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
azs webapp stop \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none
APP_STOPPED=true

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

# App settings changed while the app is stopped don't trigger an overlapping
# restart. Pass them as DEPLOY_APP_SETTINGS="KEY=value KEY2=value2".
if [ -n "${DEPLOY_APP_SETTINGS:-}" ]; then
    echo "Applying app settings: $DEPLOY_APP_SETTINGS"
    # shellcheck disable=SC2086
    azs webapp config appsettings set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --settings $DEPLOY_APP_SETTINGS \
        --output none
fi

STATE=$(azs webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query state -o tsv)
if [ "$STATE" != "Stopped" ]; then
    echo "ERROR: expected $APP_NAME to be Stopped before swapping the image, found '$STATE'."
    exit 1
fi

azs webapp config container set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --container-image-name "$FULL_IMAGE" \
    --container-registry-url "https://$ACR_LOGIN_SERVER" \
    --output none

echo "Starting web app..."
azs webapp start \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none
APP_STOPPED=false

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
