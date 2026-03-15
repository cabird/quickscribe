# System Description
**Git commit:** 5b007ef08f5714d19faf318994f63082d90698fd

# Plaud Sync Service - System Description

## Purpose

The Plaud Sync Service is an Azure Container Apps Jobs-based microservice that automatically synchronizes audio recordings from Plaud Note devices to QuickScribe, processes them for transcription, and enriches them with AI-generated metadata. It runs as a scheduled job (not an HTTP server) that provides better observability, error handling, and retry logic.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Plaud Sync Service                           │
│               (Azure Container Apps Job)                         │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐       │
│  │  Scheduled   │  │  Manual      │  │  Test Mode      │       │
│  │  Trigger     │  │  Trigger     │  │  (Environment)  │       │
│  │  (Cron)      │  │  (Env vars)  │  │                 │       │
│  └──────┬───────┘  └──────┬───────┘  └─────────────────┘       │
│         └──────────────────┴────────────────┐                   │
│                                              ▼                   │
│                                    ┌─────────────────┐           │
│                                    │  Job Executor   │           │
│                                    │  (Orchestrator) │           │
│                                    └────────┬────────┘           │
│                                             │                    │
│                    ┌────────────────────────┼────────────┐       │
│                    ▼                        ▼            ▼       │
│          ┌─────────────────┐   ┌──────────────────┐  ┌─────┐   │
│          │  Transcription  │   │  Plaud           │  │ Log │   │
│          │  Poller         │   │  Processor       │  │ Handler│ │
│          └─────────────────┘   └──────────────────┘  └─────┘   │
│                  │                       │                       │
└──────────────────┼───────────────────────┼───────────────────────┘
                   │                       │
                   ▼                       ▼
    ┌──────────────────────┐   ┌─────────────────────────┐
    │  Azure Speech        │   │  Plaud Note API         │
    │  Services (v3.2)     │   │  (webapp.plaud.ai)      │
    └──────────────────────┘   └─────────────────────────┘
                   │                       │
                   ▼                       ▼
         ┌──────────────────────────────────────────┐
         │          Azure Cosmos DB                  │
         │  • Recordings  • Transcriptions          │
         │  • Users       • Job Executions          │
         │  • Manual Review Items • Deleted Items   │
         └──────────────────────────────────────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Azure Blob Storage   │
                │  (Audio files)        │
                └──────────────────────┘
```

## 1. Repository Structure

```
plaud_sync_service/
├── src/                          # Main source code
│   ├── main.py                   # Entry point (no HTTP server)
│   ├── job_executor.py           # Job orchestration engine
│   ├── transcription_poller.py   # Transcription status checker
│   ├── plaud_processor.py        # Plaud recording processor
│   ├── logging_handler.py        # Dual-destination logger
│   ├── service_version.py        # Version tracking
│   ├── prompts.yaml              # AI prompt templates
│   └── view_jobs.py              # Job execution viewer utility
├── azure_speech/                 # Azure Speech Services client library
│   ├── AZURE_SPEECH_TRANSCRIPTION_GUIDE.md  # Detailed API guide
│   └── python-client/            # Auto-generated API client (v3.2)
│       ├── azure_speech_client/  # Main package
│       │   ├── api/              # API endpoint classes
│       │   ├── models/           # Data models
│       │   ├── api_client.py     # HTTP client
│       │   └── configuration.py  # Configuration management
│       ├── swagger_client/       # Legacy compatibility
│       ├── pyproject.toml        # Package configuration
│       └── README.md             # Client documentation
├── scripts/                      # Utility and test scripts
│   ├── test_plaud_sync.py        # Run sync with test tracking
│   ├── cleanup_test_run.py       # Clean up test data
│   ├── clear_locks.py            # Clear stuck locks
│   └── view_jobs.py              # View job executions
├── requirements.txt              # Python dependencies
├── Makefile                      # Build and deployment commands
├── Dockerfile                    # Container build configuration
├── README.md                     # Setup and usage instructions
└── SYSTEM_DESCRIPTION.md         # This file
```

## 2. Languages, Size & Composition

- **Primary Language**: Python 3.11+
- **Azure Speech Client**: Auto-generated Python from OpenAPI spec (v3.2)
- **Configuration**: YAML (prompts), JSON (environment)
- **Total Files**: ~120 Python files (mostly in azure_speech_client)
- **Core Source Files**: 8 files in `src/`
- **Scripts**: 4 utility scripts in `scripts/`

## Core Components

### 1. Main Entry Point (`src/main.py`)

Simple entry point that runs the sync service directly (no HTTP server):

- **Scheduled Execution**: Triggered by Azure Container Apps Jobs cron schedule
- **Environment-based Configuration**: `TRIGGER_SOURCE`, `TEST_RUN_ID`, `MAX_RECORDINGS`
- **Direct Execution**: Calls JobExecutor and exits with status code

Responsibilities:
- Load and validate configuration from shared library
- Create JobExecutor with validated settings
- Execute sync job and exit with appropriate status code

### 2. Job Executor (`src/job_executor.py`)

The main orchestration engine that coordinates the entire sync workflow.

**Key Features:**
- **Concurrent Job Prevention**: Uses CosmosDB locks to prevent overlapping sync jobs
- **User Iteration**: Processes all users with `plaudSettings.enableSync = true`
- **Job Execution Tracking**: Creates JobExecution documents with full logs and statistics
- **Deleted Items Blocking**: Prevents re-syncing of recordings that users have deleted
- **Dual-Phase Processing**:
  1. **Phase 1**: Check pending transcriptions and update completed ones
  2. **Phase 2**: Fetch and process new Plaud recordings

**Deleted Items Handler Integration:**
The JobExecutor integrates with DeletedItemsHandler to prevent re-syncing deleted recordings:

```python
# Load existing Plaud IDs for deduplication
existing_plaud_ids = self.recording_handler.get_user_plaud_ids(user.id)

