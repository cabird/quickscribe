RESOURCE_GROUP = QuickScribeResourceGroup
APP_NAME = QuickScribeWebApp
CONTAINER_REGISTRY = quickscribecontainerregistry
IMAGE_NAME = quickscribe-backend
LOCATION = westus2
APP_SERVICE_PLAN_LOCATION = westus
APP_SERVICE_PLAN_NAME = quickscribe-container-appservice-plan
APP_SERVICE_PLAN_SKU = B2
SHARED_DIR = ../shared
SHARED_QUICKSCRIBE_PY = ../shared_quickscribe_py
LOCAL_CONTAINER_NAME = quickscribe-local

# Get version from api_version.py
VERSION := $(shell python -c "import sys; sys.path.insert(0, 'src'); from api_version import API_VERSION; print(API_VERSION)")

.PHONY: bump_version clean build_container deploy_azure deploy_local setup_container_infrastructure docker_stop local_run compose_up compose_down compose_logs deploy setup

default: setup

repo2file:
	repo2file . repo.txt repo2file.exclusion .py .ts Makefile

# Install shared_quickscribe_py in editable mode for local development
setup:
	@echo "Installing shared_quickscribe_py in editable mode..."
	pip install -e $(SHARED_QUICKSCRIBE_PY)

bump_version:
	bump2version --allow-dirty patch
	@cat src/api_version.py

# Local development targets
local_run: setup
	@echo "Starting local development server..."
	cd src && python app.py

# Build Docker container image
build_container:
	@echo "=== Building Docker container image ==="
	@echo "Version: $(VERSION)"
	$(eval TEMP_DIR := quickscribe_deploy_$(VERSION))

	@echo "Creating temporary deployment directory..."
	mkdir -p $(TEMP_DIR)
	cp Dockerfile $(TEMP_DIR)/

	@echo "Copying shared_quickscribe_py library..."
	cp -r $(SHARED_QUICKSCRIBE_PY) $(TEMP_DIR)/shared_quickscribe_py

	@echo "Verifying required environment files..."
	@if [ ! -f ".env.local" ]; then \
		echo "ERROR: .env.local file is required but not found"; \
		exit 1; \
	fi
	@if [ ! -f ".env.azure" ]; then \
		echo "ERROR: .env.azure file is required but not found"; \
		exit 1; \
	fi

	@echo "Copying environment files..."
	cp .env.local $(TEMP_DIR)/.env.local
	cp .env.azure $(TEMP_DIR)/.env.azure

	@echo "Generating file list and copying files..."
	python generate_filelist.py
	@while IFS= read -r file; do \
		case "$$file" in \
			\#*|"") continue ;; \
		esac; \
		parent_dir=$$(dirname "$(TEMP_DIR)/$$file"); \
		mkdir -p "$$parent_dir"; \
		if [ -d "$$file" ]; then \
			echo "Copying directory: $$file"; \
			cp -r "$$file" "$$parent_dir/"; \
		elif [ -f "$$file" ]; then \
			echo "Copying file: $$file"; \
			cp "$$file" "$(TEMP_DIR)/$$file"; \
		else \
			echo "Warning: File not found: $$file"; \
		fi; \
	done < filelist.txt

	@echo "Cleaning __pycache__ directories..."
	find $(TEMP_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME):$(VERSION) -t $(IMAGE_NAME):latest $(TEMP_DIR)

	@echo "Cleaning up temporary files..."
	rm -rf $(TEMP_DIR)

	@echo ""
	@echo "=== Docker image built: $(IMAGE_NAME):$(VERSION) ==="
	@echo ""

# Local Docker deployment target
deploy_local: build_container
	@echo "=== Deploying QuickScribe locally with Docker ==="
	@echo "Version: $(VERSION)"

	@echo "Stopping any existing container..."
	-docker stop $(LOCAL_CONTAINER_NAME) 2>/dev/null || true
	-docker rm $(LOCAL_CONTAINER_NAME) 2>/dev/null || true

	@echo "Starting container..."
	@echo "Container will use .env.local (copied to .env by startup.sh)"
	docker run -d --name $(LOCAL_CONTAINER_NAME) -p 5000:8000 \
		-e PORT=8000 \
		$(IMAGE_NAME):latest

	@echo ""
	@echo "=== Local Deployment Complete ==="
	@echo "App available at: http://localhost:5000"
	@echo "Container logs: docker logs -f $(LOCAL_CONTAINER_NAME)"
	@echo "Stop container: docker stop $(LOCAL_CONTAINER_NAME)"
	@echo ""

docker_stop:
	@echo "Stopping and removing local Docker container..."
	-docker stop $(LOCAL_CONTAINER_NAME)
	-docker rm $(LOCAL_CONTAINER_NAME)

# Docker Compose targets
compose_up: setup
	@echo "Starting full stack with docker-compose..."
	@echo "Backend: http://localhost:5000"
	@echo "Frontend: http://localhost:3000"
	cd .. && docker-compose up -d

compose_down:
	@echo "Stopping docker-compose services..."
	cd .. && docker-compose down

