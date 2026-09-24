# System Description
**Git commit:** b9ac4d7a7731c9fa88a25130bc1d62f8de5497be

## 1. Repository Structure

```
v2/
├── backend/                    # FastAPI backend (Python 3.12)
│   ├── VERSION                 # App version (single source of truth for deploys)
│   ├── pyproject.toml          # Dependencies & project config
│   ├── uv.lock                 # Locked dependency versions
│   ├── src/app/
│   │   ├── main.py             # FastAPI app bootstrap, scheduler, system endpoints
│   │   ├── config.py           # Settings from env vars, version reader
│   │   ├── auth.py             # Azure AD JWT + API key authentication
│   │   ├── database.py         # SQLite schema, migrations, connection management
│   │   ├── models.py           # Pydantic models (User, Recording, etc.)
│   │   ├── routers/            # API route handlers
│   │   │   ├── recordings.py   # CRUD, upload, audio, search, speakers, tags
│   │   │   ├── ai.py           # Chat, speaker inference, analysis
│   │   │   ├── settings.py     # User profile, API key management
│   │   │   ├── participants.py # People management, merge
│   │   │   ├── tags.py         # Tag CRUD
│   │   │   ├── collections.py  # Collection management
│   │   │   ├── search.py       # Deep search
│   │   │   └── sync.py         # Plaud sync runs, logs
│   │   ├── services/           # Business logic
│   │   │   ├── recording_service.py  # Core recording ops, upload, transcription
│   │   │   ├── sync_service.py       # Plaud sync, transcription polling, speaker-ID
│   │   │   ├── ai_service.py         # Azure OpenAI chat, analysis, title gen
│   │   │   ├── speech_client.py      # Azure Speech Services client
│   │   │   ├── storage_service.py    # Azure Blob / local file storage
│   │   │   ├── embedding_engine.py   # ECAPA-TDNN speaker embeddings (lazy torch)
│   │   │   ├── speaker_processor.py  # Speaker identification orchestration
│   │   │   ├── plaud_client.py       # Plaud.ai API client
│   │   │   ├── deep_search.py        # Multi-recording semantic search
│   │   │   ├── search_summary_service.py  # AI search summaries
│   │   │   └── ...
│   │   ├── scheduler/          # APScheduler background jobs
│   │   └── prompts/            # Jinja2 LLM prompt templates
│   └── tests/                  # pytest test suite
├── frontend/                   # React 18 SPA (TypeScript, Vite, shadcn/ui, Tailwind)
│   ├── src/
│   │   ├── main.tsx            # App bootstrap with MSAL auth
│   │   ├── App.tsx             # Router and layout
│   │   ├── lib/
│   │   │   ├── auth.ts         # MSAL Azure AD config, token acquisition
│   │   │   ├── api.ts          # Axios API client with auth interceptor
│   │   │   └── queries.ts      # TanStack Query hooks
│   │   ├── components/         # UI components (layout, recordings, people, etc.)
│   │   ├── pages/              # Page-level components
│   │   └── types/models.ts     # TypeScript type definitions
│   └── package.json
├── deploy/
│   ├── Dockerfile.deps         # Base image: OS pkgs + Litestream + venv (PyTorch), hash-tagged
│   ├── Dockerfile              # App image FROM the deps image (frontend build + app source)
│   ├── entrypoint.sh           # Litestream restore + uvicorn start
│   ├── litestream.yml          # SQLite → Azure Blob replication config
│   ├── bicep/main.bicep        # Azure infrastructure template
│   └── scripts/
│       ├── config.sh           # Deployment config (resource names, SKUs)
│       ├── config.local.sh     # Local overrides (gitignored)
│       ├── 01-create-resources.sh
│       ├── 02-build-push.sh    # Build Docker image, push to ACR
│       ├── 03-deploy-app.sh    # Deploy to App Service, poll for version
│       ├── set-secrets.sh      # Set env vars on webapp
│       ├── upload-db.sh        # Upload SQLite to Azure via Litestream
│       ├── download-db.sh      # Download SQLite from Azure via Litestream
│       └── teardown.sh         # Delete all resources
├── tools/
│   ├── migrate.py              # CosmosDB → SQLite migration
│   ├── backfill_summaries.py   # AI summary backfill tool
│   └── normalize_speaker_mappings.py
└── docs/                       # Design docs, reviews, analysis
```

## 2. Languages, Size & Composition

| Language   | Files | Purpose |
|------------|-------|---------|
| Python     | ~30   | Backend API, services, migrations |
| TypeScript | ~35   | Frontend SPA, types |
| SQL        | ~1    | Schema in database.py |
| Jinja2     | 7     | LLM prompt templates |
| Shell      | 8     | Deploy scripts |
| Bicep      | 1     | Azure infrastructure |

Backend: ~9,000 lines Python. Frontend: ~7,700 lines TypeScript.

## 3. Key Components and Modules

### Backend (FastAPI)

