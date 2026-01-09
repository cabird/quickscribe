# System Description

**Git commit:** e703cbb3bd2589cde1d761b37329472fabda3df4

This document provides a comprehensive description of the QuickScribe Backend system. It is automatically maintained and updated based on code changes.

---

## 1. Repository Structure

```
backend/
├── src/                          # Main application source code
│   ├── app.py                    # Flask application factory and entry point
│   ├── config.py                 # Configuration wrapper (shared_quickscribe_py)
│   ├── auth.py                   # Azure AD JWT token validation
│   ├── llms.py                   # LLM integration (Azure OpenAI)
│   ├── ai_postprocessing.py      # AI post-processing for recordings
│   ├── blob_util.py              # Azure Blob Storage utilities
│   ├── user_util.py              # User authentication utilities
│   ├── util.py                   # General utilities
│   ├── logging_config.py         # Centralized logging with App Insights
│   ├── api_version.py            # API version constant
│   ├── plaud_sync_trigger.py     # Plaud device sync functionality
│   ├── routes/                   # Flask blueprints
│   │   ├── api.py                # Main API routes (/api/*)
│   │   ├── ai_routes.py          # AI-specific routes (/api/ai/*)
│   │   ├── local_routes.py       # Local development routes (/api/local/*)
│   │   ├── admin.py              # Admin routes (/api/admin/*)
│   │   └── participant_routes.py # Participant management (/api/participants/*)
│   ├── frontend-dist/            # Built frontend assets (served statically)
│   ├── static/                   # Static assets
│   └── templates/                # Jinja2 templates
├── tests/                        # Test suite
│   ├── conftest.py               # Shared pytest fixtures
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   ├── e2e/                      # End-to-end tests
│   └── fixtures/                 # Test utilities and fixtures
├── migrations/                   # Database migrations
│   ├── migration_runner.py       # Migration base class and utilities
│   ├── 001_normalize_diarized_transcripts.py
│   ├── 002_create_participant_profiles.py
│   └── 003_backfill_token_counts.py
├── Makefile                      # Build and deployment automation
├── Dockerfile                    # Container image definition
├── startup.sh                    # Container startup script
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Pytest configuration
├── prompts.yaml                  # LLM prompt templates
├── .bumpversion.cfg              # Version management configuration
├── .env.local                    # Local development environment
├── .env.azure                    # Azure production environment
└── .coveragerc                   # Code coverage configuration
```

---

## 2. Languages, Size & Composition

| Category | Details |
|----------|---------|
| **Primary Language** | Python 3.11 |
| **Framework** | Flask 3.0.3 |
| **Source Files** | ~25 Python modules |
| **Test Files** | ~10 test modules |
| **Lines of Code** | ~5,000+ (excluding dependencies) |
| **Configuration Files** | YAML, JSON, Makefile, Dockerfile |

### Key Language Features Used
- **Pydantic** for data validation and serialization
- **Async/await** for concurrent LLM operations
- **Type hints** throughout the codebase
- **Flask Blueprints** for modular route organization

---

## 3. Key Components and Modules

### Core Application (`src/app.py`)
- **Application Factory Pattern**: `create_app()` function creates Flask application
- **Blueprint Registration**: Modular routes organized by feature
- **Azure Service Initialization**: CosmosDB, Blob Storage clients
- **CORS Configuration**: Development (localhost:3000) vs production
- **Static File Serving**: Built frontend assets served from `frontend-dist/`

### Configuration (`src/config.py`)
- Wraps `shared_quickscribe_py.config` for backward compatibility
- Provides legacy `config.X` interface
- Environment detection (Azure vs local development)
- Supports: CosmosDB, Blob Storage, Azure OpenAI, Speech Services, Azure AD Auth

### Authentication (`src/auth.py`)
- **Azure AD JWT Token Validation**
- JWKS (JSON Web Key Set) caching with 24-hour TTL
- Token claims validation: issuer, audience, expiration
- Thread-safe key refresh with double-check locking

### LLM Integration (`src/llms.py`)
- **Azure OpenAI Integration** for AI features
- Synchronous and async API calls
- Concurrent prompt execution (`send_multiple_prompts_concurrent`)
- Timing and token usage metrics
- Prompt templates loaded from `prompts.yaml`

### AI Post-Processing (`src/ai_postprocessing.py`)
- **Title Generation**: Concise titles from transcripts
- **Description Generation**: 1-2 sentence summaries
- **Speaker Inference**: LLM-based speaker name detection
- **Participant Management**: Auto-create/match participant profiles
- Single LLM call optimization for title+description

