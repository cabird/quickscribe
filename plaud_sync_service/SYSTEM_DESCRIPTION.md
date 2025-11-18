# System Description
**Git commit:** 798b46476c2d52dc8c006a9bbfdf98d8c1623415

# Plaud Sync Service - System Description

## Purpose

The Plaud Sync Service is an Azure Functions-based microservice that automatically synchronizes audio recordings from Plaud Note devices to QuickScribe, processes them for transcription, and enriches them with AI-generated metadata. It replaces the previous queue-based transcoder container with a scheduled, observable job orchestrator that provides better visibility, error handling, and retry logic.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Plaud Sync Service                           │
│                   (Azure Functions App)                          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐       │
│  │  Timer       │  │  HTTP        │  │  Health         │       │
│  │  Trigger     │  │  Trigger     │  │  Check          │       │
│  │  (15 min)    │  │  (Manual)    │  │                 │       │
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
    │  Services            │   │  (webapp.plaud.ai)      │
    └──────────────────────┘   └─────────────────────────┘
                   │                       │
                   ▼                       ▼
         ┌──────────────────────────────────────────┐
         │          Azure Cosmos DB                  │
         │  • Recordings  • Transcriptions          │
         │  • Users       • Job Executions          │
         │  • Manual Review Items                   │
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
├── src/                          # Main source code (moved in commit 798b464)
│   ├── job_executor.py          # Job orchestration engine
│   ├── transcription_poller.py  # Transcription status checker
│   ├── plaud_processor.py       # Plaud recording processor
│   ├── logging_handler.py       # Dual-destination logger
│   ├── main.py                  # Entry point
│   ├── service_version.py       # Version tracking
│   ├── prompts.yaml             # AI prompt templates
│   └── view_jobs.py             # Job execution viewer utility
├── azure_speech/                # Azure Speech Services client library
│   └── python-client/           # Auto-generated API client
├── tests/                       # Test scripts
├── requirements.txt             # Python dependencies
├── Makefile                     # Build and deployment commands
├── README.md                    # Setup and usage instructions
└── SYSTEM_DESCRIPTION.md        # This file
```

## Core Components

### 1. Main Entry Point (`src/main.py`)

The entry point that initializes and runs the sync service:

- **Scheduled Trigger**: Runs every 15 minutes (cron: `0 */15 * * * *`)
- **HTTP Trigger**: Manual invocation from frontend or API
- **Health Check**: Returns service status and configuration

Responsibilities:
- Load and validate configuration at startup
- Dispatch execution to JobExecutor
- Handle trigger-specific parameters (user filtering, test mode)

### 2. Job Executor (`src/job_executor.py`)

The main orchestration engine that coordinates the entire sync workflow.

**Key Features:**
- **Concurrent Job Prevention**: Uses CosmosDB locks to prevent overlapping sync jobs
- **User Iteration**: Processes all users with `plaudSettings.enableSync = true`
- **Job Execution Tracking**: Creates JobExecution documents with full logs and statistics
- **Deleted Items Blocking**: Prevents re-syncing of recordings that users have deleted (uncommitted change)
- **Dual-Phase Processing**:
  1. **Phase 1**: Check pending transcriptions and update completed ones
  2. **Phase 2**: Fetch and process new Plaud recordings

**Deleted Items Handler Integration (Uncommitted):**
The JobExecutor now integrates with DeletedItemsHandler to prevent re-syncing deleted recordings:

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
- Poll Azure Speech Services batch transcription API
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

**Azure Speech Services Polling:**
- Batch transcription API (`/transcriptions/{id}`)
- Status progression: `NotStarted` → `Running` → `Succeeded` / `Failed`
- Duration format: ISO 8601 (e.g., `PT45M17S` = 45 minutes 17 seconds)
- Results downloaded from `results.url`

### 4. Plaud Processor (`src/plaud_processor.py`)

Handles the download, transcoding, and submission of Plaud recordings.

**Key Features:**

#### Deduplication
- Loads existing Plaud IDs from database before processing
- Skips recordings that already exist (by `plaudMetadata.plaudId`)
- Tracks skipped count in job statistics
- **Benefit**: Saves bandwidth, disk I/O, transcription API calls, and costs

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

**Cleanup Helpers:**
- `_cleanup_failed_recording(recording_id, user_id, blob_uploaded)`: Deletes single recording + blob
- `_cleanup_chunk_group(chunk_group_id)`: Queries and deletes all chunks in group + blobs

#### Audio Processing
- **Download**: From Plaud API with bearer token authentication
- **File Extension Handling**: Plaud `.opus` files are actually MP3 format
- **Transcoding**: FFmpeg to standardize MP3 format
  - Defensive filename handling (works with missing extensions)
  - Uses `Path.stem` approach for temp file generation
- **Splitting**: FFmpeg `-ss` (start) and `-t` (duration) for chunk extraction
- **Upload**: Azure Blob Storage with SAS URL generation

### 5. Logging Handler (`src/logging_handler.py`)

Dual-destination logging system.

**Features:**
- **Stdout**: Console logging for Azure Functions monitoring
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
    userResults: UserSyncResult[];      // Per-user breakdown
    errorCount: integer;
    testRunId?: string;                 // For test cleanup
}
```