# Also fetch deleted Plaud IDs to prevent re-syncing
deleted_plaud_ids = self.deleted_items_handler.get_deleted_plaud_ids(user.id)

# Combine both lists for deduplication
all_blocked_ids = existing_plaud_ids + deleted_plaud_ids
processor.set_existing_plaud_ids(all_blocked_ids)
```

This ensures that when a user deletes a Plaud recording, it won't be re-downloaded on the next sync.

**Execution Flow:**
```python
1. Acquire lock (prevent concurrent execution)
2. Create JobExecution record (status: running)
3. Query users with Plaud sync enabled
4. For each user:
    a. Check pending transcriptions (TranscriptionPoller)
       → Poll Azure Speech Services
       → Download completed transcripts
       → Trigger AI post-processing (title/description)
    b. Fetch new Plaud recordings (PlaudProcessor)
       → Load existing Plaud IDs (deduplication)
       → Load deleted Plaud IDs (prevent re-sync)
       → Download new recordings
       → Transcode to MP3
       → Check if chunking needed
       → Upload to blob storage
       → Submit to Azure Speech Services
5. Aggregate statistics
6. Update JobExecution (status: completed)
7. Release lock
```

### 3. Transcription Poller (`src/transcription_poller.py`)

Checks the status of pending transcriptions and processes completed ones.

**Responsibilities:**
- Query recordings with `transcription_job_status = 'submitted' | 'processing'`
- Poll Azure Speech Services batch transcription API (v3.2)
- Download completed transcriptions
- Parse diarized results (speaker identification)
- Create/update Transcription documents in CosmosDB
- **Trigger AI post-processing** for title and description generation

**AI Post-Processing Integration:**
```python
Step 8: AI Post-Processing (in _handle_completed_transcription)
    → Load transcript text
    → Call Azure OpenAI (mini model)
    → Extract JSON {title, description}
    → Update Recording document
    → Log success/failure
```

**Azure Speech Services Integration:**
Uses the auto-generated `azure_speech_client` package:
- `CustomSpeechTranscriptionsApi` for transcription management
- API v3.2 endpoint: `https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2`
- Status progression: `NotStarted` → `Running` → `Succeeded` / `Failed`

### 4. Plaud Processor (`src/plaud_processor.py`)

Handles the download, transcoding, and submission of Plaud recordings.

**Key Features:**

#### Deduplication
- Loads existing Plaud IDs from database before processing
- Also loads deleted Plaud IDs to prevent re-syncing
- Skips recordings that already exist OR have been deleted
- Tracks skipped count in job statistics

```python
# Before processing each recording
if plaud_recording.id in self._existing_plaud_ids:
    return {"skipped": 1}