### Blob Storage (`src/blob_util.py`)
- Wrapper around `shared_quickscribe_py.azure_services`
- File upload/download operations
- SAS URL generation for secure access
- Transcoding job queue management

### Routes Overview

| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `api_bp` | `/api` | Core CRUD operations, uploads, tags |
| `ai_bp` | `/api/ai` | AI analysis, speaker inference, chat |
| `local_bp` | `/api/local` | Local development utilities |
| `admin_bp` | `/api/admin` | Admin operations |
| `participant_bp` | `/api/participants` | Participant profile management |

### Key API Endpoints

**Recording Management**
- `GET /api/recording/<id>` - Get recording details
- `GET /api/recordings` - List user's recordings
- `POST /api/upload` - Upload audio file
- `PUT /api/recording/<id>` - Update recording
- `GET /api/delete_recording/<id>` - Delete recording
- `GET /api/recording/<id>/audio-url` - Get streaming URL

**Transcription Operations**
- `GET /api/transcription/<id>` - Get transcription
- `POST /api/recording/<id>/postprocess` - Trigger AI post-processing
- `POST /api/recording/<id>/update_speakers` - Update speaker names

**AI Features**
- `GET /api/ai/get_speaker_summaries/<id>` - Generate speaker summaries
- `GET /api/ai/infer_speaker_names/<id>` - AI speaker inference
- `GET /api/ai/analysis-types` - List analysis types
- `POST /api/ai/execute-analysis` - Run custom analysis
- `POST /api/ai/chat` - AI chat with transcript context

**Tags**
- `GET /api/tags/get` - Get user's tags
- `POST /api/tags/create` - Create tag
- `POST /api/tags/update` - Update tag
- `GET /api/tags/delete/<id>` - Delete tag

---

## 4. Build, Tooling, and Dependencies

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.3 | Web framework |
| Pydantic | 2.9.2 | Data validation |
| azure-cosmos | 4.7.0 | CosmosDB client |
| azure-storage-blob | 12.23.1 | Blob storage |
| azure-storage-queue | 12.12.0 | Queue storage |
| azure-identity | 1.19.0 | Azure authentication |
| openai | 1.51.2 | OpenAI API client |
| assemblyai | 0.34.0 | AssemblyAI transcription |
| PyJWT | 2.9.0 | JWT token handling |
| msal | 1.31.0 | Microsoft authentication |
| gunicorn | 22.0.0 | Production WSGI server |
| aiohttp | 3.10.11 | Async HTTP client |

### Testing Dependencies
- pytest 8.3.3
- pytest-asyncio 0.25.0
- pytest-cov 5.0.0
- pytest-flask 1.3.0
- pytest-mock 3.14.0

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Install shared_quickscribe_py in editable mode |
| `make local_run` | Start local development server |
| `make build_container` | Build Docker image |
| `make deploy_local` | Deploy locally with Docker |
| `make deploy_azure` | Deploy to Azure App Service |
| `make bump_version` | Increment patch version |
| `make compose_up` | Start full stack with docker-compose |
| `make clean` | Clean build artifacts |

### Docker Configuration
- **Base Image**: Python 3.11
- **Port**: 8000 (WEBSITES_PORT for Azure)
- **Startup**: `startup.sh` handles environment setup
- **Environment Files**: `.env.local` or `.env.azure` copied to `.env`

---

## 5. Runtime Architecture

### Request Flow

```
Client Request
     │
     ▼
┌──────────────┐
│   Flask App   │◄── CORS middleware
│   (app.py)    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Auth Check   │◄── JWT validation (auth.py)
│  @require_auth│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Blueprint   │◄── api_bp, ai_bp, etc.
│    Routes     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Handlers   │◄── shared_quickscribe_py.cosmos
│  (CosmosDB)  │
└──────────────┘
```

### Audio Processing Pipeline

```
1. Upload Audio
      │
      ▼
┌──────────────────┐
│  Blob Storage    │◄── store_recording_as_blob()
│  (Original File) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Azure Queue     │◄── send_to_transcoding_queue()
│ (Processing Job) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Transcoder       │  (Separate container)
│ Container        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Callback API     │◄── /api/transcoding_callback
│ (Status Update)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ AI Post-Process  │◄── postprocess_recording_full()
│ (Title/Desc/...)│
└──────────────────┘
```

