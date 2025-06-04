#!/bin/bash
# To run this script, use:
# ./dryrun-deploy.sh
# This will create the temporary deployment directory but won't push to Azure

# Configuration variables
IMAGE_TAG=$(date +"%Y%m%d%H%M")
TEMP_DEPLOY_DIR="/tmp/quickscribe_deploy_${IMAGE_TAG}"

# Function for cleanup
cleanup() {
    if [ "$1" != "keep" ]; then
        echo "Cleaning up temporary files..."
        if [ -d "$TEMP_DEPLOY_DIR" ]; then
            rm -rf "$TEMP_DEPLOY_DIR"
        fi
    else
        echo "Keeping temporary directory: $TEMP_DEPLOY_DIR"
        echo "You can inspect its contents to verify what would be deployed."
    fi
}

# Register the cleanup function to run on script exit
trap "cleanup keep" EXIT

echo "=== QuickScribe Deployment Dry Run ==="
echo "Creating temporary deployment directory: $TEMP_DEPLOY_DIR"
mkdir -p "$TEMP_DEPLOY_DIR"

# Define files/directories to include
echo "Copying essential files to temporary directory..."
cp Dockerfile "$TEMP_DEPLOY_DIR/"
cp startup.sh "$TEMP_DEPLOY_DIR/"
cp requirements.txt "$TEMP_DEPLOY_DIR/"
cp app.py "$TEMP_DEPLOY_DIR/"
cp api_version.py "$TEMP_DEPLOY_DIR/"

# Copy directories but exclude __pycache__ folders
echo "Copying routes directory..."
mkdir -p "$TEMP_DEPLOY_DIR/routes"
find routes -type f -not -path "*/\.*" -not -path "*/\__pycache__/*" -exec cp --parents {} "$TEMP_DEPLOY_DIR/" \;

echo "Copying db_handlers directory..."
mkdir -p "$TEMP_DEPLOY_DIR/db_handlers"
find db_handlers -type f -not -path "*/\.*" -not -path "*/\__pycache__/*" -exec cp --parents {} "$TEMP_DEPLOY_DIR/" \;

echo "Copying templates directory..."
cp -r templates "$TEMP_DEPLOY_DIR/"

echo "Copying static directory..."
cp -r static "$TEMP_DEPLOY_DIR/"

echo "Copying frontend-dist directory..."
cp -r frontend-dist "$TEMP_DEPLOY_DIR/"

cp auth.py "$TEMP_DEPLOY_DIR/"
cp blob_util.py "$TEMP_DEPLOY_DIR/"
cp config.py "$TEMP_DEPLOY_DIR/"
cp llms.py "$TEMP_DEPLOY_DIR/"
cp user_util.py "$TEMP_DEPLOY_DIR/"
cp util.py "$TEMP_DEPLOY_DIR/"

# Copy any other necessary files (add more as needed)
if [ -d "local_packages" ]; then
    mkdir -p "$TEMP_DEPLOY_DIR/local_packages"
    cp -r local_packages/*.whl "$TEMP_DEPLOY_DIR/local_packages/" 2>/dev/null || echo "No wheel files found"
fi

# Remove any __pycache__ directories from the copied files
find "$TEMP_DEPLOY_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Print stats about the directory
echo
echo "=== Deployment Directory Stats ==="
echo "Total size: $(du -sh "$TEMP_DEPLOY_DIR" | cut -f1)"
echo "File count: $(find "$TEMP_DEPLOY_DIR" -type f | wc -l) files"
echo "Directory count: $(find "$TEMP_DEPLOY_DIR" -type d | wc -l) directories"
echo
echo "Top 10 largest files:"
find "$TEMP_DEPLOY_DIR" -type f -exec du -h {} \; | sort -hr | head -n 10
echo

echo "=== Dry Run Complete ==="
echo "Your deployment directory is ready at: $TEMP_DEPLOY_DIR"
echo "You can inspect its contents to verify what would be deployed."
echo "This directory will be kept for your inspection."
