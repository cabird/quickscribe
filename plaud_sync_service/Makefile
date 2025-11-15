# Makefile for Plaud Sync Service (Azure Container Apps Jobs)

# Configuration
JOB_NAME = quickscribe-plaud-sync-job
JOB_IMAGE_NAME = plaud-sync-job
VERSION = $(shell grep SERVICE_VERSION service_version.py | cut -d '=' -f2 | sed "s/['\"]//g" | tr -d '[:space:]')
REGISTRY = quickscribecontainerregistry.azurecr.io
AZURE_ACR_NAME = quickscribecontainerregistry
AZURE_RESOURCE_GROUP = QuickScribeResourceGroup

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

.PHONY: help bump_version bump-deploy build-swagger-client job-build job-push job-create job-config job-deploy job-run job-history job-logs job-status job-delete job-test-local

# Default target
help:
	@echo "$(BLUE)Plaud Sync Service Makefile (Azure Container Apps Jobs)$(RESET)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(GREEN)build-swagger-client$(RESET) - Build Azure Speech Services swagger client wheel"
	@echo "  $(GREEN)job-build$(RESET)            - Build Container Apps Job image"
	@echo "  $(GREEN)job-push$(RESET)             - Push job image to Azure Container Registry"
	@echo "  $(GREEN)job-create$(RESET)           - Create Container Apps Job with cron schedule"
	@echo "  $(GREEN)job-config$(RESET)           - Configure job environment variables from .env"
	@echo "  $(GREEN)job-deploy$(RESET)           - Build, push, and update job image"
	@echo "  $(GREEN)job-run$(RESET)              - Manually trigger job execution"
	@echo "  $(GREEN)job-history$(RESET)          - View job execution history"
	@echo "  $(GREEN)job-logs$(RESET)             - View logs for latest execution"
	@echo "  $(GREEN)job-status$(RESET)           - Show job status"
	@echo "  $(GREEN)job-delete$(RESET)           - Delete the Container Apps Job"
	@echo "  $(GREEN)job-test-local$(RESET)       - Test job locally with Docker"
	@echo "  $(GREEN)bump_version$(RESET)         - Bump version using bump2version"
	@echo ""

# Bump version and deploy in a single command
bump-deploy:
	@echo "$(YELLOW)Bumping version...$(RESET)"
	$(MAKE) bump_version
	@echo "$(YELLOW)Building and deploying new version: $(call get_version)$(RESET)"
	$(MAKE) job-deploy
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


# ============================================================================
# Build Targets
# ============================================================================

# Build Azure Speech Services swagger client wheel
build-swagger-client:
	@echo "$(YELLOW)Building Azure Speech Services swagger client...$(RESET)"
	cd azure_speech/python-client && make build
	@echo "$(GREEN)Swagger client wheel built successfully!$(RESET)"

# ============================================================================
# Azure Container Apps Jobs Targets (scheduled batch jobs)
# ============================================================================

# Build for Container Apps Jobs
job-build:
	@echo "$(YELLOW)Building Container Apps Job image version $(call get_version)...$(RESET)"
	cd .. && docker build -f plaud_sync_service/Dockerfile.job -t $(JOB_IMAGE_NAME):$(call get_version) .
	docker tag $(JOB_IMAGE_NAME):$(call get_version) $(REGISTRY)/$(JOB_IMAGE_NAME):$(call get_version)
	docker tag $(JOB_IMAGE_NAME):$(call get_version) $(REGISTRY)/$(JOB_IMAGE_NAME):latest
	@echo "$(GREEN)Built and tagged version $(call get_version) for Container Apps Jobs$(RESET)"

# Push to ACR
job-push:
	@echo "$(YELLOW)Pushing version $(call get_version) to Azure Container Registry...$(RESET)"
	az acr login --name $(AZURE_ACR_NAME) || \
		(ACR_PASSWORD=$$(az acr credential show --name $(AZURE_ACR_NAME) --query "passwords[0].value" -o tsv) && \
		echo $$ACR_PASSWORD | docker login $(REGISTRY) --username $(AZURE_ACR_NAME) --password-stdin)
	docker push $(REGISTRY)/$(JOB_IMAGE_NAME):$(call get_version)
	docker push $(REGISTRY)/$(JOB_IMAGE_NAME):latest
	@echo "$(GREEN)Pushed version $(call get_version)$(RESET)"

# Create Container Apps Job with cron schedule
job-create:
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
		--image $(REGISTRY)/$(JOB_IMAGE_NAME):latest \
		--registry-server $(REGISTRY) \
		--registry-username $(AZURE_ACR_NAME) \
		--registry-password "$$ACR_PASSWORD" \
		--trigger-type Schedule \
		--replica-timeout 1800 \
		--replica-retry-limit 3 \
		--parallelism 1 \
		--replica-completion-count 1 \
		--cpu 0.5 \
		--memory 1Gi \
		--env-vars SERVICE_VERSION=$(call get_version) \
		--cron-expression "*/15 * * * *"; \
	'
	@echo "$(GREEN)Container Apps Job created: $(JOB_NAME)$(RESET)"
	@echo "$(BLUE)Scheduled to run every 15 minutes$(RESET)"

# Configure job environment variables from .env file
job-config:
	@echo "$(YELLOW)Configuring job environment variables from .env file...$(RESET)"
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
	@echo "$(GREEN)Job environment variables configured successfully!$(RESET)"

# Update job with new image
job-deploy: job-build job-push
	@echo "$(YELLOW)Deploying version $(call get_version) to Container Apps Job...$(RESET)"
	az containerapp job update \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--image $(REGISTRY)/$(JOB_IMAGE_NAME):$(call get_version)
	@echo "$(GREEN)Deployed version $(call get_version) to Container Apps Job$(RESET)"

# Manually trigger the job
job-run:
	@echo "$(YELLOW)Manually triggering job execution...$(RESET)"
	az containerapp job start \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP)
	@echo "$(GREEN)Job execution started$(RESET)"

# View job execution history
job-history:
	@echo "$(YELLOW)Job execution history:$(RESET)"
	az containerapp job execution list \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--output table

# View logs for latest execution
job-logs:
	@echo "$(YELLOW)Fetching latest job logs...$(RESET)"
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

# Show job status
job-status:
	@echo "$(YELLOW)Container Apps Job status:$(RESET)"
	az containerapp job show \
		--name $(JOB_NAME) \
		--resource-group $(AZURE_RESOURCE_GROUP) \
		--query "{name:name,state:properties.provisioningState,schedule:properties.configuration.scheduleTriggerConfig.cronExpression,lastExecution:properties.eventStreamEndpoint}" \
		-o table

# Delete the job
job-delete:
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

# Test job locally with Docker
job-test-local: job-build
	@echo "$(YELLOW)Running job locally with Docker...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		exit 1; \
	fi
	docker run --rm --env-file $(ENV_FILE) $(JOB_IMAGE_NAME):$(call get_version)

.PHONY: job-build job-push job-create job-deploy job-run job-history job-logs job-status job-delete job-test-local

