# GPT-5.4 Review of QuickScribe Rewrite

**Model**: GPT-5.4 (1M context)
**Date**: 2026-03-24

## Executive Summary

QuickScribe is carrying **multi-tenant SaaS / enterprise workflow complexity** for what is really a **single-user or very-small-user personal productivity app**.

Top-level recommendation:
- **Collapse the architecture**
- **Move off CosmosDB**
- **Merge Recording + Transcription at the data model level**
- **Delete the speaker ML pipeline unless it is genuinely a must-have differentiator**
- **Keep Plaud sync, transcript viewing/editing, manual speaker assignment, tags, chat, and title/summary generation**
- **Rebuild the frontend around real routes + TanStack Query + a much smaller view model**
- **Replace the shared library with a thin common package only if you still have 2+ Python services; otherwise delete it**

---

## 1. Architecture Recommendations

### Recommended Target: Single Python app + relational DB + blob/local file storage + one background worker

**Option A (strongest recommendation):**
- **Backend**: FastAPI or Flask
- **Database**: SQLite first, PostgreSQL if you want hosted durability/multi-device concurrency
- **Audio storage**: Local filesystem if self-hosted, or Azure Blob/S3/Cloudflare R2 for cloud
- **Background jobs**: Simple in-process/background task runner (Dramatiq/RQ/APScheduler)
- **Frontend**: React + router + query cache
- **Sync job**: Built into same app or tiny separate worker

### Why FastAPI over Flask
- Cleaner request/response typing
- Better Pydantic integration
- Auto OpenAPI docs
- Nicer async options
- Better fit for greenfield rewrite

### Replace the Shared Library?
- If **one deployable app**: delete the shared library entirely
- If **web app + sync worker**: keep a tiny common package with only models, config, Plaud client, and speech/openai adapters
- Do NOT recreate handler factories, generated models, or backend-coupled abstractions

---

## 2. Data Store Recommendation

### Verdict: CosmosDB is overkill
- Fake/static partition keys
- Cross-partition queries everywhere
- One-container pseudo-table design
- Cost/complexity mismatched to app size

### Default: PostgreSQL
- Perfect for relational modeling
- JSONB for flexible schema where needed
- Easy filtering/search/sorting
- Easy migrations, backups, exports

### Lowest-complexity: SQLite
- Dead simple, zero infra
- WAL mode for light concurrency
- Perfect for single-container deployment

### Merge Recording + Transcription: YES
- 1:1 relationship creates orphan risk, duplicated status fields, extra reads
- One `recordings` table with metadata + processing + transcript + speaker mapping + AI fields
- If transcript payload gets too large, split into secondary table later

---

## 3. What to Keep vs Drop

### Definitely Keep
1. Auth (Azure AD or simpler)
2. Recordings list/detail/delete/update
3. Plaud sync
4. Upload
5. Transcription retrieval
6. Audio playback/file serving
7. AI title + summary generation
8. Manual speaker assignment
9. Participants/known people (simplified)
10. Chat with transcript context
11. Tags (if actually used)

### Maybe Keep
12. Analysis templates (or replace with 3-5 hardcoded actions)

### Drop Aggressively
- Admin panel (~1330 lines)
- Speaker review queue / audit workflow (enterprise workflow software)
- ML speaker identification pipeline (ECAPA-TDNN, PyTorch, SpeechBrain)
- Manual review items
- Distributed locks (use DB transactions)
- Sync progress entity
- Codegen pipeline for models

### Speaker ID Alternative
- Keep lightweight heuristic: use transcript text, reuse participant names, LLM-assisted suggestions
- Always manual override
- No PyTorch/SpeechBrain

---

## 4. Frontend Approach

### Must-Have Changes
1. **Real route-based navigation** (`/recordings`, `/recordings/:id`, `/people`, `/settings`)
2. **TanStack Query** for server state (caching, stale-while-revalidate, mutation invalidation)
3. **Replace CustomEvents** with query invalidation + router state
4. **Paginate/infinite-scroll** recordings (server-side)
5. **Virtualize** recordings and people lists
6. **Add upload UI**
7. **Real search** (SQLite FTS5 or Postgres full-text)

### Recommended Stack
- React + TypeScript + Vite
- React Router
- TanStack Query
- Fluent UI v9 (or lighter alternative)
- Maybe Zustand for client state (probably not needed)

### Core Views
1. Recordings list
2. Recording detail
3. People
4. Settings
5. Optional: Search, Debug/Jobs

---

## 5. Sync Service Simplification

### Simplified Flow
1. Load enabled users
2. Fetch Plaud recordings list
3. Filter already imported / deleted
4. Download audio
5. Normalize to MP3
6. Store audio
7. Create recording row
8. Submit transcription job
9. Poll job status
10. On completion: store transcript + generate title/summary

### Remove
- Speaker embedding extraction
- Profile DB
- Rerating/training
- Distributed lock complexity
- Heavy job execution documents

### Azure Speech Client
- Replace ~120-file generated Swagger client with <200 line handwritten client
- Only needs: create job, get job, list files, download transcript

### Deployment
- Small internal worker module in same codebase
- Run as scheduled task, CLI cron command, or separate process

---

## 6. Key Risks

1. **Rewriting away real workflows** - Classify features as used weekly / occasionally / never before deleting
2. **Data migration complexity** - Careful mapping of all IDs, speaker mappings, Plaud metadata, deleted items blocklist
3. **Auth simplification exposure** - Keep real auth if internet-exposed
4. **Transcript storage size** - Don't return transcript JSON in list endpoints
5. **Search quality** - Essential as recordings accumulate; implement FTS early
6. **Background job idempotency** - Same Plaud item imported once, deleted items never re-imported, safe partial failure recovery
7. **Provider coupling** - Introduce thin boundaries for storage, transcription, LLM, auth
8. **Over-correcting into under-engineering** - Don't store everything as giant JSON blob
9. **Preserving transcript semantics** - Diarized text, merged segments, timestamps for playback
10. **Audio storage strategy** - Decide local vs blob, retention, backup, exports early

---

## Recommended Rewrite Phases

1. **Phase 1**: Define minimal product scope
2. **Phase 2**: Migrate data model (relational schema + Cosmos migration)
3. **Phase 3**: Rebuild backend (re-design API around reduced product)
4. **Phase 4**: Rebuild frontend (route-based, query-cached, fewer views)
5. **Phase 5**: Selectively reintroduce features (tags, search, analyses, debug jobs)
6. **Phase 6**: Decide if speaker automation deserves a second life
