# QuickScribe Root Makefile
# QuickScribe v2 is the only live system. See v2/SYSTEM_DESCRIPTION.md.

V2_DIR       = v2
BACKEND_DIR  = $(V2_DIR)/backend
FRONTEND_DIR = $(V2_DIR)/frontend
SCRIPTS_DIR  = $(V2_DIR)/deploy/scripts

.PHONY: help setup run-backend run-frontend build test lint deploy build-push deploy-app set-secrets download-db version

default: help

help:
	@echo "=========================================="
	@echo "QuickScribe (v2)"
	@echo "=========================================="
	@echo ""
	@echo "  help          - Show this help message (default)"
	@echo "  setup         - Install backend + frontend dependencies"
	@echo "  run-backend   - Run FastAPI with reload on :8000"
	@echo "  run-frontend  - Run Vite dev server on :5173"
	@echo "  build         - Build the frontend bundle"
	@echo "  test          - Run backend tests"
	@echo "  lint          - Lint backend (ruff) and frontend (eslint)"
	@echo ""
	@echo "  version       - Show the version that will be deployed"
	@echo "  build-push    - Build image and push to ACR (reads VERSION)"
	@echo "  deploy-app    - Point the web app at the new image and verify"
	@echo "  deploy        - build-push then deploy-app"
	@echo "  set-secrets   - Push env vars from .env to the web app"
	@echo "  download-db   - Download the live SQLite DB for inspection"
	@echo ""
	@echo "Deploy workflow:"
	@echo "  echo 2.8.9 > $(BACKEND_DIR)/VERSION && make deploy"
	@echo ""

setup:
	cd $(BACKEND_DIR) && uv sync
	cd $(FRONTEND_DIR) && npm install

run-backend:
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --port 8000

run-frontend:
	cd $(FRONTEND_DIR) && npm run dev

build:
	cd $(FRONTEND_DIR) && npm run build

test:
	cd $(BACKEND_DIR) && PYTHONPATH=src uv run pytest tests/

lint:
	cd $(BACKEND_DIR) && uv run ruff check .
	cd $(FRONTEND_DIR) && npm run lint

version:
	@cat $(BACKEND_DIR)/VERSION

build-push:
	cd $(SCRIPTS_DIR) && ./02-build-push.sh

deploy-app:
	cd $(SCRIPTS_DIR) && ./03-deploy-app.sh

deploy: build-push deploy-app
	@echo ""
	@echo "✓ Deployed $$(cat $(BACKEND_DIR)/VERSION)"

set-secrets:
	cd $(SCRIPTS_DIR) && ./set-secrets.sh

download-db:
	cd $(SCRIPTS_DIR) && ./download-db.sh
