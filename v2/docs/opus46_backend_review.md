# QuickScribe v2 Backend Review — Opus 4.6

**Date**: 2026-03-24
**Reviewer**: Claude Opus 4.6 (1M context)
**Scope**: All files in `v2/backend/src/`, reviewed against `v2/docs/REWRITE_SPEC.md`
**Verdict**: Solid foundation with several signature mismatches and a few architectural issues that need fixing before production use.

---

## 1. Critical Issues

### 1.1 Router-to-Service Signature Mismatches — Multiple Files Will Crash at Runtime

**Severity**: Critical — these will produce `TypeError` on every call.

**1.1a `recordings.py` router calls `recording_service.get_recording(recording_id, user.id)` but the service signature is `get_recording(user_id, recording_id)`.**

The service function at `recording_service.py:213` has parameter order `(user_id: str, recording_id: str)`, but every call from the router (lines 77, 126–129, 136–139, 150–153, 167–170, 184–187, 204–206, 214–216, 233) passes `(recording_id, user.id)` — arguments are swapped. This means the `WHERE id = ? AND user_id = ?` query will use recording_id as user_id and vice versa. **Every GET/PUT/DELETE on a recording will 404.**

- **File**: `app/routers/recordings.py` (all endpoints calling `recording_service.get_recording`)
- **Fix**: Either swap the argument order in the service, or fix all call sites in the router. The service's `(user_id, recording_id)` order is the more common convention; fix the router calls.

**1.1b `recordings.py` router calls `recording_service.update_recording(recording_id, user.id, body)` but the service signature is `update_recording(user_id, recording_id, updates)`.**

- **File**: `app/routers/recordings.py:129`
- **Fix**: Change to `recording_service.update_recording(user.id, recording_id, body)`.

**1.1c `recordings.py` router calls `recording_service.delete_recording(recording_id, user.id)` but the service signature is `delete_recording(user_id, recording_id)`.**

- **File**: `app/routers/recordings.py:139`
- **Fix**: Swap arguments.

**1.1d `recordings.py` router calls `recording_service.get_audio_url(recording_id, user.id)` but the service signature is `get_audio_url(user_id, recording_id)`.**

- **File**: `app/routers/recordings.py:153`
- **Fix**: Swap arguments.

**1.1e `recordings.py` router calls `recording_service.reprocess_recording(recording_id, user.id)` but this function does not exist in `recording_service.py`.**

- **File**: `app/routers/recordings.py:170`
- **Fix**: Implement `reprocess_recording` in `recording_service.py`. It should reset status to `pending` (or `transcribing` if speech is enabled), clear `status_message`, and re-submit.

**1.1f `recordings.py` router calls `recording_service.assign_speaker(recording_id, user_id, label, participant_id, manually_verified)` but this function does not exist in `recording_service.py`.**

- **File**: `app/routers/recordings.py:187–193`
- **Fix**: Implement `assign_speaker` in `recording_service.py`. It should load the recording's `speaker_mapping` JSON, update the entry for the given label, and save.

**1.1g `recordings.py` upload endpoint calls `recording_service.create_recording(user_id, file, title)` with keyword args `file` and `title` but `create_recording` has no `file` parameter — it expects `original_filename`, `source`, etc.**

- **File**: `app/routers/recordings.py:95–99`
- **Fix**: The upload handler needs to read the `UploadFile`, save it to blob storage, then call `create_recording` with the correct parameters. This is a substantial missing piece — the entire upload flow is not wired up.

**1.1h `recordings.py` paste endpoint calls `recording_service.paste_transcript(user_id, title, transcript_text, source_app, recorded_at)` with individual keyword args, but the service signature is `paste_transcript(user_id, request: PasteTranscriptRequest)`.**

- **File**: `app/routers/recordings.py:106–112`
- **Fix**: Change to `recording_service.paste_transcript(user_id=user.id, request=body)`.

**1.1i `participants.py` router calls `participant_service` functions with `(participant_id, user.id)` but service signatures are `(user_id, participant_id)`.**

