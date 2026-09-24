# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

| Resource | Location | Description |
|----------|----------|-------------|
| **System Description** | [`v2/SYSTEM_DESCRIPTION.md`](./v2/SYSTEM_DESCRIPTION.md) | Architecture, services, deploy scripts, runtime details |
| **Backend** | `v2/backend/` | FastAPI + async SQLite (aiosqlite) |
| **Frontend** | `v2/frontend/` | React 18 / TypeScript / Vite / Tailwind / shadcn |
| **Deploy** | `v2/deploy/` | Dockerfile, Litestream config, deploy scripts |
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

QuickScribe is a personal audio transcription application. It syncs recordings from
Plaud devices, transcribes them via Azure Speech Services, and layers AI features
(summaries, meeting notes, chat, speaker identification) on top.

**`v2/` is the only live system.** It is deployed as a single Docker container on
the `QuickScribeWebApp` Azure App Service. The earlier v1 stack (a Flask backend,
a separate React frontend, a Plaud sync Container Apps Job, and a CosmosDB
database) was fully decommissioned in July 2026 — its Azure resources were deleted
and its source removed from this repo. If you need it, it is in git history.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              QuickScribeWebApp (App Service)                  │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ React SPA      │  │ FastAPI      │  │ APScheduler      │  │
│  │ (served static)│──│ /api, /mcp   │──│ in-process jobs  │  │
│  └────────────────┘  └──────┬───────┘  └──────────────────┘  │
│                             │                                 │
│                    ┌────────▼─────────┐   ┌───────────────┐  │
│                    │ SQLite (WAL,FTS5)│──▶│  Litestream   │  │
│                    │  /app/data/app.db│   │ (replication) │  │
│                    └──────────────────┘   └───────┬───────┘  │
└───────────────────────────────────────────────────┼──────────┘
                    │              │                │
                    ▼              ▼                ▼
            ┌──────────────┐ ┌───────────┐ ┌────────────────┐
            │ Azure Speech │ │Azure OpenAI│ │  Blob Storage  │
            │ (transcribe) │ │ (AI feats) │ │ (audio + repl) │
            └──────────────┘ └───────────┘ └────────────────┘
```

### Critical constraints

- **Single instance only.** SQLite plus Litestream tolerates exactly one writer.
  Scaling the App Service beyond one replica corrupts the replica (this has
  happened before — a second App Service pointed at the same Litestream
  destination caused split-brain and had to be deleted).
- **The container filesystem is ephemeral** (`WEBSITES_ENABLE_APP_SERVICE_STORAGE=false`),
  so Litestream *is* the durability mechanism, not a convenience backup.
- **Never let the app checkpoint the WAL.** `PRAGMA wal_autocheckpoint=0` is set
  deliberately; Litestream owns checkpointing. Opening a second SQLite connection
  without replicating that pragma can destroy replicated WAL frames.

---

## Key Commands

```bash
make help          # List all targets
make setup         # Install backend + frontend dependencies
make run-backend   # FastAPI with reload on :8000
make run-frontend  # Vite dev server on :5173
make test          # Backend tests
make lint          # ruff + eslint

