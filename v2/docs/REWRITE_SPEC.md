# QuickScribe Rewrite Specification

**Date**: 2026-03-24
**Status**: Decisions Finalized
**Informed by**: 4 component analysis docs, GPT-5.4 review, Gemini 3.1 Pro review, owner decisions on all open questions

---

## Table of Contents

1. [Context & Motivation](#1-context--motivation)
2. [Guiding Principles](#2-guiding-principles)
3. [Architecture Overview](#3-architecture-overview)
4. [Data Model & Storage](#4-data-model--storage)
5. [Backend Specification](#5-backend-specification)
6. [Frontend Specification](#6-frontend-specification)
7. [Plaud Sync & Background Processing](#7-plaud-sync--background-processing)
8. [AI Features](#8-ai-features)
9. [Authentication & Authorization](#9-authentication--authorization)
10. [Features: Keep, Simplify, Drop](#10-features-keep-simplify-drop)
11. [Data Migration Strategy](#11-data-migration-strategy)
12. [Risks & Mitigations](#12-risks--mitigations)
13. [Open Questions](#13-open-questions)

---

## 1. Context & Motivation

### What QuickScribe Is
QuickScribe is a personal audio transcription application. It syncs recordings from a Plaud device, transcribes them via Azure Speech Services, enriches them with AI (titles, descriptions, chat), and lets the user browse, search, and manage transcripts with speaker identification.

### Why Rewrite
The current system has accumulated significant over-engineering for its actual use case (1-few users):

- **CosmosDB** with fake partition keys (all data in one container, static partition keys like `"recording"`, `"user"`)
- **70+ API endpoints** when ~12-15 are actually used
- **1.5GB Docker image** for speaker ID using PyTorch/SpeechBrain/ECAPA-TDNN
- **120-file auto-generated Swagger client** for 3 Azure Speech API calls
- **Enterprise features** (admin panel, audit logs, review queues, distributed locks, manual review items) for a personal app
- **Fragile model generation pipeline** (TypeScript -> JSON Schema -> Python) producing ugly code (`Status1`, `Status11`)
- **Frontend** with no URL routing, no caching, CustomEvent-based communication, no virtualization
- **10+ separate CosmosClient connection pools** (one per handler)
- **Security gaps** (no ownership checks, admin = authenticated user, arbitrary field mutation via `setattr`)

### Rewrite Goals
1. **Same functionality** for the features that matter
2. **Dramatically simpler** architecture, deployment, and maintenance
3. **Right-sized** for 1-few users
4. **Properly engineered** (real auth, proper routing, caching, search)
5. **Cheaper** to run (eliminate CosmosDB costs, reduce container resources)

---

## 2. Guiding Principles

1. **Personal-scale**: Design for 1-few users. No multi-tenant patterns, no distributed systems.
2. **Monolith first**: One application, one database. Split only if truly necessary.
3. **Delete over simplify**: If a feature isn't used regularly, remove it entirely rather than simplifying it.
4. **Source of truth in Python**: Define models in Python (Pydantic), generate TypeScript types from OpenAPI spec. No more TS-to-Python codegen.
5. **Thin integrations**: Small, handwritten clients for external services. No generated SDK bloat.
6. **Idempotent operations**: All sync/import operations must be safe to retry.
7. **Real engineering basics**: URL routing, query caching, proper auth, database migrations, full-text search.

---

## 3. Architecture Overview

### Target Architecture

```
┌─────────────────────────────────────────────────┐
│              Single Application                  │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ FastAPI   │  │ Background│  │ Static Files  │ │
│  │ API       │  │ Scheduler │  │ (Frontend)    │ │
│  └─────┬────┘  └─────┬────┘  └───────────────┘ │
│        │              │                          │
│  ┌─────▼──────────────▼────┐                    │
│  │    Application Layer     │                    │
│  │  (services, models)      │                    │
│  └─────┬──────────────┬────┘                    │
│        │              │                          │
│  ┌─────▼────┐  ┌─────▼────┐                    │
│  │ SQLite/  │  │ File     │                    │
│  │ Postgres │  │ Storage  │                    │
│  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────┘
         │                    │
    ┌────▼────┐         ┌────▼────┐
    │ Azure   │         │ Azure   │
    │ Speech  │         │ OpenAI  │
    └─────────┘         └─────────┘
         │
    ┌────▼────┐
    │ Plaud   │
    │ API     │
    └─────────┘
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend framework | FastAPI | Native async, Pydantic integration, auto OpenAPI docs |
| Database | SQLite + Litestream | Local disk + WAL replication to Azure Blob. ~$31/mo. See `~/repos/guides/deploying-sqlite-to-azure.md` |
| Audio storage | Azure Blob Storage | Keep existing blobs, storage account shared with Litestream |
| Background jobs | APScheduler or FastAPI BackgroundTasks | In-process, no separate container needed |
| Speaker ID | ECAPA-TDNN (PyTorch/SpeechBrain) | Kept — better than LLM-based inference. Same container. |
| Frontend framework | React + TypeScript + Vite | Keep what works, fix what doesn't |
| Frontend routing | React Router v7 | Real URLs, deep linking, browser history |
| Frontend data | TanStack Query | Caching, invalidation, replaces CustomEvents |
| UI library | shadcn/ui + Tailwind CSS | Modern defaults, own the components, great ecosystem |
| Auth | Azure AD via MSAL (in-app) | Keep in-app JWT validation — avoids Easy Auth re-login on deploy |
| Model source of truth | Python (Pydantic) | Generate TS types from OpenAPI spec |
| Deployment | Single container on Azure App Service | Litestream entrypoint, local dev without Docker also supported |

### Development Modes

1. **Local dev (no Docker)**: `uv run uvicorn main:app --reload`. SQLite at `./data/app.db` via `DATABASE_PATH` env var. No Litestream. `AUTH_DISABLED=true`.
2. **Local Docker**: Same production image but no `AZURE_STORAGE_ACCOUNT` set, so entrypoint.sh skips Litestream. SQLite on mounted volume.
3. **Production (Azure App Service)**: Full Litestream replication to Blob Storage. Single instance. MSAL auth enabled.

### What's Eliminated

- CosmosDB and all associated complexity
- Shared Python library (merged into main app)
- Separate Container Apps Job
- Azure Storage Queue for transcoding
- Auto-generated Swagger client (120 files -> ~150 lines)
- TypeScript-to-Python model generation pipeline
- 10 separate handler classes with individual CosmosClient instances
- Distributed locking via CosmosDB
- Easy Auth (keeping in-app MSAL to avoid re-login on deploy)
- Fluent UI (replaced by shadcn/ui + Tailwind)

---

## 4. Data Model & Storage

### Database: SQLite with WAL Mode (Default)

SQLite is the right default for a personal app:
- Zero operational cost
- Single file, trivial backups (copy the file)
- WAL mode handles light concurrency
- FTS5 for full-text search
- Can migrate to PostgreSQL later if needed

For cloud deployment where local disk isn't persistent, use PostgreSQL or Turso (SQLite over HTTP).

### Schema

#### `users` Table
```sql
CREATE TABLE users (
    id              TEXT PRIMARY KEY,           -- "user-{uuid}"
    name            TEXT,
    email           TEXT,
    role            TEXT DEFAULT 'user',
    azure_oid       TEXT UNIQUE,                -- Azure AD Object ID
    plaud_enabled   BOOLEAN DEFAULT FALSE,
    plaud_token     TEXT,                       -- Plaud bearer token (encrypted at rest)
    plaud_last_sync TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login      TIMESTAMP,
    settings_json   TEXT                        -- JSON blob for extensible settings
);
```

#### `recordings` Table (merged Recording + Transcription)
```sql
CREATE TABLE recordings (
    id                  TEXT PRIMARY KEY,       -- uuid
    user_id             TEXT NOT NULL REFERENCES users(id),

    -- Audio metadata
    title               TEXT,                   -- AI-generated or manual
    description         TEXT,                   -- AI-generated or manual
    original_filename   TEXT NOT NULL,
    file_path           TEXT,                   -- blob key or local path
    duration_seconds    REAL,
    recorded_at         TIMESTAMP,
    source              TEXT NOT NULL,          -- 'plaud', 'upload', 'paste'

    -- Plaud-specific
    plaud_id            TEXT,                   -- for dedup and delete-blocking
    plaud_metadata_json TEXT,                   -- original Plaud API response

    -- Processing status (single unified status)
    status              TEXT NOT NULL DEFAULT 'pending',
        -- pending -> transcoding -> transcribing -> processing -> ready
        -- any state -> failed
    status_message      TEXT,                   -- error details if failed
    provider_job_id     TEXT,                   -- Azure Speech transcription ID
    processing_started  TIMESTAMP,
    processing_completed TIMESTAMP,
    retry_count         INTEGER DEFAULT 0,

    -- Transcript data
    transcript_text     TEXT,                   -- plain text
    diarized_text       TEXT,                   -- "Speaker 1: ..." format
    transcript_json     TEXT,                   -- raw Azure JSON (for timestamps/segments)
    token_count         INTEGER,
    speaker_mapping     TEXT,                   -- JSON: {"Speaker 1": {participantId, displayName, ...}}

    -- Metadata
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    UNIQUE(plaud_id)                            -- prevent duplicate Plaud imports
);

CREATE INDEX idx_recordings_user_id ON recordings(user_id);
CREATE INDEX idx_recordings_status ON recordings(status);
CREATE INDEX idx_recordings_recorded_at ON recordings(user_id, recorded_at DESC);
```

#### `recordings_fts` (Full-Text Search)
```sql
CREATE VIRTUAL TABLE recordings_fts USING fts5(
    title, description, diarized_text, transcript_text,
    content='recordings',
    content_rowid='rowid'
);
-- Triggers to keep FTS in sync with recordings table
```

#### `participants` Table
```sql
CREATE TABLE participants (
    id                  TEXT PRIMARY KEY,       -- uuid
    user_id             TEXT NOT NULL REFERENCES users(id),
    display_name        TEXT NOT NULL,
    first_name          TEXT,
    last_name           TEXT,
    aliases             TEXT,                   -- JSON array
    email               TEXT,
    role                TEXT,                   -- job title
    organization        TEXT,
    relationship        TEXT,                   -- relationship to user
    notes               TEXT,
    is_user             BOOLEAN DEFAULT FALSE,  -- "this is me"
    first_seen          TIMESTAMP,
    last_seen           TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_participants_user_id ON participants(user_id);
```

#### `tags` Table
```sql
CREATE TABLE tags (
    id          TEXT PRIMARY KEY,               -- slug
    user_id     TEXT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    color       TEXT NOT NULL,                  -- hex color
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE TABLE recording_tags (
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    tag_id       TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (recording_id, tag_id)
);
```

#### `analysis_templates` Table
```sql
CREATE TABLE analysis_templates (
    id          TEXT PRIMARY KEY,               -- uuid
    user_id     TEXT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,                  -- display name
    prompt      TEXT NOT NULL,                  -- prompt text with {transcript} placeholder
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `deleted_plaud_ids` Table
```sql
CREATE TABLE deleted_plaud_ids (
    user_id     TEXT NOT NULL REFERENCES users(id),
    plaud_id    TEXT NOT NULL,
    deleted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, plaud_id)
);
```

#### `sync_runs` Table (optional, for debugging)
```sql
CREATE TABLE sync_runs (
    id              TEXT PRIMARY KEY,           -- uuid
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT NOT NULL,              -- running, completed, failed
    trigger         TEXT NOT NULL,              -- scheduled, manual
    summary_json    TEXT,                       -- stats counters
    error_message   TEXT,
    ttl_expires     TIMESTAMP                  -- auto-cleanup after 30 days
);
```

### Key Design Decisions

1. **Recording + Transcription merged**: Single `recordings` table contains both audio metadata and transcript data. List queries use column projection (SELECT only metadata columns).

2. **Unified processing status**: Instead of separate `transcoding_status`, `transcription_status`, `transcription_job_status`, use a single `status` field with a linear pipeline: `pending -> transcoding -> transcribing -> processing -> ready | failed`.

3. **Speaker mapping as JSON column**: The `speaker_mapping` JSON stores per-speaker data including `participantId`, `displayName`, `manuallyVerified`. No embeddings stored (ML speaker ID removed).

4. **Tags as separate table**: Instead of embedding in User document, tags get proper relational modeling with a join table.

5. **Plaud dedup via unique constraint**: `UNIQUE(plaud_id)` prevents duplicate imports at the database level, replacing complex application-side filtering.

6. **Full-text search via FTS5**: Built into SQLite, no external search service needed.

---

## 5. Backend Specification

### Framework: FastAPI

```
backend/
  src/
    main.py                 # FastAPI app creation, startup, static serving
    config.py               # Settings from environment (pydantic-settings)
    auth.py                 # Azure AD JWT validation
    models.py               # Pydantic models (source of truth)
    database.py             # SQLite/Postgres connection, SQLAlchemy or raw SQL

    routers/
      recordings.py         # Recording CRUD, audio URLs, upload
      participants.py       # Participant CRUD, search, merge
      ai.py                 # Chat, title/description generation
      settings.py           # User settings, Plaud config
      sync.py               # Manual sync trigger, sync status
      tags.py               # Tag CRUD, assignment

    services/
      recording_service.py  # Business logic for recordings
      transcription.py      # Azure Speech client (handwritten, ~150 lines)
      plaud_client.py       # Plaud API client (isolated)
      ai_service.py         # LLM interactions (title, description, chat, analysis)
      storage.py            # File storage abstraction (blob or local)
      sync_service.py       # Plaud sync orchestration

    scheduler/
      jobs.py               # APScheduler job definitions (sync, cleanup)
```

### API Endpoints (~25 total, down from 70+)

#### Recordings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/recordings` | List recordings (paginated, searchable, filterable) |
| GET | `/api/recordings/{id}` | Get recording with transcript |
| POST | `/api/recordings/upload` | Upload audio file |
| POST | `/api/recordings/paste` | Paste transcript text (no audio — for Zoom/Teams transcripts) |
| PUT | `/api/recordings/{id}` | Update recording metadata |
| DELETE | `/api/recordings/{id}` | Delete recording (+ block Plaud re-import if applicable) |
| GET | `/api/recordings/{id}/audio` | Get audio streaming URL |
| POST | `/api/recordings/{id}/reprocess` | Retry failed processing |

#### Speakers (on recordings)
| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/recordings/{id}/speakers/{label}` | Assign participant to speaker |

#### Participants
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/participants` | List all participants |
| GET | `/api/participants/{id}` | Get participant with recent recordings |
| POST | `/api/participants` | Create participant |
| PUT | `/api/participants/{id}` | Update participant |
| DELETE | `/api/participants/{id}` | Delete participant |
| GET | `/api/participants/search` | Search by name (fuzzy) |
| POST | `/api/participants/{id}/merge/{other_id}` | Merge two participants |

#### Tags
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tags` | List user's tags |
| POST | `/api/tags` | Create tag |
| PUT | `/api/tags/{id}` | Update tag |
| DELETE | `/api/tags/{id}` | Delete tag |
| POST | `/api/recordings/{id}/tags/{tag_id}` | Add tag to recording |
| DELETE | `/api/recordings/{id}/tags/{tag_id}` | Remove tag from recording |

#### AI
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ai/chat` | Chat with transcript context |
| POST | `/api/recordings/{id}/analyze` | Run analysis action on transcript |

#### User & Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/me` | Get current user profile |
| PUT | `/api/me/settings` | Update settings (including Plaud config) |

#### Sync
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sync/trigger` | Manually trigger Plaud sync |
| GET | `/api/sync/status` | Get recent sync run status |

#### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/version` | API version |

### Response Format

Standardized envelope for all responses:

```json
{
  "data": { ... },
  "meta": {
    "total": 150,
    "page": 1,
    "per_page": 50
  }
}
```

Error responses:
```json
{
  "error": {
    "code": "not_found",
    "message": "Recording not found"
  }
}
```

### Key Backend Design Decisions

1. **Proper HTTP methods**: DELETE for deletions, PUT for updates. No more `GET /delete_*`.
2. **Ownership checks on all endpoints**: Every recording/participant/tag query filters by `user_id`.
3. **Pagination by default**: List endpoints return paginated results with cursor or offset-based pagination.
4. **Column projection for lists**: List endpoints don't return transcript text/JSON.
5. **Single LLM client**: One `AzureOpenAIClient` class, no duplicate `llms.py` + shared lib clients.
6. **No setattr field mutation**: Explicit update schemas for each endpoint.

---

## 6. Frontend Specification

### Stack
- React 18+ / TypeScript / Vite
- React Router v7 (real URL routing)
- TanStack Query v5 (data fetching, caching, mutations)
- shadcn/ui + Tailwind CSS (component library + styling)
- @tanstack/react-virtual (list virtualization)

### Routes

```
/                           -> Redirect to /recordings
/recordings                 -> Recording list (paginated, searchable)
/recordings/:id             -> Recording detail (transcript, audio, chat)
/people                     -> Participants list
/people/:id                 -> Participant detail
/jobs                       -> Sync job list (filterable)
/jobs/:id                   -> Sync job detail with logs
/settings                   -> User settings, Plaud config, analysis templates
/search?q=...               -> Full-text search results (optional dedicated page)
```

### Component Architecture

```
App
  AuthProvider (MSAL or bypass)
  QueryClientProvider (TanStack Query)
  BrowserRouter
    Layout
      NavigationRail (sidebar desktop / bottom bar mobile)
      Outlet (React Router)
        RecordingsPage
          SearchBar + Filters
          RecordingList (virtualized)
            RecordingCard
          RecordingDetail (outlet or split view)
            AudioPlayer
            TranscriptView
              TranscriptEntry (with speaker dropdown)
            ChatPanel
        PeoplePage
          ParticipantList
          ParticipantDetail
        SettingsPage
        SearchPage (optional)
```

### Key Frontend Design Decisions

1. **URL-driven state**: Active recording, active participant, search query all in URL. No more state-based view switching.
2. **TanStack Query replaces all custom hooks**: `useRecordings` -> `useQuery(['recordings', filters])`. Automatic caching, background refetching, mutation invalidation.
3. **No CustomEvents**: Cross-component communication via query invalidation (`queryClient.invalidateQueries(['recordings'])`) after mutations.
4. **Virtualized lists**: RecordingList and ParticipantList virtualized from day one.
5. **Server-side pagination**: No more fetching all recordings at once.
6. **Real search**: Connected to backend FTS endpoint.
7. **Upload UI**: Drag-and-drop or file picker for manual uploads.
8. **Responsive**: Keep mobile support with the list-or-detail pattern, 768px breakpoint.
9. **Tailwind tokens only**: No hardcoded hex colors. Use Tailwind's design system and shadcn/ui theme variables.
10. **Designed for iteration**: UI should be easy to restyle and rearrange. Components are self-contained, styling is in Tailwind classes (easy to change), and shadcn/ui components are owned source code (not hidden in node_modules). Frontend runs independently in dev with hot reload (`npm run dev` proxying to backend) so design changes are instant.

### Transcript Display

Preserve the core UX that works:
- Diarized transcript with speaker labels
- Color-coded speaker borders (6 colors cycling)
- Click-to-play from any transcript entry (when timestamps available)
- Speaker rename via dropdown (search existing participants, create new)
- Audio player with play/pause, progress bar, volume
- Copy transcript, export to file

### Chat

Keep the existing chat UX:
- Side panel (desktop) / full-screen overlay (mobile)
- System message with tagged transcript
- Reference links that scroll to transcript entries
- Full conversation history

---

## 7. Plaud Sync & Background Processing

### Architecture

The sync service becomes a module within the main application, run by an in-process scheduler.

```python
# scheduler/jobs.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=15)
async def plaud_sync():
    """Run Plaud sync for all enabled users."""
    await sync_service.run_sync()

@scheduler.scheduled_job('interval', minutes=5)
async def poll_transcriptions():
    """Check status of pending transcription jobs."""
    await sync_service.poll_pending_transcriptions()
```

### Sync Pipeline (Simplified)

```
For each user with Plaud enabled:

1. Fetch recording list from Plaud API
2. Filter out:
   - Already imported (recordings.plaud_id)
   - Deleted (deleted_plaud_ids table)
3. For each new recording:
   a. Download from Plaud (via presigned S3 URL)
   b. Transcode to MP3 128kbps (ffmpeg, in thread pool)
   c. Upload to storage (blob or local)
   d. Insert recording row (status='transcribing')
   e. Submit to Azure Speech Services
4. Poll pending transcriptions:
   a. Check Azure Speech status
   b. On completion: download transcript JSON, parse diarized text
   c. Generate title + description via LLM
   d. Update recording (status='ready')
```

### Azure Speech Client (Handwritten)

Replace the 120-file generated client with a minimal implementation:

```python
class AzureSpeechClient:
    """Minimal Azure Speech Services v3.2 batch transcription client."""

    def __init__(self, subscription_key: str, region: str):
        self.base_url = f"https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2"
        self.headers = {"Ocp-Apim-Subscription-Key": subscription_key}

    async def create_transcription(self, audio_url: str, display_name: str) -> str:
        """Submit transcription job. Returns transcription ID."""
        ...

    async def get_transcription(self, transcription_id: str) -> dict:
        """Get transcription status."""
        ...

    async def get_transcript_content(self, transcription_id: str) -> dict:
        """Download completed transcript JSON."""
        ...
```

Target: ~150 lines total including error handling and pagination.

### Plaud Client (Isolated)

Keep the existing Plaud client logic but isolate it completely:
- Own module with no leaking of Plaud types into core models
- Map `AudioFile` -> `Recording` at the boundary
- Handle the `.opus` -> MP3 quirk
- Keep browser-spoofing headers
- Add clear error handling for when Plaud changes their API

### Chunking

Simplify chunking:
- Only chunk if Azure Speech rejects based on size/duration
- Treat chunks as implementation detail (not separate DB records)
- Stitch transcript text back together before saving
- Store chunk metadata in a JSON field if needed for debugging

### Speaker Identification (ECAPA-TDNN) — KEPT

The ML speaker identification pipeline stays in the rewrite. It runs in the same container as the API.

**Pipeline (same as current):**
1. After transcription completes, download audio from Blob Storage
2. Parse diarization segments from Azure Speech JSON
3. Extract ECAPA-TDNN embeddings per speaker (SpeechBrain, CPU-only)
4. Match against per-user speaker profile DB (cosine similarity)
5. Assign auto (>=0.78) / suggest (>=0.68) / unknown (<0.68)
6. Re-rate existing speakers when profiles grow

**Storage changes:**
- Speaker profiles: move from Blob Storage JSON to a `speaker_profiles` SQLite table (or keep as blob — TBD during implementation)
- Speaker embeddings stored in `speaker_mapping` JSON on recordings table
- Profile centroids and sample embeddings stored per-participant

**Simplifications vs current:**
- No separate Container Apps Job — runs as background task
- No distributed locks — DB-level locking
- Lazy-load PyTorch on first speaker ID request (avoid startup cost for API-only requests)
- Run embedding extraction in thread pool (`asyncio.to_thread()`) to avoid blocking

### What's Removed from Sync

- Distributed CosmosDB locks (use DB-level locking)
- ManualReviewItem documents (simple retry_count + status='failed' on recording)
- Auto-generated Swagger client (replace with ~150 line handwritten client)

### Job Monitoring — KEPT

Full Jobs view rebuilt with proper routing and data fetching:

**`sync_runs` table:**
```sql
CREATE TABLE sync_runs (
    id              TEXT PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT NOT NULL,              -- running, completed, failed
    trigger         TEXT NOT NULL,              -- scheduled, manual
    stats_json      TEXT,                       -- {transcriptions_checked, recordings_found, ...}
    error_message   TEXT,
    logs_json       TEXT,                       -- [{timestamp, level, message}, ...]
    users_processed TEXT,                       -- JSON array of user IDs
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Endpoints:**
- `GET /api/sync/runs` — paginated list with filters (status, trigger, date, has_activity, min_duration)
- `GET /api/sync/runs/{id}` — full detail with logs
- `POST /api/sync/trigger` — manual sync trigger

**Frontend:** Full Jobs view at `/jobs` and `/jobs/:id` with filtering, log viewer, "Sync Now" button. Mobile-friendly.

---

## 8. AI Features

### Keep

1. **Title + Description Generation**
   - Run after transcription completes
   - Single LLM call returning JSON `{"title": "...", "description": "..."}`
   - Use gpt-4o-mini or equivalent for cost efficiency

2. **Chat with Transcript**
   - System message with tagged transcript
   - Full conversation history
   - Support single transcript context
   - Reference links to transcript segments

3. **LLM-Assisted Speaker Name Inference**
   - After transcription, run `infer_speaker_names` prompt to guess names from conversational context
   - Present as supplementary suggestions alongside ECAPA-TDNN identification
   - Useful when voice profiles don't exist yet for new speakers

### Simplify

4. **Analysis Actions (Simple Custom Prompts)**
   - Simple list of user-defined prompt templates in settings
   - Each has a name and prompt text with `{transcript}` placeholder
   - No global vs user partitioning, no built-in vs custom distinction
   - Stored in a simple `analysis_templates` table
   - Run against any transcript from the recording detail view

### Drop

- Multi-model deployment management
- Separate sync + async LLM client implementations (use one async client)
- Full CRUD analysis type system with partitioning

### LLM Client

Single `AIService` class:

```python
class AIService:
    """Unified LLM interaction layer."""

    async def generate_title_description(self, transcript: str) -> dict:
        ...

    async def infer_speakers(self, transcript: str) -> dict:
        ...

    async def chat(self, messages: list[dict], transcript_context: str) -> dict:
        ...

    async def run_analysis(self, transcript: str, prompt_template: str) -> str:
        ...
```

Backed by Azure OpenAI initially, but with a clean enough interface to swap providers.

---

## 9. Authentication & Authorization

### Approach

Keep Azure AD authentication if the app is internet-exposed. Simplify the implementation.

### Implementation

```python
# auth.py
async def get_current_user(request: Request) -> User:
    """Validate JWT and return user, auto-provisioning if needed."""
    if settings.auth_disabled:
        return get_dev_user()

    token = extract_bearer_token(request)
    claims = validate_jwt(token)  # Azure AD JWKS validation
    user = await db.get_user_by_azure_oid(claims["oid"])

    if not user:
        user = await db.create_user(
            azure_oid=claims["oid"],
            email=claims.get("email"),
            name=claims.get("name"),
        )

    return user
```

### Key Changes from Current

1. **Every endpoint checks ownership**: No more accessing other users' data
2. **No admin role**: For a personal app, if you're authenticated, you're the user
3. **No `setattr` field mutation**: Explicit update models per endpoint
4. **Dev bypass**: Simple `AUTH_DISABLED=true` env var for local development
5. **No local user switching**: Single dev user, no session-based user selection

---

## 10. Features: Keep, Simplify, Drop

### Keep (Same Functionality)

| Feature | Notes |
|---------|-------|
| Plaud sync (download, transcode, upload, transcribe) | Core pipeline, simplified |
| Recording list with search and date filtering | Add server-side pagination + FTS |
| Recording detail with transcript and audio player | Core UX |
| Speaker diarization display | From Azure Speech, displayed as-is |
| Manual speaker-to-participant assignment | Via dropdown, with find-or-create |
| Participant CRUD | Simplified (display_name, name, email, notes, aliases) |
| Participant merge | Keep, useful for dedup |
| Chat with transcript context | Keep as-is |
| AI title + description generation | Keep as-is |
| Plaud deleted-item blocking | Essential to prevent re-sync |
| Audio playback with transcript sync | Click-to-play from transcript entries |
| ECAPA-TDNN speaker identification | Keep full pipeline, simplify review UX |
| Speaker profile management | Keep per-user profile DB with centroids |
| Job monitoring view | Full rebuild with filters, logs, manual trigger |
| Transcript copy and export | Keep as-is |
| Mobile responsive design | Keep list-or-detail pattern |
| Settings (profile, Plaud token config) | Keep as-is |

### Simplify

| Feature | Current | Rewrite |
|---------|---------|---------|
| Tags | Embedded in User doc, complex CRUD | Proper relational table, simple CRUD |
| Analysis types | Full CRUD with global/user partitioning | Simple custom prompt templates in settings |
| Speaker identification | Complex review queue + audit log | Keep ECAPA-TDNN, simplify review UX, drop audit log |
| Processing status | 5+ separate status fields | Single `status` enum |
| Job monitoring | Admin-only UI, complex partitioning | Rebuilt as dedicated `/jobs` view, proper routing + data fetching |
| Sync trigger | Azure Container Apps Job API trigger | HTTP endpoint + in-process scheduler |
| Upload | Two duplicate endpoints (file/audio_file) | One upload endpoint |

### Drop

| Feature | Reason |
|---------|--------|
| Admin panel (1330 lines, 15 endpoints) | Personal app doesn't need admin dashboard |
| Audit log | Overkill for personal use |
| Manual review items | Simple retry_count + status='failed' instead |
| Distributed locks | Single instance, use DB-level locking |
| Integrity checks | Relational DB with foreign keys handles this |
| Bulk operations | Not needed at personal scale |
| Data export | Direct DB access is sufficient |
| Test user management | Use dev bypass instead |
| Sync progress tracking entity | Logs + optional sync_runs table |
| WebSocket support (unused) | Never implemented |
| AssemblyAI integration | Unused alternative provider |

---

## 11. Data Migration Strategy

### Overview

Standalone migration script that connects to the **old system** (CosmosDB + old Blob Storage) and the **new system** (SQLite + new Blob Storage container), pulls everything down, transforms it, and populates the new app's database and storage. **The old app is never touched or modified.**

### Architecture

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   OLD SYSTEM (read-only)│         │   NEW SYSTEM (write)    │
│                         │         │                         │
│  CosmosDB ─────────────────────►  SQLite database          │
│  (recordings container) │  migrate│  (app.db)               │
│                         │  script │                         │
│  Blob Storage ─────────────────►  Blob Storage              │
│  (audio-files container)│         │  (new container/account) │
└─────────────────────────┘         └─────────────────────────┘
```

### Configuration

The migration script reads connection details from a config file or env vars:

```bash
# Old system (read-only)
OLD_COSMOS_ENDPOINT=https://xxx.documents.azure.com:443/
OLD_COSMOS_KEY=xxx
OLD_COSMOS_DATABASE=quickscribe
OLD_COSMOS_CONTAINER=recordings
OLD_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=xxx;...
OLD_BLOB_CONTAINER=audio-files

# New system (write)
NEW_SQLITE_PATH=./data/app.db
NEW_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=yyy;...
NEW_BLOB_CONTAINER=audio-files

# Optional
# SPEAKER_PROFILES_BLOB_CONTAINER=speaker-profiles  (if migrating voice profiles)
```

### Migration Steps

1. **Connect to old CosmosDB** (read-only): Query all documents from the `recordings` container, grouped by partition key type (`user`, `recording`, `transcription`, `participant`, `deleted_items`, `job_execution`, etc.)

2. **Sanitize**: Handle missing fields, inconsistent date formats, null values. CosmosDB allowed arbitrary schema variations — strict SQL inserts will fail on dirty data.

3. **Map entities to new schema**:
   - `User` documents -> `users` table
   - `Recording` + linked `Transcription` documents -> merged `recordings` table (join on `recording.transcription_id == transcription.id`)
   - `Participant` documents -> `participants` table
   - `Tag` (from User.tags) -> `tags` table + `recording_tags` join table (cross-reference `recording.tagIds`)
   - `DeletedItems.items.plaud_recording` -> `deleted_plaud_ids` table
   - `JobExecution` documents -> `sync_runs` table (recent ones only, or all — configurable)

4. **Preserve critical fields**:
   - `plaudMetadata.plaudId` (for dedup and delete-blocking)
   - `speaker_mapping` (all manual assignments, verified statuses, embeddings)
   - `transcript_json` (for timestamp-based playback)
   - `diarized_transcript` and `text`
   - `recorded_timestamp`, `duration`
   - All participant data (display names, aliases, relationships, etc.)

5. **Strip fields**:
   - CosmosDB system fields (`_rid`, `_self`, `_etag`, `_ts`, `_attachments`)
   - Identification history audit trails
   - Processing failure tracking (start fresh)

6. **Copy audio blobs**:
   - For each recording with a `file_path`/`unique_filename`/`blob_name`:
     - Copy blob from old storage account/container to new storage account/container
     - Use Azure SDK blob-to-blob copy (server-side, no download needed if same region)
     - Map old blob path to new standardized path: `{user_id}/{recording_id}.mp3`
     - Update `file_path` in the new recordings table
   - Also copy speaker profile blobs if migrating voice profiles

7. **Populate FTS index**: After all recordings are inserted, rebuild `recordings_fts` from transcript text

8. **Verify**:
   - Count checks (old entity counts vs new table counts)
   - Spot-check key recordings (title, transcript snippet, speaker mapping)
   - Verify blob existence for every `file_path` in the new storage
   - Test audio URL generation
   - Test FTS search

### Migration Script Design

```
tools/migrate.py
```

**PEP 723 inline script metadata** so it runs with just `uv run tools/migrate.py`:

```python
# /// script
# dependencies = ["azure-cosmos", "azure-storage-blob", "rich", "pydantic"]
# requires-python = ">=3.11"
# ///
```

**Features**:
- `--dry-run`: Report what would be migrated (counts, sample data) without writing anything
- `--verify-only`: Run verification checks against an already-migrated new system
- `--skip-blobs`: Migrate DB only, skip blob copying (for testing schema mapping quickly)
- `--verbose`: Show per-record progress
- Progress bars via `rich`
- Error handling: skip-and-log problematic documents, continue with the rest, report failures at end
- Idempotent: can be re-run safely (uses `INSERT OR REPLACE` / checks for existing records)
- Produces a migration report at the end:
  ```
  Migration Complete
  ─────────────────
  Users:          3 migrated, 0 failed
  Recordings:   247 migrated, 1 failed (see errors.log)
  Participants:  42 migrated, 0 failed
  Tags:           8 migrated, 0 failed
  Blobs:        245 copied (12.4 GB), 2 skipped (no source blob)
  FTS index:    rebuilt (247 recordings indexed)
  Deleted IDs:   15 migrated
  ```

### Blob Path Normalization

Old system has inconsistent blob paths:
- Some: `{unique_filename}` (just filename)
- Some: `{user_id}/{unique_filename}`
- Some: referenced via `blob_name` field

New system standardizes to: `{user_id}/{recording_id}.mp3`

The migration script handles all old patterns and writes the new standardized path.

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Losing workflows you actually use** | Before starting: classify every feature as used-weekly / used-occasionally / never-used. Only drop "never-used". |
| **Data migration errors** | Write robust migration script with dry-run, validation, and rollback. Keep CosmosDB running until rewrite is verified. |
| **Deleted Plaud items re-appearing** | Migrate `deleted_plaud_ids` carefully. Test with actual Plaud sync after migration. |
| **Plaud API breaking** | Keep Plaud client completely isolated. Map to internal types at boundary. Monitor for breakage. |
| **Transcript display regressions** | Preserve exact `transcript_json` and `diarized_text` format. Test audio-transcript sync. |
| **Search becoming essential** | Implement FTS from day one, not as a "later" feature. |
| **Auth regression** | If internet-exposed, keep proper JWT validation. Test thoroughly. |
| **Background job blocking web server** | Run ffmpeg/downloads in thread pool (`asyncio.to_thread()`). |
| **Over-simplification** | Don't store everything as JSON blobs. Use proper relational modeling where it matters. Keep pagination and projection. |
| **Provider lock-in** | Use thin service abstractions for storage, transcription, LLM. Not a full abstraction layer, just clean interfaces. |
| **Scope creep during rewrite** | Stick to the spec. Don't add features during rewrite. Reach feature parity first. |

---

## 13. New Feature: Transcript Paste (Zoom/Teams)

**Problem**: Not all transcripts come from Plaud. Users may have transcripts from Zoom, Teams, or other sources that they want to add to QuickScribe for search, chat, and AI analysis — but without audio.

**Endpoint**: `POST /api/recordings/paste`

**Request body**:
```json
{
  "title": "Weekly standup - March 24",
  "transcript_text": "John: Hey everyone, let's get started...\nJane: Sure, I'll go first...",
  "source": "paste",
  "recorded_at": "2026-03-24T10:00:00Z"  // optional
}
```

**Behavior**:
- Creates a recording with `source='paste'`, no `file_path`, no audio
- Parses speaker labels from common transcript formats (e.g., `Name: text`, `[Name] text`, `Name (HH:MM:SS): text`)
- Runs AI title/description generation
- Runs speaker name matching against existing participants
- Indexed in FTS for search
- No audio player shown in UI (gracefully hidden when no audio)
- Status goes directly to `ready` (no transcription/transcoding pipeline)

**Frontend**: "Paste Transcript" button/dialog accessible from the recordings list. Textarea for pasting, optional title and date fields.

---

## 14. Testing Strategy

### Backend Tests
- **Unit tests** for all services (recording, participant, tag, AI, sync, speaker ID, storage)
- **Integration tests** for API endpoints (each router tested against a real SQLite in-memory DB)
- **Auth tests** (JWT validation, dev bypass, user auto-provisioning)
- Framework: **pytest** + **pytest-asyncio** + **httpx** (for async FastAPI test client)
- Test database: in-memory SQLite per test session, fresh schema each run
- Fixtures for common data (users, recordings with transcripts, participants)

### Frontend Tests
- **Component tests** for key UI components (recording list, transcript viewer, audio player, speaker dropdown)
- **Integration tests** for data flow (TanStack Query hooks, router navigation)
- Framework: **Vitest** + **Testing Library**

### Review Process

Each major phase gets reviewed by three external models before proceeding:

1. **Backend** -> reviewed by GPT-5.4, Gemini 3.1 Pro, Opus 4.6
2. **Frontend** -> reviewed by GPT-5.4, Gemini 3.1 Pro, Opus 4.6
3. **Deploy infrastructure** -> reviewed by GPT-5.4, Gemini 3.1 Pro, Opus 4.6
4. **Migration script** -> reviewed by GPT-5.4, Gemini 3.1 Pro, Opus 4.6

Reviews check for: correctness, security, missing edge cases, performance, spec adherence.

---

## 15. Future: Semantic Search with FAISS

**Not in v1**, but the schema and architecture should accommodate this later:

- FAISS vector index alongside SQLite FTS5 for keyword search
- Embeddings generated per transcript chunk (or per recording)
- Stored in a separate file or SQLite table with blob columns
- Query interface: user types natural language, system finds semantically similar transcript passages
- Could reuse the existing Azure OpenAI integration for embedding generation

**Design consideration**: Keep transcript text accessible for both FTS5 and future embedding generation. Don't compress or discard raw text.

---

## 15. Open Questions — RESOLVED

All questions resolved during spec review session:

| # | Question | Decision |
|---|----------|----------|
| 1 | Deployment target | Azure App Service (cloud) + SQLite + Litestream. Local dev without Docker also supported. |
| 2 | Auth approach | Keep in-app Azure AD via MSAL + JWT validation. Avoids Easy Auth re-login on deploy. `AUTH_DISABLED=true` for local dev. |
| 3 | Audio file storage | Keep Azure Blob Storage. Storage account shared with Litestream. |
| 4 | Speaker identification | Keep ECAPA-TDNN (PyTorch/SpeechBrain). Same container. Better than LLM-based inference. |
| 5 | Tags | Keep in rewrite. Proper relational table. Build the UI this time. |
| 6 | Analysis actions | Simple custom prompts. List of templates in settings (name + prompt). No global/user partitioning. |
| 7 | UI library | shadcn/ui + Tailwind CSS. Replacing Fluent UI v9. |
| 8 | Job monitoring | Full Jobs view rebuilt. Filters, logs, manual trigger, mobile-friendly. `/jobs` route. |

---

## Supporting Documents

| Document | Description |
|----------|-------------|
| [`backend_analysis.md`](./backend_analysis.md) | Detailed analysis of all 70+ backend endpoints, auth, DB patterns, AI features, tech debt |
| [`frontend_analysis.md`](./frontend_analysis.md) | All views, components, data flow, responsive design, 22 tech debt items |
| [`plaud_sync_analysis.md`](./plaud_sync_analysis.md) | Full pipeline analysis, speaker ID system, chunking, Azure Speech integration |
| [`shared_library_analysis.md`](./shared_library_analysis.md) | Package structure, all 10 handlers, data models, CosmosDB schema, model generation pipeline |
| [`gpt54_review.md`](./gpt54_review.md) | GPT-5.4 architecture review and recommendations |
| [`gemini31pro_review.md`](./gemini31pro_review.md) | Gemini 3.1 Pro architecture review and recommendations |