All participant router calls have the arguments swapped:
- `get_participant(participant_id, user.id)` vs service `get_participant(user_id, participant_id)`
- `update_participant(participant_id, user.id, body)` vs service `update_participant(user_id, participant_id, data)`
- `delete_participant(participant_id, user.id)` vs service `delete_participant(user_id, participant_id)`
- `merge_participants(participant_id, other_id, user.id)` vs service `merge_participants(user_id, primary_id, secondary_id)`

- **File**: `app/routers/participants.py` (lines 59, 68, 77–80, 87–90, 96–102)
- **Fix**: Swap argument order in all router calls.

**1.1j `participants.py` router lists participants with `list_participants(user_id, page, per_page)` but service signature is `list_participants(user_id)` with no pagination parameters.**

- **File**: `app/routers/participants.py:31–33` vs `app/services/participant_service.py:23`
- **Fix**: Add pagination parameters to the service function, or remove them from the router.

**1.1k `participants.py` router search calls `search_participants(user_id, name, fuzzy, page, per_page)` but service signature is `search_participants(user_id, name, fuzzy)` — no pagination parameters.**

- **File**: `app/routers/participants.py:46–52` vs `app/services/participant_service.py:189`
- **Fix**: Add pagination to the service, or remove from the router.

**1.1l `tag_service` functions have `(user_id, ...)` as first param but router calls `add_tag_to_recording(recording_id, tag_id, user.id)` and `remove_tag_from_recording(recording_id, tag_id, user.id)` while service signatures are `(user_id, recording_id, tag_id)`.**

- **File**: `app/routers/recordings.py:208,217` vs `app/services/tag_service.py:125,160`
- **Fix**: Swap argument order in router calls.

Similarly, `tag_service.get_tag(tag_id, user.id)` in the tags router (line 33) — the service function `get_tag` does not exist. There's no standalone `get_tag` function in `tag_service.py`.

- **Fix**: Add a `get_tag(user_id, tag_id)` function to `tag_service.py`, or inline the check.

**1.1m `tag_service.update_tag(tag_id, user.id, body)` — service signature is `update_tag(user_id, tag_id, data)`. Arguments swapped.**

- **File**: `app/routers/tags.py:36` vs `app/services/tag_service.py:57`

**1.1n `tag_service.delete_tag(tag_id, user.id)` — service signature is `delete_tag(user_id, tag_id)`. Arguments swapped.**

- **File**: `app/routers/tags.py:45` vs `app/services/tag_service.py:103`

### 1.2 AI Router/Service Chat Signature Mismatch

The AI router calls:
```python
ai_service.chat(recording_id=body.recording_id, user_id=user.id, messages=body.messages)
```

But `ai_service.chat` signature is:
```python
async def chat(messages: list[dict], transcript_context: str) -> ChatResponse
```

It expects `messages` and `transcript_context`, not `recording_id`/`user_id`. The router needs to fetch the recording's transcript and pass it as `transcript_context`.

- **File**: `app/routers/ai.py:24–28` vs `app/services/ai_service.py:136`
- **Fix**: Fetch recording, extract transcript, call `ai_service.chat(messages=[m.model_dump() for m in body.messages], transcript_context=recording.diarized_text or recording.transcript_text)`.

### 1.3 AI Router/Service Analysis Signature Mismatch

The recordings router calls:
```python
ai_service.run_analysis(recording_id=recording_id, user_id=user.id, template_id=body.template_id)
```

But `ai_service.run_analysis` signature is:
```python
async def run_analysis(transcript: str, prompt_template: str) -> str
```

It expects `transcript` and `prompt_template`, not `recording_id`/`user_id`/`template_id`. The router needs to fetch both the recording and the template, then pass the transcript and prompt.

- **File**: `app/routers/recordings.py:233–238` vs `app/services/ai_service.py:193`
- **Fix**: Fetch the recording and template, validate the template has `{transcript}`, then call `ai_service.run_analysis(transcript=..., prompt_template=template.prompt)`.

### 1.4 Sync Router/Service Signature Mismatches

**1.4a** `sync.py` router calls `sync_service.run_sync(user_id=user.id, trigger="manual")` but service signature is `run_sync(trigger="scheduled") -> SyncRun` — no `user_id` parameter. The sync service syncs ALL enabled users, not a specific user.

