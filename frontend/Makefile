# Makefile in the frontend directory

MODELS_SRC = ../shared/models.ts
MODELS_DEST = ./src/interfaces/models.ts

# The target file depends on the source file, so Make will only copy if necessary
$(MODELS_DEST): $(MODELS_SRC)
	cp $(MODELS_SRC) $(MODELS_DEST)
	@echo "models.ts copied to frontend"

# Default target to call the sync
sync-models: $(MODELS_DEST)
	@echo "models.ts is up to date"
