# System Description
**Git commit:** 5b007ef08f5714d19faf318994f63082d90698fd

## 1. Repository Structure

```
shared_quickscribe_py/
├── Makefile                    # Build automation for model generation
├── README.md                   # Package documentation
├── setup.py                    # Python package configuration
└── shared_quickscribe_py/      # Main package source
    ├── __init__.py             # Package version (0.1.0)
    ├── azure_services/         # Azure service client modules
    │   ├── __init__.py         # Exports all Azure service clients
    │   ├── azure_openai.py     # Azure OpenAI LLM client (sync/async)
    │   ├── blob_storage.py     # Blob & Queue storage operations
    │   └── speech_service.py   # Azure Speech Services (placeholder)
    ├── config/                 # Configuration management
    │   ├── __init__.py
    │   ├── README.md           # Config documentation
    │   └── settings.py         # Pydantic settings with feature flags
    ├── cosmos/                 # CosmosDB data layer
    │   ├── __init__.py         # Exports all handlers and models
    │   ├── models.py           # Auto-generated Pydantic models
    │   ├── handler_factory.py  # Flask request-scoped handler factories
    │   ├── helpers.py          # Utility functions (slugify)
    │   ├── util.py             # Cosmos field filtering
    │   ├── recording_handler.py
    │   ├── transcription_handler.py
    │   ├── user_handler.py
    │   ├── participant_handler.py
    │   ├── analysis_type_handler.py
    │   ├── sync_progress_handler.py
    │   ├── job_execution_handler.py
    │   ├── locks_handler.py
    │   ├── manual_review_handler.py
    │   └── deleted_items_handler.py
    ├── logging/                # Logging configuration
    │   ├── __init__.py
    │   └── config.py           # Centralized logger factory
    └── plaud/                  # Plaud device integration
        ├── __init__.py
        └── client.py           # Plaud.AI API client
```

## 2. Languages, Size & Composition

| Metric | Value |
|--------|-------|
| Primary Language | Python 3.11+ |
| Total Lines of Code | ~5,040 lines |
| Number of Python Files | 26 (excluding build artifacts) |
| Package Version | 0.1.1 |

**File Distribution by Size:**
- `cosmos/models.py`: 563 lines (auto-generated Pydantic models)
- `azure_services/azure_openai.py`: 472 lines
- `config/settings.py`: 450 lines
- `cosmos/job_execution_handler.py`: 338 lines
- `cosmos/participant_handler.py`: 332 lines

## 3. Key Components and Modules

### CosmosDB Data Layer (`cosmos/`)

The data layer provides typed Pydantic models and handler classes for all domain entities:

| Handler | Entity | Purpose |
|---------|--------|---------|
| `RecordingHandler` | `Recording` | Audio recording metadata, status tracking |
| `TranscriptionHandler` | `Transcription` | Transcription text, speaker diarization |
| `UserHandler` | `User` | User profiles, Plaud settings |
| `ParticipantHandler` | `Participant` | Speaker/participant management |
| `AnalysisTypeHandler` | `AnalysisType` | Custom AI analysis prompts |
| `JobExecutionHandler` | `JobExecution` | Batch job execution logs |
| `SyncProgressHandler` | `SyncProgress` | Plaud sync progress tracking |
| `LocksHandler` | - | Distributed locking |
| `ManualReviewItemHandler` | `ManualReviewItem` | Failed items requiring review |
| `DeletedItemsHandler` | `DeletedItems` | Soft-delete tracking |

**Key Enums:**
- `TranscriptionStatus`: not_started, in_progress, completed, failed
- `TranscodingStatus`: not_started, queued, in_progress, completed, failed
- `Source`: upload, plaud, stream

**Model Generation:**
Models are auto-generated from TypeScript definitions in `../shared/Models.ts` using:
```bash
make build  # Runs typescript-json-schema → datamodel-codegen pipeline
```

### Azure Services (`azure_services/`)

**AzureOpenAIClient** - LLM integration with:
- Synchronous and async request methods
- Timing and token usage metrics
- Concurrent multi-prompt execution
- Factory function `get_openai_client(model_type)` for "normal" or "mini" models

**BlobStorageClient** - File storage operations:
- Upload/download with streaming
- SAS URL generation with configurable permissions
- Blob existence checks and deletion

**QueueStorageClient** - Message queue operations:
- JSON message serialization
- `send_transcoding_job()` helper for audio processing queue

**AzureSpeechClient** - Placeholder for batch transcription (not yet implemented)

### Configuration (`config/settings.py`)

Pydantic-based settings with conditional validation:

```python
settings = QuickScribeSettings()
if settings.ai_enabled:
    # Azure OpenAI config is validated and available
    client = AzureOpenAIClient(settings.azure_openai.api_endpoint, ...)
```

**Feature Flags:**
- `ai_enabled` - Azure OpenAI for AI post-processing
- `cosmos_enabled` - CosmosDB database
- `blob_storage_enabled` - Azure Blob Storage
- `speech_services_enabled` - Azure Speech Services
- `plaud_enabled` - Plaud device integration
- `azure_ad_auth_enabled` - Azure AD authentication
- `assemblyai_enabled` - Alternative transcription provider
- `plaud_sync_trigger_enabled` - Container Apps job triggering

