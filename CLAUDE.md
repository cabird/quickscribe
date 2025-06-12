# CLAUDE.md

<!-- Last updated for commit: 0b5c14dba1691c16fd9cfef10ae6bccfd3490170 -->

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

📋 For a comprehensive understanding of the codebase structure, see [`DIRECTORY_MAPPING.md`](./DIRECTORY_MAPPING.md). This document provides detailed summaries of every major file and directory, making it easy to understand the project architecture and locate specific functionality.

📝 For current development priorities and implementation plans, see [`TODOs`](./TODOs). This file contains prioritized tasks with detailed implementation steps for ongoing development work.

🎨 For the new frontend architecture and implementation details, see [`frontend_new/ARCHITECTURE.md`](./frontend_new/ARCHITECTURE.md). This document provides comprehensive technical details about the modern React frontend, including component architecture, state management, and integration patterns.

🚀 For new frontend setup and usage instructions, see [`frontend_new/README.md`](./frontend_new/README.md). This covers installation, development workflow, and deployment procedures for the new frontend.

⚙️ For backend architecture and implementation details, see [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md). This document provides comprehensive technical details about the Flask API server, database handlers, Azure services integration, and microservices communication patterns.

🔧 For backend setup and usage instructions, see [`backend/README.md`](./backend/README.md). This covers installation, configuration, testing, and deployment procedures for the backend API server.

🐳 For transcoder container architecture and implementation details, see [`transcoder_container/ARCHITECTURE.md`](./transcoder_container/ARCHITECTURE.md). This document provides comprehensive technical details about the containerized audio processing service, queue-based processing, and Azure Container Apps deployment.

📦 For transcoder container setup and usage instructions, see [`transcoder_container/README.md`](./transcoder_container/README.md). This covers building, configuration, testing, and deployment procedures for the audio processing microservice.

## General Instructions

**Planning Before Implementation**: Always present a detailed implementation plan before writing any code. The plan should include:
- Clear understanding of the requirements
- Proposed approach and architecture
- Potential alternatives or trade-offs
- Questions for clarification

**Confirmation Process**: After presenting the plan and resolving any questions, explicitly ask for confirmation before proceeding with implementation. This ensures alignment and prevents unnecessary rework.


## Overview

QuickScribe is a full-stack audio transcription application with three main components:
- **Backend**: Flask API server with Azure integrations (`/backend/`)
- **Frontend**: Modern React/TypeScript web app (`/frontend_new/`)
- **Transcoder**: Containerized audio processing service (`/transcoder_container/`)

## Key Commands

#### AI Post-Processing
```bash
# Test AI post-processing on completed recordings
curl -X POST http://localhost:5000/api/recording/<recording_id>/postprocess

# Check llms.py async infrastructure
python -c "import backend.llms; print('Async LLM infrastructure ready')"
```

### Backend Development
```bash
# IMPORTANT: Always use the virtual environment for backend operations
cd backend && source venv/bin/activate

# Build shared models from TypeScript definitions
make build

# Run Flask development server
python app.py

# Run tests (requires virtual environment)
python run_tests.py unit
python run_tests.py fast

# Deploy to Azure production
make deploy_azure

# Deploy to test slot
make deploy_to_test

# Bump version
make bump_version
```

### Frontend Development
```bash
cd frontend_new

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Type checking
npm run typecheck

# Linting
npm run lint
```

### Transcoder Container
```bash
cd transcoder_container

# Build Docker image
make build

# Run locally
make run

# Deploy to Azure Container Apps
make azure-deploy

# Bump version and deploy
make bump-deploy

# View logs
make logs
```

## Architecture

### Microservices Communication
1. **Web API** → **Azure Storage Queue** → **Transcoder Service**
2. **Transcoder** processes audio files from blob storage
3. **Transcoder** → **Callback API** → **CosmosDB** update

### Shared Models
- Models shared amongst the backend, transcoding container, and frontend are stored in <repo>/shared/Models.ts
- Generated Python models in `backend/db_handlers/models.py` (includes new `description` field for recordings)
- Build with `make build` in backend directory (requires virtual environment: `source venv/bin/activate`)
- TypeScript models in `frontend_new/src/types/index.ts`

#### Model Synchronization Workflow
1. Edit `shared/Models.ts` 
2. Run `make build` in backend directory
3. Frontend models are automatically synchronized via `npm run sync-models` (runs before dev/build)
4. Update frontend components to handle optional fields safely

