#!/bin/bash
# deploy_simple.sh - Deploy to Azure Container Jobs

set -e

# Load environment variables
set -a
source .env
set +a

echo "🚀 Deploying transcoder container job..."

# Get version
VERSION=$(python -c "exec(open('container_app_version.py').read()); print(CONTAINER_APP_VERSION)")

# Get ACR credentials (admin must be enabled)
echo "🔑 Getting ACR credentials..."
ACR_USERNAME=$(az acr credential show --name quickscribecontainerregistry --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name quickscribecontainerregistry --query passwords[0].value --output tsv)

# Check if container job exists
if az containerapp job show --name quickscribetranscoderjobs --resource-group QuickScribeResourceGroup >/dev/null 2>&1; then
    echo "📝 Container job exists, updating..."
    
    # Update existing container job
    az containerapp job update \
      --name quickscribetranscoderjobs \
      --resource-group QuickScribeResourceGroup \
      --image $AZURE_ACR_LOGIN_SERVER/transcoder-container:$VERSION \
      --cpu 1.0 \
      --memory 2.0Gi \
      --set-env-vars "AZURE_STORAGE_CONNECTION_STRING=secretref:azure-storage-connection" \
                     "TRANSCODING_QUEUE_NAME=$TRANSCODING_QUEUE_NAME" \
                     "LOG_LEVEL=$LOG_LEVEL" \
                     "CONTAINER_VERSION=$VERSION"
   
    echo "✅ Container job updated successfully!"
    
else
    echo "🆕 Container job doesn't exist, creating..."
    
    # Create new container job with all settings
    az containerapp job create \
      --name quickscribetranscoderjobs \
      --resource-group QuickScribeResourceGroup \
      --environment $AZURE_CONTAINER_APP_ENV \
      --trigger-type Event \
      --replica-timeout 300 \
      --replica-retry-limit 2 \
      --replica-completion-count 1 \
      --parallelism 1 \
      --polling-interval 30 \
      --min-executions 0 \
      --max-executions 1 \
      --scale-rule-name queue-scale \
      --scale-rule-type azure-queue \
      --scale-rule-metadata "queueLength=1" "queueName=$TRANSCODING_QUEUE_NAME" "accountName=quickscribestorage" \
      --scale-rule-auth "connection=azure-storage-connection" \
      --image $AZURE_ACR_LOGIN_SERVER/transcoder-container:$VERSION \
      --registry-server $AZURE_ACR_LOGIN_SERVER \
      --registry-username $ACR_USERNAME \
      --registry-password $ACR_PASSWORD \
      --cpu 1.0 \
      --memory 2.0Gi \
      --secrets "azure-storage-connection=$AZURE_STORAGE_CONNECTION_STRING" \
      --env-vars "AZURE_STORAGE_CONNECTION_STRING=secretref:azure-storage-connection" \
                 "TRANSCODING_QUEUE_NAME=$TRANSCODING_QUEUE_NAME" \
                 "LOG_LEVEL=$LOG_LEVEL" \
                 "CONTAINER_VERSION=$VERSION"
    
    echo "✅ Container job created successfully!"
fi

echo "🎉 Deployment complete!"

# Show current status
echo ""
echo "📊 Current Status:"
az containerapp job show \
  --name quickscribetranscoderjobs \
  --resource-group QuickScribeResourceGroup \
  --query "{Name:name, Status:properties.provisioningState, Image:properties.template.containers[0].image, TriggerType:properties.configuration.triggerType}" \
  --output table