```

#### Automatic Chunking
Files are automatically split if they exceed:
- **Size threshold**: 300 MB
- **Duration threshold**: 2 hours (7200 seconds)

Chunking strategy:
- Max chunk size: 200 MB
- Max chunk duration: 1.5 hours (5400 seconds)
- Each chunk becomes an independent Recording
- **Chunk Group ID**: UUID linking all chunks from same original file
- Title format: `"Original Filename - Part X of Y"`
- Timestamps adjusted for chunk offsets

#### Atomic Processing with Cleanup
**Single Recording Processing** (`_process_single_recording`):
```
1. Transcode → FAIL: No cleanup needed (nothing created yet)
2. Create Recording in Cosmos → POINT OF NO RETURN
3. Upload blob → FAIL: Delete recording
4. Update recording → FAIL: Delete recording + blob
5. Submit transcription → FAIL: Keep recording (manual retry possible)
```

**Chunked Recording Processing** (`_process_chunked_recording`):
```
1. Generate chunk_group_id (UUID)
2. For each chunk:
    a. Transcode → FAIL: No cleanup needed
    b. Create Recording (with chunkGroupId) → POINT OF NO RETURN
    c. Upload blob → FAIL: Delete ALL chunks in group
    d. Update recording → FAIL: Delete ALL chunks in group
    e. Submit transcription → FAIL: Keep chunk (manual retry)
3. If ANY chunk fails → cleanup entire group
```

#### Audio Processing
- **Download**: From Plaud API with bearer token authentication
- **File Extension Handling**: Plaud `.opus` files are actually MP3 format
- **Transcoding**: FFmpeg to standardize MP3 format (128k bitrate)
- **Splitting**: FFmpeg `-ss` (start) and `-t` (duration) for chunk extraction
- **Upload**: Azure Blob Storage with SAS URL generation (48-hour expiry)

### 5. Azure Speech Client Library (`azure_speech/python-client/`)

Auto-generated Python client for Azure Speech Services API v3.2.

**Package Structure:**
- `azure_speech_client.Configuration`: API configuration with subscription key
- `azure_speech_client.ApiClient`: HTTP client with authentication
- `azure_speech_client.CustomSpeechTranscriptionsApi`: Transcription management

**Key API Classes:**
- `CustomSpeechTranscriptionsApi` - Batch transcription operations
- `CustomSpeechDatasetsForModelAdaptationApi` - Dataset management
- `CustomSpeechModelsApi` - Custom model operations
- `CustomSpeechEndpointsApi` - Endpoint management

**Models:**
- `Transcription`, `TranscriptionProperties` - Transcription configuration
- `DiarizationProperties`, `DiarizationSpeakersProperties` - Speaker diarization

### 6. Logging Handler (`src/logging_handler.py`)

Dual-destination logging system.

**Features:**
- **Stdout**: Console logging for Azure Container Apps monitoring
- **CosmosDB**: Structured logs stored in JobExecution documents
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Context Preservation**: All logs associated with job execution ID

## Data Models

### JobExecution
Tracks each sync job execution with comprehensive metadata:

```typescript
interface JobExecution {
    id: string;                         // Job execution ID (UUID)
    partitionKey: "job_execution";      // Partition key
    status: "queued" | "running" | "completed" | "failed";
    startTime: string;                  // ISO timestamp
    endTime?: string;                   // ISO timestamp
    triggerSource: "scheduled" | "manual";
    logs: JobLogEntry[];                // All log entries
    stats: JobExecutionStats;           // Aggregated statistics
    usersProcessed: string[];           // User IDs processed
    errorMessage?: string;              // Error details if failed
    ttl: number;                        // 30 days TTL
    testRunId?: string;                 // For test cleanup
}
```

### JobExecutionStats
Aggregated statistics for the entire job:

```typescript
interface JobExecutionStats {
    transcriptions_checked: integer;    // Pending transcriptions checked
    transcriptions_completed: integer;  // Transcriptions that finished
    recordings_found: integer;          // Total from Plaud API
    recordings_downloaded: integer;     // Successfully downloaded
    recordings_transcoded: integer;     // Successfully transcoded
    recordings_uploaded: integer;       // Uploaded to blob storage
    recordings_skipped: integer;        // Already in database or deleted
    transcriptions_submitted: integer;  // Submitted to Azure Speech
    chunks_created: integer;            // For large files
    errors: integer;                    // Total errors
}
```

### Recording (Extended)
Added fields to support new features:

```typescript
interface Recording {
    // ... existing fields ...

    // AI-generated metadata
    description?: string;               // 1-2 sentence summary

    // Chunking support
    chunkGroupId?: string;              // UUID linking related chunks

    // Test tracking
    testRunId?: string;                 // For test cleanup

