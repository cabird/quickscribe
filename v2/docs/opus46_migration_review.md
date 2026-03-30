# Migration Script & Storage Service Review

**Reviewer**: Claude Opus 4.6
**Date**: 2026-03-24
**Files reviewed**:
- `v2/tools/migrate.py`
- `v2/backend/src/app/services/storage_service.py`
- `v2/backend/src/app/config.py`
- `v2/backend/src/app/main.py`
- `v2/backend/src/app/database.py`

Findings are ordered by severity: CRITICAL > HIGH > MEDIUM > LOW.

---

## 1. Migration Correctness

### CRITICAL: Only one CosmosDB container is queried — all others are missed

**File**: `migrate.py`, lines 133–188

The migration reads from a single CosmosDB container (`config.cosmos_container`, defaulting to `"recordings"`). However, v1 uses **5 separate Cosmos containers** as documented in the project CLAUDE.md:

| Container | Partition Key | Purpose |
|-----------|---------------|---------|
| `recordings` | `userId` | Audio recording metadata |
| `users` | `id` | User profiles, Plaud settings |
| `transcriptions` | `userId` | Transcript text, speaker diarization |
| `job_executions` | `partitionKey` | Plaud sync job logs |
| `deleted_items` | `userId` | Soft-delete tracking |

The script's `read_cosmos_documents()` queries `SELECT * FROM c` on one container and then tries to classify documents by `type`/`partitionKey` fields (lines 163–182). This will only work if all documents happen to live in one container. Based on the v1 architecture, **users, transcriptions, and deleted_items live in separate containers**, so the migration will silently produce 0 users, 0 transcriptions, and 0 deleted items.

**Fix**: Query each container separately:
```python
for container_name in ["recordings", "users", "transcriptions", "deleted_items", "job_executions"]:
    container = database.get_container_client(container_name)
    docs = list(container.query_items(...))
```

### CRITICAL: `transcript_json` is not serialized to JSON string

**File**: `migrate.py`, line 441

```python
tx.get("transcript_json") if tx else None,
```

The v1 `Transcription.transcript_json` field is typed as `string` in the TypeScript model, but in CosmosDB it may be stored as a parsed JSON object (since Cosmos stores JSON natively). If it comes back as a `dict`, inserting it directly into SQLite will call `str()` on it, producing Python repr format (`{'key': 'value'}`) instead of valid JSON. This would break any frontend code trying to `JSON.parse()` the field.

**Fix**: Apply `json.dumps()` like is done for `speaker_mapping` and `plaud_metadata_json`:
```python
json.dumps(tx.get("transcript_json")) if tx and tx.get("transcript_json") and isinstance(tx["transcript_json"], (dict, list)) else tx.get("transcript_json") if tx else None,
```

### HIGH: `analysisResults` from Transcription are silently dropped

**File**: `migrate.py` — not present

The v1 `Transcription` model includes `analysisResults?: AnalysisResult[]` (see `shared/Models.ts`, line 373). These are AI-generated analysis results. The migration does not preserve them. The v2 schema has `analysis_templates` but no `analysis_results` table, so there may be nowhere to put them — but this should be called out as a conscious decision, not a silent drop.

### HIGH: `settings_json` is never populated for users

**File**: `migrate.py`, lines 321–337

The `users` table has a `settings_json` column, but the migration INSERT doesn't include it. The v1 User model has `plaudSettings` (partially extracted to `plaud_enabled`, `plaud_token`, `plaud_last_sync`), but other settings fields like `activeSyncToken`, `activeSyncStarted`, and any future settings are lost. The `settings_json` column should store whatever doesn't have a dedicated column.

### HIGH: `az_raw_transcription` is dropped

The v1 `Transcription` model includes `az_raw_transcription` (the raw Azure transcription JSON). This is not migrated and there's no column for it in v2. If this data is needed for debugging or reprocessing, it's gone after migration.

### MEDIUM: User `userId` field mismatch in v1 recordings

**File**: `migrate.py`, line 382

```python
user_id = rec.get("user_id", "")
```

The v1 Recording model uses `user_id` but the v1 Cosmos container uses `userId` as the partition key. Some documents may store ownership under `userId` instead of `user_id`. The migration should check both:
```python
user_id = rec.get("user_id") or rec.get("userId", "")
```

### MEDIUM: `_resolve_file_path` always defaults extension to `.mp3`

**File**: `migrate.py`, lines 603–619

If a recording has no `blob_name` or `unique_filename` but does have a `file_path`, the extension defaults to `.mp3`. The v1 system handles `.opus` files (which are actually MP3, per the "Known Quirks" in CLAUDE.md), but also `.wav` and potentially other formats. The function should extract the extension from `file_path` as a fallback.

