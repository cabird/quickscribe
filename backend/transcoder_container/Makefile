# Makefile for Transcoder Container App

# Configuration
APP_NAME = transcoder-container
IMAGE_NAME = $(APP_NAME)
CONTAINER_NAME = $(APP_NAME)-local
VERSION := $(shell python -c "exec(open('container_app_version.py').read()); print(CONTAINER_APP_VERSION)")
REGISTRY = quickscribecontainerregistry.azurecr.io
AZURE_ACR_NAME = quickscribecontainerregistry
AZURE_RESOURCE_GROUP = QuickScribeResourceGroup

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
	@echo ""

repo2file:
	repo2file . repo.txt repo2file.exclusion .py 

bump_version:
	bump2version --allow-dirty patch
	@cat container_app_version.py

# build the docker image
build:
	@echo "$(YELLOW)Building Docker image...$(RESET)"
	docker build -t $(IMAGE_NAME):$(VERSION) .
	@echo "$(GREEN)Docker image built successfully!$(RESET)"

# Azure build with stored version
azure-build:
	@echo "$(YELLOW)Building and tagging for Azure with version: $(VERSION)$(RESET)"
	docker build -t $(IMAGE_NAME):$(VERSION) .
	docker tag $(IMAGE_NAME):$(VERSION) $(REGISTRY)/$(APP_NAME):$(VERSION)
	@echo "$(GREEN)Built and tagged version $(VERSION)$(RESET)"

# Azure push with stored version
azure-push:
	@echo "$(YELLOW)Pushing version $(VERSION) to Azure Container Registry...$(RESET)"
	az acr login --name $(AZURE_ACR_NAME)
	docker push $(REGISTRY)/$(APP_NAME):$(VERSION)
	@echo "$(GREEN)Pushed version $(VERSION)$(RESET)"

# Azure deploy with stored version
azure-deploy:
	@echo "$(YELLOW)Deploying version $(VERSION) to Azure Container Apps...$(RESET)"
	az containerapp update \
		--name $(APP_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--image $(REGISTRY)/$(APP_NAME):$(VERSION) \
	@echo "$(GREEN)Deployed version $(VERSION)$(RESET)"

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
		$(IMAGE_NAME):$(VERSION)
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
	@docker rmi $(IMAGE_NAME):$(VERSION) || true
	@echo "$(GREEN)Cleanup complete.$(RESET)"

# Push image to registry
push: build
	@echo "$(YELLOW)Pushing image to registry...$(RESET)"
	docker tag $(IMAGE_NAME):$(VERSION) $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
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