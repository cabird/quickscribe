#!/bin/bash
# Delete all Azure resources by removing the resource group.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login

echo "WARNING: This will delete the resource group '$RESOURCE_GROUP' and ALL resources in it."
echo "  - App Service Plan: $APP_SERVICE_PLAN"
echo "  - Web App:          $APP_NAME"
echo "  - Container Registry: $ACR_NAME"
echo "  - Storage Account:  $STORAGE_ACCOUNT (including all backups!)"
echo ""
read -p "Type the resource group name to confirm: " CONFIRM

if [ "$CONFIRM" != "$RESOURCE_GROUP" ]; then
    echo "Confirmation did not match. Aborting."
    exit 1
fi

echo "Deleting resource group '$RESOURCE_GROUP'..."
az group delete \
    --name "$RESOURCE_GROUP" \
    --yes \
    --no-wait

echo "Deletion initiated (running in background)."
echo "Check status: az group show --name $RESOURCE_GROUP"
