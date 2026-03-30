#!/bin/bash
# Set application secrets (env vars) on Azure Web App.
# Loads from .env file if present, or set variables before running.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_azure_login

# Load .env if present
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading secrets from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "No .env file found at $ENV_FILE"
    echo "Set environment variables before running, or create a .env file."
fi

# Build settings array — only set vars that are non-empty
SETTINGS=()

[ -n "$AZURE_OPENAI_API_ENDPOINT" ]   && SETTINGS+=("AZURE_OPENAI_API_ENDPOINT=$AZURE_OPENAI_API_ENDPOINT")
[ -n "$AZURE_OPENAI_API_KEY" ]         && SETTINGS+=("AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY")
[ -n "$AZURE_OPENAI_DEPLOYMENT" ]      && SETTINGS+=("AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT")
[ -n "$SPEECH_SERVICES_KEY" ]          && SETTINGS+=("SPEECH_SERVICES_KEY=$SPEECH_SERVICES_KEY")
[ -n "$SPEECH_SERVICES_REGION" ]       && SETTINGS+=("SPEECH_SERVICES_REGION=$SPEECH_SERVICES_REGION")
[ -n "$AZURE_AD_CLIENT_ID" ]           && SETTINGS+=("AZURE_AD_CLIENT_ID=$AZURE_AD_CLIENT_ID")
[ -n "$AZURE_AD_TENANT_ID" ]           && SETTINGS+=("AZURE_AD_TENANT_ID=$AZURE_AD_TENANT_ID")
[ -n "$PLAUD_ENABLED" ]                && SETTINGS+=("PLAUD_ENABLED=$PLAUD_ENABLED")
[ -n "$AZURE_STORAGE_CONNECTION_STRING" ] && SETTINGS+=("AZURE_STORAGE_CONNECTION_STRING=$AZURE_STORAGE_CONNECTION_STRING")
[ -n "$BLOB_CONTAINER_AUDIO" ]         && SETTINGS+=("BLOB_CONTAINER_AUDIO=$BLOB_CONTAINER_AUDIO")

if [ ${#SETTINGS[@]} -eq 0 ]; then
    echo "No secrets to set. Define variables in .env or environment."
    exit 0
fi

echo "Setting ${#SETTINGS[@]} app settings..."
az webapp config appsettings set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings "${SETTINGS[@]}" \
    --output none

echo "Secrets set successfully."
