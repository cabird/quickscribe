# Gemini 3.1 Pro Review of QuickScribe Rewrite

**Model**: Gemini 3.1 Pro Preview (1M context)
**Date**: 2026-03-24

## Executive Summary

"Enterprise Architecture for a Personal App." The current system is built to handle thousands of concurrent users and enterprise compliance but is serving an audience of one (or a few).

---

## 1. Architecture: Modular Monolith (FastAPI or Litestar)

- **Merge Backend and Sync Service**: Run a single web service. Use in-process scheduler (APScheduler or FastAPI BackgroundTasks) for Plaud sync every 15 minutes. No separate Container App Job or distributed locks needed.
- **Drop the Transcoding Queue**: No Azure Storage Queues for single user. Transcode synchronously or in simple async background task.
- **Framework**: Switch to **FastAPI** for native async support (I/O heavy: polling Azure Speech, calling LLMs, downloading files) and auto-generated OpenAPI docs.

---

## 2. Data Store: SQLite (WAL mode) or PostgreSQL

- **CosmosDB is wrong tool**: Fake partition keys prove data is fundamentally relational forced into NoSQL, resulting in expensive cross-partition queries and complex application-side joins.
- **SQLite**: Single `data.db` file with WAL, blazingly fast, zero-cost, trivial backup. Use Turso for SQLite over HTTP if deploying to ephemeral PaaS.
- **PostgreSQL**: If persistent disk isn't available on target platform.
- **Merge Recording + Transcription**: YES. Strict 1:1 relationship. Separate creates distributed state bugs. Store `speaker_mapping` and `transcript_json` in JSON/JSONB columns.

---

## 3. What to Keep vs Drop

### Drop Aggressively
- **ECAPA-TDNN Speaker ID (1.5GB Docker Image)**: Drop entirely. **Alternative**: Rely on Azure Speech's built-in diarization + existing LLM prompt (`infer_speaker_names`) for context-based speaker identification. Let user manually correct in UI.
- **Admin Panel & Audit Logs**: Drop 1300+ lines of admin routes, ManualReviewItem queue, identificationHistory audit trails. Simple `status=failed` + error in standard UI.
- **TS-to-Python Model Generation**: Drop `datamodel-codegen`. Define source-of-truth in Python (Pydantic/FastAPI), generate TS types from Python via `pydantic2ts` or OpenAPI spec.

### Keep
- **Azure Blob Storage**: Databases shouldn't store 100MB audio files
- **Azure AD Auth**: If already working, keep it
- **Azure Speech & OpenAI**: Core AI engines, but simplify integration

---

## 4. Frontend: React Router v7 + TanStack Query

- **Routing**: Real URL routing (`/transcripts/:id`) for browser history, deep linking
- **State & Caching**: TanStack Query replaces CustomEvent bus and manual useEffect fetching. Automatic caching, background refetching, cross-component state invalidation.
- **Virtualization**: `@tanstack/react-virtual` for RecordingsList and TranscriptViewer. Thousands of DOM nodes for 2-hour transcript will freeze browser.

---

## 5. Sync Service: API-Direct Polling in Background Task

- **Ditch Swagger Client**: 120-file client is overkill for 3 endpoints. Write 50-line wrapper using httpx/requests.
- **Simplified Pipeline**: Cron -> fetch Plaud list -> filter -> download -> ffmpeg -> upload blob -> POST Azure Speech -> poll -> download JSON -> LLM title/desc -> save DB
- **Chunking**: Only chunk if Azure Speech rejects. Treat chunks as backend implementation detail, stitch transcript back together before saving.

---

## 6. Key Risks & Gotchas

1. **Plaud API is Undocumented**: Spoofing Chrome headers to hit `api.plaud.ai` WILL break. Keep Plaud client highly isolated. Map Plaud's AudioFile to generic Recording immediately.
2. **Blocking the Event Loop**: If sync moves into main backend, run ffmpeg and large downloads in thread pool (`asyncio.to_thread()`) to avoid blocking web server.
3. **Data Migration**: CosmosDB allowed arbitrary schema variations. Dirty data (missing fields, different date formats) will crash strict SQL inserts. Write robust sanitization script.