### JobExecutionStats
Aggregated statistics for the entire job:

```typescript
interface JobExecutionStats {
    users_processed: integer;           // Total users synced
    transcriptions_checked: integer;    // Pending transcriptions checked
    transcriptions_completed: integer;  // Transcriptions that finished
    recordings_fetched: integer;        // Total from Plaud API
    recordings_skipped: integer;        // Already in database (deduplication)
    recordings_processed: integer;      // Downloaded and processed
    recordings_transcoded: integer;     // Successfully transcoded
    recordings_uploaded: integer;       // Uploaded to blob storage
    recordings_submitted: integer;      // Submitted to Azure Speech
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
    reason: string;                     // Failure reason
    failureCount: integer;              // Number of failures
    lastFailureMessage: string;
    createdAt: string;                  // ISO timestamp
}
```

## Key Features

### 1. Deduplication and Deleted Items Prevention

**Problem Solved**: Previous implementation downloaded and processed all Plaud recordings on every sync, creating duplicates. Additionally, deleted recordings were being re-synced.

**Solution**:
- Query existing `plaudMetadata.plaudId` values before processing
- Query deleted Plaud IDs from DeletedItemsHandler (uncommitted change)
- Skip recordings that already exist OR have been deleted
- Track skipped count separately from processed count

**Implementation**:
```python
# src/job_executor.py
existing_plaud_ids = self.recording_handler.get_user_plaud_ids(user.id)

# NEW: Fetch deleted Plaud IDs to prevent re-syncing
deleted_plaud_ids = self.deleted_items_handler.get_deleted_plaud_ids(user.id)

# Combine both lists for deduplication
all_blocked_ids = existing_plaud_ids + deleted_plaud_ids
processor.set_existing_plaud_ids(all_blocked_ids)

# src/plaud_processor.py
if plaud_recording.id in self._existing_plaud_ids:
    return {"skipped": 1}  # Skips both existing and deleted recordings
```

**Benefits**:
- Prevents duplicate recordings in database
- Prevents re-downloading deleted recordings
- Saves bandwidth, storage, transcription API calls, and costs
- Respects user's deletion actions

### 2. Automatic Chunking

**Problem Solved**: Azure Speech Services has file size and duration limits.

**Solution**: Automatically split large files into manageable chunks.

**Thresholds**:
- File size > 300 MB, OR
- Duration > 2 hours (7200 seconds)

**Chunk Sizing**:
- Max 200 MB per chunk
- Max 1.5 hours per chunk
- Minimum 2 chunks

**Chunk Linking**:
- Each chunk gets a unique `chunkGroupId` (UUID)
- Query: `SELECT * FROM c WHERE c.chunkGroupId = @group_id`
- Enables future features: chunk reassembly, UI grouping, batch operations

### 3. AI Post-Processing

**Integration Point**: Automatically triggered when transcription completes.

**Process**:
1. Transcription poller detects `status = Succeeded`
2. Download transcript with speaker diarization
3. Call Azure OpenAI mini model with transcript text
4. Parse JSON response: `{title: "...", description: "..."}`
5. Update Recording document

**Prompt Template** (from `prompts.yaml`):
```yaml
generate_title_and_description:
  system: "You are an assistant that generates concise titles and descriptions..."
  user: "Based on this transcript:\n\n{transcript}\n\nGenerate:\n1. Title (max 60 chars)\n2. Description (1-2 sentences)"
  response_format: "JSON: {\"title\": \"...\", \"description\": \"...\"}"
```

