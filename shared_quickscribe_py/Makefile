SHARED_DIR = ../shared

.PHONY: build clean

default: build

build: shared_quickscribe_py/cosmos/models.py

shared_quickscribe_py/cosmos/models.py: $(SHARED_DIR)/Models.ts
	@echo "Generating JSON schema from TypeScript models..."
	typescript-json-schema $(SHARED_DIR)/Models.ts "*" --propOrder --required --out $(SHARED_DIR)/models.schema.json
	@echo "Generating Pydantic models from JSON schema..."
	datamodel-codegen --input $(SHARED_DIR)/models.schema.json --input-file-type jsonschema --output-model-type pydantic_v2.BaseModel --use-subclass-enum --output shared_quickscribe_py/cosmos/models.py
	@echo "Models generated successfully!"

clean:
	rm -f $(SHARED_DIR)/models.schema.json
	@echo "Cleaned generated files"
