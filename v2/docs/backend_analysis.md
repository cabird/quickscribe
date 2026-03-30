# QuickScribe Backend -- Comprehensive Functionality Analysis

**Purpose:** This document captures every piece of functionality in the current Flask backend to inform a full rewrite. It covers routes, auth, database patterns, AI features, file handling, configuration, dependencies, and technical debt.

**Current version:** 0.1.75
**Framework:** Flask 3.0.3 / Python 3.11
**Source:** `backend/src/`

---

## Table of Contents

1. [Application Structure](#1-application-structure)
2. [Authentication & Authorization](#2-authentication--authorization)
3. [API Routes -- Complete Reference](#3-api-routes----complete-reference)
4. [Database (CosmosDB) Interactions](#4-database-cosmosdb-interactions)
5. [AI Features](#5-ai-features)
6. [File Handling & Blob Storage](#6-file-handling--blob-storage)
7. [Configuration & Settings](#7-configuration--settings)
8. [Dependencies](#8-dependencies)
9. [Technical Debt & Simplification Opportunities](#9-technical-debt--simplification-opportunities)

---

## 1. Application Structure

### Entry Point: `app.py`

- Uses **application factory pattern** (`create_app()`)
- Initializes BlobServiceClient and CosmosClient at startup (module-level globals)
- Registers five blueprints:
  - `api_bp` at `/api`
  - `ai_bp` at `/api/ai`
  - `local_bp` at `/api/local`
  - `admin_bp` at `/api/admin`
  - `participant_bp` at `/api/participants`
- Serves built frontend from `frontend-dist/` as static files
- SPA catch-all route returns `index.html` for client-side routing
- CORS: allows `localhost:3000` in dev, open in production
- Runs on port 5050 locally, port 8000 in Docker (gunicorn)

### Module Layout

| Module | Purpose |
|--------|---------|
| `app.py` | Flask app factory, static serving, auth routes |
| `auth.py` | Azure AD JWT validation (JWKS fetch, token decode) |
| `user_util.py` | `get_current_user()`, `require_auth` decorator |
| `config.py` | Backward-compat wrapper around shared settings |
| `llms.py` | Azure OpenAI integration (sync + async) |
| `ai_postprocessing.py` | Title/description generation, speaker inference coordination |
| `blob_util.py` | Blob storage wrapper (upload, download, SAS URLs, queue) |
| `util.py` | Audio duration extraction, text utilities |
| `logging_config.py` | JSON logging, Azure App Insights integration |
| `plaud_sync_trigger.py` | Azure Container Apps Job trigger for Plaud sync |
| `api_version.py` | Single constant: `API_VERSION = '0.1.75'` |
| `routes/api.py` | Core CRUD, upload, tags, speaker management (~2080 lines) |
| `routes/ai_routes.py` | AI analysis, speaker inference, chat |
| `routes/admin.py` | Admin dashboard, data management, jobs |
| `routes/local_routes.py` | Dev-only test user management |
| `routes/participant_routes.py` | Participant CRUD, search, merge |

---

## 2. Authentication & Authorization

### Mechanism

Azure AD (Entra ID) JWT token validation. The frontend (React SPA) acquires tokens via MSAL and sends them as `Authorization: Bearer <token>`.

### Token Validation (`auth.py`)

1. Extract Bearer token from `Authorization` header
2. Decode JWT header to get `kid` (key ID)
3. Fetch JWKS from `https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys`
   - Cached for 24 hours with thread-safe double-check locking
   - Falls back to stale cache (up to 7 days) if fetch fails
4. Validate signature (RS256), issuer, audience (client_id + `api://client_id`), expiration

### User Resolution (`user_util.py`)

Two modes controlled by `AUTH_MODE` env var:

**Disabled mode** (local dev, `AUTH_MODE=disabled` + `USE_DEV_USER_BYPASS=true`):
- Checks Flask session for `local_user_id` (set via `/api/local/login`)
- Falls back to default user "cbird" looked up by name

**Enabled mode** (production, `AUTH_MODE=enabled`):
1. Validate JWT token
2. Extract `oid` (Azure AD Object ID) as user identity
3. Look up user by `azure_oid`
4. If not found, try matching by email and link the Azure OID
5. If still not found, auto-provision a new User with `id = "user-{oid}"`

### `require_auth` Decorator

A `functools.wraps` decorator that calls `get_current_user()` and returns 401 if `None`. Applied to almost all endpoints (except health, version, transcoding_callback, and local dev routes which have their own guards).

### Authorization Gaps

- **No ownership checks on several endpoints**: `GET /api/user/<user_id>`, `GET /api/users`, `PUT /api/user/<user_id>`, `DELETE /api/delete_user/<user_id>`, `GET /api/user/<user_id>/recordings`, `GET /api/user/<user_id>/transcriptions` -- any authenticated user can access any other user's data
- **Admin routes have no real admin check**: `require_admin` is just an alias for `require_auth` with a comment "we'll add proper checks later"
- **Transcoding callback is unauthenticated** (by design -- uses callback token instead)

---

## 3. API Routes -- Complete Reference

### Blueprint: `api_bp` (`/api`)

#### Health & Metadata

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/get_api_version` | No | Returns `{ version: "0.1.75" }` |
| GET | `/api/health` | No | Returns status, version, timestamp, service name |

#### User Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/me` | Yes | Get current user's profile. Returns `User.model_dump()` |
| PUT | `/api/me/plaud-settings` | Yes | Update current user's Plaud settings (enableSync, bearerToken) |
| GET | `/api/user/<user_id>` | Yes | Get any user by ID (no ownership check) |
| GET | `/api/users` | Yes | List all users (no admin check) |
| POST | `/api/users` | Yes | Get users by list of IDs. Body: `{ ids: [...] }` |
| PUT | `/api/user/<user_id>` | Yes | Update any user (no ownership check, sets arbitrary fields) |
| GET | `/api/delete_user/<user_id>` | Yes | Delete any user (uses GET method, no ownership check) |

#### Recording Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/recording/<id>` | Yes | Get single recording. Returns `Recording.model_dump()` |
| GET | `/api/recordings` | Yes | List current user's recordings with enriched speaker names. Uses optimized `get_recording_summaries()` + batch participant lookup |
| POST | `/api/recordings` | Yes | Get recordings by list of IDs. Body: `{ ids: [...] }` |
| PUT | `/api/recording/<id>` | Yes | Update recording (sets arbitrary fields via `setattr`) |
| GET | `/api/delete_recording/<id>` | Yes | Delete recording. If Plaud source, adds plaudId to deleted_items to prevent re-sync |
| GET | `/api/recording/<id>/audio-url` | Yes | Generate 24h SAS URL for audio streaming. Checks ownership. Handles blob_name or user_id/filename patterns |
| GET | `/api/transcoding_status/<id>` | Yes | Get transcoding status fields for a recording |

#### Transcription Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/transcription/<id>` | Yes | Get transcription with enriched speaker_mapping (participant displayNames resolved). Checks ownership |
| POST | `/api/transcriptions` | Yes | Get transcriptions by list of IDs. Body: `{ ids: [...] }` |
| PUT | `/api/transcription/<id>` | Yes | Update transcription (sets arbitrary fields) |
| GET | `/api/delete_transcription/<id>` | Yes | Delete transcription |
| GET | `/api/user/<user_id>/transcriptions` | Yes | Get all transcriptions for a user (no ownership check) |
| GET | `/api/user/<user_id>/recordings` | Yes | Get all recordings for a user (no ownership check) |

#### File Upload

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/upload` | Yes | Upload audio file. Saves to /tmp, uploads to blob, creates Recording, queues transcoding job. Returns recording_id and transcoding_token |
| POST | `/api/upload_from_ios_share` | Yes | Same as upload but expects `audio_file` form field instead of `file` |

**Upload flow:**
1. Save uploaded file to `/tmp/<uuid>.<ext>`
2. Upload original to Azure Blob Storage
3. Create Recording in CosmosDB (status: `queued`)
4. Send message to Azure Storage Queue with source blob, target blob (.mp3), recording_id, callbacks
5. Delete temp file
6. Return recording_id

#### Transcoding Callback

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/transcoding_callback` | No (token) | Webhook from transcoding container. Validates callback_token against recording. Handles `in_progress`, `completed` (triggers AI postprocessing), `failed` statuses |

#### AI Postprocessing

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/recording/<id>/postprocess` | Yes | Manually trigger AI postprocessing (title + description generation). Checks ownership and transcription_status == completed |

#### Speaker Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/recording/<id>/update_speakers` | Yes | Update speaker mapping. Accepts both legacy string format and new participant format with participantId/displayName |
| POST | `/api/transcription/<id>/speaker` | Yes | Update single speaker assignment. Body: `{ speaker_label, participant_id, manually_verified }`. Merges into existing mapping, adds audit history |

#### Speaker Identification Review System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/speaker-reviews` | Yes | Get recordings with pending speaker ID reviews. Filters by identificationStatus (suggest/unknown). Supports pagination |
| GET | `/api/speaker-audit` | Yes | Get flattened audit trail of all speaker ID actions across recordings. Paginated |
| POST | `/api/transcription/<id>/speaker/<label>/accept` | Yes | Accept speaker suggestion. Copies suggestedParticipantId to participantId, sets manuallyVerified. Optional `useForTraining` to update voice profile |
| POST | `/api/transcription/<id>/speaker/<label>/reject` | Yes | Reject suggestion. Clears suggested, sets status to 'unknown' |
| POST | `/api/transcription/<id>/speaker/<label>/dismiss` | Yes | Dismiss speaker permanently (sets status to 'dismissed') |
| POST | `/api/transcription/<id>/speaker/<label>/reassign` | Yes | Reassign speaker to different participant. Body: `{ participantId, useForTraining }` |
| POST | `/api/transcription/<id>/speaker/<label>/training` | Yes | Toggle training approval. Body: `{ useForTraining: bool }`. When enabling, triggers `speaker_profile_updater.update_profile_from_mapping()` |
| POST | `/api/transcription/<id>/reidentify` | Yes | Re-trigger speaker ID. Clears auto/suggest data (keeps manually verified), resets recording status to 'not_started' |
| POST | `/api/speaker-profiles/rebuild` | Yes | Rebuild all speaker profiles from verified mappings |

#### Tags

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/tags/get` | Yes | Get current user's tags. Tags are stored on the User document |
| POST | `/api/tags/create` | Yes | Create tag. Body: `{ name, color }`. Validates hex color, max 32 chars |
| POST | `/api/tags/update` | Yes | Update tag. Body: `{ tagId, name?, color? }` |
| GET | `/api/tags/delete/<tag_id>` | Yes | Delete tag (uses GET method) |
| GET | `/api/recordings/<id>/add_tag/<tag_id>` | Yes | Add tag to recording (uses GET method). Validates ownership of both recording and tag |
| GET | `/api/recordings/<id>/remove_tag/<tag_id>` | Yes | Remove tag from recording (uses GET method) |

### Blueprint: `ai_bp` (`/api/ai`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/ai/test` | No | Health check, returns `{ status: "up" }` |
| GET | `/api/ai/get_speaker_summaries/<transcription_id>` | Yes | Normalizes diarized transcript to "Speaker 1", "Speaker 2" etc., sends to LLM for identifying characteristics. Returns `{ "Speaker 1": "summary...", ... }` |
| GET | `/api/ai/infer_speaker_names/<transcription_id>` | Yes | LLM infers actual names from transcript context. Updates transcription with speaker_mapping and rewritten diarized_transcript. Currently always allows re-inference (TODO guard commented out) |
| GET | `/api/ai/analysis-types` | Yes | Get all analysis types (built-in + user custom) |
| POST | `/api/ai/analysis-types` | Yes | Create custom analysis type. Body: `CreateAnalysisTypeRequest` (name, title, shortTitle (max 12), description, icon, prompt) |
| PUT | `/api/ai/analysis-types/<id>` | Yes | Update custom analysis type. Allowed fields: title, shortTitle, description, icon, prompt, name |
| DELETE | `/api/ai/analysis-types/<id>` | Yes | Delete custom analysis type (user can only delete own) |
| POST | `/api/ai/execute-analysis` | Yes | Run analysis on transcription. Body: `{ transcriptionId, analysisTypeId, customPrompt? }`. Replaces `{transcript}` in prompt template. Stores result in `transcription.analysisResults[]`. Records timing and token usage |
| POST | `/api/ai/chat` | Yes | Chat with transcript context. Accepts full message history (system/user/assistant). Supports single or multiple transcription IDs. Returns AI response with usage stats. Error handling for rate limits, content filter, token limits |

**Chat request shape:**
```json
{
  "transcription_id": "uuid",       // OR
  "transcription_ids": ["uuid1", "uuid2"],
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Chat response shape:**
```json
{
  "message": "AI response text",
  "usage": { "promptTokens": 1250, "completionTokens": 45, "totalTokens": 1295 },
  "responseTimeMs": 1450
}
```

### Blueprint: `admin_bp` (`/api/admin`)

All routes require `@require_auth` + `@require_admin` (which currently just equals `@require_auth`).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/admin/overview` | Admin | Entity counts, statistics (recordings with transcriptions, in-progress, failed), recent activity |
| GET | `/api/admin/users` | Admin | All users with recording counts, tag counts, plaud settings status |
| GET | `/api/admin/recordings` | Admin | All recordings with user names, durations, statuses |
| GET | `/api/admin/transcriptions` | Admin | All transcriptions with recording titles, text snippets, analysis counts |
| GET | `/api/admin/tags` | Admin | All tags across users with usage counts |
| GET | `/api/admin/analysis-types` | Admin | All analysis types with usage counts |
| GET | `/api/admin/users/<id>` | Admin | User detail with recordings list and tags |
| GET | `/api/admin/recordings/<id>` | Admin | Recording detail with user info, transcription summary, tags |
| GET | `/api/admin/transcriptions/<id>` | Admin | Transcription detail with recording info, analysis results |
| GET | `/api/admin/users/<id>/related/<type>` | Admin | Get user's related entities (recordings or tags) |
| GET | `/api/admin/recordings/<id>/related/<type>` | Admin | Get recording's related entities (transcription or tags) |
| POST | `/api/admin/integrity-check` | Admin | Check for orphaned recordings, transcriptions, broken references, missing tags |
| DELETE | `/api/admin/users/<id>` | Admin | Cascade delete user + all recordings + transcriptions |
| DELETE | `/api/admin/recordings/<id>` | Admin | Delete recording + transcription |
| POST | `/api/admin/bulk-operations` | Admin | Bulk delete recordings or users. Body: `{ operation, entity_type, entity_ids }` |
| GET | `/api/admin/export` | Admin | Export all data as JSON. Query param: `?types=users,recordings,transcriptions,analysis_types` |
| GET | `/api/admin/search` | Admin | Global search across users, recordings, tags by text match |
| GET | `/api/admin/jobs` | Admin | Paginated job executions with filtering (status, trigger_source, user_id, date range, min_duration, has_activity). Supports sorting |
| GET | `/api/admin/jobs/<id>` | Admin | Full job execution detail including logs |
| POST | `/api/admin/plaud-sync/trigger` | Admin | Manually trigger Plaud sync Container Apps Job |
| GET | `/api/admin/plaud-sync/status` | Admin | Get Plaud sync job provisioning state |

### Blueprint: `local_bp` (`/api/local`)

All routes gated by `USE_DEV_USER_BYPASS` env var. Not deployed to production.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/local/users` | DevOnly | List test users |
| POST | `/api/local/login` | DevOnly | Set session user. Body: `{ user_id }` |
| POST | `/api/local/reset-user/<id>` | DevOnly | Delete all data for test user (recordings, transcriptions, blobs, plaud settings) |
| POST | `/api/local/create_test_user` | DevOnly | Create test user. Body: `{ name, email }` |
| POST | `/api/local/delete_test_user/<id>` | DevOnly | Delete test user and all associated data |
| POST | `/api/local/create_dummy_recording` | DevOnly | Create fake recording for testing |

### Blueprint: `participant_bp` (`/api/participants`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/participants` | Yes | Get all participants for current user |
| GET | `/api/participants/<id>` | Yes | Get single participant |
| POST | `/api/participants` | Yes | Create participant. Required: `displayName`. Optional: firstName, lastName, email, role, organization, relationshipToUser, notes, aliases |
| PUT | `/api/participants/<id>` | Yes | Update participant fields |
| DELETE | `/api/participants/<id>` | Yes | Delete participant (TODO: cleanup references in recordings/transcriptions) |
| GET | `/api/participants/search?name=X&fuzzy=true` | Yes | Search participants by name with optional fuzzy matching |
| POST | `/api/participants/<id>/merge/<other_id>` | Yes | Merge two participants. Keeps first, deletes second. Combines aliases, notes, timestamps. Body: optional `merge_fields` overrides |
| POST | `/api/participants/<id>/update_last_seen` | Yes | Update lastSeen timestamp. Body: optional `{ timestamp }` |
| GET | `/api/participants/<id>/recordings?limit=5&offset=0` | Yes | Get recordings where participant appears (via transcription speaker_mapping). Paginated |

### Non-Blueprint Routes (registered in `app.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/login` | No | Initiates OAuth login flow |
| GET | `/auth/callback` | No | OAuth callback handler |
| GET | `/` | No | Serves `index.html` |
| GET | `/<path:path>` | No | SPA catch-all. Returns static files if they exist, otherwise `index.html` |

---

## 4. Database (CosmosDB) Interactions

### Containers

| Container | Partition Key | Document Types | Purpose |
|-----------|---------------|----------------|---------|
| `recordings` | `userId` | Recording | Audio recording metadata |
| `users` | `id` | User | User profiles with tags embedded |
| `transcriptions` | `userId` | Transcription | Transcript text, speaker_mapping, analysisResults |
| `job_executions` | `partitionKey` | JobExecution | Plaud sync job logs (TTL: 30 days) |
| `deleted_items` | `userId` | DeletedItems | Soft-delete tracking to prevent re-sync |
| `participants` | `userId` | Participant | Speaker/person profiles |
| `analysis_types` | `partitionKey` | AnalysisType | "global" for built-in, userId for custom |
| `sync_progress` | `partitionKey` | SyncProgress | Plaud sync operation tracking |

### Handler Pattern

All database access goes through handler classes from `shared_quickscribe_py.cosmos`:

```python
from shared_quickscribe_py.cosmos import get_recording_handler, get_transcription_handler
handler = get_recording_handler()
recording = handler.get_recording(recording_id)
handler.update_recording(recording)
```

Handlers are obtained via `get_*_handler()` factory functions. They appear to be request-scoped singletons (created once per request or module import).

### Key Data Models (from `shared/Models.ts`)

**User**: id, name, email, role, azure_oid, plaudSettings (embedded), tags[] (embedded), is_test_user, partitionKey

**Recording**: id, user_id, original_filename, unique_filename, title, description, duration, recorded_timestamp, upload_timestamp, source ("upload"|"plaud"|"stream"), transcription_status, transcription_id, transcoding_status, transcoding_token, plaudMetadata (embedded), tagIds[], speaker_identification_status, partitionKey

**Transcription**: id, user_id, recording_id, diarized_transcript (string), text (string), transcript_json, az_raw_transcription, token_count, speaker_mapping (dict of SpeakerMappingEntry), analysisResults[] (embedded), partitionKey

**SpeakerMappingEntry**: participantId, confidence, manuallyVerified, identificationStatus, similarity, suggestedParticipantId, topCandidates[], identifiedAt, useForTraining, identificationHistory[], embedding (internal, stripped from API responses)

**Participant**: id, userId, firstName, lastName, displayName, aliases[], email, role, organization, relationshipToUser, notes, isUser, firstSeen, lastSeen, partitionKey

**AnalysisType**: id, name, title, shortTitle (max 12 chars), description, icon, prompt (template with `{transcript}`), userId, isActive, isBuiltIn, partitionKey ("global" or userId)

**AnalysisResult** (embedded in Transcription): analysisType, analysisTypeId, content, createdAt, status, errorMessage, llmResponseTimeMs, promptTokens, responseTokens

**Tag** (embedded in User): id, name, color (hex)

### Query Patterns

- Most queries go through handler methods that abstract CosmosDB SQL queries
- `list_recordings` uses an optimized `get_recording_summaries()` that returns lightweight projections
- Speaker name enrichment for recording lists uses `get_speaker_mappings_for_user()` -- fetches only recording_id and speaker_mapping columns (not full transcript text)
- Participant displayNames are resolved at query time (enrichment pattern in `enrich_transcription_with_participants`)
- Speaker reviews and audit log use raw CosmosDB SQL queries with `container.query_items()` and `enable_cross_partition_query=True`
- Admin endpoints load ALL entities into memory for counting/searching (no server-side filtering)

---

## 5. AI Features

### Azure OpenAI Integration (`llms.py`)

**Configuration:**
- Uses Azure OpenAI (not standard OpenAI)
- Single deployment, configured via `AZURE_OPENAI_API_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION`
- Default parameters: temperature=0.1, top_p=0.95, max_tokens=800

**Functions:**
- `send_prompt_to_llm(prompt)` -- sync, returns content string
- `send_prompt_to_llm_with_timing(prompt)` -- sync, returns `{ content, llmResponseTimeMs, promptTokens, responseTokens }`
- `send_prompt_to_llm_async(prompt)` -- async via aiohttp
- `send_prompt_to_llm_async_with_timing(prompt)` -- async with timing
- `send_multiple_prompts_concurrent(prompts)` -- async, runs multiple in parallel
- `get_speaker_mapping(transcript_text)` -- infer speaker names, parse JSON from response
- `get_speaker_summaries_via_llm(transcript_text)` -- get identifying characteristics per speaker

**Also uses:** `shared_quickscribe_py.azure_services.azure_openai.get_openai_client("normal")` for the chat endpoint (separate client with `send_messages_with_timing()` method).

### Prompt Templates (`prompts.yaml`)

Five prompts defined:

1. **`infer_speaker_names`**: Given "Speaker 1", "Speaker 2" transcript, infer actual names. Output: JSON mapping `{ "Speaker 1": { "name": "...", "reasoning": "..." } }`. Uses `__TRANSCRIPT__` placeholder.

2. **`get_speaker_summaries`**: Analyze transcript to create 1-3 sentence identifying summaries per speaker (who they are, not what they said). Prioritizes explicit names > relationships > contextual clues > behavioral patterns. Output: JSON `{ "speaker_summaries": { "Speaker 1": "summary..." } }`. Uses `__TRANSCRIPT__` placeholder.

3. **`generate_title`**: Generate max 60-char title. Uses `__TRANSCRIPT__` placeholder.

4. **`generate_description`**: Generate 1-2 sentence summary. Uses `__TRANSCRIPT__` placeholder.

5. **`generate_title_and_description`**: Combined single-call version. Output: JSON `{ "title": "...", "description": "..." }`. Uses `__TRANSCRIPT__` placeholder.

### AI Post-Processing Pipeline (`ai_postprocessing.py`)

**`postprocess_recording_full(recording_id)`** -- triggered after transcoding completes or manually:
1. Fetch recording and transcript text (prefers diarized)
2. Generate title + description via single LLM call (async, parsed from JSON response)
3. Update recording with generated title/description
4. Speaker inference is **disabled** (hardcoded skip)

**Speaker inference flow** (when enabled):
1. LLM infers names from transcript
2. For each inferred name, search existing Participant profiles (fuzzy match)
3. If match found, link participant with confidence score
4. If no match, auto-create new Participant profile
5. Store SpeakerMapping objects in transcription

### Analysis System

- Analysis types are configurable prompt templates stored in CosmosDB
- Built-in types have `partitionKey = "global"`, custom types have `partitionKey = userId`
- Execution: replace `{transcript}` in prompt template with actual transcript text, send to LLM
- Results stored as `AnalysisResult` objects embedded in the Transcription document
- Failed results are also stored (with status='failed' and errorMessage)

### Chat

- Accepts full conversation history (system + user + assistant messages)
- Supports referencing multiple transcriptions
- Frontend constructs system message with tagged transcript (`[[ref_AA00]]` markers)
- Backend just proxies messages to Azure OpenAI and returns response with usage stats
- Uses `get_openai_client("normal").send_messages_with_timing()` from shared library

---

## 6. File Handling & Blob Storage

### Upload Flow

1. File received via multipart form (`file` field or `audio_file` for iOS)
2. Saved to `/tmp/<uuid>.<original_ext>`
3. Uploaded to Azure Blob Storage container (recording container)
4. Recording created in CosmosDB with `transcoding_status = queued`
5. Message sent to Azure Storage Queue with:
   - recording_id, source_blob, target_blob (.mp3), original_filename, user_id
   - callbacks array (backend callback URL + optional test webhook)
6. Temp file deleted

### Blob Storage (`blob_util.py`)

Thin wrapper around `shared_quickscribe_py.azure_services.BlobStorageClient`:
- `store_recording_as_blob(file_path, blob_filename)` -- upload
- `save_blob_to_local_file(blob_filename, local_file_path)` -- download
- `generate_recording_sas_url(filename, read, write)` -- 24-hour SAS URL
- `send_to_transcoding_queue(...)` -- queue message for transcoder
- `delete_recording_blob(filename)` -- delete blob

### Audio URL Generation

The `GET /api/recording/<id>/audio-url` endpoint:
1. Verifies recording ownership
2. Checks transcoding/transcription status
3. Resolves blob name: tries `recording.blob_name`, then `{user_id}/{unique_filename}`, then just `unique_filename`
4. Generates read-only SAS URL valid 24 hours
5. Returns `{ audio_url, expires_in: 86400, content_type: "audio/mpeg" }`

### Audio Duration

`util.py` uses `mutagen` library to extract duration from MP3 and M4A files.

---

## 7. Configuration & Settings

### Configuration Hierarchy

1. `.env` file (copied from `.env.local` or `.env.azure` by `startup.sh`)
2. `shared_quickscribe_py.config.get_settings()` -- validates and structures all settings
3. `config.py` (`Config` class) -- backward-compat wrapper exposing `config.X` properties

### Feature Flags (from `shared_quickscribe_py.config`)

| Flag | Purpose |
|------|---------|
| `cosmos_enabled` | CosmosDB integration |
| `blob_storage_enabled` | Azure Blob Storage |
| `ai_enabled` | Azure OpenAI features |
| `speech_services_enabled` | Azure Speech Services |
| `plaud_enabled` | Plaud device integration |
| `azure_ad_auth_enabled` | Azure AD authentication |
| `assemblyai_enabled` | AssemblyAI transcription |
| `plaud_sync_trigger_enabled` | Manual Plaud sync triggering |

### Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `AZURE_COSMOS_ENDPOINT` | CosmosDB endpoint |
| `AZURE_COSMOS_KEY` | CosmosDB key |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob + Queue storage |
| `AZURE_OPENAI_API_ENDPOINT` | OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | OpenAI key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name |
| `AZURE_OPENAI_API_VERSION` | API version string |
| `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` | Azure AD app registration |
| `AUTH_MODE` | "enabled" or "disabled" |
| `USE_DEV_USER_BYPASS` | "true" to enable dev user mode |
| `DEFAULT_DEV_USER` | Default dev user name (default: "cbird") |
| `FLASK_ENV` / `FLASK_DEBUG` | Development mode flags |
| `LOG_LEVEL` | Logging level (default: INFO) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights telemetry |
| `BACKEND_BASE_URL` | Override for callback URL generation in Docker |
| `PLAUD_SYNC_TRIGGER_*` | Service principal for Container Apps Job trigger |

### Logging

- JSON-formatted console output via custom `JSONFormatter`
- File output to `backend/logs/backend.log`
- Azure App Insights via OpenCensus `AzureLogHandler` (when connection string present)
- Custom `MetadataFilter` adds service, namespace, version as custom dimensions
- Logger namespace: `quickscribe.backend.<module>`

---

## 8. Dependencies

### Core Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.3 | Web framework |
| flask-cors | 6.0.1 | CORS handling |
| gunicorn | 22.0.0 | Production WSGI server |
| Pydantic | 2.9.2 | Data validation and serialization |
| azure-cosmos | 4.7.0 | CosmosDB client |
| azure-storage-blob | 12.23.1 | Blob storage |
| azure-storage-queue | 12.12.0 | Queue storage (transcoding jobs) |
| azure-identity | 1.19.0 | Azure authentication |
| azure-keyvault-secrets | 4.8.0 | Key Vault (unused in current code?) |
| azure-mgmt-appcontainers | 3.1.0 | Container Apps Job trigger |
| openai | 1.51.2 | OpenAI client (used by shared lib) |
| aiohttp | 3.10.11 | Async HTTP for concurrent LLM calls |
| PyJWT | 2.9.0 | JWT token decoding |
| msal | 1.31.0 | MSAL (imported but auth is JWT-only) |
| assemblyai | 0.34.0 | AssemblyAI transcription (alternative provider) |
| requests | 2.32.3 | HTTP client (LLM calls, JWKS fetch) |
| python-dotenv | 1.0.1 | .env file loading |
| PyYAML | 6.0.2 | Prompt template loading |
| mutagen | 1.47.0 | Audio file metadata (duration) |
| pydub | 0.25.1 | Audio processing |
| tiktoken | 0.8.0 | Token counting |
| numpy | >=1.24.0 | Numeric operations (speaker embeddings) |

### Likely Unused / Overkill Dependencies

| Package | Notes |
|---------|-------|
| Flask-SocketIO, python-socketio, python-engineio, simple-websocket | WebSocket support -- no websocket routes exist |
| Flask-WTF, WTForms | Form handling -- only JSON API endpoints exist |
| azure-functions | Azure Functions SDK -- this is a Flask app |
| azure-cognitiveservices-speech | Speech SDK -- transcription done by plaud_sync_service |
| google-api-core, google-auth, googleapis-common-protos | Google APIs -- no Google integration |
| black, isort | Dev tools in production requirements |
| bump2version | Dev tool in production requirements |
| datamodel-code-generator | Code gen tool in production requirements |
| coverage, pytest, pytest-* | Test dependencies in production requirements |
| protobuf, proto-plus | Protobuf -- likely pulled in by google deps |

### Shared Library

`shared_quickscribe_py` is installed in editable mode. It provides:
- Pydantic models (User, Recording, Transcription, etc.)
- CosmosDB handler classes
- Azure service wrappers (BlobStorageClient, OpenAI client)
- Configuration/settings system

---

## 9. Technical Debt & Simplification Opportunities

### Security Issues

1. **No authorization on many endpoints**: Multiple endpoints allow any authenticated user to read/modify/delete any other user's data:
   - `GET /api/user/<user_id>`, `PUT /api/user/<user_id>`, `GET /api/delete_user/<user_id>`
   - `GET /api/user/<user_id>/recordings`, `GET /api/user/<user_id>/transcriptions`
   - `PUT /api/recording/<recording_id>` and `PUT /api/transcription/<transcription_id>` (no ownership check)
   - `GET /api/users` lists all users

2. **Admin is not admin**: `require_admin` is just `require_auth`. Anyone authenticated is an "admin."

3. **Arbitrary field updates**: `PUT` routes use `setattr(obj, key, value)` for every field in the request body, allowing modification of internal fields like `user_id`, `partitionKey`, `type`, etc.

### HTTP Method Misuse

Several destructive/mutating operations use GET:
- `GET /api/delete_recording/<id>`
- `GET /api/delete_transcription/<id>`
- `GET /api/delete_user/<user_id>`
- `GET /api/tags/delete/<id>`
- `GET /api/recordings/<id>/add_tag/<id>`
- `GET /api/recordings/<id>/remove_tag/<id>`

### Architecture Complexity (Overkill for 1-Few Users)

1. **Admin dashboard with full CRUD** (`admin.py` is ~1330 lines): For a personal app, a full admin panel with overview stats, integrity checks, bulk operations, export, and global search is substantial overhead. The admin endpoints load ALL entities into memory for every request.

2. **Speaker identification review queue system**: Accept/reject/dismiss/reassign/training-toggle pipeline with full audit history is very enterprise-grade for a personal transcription app. This is ~700 lines of route code in `api.py`.

3. **Speaker profile training system**: Voice profile embeddings, training approval workflows, profile rebuild -- references `speaker_profile_updater` module that may not even be in the backend directory.

4. **Participant system**: Full CRUD + search + merge + recordings lookup adds significant complexity. For a personal app, a simple "known speakers" list would suffice.

5. **Analysis types system**: Configurable prompt templates with global vs. user-scoped partitioning. For one user, this could just be hardcoded or a simple config file.

6. **Plaud sync trigger service**: A whole service principal + Container Apps Job management layer for triggering a cron job manually.

### Code Quality Issues

1. **Massive route files**: `api.py` is ~2080 lines with mixed concerns (CRUD, upload, tags, speaker ID review, audit log). Should be split or simplified.

2. **Duplicate upload code**: `upload` and `upload_from_ios_share` are nearly identical (one expects `file`, the other `audio_file`).

3. **Mutable global state in `llms.py`**: A module-level `payload` dict is mutated in `send_prompt_to_llm()` -- not thread-safe. The `send_prompt_to_llm_with_timing` and async versions copy it, but the basic `send_prompt_to_llm` mutates in place.

4. **Two LLM client systems**: `llms.py` uses raw `requests.post()` to Azure OpenAI, while the chat endpoint uses `shared_quickscribe_py.azure_services.azure_openai.get_openai_client()`. These should be unified.

5. **Backward-compat config wrapper**: `config.py` wraps the shared settings with a legacy `config.X` property interface. In a rewrite, use the shared settings directly.

6. **Inconsistent response formats**: Some endpoints return `{ status, data, count }`, others return raw model dumps, others return `{ error }` or `{ message }`. No standard envelope.

7. **Tags stored on User document**: Tags are embedded in the User document rather than being separate entities. This means tag operations require reading/writing the entire User document.

8. **Logging noise**: `logging_config.py` has print statements with question mark emojis that go to stdout. The `app.py` has `print("Registered routes:")` that runs on every startup.

9. **Dead/deprecated code**: Several functions in `ai_postprocessing.py` are marked deprecated (`update_recording_participants`, `update_recording_participants_with_participants`, `update_transcription_speaker_data`).

10. **30-day transcoding timeout**: `TRANSCRIPTION_IN_PROGRESS_TIMEOUT_SECONDS = 24 * 60 * 60 * 30` is defined but never actually used for timeout logic.

### Dependency Bloat

The `requirements.txt` includes test dependencies (pytest, coverage), dev tools (black, isort, bump2version), code generators (datamodel-code-generator), and unused libraries (Flask-SocketIO, Flask-WTF, Google APIs, azure-functions). A clean rewrite should have separate dev/prod dependency lists and only include what's actually used.

### What Actually Matters (Core Functionality)

For a rewrite targeting 1-few users, the essential functionality is:

1. **Auth**: Azure AD JWT validation + user auto-provisioning
2. **Recordings CRUD**: List, get, update, delete (with Plaud deleted-items tracking)
3. **File upload**: Upload to blob, queue transcoding
4. **Transcoding callback**: Accept status updates from transcoder
5. **Transcription retrieval**: Get transcript with speaker names
6. **Audio streaming**: Generate SAS URLs
7. **AI postprocessing**: Title/description generation
8. **Speaker management**: Manual speaker-to-participant assignment
9. **Chat**: LLM chat with transcript context
10. **Analysis execution**: Run configurable prompts against transcripts
11. **Tags**: Create/manage/assign tags to recordings
12. **Participants**: Basic CRUD for known speakers

Everything else (admin panel, speaker ID review queue, audit log, training pipeline, bulk operations, integrity checks, export, test user management) could be dropped or dramatically simplified.