- **Authentication** (`auth.py`): Dual auth — Azure AD JWT (Bearer token) for browser, API key (X-API-Key header) for iPhone uploads. Email-first user lookup. Auto-provisions users on first login.
- **Recording Service** (`recording_service.py`): Core CRUD, file upload with ffmpeg transcode to mono MP3, Azure Speech transcription submission, paginated listing with `COALESCE(recorded_at, created_at)` sort.
- **Sync Service** (`sync_service.py`): Plaud device sync (fetches recordings via Plaud API), transcription polling (5-min scheduler), AI enrichment (title/description), speaker identification pipeline. Clear logging of skip reasons.
- **AI Service** (`ai_service.py`): Azure OpenAI integration. Chat uses `gpt-5.4-mini` with `reasoning_effort="low"` for speed. Analysis and speaker inference use the main deployment.
- **Speaker ID** (`embedding_engine.py`, `speaker_processor.py`): ECAPA-TDNN via SpeechBrain/PyTorch (CPU-only). Lazy-loads model on first use. Runs after transcription completes.
- **Storage** (`storage_service.py`): Abstraction over Azure Blob Storage and local filesystem. SAS URL generation for Speech Services.

### Frontend (React + shadcn/Tailwind)

- **Auth** (`auth.ts`): MSAL React with `MsalAuthenticationTemplate` (redirect flow). No popups.
- **API Client** (`api.ts`): Axios with Bearer token interceptor. Version endpoint bypasses auth.
- **Pages**: Recordings (split-list/detail), People, Jobs, Settings, Search, Collections, Speaker Reviews.
- **Settings**: API key card with generate/reveal/copy for iPhone upload setup.

### Database (SQLite + Litestream)

- **Engine**: SQLite with WAL mode, `busy_timeout=5000`.
- **Replication**: Litestream continuously replicates to Azure Blob Storage (1s sync interval, 24h snapshots).
- **Tables**: `users`, `recordings` (with FTS5), `participants`, `tags`, `recording_tags`, `sync_runs`, `run_logs`, `speaker_profiles`, `collections`, `collection_items`, `deleted_plaud_ids`.
- **Migrations**: In `database.py._migrate_schema()`. Backfills null `recorded_at` from `created_at`.

## 4. Build, Tooling, and Dependencies

### Version Management

- **Source of truth**: `backend/VERSION` file (e.g., `2.7.2`)
- **Config reads**: `config.py._read_version()` reads VERSION file, falls back to pyproject.toml
- **Docker**: VERSION file copied separately from pyproject.toml to avoid busting deps cache on version bumps

### Docker Build (deploy/Dockerfile.deps + deploy/Dockerfile)

Two images, so the ~2 GB PyTorch venv is built once and reused:

| Image | Contents | Rebuilt when |
|-------|----------|--------------|
| `quickscribe-deps:<hash>` (`Dockerfile.deps`) | python:3.12-slim, ffmpeg, libsndfile1, Litestream, `appuser`, full venv from uv.lock (incl. PyTorch CPU) | Hash of `Dockerfile.deps` + `pyproject.toml` + `uv.lock` changes, or `DEPS_REBUILD=1` |
| `quickscribe-v2:<version>` (`Dockerfile`) | `FROM` the deps image + React build + `backend/src` + config + `VERSION` | Every deploy |

`02-build-push.sh` computes the hash, builds the deps image only if that tag is
missing from ACR, then builds the app image with `--build-arg DEPS_IMAGE=...`.
It uses local Docker if available, otherwise `az acr build` (no local layer
cache, which is why the deps image exists). Because the deps tag is
content-addressed, App Service keeps its cached deps layers and a normal deploy
pulls only the thin app layers.

- Nothing in the app image may `chown -R` or otherwise touch the venv: that
  rewrites every file into a new multi-GB layer. Put OS/venv changes in
  `Dockerfile.deps`, already owned by `appuser`.
- Only versioned tags are pushed, never `:latest`. ACR has a continuous-deploy
  webhook (`quickscribecd`) on `:latest`; a CD-triggered restart overlaps old
  and new containers (Litestream split-brain). `DOCKER_ENABLE_CI=false` on the
  app as a second guard.
- Frontend MSAL settings (`VITE_AUTH_ENABLED`, `VITE_AZURE_CLIENT_ID`,
  `VITE_AZURE_TENANT_ID`) are passed as build args from `config.local.sh`; the
  build refuses to run if auth is enabled but they are unset.

### Pinned Versions

- Python deps: All pinned via `uv.lock` (96 packages)
- uv: `0.11.2`
- Node: `22.14-slim`
- Litestream: `0.3.14`
- PyTorch: `2.4.1` (CPU-only from pytorch-cpu index)
- SpeechBrain: `1.0.3`

### Deploy Scripts

```bash
# Full deploy workflow:
cd v2/deploy/scripts
./02-build-push.sh    # Build image, push to ACR (reads VERSION)
./03-deploy-app.sh    # Set container on webapp, restart, poll for version match

# Other scripts:
./set-secrets.sh      # Set env vars from .env file
./upload-db.sh        # Upload local SQLite to Azure Blob via Litestream
./download-db.sh      # Download live SQLite from Azure Blob
```