    // Token count (denormalized from transcription)
    token_count?: number;               // For fast frontend display
}
```

### ManualReviewItem
Queue for recordings that failed multiple times:

```typescript
interface ManualReviewItem {
    id: string;                         // UUID
    partitionKey: "manual_review";
    recordingId: string;                // Reference to Recording
    userId: string;
    recordingTitle: string;
    failureCount: integer;              // Number of failures
    lastError: string;
    failureHistory: FailureRecord[];    // Detailed failure history
    status: "pending" | "resolved";
    createdAt: string;                  // ISO timestamp
    updatedAt: string;                  // ISO timestamp
    testRunId?: string;
}
```

## 3. Key Components and Modules

### Shared Library Integration

Uses `shared_quickscribe_py` for all common functionality:

```python
from shared_quickscribe_py.config import get_settings, QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, UserHandler, TranscriptionHandler, LocksHandler,
    JobExecutionHandler, ManualReviewItemHandler, DeletedItemsHandler,
    Recording, User, JobExecution, Transcription, ManualReviewItem
)
from shared_quickscribe_py.azure_services import BlobStorageClient
from shared_quickscribe_py.azure_services.azure_openai import get_openai_client
from shared_quickscribe_py.plaud import PlaudClient
```

### Configuration System

Uses Pydantic-based configuration from shared library:

```python
from shared_quickscribe_py.config import get_settings

settings = get_settings()  # Validates at startup

# Access nested settings
settings.cosmos.endpoint
settings.cosmos.key
settings.speech_services.subscription_key
settings.speech_services.region
settings.ai_enabled  # Feature flag
```

## 4. Build, Tooling, and Dependencies

### Python Packages (`requirements.txt`)
```
# Azure SDK components
azure-cosmos>=4.5.0
azure-storage-blob>=12.19.0
azure-storage-queue>=12.8.0
azure-identity>=1.15.0

# Audio processing
ffmpeg-python>=0.2.0

# HTTP requests
requests>=2.31.0
aiohttp>=3.9.0

# Configuration and data formats
PyYAML>=6.0

# Logging and monitoring
opencensus-ext-azure>=1.1.9
```

### Additional Dependencies (via Dockerfile)
- `shared_quickscribe_py` - Shared library (editable install)
- `azure_speech_client` - Azure Speech Services client (local install)

### External Services
- **Azure Cosmos DB**: Document storage
- **Azure Blob Storage**: Audio file storage
- **Azure Speech Services**: Batch transcription API (v3.2)
- **Azure OpenAI**: AI post-processing (title/description)
- **Plaud Note API**: Recording synchronization

### System Requirements
- **FFmpeg**: Audio transcoding and chunking
- **Python 3.11+**: Runtime environment
- **Azure Container Apps Jobs**: Scheduled execution

## 5. Runtime Architecture

### Container Apps Job Execution

The service runs as an Azure Container Apps Job (not an HTTP server):

1. **Trigger**: Cron schedule or manual trigger
2. **Execution**: Container starts, runs `main.py`, exits
3. **Status**: Exit code 0 = success, non-zero = failure
4. **Logs**: Streamed to Azure Monitor via stdout/stderr

### Environment Variables

```bash
# Execution control
TRIGGER_SOURCE=scheduled|manual
TEST_RUN_ID=test_20250108_120000
MAX_RECORDINGS=5