compose_logs:
	@echo "Following docker-compose logs..."
	cd .. && docker-compose logs -f

clean:
	rm -rf filelist.txt
	rm -rf quickscribe_deploy_*
	-docker stop $(LOCAL_CONTAINER_NAME) 2>/dev/null || true
	-docker rm $(LOCAL_CONTAINER_NAME) 2>/dev/null || true

# Azure container deployment targets
setup_container_infrastructure:
	@echo "Setting up container infrastructure..."
	az group create --name $(RESOURCE_GROUP) --location $(LOCATION)
	az acr create --resource-group $(RESOURCE_GROUP) --name $(CONTAINER_REGISTRY) --sku Basic --admin-enabled true
	az acr login --name $(CONTAINER_REGISTRY)

deploy_azure: build_container
	@echo "=== Deploying to Azure: $(APP_NAME) version $(VERSION) ==="
	@echo "Ensure you are logged in to Azure CLI with Contributor permissions"
	@echo ""

	@echo "Getting Azure Container Registry credentials..."
	$(eval ACR_LOGIN_SERVER := $(shell az acr show --name $(CONTAINER_REGISTRY) --query loginServer -o tsv))
	$(eval ACR_USERNAME := $(shell az acr credential show --name $(CONTAINER_REGISTRY) --query username -o tsv))
	$(eval ACR_PASSWORD := $(shell az acr credential show --name $(CONTAINER_REGISTRY) --query passwords[0].value -o tsv))
	@echo "ACR Login Server: $(ACR_LOGIN_SERVER)"

	@echo "Logging Docker into Azure Container Registry..."
	@echo "$(ACR_PASSWORD)" | docker login $(ACR_LOGIN_SERVER) -u $(ACR_USERNAME) --password-stdin

	@echo "Tagging image for Azure Container Registry..."
	docker tag $(IMAGE_NAME):$(VERSION) $(ACR_LOGIN_SERVER)/$(IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME):latest $(ACR_LOGIN_SERVER)/$(IMAGE_NAME):latest

	@echo "Pushing Docker image to Azure Container Registry..."
	docker push $(ACR_LOGIN_SERVER)/$(IMAGE_NAME):$(VERSION)
	docker push $(ACR_LOGIN_SERVER)/$(IMAGE_NAME):latest

	@echo "Checking if web app exists..."
	$(eval APP_EXISTS := $(shell az webapp list --query "[?name=='$(APP_NAME)']" -o tsv))
	@if [ -z "$(APP_EXISTS)" ]; then \
		echo "Creating app service plan..."; \
		az appservice plan create --resource-group $(RESOURCE_GROUP) \
			--location $(APP_SERVICE_PLAN_LOCATION) \
			--name $(APP_SERVICE_PLAN_NAME) \
			--is-linux --sku $(APP_SERVICE_PLAN_SKU); \
		echo "Creating new web app..."; \
		az webapp create --resource-group $(RESOURCE_GROUP) --name $(APP_NAME) \
			--plan $(APP_SERVICE_PLAN_NAME) \
			--deployment-container-image-name "$(ACR_LOGIN_SERVER)/$(IMAGE_NAME):$(VERSION)"; \
	else \
		echo "Updating existing web app..."; \
		az webapp config container set --resource-group $(RESOURCE_GROUP) --name $(APP_NAME) \
			--container-image-name "$(ACR_LOGIN_SERVER)/$(IMAGE_NAME):$(VERSION)" \
			--container-registry-url "https://$(ACR_LOGIN_SERVER)" \
			--container-registry-user "$(ACR_USERNAME)" \
			--container-registry-password "$(ACR_PASSWORD)"; \
	fi

	@echo "Configuring web app settings..."
	@if [ -f "startup.sh" ]; then \
		echo "Setting startup file..."; \
		az webapp config set --resource-group $(RESOURCE_GROUP) --name $(APP_NAME) \
			--startup-file "/app/startup.sh"; \
	fi

	@echo "Setting container registry credentials as app settings..."
	az webapp config appsettings set --resource-group $(RESOURCE_GROUP) --name $(APP_NAME) \
		--settings \
		DOCKER_REGISTRY_SERVER_URL="https://$(ACR_LOGIN_SERVER)" \
		DOCKER_REGISTRY_SERVER_USERNAME="$(ACR_USERNAME)" \
		DOCKER_REGISTRY_SERVER_PASSWORD="$(ACR_PASSWORD)" \
		WEBSITES_PORT=8000 \
		>/dev/null

	@echo "Application configuration loaded from .env.azure file baked into Docker image"

	@echo "Enabling continuous deployment..."
	az webapp deployment container config --enable-cd true \
		--resource-group $(RESOURCE_GROUP) --name $(APP_NAME)

	$(eval APP_URL := $(shell az webapp show --resource-group $(RESOURCE_GROUP) --name $(APP_NAME) --query defaultHostName -o tsv))
	@echo ""
	@echo "=== Deployment Complete ==="
	@echo "App available at: https://$(APP_URL)"
	@echo "Version deployed: $(VERSION)"
	@echo ""

# Default deploy target points to Azure deployment
deploy: deploy_azure
