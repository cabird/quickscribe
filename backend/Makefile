RESOURCE_GROUP = QuickScribeResourceGroup
APP_NAME = QuickScribeWebApp
CONTAINER_APP_NAME = quickscribe-containerized-webapp
CONTAINER_REGISTRY = quickscribecontainerregistry
IMAGE_NAME = quickscribe-backend
LOCATION = westus2
APP_SERVICE_PLAN_LOCATION = westus
APP_SERVICE_PLAN_NAME = quickscribe-container-appservice-plan
APP_SERVICE_PLAN_SKU = B2
SPEECH_CLIENT_DIR = azure_speech/python-client
SHARED_DIR = ../shared

# Get version from api_version.py
VERSION := $(shell python -c "from api_version import API_VERSION; print(API_VERSION)")

.PHONY: build_packages bump_version build_zip clean build deploy_container setup_container_infrastructure docker_build docker_run docker_stop local_run compose_up compose_down compose_logs

default: build

repo2file:
	repo2file . repo.txt repo2file.exclusion .py .ts Makefile

build: db_handlers/models.py

db_handlers/models.py: $(SHARED_DIR)/Models.ts
	typescript-json-schema $(SHARED_DIR)/Models.ts "*" --propOrder --required --out $(SHARED_DIR)/models.schema.json 
	datamodel-codegen --input $(SHARED_DIR)/models.schema.json --input-file-type jsonschema  --output-model-type pydantic_v2.BaseModel --use-subclass-enum --output db_handlers/models.py

