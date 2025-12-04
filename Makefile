# QuickScribe Root Makefile
# Orchestrates building, running, and deploying all components

BACKEND_DIR = backend
FRONTEND_DIR = v3_frontend
SHARED_PY_DIR = shared_quickscribe_py
PLAUD_DIR = plaud_sync_service

.PHONY: help setup build run-dev run-local build-containers run-local-container deploy-azure deploy-backend deploy-plaud clean bump-version bump-version-backend bump-version-plaud

# Default target
default: help

help:
	@echo "=========================================="
	@echo "QuickScribe Project Makefile"
	@echo "=========================================="
	@echo ""
	@echo "Available targets:"
	@echo ""
	@echo "  help                 - Show this help message (default)"
	@echo "  build                - Build all components (models, frontend assets)"
	@echo "  run-dev              - Run full dev environment (frontend dev server + backend)"
	@echo "  run-local            - Run backend locally (serves built frontend assets)"
	@echo "  build-containers     - Build all Docker container images"
	@echo "  run-local-container  - Run backend in Docker container locally"
	@echo "  deploy-backend       - Deploy backend (web app) to Azure"
	@echo "  deploy-plaud         - Deploy plaud sync service to Azure"
	@echo "  deploy-azure         - Deploy both backend and plaud service to Azure"
	@echo "  clean                - Clean all build artifacts"
	@echo "  bump-version-backend - Bump backend version"
	@echo "  bump-version-plaud   - Bump plaud service version"
	@echo "  bump-version         - Bump all versions (backend + plaud)"
	@echo ""
	@echo "Common workflows:"
	@echo "  Development:   make build && make run-dev"
	@echo "  Local testing: make build && make run-local"
	@echo "  Docker test:   make build-containers && make run-local-container"
	@echo "  Deploy all:    make bump-version && make build && make deploy-azure"
	@echo "  Deploy backend: make bump-version-backend && make build && make deploy-backend"
	@echo ""

# Build all components
build:
	@echo "=========================================="
	@echo "Building all components"
	@echo "=========================================="
	@echo ""
	@echo "=== Building backend models ==="
	cd $(BACKEND_DIR) && make build
	@echo ""
	@echo "=== Building shared_quickscribe_py models ==="
	cd $(SHARED_PY_DIR) && make build
	@echo ""
	@echo "=== Building frontend ==="
	cd $(FRONTEND_DIR) && npm run build
	@echo ""
	@echo "=== Copying frontend assets to backend ==="
	cd $(FRONTEND_DIR) && ./deploy.sh
	@echo ""
	@echo "✓ All components built successfully!"

# Install shared library for local development
setup:
	@echo "Installing shared_quickscribe_py in editable mode..."
	cd $(BACKEND_DIR) && make setup

# Run full development environment (frontend dev server + backend)
run-dev: setup
	@echo "=========================================="
	@echo "Starting full development environment"
	@echo "=========================================="
	@echo ""
	@echo "Frontend dev server: http://localhost:5173"
	@echo "Backend API: http://localhost:8000"
	@echo ""
	@echo "Starting backend..."
	cd $(BACKEND_DIR) && ./startup.sh &
	@echo "Starting frontend dev server..."
	cd $(FRONTEND_DIR) && npm run dev

# Run backend locally (serves built frontend assets)
run-local: setup
	@echo "=========================================="
	@echo "Starting backend (serves frontend assets)"
	@echo "=========================================="
	@echo ""
	@echo "Application: http://localhost:8000"
	@echo ""
	cd $(BACKEND_DIR) && ./startup.sh

# Build all Docker containers
build-containers:
	@echo "=========================================="
	@echo "Building Docker containers"
	@echo "=========================================="
	@echo ""
	@echo "=== Building backend container ==="
	cd $(BACKEND_DIR) && make build_container
	@echo ""
	@echo "=== Building plaud sync service container ==="
	cd $(PLAUD_DIR) && make build
	@echo ""
	@echo "✓ All containers built successfully!"

# Run backend in Docker container locally
run-local-container:
	@echo "=========================================="
	@echo "Running backend in Docker container"
	@echo "=========================================="
	@echo ""
	cd $(BACKEND_DIR) && make deploy_local

# Deploy backend to Azure
deploy-backend:
	@echo "=========================================="
	@echo "Deploying backend (web app) to Azure"
	@echo "=========================================="
	@echo ""
	cd $(BACKEND_DIR) && make deploy_azure
	@echo ""
	@echo "✓ Backend deployed!"

# Deploy plaud service to Azure
deploy-plaud:
	@echo "=========================================="
	@echo "Deploying plaud sync service to Azure"
	@echo "=========================================="
	@echo ""
	cd $(PLAUD_DIR) && make azure-deploy
	@echo ""
	@echo "✓ Plaud service deployed!"

# Deploy both to Azure
deploy-azure: deploy-backend deploy-plaud
	@echo ""
	@echo "✓ All services deployed!"

# Clean all build artifacts
clean:
	@echo "=========================================="
	@echo "Cleaning all build artifacts"
	@echo "=========================================="
	@echo ""
	@echo "=== Cleaning backend ==="
	cd $(BACKEND_DIR) && make clean
	@echo ""
	@echo "=== Cleaning shared_quickscribe_py ==="
	cd $(SHARED_PY_DIR) && make clean
	@echo ""
	@echo "=== Cleaning frontend ==="
	cd $(FRONTEND_DIR) && rm -rf dist node_modules/.vite
	@echo ""
	@echo "✓ All artifacts cleaned!"

# Bump backend version only
bump-version-backend:
	@echo "=========================================="
	@echo "Bumping backend version"
	@echo "=========================================="
	@echo ""
	cd $(BACKEND_DIR) && make bump_version
	@echo ""
	@echo "✓ Backend version bumped!"

# Bump plaud service version only
bump-version-plaud:
	@echo "=========================================="
	@echo "Bumping plaud service version"
	@echo "=========================================="
	@echo ""
	cd $(PLAUD_DIR) && make bump_version
	@echo ""
	@echo "✓ Plaud service version bumped!"

# Bump all versions
bump-version: bump-version-backend bump-version-plaud
	@echo ""
	@echo "✓ All versions bumped!"
