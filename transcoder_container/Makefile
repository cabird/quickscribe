# Makefile for Transcoder Container App

# Configuration
APP_NAME = quickscribetranscoder
IMAGE_NAME = transcoder-container
CONTAINER_NAME = $(IMAGE_NAME)-local
VERSION = $(shell grep CONTAINER_APP_VERSION container_app_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')
#read this from the .env file
TRANSCODING_QUEUE_NAME = $(shell grep TRANSCODING_QUEUE_NAME .env | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')
REGISTRY = quickscribecontainerregistry.azurecr.io
AZURE_ACR_NAME = quickscribecontainerregistry
AZURE_RESOURCE_GROUP = QuickScribeResourceGroup

# Function to dynamically get the current version at runtime
get_version = $(shell grep CONTAINER_APP_VERSION container_app_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')

# Environment file for local development
ENV_FILE = .env.local

# Colors for output
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
BLUE = \033[34m
RESET = \033[0m

.PHONY: build_packages bump_version build_zip clean build

# Default target
help:
	@echo "$(BLUE)Transcoder Container Makefile$(RESET)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(GREEN)build$(RESET)        - Build the Docker image"
	@echo "  $(GREEN)run$(RESET)          - Run the container locally"
	@echo "  $(GREEN)stop$(RESET)         - Stop the running container"
	@echo "  $(GREEN)logs$(RESET)         - Show container logs"
	@echo "  $(GREEN)clean$(RESET)        - Remove container and image"
	@echo "  $(GREEN)test$(RESET)         - Run tests"
	@echo "  $(GREEN)schemas$(RESET)      - Generate JSON schemas from TypeScript"
	@echo "  $(GREEN)push$(RESET)         - Push image to registry"
	@echo "  $(GREEN)shell$(RESET)        - Open shell in running container"
	@echo "  $(GREEN)deploy-local$(RESET) - Deploy with docker-compose"
	@echo "  $(GREEN)dev$(RESET)          - Start development environment"
	@echo "  $(GREEN)bump-deploy$(RESET)  - Bump version, build, and deploy in one command"
	@echo ""

# Bump version and deploy in a single command
bump-deploy:
	@echo "$(YELLOW)Bumping version...$(RESET)"
	$(MAKE) bump_version
	@echo "$(YELLOW)Building and deploying new version: $(call get_version)$(RESET)"
	$(MAKE) azure-deploy
	@echo "$(GREEN)Version $(call get_version) built and deployed successfully!$(RESET)"

repo2file:
	repo2file . repo.txt repo2file.exclusion .py 

bump_version:
	bump2version --allow-dirty patch
	@cat container_app_version.py

# build the docker image
build:
	@echo "$(YELLOW)Building Docker image...$(RESET)"
	docker build -t $(IMAGE_NAME):$(call get_version) .
	@echo "$(GREEN)Docker image built successfully!$(RESET)"

# Azure build with current version
azure-build:
	@echo "$(YELLOW)Building and tagging for Azure with version: $(call get_version)$(RESET)"
	docker build -t $(IMAGE_NAME):$(call get_version) .
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(APP_NAME):$(call get_version)
	@echo "$(GREEN)Built and tagged version $(call get_version)$(RESET)"

# Azure push with current version
azure-push:
	@echo "$(YELLOW)Pushing version $(call get_version) to Azure Container Registry...$(RESET)"
	az acr login --name $(AZURE_ACR_NAME)
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	@echo "$(GREEN)Pushed version $(call get_version)$(RESET)"

# Azure deploy with current version
azure-deploy: azure-build azure-push
	@echo "$(YELLOW)Deploying version $(call get_version) to Azure Container Apps...$(RESET)"
	az containerapp update \
		--name $(APP_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--image $(REGISTRY)/$(IMAGE_NAME):$(call get_version) \
		--cpu 1.0 \
      	--memory 2.0Gi
	@echo "$(YELLOW)add queue scaling rules to Azure Container Apps...$(RESET)"
	az containerapp update \
		--name quickscribetranscoder \
		--resource-group QuickScribeResourceGroup \
		--scale-rule-name queue-scale \
		--scale-rule-type azure-queue \
		--scale-rule-metadata queueName="$(TRANSCODING_QUEUE_NAME)" queueLength="1" \
		--scale-rule-auth connection=AZURE_STORAGE_CONNECTION_STRING \
		--min-replicas 0 \
		--max-replicas 1
	@echo "$(YELLOW)Checking deployment status...$(RESET)"
	az containerapp show \
		--name quickscribetranscoder \
		--resource-group QuickScribeResourceGroup \
		--query "{Name:name, Status:properties.provisioningState, Image:properties.template.containers[0].image}" \
		--output table
	@echo "$(GREEN)Deployed version $(call get_version)$(RESET)"


# Run the container locally
run: build
	@echo "$(YELLOW)Starting container...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found. Please create it with required environment variables.$(RESET)"; \
		echo "$(BLUE)Example:$(RESET)"; \
		echo "AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=..."; \
		echo "TRANSCODING_QUEUE_NAME=transcoding-queue"; \
		exit 1; \
	fi
	docker run -d \
		--name $(CONTAINER_NAME) \
		--env-file $(ENV_FILE) \
		--restart unless-stopped \
		$(IMAGE_NAME):$(call get_version)
	@echo "$(GREEN)Container started successfully!$(RESET)"
	@echo "$(BLUE)Container ID: $$(docker ps -q -f name=$(CONTAINER_NAME))$(RESET)"

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

# Restart container
restart: stop run

status:
	@echo "$(YELLOW)Container status:$(RESET)"
	@docker ps -a | grep $(CONTAINER_NAME) || echo "$(RED)Container not found.$(RESET)"

# Complete rebuild (clean + build)
rebuild: clean build

monitor:
	@echo "$(YELLOW)Monitoring container logs...$(RESET)"
	@echo "$(BLUE)Press Ctrl+C to stop monitoring$(RESET)"
	docker logs -f $(CONTAINER_NAME)
