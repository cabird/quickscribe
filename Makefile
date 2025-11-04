# QuickScribe Root Makefile
# Provides convenience commands for building shared models

SHARED_DIR = shared
BACKEND_DIR = backend
SHARED_PY_DIR = shared_quickscribe_py/shared_quickscribe_py/cosmos
BACKEND_MODELS = $(BACKEND_DIR)/db_handlers/models.py
SHARED_PY_MODELS = $(SHARED_PY_DIR)/models.py
SCHEMA_OUTPUT = $(SHARED_DIR)/models.schema.json
MODELS_INPUT = $(SHARED_DIR)/Models.ts

.PHONY: build-models help clean-models

help:
	@echo "QuickScribe Root Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  build-models    - Build Python models from TypeScript definitions"
	@echo "  clean-models    - Remove generated model files"
	@echo "  help           - Show this help message"
	@echo ""
	@echo "Usage:"
	@echo "  make build-models    # Generates models.py in backend and shared_quickscribe_py"
	@echo ""
	@echo "Output locations:"
	@echo "  - backend/db_handlers/models.py"
	@echo "  - shared_quickscribe_py/shared_quickscribe_py/cosmos/models.py"

# Build Python models from shared TypeScript definitions
build-models: $(BACKEND_MODELS) $(SHARED_PY_MODELS)

$(BACKEND_MODELS): $(MODELS_INPUT)
	@echo "Building Python models from shared/Models.ts..."
	@echo "Step 1: Generating JSON schema..."
	typescript-json-schema $(MODELS_INPUT) "*" --propOrder --required --out $(SCHEMA_OUTPUT)
	@echo "Step 2: Generating Pydantic models for backend..."
	datamodel-codegen --input $(SCHEMA_OUTPUT) --input-file-type jsonschema \
		--output-model-type pydantic_v2.BaseModel --use-subclass-enum \
		--output $(BACKEND_MODELS)
	@echo "✓ Backend models built at $(BACKEND_MODELS)"

$(SHARED_PY_MODELS): $(BACKEND_MODELS)
	@echo "Step 3: Copying models to shared_quickscribe_py..."
	cp $(BACKEND_MODELS) $(SHARED_PY_MODELS)
	@echo "✓ Shared models built at $(SHARED_PY_MODELS)"

# Clean generated files
clean-models:
	@echo "Cleaning generated model files..."
	rm -f $(BACKEND_MODELS)
	rm -f $(SHARED_PY_MODELS)
	rm -f $(SCHEMA_OUTPUT)
	@echo "✓ Cleaned"

# Alias for convenience
build: build-models