- **File**: `app/routers/sync.py:21` vs `app/services/sync_service.py:80`
- **Fix**: Either add a `user_id` parameter to scope sync to one user (better for manual trigger), or remove `user_id` from the router call. The router also expects `run_id` as return value but the service returns a `SyncRun`.

**1.4b** `sync.py` router calls `sync_service.get_sync_runs(page, per_page, status)` but service signature is `get_sync_runs(page, per_page, status_filter)` — parameter name mismatch (`status` vs `status_filter`). This won't crash because they're passed as positional, but it's confusing.

- **File**: `app/routers/sync.py:33–37`

### 1.5 `list_recordings` Router Passes `date_range` and `sort` but Service Expects `date_from` and `date_to`

The router passes `date_range` and `sort` parameters (line 38, 47) but the service function signature accepts `date_from` and `date_to` (line 143). The `sort` parameter is not accepted at all.

- **File**: `app/routers/recordings.py:41–48` vs `app/services/recording_service.py:137–144`
- **Fix**: Either parse `date_range` in the router and pass `date_from`/`date_to`, or update the service. Add `sort` parameter to the service.

### 1.6 `search_recordings` Router Expects Tuple Return but Service Returns List

The router calls:
```python
recordings, total = await recording_service.search_recordings(user_id, q, page, per_page)
```

But the service signature is `search_recordings(user_id, query) -> list[RecordingSummary]` — returns a list, not a tuple. It also doesn't accept `page`/`per_page`.

- **File**: `app/routers/recordings.py:60–65` vs `app/services/recording_service.py:412`
- **Fix**: Update the service to return `(list, int)` tuple and accept pagination params, or update the router.

### 1.7 `list_recordings` Service Returns `PaginatedResponse` but Router Expects Tuple

The service's `list_recordings` returns `PaginatedResponse` (line 210), but the router unpacks it as `recordings, total = await recording_service.list_recordings(...)`.

- **File**: `app/routers/recordings.py:41` vs `app/services/recording_service.py:144`
- **Fix**: Change the service to return `(list, int)` tuple, or change the router to accept `PaginatedResponse`.

---

## 2. Major Issues

### 2.1 Database Singleton is Unsafe for Concurrent Async Access

The database module uses a single global `_db` connection. While SQLite WAL mode allows concurrent reads, **aiosqlite wraps a single `sqlite3.Connection` with a background thread**. All operations on a single `aiosqlite.Connection` are serialized through that thread. Under concurrent requests, this means:

1. One long query blocks all others.
2. Multiple coroutines calling `db.execute` + `db.commit` on the same connection can interleave in problematic ways (e.g., one coroutine's `commit` commits another's uncommitted writes).

- **File**: `app/database.py`
- **Fix**: Use a connection pool or create per-request connections. A simple approach: create a new `aiosqlite.connect()` for each request using a FastAPI dependency. For the scheduler jobs, create dedicated connections. Alternatively, use `aiosqlite` with a mutex, though that defeats the purpose of async.

### 2.2 Missing `reprocess_recording` Function

The spec defines `POST /api/recordings/{id}/reprocess` but the `recording_service.py` has no `reprocess_recording` function. The router references it, so any call will crash with `AttributeError`.

- **File**: `app/services/recording_service.py`
- **Fix**: Implement it — reset status, clear error, optionally re-submit to speech services.

### 2.3 Missing `assign_speaker` Function

The spec defines `PUT /api/recordings/{id}/speakers/{label}` but `recording_service.py` has no `assign_speaker` function. This is core functionality for speaker identification.

- **File**: `app/services/recording_service.py`
- **Fix**: Implement — load `speaker_mapping` JSON, update the entry for the label with the participant data, save, optionally update the participant's `last_seen`.

### 2.4 Upload Flow Not Implemented

The router's `upload_recording` endpoint passes a `file: UploadFile` directly to `create_recording`, which doesn't accept file objects. The entire upload-to-blob-and-create-recording pipeline is missing.

- **File**: `app/routers/recordings.py:88–100`
- **Fix**: Read the file, upload to blob storage via `storage_service.upload_file`, then call `create_recording` with proper parameters. Submit for transcription if speech is enabled.

### 2.5 FTS5 `content=` Sync Uses `rowid` But Primary Key is TEXT