### MEDIUM: `_find_old_blob_name` has unreachable code path

**File**: `migrate.py`, lines 622–639

The function checks `file_path` at line 626, and if found, returns it. Then at line 632 it tries to construct from `user_id + unique_filename`, but `unique_filename` was already checked at line 625. The only way to reach line 632 is if none of the three fields exist, making lines 632–637 unreachable dead code.

### LOW: Default status mapping may be wrong for never-transcribed recordings

**File**: `migrate.py`, lines 642–656

The fallback at line 656 returns `"ready"` for any recording that doesn't match the explicit status checks. This means recordings with `transcription_status: "not_started"` will be mapped to `"ready"` instead of `"pending"`, which could mask recordings that were never processed.

**Fix**: Check for `not_started` explicitly:
```python
elif ts == "not_started" or ts == "":
    return "pending"
```

---

## 2. Data Integrity

### CRITICAL: `INSERT OR REPLACE` on recordings breaks FTS triggers

**File**: `migrate.py`, line 411; `database.py`, lines 174–189

SQLite's `INSERT OR REPLACE` is semantically a DELETE followed by an INSERT. The FTS triggers in `database.py` fire on DELETE (line 179) and INSERT (line 174). During migration, the initial INSERT fires the FTS INSERT trigger, adding a row to `recordings_fts`. If migration is re-run, the REPLACE triggers a DELETE (removing from FTS) then an INSERT (re-adding to FTS). This is actually correct for idempotency.

However, the migration also does an explicit FTS rebuild at line 805:
```python
conn.execute("INSERT INTO recordings_fts(recordings_fts) VALUES('rebuild')")
```

This rebuild command is only valid for **content-synced** FTS tables (which this is). But the migration uses `sqlite3` (sync), while `database.py` uses `aiosqlite`. The FTS triggers were created by parsing `database.py` and executing the schema SQL (lines 219–223). This should work, but if the schema extraction fails (which it can — see below), the inline fallback at `_create_schema_inline` (line 232) does **not create FTS tables or triggers**. In that case, the FTS rebuild at line 805 will fail with a "no such table" error.

**Fix**: Add FTS table creation to `_create_schema_inline()`.

### HIGH: Schema extraction via string parsing is fragile

**File**: `migrate.py`, lines 204–228

The schema is extracted by finding `SCHEMA_SQL = """` and `FTS_SCHEMA_SQL = """` via string search. This will break if:
- The variable name changes
- The quotes change to single quotes or f-strings
- There's a comment containing `"""`
- The path resolution fails (two attempts are made, but both assume specific directory layouts)

**Fix**: Import `database.py` as a module and access `SCHEMA_SQL` and `FTS_SCHEMA_SQL` directly, or maintain the schema as a separate `.sql` file.

### HIGH: Foreign key violations on re-run

**File**: `migrate.py`, lines 321, 410, 481

`INSERT OR REPLACE` on the `users` table will delete and re-insert the user. With `PRAGMA foreign_keys=ON`, this cascading delete could wipe out all `recordings`, `participants`, `tags`, etc. referencing that user — depending on whether the foreign keys have `ON DELETE CASCADE`.

Checking the schema: `recordings.user_id` references `users(id)` with **no ON DELETE clause** (default is RESTRICT/NO ACTION). So `INSERT OR REPLACE` on a user that has recordings would **fail** with a foreign key violation.

**Fix**: Either disable foreign keys during migration (`PRAGMA foreign_keys=OFF`), use `INSERT OR IGNORE` + `UPDATE`, or ensure the migration order handles this (users first with no existing recordings, which only works on first run).

### MEDIUM: `dotenv` is imported but not in PEP 723 dependencies

**File**: `migrate.py`, line 48–50

```python
from dotenv import load_dotenv
load_dotenv()
```

But `python-dotenv` is not listed in the script dependencies (lines 1–8). Running with `uv run tools/migrate.py` will fail with an ImportError.

### MEDIUM: No transaction wrapping — partial migration on failure

**File**: `migrate.py`, lines 781–807

