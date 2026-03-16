# Makefile for Speaker Identification Service

# Configuration
JOB_NAME = quickscribe-speaker-id-job
IMAGE_NAME = speaker-id
VERSION = $(shell grep SERVICE_VERSION src/service_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')
REGISTRY = quickscribecontainerregistry.azurecr.io
AZURE_ACR_NAME = quickscribecontainerregistry
AZURE_RESOURCE_GROUP = QuickScribeResourceGroup

# Function to dynamically get the current version at runtime
get_version = $(shell grep SERVICE_VERSION src/service_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')

# Environment file for local development
ENV_FILE = .env

# Colors for output
RED = \033[31m
GREEN = \033[32m
YELLOW = \033[33m
BLUE = \033[34m
RESET = \033[0m

.PHONY: help bump_version bump-deploy build push create azure-config azure-deploy run history logs status delete test-local

# Default target
help:
	@echo "$(BLUE)Speaker Identification Service Makefile$(RESET)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(GREEN)build$(RESET)                - Build container image"
	@echo "  $(GREEN)push$(RESET)                 - Push image to Azure Container Registry"
	@echo "  $(GREEN)create$(RESET)               - Create Container Apps Job with cron schedule"
	@echo "  $(GREEN)azure-config$(RESET)         - Configure environment variables from .env"
	@echo "  $(GREEN)azure-deploy$(RESET)         - Build, push, and update image"
	@echo "  $(GREEN)run$(RESET)                  - Manually trigger execution"
	@echo "  $(GREEN)history$(RESET)              - View execution history"
	@echo "  $(GREEN)logs$(RESET)                 - View logs for latest execution"
	@echo "  $(GREEN)status$(RESET)               - Show current status"
	@echo "  $(GREEN)delete$(RESET)               - Delete the Container Apps Job"
	@echo "  $(GREEN)test-local$(RESET)           - Test locally with Docker"
	@echo "  $(GREEN)bump_version$(RESET)         - Bump version using bump2version"
	@echo ""

# Bump version and deploy
bump-deploy:
	@echo "$(YELLOW)Bumping version...$(RESET)"
	$(MAKE) bump_version
	@echo "$(YELLOW)Building and deploying new version: $(call get_version)$(RESET)"
	$(MAKE) azure-deploy
	@echo "$(GREEN)Version $(call get_version) built and deployed successfully!$(RESET)"

# Bump version
bump_version:
	@if [ -f .venv/bin/bump2version ]; then \
		.venv/bin/bump2version --allow-dirty patch; \
	elif command -v bump2version &> /dev/null; then \
		bump2version --allow-dirty patch; \
	else \
		echo "$(RED)Error: bump2version not found. Install with: pip install bump2version$(RESET)"; \
		exit 1; \
	fi
	@cat src/service_version.py

# Build container image
build:
	@echo "$(YELLOW)Building container image version $(call get_version)...$(RESET)"
	$(eval TEMP_DIR := speaker_id_deploy_$(call get_version))

	@echo "Creating temporary deployment directory..."
	mkdir -p $(TEMP_DIR)

	@echo "Copying Dockerfile..."
	cp Dockerfile $(TEMP_DIR)/

	@echo "Copying shared_quickscribe_py library..."
	cp -r ../shared_quickscribe_py $(TEMP_DIR)/shared_quickscribe_py

	@echo "Copying speaker_id_service files..."
	mkdir -p $(TEMP_DIR)/speaker_id_service
	cp requirements.txt $(TEMP_DIR)/speaker_id_service/
	cp -r src $(TEMP_DIR)/speaker_id_service/

	@echo "Cleaning __pycache__ directories..."
	find $(TEMP_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

	@echo "Building Docker image..."
	docker build -f $(TEMP_DIR)/Dockerfile -t $(IMAGE_NAME):$(call get_version) $(TEMP_DIR)
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	docker tag $(IMAGE_NAME):$(call get_version) $(REGISTRY)/$(IMAGE_NAME):latest

	@echo "Cleaning up temporary files..."
	rm -rf $(TEMP_DIR)

	@echo "$(GREEN)Built and tagged version $(call get_version)$(RESET)"

# Push to ACR
push:
	@echo "$(YELLOW)Pushing version $(call get_version) to Azure Container Registry...$(RESET)"
	az acr login --name $(AZURE_ACR_NAME) || \
		(ACR_PASSWORD=$$(az acr credential show --name $(AZURE_ACR_NAME) --query "passwords[0].value" -o tsv) && \
		echo $$ACR_PASSWORD | docker login $(REGISTRY) --username $(AZURE_ACR_NAME) --password-stdin)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	docker push $(REGISTRY)/$(IMAGE_NAME):latest
	@echo "$(GREEN)Pushed version $(call get_version)$(RESET)"

# Create Container Apps Job with cron schedule
create:
	@echo "$(YELLOW)Creating Container Apps Job...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Getting registry credentials...$(RESET)"
	@bash -c ' \
	ACR_PASSWORD=$$(az acr credential show --name $(AZURE_ACR_NAME) --query "passwords[0].value" -o tsv); \
	az containerapp job create \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--environment quickscribe-env \
		--image $(REGISTRY)/$(IMAGE_NAME):latest \
		--registry-server $(REGISTRY) \
		--registry-username $(AZURE_ACR_NAME) \
		--registry-password "$$ACR_PASSWORD" \
		--trigger-type Schedule \
		--replica-timeout 1800 \
		--replica-retry-limit 3 \
		--parallelism 1 \
		--replica-completion-count 1 \
		--cpu 1 \
		--memory 2Gi \
		--env-vars SERVICE_VERSION=$(call get_version) \
		--cron-expression "*/30 * * * *"; \
	'
	@echo "$(GREEN)Container Apps Job created: $(JOB_NAME)$(RESET)"
	@echo "$(BLUE)Scheduled to run every 30 minutes$(RESET)"

# Configure environment variables from .env file
azure-config:
	@echo "$(YELLOW)Configuring environment variables from .env file...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		exit 1; \
	fi
	@bash -c ' \
	ENV_VARS=""; \
	while IFS= read -r line || [[ -n "$$line" ]]; do \
		line=$$(echo "$$line" | sed "s/^[[:space:]]*//;s/[[:space:]]*$$//"); \
		if [[ "$$line" =~ ^#.*$$ ]] || [[ -z "$$line" ]]; then continue; fi; \
		key=$$(echo "$$line" | cut -d= -f1); \
		value=$$(echo "$$line" | cut -d= -f2-); \
		ENV_VARS="$$ENV_VARS $$key=$$value"; \
	done < $(ENV_FILE); \
	az containerapp job update \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--set-env-vars $$ENV_VARS SERVICE_VERSION=$(call get_version); \
	'
	@echo "$(GREEN)Environment variables configured successfully!$(RESET)"

# Deploy: build, push, and update image
azure-deploy: build push
	@echo "$(YELLOW)Deploying version $(call get_version)...$(RESET)"
	az containerapp job update \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--image $(REGISTRY)/$(IMAGE_NAME):$(call get_version)
	@echo "$(GREEN)Deployed version $(call get_version)$(RESET)"
	@echo ""
	@echo "$(YELLOW)NOTE: Environment variables were NOT updated.$(RESET)"
	@echo "$(YELLOW)If you changed any values in .env, run: make azure-config$(RESET)"

# Manually trigger execution
run:
	@echo "$(YELLOW)Manually triggering execution...$(RESET)"
	az containerapp job start \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP)
	@echo "$(GREEN)Execution started$(RESET)"

# View execution history
history:
	@echo "$(YELLOW)Execution history:$(RESET)"
	az containerapp job execution list \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--output table

# View logs for latest execution
logs:
	@echo "$(YELLOW)Fetching latest logs...$(RESET)"
	@LATEST_EXEC=$$(az containerapp job execution list \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--query "[0].name" -o tsv); \
	if [ -z "$$LATEST_EXEC" ]; then \
		echo "$(RED)No executions found$(RESET)"; \
	else \
		echo "$(YELLOW)Showing logs for execution: $$LATEST_EXEC$(RESET)"; \
		az containerapp job logs show \
			--name $(JOB_NAME) \
			--resource-group $(AZURE_RESOURCE_GROUP) \
			--execution $$LATEST_EXEC \
			--container $(JOB_NAME); \
	fi

# Show current status
status:
	@echo "$(YELLOW)Current status:$(RESET)"
	az containerapp job show \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--query "{name:name,state:properties.provisioningState,schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" \
		-o table

# Delete the Container Apps Job
delete:
	@echo "$(RED)Deleting Container Apps Job...$(RESET)"
	@read -p "Are you sure you want to delete $(JOB_NAME)? (y/N) " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		az containerapp job delete \
			--name $(JOB_NAME) \
			--resource-group $(AZURE_RESOURCE_GROUP) \
			--yes; \
		echo "$(GREEN)Job deleted$(RESET)"; \
	else \
		echo "$(YELLOW)Cancelled$(RESET)"; \
	fi

# Test locally with Docker
test-local: build
	@echo "$(YELLOW)Running locally with Docker...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		exit 1; \
	fi
	docker run --rm --env-file $(ENV_FILE) $(IMAGE_NAME):$(call get_version)