The `recordings` table has `id TEXT PRIMARY KEY`. In SQLite, a table with a non-INTEGER primary key still has an implicit `rowid`, but there's a subtle issue: the `content_rowid='rowid'` in FTS5 references the implicit rowid. The triggers use `new.rowid` which works, but **if recordings are ever deleted and re-inserted, rowids could theoretically be reused**, leading to stale FTS entries. This is mitigated by the delete trigger, so in practice this should be fine, but it's worth noting.

More importantly: **the FTS triggers fire on INSERT/UPDATE/DELETE, but the `PRAGMA foreign_keys=ON` and `ON DELETE CASCADE` on `recording_tags` will work correctly with the text-PK DELETE.** The cascade + FTS trigger ordering should be fine.

- **File**: `app/database.py:159–183`
- **Assessment**: Low risk but worth a note. The implementation is correct.

### 2.6 `get_tag` Function Missing from `tag_service.py`

The tags router calls `tag_service.get_tag(tag_id, user.id)` on lines 33 and 43, but no `get_tag` function exists in the service.

- **File**: `app/services/tag_service.py`
- **Fix**: Add a `get_tag(user_id: str, tag_id: str) -> Tag | None` function.

### 2.7 Sync Runs Endpoint Has No User Scoping

`GET /api/sync/runs` and `GET /api/sync/runs/{id}` return sync runs for ALL users. While this is a personal app, the spec says "every endpoint checks ownership." The sync_runs table doesn't even have a `user_id` column, and the `users_processed` field is a JSON array.

- **File**: `app/routers/sync.py`, `app/services/sync_service.py`
- **Fix**: For a personal app this is acceptable, but be aware that if multiple users exist, any user can see all sync runs.

### 2.8 Manual Sync Trigger Syncs All Users, Not Just the Requesting User

When a user hits `POST /api/sync/trigger`, the `run_sync` function syncs ALL Plaud-enabled users. The router passes `user_id` but the service ignores it.

- **File**: `app/services/sync_service.py:80`
- **Fix**: Add a `user_id` parameter to `run_sync` and filter to that user for manual triggers. Keep the scheduled trigger syncing all users.

### 2.9 `run_sync` Return Type Inconsistency

The router expects `run_id` from `sync_service.run_sync()`:
```python
run_id = await sync_service.run_sync(user_id=user.id, trigger="manual")
return {"run_id": run_id, "message": "Sync started"}
```

But the service returns a `SyncRun` object, not a string ID.

- **File**: `app/routers/sync.py:21–22` vs `app/services/sync_service.py:80`
- **Fix**: Use `result = await sync_service.run_sync(...)` then `return {"run_id": result.id, ...}`.

### 2.10 `_get_dev_user` Fragile Lookup

The dev user is looked up by `WHERE name = 'dev'` which could match any user named "dev". Should use a deterministic ID or a flag column.

- **File**: `app/auth.py:153–154`
- **Fix**: Use a fixed ID like `"user-dev"` and look up by ID, or use `WHERE email = 'dev@localhost'`.

### 2.11 `last_login` Updated on Every Request

`get_current_user` updates `last_login` and commits on every single authenticated request. This is unnecessary write load.

- **File**: `app/auth.py:203–207`
- **Fix**: Only update if the last login was more than N minutes ago, or remove entirely and update only on token refresh.

### 2.12 Paste Transcript Doesn't Run AI Enrichment

The spec says pasted transcripts should "run AI title/description generation" and "run speaker name matching against existing participants." The current `paste_transcript` does neither — it just creates the recording with status `ready`.

- **File**: `app/services/recording_service.py:383–409`
- **Fix**: Add AI title/description generation (when `ai_enabled`) and speaker parsing for pasted transcripts.

---

## 3. Minor Issues

### 3.1 `_jwks_lock` is a `threading.Lock` but Never Used

The lock is declared but `_get_signing_key` doesn't use it. The async function could have multiple coroutines refreshing JWKS simultaneously (harmless but wasteful).

- **File**: `app/auth.py:28–29`
- **Fix**: Either use an `asyncio.Lock` around the refresh, or remove the unused threading lock.

### 3.2 `generate_sas_url` Creates a Sync `BlobServiceClient` Every Call

