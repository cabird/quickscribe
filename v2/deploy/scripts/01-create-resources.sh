#!/bin/bash
# Create Azure resources using Bicep template.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login
print_config

echo ""
echo "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none

BICEP_FILE="$SCRIPT_DIR/../bicep/main.bicep"

echo "Deploying Bicep template..."
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$(az_path "$BICEP_FILE")" \
    --parameters \
        appServicePlanName="$APP_SERVICE_PLAN" \
        webAppName="$APP_NAME" \
        acrName="$ACR_NAME" \
        storageAccountName="$STORAGE_ACCOUNT" \
        blobContainerName="$BLOB_CONTAINER" \
        imageName="$IMAGE_NAME" \
        appSku="$APP_SKU" \
        appPort="$APP_PORT" \
        dbPath="$DB_PATH_IN_CONTAINER" \
    --output none

echo ""
echo "Resources created successfully."
echo "  Web App URL: https://$APP_NAME.azurewebsites.net"
echo "  ACR:         $ACR_NAME.azurecr.io"
echo "  Storage:     $STORAGE_ACCOUNT"