### Plaud Integration (`plaud/client.py`)

**PlaudClient** - Plaud.AI device API integration:
- Fetch recordings list from Plaud cloud
- Download audio files via temporary S3 URLs
- Filter recordings by ID or timestamp
- Convert Plaud metadata to `PlaudMetadata` model format

**Key Classes:**
- `AudioFile` - Dataclass representing a Plaud recording
- `PlaudResponse` - API response wrapper

## 4. Build, Tooling, and Dependencies

### Dependencies (from setup.py)

```
# Azure services
azure-cosmos>=4.7.0
azure-storage-blob>=12.23.0
azure-storage-queue>=12.12.0
azure-identity>=1.19.0

# Data validation
pydantic>=2.9.0
pydantic-settings>=2.0.0

# HTTP clients
httpx>=0.27.0
requests>=2.32.0

# Utilities
python-dotenv>=1.0.0
mutagen>=1.47.0          # Audio metadata
tiktoken>=0.5.0          # Token counting for LLMs
```

### Build Commands

```bash
# Generate Pydantic models from TypeScript
make build

# Clean generated schema files
make clean

# Install in development mode
pip install -e .
```

### Model Generation Pipeline

1. `typescript-json-schema` converts `../shared/Models.ts` to JSON Schema
2. `datamodel-codegen` generates `cosmos/models.py` with Pydantic v2 models
3. Handler classes extend base models with additional serialization logic

## 5. Runtime Architecture

### Service Integration Pattern

This library is designed to be installed as a dependency in multiple services:

```
┌─────────────────┐     ┌─────────────────────┐     ┌────────────────────┐
│   Backend API   │     │ Transcoder Container│     │ Plaud Sync Service │
│   (/backend/)   │     │(/transcoder_container)│   │ (/plaud_sync_service)│
└────────┬────────┘     └──────────┬──────────┘     └─────────┬──────────┘
         │                         │                          │
         └─────────────────────────┼──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   shared_quickscribe_py     │
                    │  (installed via pip -e)     │
                    └─────────────────────────────┘
```

### Handler Factory Pattern

For Flask applications, handlers use request-scoped caching via `flask.g`:

```python
from shared_quickscribe_py.cosmos import get_recording_handler

@app.route('/api/recording/<id>')
def get_recording(id):
    handler = get_recording_handler()  # Cached for request lifetime
    return handler.get_recording(id)
```

### Database Access Pattern

All handlers follow a consistent pattern:
1. Accept CosmosDB connection parameters in constructor
2. Create container client internally
3. Return Pydantic model instances (not raw dicts)
4. Handle enum serialization/deserialization

## 6. Development Workflows

### Adding New Models

1. Edit TypeScript models in `../shared/Models.ts`
2. Run `make build` to regenerate Python models
3. Create/update handler class if needed
4. Export from `cosmos/__init__.py`

### Testing Changes

Since this is a shared library, test across all consuming services:
1. Make changes in `shared_quickscribe_py/`
2. Changes are immediately available due to `-e` install
3. Run tests in backend, transcoder, and sync service

### Environment Variables

Required variables depend on enabled features (see `config/settings.py` for full list):

```bash
# Core Azure services
AZURE_COSMOS_ENDPOINT=https://xxx.documents.azure.com
AZURE_COSMOS_KEY=xxx
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# AI features (when ai_enabled=true)
AZURE_OPENAI_API_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_MINI_DEPLOYMENT_NAME=gpt-4o-mini
```

## 7. Known Limitations / TODOs

1. **Azure Speech Services** (`speech_service.py`):
   - Currently a placeholder with `NotImplementedError`
   - Full implementation needed for batch transcription
   - Reference: `backend/routes/az_transcription_routes.py`
   - Should support: batch creation, status polling, result download, diarization

2. **Handler Factory Coupling**:
   - `handler_factory.py` imports from a `config` module not in this package
   - Designed specifically for Flask backend integration
   - Non-Flask services must instantiate handlers directly

3. **Model Compatibility**:
   - Auto-generated models may have generic status enums (Status1, Status10, etc.)
   - Consider improving JSON schema output for cleaner enum names

## 8. Suggested Improvements or Considerations for AI Agents

1. **When modifying models**: Always run `make build` in the parent backend directory after changing `../shared/Models.ts` to keep Python models in sync.

2. **When using handlers**: Check if the service is Flask-based before using factory functions. For non-Flask services, instantiate handlers directly with connection parameters.

3. **Async operations**: The `AzureOpenAIClient` supports both sync and async methods. Use async variants (`send_prompt_async`, `send_multiple_prompts_concurrent`) for batch operations to improve performance.

4. **Configuration validation**: Always use `QuickScribeSettings()` or `get_settings()` at startup to validate all required environment variables before the application begins processing.

5. **Plaud integration quirks**: Plaud creates `.opus` files that are actually MP3 format. The `PlaudClient.download_file()` method handles this conversion automatically.

6. **Recording timestamps**: When creating recordings, `title` defaults to `original_filename` and `recorded_timestamp` defaults to upload time if not provided.