make version       # Show version that will be deployed
make deploy        # build-push then deploy-app
```

### Deploying

```bash
make deploy
```

`02-build-push.sh` **auto-increments the patch version** in `v2/backend/VERSION`
and tags the image with the result — do not bump it by hand first or you will
skip a version. Edit `VERSION` manually only when changing the major or minor
number, and set it to one below the value you want released.

`v2/backend/VERSION` is the source of truth for the deployed version, not
`pyproject.toml`.

`03-deploy-app.sh` stops the app, swaps the image, then starts it — deliberately
*not* `az webapp restart`, because App Service keeps the old container alive
during warm-up and two live containers would both write to the same Litestream
destination and split the database. It then polls `/api/health` until the
reported version matches, so a failed rollout surfaces as a timeout rather than
a silent no-op.

### Tests

```bash
cd v2/backend && PYTHONPATH=src uv run pytest tests/
```

`PYTHONPATH=src` is required — the app package is not installed.
`asyncio_mode = "auto"` is configured, so async tests need no decorator.

---

## Database

Async SQLite via `aiosqlite`, WAL mode, FTS5 for search. Schema lives in
`SCHEMA_SQL` / `FTS_SCHEMA_SQL` in `v2/backend/src/app/database.py` and is applied
idempotently on startup, with ad-hoc migrations in `_migrate_schema()`.

| Table | Purpose |
|-------|---------|
| `recordings` | Recording metadata **and** transcript columns (`transcript_text`, `diarized_text`, `transcript_json`, `speaker_mapping`) |
| `recordings_fts` | FTS5 index over titles, summaries, transcript text |
| `participants` / `speaker_profiles` | People and their ECAPA-TDNN voice embeddings |
| `collections` / `collection_items` | User-defined groupings |
| `tags` / `recording_tags` | Tagging |
| `sync_runs` / `run_logs` | Sync job history (pruned daily, see below) |
| `users`, `mcp_tokens`, `deleted_plaud_ids`, `search_traces` | Auth, MCP access, dedup, search debugging |

**Search** (`services/search_service.py`, `GET /api/search`, the Search page and the
Recordings-list box) is plain ranked FTS5, no LLM: two external-content indexes over the
`search_docs` view (`search_fts` stemmed, `search_exact_fts` for quoted phrases), kept in sync
by triggers on `recordings` and rebuilt on startup when `SEARCH_SCHEMA_SQL` changes (version
hash in `search_meta`). They are keyed on `recordings.rowid`, so don't `INSERT OR REPLACE`
into `recordings` or `VACUUM` without forcing a rebuild. "Ask AI" (`deep_search.py`) is the
LLM fallback; from the Search page it is scoped to the top keyword results. The older
`recordings_fts` index still serves MCP and collections.

The app shares **one** `aiosqlite` connection via `await get_db()`. Because of
that, avoid awaiting between a write and its `commit()` — an unrelated coroutine
can otherwise have its in-flight write committed by your code.

---

## Background Jobs

Registered in `v2/backend/src/app/scheduler/jobs.py` (APScheduler, in-process):

| Job | Interval | Purpose |
|-----|----------|---------|
| `plaud_sync_job` | `sync_interval_minutes` (15) | Pull new recordings from Plaud |
| `poll_transcriptions_job` | 5 min | Poll Azure Speech for completed jobs |
| `refresh_meeting_notes_job` | 60 min | Generate/regenerate meeting notes |
| `prune_run_history_job` | 24 h | Delete `sync_runs` older than `run_history_retention_days` (30) |

`plaud_sync_job` is only registered when the server-wide `PLAUD_ENABLED` setting
is true (the default); when false, manual triggers also return 409 and the UI
shows sync as disabled. Per-user sync is separately gated by `users.plaud_enabled`
and `users.plaud_token`.

`sync_runs` previously grew unbounded and reached 25k rows / 88 MB, which also
inflated every hourly Litestream snapshot. Any new per-run bookkeeping table needs
a retention story from the start.

---

## Plaud Integration

`v2/backend/src/app/services/plaud_client.py` talks to the Plaud API.

**Parse defensively.** Plaud adds fields to its API without notice; v1 crashed for
three weeks because it did `AudioFile(**file_data)` against a fixed dataclass.
`_parse_audio_file()` filters to known dataclass fields first — preserve that
behavior when touching this code.

Known quirk: Plaud `.opus` files are actually MP3.

---

## Authentication

- Azure AD via MSAL in the frontend, JWT validation in FastAPI (`app/auth.py`).
- API keys for uploads; opaque bearer tokens for MCP (`mcp_tokens`).
- EasyAuth is **not** used.
- `auth_disabled=True` in settings bypasses auth for local dev and tests.

---

## MCP Server

Exposed at `/mcp` with bearer-token auth, offering read-only tools for search,
recording/transcript retrieval, participants, tags, AI chat, meeting notes, and
cross-recording synthesis.

---

## Configuration

`v2/backend/src/app/config.py` (`pydantic-settings`, reads `.env`). Feature
availability is derived from whether credentials are present:

```python
from app.config import get_settings

settings = get_settings()
if settings.ai_enabled:      # azure_openai_endpoint and api_key both set
    ...
```

---

## Common Patterns

### Frontend styling (Tailwind + shadcn)

```typescript
import { cn } from "@/lib/utils";

// Good: merge conditionally with cn()
className={cn("mt-0.5 text-[13px]", isActive && "font-semibold")}
```

### Safe field access

```typescript
{recording.title || recording.original_filename}
recording?.description
```

---

## File Locations Reference

| What | Where |
|------|-------|
| DB schema & connection | `v2/backend/src/app/database.py` |
| Settings | `v2/backend/src/app/config.py` |
| API routes | `v2/backend/src/app/routers/` |
| Business logic | `v2/backend/src/app/services/` |
| Background jobs | `v2/backend/src/app/scheduler/jobs.py` |
| LLM prompts | `v2/backend/src/app/prompts/` |
| Version (source of truth) | `v2/backend/VERSION` |
| Frontend components | `v2/frontend/src/components/` |
| Dockerfile / Litestream | `v2/deploy/` |
| Deploy scripts | `v2/deploy/scripts/` |
