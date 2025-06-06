#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Configuration variables
RESOURCE_GROUP="QuickScribeResourceGroup"
APP_NAME="quickscribe-containerized-webapp"
LOCATION="westus2"
APP_SERVICE_PLAN_LOCATION="westus"
APP_SERVICE_PLAN_NAME="quickscribe-container-appservice-plan"
CONTAINER_REGISTRY="quickscribecontainerregistry"
APP_SERVICE_PLAN_SKU="B2"
IMAGE_NAME="quickscribe-backend"
# Extract version from api_version.py
IMAGE_TAG=$(python -c "import sys; sys.path.append('.'); from api_version import API_VERSION; print(API_VERSION)")
TEMP_DEPLOY_DIR="./quickscribe_deploy_${IMAGE_TAG}"

# Function for cleanup
cleanup() {
    echo "Cleaning up temporary files..."
    if [ -d "$TEMP_DEPLOY_DIR" ]; then
        rm -rf "$TEMP_DEPLOY_DIR"
        echo "skipping cleanup of $TEMP_DEPLOY_DIR"
    fi
}

# Register the cleanup function to run on script exit
trap cleanup EXIT

echo "=== QuickScribe Azure Deployment Script ==="
echo "Deploying to resource group: $RESOURCE_GROUP"
echo "App name: $APP_NAME"
echo "Container registry: $CONTAINER_REGISTRY"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"
echo ""

# Create resource group if it doesn't exist
echo "Creating resource group if it doesn't exist..."
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create container registry if it doesn't exist
echo "Creating container registry if it doesn't exist..."
az acr create --resource-group $RESOURCE_GROUP --name $CONTAINER_REGISTRY --sku Basic --admin-enabled true

# Log in to ACR
echo "Logging in to container registry..."
az acr login --name $CONTAINER_REGISTRY || {
    echo "Failed to log in to container registry"
    exit 1
}

# Build and push the Docker image
echo "Building and pushing Docker image..."

# Create a clean temporary directory for deployment
echo "Creating temporary deployment directory: $TEMP_DEPLOY_DIR"
mkdir -p "$TEMP_DEPLOY_DIR"

# Always copy Dockerfile (might not be in fileinclude)
echo "Copying essential Dockerfile..."
cp Dockerfile "$TEMP_DEPLOY_DIR/"

# Generate the file list using the existing Python script
echo "Generating file list from 'fileinclude' patterns..."
python generate_filelist.py

# Read filelist.txt and copy each file to the temp directory
echo "Copying files to deployment directory..."
while IFS= read -r file; do
    # Skip comments and empty lines
    [[ "$file" =~ ^#.*$ || -z "$file" ]] && continue
    
    # Make sure parent directories exist
    parent_dir=$(dirname "$TEMP_DEPLOY_DIR/$file")
    mkdir -p "$parent_dir"
    
    # Handle file or directory copy
    if [ -d "$file" ]; then
        echo "Copying directory: $file"
        cp -r "$file" "$parent_dir/"
    elif [ -f "$file" ]; then
        echo "Copying file: $file"
        cp "$file" "$TEMP_DEPLOY_DIR/$file"
    else
        echo "Warning: File not found: $file"
    fi
done < filelist.txt

# Remove any __pycache__ directories from the copied files
echo "Removing __pycache__ directories..."
find "$TEMP_DEPLOY_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "Building version: $IMAGE_TAG"
az acr build --registry $CONTAINER_REGISTRY --image $IMAGE_NAME:$IMAGE_TAG --image $IMAGE_NAME:latest "$TEMP_DEPLOY_DIR" || {
    echo "Failed to build and push Docker image"
    exit 1
}

# Get the container registry credentials
echo "Getting container registry credentials..."
ACR_USERNAME=$(az acr credential show --name $CONTAINER_REGISTRY --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $CONTAINER_REGISTRY --query passwords[0].value -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name $CONTAINER_REGISTRY --query loginServer -o tsv)

# Create or update the web app
echo "Creating/updating web app..."

# Check if app already exists
APP_EXISTS=$(az webapp list --query "[?name=='$APP_NAME']" -o tsv)

if [ -z "$APP_EXISTS" ]; then
    echo "Checking if app service plan exists..."
    APP_PLAN_EXISTS=$(az appservice plan list --query "[?name=='quickscribe-appservice-plan']" -o tsv)
    
    if [ -z "$APP_PLAN_EXISTS" ]; then
        echo "Creating app service plan..."
        az appservice plan create --resource-group $RESOURCE_GROUP \
            --location $APP_SERVICE_PLAN_LOCATION \
            --name $APP_SERVICE_PLAN_NAME \
            --is-linux --sku $APP_SERVICE_PLAN_SKU
    fi
    
    echo "Creating new web app..."
    az webapp create --resource-group $RESOURCE_GROUP --name $APP_NAME \
        --plan "$APP_SERVICE_PLAN_NAME" \
        --deployment-container-image-name "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG"
else
    echo "Updating existing web app..."
    az webapp config container set --resource-group $RESOURCE_GROUP --name $APP_NAME \
        --container-image-name "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG" \
        --container-registry-url "https://$ACR_LOGIN_SERVER" \
        --container-registry-user "$ACR_USERNAME" \
        --container-registry-password "$ACR_PASSWORD"
fi

# Configure the web app
echo "Configuring web app settings..."

# Detect if startup.sh exists and make sure it's used correctly
if [ -f "startup.sh" ]; then
    echo "Setting startup file to startup.sh..."
    az webapp config set --resource-group $RESOURCE_GROUP --name $APP_NAME \
        --startup-file "/app/startup.sh"
fi

# Apply app settings from environment file if it exists
if [ -f ".env" ]; then
    echo "Applying settings from .env file..."
    
    # Collect all settings in a temporary array
    declare -a settings_array
    
    # Read each line from .env file
    while IFS= read -r line || [[ -n $line ]]; do
        # Skip comments and empty lines
        [[ $line =~ ^#.*$ ]] && continue
        [[ -z $line ]] && continue
        
        # Extract key and value
        key=$(echo "$line" | cut -d= -f1)
        value=$(echo "$line" | cut -d= -f2-)
        
        echo "Adding setting: $key"
        settings_array+=("$key=$value")
    done < .env
    
    # Apply all settings in a single command for efficiency
    if [ ${#settings_array[@]} -gt 0 ]; then
        echo "Applying ${#settings_array[@]} settings to web app..."
        az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $APP_NAME \
            --settings "${settings_array[@]}" >/dev/null || {
            echo "Failed to set app settings"
            exit 1
        }
    fi
fi

# Configure for continuous deployment
echo "Enabling continuous deployment..."
az webapp deployment container config --enable-cd true \
    --resource-group $RESOURCE_GROUP --name $APP_NAME || {
    echo "Failed to enable continuous deployment"
    exit 1
}


# Get the app URL
APP_URL=$(az webapp show --resource-group $RESOURCE_GROUP --name $APP_NAME --query defaultHostName -o tsv)

echo ""
echo "=== Deployment Complete ==="
echo "Your app is available at: https://$APP_URL"
echo ""
echo "To view logs, use: az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
