# Plaud Sync Service - Comprehensive Functionality Analysis

**Purpose:** Reference document for rewriting the Plaud Sync Service.
**Analyzed version:** v0.3.1
**Date:** 2026-03-24

---

## Table of Contents

1. [Overall Architecture](#1-overall-architecture)
2. [Plaud Device Integration](#2-plaud-device-integration)
3. [Recording Download & Upload](#3-recording-download--upload)
4. [Transcription Pipeline](#4-transcription-pipeline)
5. [Speaker Diarization](#5-speaker-diarization)
6. [Speaker Identification (ECAPA-TDNN)](#6-speaker-identification-ecapa-tdnn)
7. [AI Post-Processing](#7-ai-post-processing)
8. [Job Execution & Locking](#8-job-execution--locking)
9. [Chunking](#9-chunking)
10. [Error Handling & Retry Logic](#10-error-handling--retry-logic)
11. [Deleted Items Blocking](#11-deleted-items-blocking)
12. [Configuration & Scheduling](#12-configuration--scheduling)
13. [Utility Scripts](#13-utility-scripts)
14. [Dependencies](#14-dependencies)
15. [Technical Debt & Complexity Analysis](#15-technical-debt--complexity-analysis)

---

## 1. Overall Architecture

### Runtime Model

The service runs as an **Azure Container Apps Job** (not an HTTP server). It is triggered by a cron schedule, executes `main.py`, and exits with a status code (0 = success, non-zero = failure).

- **Cron schedule:** `*/15 * * * *` (every 15 minutes)
- **Container resources:** 2 CPU, 4 GiB memory
- **Replica timeout:** 5400 seconds (90 minutes)
- **Replica retry limit:** 3

### Entry Point: `src/main.py`

1. Loads configuration via `get_settings()` from the shared library.
2. Reads environment variables: `TRIGGER_SOURCE`, `TEST_RUN_ID`, `MAX_RECORDINGS`, `MAX_SPEAKER_ID_PER_USER`.
3. Creates a `JobExecutor` with the settings.
4. Calls `executor.execute_sync_job()`.
5. Exits with code 0 or 1.

### Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 83 | Entry point |
| `job_executor.py` | 884 | Orchestration engine (largest file) |
| `transcription_poller.py` | 467 | Polls Azure Speech for completed transcriptions |
| `plaud_processor.py` | 667 | Download, transcode, upload, submit recordings |
| `speaker_processor.py` | 313 | Speaker identification against profile DB |
| `embedding_engine.py` | 190 | ECAPA-TDNN model wrapper for speaker embeddings |
| `profile_manager.py` | 41 | Thin wrapper around SpeakerProfileStore |
| `logging_handler.py` | 96 | Dual-destination logger (stdout + in-memory for CosmosDB) |
| `service_version.py` | 1 | Version string |
| `prompts.yaml` | 48 | LLM prompt templates |

### Execution Flow (Four Phases Per User)

```
For each user with Plaud sync enabled:

  Phase A: Check Pending Transcriptions (TranscriptionPoller)
    - Query recordings where transcription_job_status IN ('submitted', 'processing')
    - Poll Azure Speech Services API for each
    - Download completed transcript JSON
    - Parse diarized transcript
    - Trigger AI post-processing (title/description generation)
    - Returns list of completed recording IDs

  Phase B: Speaker Identification (SpeakerProcessor)
    - Process newly completed recordings from Phase A
    - Process backlog of unidentified recordings (up to MAX_SPEAKER_ID_PER_USER, default 10)
    - Download audio, extract ECAPA-TDNN embeddings per speaker
    - Match against user's speaker profile DB (cosine similarity)
    - Assign auto/suggest/unknown status based on thresholds

  Phase C: Re-rate Existing Speakers
    - Re-check suggest/unknown speakers against current profiles (no ML needed)
    - Pure cosine similarity math on stored embeddings
    - Only upgrade, never downgrade (unknown->suggest, suggest->auto)

  Phase D: Fetch New Plaud Recordings (PlaudProcessor)
    - Fetch recording list from Plaud API
    - Filter out existing + deleted IDs
    - Download, transcode, upload, submit for transcription
```

---

## 2. Plaud Device Integration

### Plaud API Client (shared library: `shared_quickscribe_py/plaud/client.py`)

The Plaud API is an **undocumented REST API** at `api.plaud.ai`. Authentication uses a bearer token obtained from the Plaud web app (not OAuth -- users manually copy their token).

**Base URL:** `https://api.plaud.ai`

**API Endpoints Used:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/file/simple/web?skip=0&limit=99999&is_trash=2&sort_by=start_time&is_desc=true` | GET | List all recordings |
| `/file/temp-url/{file_id}` | GET | Get temporary S3 download URL |

**Authentication:**
- Bearer token in `Authorization: bearer {token}` header
- Token stored in user's `plaudSettings.bearerToken` field in CosmosDB
- Users must manually obtain and paste their token (extracted from Plaud web app cookies/headers)
- Token is re-used on every sync -- no refresh mechanism

**Request Headers:** The client mimics a Chrome browser with full `User-Agent`, `Referer: https://app.plaud.ai/`, `sec-ch-ua` headers, etc. This suggests the API is meant for the web app, not third-party integrations.

**Data Model -- `AudioFile`:**
```python
@dataclass
class AudioFile:
    id: str               # Plaud recording ID (used for deduplication)
    filename: str         # Human-readable name
    filesize: int         # Bytes
    filetype: str         # e.g., "opus" (though actually MP3)
    fullname: str         # Full filename with extension
    duration: int         # Duration in milliseconds
    start_time: int       # Unix timestamp in milliseconds
    end_time: int         # Unix timestamp in milliseconds
    timezone: int         # UTC offset in hours
    serial_number: str    # Device serial number
    is_trash: bool
    # ... other fields
```

**Key quirk:** Plaud `.opus` files are actually MP3 format. The client handles this by remapping the extension.

**Download flow:**
1. Call `/file/temp-url/{file_id}` to get a presigned S3 URL
2. Download via HTTP GET to a temp file
3. S3 URLs are method-specific (HEAD requests return 403)

---

## 3. Recording Download & Upload

### Download (`PlaudProcessor._download_recording`)

1. Create temp file with appropriate extension (opus -> mp3 remapping)
2. Get presigned S3 download URL from Plaud API
3. Check disk space (warn if < 500MB, but continue)
4. Stream download with `requests.get(stream=True)`, 8KB chunks
5. **5-second sleep between downloads** to avoid Plaud rate limiting
6. Return local file path

### Transcoding (`PlaudProcessor._transcode_to_mp3`)

Uses `ffmpeg-python` wrapper:
```python
ffmpeg.input(input_file)
    .output(output_file, acodec='libmp3lame', audio_bitrate='128k')
    .overwrite_output()
    .run(capture_stdout=True, capture_stderr=True)
```

Output: Standardized MP3 at 128kbps.

### Upload (`PlaudProcessor._upload_to_blob`)

1. Upload transcoded file to Azure Blob Storage at path `{user_id}/{recording_id}.mp3`
2. Generate SAS URL with 48-hour expiry (for Azure Speech Services to access)
3. Uses `BlobStorageClient` from shared library

### Recording Creation in CosmosDB

After upload, a `Recording` document is created/updated with:
- `type: "recording"` (required for queries)
- `source: "plaud"`
- `unique_filename: "{user_id}/{recording_id}.mp3"`
- `plaudMetadata`: Nested object with `plaudId`, `originalTimestamp`, `plaudFilename`, `plaudFileSize`, `plaudDuration`, `plaudFileType`, `syncedAt`
- `transcoding_status: "completed"`
- `transcription_status: "not_started"` (then updated to submitted)
- `testRunId`: If in test mode

---

## 4. Transcription Pipeline

### Submission (`PlaudProcessor._submit_transcription`)

Uses the auto-generated `azure_speech_client` package (from OpenAPI spec, Azure Speech Services v3.2).

**Configuration:**
```python
configuration.api_key["Ocp-Apim-Subscription-Key"] = speech_key
configuration.host = f"https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2"
```

**Transcription request:**
```python
TranscriptionProperties:
  punctuation_mode: "DictatedAndAutomatic"
  diarization_enabled: True
  diarization: DiarizationProperties(
    speakers: DiarizationSpeakersProperties(min_count=1, max_count=5)
  )

Transcription:
  display_name: "Transcription of {title}"
  locale: "en-US"
  content_urls: [blob_sas_url]  # 48-hour SAS token
```

**Submission method:** `api.transcriptions_create_with_http_info()` -- extracts transcription ID from the `location` response header.

### Polling (`TranscriptionPoller.check_and_update_transcription`)

For each recording with `transcription_job_status IN ('submitted', 'processing')`:

1. Call `api.transcriptions_get(transcription_job_id)`
2. Handle status:
   - `Succeeded`: Download transcript, parse, update records, trigger AI post-processing
   - `Failed`: Update recording status, track failure
   - `Running`: Update status to `processing`
   - `NotStarted`: Keep as `submitted`
3. Update `last_check_time` on every check

### Transcript Download (`TranscriptionPoller._download_transcript`)

1. Call `api.transcriptions_list_files(transcription_id)`
2. Paginate through results (custom `_paginate` generator handles the auto-generated client's lack of pagination support)
3. Find file with `kind == "Transcription"`
4. Download content via `content_url` (direct HTTP GET)
5. Return raw JSON string

### Transcript Parsing (`TranscriptionPoller._generate_diarized_transcript`)

Converts Azure Speech JSON format to human-readable diarized text:

**Input (Azure format):**
```json
{
  "recognizedPhrases": [
    {"speaker": 1, "nBest": [{"display": "Hello there."}]},
    {"speaker": 2, "nBest": [{"display": "Hi, how are you?"}]}
  ]
}
```

**Output:**
```
Speaker 1: Hello there.

Speaker 2: Hi, how are you?
```

Consecutive phrases from the same speaker are merged into a single paragraph.

### Data Storage After Completion

The `Transcription` document receives:
- `az_transcription_id`: Azure job ID
- `az_raw_transcription`: String representation of API response
- `transcript_json`: Raw JSON from Azure
- `diarized_transcript`: Human-readable text

The `Recording` document receives:
- `transcription_status: "completed"`
- `transcription_id`: Link to Transcription document
- `transcription_job_status: "completed"`
- `transcription_job_id: null` (cleared after completion)
- `token_count`: Denormalized from Transcription for fast frontend display

---

## 5. Speaker Diarization

Speaker diarization is handled **entirely by Azure Speech Services** during transcription. The service does not perform its own diarization.

**Configuration:** `min_count=1, max_count=5` speakers.

**Azure output format:** Each `recognizedPhrase` has a `speaker` field (integer 1-5), plus `offsetInTicks` and `durationInTicks` for timing.

The diarization output is used downstream by the Speaker Identification system (Phase B) to build per-speaker audio segments for embedding extraction.

---

## 6. Speaker Identification (ECAPA-TDNN)

This is a substantial ML-based feature that identifies speakers across recordings using voice embeddings.

### Architecture

```
Audio File (from Blob Storage)
    |
    v
EmbeddingEngine (ECAPA-TDNN via SpeechBrain)
    |
    v
Per-speaker centroid embeddings (L2-normalized)
    |
    v
Match against SpeakerProfileDB (cosine similarity)
    |
    v
auto (>=0.78) / suggest (>=0.68) / unknown (<0.68)
```

### EmbeddingEngine (`embedding_engine.py`)

- **Model:** `speechbrain/spkrec-ecapa-voxceleb` (ECAPA-TDNN trained on VoxCeleb)
- **Pre-cached in Docker image** at `/app/pretrained_models/spkrec-ecapa-voxceleb`
- **CPU-only** (torch==2.4.1+cpu, torchaudio==2.4.1+cpu)
- **Lazy-loaded** on first use to avoid ~800MB torch import cost when not needed

**Key methods:**
- `load_audio_mono_16k(path)`: Loads audio, converts MP3 via ffmpeg subprocess, resamples to 16kHz mono
- `slice_audio(wav, sr, start_s, end_s)`: Extract time slice from waveform
- `embedding_from_waveform(wav)`: Extract 192-dim embedding via `model.encode_batch()`
- `embeddings_for_segments(path, segments)`: Batch extraction with min/max duration filtering
- `merge_adjacent_segments(diarization)`: Merge consecutive same-speaker segments (gap <= 0.35s)

### SpeakerProcessor (`speaker_processor.py`)

**Processing pipeline for one recording:**

1. Parse diarization segments from `transcript_json` (Azure format: `offsetInTicks`, `durationInTicks`, `speaker`)
2. Merge adjacent segments for same speaker
3. Check existing `speaker_mapping` to skip:
   - `identificationStatus == "dismissed"`: Skip entirely
   - `manuallyVerified == true` without `useForTraining`: Skip
   - `manuallyVerified == true` with `useForTraining` but no `embedding`: Extract embedding only
4. Select top 15 longest segments per active speaker (minimum 2s duration)
5. Trim edges on long segments (>10s: trim 3s from each end)
6. Window to center 10s for very long segments
7. Download audio from Blob Storage to temp file
8. Extract embeddings per segment, build per-speaker centroid (L2-normalized mean)
9. Match each centroid against profile DB using `match_with_confidence()`
10. Handle duplicate auto-matches (same participant matched to two speakers): demote lower confidence one to "suggest"
11. Return results dict mapping speaker labels to identification results

**Confidence thresholds:**
- `AUTO_THRESHOLD = 0.78`: Auto-assign participant
- `SUGGEST_THRESHOLD = 0.68`: Suggest candidate, needs review
- `MIN_CANDIDATE_THRESHOLD = 0.40`: Minimum for showing in top candidates list

### SpeakerProfileDB (shared library: `speaker_profiles/profile_store.py`)

- Per-user profile database stored as JSON blob at `speaker-profiles/{userId}/profiles.json`
- Each profile: `participant_id`, `display_name`, `centroid` (192-dim), `n_samples`, `recording_ids`, `embedding_std`
- Centroid is running mean of all L2-normalized embeddings (keeps last 500)
- Loaded once per user per job run, saved once at end

### Re-rating (`job_executor._rerate_speakers_for_user`)

After profiles grow with new embeddings, existing suggest/unknown speakers may now match better:

1. Query recordings with `speaker_identification_status IN ('needs_review', 'completed')`
2. For each speaker mapping entry with status `suggest` or `unknown`:
   - Read stored `embedding` from the mapping
   - Re-match against current profiles using `match_with_confidence()`
   - Only upgrade (unknown->suggest, suggest->auto), never downgrade
   - Write audit trail to `identificationHistory`
3. Update recording status to `completed` if all speakers are now resolved

### Speaker Mapping Data Structure (stored in Transcription.speaker_mapping)

```json
{
  "Speaker 1": {
    "participantId": "uuid",
    "confidence": 0.85,
    "manuallyVerified": false,
    "identificationStatus": "auto",
    "similarity": 0.85,
    "topCandidates": [
      {"participantId": "uuid", "displayName": "John", "similarity": 0.85},
      {"participantId": "uuid2", "displayName": "Jane", "similarity": 0.42}
    ],
    "identifiedAt": "2025-01-01T00:00:00",
    "embedding": [0.1, 0.2, ...],  // 192 floats
    "identificationHistory": [
      {
        "timestamp": "2025-01-01T00:00:00",
        "action": "auto_assigned",
        "source": "worker",
        "participantId": "uuid",
        "similarity": 0.85,
        "candidatesPresented": [...]
      }
    ]
  }
}
```

---

## 7. AI Post-Processing

### When It Runs

After a transcription completes successfully (in `TranscriptionPoller._handle_completed_transcription`, Step 8), if `settings.ai_enabled` is true.

### Implementation

- Uses Azure OpenAI **mini model** (gpt-4o-mini) via `get_openai_client("mini")`
- Async call: `asyncio.run(self._generate_title_and_description(transcript_text))`
- Uses `AzureOpenAIClient.send_prompt_async()` from shared library

### Prompt (`prompts.yaml`)

Single prompt generates both title and description:

```
Analyze this audio transcript and generate both a title and description.

For the title:
- Maximum 60 characters
- Concise and descriptive
- Focus on the main topic or purpose
- No quotes around the title

For the description:
- 1-2 sentences summarizing the main content
- Informative about what was discussed or accomplished
- Concise but comprehensive

IMPORTANT: Return only valid JSON with no additional text.

Required format:
{"title": "...", "description": "..."}

=== BEGIN AUDIO TRANSCRIPT ===
__TRANSCRIPT__
=== END AUDIO TRANSCRIPT ===

[prompt is repeated after transcript -- appears to be a bug/redundancy]
```

**Note:** The prompt text is duplicated -- the instructions appear both before and after the transcript placeholder. This is wasteful of tokens.

### Response Parsing

Extracts JSON from response by finding first `{` and last `}`. Parses and validates that both `title` and `description` are non-empty.

### Result

Updates the Recording document with:
- `recording.title = ai_content['title']`
- `recording.description = ai_content['description']`

---

## 8. Job Execution & Locking

### Lock Mechanism (shared library: `cosmos/locks_handler.py`)

Uses CosmosDB document creation as a mutex:

**Lock document:**
```json
{
  "id": "plaud-sync-lock",
  "ownerId": "job-uuid",
  "acquiredAt": "2025-01-01T00:00:00",
  "ttl": 5400,
  "partitionKey": "locks"
}
```

**Acquire flow:**
1. Attempt to create lock document (CosmosDB guarantees uniqueness on `id`)
2. If `CosmosResourceExistsError`:
   - Read existing lock
   - If expired (acquiredAt + TTL < now): force-delete and retry
   - If still valid: return False (another job is running)
3. If lock was deleted between attempts (race): retry once

**Lock TTL:** 5400 seconds (90 minutes) -- set in `job_executor.py`, not in the lock handler.

**Release:** Read lock, verify ownership, delete document.

**Important:** The CosmosDB `ttl` field provides automatic deletion by Cosmos, but the handler also implements manual expiry checking as a belt-and-suspenders approach.

### Job Execution Tracking

Each job creates a `JobExecution` document in CosmosDB:

```python
JobExecution(
    id=job_id,         # UUID
    status="running",  # -> "completed" | "failed"
    triggerSource="scheduled" | "manual",
    startTime=...,
    endTime=...,
    logs=[],           # Array of JobLogEntry
    stats=JobExecutionStats(...),
    usersProcessed=[],
    errorMessage=None,
    ttl=2592000,       # 30 days
    partitionKey="job_execution",
    testRunId=None
)
```

**JobExecutionStats tracks:**
- `transcriptions_checked`, `transcriptions_completed`
- `recordings_found`, `recordings_downloaded`, `recordings_transcoded`
- `recordings_uploaded`, `recordings_skipped`, `transcriptions_submitted`
- `chunks_created`, `errors`

**Logging:** The `JobLogger` captures all logs in an in-memory deque (max 1000 entries) and writes them to the JobExecution document at completion.

---

## 9. Chunking

### When Triggered

Files are chunked if **either** condition is met:
- File size > **300 MB**
- Duration > **7200 seconds** (2 hours)

Detection uses `ffmpeg.probe()` for duration and `os.path.getsize()` for file size.

### Chunk Parameters

- **Max chunk duration:** 5400 seconds (1.5 hours)
- **Max chunk size:** 200 MB (not directly enforced -- chunking is time-based)
- **Number of chunks:** `ceil(total_duration / chunk_duration)`, minimum 2

### Splitting

Uses ffmpeg with `-ss` (start) and `-t` (duration) flags, with `codec='copy'` (no re-encoding during split).

Each chunk is then individually transcoded to MP3 128kbps.

### Chunk Recordings

Each chunk becomes an independent Recording document with:
- `chunkGroupId`: UUID linking all chunks from the same source file
- `title`: `"{original_filename} - Part X of Y"`
- `recorded_timestamp`: Offset by chunk position
- `duration`: `CHUNK_DURATION_SECONDS` (5400s -- note: always the max, not actual duration)

### Atomic Cleanup

If any chunk in a group fails:
1. Query all recordings with the same `chunkGroupId`
2. Delete all their blobs from storage
3. Delete all their CosmosDB records
4. Re-raise exception to stop processing remaining chunks

---

## 10. Error Handling & Retry Logic

### Failure Tracking

Each recording tracks `processing_failure_count` and `last_failure_message`.

### Manual Review Threshold

After **3 failures** (`MAX_PROCESSING_FAILURES`), the recording is:
1. Marked with `needs_manual_review = True`
2. A `ManualReviewItem` document is created/updated in CosmosDB:
   ```json
   {
     "id": "uuid",
     "recordingId": "...",
     "userId": "...",
     "recordingTitle": "...",
     "failureCount": 3,
     "lastError": "...",
     "failureHistory": [
       {"timestamp": "...", "error": "...", "step": "transcription_failed", "attemptNumber": 3}
     ],
     "status": "pending",
     "partitionKey": "manual_review"
   }
   ```

### Failure Steps Tracked

- `transcription_failed`: Azure Speech Services returned Failed status
- `download_transcript`: Could not download completed transcript
- `handle_completion`: Error during post-processing

### Atomic Cleanup for Plaud Processing

**Single recording failure:**
- If recording was created in CosmosDB but subsequent steps fail:
  - Delete blob (if uploaded)
  - Delete recording from CosmosDB
- Transcription submission failure is **non-fatal** (recording kept for manual retry)

**Chunked recording failure:**
- If any chunk fails, all chunks in the group are cleaned up

### What is NOT retried automatically

- Failed Plaud API calls (no retry)
- Failed downloads (no retry)
- Failed transcriptions (tracked for manual review after 3 failures, but no auto-retry)
- The 15-minute cron cycle provides implicit retry -- pending transcriptions are re-checked each cycle

### Per-User Error Isolation

If processing one user fails with an exception, the error is caught and the next user is processed. The error increments `stats.errors`.

---

## 11. Deleted Items Blocking

### Purpose

Prevents re-syncing recordings that users have deliberately deleted from QuickScribe.

### Mechanism

The `DeletedItemsHandler` (shared library) maintains a per-user document:

```json
{
  "id": "deleted_items_{userId}",
  "type": "deleted_items",
  "userId": "...",
  "items": {
    "plaud_recording": ["plaud-id-1", "plaud-id-2"]
  },
  "partitionKey": "deleted_items"
}
```

### Integration in Sync Flow

```python
existing_plaud_ids = recording_handler.get_user_plaud_ids(user.id)
deleted_plaud_ids = deleted_items_handler.get_deleted_plaud_ids(user.id)
all_blocked_ids = existing_plaud_ids + deleted_plaud_ids
processor.set_existing_plaud_ids(all_blocked_ids)
```

New recordings from Plaud are filtered: `[r for r in all_recordings if r.id not in all_blocked_ids]`

The `PlaudProcessor` also has a safety check inside `process_recording()` as a belt-and-suspenders guard.

---

## 12. Configuration & Scheduling

### Environment Variables

**Job execution control:**
| Variable | Purpose | Default |
|----------|---------|---------|
| `TRIGGER_SOURCE` | "scheduled" or "manual" | "scheduled" |
| `TEST_RUN_ID` | Test mode identifier | None |
| `MAX_RECORDINGS` | Limit recordings per user | None (unlimited) |
| `MAX_SPEAKER_ID_PER_USER` | Limit speaker ID backlog per user | 10 |

**Service configuration (from shared library via pydantic-settings):**
| Variable | Purpose |
|----------|---------|
| `AZURE_COSMOS_ENDPOINT` | CosmosDB endpoint |
| `AZURE_COSMOS_KEY` | CosmosDB key |
| `AZURE_COSMOS_DATABASE_NAME` | Database name (default: "quickscribe") |
| `AZURE_COSMOS_CONTAINER_NAME` | Container name (default: "recordings") |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob Storage connection string |
| `AZURE_STORAGE_CONTAINER_NAME` | Audio container (default: "audio-files") |
| `SPEECH_SERVICES_SUBSCRIPTION_KEY` | Azure Speech key |
| `SPEECH_SERVICES_REGION` | Azure Speech region |
| `AZURE_OPENAI_API_ENDPOINT` | OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | OpenAI key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Standard model deployment |
| `AZURE_OPENAI_MINI_DEPLOYMENT_NAME` | Mini model deployment |
| `AI_ENABLED` | Feature flag for AI post-processing |

### Feature Flags (from `QuickScribeSettings`)

- `ai_enabled`: Controls AI title/description generation
- `cosmos_enabled`: CosmosDB operations
- `blob_storage_enabled`: Blob operations
- `speech_services_enabled`: Transcription
- `plaud_enabled`: Plaud API integration

### Scheduling

Managed via Azure Container Apps Job cron expression: `*/15 * * * *`

Container Apps Job settings:
- `--replica-timeout 5400` (90 min max runtime)
- `--replica-retry-limit 3` (Azure-level retry)
- `--parallelism 1` (single replica)
- `--replica-completion-count 1`

---

## 13. Utility Scripts

All in `plaud_sync_service/scripts/`.

### `test_plaud_sync.py`
Runs the full sync job locally with a test run ID for cleanup tracking.
- `--max-recordings N`: Limit recordings per user
- `--user-id ID`: Process specific user
- `--check-transcriptions-only`: Skip Plaud download phase

### `cleanup_test_run.py`
Cleans up all resources created during a test run by querying for documents with matching `testRunId`.
- Deletes transcriptions, recordings, blobs, job executions, manual review items
- `--dry-run`: Preview mode
- `--latest`: Clean most recent test
- `--all`: Clean all test data
- `--list`: List test run IDs

### `clear_locks.py`
Force-deletes the sync lock document from CosmosDB. Only works in development mode.

### `view_jobs.py`
Interactive viewer for job execution history. Color-coded status, shows stats, allows drilling into job details and logs.

---

## 14. Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `azure-cosmos` | >=4.5.0 | CosmosDB operations |
| `azure-storage-blob` | >=12.19.0 | Blob Storage |
| `azure-storage-queue` | >=12.8.0 | Queue (unused in current code) |
| `azure-identity` | >=1.15.0 | Azure auth |
| `ffmpeg-python` | >=0.2.0 | Audio transcoding/splitting |
| `requests` | >=2.31.0 | HTTP (Plaud API, transcript download) |
| `aiohttp` | >=3.9.0 | Async HTTP (OpenAI) |
| `PyYAML` | >=6.0 | Prompt templates |
| `opencensus-ext-azure` | >=1.1.9 | Azure monitoring |
| `numpy` | >=1.24.0 | Embedding math |
| `torch` | ==2.4.1+cpu | ML framework (~800MB) |
| `torchaudio` | ==2.4.1+cpu | Audio loading |
| `speechbrain` | ==1.0.3 | ECAPA-TDNN model |
| `soundfile` | - | Audio I/O for speechbrain |
| `huggingface_hub` | ==0.24.7 | Model download |

### System Dependencies
- **FFmpeg**: Static binary copied from `mwader/static-ffmpeg:7.1` Docker image
- **libsndfile1**: Audio file I/O library

### External Services

| Service | Usage |
|---------|-------|
| Azure CosmosDB | All data storage (recordings, transcriptions, users, jobs, locks, deleted items) |
| Azure Blob Storage | Audio files, speaker profiles |
| Azure Speech Services v3.2 | Batch transcription with diarization |
| Azure OpenAI | Title/description generation (gpt-4o-mini) |
| Plaud API (api.plaud.ai) | Recording list and download |

### Internal Dependencies
- `shared_quickscribe_py`: Shared Python library (editable install)
- `azure_speech_client`: Auto-generated Azure Speech Services Python client from OpenAPI spec

---

## 15. Technical Debt & Complexity Analysis

### Massive Docker Image

The Docker image includes PyTorch (~800MB), SpeechBrain (~200MB), and ECAPA-TDNN model weights (~100MB) for speaker identification. Total image is likely >1.5GB. This means:
- Slow cold starts
- High memory usage (4 GiB allocated)
- 2 CPU cores allocated

For a small-scale app, this is significant infrastructure cost.

### Over-Engineered for Scale

The service was designed for multi-user, multi-recording, concurrent-safe processing. For a small-scale personal app:
- **CosmosDB-based distributed locking** is overkill when there is only one instance
- **Manual review queue** adds complexity but there is no admin UI to process it
- **Chunk group atomic cleanup** handles an edge case (>2hr recordings) that may rarely occur
- **Test run tracking with cleanup scripts** suggests testing is manual and complex

### Speaker Identification Complexity

The speaker ID system is the most complex part:
- Requires PyTorch + SpeechBrain (heavy ML dependencies)
- Downloads audio files from Blob Storage for embedding extraction
- Maintains per-user profile databases in Blob Storage
- Has three processing phases (identify, re-rate, embedding-only for training)
- Complex status management (auto/suggest/unknown/dismissed/verified)
- Duplicate auto-match detection
- Audit trail in `identificationHistory`

### Azure Speech Client Code Bloat

The `azure_speech/python-client/` directory contains an auto-generated Swagger client with ~120 files. Only a tiny fraction is used:
- `CustomSpeechTranscriptionsApi` (create, get, list_files)
- A handful of model classes
- Custom pagination workaround

### Code Duplication

- Azure Speech API client initialization is duplicated in both `TranscriptionPoller.__init__` and `PlaudProcessor.__init__`
- The `prompts.yaml` file has the prompt text duplicated within itself (instructions appear before and after the transcript placeholder)
- Lock TTL is hardcoded in `job_executor.py` rather than being in config

### Mixed Async/Sync

The service is fundamentally synchronous, but the AI post-processing uses `asyncio.run()` to call the async OpenAI client. This is awkward and could cause issues if called from an existing event loop.

### Sequential Processing

- Users are processed sequentially
- Recordings per user are processed sequentially
- Chunks are processed sequentially
- No parallelism despite multiple users and recordings

### Missing Features / Gaps

- No incremental sync (fetches ALL recordings from Plaud every time, with limit=99999)
- No token caching for Plaud API
- No streaming upload (download to disk, then upload to blob)
- No retry with backoff for transient failures
- `azure-storage-queue` is in requirements but appears unused
- Lock TTL of 90 minutes is generous; typical jobs should complete in minutes
- `ManualReviewItem` documents are created but there is no UI or process to resolve them
- The `view_jobs.py` script in `src/` is duplicated in `scripts/`

### Docker Build Complexity

The Makefile creates a temporary deployment directory, copies files from multiple locations (shared library, azure_speech client, source), builds the Docker image, then cleans up. This is necessary because the Docker context needs files from outside the service directory.

### Single CosmosDB Container

All document types (recordings, users, transcriptions, jobs, locks, deleted items, manual reviews) share a single CosmosDB container. Partition keys vary by type. This simplifies infrastructure but makes queries more complex and cross-partition queries necessary.

### Hardcoded Values

- Plaud API base URL: `https://api.plaud.ai`
- Transcription locale: `en-US` (no multi-language support)
- Speaker diarization: 1-5 speakers (hardcoded)
- SAS URL expiry: 48 hours
- Download throttle: 5 seconds
- Max log entries: 1000 per job
- Embedding dimension: 192 (ECAPA-TDNN output size)
- Auto/suggest thresholds: 0.78/0.68

### Potential Data Integrity Issues

- Recording creation is the "point of no return" -- if subsequent steps fail, cleanup is attempted but failures during cleanup are only logged, not retried
- The chunk duration in the Recording document is always set to `CHUNK_DURATION_SECONDS` (5400s) rather than the actual chunk duration (the last chunk will be shorter)
- `transcription_job_id` is set to `None` after completion, losing the Azure reference