**Model Selection**:
- Uses **mini model** (e.g., gpt-4o-mini) for cost efficiency
- Fallback gracefully if AI fails (transcription still succeeds)

### 4. Atomic Processing with Cleanup

**Problem Solved**: Failed processing left orphaned records and blobs.

**Solution**: Track state and cleanup on failure.

**Guarantees**:
- **Single recordings**: All-or-nothing (blob upload failure → delete recording)
- **Chunked recordings**: All-or-nothing (any chunk fails → delete all chunks)
- **Transcription failure**: Non-fatal (keep recording for manual retry)

**Cleanup Triggers**:
- Exception in processing pipeline
- Blob upload failure
- Recording update failure

**Cleanup Operations**:
- Delete Recording document from CosmosDB
- Delete blob file from Azure Storage
- Query and delete all chunks in a group (for chunked processing)

### 5. Failure Handling and Retry

**Per-Recording Failures**:
- Logged but don't fail entire job
- Increment `processing_failure_count` on Recording
- Retry automatically on next sync run

**Auto-Retry Logic**:
- Max 3 attempts per recording
- After 3 failures: `needs_manual_review = true`
- Create ManualReviewItem document

**Manual Review Queue**:
- Query: `SELECT * FROM c WHERE c.needs_manual_review = true`
- Contains failure details and error messages
- Admin can diagnose and retry manually

**Critical Failures** (fail entire job):
- Plaud API authentication failure
- CosmosDB connection failure
- Configuration validation failure

## Configuration

### Shared Configuration System

Uses Pydantic-based configuration from `shared_quickscribe_py`:

```python
from shared_quickscribe_py.config import get_settings

settings = get_settings()  # Validates at startup
```

**Feature Flags**:
```python
settings.ai_enabled            # Enable AI post-processing
settings.cosmos_enabled        # Enable CosmosDB
settings.blob_storage_enabled  # Enable Blob Storage
settings.speech_services_enabled  # Enable transcription
settings.plaud_enabled         # Enable Plaud sync
```

**Service Settings**:
```python
settings.azure_openai.api_endpoint
settings.azure_openai.deployment_name
settings.azure_openai.mini_deployment_name

settings.cosmos.endpoint
settings.cosmos.key
settings.cosmos.database_name

settings.blob_storage.connection_string
settings.blob_storage.audio_container_name

settings.speech_services.subscription_key
settings.speech_services.region

settings.plaud_api.base_url
```

### Environment Variables

See `local.settings.json.example` for complete list. Key variables:

```bash
# Cosmos DB
AZURE_COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
AZURE_COSMOS_KEY=your-key
AZURE_COSMOS_DATABASE_NAME=quickscribe

# Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_STORAGE_CONTAINER_NAME=audio-files

# Azure Speech Services
AZURE_SPEECH_SUBSCRIPTION_KEY=your-key
AZURE_SPEECH_REGION=westus2

# Azure OpenAI (for AI post-processing)
AZURE_OPENAI_API_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-prod
AZURE_OPENAI_MINI_DEPLOYMENT_NAME=gpt-4o-mini-prod
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Feature Flags
AI_ENABLED=true
PLAUD_ENABLED=true

# Optional
TEST_RUN_ID=test_20250104_120000  # For test runs
LOG_LEVEL=INFO  # DEBUG for verbose logging
```

## Dependencies

### Python Packages (`requirements.txt`)
```
azure-functions>=1.18.0
azure-cosmos>=4.5.0
azure-storage-blob>=12.19.0
openai>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
requests>=2.31.0
PyYAML>=6.0.0
ffmpeg-python>=0.2.0
```

### External Services
- **Azure Cosmos DB**: Document storage
- **Azure Blob Storage**: Audio file storage
- **Azure Speech Services**: Batch transcription API
- **Azure OpenAI**: AI post-processing (title/description)
- **Plaud Note API**: Recording synchronization

### System Requirements
- **FFmpeg**: Audio transcoding and chunking
- **Python 3.11+**: Runtime environment
- **Azure Functions Core Tools v4**: Local development

## Monitoring and Observability

