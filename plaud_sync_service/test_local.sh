#!/bin/bash
# Local testing script for Plaud Sync Service
# This script sets up the environment and triggers a manual sync run

set -e

echo "=== Plaud Sync Service - Local Testing ==="
echo ""

# Check if local.settings.json exists
if [ ! -f "local.settings.json" ]; then
    echo "ERROR: local.settings.json not found"
    echo "Please copy local.settings.json.example to local.settings.json and configure it"
    exit 1
fi

# Check if shared_quickscribe_py is installed
python -c "import shared_quickscribe_py" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing shared_quickscribe_py..."
    pip install -e ../shared_quickscribe_py
fi

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    echo "ERROR: Azure Functions Core Tools not found"
    echo "Please install from: https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local"
    exit 1
fi

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ERROR: FFmpeg not found"
    echo "Please install FFmpeg: sudo apt-get install ffmpeg (Linux) or brew install ffmpeg (Mac)"
    exit 1
fi

echo "✓ All prerequisites installed"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "=== Starting Azure Functions Runtime ==="
echo ""
echo "The service will be available at: http://localhost:7071"
echo ""
echo "Available endpoints:"
echo "  - GET  http://localhost:7071/api/health"
echo "  - POST http://localhost:7071/api/sync/trigger"
echo ""
echo "To trigger a manual sync:"
echo "  curl -X POST http://localhost:7071/api/sync/trigger"
echo ""
echo "To trigger for specific user:"
echo "  curl -X POST 'http://localhost:7071/api/sync/trigger?user_id=<USER_ID>'"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the Functions runtime
func start
