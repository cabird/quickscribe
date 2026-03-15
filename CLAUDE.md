# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

| Resource | Location | Description |
|----------|----------|-------------|
| **Backend Docs** | [`backend/SYSTEM_DESCRIPTION.md`](./backend/SYSTEM_DESCRIPTION.md) | Flask API architecture, routes, database handlers |
| **Frontend Docs** | [`v3_frontend/SYSTEM_DESCRIPTION.md`](./v3_frontend/SYSTEM_DESCRIPTION.md) | React/TypeScript architecture, components, services |
| **Plaud Sync Docs** | [`plaud_sync_service/SYSTEM_DESCRIPTION.md`](./plaud_sync_service/SYSTEM_DESCRIPTION.md) | Container Apps Job, transcription polling, sync workflow |
| **Shared Library Docs** | [`shared_quickscribe_py/SYSTEM_DESCRIPTION.md`](./shared_quickscribe_py/SYSTEM_DESCRIPTION.md) | Shared models, handlers, Azure services |
| **Development TODOs** | [`TODOs`](./TODOs) | Current development priorities |

## General Instructions

**Planning Before Implementation**: Always present a detailed implementation plan before writing any code. The plan should include:
- Clear understanding of the requirements
- Proposed approach and architecture
- Potential alternatives or trade-offs
- Questions for clarification

**Confirmation Process**: After presenting the plan and resolving any questions, explicitly ask for confirmation before proceeding with implementation.

---

## Project Overview

QuickScribe is a full-stack audio transcription application with the following components:

| Component | Directory | Technology | Purpose |
|-----------|-----------|------------|---------|
| **Backend** | `backend/` | Flask 3.0 / Python 3.11 | REST API, authentication, AI features |
| **Frontend** | `v3_frontend/` | React 18 / TypeScript / Vite | Web application UI |
| **Plaud Sync** | `plaud_sync_service/` | Python / Container Apps Job | Scheduled Plaud device sync & transcription |
| **Shared Library** | `shared_quickscribe_py/` | Python package | Shared models, handlers, Azure clients |
| **Shared Models** | `shared/Models.ts` | TypeScript | Source of truth for data models |

### Architecture Overview

```
┌─────────────────┐     ┌─────────────────────┐     ┌────────────────────┐
│   v3_frontend   │────▶│      backend        │◀────│  plaud_sync_service│
│   (React SPA)   │     │   (Flask API)       │     │  (Container Job)   │
└─────────────────┘     └─────────┬───────────┘     └─────────┬──────────┘
                                  │                           │
                    ┌─────────────▼───────────────────────────▼──────────┐
                    │              shared_quickscribe_py                  │
                    │  (CosmosDB handlers, Azure services, Plaud client) │
                    └─────────────────────────────────────────────────────┘
                                           │
               ┌───────────────────────────┼───────────────────────────┐
               ▼                           ▼                           ▼
        ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
        │ Azure CosmosDB│          │ Azure Blob   │          │ Azure Speech │
        │ (Data store)  │          │ Storage      │          │ Services     │
        └──────────────┘          └──────────────┘          └──────────────┘
```

---

## Key Commands

### Root Makefile Commands (Recommended)

```bash
# Show all available commands
make help

# Build all components (models + frontend)
make build

# Run full dev environment (frontend dev server + backend)
make run-dev

# Run backend locally (serves built frontend)
make run-local

# Build all Docker containers
make build-containers

# Deploy to Azure
make deploy-azure        # Both backend and plaud service
make deploy-backend      # Backend only
make deploy-plaud        # Plaud sync service only

# Version management
make bump-version        # Bump all versions
make bump-version-backend
make bump-version-plaud
```

### Backend Development

```bash
cd backend
source venv/bin/activate  # IMPORTANT: Always activate venv

# Run development server
make local_run
# OR: cd src && python app.py

# Build Python models from TypeScript
make build

# Run tests
python run_tests.py unit
python run_tests.py integration
python run_tests.py fast    # Quick tests (excludes slow)
python run_tests.py all     # Full suite with coverage

# Docker operations
make build_container
make deploy_local
make compose_up
```