### Database Structure
- **CosmosDB** containers: `recordings`, `users`, `transcripts`
- Partition keys: `userId` for recordings/transcripts, `id` for users
- Handlers in `backend/src/db_handlers/`

### Authentication Flow
- Azure AD authentication via MSAL
- Frontend acquires token → Backend validates with Azure
- User info stored in CosmosDB on first login

### Queue Processing
- Audio files uploaded to Azure Blob Storage
- Message sent to `audio-processing-queue`
- Transcoder picks up message, processes file
- Status updates via callback to `/api/transcoder/callback`
- Automatic AI post-processing triggered on completion (title, description, speakers)

## Environment Configuration

### Backend (.env)
Critical variables:
- `AZURE_COSMOS_ENDPOINT`, `AZURE_COSMOS_KEY`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
- `ASSEMBLYAI_API_KEY`, `OPENAI_API_KEY`
- `CALLBACK_URL` (for transcoder callbacks)

### Frontend (.env)
- `VITE_API_URL` (backend URL)
- `VITE_AZURE_CLIENT_ID` (for MSAL)

### Transcoder (.env)
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_QUEUE_NAME`
- `CALLBACK_URL`, `CALLBACK_API_KEY`

## Testing Strategy

### Frontend Testing
- Unit tests with Vitest: `npm test`
- Component testing with React Testing Library
- Run specific test: `npm test <filename>`

### Backend Testing
- **Pytest Framework**: Comprehensive test suite with unit, integration, and E2E tests
- **Test Categories**:
  - `python run_tests.py unit` - Unit tests for individual components
  - `python run_tests.py integration` - API endpoint and service integration tests  
  - `python run_tests.py e2e` - Complete workflow tests
  - `python run_tests.py fast` - Quick tests (excludes slow tests)
  - `python run_tests.py all` - Full test suite with coverage
- **Test Structure**: `tests/{unit,integration,e2e}/` with shared fixtures in `conftest.py`
- **Coverage**: Current coverage at 41%, target goal of 70%
- **Mock Strategy**: Tests use proper mock patching at route import level to prevent database hits
- **Requirements**: Tests require virtual environment activation (`source venv/bin/activate`)
- **Legacy Scripts**: Standalone test scripts in `/scripts/` directory (being migrated)

## Deployment Process

### Production Deployment
1. Frontend: `npm run build` → assets served by backend static file handler
2. Backend: `make deploy_azure` → deploys to App Service
3. Transcoder: `make azure-deploy` → deploys to Container Apps

### Version Management
- API version in `backend/src/api_version.py`
- Transcoder version in `transcoder_container/app_version.py`
- Bump with respective `make bump_version` commands

## Key Implementation Details

### Audio Processing Flow
1. User uploads/records audio → stored in blob container
2. Queue message created with blob reference
3. Transcoder downloads, converts to MP3, uploads result
4. Callback updates recording status in CosmosDB
5. Frontend polls for status updates

### Transcription Services
- **Azure Speech Services**: Default transcription provider
- **AssemblyAI**: Alternative provider with speaker diarization
- Service selection in `backend/src/services/transcription_service.py`

### Plaud Device Integration
- Sync endpoint: `/plaud/sync/start`
- Downloads recordings from Plaud API
- Creates recording entries in CosmosDB
- Queues for transcription processing

## Pydantic Model Architecture

### Extended Models with Serialization
The codebase uses extended Pydantic models in `backend/db_handlers/user_handler.py` that override base models from `backend/db_handlers/models.py` to add proper datetime handling:

```python
class PlaudSettings(models.PlaudSettings):
    # Override datetime fields to use actual datetime objects
    activeSyncStarted: Optional[datetime] = None
    lastSyncTimestamp: Optional[datetime] = None
    
    @field_validator('activeSyncStarted', 'lastSyncTimestamp', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        # Handles ISO strings from CosmosDB → datetime objects
    
    @field_serializer('activeSyncStarted', 'lastSyncTimestamp')
    def serialize_datetime(self, value) -> Optional[str]:
        # Handles datetime objects → ISO strings for storage
```

**Best Practice**: Use `user_handler.save_user(user)` instead of manual dictionary conversion. Routes should work with model objects directly:
```python
# Good:
user.plaudSettings.activeSyncToken = sync_token
user.plaudSettings.activeSyncStarted = datetime.now(UTC)
user_handler.save_user(user)

# Avoid:
plaud_dict = user.plaudSettings.model_dump()
plaud_dict['activeSyncToken'] = sync_token
user_handler.update_user(user_id, plaudSettingsDict=plaud_dict)
```

## Testing Strategy

### CosmosDB Serialization Testing
Use `scripts/test_cosmosdb_serialization.py` to validate complete database round-trips:
- Tests all datetime field serialization/deserialization
- Validates field modifications persist through save/retrieve cycles
- Ensures None values handled correctly
- Verifies legacy method compatibility

Run with: `scripts/.venv/bin/python scripts/test_cosmosdb_serialization.py`

### Model-Only Testing  
Use `scripts/test_user_models.py` for faster Pydantic validation without database:
- Field validator testing
- Serialization format verification
- Edge case handling

### Testing the backend

Look in <repo>/docker-compose.yml to see how the local setup runs.  Write tests against the 
backend assuming it's running locally.  Look in backend/routes/api.py for a set of
local endpoints to handle things like loggin in locally, managing test users, etc.
The routes have "local" in their names.

## Local Development Patterns

### Hot Reloading
Backend configured for hot reloading in `startup.sh`:
```bash
export FLASK_APP=app.py
export FLASK_DEBUG=1
export FLASK_ENV=development
python -m flask run --host=0.0.0.0 --port=$PORT --debug --reload
```

### Virtual Environment Usage
Scripts require the virtual environment: `scripts/.venv/bin/python script_name.py`

### Route Structure
- Main API routes: `/api/*` 
- Plaud-specific routes: `/plaud/*` (not under `/api/plaud`)
- AI routes: `/api/ai/*` (in `backend/routes/ai_routes.py`)
- Static file exclusions in `app.py` catch-all route include `"plaud/"`

#### AI Route Architecture
- All AI operations go under `/api/ai/` prefix
- File: `backend/routes/ai_routes.py` with `ai_bp` blueprint
- Register in `app.py`: `app.register_blueprint(ai_bp, url_prefix='/api/ai')`
- Speaker inference uses `transcription_id` not `recording_id`

## Common Issues & Solutions

### Pydantic Dictionary Access
❌ **Don't**: `user.plaudSettings['field'] = value` (treats model as dict)
✅ **Do**: `user.plaudSettings.field = value` (uses model fields)

### DateTime Serialization
❌ **Don't**: Manual `.isoformat()` conversion in routes
✅ **Do**: Let Pydantic field serializers handle it automatically

### User Updates
❌ **Don't**: `update_user(user_id, plaudSettingsDict=dict)` 
✅ **Do**: `save_user(user)` for clean model-based API

### Plaud File Extensions
Plaud devices create `.opus` files that are actually MP3 format. Handle in transcoder:
```python
if extension == 'opus':
    extension = 'mp3'
```

### Database Migration & Backward Compatibility
When adding required fields to models, use the extended Recording class in `recording_handler.py` to provide defaults in `__init__()` for missing fields:
```python
def __init__(self, **data):
    # Handle migration: provide defaults for missing required fields
    if 'title' not in data or data['title'] is None:
        data['title'] = data.get('original_filename', 'Unknown')
    if 'recorded_timestamp' not in data or data['recorded_timestamp'] is None:
        data['recorded_timestamp'] = data.get('upload_timestamp', datetime.now(UTC).isoformat())
    super().__init__(**data)
```
- Make new fields optional in `Models.ts` initially, then migrate existing data
- Pattern: `data['new_field'] = data.get('fallback_field', default_value)`

### Frontend Component State Management

#### Recording Card Update Mechanism
- RecordingCard components dispatch `'recordingUpdated'` CustomEvents
- RecordingCardsPage listens for these events to update state in-place:
```javascript
window.dispatchEvent(new CustomEvent('recordingUpdated', { 
    detail: { recording: updatedRecording } 
}));
```
- Prevents need for full page reloads after transcription actions

#### Safe Field Access Patterns
- Always provide fallbacks: `{recording.title || recording.original_filename}`
- Conditional rendering for optional fields: `{field && <Component />}`
- Use TypeScript optional fields (`field?: type`) during migrations
- Handle both prop updates and internal state changes in components