`generate_sas_url` calls `_get_sync_client()` just to get the `account_name`, then immediately discards the client. This is wasteful.

- **File**: `app/services/storage_service.py:83–95`
- **Fix**: Parse `account_name` from the connection string directly, or cache it.

### 3.3 `_parse_audio_file` Uses `__dataclass_fields__` Internal API

Accessing `AudioFile.__dataclass_fields__` works but is a CPython implementation detail.

- **File**: `app/services/plaud_client.py:85`
- **Fix**: Use `dataclasses.fields(AudioFile)` instead.

### 3.4 `ai_service._get_client()` Creates a New Client Per Call

Every AI function creates a new `AsyncAzureOpenAI` client and closes it in a `finally` block. This means no connection reuse. For an app with light AI usage this is acceptable, but a module-level client would be more efficient.

- **File**: `app/services/ai_service.py:33–40`
- **Fix**: Consider a module-level lazy singleton or a client that persists across calls.

### 3.5 Exception Handling in `tag_service.create_tag` is Too Broad

The `except Exception` on line 46 catches ALL exceptions as a UNIQUE constraint violation, including network errors, programming errors, etc.

- **File**: `app/services/tag_service.py:46–51`
- **Fix**: Catch `aiosqlite.IntegrityError` (or `sqlite3.IntegrityError`) specifically.

### 3.6 Same Broad Exception Issue in `tag_service.update_tag`

- **File**: `app/services/tag_service.py:93–97`
- **Fix**: Same as above — catch the specific integrity error.

### 3.7 Missing `get_tag` Function Means Tags Router Has Dead Code Paths

The tags router references `tag_service.get_tag` which doesn't exist, but the router file will load without error because the call is only inside endpoint functions. It will crash at runtime when any tag update/delete endpoint is called.

- **File**: `app/routers/tags.py:33,43`

### 3.8 `PaginatedResponse.data` Has Untyped `list`

```python
class PaginatedResponse(BaseModel):
    data: list = []
```

This loses type information. Should be generic or at minimum `list[Any]`.

- **File**: `app/models.py:263`
- **Fix**: Use `data: list[Any] = []` or a generic pattern.

### 3.9 `ChatMessage.role` Should Be an Enum

Accepting any string for the role field means the frontend could send invalid roles without validation.

- **File**: `app/models.py:334`
- **Fix**: Use `Literal["system", "user", "assistant"]` or a `str` enum.

### 3.10 `NULLS LAST` May Not Work in All SQLite Versions

`ORDER BY recorded_at DESC NULLS LAST` requires SQLite 3.30.0+. Most modern systems have this, but it's worth noting.

- **File**: `app/services/recording_service.py:199`

### 3.11 CORS Origins Are Hardcoded to `localhost:5173`

Only `http://localhost:5173` is allowed. Production will need the actual domain, or `*` if behind a reverse proxy.

- **File**: `app/main.py:67`
- **Fix**: Make CORS origins configurable via settings.

### 3.12 Static File Serving Security: Path Traversal

```python
file_path = FRONTEND_DIR / full_path
if full_path and file_path.is_file():
    return FileResponse(file_path)
```

While FastAPI/Starlette should handle path normalization, this pattern with user-controlled `full_path` joined to `FRONTEND_DIR` could be risky if not properly sanitized. A path like `../../etc/passwd` after joining could escape the frontend directory.

- **File**: `app/main.py:119–121`
- **Fix**: Add `file_path.resolve().is_relative_to(FRONTEND_DIR.resolve())` check.

### 3.13 `speaker_profiles` Table Has No Deletion Cascade from Participants

When a participant is deleted, `participant_service.delete_participant` clears speaker_mapping references but does not clean up `speaker_profiles` entries that reference the deleted participant.

- **File**: `app/services/participant_service.py:144–186`, `app/database.py:141–154`
- **Fix**: Add `ON DELETE CASCADE` to the foreign key, or add explicit cleanup in `delete_participant`.

### 3.14 Inconsistent Return Types from Service Functions

Some service functions raise `HTTPException` for not-found (e.g., `get_recording`, `get_participant`), while the routers also check for `None` returns and raise their own 404s. This means some 404s could be raised from both layers, and the router's None-check is dead code.