build_packages:
	$(MAKE) -C $(SPEECH_CLIENT_DIR) build
	mkdir -p local_packages
	cp $(SPEECH_CLIENT_DIR)/dist/*whl local_packages

bump_version:
	bump2version --allow-dirty patch
	@cat api_version.py

build_zip: build_packages
	rm -f app.zip
	pip freeze | grep -v "swagger_client" > requirements.txt
	python generate_filelist.py
	zip app.zip -@ < filelist.txt

deploy_azure: build_zip
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	# set an app setting to force a build during deployment
	az webapp config appsettings set --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false
	az webapp deploy --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --type zip --src-path app.zip

deploy_to_test: build_zip
	@echo "Ensure that you are logged in to the Azure CLI *AND* that you have elevated your permissions to the Contributor."
	# set an app setting to force a build during deployment
	az webapp config appsettings set --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --slot test --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false
	az webapp deploy --name $(APP_NAME) --resource-group $(RESOURCE_GROUP) --slot test --type zip --src-path app.zip

deploy: deploy_azure

# Local development targets
local_run: build
	@echo "Starting local development server..."
	python app.py

# Local Docker targets
docker_build: build
	@echo "Building Docker image locally (version $(VERSION))..."
	python generate_filelist.py
	docker build -t $(IMAGE_NAME):$(VERSION) -t $(IMAGE_NAME):latest .

docker_run: docker_build
	@echo "Running Docker container locally on port 5000..."
	@echo "App will be available at http://localhost:5000"
	@if [ -f ".env.local" ]; then \
		echo "Using .env.local file..."; \
		docker run -d --name quickscribe-local -p 5000:8000 \
			--env-file .env.local \
			$(IMAGE_NAME):latest; \
	elif [ -f ".env" ]; then \
		echo "Using .env file..."; \
		docker run -d --name quickscribe-local -p 5000:8000 \
			--env-file .env \
			$(IMAGE_NAME):latest; \
	else \
		echo "No .env file found, running without environment file..."; \
		docker run -d --name quickscribe-local -p 5000:8000 \
			$(IMAGE_NAME):latest; \
	fi

docker_stop:
	@echo "Stopping and removing local Docker container..."
	-docker stop quickscribe-local
	-docker rm quickscribe-local

# Docker Compose targets
compose_up: build
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
	$(MAKE) -C $(SPEECH_CLIENT_DIR) clean
	rm -rf local_packages
	rm -rf app.zip
	rm -rf filelist.txt
	rm -rf quickscribe_deploy_*
	-docker stop quickscribe-local 2>/dev/null || true
	-docker rm quickscribe-local 2>/dev/null || true

# Container deployment targets
setup_container_infrastructure:
	@echo "Setting up container infrastructure..."
	az group create --name $(RESOURCE_GROUP) --location $(LOCATION)
	az acr create --resource-group $(RESOURCE_GROUP) --name $(CONTAINER_REGISTRY) --sku Basic --admin-enabled true
	az acr login --name $(CONTAINER_REGISTRY)

deploy_container: build
	@echo "=== Deploying containerized web app version $(VERSION) ==="
	@echo "Creating temporary deployment directory..."
	$(eval TEMP_DIR := quickscribe_deploy_$(VERSION))
	mkdir -p $(TEMP_DIR)
	cp Dockerfile $(TEMP_DIR)/
	
	@echo "Verifying required environment files..."
	@if [ ! -f ".env.local" ]; then \
		echo "ERROR: .env.local file is required but not found"; \
		exit 1; \
	fi
	@if [ ! -f ".env.production" ]; then \
		echo "ERROR: .env.production file is required but not found"; \
		exit 1; \
	fi
	
	@echo "Copying environment files..."
	cp .env.local $(TEMP_DIR)/.env.local
	cp .env.production $(TEMP_DIR)/.env.production
	
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
	
	@echo "Building and pushing Docker image version $(VERSION)..."
	az acr build --registry $(CONTAINER_REGISTRY) --image $(IMAGE_NAME):$(VERSION) --image $(IMAGE_NAME):latest $(TEMP_DIR)
	
	@echo "Getting container registry credentials..."
	$(eval ACR_USERNAME := $(shell az acr credential show --name $(CONTAINER_REGISTRY) --query username -o tsv))
	$(eval ACR_PASSWORD := $(shell az acr credential show --name $(CONTAINER_REGISTRY) --query passwords[0].value -o tsv))
	$(eval ACR_LOGIN_SERVER := $(shell az acr show --name $(CONTAINER_REGISTRY) --query loginServer -o tsv))
	
	@echo "Checking if web app exists..."
	$(eval APP_EXISTS := $(shell az webapp list --query "[?name=='$(CONTAINER_APP_NAME)']" -o tsv))
	@if [ -z "$(APP_EXISTS)" ]; then \
		echo "Creating app service plan..."; \
		az appservice plan create --resource-group $(RESOURCE_GROUP) \
			--location $(APP_SERVICE_PLAN_LOCATION) \
			--name $(APP_SERVICE_PLAN_NAME) \
			--is-linux --sku $(APP_SERVICE_PLAN_SKU); \
		echo "Creating new web app..."; \
		az webapp create --resource-group $(RESOURCE_GROUP) --name $(CONTAINER_APP_NAME) \
			--plan $(APP_SERVICE_PLAN_NAME) \
			--deployment-container-image-name "$(ACR_LOGIN_SERVER)/$(IMAGE_NAME):$(VERSION)"; \
	else \
		echo "Updating existing web app..."; \
		az webapp config container set --resource-group $(RESOURCE_GROUP) --name $(CONTAINER_APP_NAME) \
			--container-image-name "$(ACR_LOGIN_SERVER)/$(IMAGE_NAME):$(VERSION)" \
			--container-registry-url "https://$(ACR_LOGIN_SERVER)" \
			--container-registry-user "$(ACR_USERNAME)" \
			--container-registry-password "$(ACR_PASSWORD)"; \
	fi
	
	@echo "Configuring web app settings..."
	@if [ -f "startup.sh" ]; then \
		echo "Setting startup file..."; \
		az webapp config set --resource-group $(RESOURCE_GROUP) --name $(CONTAINER_APP_NAME) \
			--startup-file "/app/startup.sh"; \
	fi
	
	@echo "Environment configuration handled by startup.sh in Docker image"
	
	@echo "Enabling continuous deployment..."
	az webapp deployment container config --enable-cd true \
		--resource-group $(RESOURCE_GROUP) --name $(CONTAINER_APP_NAME)
	
	@echo "Cleaning up temporary files..."
	rm -rf $(TEMP_DIR)
	
	$(eval APP_URL := $(shell az webapp show --resource-group $(RESOURCE_GROUP) --name $(CONTAINER_APP_NAME) --query defaultHostName -o tsv))
	@echo ""
	@echo "=== Deployment Complete ==="
	@echo "App available at: https://$(APP_URL)"
	@echo "Version deployed: $(VERSION)"
	@echo ""