### Frontend Development

```bash
cd v3_frontend

npm install              # Install dependencies
npm run dev              # Start dev server (port 3000)
npm run build            # Production build
npm run sync-models      # Sync from /shared/Models.ts
npm run lint             # ESLint
npm run format           # Prettier
npm run deploy:build-and-copy  # Build and deploy to backend
```

### Plaud Sync Service

```bash
cd plaud_sync_service

# Build and deploy
make build               # Build Docker image
make azure-deploy        # Deploy to Azure Container Apps

# Test scripts
python scripts/test_plaud_sync.py --max-recordings 5
python scripts/cleanup_test_run.py --latest
python scripts/view_jobs.py
python scripts/clear_locks.py
```

---

## Shared Models Workflow

Models are defined in TypeScript and generated for Python/Frontend:

```
shared/Models.ts (Source of Truth)
        │
        ├──▶ make build (in backend/)
        │    └──▶ shared_quickscribe_py/cosmos/models.py (Python)
        │
        └──▶ npm run sync-models (in v3_frontend/)
             └──▶ v3_frontend/src/types/models.ts (TypeScript copy)
```

**Workflow when changing models:**
1. Edit `shared/Models.ts`
2. Run `make build` in `backend/` directory
3. Run `npm run dev` or `npm run sync-models` in `v3_frontend/`
4. Update handlers if new fields need special processing

---

## Database (CosmosDB)

### Containers

| Container | Partition Key | Purpose |
|-----------|---------------|---------|
| `recordings` | `userId` | Audio recording metadata |
| `users` | `id` | User profiles, Plaud settings |
| `transcriptions` | `userId` | Transcript text, speaker diarization |
| `job_executions` | `partitionKey` | Plaud sync job logs |
| `deleted_items` | `userId` | Soft-delete tracking |

### Handler Pattern

Handlers are in `shared_quickscribe_py/cosmos/`:

```python
from shared_quickscribe_py.cosmos import get_recording_handler, Recording

handler = get_recording_handler()  # Flask request-scoped
recording = handler.get_recording(recording_id, user_id)
handler.save_recording(recording)
```

---

## API Routes (Backend)

| Blueprint | Prefix | File | Purpose |
|-----------|--------|------|---------|
| `api_bp` | `/api` | `routes/api.py` | Core CRUD, uploads, tags |
| `ai_bp` | `/api/ai` | `routes/ai_routes.py` | AI analysis, chat, speaker inference |
| `local_bp` | `/api/local` | `routes/local_routes.py` | Local dev utilities |
| `admin_bp` | `/api/admin` | `routes/admin.py` | Admin operations |
| `participant_bp` | `/api/participants` | `routes/participant_routes.py` | Participant management |

### Key Endpoints

**Recordings**
- `GET /api/recordings` - List user's recordings
- `GET /api/recording/<id>` - Get recording details
- `POST /api/upload` - Upload audio file
- `PUT /api/recording/<id>` - Update recording
- `GET /api/recording/<id>/audio-url` - Get streaming URL

**AI Features**
- `POST /api/ai/chat` - Chat with transcript context
- `GET /api/ai/infer_speaker_names/<id>` - AI speaker inference
- `POST /api/recording/<id>/postprocess` - Trigger AI post-processing

---

## Authentication

- **Azure AD** authentication via MSAL
- Frontend acquires token → Backend validates JWT
- Token validation in `backend/src/auth.py`
- JWKS caching with 24-hour TTL

**Frontend auth toggle:**
- `VITE_AUTH_ENABLED=true` for production
- `VITE_AUTH_ENABLED=false` for local development without auth

---

## Plaud Sync Service Architecture

Runs as **Azure Container Apps Job** (not HTTP server):

