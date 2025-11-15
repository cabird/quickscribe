#!/bin/bash
# Deploy V3 Frontend - Replaces current frontend
set -e

echo "========================================"
echo "V3 Frontend Deployment Script"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "Error: Must run from v3_frontend directory"
    exit 1
fi

# Build the frontend
echo "Step 1: Building V3 frontend..."
npm run build

if [ ! -d "dist" ]; then
    echo "Error: Build failed - dist directory not found"
    exit 1
fi

# Copy to backend
echo ""
echo "Step 2: Copying to backend static directory..."
echo "  Clearing old frontend: ../backend/src/frontend-dist/"
rm -rf ../backend/src/frontend-dist/*

echo "  Copying new frontend..."
cp -r dist/* ../backend/src/frontend-dist/

# Verify
echo ""
echo "Step 3: Verifying deployment files..."
if [ -f "../backend/src/frontend-dist/index.html" ]; then
    echo "  ✓ index.html copied"
else
    echo "  ✗ index.html NOT found - deployment failed!"
    exit 1
fi

if [ -d "../backend/src/frontend-dist/assets" ]; then
    echo "  ✓ assets directory copied"
else
    echo "  ✗ assets directory NOT found - deployment failed!"
    exit 1
fi

echo ""
echo "========================================"
echo "V3 Frontend ready for backend deployment"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. cd ../backend"
echo "  2. make deploy_azure"
echo ""
echo "For local testing (without Docker):"
echo "  1. cd ../backend"
echo "  2. ./startup.sh"
echo "  3. Open http://localhost:8000"
echo ""
echo "For local testing (with Docker):"
echo "  1. cd ../backend"
echo "  2. make deploy_local"
echo "  3. Open http://localhost:5000"
echo ""