The migration executes many individual INSERTs across multiple entity types, with a single `conn.commit()` at line 793. If the script crashes during `migrate_recordings()`, the users are committed (wait — actually no, there's no intermediate commit). The single commit at 793 means either all DB changes succeed or none do (if the script crashes before commit). This is actually good behavior. But the blob download (line 798) happens **after** commit, so a crash during blob download leaves the DB committed but blobs incomplete. This is acceptable since blobs can be re-downloaded.

### LOW: `conn.commit()` not called after each batch for large datasets

For very large migrations (thousands of recordings), holding all changes in a single transaction could use significant memory and WAL journal space. Consider committing in batches.

---

## 3. Idempotency

### HIGH: `INSERT OR REPLACE` semantics are destructive on re-run (see FK issue above)

As noted, `INSERT OR REPLACE` is a DELETE + INSERT. For tables with foreign key relationships, this is dangerous. On re-run:
1. `INSERT OR REPLACE INTO users` — tries to delete existing user, blocked by FK from recordings
2. Even if it works, recording_tags would be orphaned if recordings are replaced

**Recommendation**: Use `INSERT ... ON CONFLICT(id) DO UPDATE SET ...` (SQLite UPSERT syntax, available since 3.24.0) for true idempotent updates without DELETE semantics.

### MEDIUM: Tags use `INSERT OR REPLACE` which could duplicate if IDs change

If tags in v1 are identified by slug (`"meeting"`) but the migration generates different IDs on re-run, you'd get duplicates. The current code uses the tag's `id` field directly from v1, so this should be stable.

### OK: Blob download is idempotent

**File**: `migrate.py`, lines 562–564

The blob download checks `if local_dest.exists()` and skips. This is correct for idempotency.

---

## 4. Storage Abstraction Quality

### MEDIUM: `file_exists()` always returns `True` for Azure mode

**File**: `storage_service.py`, lines 101–109

```python
if settings.use_local_storage:
    return (settings.local_blob_dir / blob_name).exists()
else:
    # For Azure, we'd need a head_blob call — skip for now
    return True
```

This is a bug waiting to happen. Any code that checks `file_exists()` before serving a URL will incorrectly believe the file exists in Azure mode. This should at least log a warning or use `blob.exists()`.

### MEDIUM: Azure download reads entire file into memory

**File**: `storage_service.py`, lines 176–179

```python
stream = await blob.download_blob()
data = await stream.readall()
f.write(data)
```

For large audio files (potentially hundreds of MB), this reads the entire blob into memory. The `readinto()` method or chunked reading would be more memory-efficient:
```python
stream = await blob.download_blob()
await stream.readinto(f)
```

### MEDIUM: New BlobServiceClient created on every operation

**File**: `storage_service.py`, lines 156–158, 171–173, etc.

Every upload/download/delete creates a new `AsyncBlobServiceClient`, connects, performs the operation, and disconnects. This is inefficient for batch operations. Consider caching the client or using a module-level singleton.

### LOW: `_azure_copy` doesn't wait for copy completion

**File**: `storage_service.py`, lines 225–236

`start_copy_from_url()` initiates an async copy on the server side. The function returns immediately without polling for completion. For large blobs, the copy may still be in progress when the function returns.

### LOW: Mixed sync/async in storage service

`generate_sas_url()` (line 67) and `file_exists()` (line 101) are synchronous, while `upload_file()`, `download_file()`, `delete_blob()`, and `copy_blob()` are async. This is intentional (SAS generation doesn't need I/O, existence check is local-only), but the `file_exists()` Azure path would need to be async if properly implemented.

### GOOD: Path traversal protection is correct

**File**: `main.py`, lines 122–125

```python
file_path = (blob_dir / blob_path).resolve()
if not str(file_path).startswith(str(blob_dir.resolve())):
    return JSONResponse(status_code=403, content={"detail": "Forbidden"})
```

This correctly resolves symlinks and `..` traversal, then validates the resolved path starts with the blob directory. This is the standard approach and is secure.

### GOOD: Local/Azure dual-mode abstraction is clean

The public API (`upload_file`, `download_file`, `generate_sas_url`, `delete_blob`) provides a clean interface. The `use_local_storage` property-based switching is straightforward. The lazy Azure SDK imports are a nice touch for dev environments that don't have Azure packages.

---

## 5. Security

### HIGH: Cosmos key and blob connection strings logged in plaintext

**File**: `migrate.py`, line 761

```python
log(f"Source: CosmosDB at {config.cosmos_endpoint}")
```

The endpoint itself isn't a secret, but there's no protection against accidentally logging the key. More importantly, the `MigrateConfig` dataclass has no `__repr__` override, so if it's ever printed/logged (e.g., in a traceback), all credentials are exposed.

**Fix**: Add `repr=False` to sensitive fields or override `__repr__`.

### MEDIUM: `plaud_token` stored in plaintext in SQLite

**File**: `migrate.py`, line 333; `database.py`, line 28

The Plaud bearer token is stored as plaintext in the `users` table. This is the same as v1 (Cosmos), but the migration to SQLite makes it a local file that's easier to access. Consider encrypting at rest or at minimum ensuring the SQLite file has restrictive permissions.

### LOW: SAS URL account key extraction via string parsing

**File**: `storage_service.py`, lines 191–196

```python
parts = dict(
    part.split("=", 1)
    for part in settings.azure_storage_connection_string.split(";")
    if "=" in part
)
account_key = parts.get("AccountKey", "")
```

This works but is fragile. If the connection string format changes or uses a different auth method (SAS-based connection string, managed identity), this will silently produce an empty key and the SAS generation will fail.

---

## 6. Missing Items from Spec

### CRITICAL: JobExecution -> sync_runs migration is not implemented

**File**: `migrate.py` — not present

The spec (section 11, step 3) explicitly calls for:
> `JobExecution` documents -> `sync_runs` table (recent ones only, or all — configurable)

The migration reads `job_execution` documents (line 159) and groups them (line 176), but never migrates them. The `migrate_job_executions()` function doesn't exist. The `sync_runs` table exists in the schema but will be empty after migration.

### HIGH: No server-side blob copy option

The spec (section 11, step 6) says:
> Use Azure SDK blob-to-blob copy (server-side, no download needed if same region)

The migration only implements local download (`migrate_blobs` downloads to local filesystem). There's no option to copy blobs server-side from old Azure to new Azure storage. For 12+ GB of audio, downloading locally and re-uploading would take significantly longer than a server-side copy.

**Fix**: Add an `--azure-to-azure` mode that uses `start_copy_from_url()` with SAS URLs from the source.

### HIGH: No count verification against source

The spec (section 11, step 8) says:
> Count checks (old entity counts vs new table counts)

The `verify_migration()` function (line 670) only checks counts in the new database. It doesn't compare against the source CosmosDB counts to detect missing records.

### MEDIUM: No spot-check verification

The spec calls for:
> Spot-check key recordings (title, transcript snippet, speaker mapping)

Not implemented in `verify_migration()`.

### MEDIUM: Speaker profiles not migrated

The v2 schema has a `speaker_profiles` table (defined in `database.py`, lines 142–155). The spec mentions:
> Also copy speaker profile blobs if migrating voice profiles

The migration does not handle speaker profiles. If v1 has speaker embedding data, it's lost.

### LOW: `analysis_templates` not migrated

The v1 `analysis_type` documents are grouped (line 179) but never migrated. The v2 schema has an `analysis_templates` table.

### LOW: No progress bars

The spec says "Progress bars via `rich`". The `rich` library is imported and `Progress` is imported (line 54), but never used. All output goes through `log()` which just prints text.

---

## 7. Blob Download

### MEDIUM: No progress indication for large downloads

**File**: `migrate.py`, lines 536–596

The blob download loop has no progress bar, ETA, or even a running count. For hundreds of recordings totaling 12+ GB, the user gets no feedback (unless `--verbose` is set, in which case they get per-file messages).

**Fix**: Use the imported `rich.progress.Progress` context manager to show a progress bar.

### MEDIUM: No retry logic for transient blob download failures

A single network timeout or Azure throttle response will mark the blob as failed and move on. For a one-time migration of valuable data, there should be at least a retry with backoff.

### MEDIUM: `stream.readinto(f)` may not work as expected

**File**: `migrate.py`, line 583

```python
stream = blob.download_blob()
stream.readinto(f)
```

The `readinto()` method on the Azure `StorageStreamDownloader` writes directly to the file. This is actually the correct and memory-efficient approach (better than the storage_service.py implementation). However, for very large files, this could timeout. Consider setting `max_single_get_size` and `max_chunk_get_size` on the download.

### LOW: No checksum/size validation after download

After downloading, the script records the size but doesn't verify it against the source blob's size. A truncated download would be silently accepted.

### OK: Existing file skip is correct

The `if local_dest.exists()` check (line 563) prevents re-downloading files, which is good for idempotency and resumability after interruption.

---

## Summary of Priorities

| Severity | Count | Key items |
|----------|-------|-----------|
| CRITICAL | 3 | Single-container query misses most data; FK violations on re-run; JobExecution migration missing |
| HIGH | 7 | transcript_json serialization; analysisResults dropped; schema parsing fragile; no server-side blob copy; no source count verification; settings_json empty; az_raw_transcription dropped |
| MEDIUM | 11 | dotenv missing from deps; file_exists always true for Azure; userId field mismatch; progress bars missing; no retry on blob download; etc. |
| LOW | 6 | Default status mapping; copy completion; mixed sync/async; etc. |

The migration script is a solid start with good structure (dry-run, verify, skip-blobs, error tracking), but the **single-container query is a showstopper** — it will silently produce an incomplete migration. Fix that first, then address the FK/UPSERT semantics, and the remaining issues are mostly polish.
