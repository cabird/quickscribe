#!/bin/bash
# deploy-explicit.sh - Fixed version with correct update syntax

set -e

# Load environment variables
set -a
source .env
set +a

echo "?? Deploying transcoder container app..."

# Get version
VERSION=$(python -c "exec(open('container_app_version.py').read()); print(CONTAINER_APP_VERSION)")

# Get ACR credentials (admin must be enabled)
echo "🔑 Getting ACR credentials..."
ACR_USERNAME=$(az acr credential show --name quickscribecontainerregistry --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name quickscribecontainerregistry --query passwords[0].value --output tsv)


# Check if container app exists
if az containerapp show --name quickscribetranscoder --resource-group QuickScribeResourceGroup >/dev/null 2>&1; then
    echo "?? Container app exists, updating..."
    
    # Update existing container app (without scale settings)
    az containerapp update \
      --name quickscribetranscoder \
      --resource-group QuickScribeResourceGroup \
      --image $AZURE_ACR_LOGIN_SERVER/transcoder-container:$VERSION \
      --replace-env-vars AZURE_STORAGE_CONNECTION_STRING="$AZURE_STORAGE_CONNECTION_STRING" \
                         TRANSCODING_QUEUE_NAME="$TRANSCODING_QUEUE_NAME" \
                         LOG_LEVEL="$LOG_LEVEL" \
                         CONTAINER_VERSION="$VERSION" \
      --cpu 1.0 \
      --memory 2.0Gi
    
   
    echo "? Container app updated successfully!"
    
else
    echo "?? Container app doesn't exist, creating..."
    
    # Create new container app with all settings
    az containerapp create \
      --name quickscribetranscoder \
      --resource-group QuickScribeResourceGroup \
      --environment $AZURE_CONTAINER_APP_ENV \
      --image $AZURE_ACR_LOGIN_SERVER/transcoder-container:$VERSION \
      --registry-server $AZURE_ACR_LOGIN_SERVER \
      --registry-username $ACR_USERNAME \
      --registry-password $ACR_PASSWORD \
      --env-vars AZURE_STORAGE_CONNECTION_STRING="$AZURE_STORAGE_CONNECTION_STRING" \
                 TRANSCODING_QUEUE_NAME="$TRANSCODING_QUEUE_NAME" \
                 LOG_LEVEL="$LOG_LEVEL" \
                 CONTAINER_VERSION="$VERSION" \
      --min-replicas 0 \
      --max-replicas 1 \
      --cpu 1.0 \
      --memory 2.0Gi \
    
    echo "? Container app created successfully!"
fi

# Configure queue-based scaling (this will also set min/max replicas)
echo "?? Configuring queue-based scaling..."
az containerapp update \
  --name quickscribetranscoder \
  --resource-group QuickScribeResourceGroup \
  --scale-rule-name queue-scale \
  --scale-rule-type azure-queue \
  --scale-rule-metadata queueName="$TRANSCODING_QUEUE_NAME" queueLength="1" \
  --scale-rule-auth connection=AZURE_STORAGE_CONNECTION_STRING \
  --min-replicas 0 \
  --max-replicas 1

echo "?? Deployment complete!"

# Show current status
echo ""
echo "?? Current Status:"
az containerapp show \
  --name quickscribetranscoder \
  --resource-group QuickScribeResourceGroup \
  --query "{Name:name, Status:properties.provisioningState, Image:properties.template.containers[0].image}" \
  --output table