### Logging Architecture
- **Console Output**: JSON-formatted logs
- **Azure App Insights**: Optional integration via OpenCensus
- **Custom Dimensions**: service, namespace, version, request context
- **Logger Namespace**: `quickscribe.backend.<module>`

### External Service Integrations

| Service | Purpose | Module |
|---------|---------|--------|
| Azure CosmosDB | Data persistence | shared_quickscribe_py.cosmos |
| Azure Blob Storage | Audio file storage | blob_util.py |
| Azure Queue Storage | Transcoding jobs | blob_util.py |
| Azure OpenAI | LLM operations | llms.py |
| Azure Speech Services | Transcription | transcription_service.py |
| AssemblyAI | Alternative transcription | assemblyai |
| Azure AD | Authentication | auth.py |
| Azure App Insights | Monitoring | logging_config.py |

---

## 6. Development Workflows

### Local Development Setup

```bash
# 1. Activate virtual environment
cd /home/cbird/repos/quickscribe/backend
source venv/bin/activate

# 2. Install shared library
make setup

# 3. Start development server
make local_run
# OR
cd src && python app.py
```

### Running Tests

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all tests with coverage
python run_tests.py all

# Run specific test categories
python run_tests.py unit
python run_tests.py integration
python run_tests.py e2e
python run_tests.py fast  # Excludes slow tests

# Options
python run_tests.py all --verbose
python run_tests.py all --html  # HTML coverage report
```

### Docker Development

```bash
# Build and run locally
make build_container
make deploy_local

# Full stack with docker-compose
make compose_up
make compose_logs
make compose_down
```

### Deployment

```bash
# Deploy to Azure
make bump_version
make deploy_azure

# Deploy to test slot
make deploy_to_test
```

### Database Migrations

```bash
cd migrations
python 001_normalize_diarized_transcripts.py --dry-run
python 001_normalize_diarized_transcripts.py --execute
```

---

## 7. Known Limitations / TODOs

### Code TODOs

1. **`src/routes/participant_routes.py`**
   - TODO: Add logic to clean up participant references in recordings/transcriptions
   - TODO: Update all recordings and transcriptions to point to primary participant

2. **`src/routes/ai_routes.py`**
   - TODO: Uncomment speaker inference guard to prevent multiple inferences on the same transcription

### Technical Debt

- **Test Coverage**: Currently at ~41%, target is 70%
- **Speaker Inference**: Currently disabled in post-processing; users manually assign speakers
- **Legacy Routes**: Some DELETE operations use GET method (e.g., `/delete_recording/<id>`)
- **Plaud Integration**: File extension handling for `.opus` files that are actually MP3

### Known Issues

- Transcoding timeout is set to 30 days (TRANSCRIPTION_IN_PROGRESS_TIMEOUT_SECONDS)
- Some older recordings may lack `transcoding_status` field

---

## 8. Suggested Improvements or Considerations for AI Agents

### Code Navigation Tips

1. **Start with `src/app.py`** to understand application structure
2. **Route files** in `src/routes/` define all API endpoints
3. **Shared models** are in `shared_quickscribe_py` (external package)
4. **Database handlers** accessed via `get_*_handler()` factory functions

### Common Patterns

1. **Authentication**: Use `@require_auth` decorator on protected routes
2. **User Context**: Call `get_current_user()` to get authenticated user
3. **Database Operations**: Use handlers from `shared_quickscribe_py.cosmos`
4. **Logging**: Use `get_logger('module_name', API_VERSION)`

### Testing Considerations

- Tests require virtual environment activation
- Use mock patching at route import level for database isolation
- Integration tests may require running backend locally
- See `backend/tests/conftest.py` for shared fixtures

### Environment Variables

Key environment variables (see `.env.local` or `.env.azure`):
- `AZURE_COSMOS_ENDPOINT`, `AZURE_COSMOS_KEY`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
- `ASSEMBLYAI_API_KEY`, `OPENAI_API_KEY`
- `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `FLASK_ENV`, `FLASK_DEBUG`

### Safe Modifications

When modifying the backend:
1. Run `python run_tests.py fast` before committing
2. Update models in `shared/Models.ts` and run `make build`
3. Test locally with `make local_run` or `make compose_up`
4. Check for breaking changes in API responses

### API Response Format

Most endpoints return JSON with this structure:
```json
{
  "status": "success|error",
  "data": {...},
  "message": "Optional message",
  "error": "Error message if status is error"
}
```

Or Pydantic models directly: `model.model_dump()`