```
Cron Schedule → Container Start → JobExecutor → Exit
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
           TranscriptionPoller   PlaudProcessor    LoggingHandler
           (poll Azure Speech)   (download/upload)  (CosmosDB logs)
```

**Key Features:**
- Concurrent job prevention via CosmosDB locks
- Automatic chunking for large files (>300MB or >2 hours)
- Deleted items blocking (prevents re-syncing deleted recordings)
- AI post-processing (title, description generation)

---

## Configuration

### Feature Flags (shared_quickscribe_py/config/settings.py)

```python
from shared_quickscribe_py.config import get_settings

settings = get_settings()
if settings.ai_enabled:
    # Azure OpenAI available
if settings.plaud_enabled:
    # Plaud integration available
```

Available flags: `ai_enabled`, `cosmos_enabled`, `blob_storage_enabled`, `speech_services_enabled`, `plaud_enabled`, `azure_ad_auth_enabled`, `assemblyai_enabled`

### Environment Variables

**Backend (.env)**
```bash
AZURE_COSMOS_ENDPOINT=...
AZURE_COSMOS_KEY=...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_OPENAI_API_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_CLIENT_ID=...  # Azure AD
```

**Frontend (.env)**
```bash
VITE_API_URL=                     # Empty for production
VITE_AUTH_ENABLED=true
VITE_AZURE_CLIENT_ID=...
VITE_AZURE_TENANT_ID=...
```

---

## Common Patterns

### Pydantic Model Usage

```python
# Good: Use model attributes directly
user.plaudSettings.enableSync = True
handler.save_user(user)

# Bad: Don't treat models as dicts
user.plaudSettings['enableSync'] = True  # ❌
```

### Frontend Styling (Fluent UI)

```typescript
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  container: { padding: tokens.spacingHorizontalM },
});

// Good: Use mergeClasses
className={mergeClasses(styles.container, isActive && styles.active)}

// Bad: Don't use template literals
className={`${styles.container} ${styles.active}`}  // ❌
```

### Safe Field Access

```typescript
// Always provide fallbacks for optional fields
{recording.title || recording.original_filename}
{field && <Component />}
recording?.description
```

---

## Development Workflows

### Local Development

```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate && make local_run

# Terminal 2: Frontend
cd v3_frontend && npm run dev

# Frontend at http://localhost:3000 (proxies to backend at 5050)
```

### Full Stack with Docker

```bash
make build              # Build all components
make build-containers   # Build Docker images
make run-local-container  # Run in Docker
```

### Testing

```bash
# Backend tests
cd backend && source venv/bin/activate
python run_tests.py fast

# Plaud sync test with cleanup
cd plaud_sync_service
python scripts/test_plaud_sync.py --max-recordings 3
python scripts/cleanup_test_run.py --latest
```

---

## Known Quirks

1. **Plaud `.opus` files**: Actually MP3 format - handled automatically
2. **Frontend port**: Dev server on 3000, proxies `/api` and `/plaud` to backend on 5050
3. **Virtual environment**: Backend and scripts require `source venv/bin/activate`
4. **Model sync**: Frontend models auto-sync on `npm run dev` / `npm run build`
5. **Azure Speech API**: Uses v3.2 endpoint with custom client in `plaud_sync_service/azure_speech/`

---

## File Locations Reference

| What | Where |
|------|-------|
| TypeScript models (source) | `shared/Models.ts` |
| Python models (generated) | `shared_quickscribe_py/cosmos/models.py` |
| Frontend models (synced) | `v3_frontend/src/types/models.ts` |
| Database handlers | `shared_quickscribe_py/cosmos/*_handler.py` |
| Backend routes | `backend/src/routes/*.py` |
| LLM prompts | `backend/prompts.yaml`, `plaud_sync_service/src/prompts.yaml` |
| API version | `backend/src/api_version.py` |
| Frontend components | `v3_frontend/src/components/` |
| Frontend services | `v3_frontend/src/services/` |
