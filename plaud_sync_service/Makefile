# Makefile for Plaud Sync Service (Azure Functions)

# Configuration
FUNCTION_APP_NAME = quickscribe-plaud-sync
IMAGE_NAME = plaud-sync-service
CONTAINER_NAME = $(IMAGE_NAME)-local
VERSION = $(shell grep SERVICE_VERSION service_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')
REGISTRY = quickscribecontainerregistry.azurecr.io
AZURE_ACR_NAME = quickscribecontainerregistry
AZURE_RESOURCE_GROUP = QuickScribeResourceGroup
AZURE_APP_SERVICE_PLAN = quickscribe-plaud-sync-plan

# Function to dynamically get the current version at runtime
get_version = $(shell grep SERVICE_VERSION service_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')

# Environment file for local development
ENV_FILE = .env

# Colors for output
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
BLUE = \033[34m
RESET = \033[0m

.PHONY: help build run stop logs clean push shell status rebuild bump_version bump-deploy azure-build azure-push azure-deploy azure-config health

# Default target
help:
	@echo "$(BLUE)Plaud Sync Service Makefile (Azure Functions)$(RESET)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(GREEN)build$(RESET)         - Build the Docker image"
	@echo "  $(GREEN)run$(RESET)           - Run the container locally (with Docker)"
	@echo "  $(GREEN)run-local$(RESET)     - Run locally with func start (no Docker)"
	@echo "  $(GREEN)stop$(RESET)          - Stop the running container"
	@echo "  $(GREEN)logs$(RESET)          - Show container logs"
	@echo "  $(GREEN)clean$(RESET)         - Remove container and image"
	@echo "  $(GREEN)push$(RESET)          - Push image to Azure Container Registry"
	@echo "  $(GREEN)shell$(RESET)         - Open shell in running container"
	@echo "  $(GREEN)status$(RESET)        - Show container status"
	@echo "  $(GREEN)rebuild$(RESET)       - Clean and rebuild"
	@echo "  $(GREEN)bump_version$(RESET)  - Bump version using bump2version"
	@echo "  $(GREEN)bump-deploy$(RESET)   - Bump version and deploy in one command"
	@echo "  $(GREEN)azure-build$(RESET)   - Build and tag for Azure"
	@echo "  $(GREEN)azure-push$(RESET)    - Push to Azure Container Registry"
	@echo "  $(GREEN)azure-config$(RESET)  - Configure Function App settings from .env"
	@echo "  $(GREEN)azure-deploy$(RESET)  - Build, push, and deploy to Azure Functions"
	@echo "  $(GREEN)health$(RESET)        - Check health of deployed service"
	@echo ""

# Bump version and deploy in a single command
bump-deploy:
	@echo "$(YELLOW)Bumping version...$(RESET)"
	$(MAKE) bump_version
	@echo "$(YELLOW)Building and deploying new version: $(call get_version)$(RESET)"
	$(MAKE) azure-deploy
	@echo "$(GREEN)Version $(call get_version) built and deployed successfully!$(RESET)"

# Bump version using bump2version
bump_version:
	@if [ -f .venv/bin/bump2version ]; then \
		.venv/bin/bump2version --allow-dirty patch; \
	elif command -v bump2version &> /dev/null; then \
		bump2version --allow-dirty patch; \
	else \
		echo "$(RED)Error: bump2version not found. Install with: pip install bump2version$(RESET)"; \
		exit 1; \
	fi
	@cat service_version.py

# Build the Docker image
build:
	@echo "$(YELLOW)Building Docker image version $(call get_version)...$(RESET)"
	cd .. && docker build -f plaud_sync_service/Dockerfile -t $(IMAGE_NAME):$(call get_version) .
	@echo "$(GREEN)Docker image built successfully!$(RESET)"

# Azure build with current version
azure-build:
	@echo "$(YELLOW)Building and tagging for Azure with version: $(call get_version)$(RESET)"
	cd .. && docker build -f plaud_sync_service/Dockerfile -t $(IMAGE_NAME):$(call get_version) .
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(IMAGE_NAME):latest
	@echo "$(GREEN)Built and tagged version $(call get_version)$(RESET)"

# Azure push with current version
azure-push:
	@echo "$(YELLOW)Pushing version $(call get_version) to Azure Container Registry...$(RESET)"
	az acr login --name $(AZURE_ACR_NAME) || \
		(ACR_PASSWORD=$$(az acr credential show --name $(AZURE_ACR_NAME) --query "passwords[0].value" -o tsv) && \
		echo $$ACR_PASSWORD | docker login $(REGISTRY) --username $(AZURE_ACR_NAME) --password-stdin)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	docker push $(REGISTRY)/$(IMAGE_NAME):latest
	@echo "$(GREEN)Pushed version $(call get_version)$(RESET)"

# Configure Azure Function App settings from .env file
azure-config:
	@echo "$(YELLOW)Configuring Function App settings from .env file...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		exit 1; \
	fi
	@echo "Reading settings from $(ENV_FILE)..."
	@bash -c ' \
	SETTINGS=""; \
	while IFS= read -r line || [[ -n "$$line" ]]; do \
		line=$$(echo "$$line" | sed "s/^[[:space:]]*//;s/[[:space:]]*$$//"); \
		if [[ "$$line" =~ ^#.*$$ ]] || [[ -z "$$line" ]]; then continue; fi; \
		key=$$(echo "$$line" | cut -d= -f1); \
		value=$$(echo "$$line" | cut -d= -f2-); \
		SETTINGS="$$SETTINGS $$key=$$value"; \
	done < $(ENV_FILE); \
	az functionapp config appsettings set \
		--name $(FUNCTION_APP_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--settings $$SETTINGS SERVICE_VERSION=$(call get_version) FUNCTIONS_WORKER_RUNTIME=python WEBSITES_ENABLE_APP_SERVICE_STORAGE=false FUNCTIONS_EXTENSION_VERSION=~4 \
	'
	@echo "$(GREEN)Function App settings configured successfully!$(RESET)"

# Azure deploy to Functions
azure-deploy: azure-build azure-push
	@echo "$(YELLOW)Deploying version $(call get_version) to Azure Functions...$(RESET)"
	az functionapp config container set \
		--name $(FUNCTION_APP_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--image $(REGISTRY)/$(IMAGE_NAME):$(call get_version) \
		--registry-server https://$(REGISTRY) \
		--registry-username $(AZURE_ACR_NAME) \
		--registry-password "$$(az acr credential show --name $(AZURE_ACR_NAME) --query 'passwords[0].value' -o tsv)"
	@echo "$(YELLOW)Configuring application settings...$(RESET)"
	$(MAKE) azure-config
	@echo "$(YELLOW)Restarting Function App...$(RESET)"
	az functionapp restart --name $(FUNCTION_APP_NAME) --resource-group $(AZURE_RESOURCE_GROUP)
	@echo "$(YELLOW)Checking deployment status...$(RESET)"
	@sleep 5
	@az functionapp show \
		--name $(FUNCTION_APP_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		-o json | grep -E '"name"|"state"|"defaultHostName"' | head -3
	@echo "$(GREEN)Deployed Function App version $(call get_version)$(RESET)"
	@echo "$(BLUE)Health check URL: https://$(FUNCTION_APP_NAME).azurewebsites.net/api/health$(RESET)"

# Run the container locally with Docker
run: build
	@echo "$(YELLOW)Starting container locally...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found. Please create it with required environment variables.$(RESET)"; \
		exit 1; \
	fi
	docker run --rm \
		--name $(CONTAINER_NAME) \
		--env-file $(ENV_FILE) \
		-p 7071:80 \
		$(IMAGE_NAME):$(call get_version)
	@echo "$(GREEN)Container started successfully!$(RESET)"
	@echo "$(BLUE)Health check: http://localhost:7071/api/health$(RESET)"

# Run locally using Azure Functions Core Tools (no Docker)
run-local:
	@echo "$(YELLOW)Starting Azure Functions locally...$(RESET)"
	@if [ ! -f local.settings.json ]; then \
		echo "$(RED)Error: local.settings.json not found$(RESET)"; \
		exit 1; \
	fi
	func start --python --verbose

# Stop the container
stop:
	@echo "$(YELLOW)Stopping container...$(RESET)"
	@docker stop $(CONTAINER_NAME) || true
	@echo "$(GREEN)Container stopped.$(RESET)"

# Show container logs
logs:
	@echo "$(YELLOW)Showing logs for $(CONTAINER_NAME)...$(RESET)"
	docker logs -f $(CONTAINER_NAME)

# Clean up container and image
clean: stop
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	@docker rm $(CONTAINER_NAME) || true
	@docker rmi $(IMAGE_NAME):$(call get_version) || true
	@echo "$(GREEN)Cleanup complete.$(RESET)"

# Push image to registry
push: build
	@echo "$(YELLOW)Pushing image to registry...$(RESET)"
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	@echo "$(GREEN)Image pushed successfully!$(RESET)"

# Open shell in running container
shell:
	@echo "$(YELLOW)Opening shell in container...$(RESET)"
	docker exec -it $(CONTAINER_NAME) /bin/bash

# Show status
status:
	@echo "$(YELLOW)Container status:$(RESET)"
	@docker ps -a | grep $(CONTAINER_NAME) || echo "$(RED)Container not found.$(RESET)"

# Complete rebuild (clean + build)
rebuild: clean build

# Check health of deployed service
health:
	@echo "$(YELLOW)Checking health of deployed Function App...$(RESET)"
	@curl -s https://$(FUNCTION_APP_NAME).azurewebsites.net/api/health | python -m json.tool || \
		echo "$(RED)Health check failed$(RESET)"