# Shared library provides all service configuration
# (Cosmos, Blob Storage, Speech Services, OpenAI, Plaud)
```

## 6. Development Workflows

### Test Scripts

**`scripts/test_plaud_sync.py`**: Run sync with test tracking
```bash
python scripts/test_plaud_sync.py --max-recordings 5
python scripts/test_plaud_sync.py --user-id <user_id>
python scripts/test_plaud_sync.py --check-transcriptions-only
```

**`scripts/cleanup_test_run.py`**: Clean up test data
```bash
python scripts/cleanup_test_run.py <test_run_id>        # Specific test run
python scripts/cleanup_test_run.py --latest              # Most recent test
python scripts/cleanup_test_run.py --all                 # All test runs
python scripts/cleanup_test_run.py <test_run_id> --dry-run  # Preview
```

**`scripts/clear_locks.py`**: Clear stuck locks
```bash
python scripts/clear_locks.py
```

**`scripts/view_jobs.py`**: View job executions
```bash
python scripts/view_jobs.py
python scripts/view_jobs.py --job-id <job_id>
```

### Test Mode Support

Enable via `TEST_RUN_ID` environment variable:

```python
test_run_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4()[:8]}"
executor.execute_sync_job(trigger_source="manual", test_run_id=test_run_id)
```

**Benefits**:
- All created documents tagged with `testRunId`
- Cleanup script can remove all test data
- Query test data: `SELECT * FROM c WHERE c.testRunId = @test_run_id`

## 7. Known Limitations / TODOs

### Current Limitations
- Sequential user processing (not parallel)
- Re-authentication on each sync (no token caching)
- Download to disk before upload (no streaming)
- Sequential chunk processing

### Planned Features
- [ ] Real-time progress updates via SignalR
- [ ] Configurable chunking thresholds per user
- [ ] Support for multiple Plaud accounts per user
- [ ] Incremental sync (timestamp-based, not full scan)
- [ ] Webhook support for instant sync on new recording
- [ ] Parallel user processing
- [ ] Distributed locking with Azure Blob leases
- [ ] Retry backoff strategy for transient failures
- [ ] Admin UI for manual review queue
- [ ] Metrics dashboard in frontend

### Potential Optimizations
- Cache Plaud bearer tokens
- Stream downloads directly to blob storage
- Parallel chunk processing
- Batch blob uploads
- CosmosDB bulk operations

## 8. Suggested Improvements or Considerations for AI Agents

### When Working with This Service

1. **Configuration**: Always use `get_settings()` from shared library - never hardcode values
2. **Database Operations**: Use handlers from `shared_quickscribe_py.cosmos` - they handle serialization
3. **Azure Speech Client**: Import from `azure_speech_client` package, not direct HTTP calls
4. **Atomic Operations**: Follow the cleanup patterns in `plaud_processor.py` for new operations
5. **Testing**: Use `TEST_RUN_ID` for all test runs to enable cleanup

### Key Patterns

**Deduplication Check**:
```python
existing_ids = recording_handler.get_user_plaud_ids(user_id)
deleted_ids = deleted_items_handler.get_deleted_plaud_ids(user_id)
all_blocked = existing_ids + deleted_ids
```

**Atomic Cleanup on Failure**:
```python
try:
    # Create resources
    recording = handler.create_recording(...)
    blob_client.upload(...)
except Exception:
    # Cleanup everything created
    handler.delete_recording(recording.id)
    blob_client.delete(blob_path)
```

**Azure Speech Services API**:
```python
configuration = azure_speech_client.Configuration()
configuration.api_key["Ocp-Apim-Subscription-Key"] = speech_key
configuration.host = f"https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2"
api_client = azure_speech_client.ApiClient(configuration)
api = azure_speech_client.CustomSpeechTranscriptionsApi(api_client=api_client)
```

## Recent Changes

### Commits Since Last Update

1. **5b007ef**: docs: Update backend system description
2. **e703cbb**: fix: Plaud sync bugs and UI improvements
3. **e95b648**: feat: Add manual Plaud sync trigger and UI improvements
4. **5812b26**: Consolidate db_handlers to shared library, add azure_oid, rename azure_speech_client
5. **728bcbb**: Cleaning up infra and build files, adding system descriptions, adding correct method of deleting recordings

### Key Changes

#### Architecture Change: Container Apps Job (not Functions)
- Service now runs as Azure Container Apps Job instead of Azure Functions
- No HTTP server - direct execution via `main.py`
- Environment-based trigger configuration
- Exit code indicates success/failure

#### Azure Speech Client Reorganization
- Renamed from `swagger_client` to `azure_speech_client`
- Proper Python package structure with `pyproject.toml`
- API v3.2 support
- Located in `azure_speech/python-client/`

#### Shared Library Integration
- All database handlers moved to `shared_quickscribe_py`
- Configuration system from shared library
- Azure services clients from shared library
- Plaud client from shared library

#### Scripts Directory
- Test and utility scripts moved to `scripts/` directory
- `test_plaud_sync.py` - Run sync with options
- `cleanup_test_run.py` - Cleanup test data
- `clear_locks.py` - Clear stuck locks
- `view_jobs.py` - View job executions

#### Deleted Items Prevention
- Integration with `DeletedItemsHandler`
- Prevents re-syncing deleted recordings
- Combined blocking of existing + deleted Plaud IDs

## Related Documentation

- **README.md**: Setup and usage instructions
- **AZURE_SPEECH_TRANSCRIPTION_GUIDE.md**: Detailed Azure Speech API guide
- **azure_speech/python-client/README.md**: Azure Speech client documentation