## 5. Runtime Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Azure App Service (B2, westus)                              │
│                                                             │
│  entrypoint.sh                                              │
│  ├── litestream restore (from Azure Blob)                   │
│  └── litestream replicate -exec "uvicorn app.main:app"      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ FastAPI (uvicorn, port 8000)                        │    │
│  │                                                     │    │
│  │ Routers: /api/recordings, /api/ai, /api/me, ...     │    │
│  │                                                     │    │
│  │ Scheduler (APScheduler):                            │    │
│  │   - poll_transcriptions_job (every 5 min)           │    │
│  │   - plaud_sync_job (every 15 min)                   │    │
│  └──────────────┬──────────────────────────────────────┘    │
│                 │                                           │
│  ┌──────────────▼──────────┐  ┌─────────────────────┐      │
│  │ SQLite (WAL mode)       │  │ Litestream           │      │
│  │ /app/data/app.db        │──│ → Azure Blob Storage │      │
│  └─────────────────────────┘  └─────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Azure Blob      │ │ Azure Speech    │ │ Azure OpenAI    │
│ (recordings,    │ │ Services        │ │ (gpt-5,         │
│  Litestream)    │ │ (batch transcr) │ │  gpt-5.4-mini)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Authentication Flows

**Browser**: MSAL.js → Azure AD login → JWT Bearer token → backend validates via JWKS
**iPhone**: iOS Shortcut → `X-API-Key` header → backend looks up user by api_key column

### Upload → Transcription Pipeline

1. File received (multipart form, `file` or `audio_file` field)
2. Streamed to temp disk (chunked, avoids memory spikes)
3. Transcoded to mono MP3 via ffmpeg (Azure Speech requires mono)
4. Uploaded to Azure Blob Storage
5. Transcription submitted to Azure Speech Services (async, returns immediately)
6. Response returned to client with `status: "transcribing"`
7. `poll_transcriptions_job` (5-min interval) picks up completed transcriptions
8. AI enrichment: title, description, search summary
9. Speaker identification: ECAPA-TDNN embeddings (if PyTorch available)

## 6. Development Workflows

### Local Development

```bash
cd v2/backend
cp .env.example .env    # Configure Azure keys
uv sync                 # Install deps
uv run uvicorn app.main:app --reload --port 8000

cd v2/frontend
npm install
npm run dev             # Vite dev server on :5173
```

### Deploy to Azure

```bash
# 1. Build and push. This AUTO-BUMPS the patch number in backend/VERSION and
#    tags the image with the result, so do not bump it by hand first.
#    (Deps image is reused if Dockerfile.deps/pyproject.toml/uv.lock are unchanged.)
cd v2/deploy/scripts
./02-build-push.sh

# 2. Deploy and verify
./03-deploy-app.sh

# App settings can be changed in the same stopped window (no overlapping restart):
DEPLOY_APP_SETTINGS="KEY=value" ./03-deploy-app.sh
```

### Useful Commands

```bash
# Tail logs
az webapp log tail --name QuickScribeWebApp --resource-group QuickScribeResourceGroup

# Download live DB for inspection
./deploy/scripts/download-db.sh

# Upload local DB to production
./deploy/scripts/upload-db.sh

# Test upload via API key
curl -X POST https://quickscribe-v2.azurewebsites.net/api/recordings/upload \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@recording.m4a"
```

## 7. Known Limitations / TODOs

- **Speaker ID model download**: ECAPA-TDNN model downloads from HuggingFace on first use (~100MB). Could pre-bake into image.
- **Single instance only**: SQLite + Litestream requires exactly 1 App Service instance. Cannot scale out.
- **App Service pull time**: 2.65GB image takes ~2-3min to pull on restart. Cached layers help for subsequent deploys.
- **9 duplicate Plaud recordings**: Show as "new" each sync but get skipped by duplicate check. Need investigation.
- **No pagination cursor**: List endpoint uses offset pagination, not cursor-based.

## 8. Suggested Improvements or Considerations for AI Agents

- **VERSION file** is the source of truth for deployed version. Always bump this, not pyproject.toml version.
- **uv.lock** must be regenerated (`uv lock`) when changing dependencies in pyproject.toml.
- **Docker `--network host`** is passed for local Docker builds (DNS failed without it on the old WSL machine). Without local Docker, builds run in ACR via `az acr build`.
- **Deploy target** is pinned by `SUBSCRIPTION` in `deploy/scripts/config.local.sh` (gitignored); all deploy commands go through the `azs` wrapper in `config.sh`.
- **Azure Speech requires mono audio**. The `_transcode_to_mp3()` function in sync_service.py handles this with `-ac 1`.
- **API key auth** only works on the `/api/recordings/upload` endpoint. All other endpoints require Azure AD Bearer tokens.
- **Config secrets** are in Azure App Service settings, not in the container. Use `set-secrets.sh` to update.
- **Litestream** handles DB persistence across container restarts. Never rely on container filesystem for data.
