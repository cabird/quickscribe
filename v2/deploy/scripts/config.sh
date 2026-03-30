#!/bin/bash
# Shared configuration for all deployment scripts.
# Override any variable in config.local.sh (gitignored).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults ---
RESOURCE_GROUP="${RESOURCE_GROUP:-quickscribe-v2-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-quickscribev2acr}"
APP_SERVICE_PLAN="${APP_SERVICE_PLAN:-quickscribe-v2-plan}"
APP_NAME="${APP_NAME:-quickscribe-v2}"
APP_SKU="${APP_SKU:-B3}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-quickscribev2store}"
BLOB_CONTAINER="${BLOB_CONTAINER:-quickscribe-backup}"
IMAGE_NAME="${IMAGE_NAME:-quickscribe-v2}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
APP_PORT="${APP_PORT:-8000}"
DB_PATH_IN_CONTAINER="${DB_PATH_IN_CONTAINER:-/app/data/app.db}"
DB_BLOB_NAME="${DB_BLOB_NAME:-app.db}"

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
    echo "  PROJECT_ROOT:      $PROJECT_ROOT"
    echo "================================="
}

check_azure_login() {
    if ! az account show &>/dev/null; then
        echo "ERROR: Not logged in to Azure. Run 'az login' first."
        exit 1
    fi
    echo "Azure account: $(az account show --query name -o tsv)"
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
