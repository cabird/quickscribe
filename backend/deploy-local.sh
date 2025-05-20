#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Configuration variables
IMAGE_NAME="quickscribe-backend"
CONTAINER_NAME="quickscribe-local"
PORT=8000
LOCAL_ENV_FILE=".env"
TEMP_DEPLOY_DIR="./quickscribe_deploy_local"

# Function for cleanup
cleanup() {
    echo "Cleaning up temporary files..."
    if [ -d "$TEMP_DEPLOY_DIR" ]; then
        rm -rf "$TEMP_DEPLOY_DIR"
    fi
}

# Register the cleanup function to run on script exit
trap cleanup EXIT

echo "=== QuickScribe Local Docker Deployment ==="

# Create a clean temporary directory for deployment
echo "Creating temporary deployment directory: $TEMP_DEPLOY_DIR"
mkdir -p "$TEMP_DEPLOY_DIR"

# Always copy Dockerfile
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

# Stop and remove any existing container with the same name
echo "Checking for existing container..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping and removing existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" || true
    docker rm "$CONTAINER_NAME" || true
fi

# Build the Docker image locally
echo "Building Docker image: $IMAGE_NAME:latest"
docker build -t "$IMAGE_NAME:latest" "$TEMP_DEPLOY_DIR"

# Create environment variable arguments for docker run
ENV_ARGS=""
if [ -f "$LOCAL_ENV_FILE" ]; then
    echo "Using environment variables from $LOCAL_ENV_FILE"
    ENV_ARGS=$(grep -v '^#' "$LOCAL_ENV_FILE" | xargs -I{} echo "-e {}")
fi

# Run the Docker container
echo "Starting container: $CONTAINER_NAME"
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:${PORT}" \
    -e "PORT=${PORT}" \
    ${ENV_ARGS} \
    "$IMAGE_NAME:latest"

# Check if container started successfully
if [ $? -eq 0 ] && docker ps | grep -q "$CONTAINER_NAME"; then
    echo ""
    echo "=== Deployment Successful ==="
    echo "QuickScribe is running locally at: http://localhost:${PORT}"
    echo ""
    echo "Container logs command: docker logs -f $CONTAINER_NAME"
    echo "Stop container command: docker stop $CONTAINER_NAME"
    echo "Start container command: docker start $CONTAINER_NAME"
    echo "Remove container command: docker rm $CONTAINER_NAME"
else
    echo ""
    echo "=== Deployment Failed ==="
    echo "Container failed to start. Check logs for more information:"
    echo "docker logs $CONTAINER_NAME"
    exit 1
fi

# Optional: Show container logs
echo ""
echo "Showing initial container logs (Ctrl+C to exit logs):"
sleep 2
docker logs -f "$CONTAINER_NAME"