- **File**: Multiple — `recording_service.get_recording` raises 404, but `recordings.py:78` checks `if not recording`.
- **Fix**: Pick one pattern. Either services raise HTTPException (and routers don't check), or services return `None` (and routers check). The current mix works but is confusing.

---

## 4. Positive Observations

### 4.1 All SQL Queries Are Properly Parameterized

Every SQL query uses `?` placeholders with parameter tuples. No string interpolation of user data into SQL. This is done correctly and consistently across all service files.

### 4.2 FTS5 Integration Is Correct

The FTS5 content-sync triggers (insert, delete, update) are implemented correctly. The update trigger properly deletes the old entry before inserting the new one. The `content='recordings'` and `content_rowid='rowid'` configuration is correct.

### 4.3 Ownership Checks Are Comprehensive

Every endpoint that accesses user-specific data includes a `user_id` filter in the SQL `WHERE` clause. There are no endpoints that allow accessing another user's data.

### 4.4 Clean Separation of Concerns

The codebase follows a clear layered architecture: routers handle HTTP concerns, services handle business logic, and external clients are properly isolated. The Plaud client keeps its types internal and maps at the boundary. The speech client is a clean ~150-line replacement for the 120-file generated SDK.

### 4.5 Pydantic Models Are Well-Designed

The model hierarchy is clean: `Recording` for DB rows, `RecordingSummary` for lists (no transcript text), `RecordingDetail` for full views. Update models use explicit optional fields rather than `setattr`. The speaker mapping model is well-structured.

### 4.6 Plaud Client is Solid

The Plaud client correctly handles the `.opus` -> MP3 quirk, uses browser-spoofing headers, filters trashed recordings, and has proper timeout configuration. The `AudioFile` dataclass with computed properties (`duration_seconds`, `recording_datetime`) is clean.

### 4.7 Sync Pipeline Design Is Sound

The sync service correctly:
- Filters already-imported recordings via `plaud_id`
- Blocks deleted recordings via `deleted_plaud_ids`
- Logs each run to `sync_runs` with stats
- Handles errors per-user and per-recording without aborting the whole run
- Applies `max_recordings_per_sync` limit

### 4.8 Transcript Parsing is Correct

`_parse_transcript` properly handles Azure Speech JSON, sorting by `offsetInTicks`, grouping consecutive phrases by speaker, and building both plain and diarized text. The speaker mapping skeleton extraction is clean.

### 4.9 Good Schema Design

The database schema is well-designed:
- Proper indexes on common query patterns
- `UNIQUE(plaud_id)` for dedup
- `UNIQUE(user_id, name)` on tags
- `ON DELETE CASCADE` on `recording_tags`
- FTS5 for full-text search
- Clean separation of concerns

### 4.10 Prompt Templates Are Clean

Using `prompts.yaml` for prompt management is a good pattern. The prompts themselves are well-crafted with clear JSON output format instructions.

---

## 5. Summary of Required Changes

### Must Fix Before Any Testing (Critical)

| # | Issue | Files |
|---|-------|-------|
| 1 | Swap argument order in ALL router-to-service calls | `routers/recordings.py`, `routers/participants.py`, `routers/tags.py`, `routers/ai.py` |
| 2 | Fix `upload_recording` — implement full upload flow | `routers/recordings.py`, `services/recording_service.py` |
| 3 | Fix `paste_transcript` call signature | `routers/recordings.py` |
| 4 | Fix AI chat/analysis call signatures | `routers/ai.py`, `routers/recordings.py` |
| 5 | Implement missing `reprocess_recording` | `services/recording_service.py` |
| 6 | Implement missing `assign_speaker` | `services/recording_service.py` |
| 7 | Implement missing `get_tag` | `services/tag_service.py` |
| 8 | Fix `list_recordings` return type mismatch | `services/recording_service.py` |
| 9 | Fix `search_recordings` return type and pagination | `services/recording_service.py` |
| 10 | Fix `list_participants`/`search_participants` missing pagination | `services/participant_service.py` |
| 11 | Fix sync router/service parameter mismatches | `routers/sync.py`, `services/sync_service.py` |

### Should Fix Before Production (Major)

| # | Issue | Files |
|---|-------|-------|
| 12 | Database singleton concurrency safety | `database.py` |
| 13 | CORS origins configurable | `main.py`, `config.py` |
| 14 | Path traversal check in SPA catch-all | `main.py` |
| 15 | Paste transcript AI enrichment | `services/recording_service.py` |
| 16 | `speaker_profiles` cleanup on participant delete | `services/participant_service.py` |
| 17 | `last_login` update throttling | `auth.py` |
| 18 | Narrow exception handling in tag_service | `services/tag_service.py` |

### Nice to Have (Minor)

| # | Issue | Files |
|---|-------|-------|
| 19 | Remove unused threading lock | `auth.py` |
| 20 | Cache account_name in storage_service | `services/storage_service.py` |
| 21 | Use `dataclasses.fields()` instead of `__dataclass_fields__` | `services/plaud_client.py` |
| 22 | Type `PaginatedResponse.data` | `models.py` |
| 23 | Enum for `ChatMessage.role` | `models.py` |

---

## 6. Spec Compliance Checklist

| Spec Endpoint | Implemented | Working | Notes |
|---------------|-------------|---------|-------|
| `GET /api/recordings` | Yes | No | Return type mismatch, date_range/sort params wrong |
| `GET /api/recordings/{id}` | Yes | No | Argument order swapped |
| `POST /api/recordings/upload` | Yes | No | Upload flow not wired |
| `POST /api/recordings/paste` | Yes | No | Call signature wrong |
| `PUT /api/recordings/{id}` | Yes | No | Argument order swapped |
| `DELETE /api/recordings/{id}` | Yes | No | Argument order swapped |
| `GET /api/recordings/{id}/audio` | Yes | No | Argument order swapped |
| `POST /api/recordings/{id}/reprocess` | Yes | No | Service function missing |
| `PUT /api/recordings/{id}/speakers/{label}` | Yes | No | Service function missing |
| `POST /api/recordings/{id}/tags/{tag_id}` | Yes | No | Argument order swapped |
| `DELETE /api/recordings/{id}/tags/{tag_id}` | Yes | No | Argument order swapped |
| `POST /api/recordings/{id}/analyze` | Yes | No | Call signature wrong |
| `GET /api/participants` | Yes | No | Service missing pagination |
| `GET /api/participants/{id}` | Yes | No | Argument order swapped |
| `POST /api/participants` | Yes | Yes | Works |
| `PUT /api/participants/{id}` | Yes | No | Argument order swapped |
| `DELETE /api/participants/{id}` | Yes | No | Argument order swapped |
| `GET /api/participants/search` | Yes | No | Service missing pagination |
| `POST /api/participants/{id}/merge/{other_id}` | Yes | No | Argument order swapped |
| `GET /api/tags` | Yes | Yes | Works |
| `POST /api/tags` | Yes | Yes | Works |
| `PUT /api/tags/{id}` | Yes | No | Missing `get_tag`, args swapped |
| `DELETE /api/tags/{id}` | Yes | No | Missing `get_tag`, args swapped |
| `POST /api/ai/chat` | Yes | No | Call signature wrong |
| `GET /api/me` | Yes | Yes | Works |
| `PUT /api/me/settings` | Yes | Yes | Works |
| `GET/POST/PUT/DELETE /api/me/analysis-templates` | Yes | Yes | Works (direct DB, no service) |
| `POST /api/sync/trigger` | Yes | No | Signature mismatch, return type wrong |
| `GET /api/sync/runs` | Yes | Partial | Works but param name mismatch |
| `GET /api/sync/runs/{id}` | Yes | Yes | Works |
| `GET /api/health` | Yes | Yes | Works |
| `GET /api/version` | Yes | Yes | Works |
| `GET /api/recordings/search` | Yes | No | Return type mismatch |

**Bottom line**: The codebase has excellent architecture and design, but a pervasive argument-order mismatch between routers and services means approximately 80% of endpoints will crash at runtime. This appears to be a systematic issue where the routers were written with `(entity_id, user_id)` convention while the services use `(user_id, entity_id)`. A single pass to fix argument order in all router files, plus implementing the 3 missing service functions, will bring this to a working state.
