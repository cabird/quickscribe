#!/bin/bash
# Shared configuration for all deployment scripts.
# Override any variable in config.local.sh (gitignored).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults ---
# Azure subscription every script targets. Pinned explicitly so a deploy never
# lands in whatever `az account show` happens to default to.
SUBSCRIPTION="${SUBSCRIPTION:-}"
RESOURCE_GROUP="${RESOURCE_GROUP:-quickscribe-v2-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-quickscribev2acr}"
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-quickscribe-v2-plan}"
APP_NAME="${APP_NAME:-quickscribe-v2}"
APP_SKU="${APP_SKU:-B3}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-quickscribev2store}"
BLOB_CONTAINER="${BLOB_CONTAINER:-quickscribe-backup}"
IMAGE_NAME="${IMAGE_NAME:-quickscribe-v2}"
DEPS_IMAGE_NAME="${DEPS_IMAGE_NAME:-quickscribe-deps}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
APP_PORT="${APP_PORT:-8000}"
DB_PATH_IN_CONTAINER="${DB_PATH_IN_CONTAINER:-/app/data/app.db}"
DB_BLOB_NAME="${DB_BLOB_NAME:-app.db}"

# Frontend MSAL settings, baked into the bundle at build time
VITE_AUTH_ENABLED="${VITE_AUTH_ENABLED:-true}"
VITE_AZURE_CLIENT_ID="${VITE_AZURE_CLIENT_ID:-}"
VITE_AZURE_TENANT_ID="${VITE_AZURE_TENANT_ID:-}"

# Project root (v2/ directory)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Load local overrides ---
if [ -f "$SCRIPT_DIR/config.local.sh" ]; then
    source "$SCRIPT_DIR/config.local.sh"
fi

# --- Helper functions ---

print_config() {
    echo "=== Deployment Configuration ==="
    echo "  RESOURCE_GROUP:    $RESOURCE_GROUP"
    echo "  LOCATION:          $LOCATION"
    echo "  ACR_NAME:          $ACR_NAME"
    echo "  APP_SERVICE_PLAN:  $APP_SERVICE_PLAN"
    echo "  APP_NAME:          $APP_NAME"
    echo "  APP_SKU:           $APP_SKU"
    echo "  STORAGE_ACCOUNT:   $STORAGE_ACCOUNT"
    echo "  BLOB_CONTAINER:    $BLOB_CONTAINER"
    echo "  IMAGE_NAME:        $IMAGE_NAME"
    echo "  IMAGE_TAG:         $IMAGE_TAG"
    echo "  APP_PORT:          $APP_PORT"
    echo "  SUBSCRIPTION:      ${SUBSCRIPTION:-<az default>}"
    echo "  PROJECT_ROOT:      $PROJECT_ROOT"
    echo "================================="
}

check_azure_login() {
    if ! az account show &>/dev/null; then
        echo "ERROR: Not logged in to Azure. Run 'az login' first."
        exit 1
    fi
    if [ -n "$SUBSCRIPTION" ]; then
        if ! az account show --subscription "$SUBSCRIPTION" &>/dev/null; then
            echo "ERROR: Subscription $SUBSCRIPTION not accessible."
            exit 1
        fi
        echo "Azure subscription: $(az account show --subscription "$SUBSCRIPTION" --query name -o tsv)"
    else
        echo "Azure subscription: $(az account show --query name -o tsv) (az default; set SUBSCRIPTION to pin)"
    fi
}

# Run az against the pinned subscription (or the az default if unset).
azs() {
    if [ -n "$SUBSCRIPTION" ]; then
        az "$@" --subscription "$SUBSCRIPTION"
    else
        az "$@"
    fi
}

# Stop the web app and wait until its container has actually gone, so it can't
# still be replicating to Litestream when something else touches the database.
# Use this instead of `az webapp restart`, and before changing app settings:
# App Service keeps the old container alive while a new one warms up, and two
# live containers split the database. See 03-deploy-app.sh.
stop_app_and_wait() {
    echo "Stopping $APP_NAME..."
    azs webapp stop --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --output none
    echo "Waiting for the container to stop responding..."
    local health_url="https://$APP_NAME.azurewebsites.net/api/health"
    for _ in {1..18}; do
        if ! curl -sf -m 3 "$health_url" >/dev/null 2>&1; then
            break
        fi
        sleep 5
    done
    # Margin for any in-flight Litestream WAL flush
    sleep 10
}

start_app() {
    echo "Starting $APP_NAME..."
    azs webapp start --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --output none
}

# Printed by scripts that exit with the app still stopped
print_start_hint() {
    echo ""
    echo "!!! $APP_NAME is STOPPED. Fix and rerun, or start it with:"
    echo "!!!   az webapp start --name $APP_NAME --resource-group $RESOURCE_GROUP${SUBSCRIPTION:+ --subscription $SUBSCRIPTION}"
}

require_frontend_auth_config() {
    if [ "$VITE_AUTH_ENABLED" = "true" ] && { [ -z "$VITE_AZURE_CLIENT_ID" ] || [ -z "$VITE_AZURE_TENANT_ID" ]; }; then
        echo "ERROR: VITE_AUTH_ENABLED=true but VITE_AZURE_CLIENT_ID/VITE_AZURE_TENANT_ID are not set."
        echo "       Set them in config.local.sh, or the frontend will ship without working login."
        exit 1
    fi
}

is_wsl() {
    [ -f /proc/version ] && grep -qi microsoft /proc/version
}

# Convert a path for use with Azure CLI on WSL
az_path() {
    local path="$1"
    if is_wsl; then
        wslpath -m "$path"
    else
        echo "$path"
    fi
}