### Logging Destinations
1. **Azure Application Insights**: All function executions, metrics, exceptions
2. **Cosmos DB JobExecution**: Structured logs per job execution
3. **Stdout**: Console logs for Azure Functions runtime

### Key Metrics
- Job execution duration
- Per-user processing time
- Transcription completion rate
- Deduplication ratio (skipped vs. fetched)
- Error rate and failure reasons
- API call counts (Plaud, Azure Speech, OpenAI)

### Queries

**Recent Jobs**:
```sql
SELECT * FROM c
WHERE c.partitionKey = 'job_execution'
ORDER BY c.startTime DESC
```

**Failed Jobs**:
```sql
SELECT * FROM c
WHERE c.partitionKey = 'job_execution'
AND c.status = 'failed'
```

**Manual Review Queue**:
```sql
SELECT * FROM c
WHERE c.partitionKey = 'manual_review'
ORDER BY c.createdAt DESC
```

**Recordings Needing Review**:
```sql
SELECT * FROM c
WHERE c.type = 'recording'
AND c.needs_manual_review = true
```

## Testing

### Test Mode Support

Enable via `TEST_RUN_ID` environment variable:

```python
# test_plaud_sync.py
test_run_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4()[:8]}"
executor.execute_sync_job(trigger_source="manual", test_run_id=test_run_id)
```

**Benefits**:
- All created documents tagged with `testRunId`
- Cleanup script can remove all test data: `python cleanup_test_run.py <test_run_id>`
- Query test data: `SELECT * FROM c WHERE c.testRunId = @test_run_id`

### Test Scripts

**`test_plaud_sync.py`**: Run sync with test tracking
```bash
python test_plaud_sync.py --max-recordings 5
python test_plaud_sync.py --user-id <user_id>
python test_plaud_sync.py --check-transcriptions-only
```

**`cleanup_test_run.py`**: Clean up test data
```bash
python cleanup_test_run.py <test_run_id>        # Specific test run
python cleanup_test_run.py --latest              # Most recent test
python cleanup_test_run.py --all                 # All test runs
python cleanup_test_run.py --list                # List test runs
python cleanup_test_run.py <test_run_id> --dry-run  # Preview
```

## Future Enhancements

### Planned Features
- [ ] Real-time progress updates via SignalR
- [ ] Configurable chunking thresholds per user
- [ ] Support for multiple Plaud accounts per user
- [ ] Incremental sync (timestamp-based, not full scan)
- [ ] Webhook support for instant sync on new recording
- [ ] Parallel user processing (currently sequential)
- [ ] Distributed locking with Azure Blob leases
- [ ] Retry backoff strategy for transient failures
- [ ] Admin UI for manual review queue
- [ ] Metrics dashboard in frontend

### Potential Optimizations
- Cache Plaud bearer tokens (currently re-authenticated each sync)
- Stream downloads (currently download to disk first)
- Parallel chunk processing (currently sequential)
- Batch blob uploads (currently one-by-one)
- CosmosDB bulk operations (currently individual inserts)

## Recent Changes

### Commit 798b464: Source Code Reorganization
- **What Changed**: All source files moved from root to `src/` directory
- **Files Moved**:
  - `job_executor.py` → `src/job_executor.py`
  - `transcription_poller.py` → `src/transcription_poller.py`
  - `plaud_processor.py` → `src/plaud_processor.py`
  - `logging_handler.py` → `src/logging_handler.py`
  - `main.py` → `src/main.py`
  - `service_version.py` → `src/service_version.py`
  - `prompts.yaml` → `src/prompts.yaml`
  - `view_jobs.py` → `src/view_jobs.py`
- **Benefit**: Cleaner repository structure, separates source from config/docs

### Uncommitted: DeletedItemsHandler Integration
- **What Changed**: JobExecutor now queries DeletedItemsHandler to prevent re-syncing deleted recordings
- **Impact**: Recordings deleted by users won't be re-downloaded on next sync
- **Files Modified**: `src/job_executor.py`
- **Status**: Working in local branch, pending commit

## Related Documentation

- **README.md**: Setup and usage instructions
- **AI_POSTPROCESSING.md**: AI post-processing implementation details
- **DEDUPLICATION_FIX.md**: Deduplication feature explanation
- **CONFIG_MIGRATION.md**: Configuration system migration details
- **DELETE_SOLUTION.md**: Deleted recordings handling (planned feature)
