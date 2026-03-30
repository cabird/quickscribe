# Speaker Identification System Review (v2)

**Reviewer**: Claude Opus 4.6 (1M context)
**Date**: 2026-03-25
**Scope**: All speaker ID files in v2 backend

---

## Executive Summary

The v2 speaker identification implementation is solid and addresses the major v1 issues identified in the plan review. The pipeline is structurally correct end-to-end, the profile persistence bug is fixed, training is automatic, and the code is well-organized. However, there are several bugs, a concurrency concern, and some missing pieces that need attention before this is production-ready.

**Severity breakdown**: 2 high, 5 medium, 4 low.

---

## 1. Correctness

### 1.1 HIGH: `assign_speaker` does not train profiles

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/recording_service.py`, lines 501-552

When a user manually assigns a speaker via `assign_speaker()`, the function updates the `speaker_mapping` JSON but never calls `profile_store.update_profile_with_embedding()`. This means the core training loop described in the plan review (section 3b: "corrections automatically improve profiles") does not work.

The function also has a logic error on line 542:
```python
mapping[speaker_label]["identification_status"] = "auto" if not manually_verified else "auto"
```
Both branches of this ternary return `"auto"`. When `manually_verified=True` (the default), the status should probably reflect that the user explicitly confirmed it. More importantly, the `manuallyVerified` / `manually_verified` field is set, but no training occurs.

**Fix required**: After updating the mapping, check if the entry has a stored `embedding`. If so, call `profile_store.update_profile_with_embedding(user_id, participant_id, embedding, recording_id)`. If the speaker was previously assigned to a different participant, the old participant's profile should ideally have that embedding removed (though this is a lower priority).

### 1.2 HIGH: `process_recording` does not use configurable thresholds

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, lines 36-38
**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/config.py`, lines 42-43

The config has `speaker_id_auto_threshold` (0.78) and `speaker_id_suggest_threshold` (0.68), but `speaker_processor.py` hardcodes its own module-level constants:
```python
AUTO_THRESHOLD = 0.78
SUGGEST_THRESHOLD = 0.68
```
These are never read from `settings`. If someone changes the config values, nothing happens. Either remove the config fields (since they are dead) or wire them through.

### 1.3 MEDIUM: Duplicate field names in speaker_mapping writes

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, lines 406-447

Every speaker_mapping write stores both camelCase and snake_case versions of the same field:
```python
entry["participantId"] = result["participant_id"]
entry["participant_id"] = result["participant_id"]
```

This is a pragmatic compatibility approach for v1 data migration, but it doubles the JSON size of speaker_mapping entries and creates a maintenance hazard where one field gets updated but the other does not. Since `SpeakerMappingEntry` in `models.py` (line 66-88) already handles both via Pydantic `Field(alias=...)`, the v2 code should write only snake_case and let Pydantic handle deserialization of either format from legacy data.

### 1.4 MEDIUM: `rerate_speakers` loads ALL recordings for a user

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, lines 480-484

The query fetches every recording with a non-null speaker_mapping:
```sql
SELECT id, speaker_mapping FROM recordings
WHERE user_id = ? AND speaker_mapping IS NOT NULL
```

For a user with hundreds of recordings, this loads all speaker_mapping JSON blobs (which can be several KB each with embeddings). The function then filters in Python for entries with `suggest` or `unknown` status. This should be filtered in SQL, but since speaker_mapping is a JSON column in SQLite, a simple `WHERE` clause cannot filter on nested JSON fields efficiently. Consider adding an indexed `speaker_id_status` column to the recordings table, or at minimum adding a `LIKE '%suggest%' OR LIKE '%unknown%'` filter to reduce the result set.

### 1.5 LOW: `_parse_diarization` does not handle all Azure Speech formats

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, lines 48-80

The function handles `recognizedPhrases` (dict format) and a generic list-of-segments format. However, the `transcript_json` stored by `sync_service._handle_transcription_complete` (line 436) is `json.dumps(content)` where `content` is the full Azure Speech response dict. This means `transcript_json` will always be a dict with a `recognizedPhrases` key. The list format handler is dead code unless some other code path writes a different format. Not a bug, but worth verifying there are no other writers.

---

## 2. Integration

### 2.1 Sync service integration is correct

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/sync_service.py`, lines 452-471

The speaker ID integration in `_handle_transcription_complete` follows the plan review's recommendation #1: it runs inline during the `processing` phase, after transcription completes but before the status transitions to `ready`. The lock is acquired, `process_recording` is called, and `rerate_speakers` runs if identification succeeded. The `try/except` on line 466 correctly treats speaker ID failure as non-fatal (the recording still becomes `ready`).

### 2.2 Recording service embedding stripping works

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/recording_service.py`, line 291

The `get_recording` function strips embeddings from API responses:
```python
entry.embedding = None
```
This addresses plan review recommendation #6. Embeddings (192 floats per speaker) are correctly excluded from RecordingDetail responses.

### 2.3 Display name enrichment works

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/recording_service.py`, lines 265-288

The `get_recording` function correctly joins participant display names into speaker_mapping entries, addressing plan review item 7c.

### 2.4 MEDIUM: `profile_store.rebuild_all_profiles` participant lookup is missing user_id filter

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/profile_store.py`, line 369

```python
p_rows = await db.execute_fetchall(
    "SELECT display_name FROM participants WHERE id = ?", (participant_id,)
)
```

This query does not filter by `user_id`. While participant IDs are UUIDs and collisions are astronomically unlikely, it is a correctness issue: a participant ID from user A's speaker_mapping could theoretically resolve to user B's participant row. The query at line 276 in `update_profile_with_embedding` correctly includes `AND user_id = ?`. This one should too.

---

## 3. Concurrency

### 3.1 MEDIUM: `asyncio.Lock` is created at module level -- not safe across workers

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, line 33

```python
_speaker_id_lock = asyncio.Lock()
```

This is fine for a single-worker deployment (which is expected for this app). However:

1. **The lock is never acquired inside `process_recording` itself.** The callers (`sync_service.py` line 457 and `recordings.py` lines 211, 278) acquire it externally via `async with speaker_processor._speaker_id_lock`. This means any new caller that forgets to acquire the lock will bypass protection. The lock should be acquired inside `process_recording` and `rerate_speakers` themselves, not by callers.

2. **Nested lock acquisition risk**: In `sync_service.py` line 457-465, the lock is acquired, then `process_recording` is called, then `rerate_speakers` is called, all within the same `async with` block. If `process_recording` or `rerate_speakers` were ever changed to acquire the lock internally (per the recommendation above), you would get a deadlock since `asyncio.Lock` is not reentrant. The solution is to either (a) always acquire externally (current approach, but fragile) or (b) acquire internally and never nest, or (c) make the callers call a higher-level function that acquires once and runs both steps.

**Recommendation**: Create a single `async def run_speaker_id_pipeline(user_id, recording_id)` function that acquires the lock internally and calls both `process_recording` and `rerate_speakers`. Callers use this instead of touching the lock directly.

### 3.2 LOW: `_sync_running` boolean guard in sync_service is not thread-safe

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/sync_service.py`, lines 37, 100-108

The `_sync_running` boolean is a simple flag without any lock. In an async context with a single event loop thread, this is fine (no concurrent mutation of the flag). But it provides no protection against the same sync being triggered from multiple workers if the app were ever scaled. This is low severity since the app is designed for single-instance deployment.

---

## 4. Performance

### 4.1 Audio loaded twice in process_recording

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, lines 159 and 355-360

Inside `_process_recording_sync`, the audio is loaded via `engine.load_audio_mono_16k(audio_path)` on line 159. However, `process_recording` (the async wrapper) downloads the audio to a temp file on lines 355-360, then passes the temp path to `_process_recording_sync` which loads it. This is correct -- the audio is loaded once from the temp file. No issue here.

### 4.2 LOW: All profiles loaded into memory for matching

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/profile_store.py`, lines 77-109

`get_profiles` deserializes ALL embeddings for ALL profiles (not just centroids). For matching, only centroids are needed. The `embeddings_blob` deserialization on line 96 is wasted work during the identification pipeline. For a user with 70 participants and 50 embeddings each, this is ~70 * 50 * 192 * 4 = ~2.7MB of numpy arrays created and then ignored.

**Suggestion**: Add a `get_profiles_for_matching(user_id)` function that only loads `participant_id`, `display_name`, and `centroid`. Or add a `load_embeddings=False` parameter.

### 4.3 PyTorch memory management is correct

The embedding engine uses `torch.inference_mode()` (line 122 of `embedding_engine.py`), `.detach().cpu().numpy()` (line 125), and casts to `float32` (line 126). This prevents tensor graph leaks. The singleton pattern (`get_engine`) ensures the model is loaded once and stays resident, which is correct per the plan review.

---

## 5. v1 Parity

The implementation covers all major v1 capabilities:

| Feature | v1 | v2 | Status |
|---------|----|----|--------|
| Segment selection (merge, top-N, edge trim, center window) | Yes | Yes | Matching constants |
| Thresholds (auto 0.78, suggest 0.68, min candidate 0.40) | Yes | Yes | Matching values |
| Duplicate auto-match detection | Yes | Yes | Lines 259-281 |
| Skip verified/dismissed speakers | Yes | Yes | Lines 103-123 |
| Embedding-only extraction for verified speakers | Yes (with useForTraining) | Yes (automatic) | Improved |
| Re-rating | Yes | Yes | Lines 466-597 |
| Profile training on verification | Via useForTraining toggle | Automatic for embedding_only path | Partial -- see 1.1 |
| Re-identification (clear and re-run) | Yes | Yes | Router line 219-283 |
| Profile rebuild | Yes | Yes | profile_store.rebuild_all_profiles |

**Gap**: The v1 `max_speaker_id_per_user` cap (10 recordings per sync run) is present in config (`config.py` line 53) but is not enforced anywhere in the code. The `process_recording` function processes a single recording, and `_handle_transcription_complete` calls it for every completed transcription without any cap. If a batch of recordings complete simultaneously, all will be processed. This is arguably fine for v2 since it runs inline rather than as a batch, but the config field is misleading.

---

## 6. Improvements Over v1

### 6.1 Profile persistence bug: FIXED

The plan review (section 3a) identified that v1's `SpeakerProfile.to_dict()` only serialized centroids, not individual embeddings. v2 stores both:
- `centroid` as BLOB (`profile_store.py` line 135)
- `embeddings_blob` as BLOB (`profile_store.py` line 136)

The `rebuild_all_profiles` function (lines 309-396) correctly rebuilds from individual embeddings, and `update_profile_with_embedding` (lines 243-306) correctly appends new embeddings and recomputes centroids. The cap of 100 embeddings per profile (line 24) follows the plan review recommendation.

### 6.2 Automatic training: PARTIALLY IMPLEMENTED

Training is automatic for the "embedding_only" path (verified speakers that need embedding extraction, lines 391-404 in `speaker_processor.py`). However, as noted in issue 1.1, the `assign_speaker` endpoint does not trigger profile training. This means the primary training path (user verifies a speaker in the UI) does not update profiles.

### 6.3 Dropped useForTraining: DONE

The `SpeakerMappingEntry` model still has `use_for_training` (line 83 of `models.py`) but it is never checked in the identification pipeline. Training is triggered by `manuallyVerified` status instead, which is correct.

### 6.4 Dropped identificationHistory: DONE

No history arrays are written. Only `identifiedAt` / `identified_at` timestamps are stored.

### 6.5 Simplified review flow: DONE

v1 had 5 endpoints. v2 has:
- `PUT /{recording_id}/speakers/{label}` -- assign/reassign
- `POST /{recording_id}/identify-speakers` -- manual trigger
- `POST /{recording_id}/reidentify` -- clear and re-run

This is a cleaner API.

---

## 7. Missing Pieces

### 7.1 MEDIUM: No speaker ID trigger after manual upload + transcription

The speaker ID integration exists in `sync_service._handle_transcription_complete` (for Plaud sync). But for uploaded recordings (`recording_service.upload_recording`, line 555), there is no code path that triggers speaker identification after transcription completes. If uploaded recordings go through the same `poll_pending_transcriptions` -> `_handle_transcription_complete` flow, this is covered. But `upload_recording` just sets status to `pending` and returns -- the polling mechanism would need to pick it up. Verify that uploaded recordings flow through the same transcription polling pipeline.

### 7.2 No dismiss speaker endpoint

The `assign_speaker` endpoint handles assignment, but there is no way to dismiss a speaker (mark as "don't identify this one"). The `reidentify` endpoint preserves dismissed status (line 255-256), implying dismissal is a supported concept, but no endpoint sets it. Users would need to be able to set `identification_status: "dismissed"` through the API.

### 7.3 No endpoint to list or view speaker profiles

There is no API endpoint to view speaker profiles (how many samples, which recordings contributed, etc.). The rebuild endpoint exists (`POST /api/me/speaker-profiles/rebuild`), but no GET endpoint. For debugging and user trust, a `GET /api/me/speaker-profiles` endpoint would be valuable.

### 7.4 `embedding_std` is computed but never used

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/profile_store.py`, lines 69-74

The plan review (section 7e) recommended dropping this. It is computed and stored but never read or exposed. Dead code.

---

## 8. API Endpoints

### 8.1 Endpoints are correct and functional

| Endpoint | Method | Purpose | Auth | Notes |
|----------|--------|---------|------|-------|
| `/{id}/speakers/{label}` | PUT | Assign speaker | Yes | Missing training trigger (1.1) |
| `/{id}/identify-speakers` | POST | Manual ID trigger | Yes | Checks speaker_id_enabled, skips paste |
| `/{id}/reidentify` | POST | Clear + re-run | Yes | Correctly preserves verified/dismissed |
| `/api/me/speaker-profiles/rebuild` | POST | Rebuild all profiles | Yes | Destructive (deletes first) |

### 8.2 URL encoding concern for speaker labels

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/routers/recordings.py`, line 177

Speaker labels like "Speaker 1" contain a space. In the URL path `/{recording_id}/speakers/{label}`, FastAPI will handle URL-decoded values, so `speakers/Speaker%201` should work. However, this should be tested -- if the frontend sends the label without encoding, or double-encodes it, the lookup in speaker_mapping will fail silently (the label won't match).

---

## 9. Edge Cases

### 9.1 No audio file: Handled

`process_recording` checks `file_path` (line 325) and `source == "paste"` (line 320). Both return `False` gracefully.

### 9.2 No transcript_json: Handled

Checked on line 330. Returns `False`.

### 9.3 No profiles yet (new user): Handled

If `profiles` is empty, `profile_centroids` will be empty (line 192-194 in `speaker_processor.py`), and all speakers will get `status: "unknown"` with empty `top_candidates`. The embeddings are still stored in speaker_mapping, ready for future matching after profiles are created.

### 9.4 Empty segments after merge: Handled

If `merge_adjacent_segments` returns an empty list, `_parse_diarization` would have returned `[]`, caught on line 337.

### 9.5 All speakers already verified: Handled

`active_speakers` will be empty (line 128), returns `{}` on line 129.

### 9.6 Very short recording (all segments < 2s): Handled

No segments pass the `MIN_DURATION` filter, `speaker_segments` is empty, `selected_segments` is empty, `centroids` is empty, returns `{}`.

### 9.7 MEDIUM: `needs_embedding_only` speakers may not have segments in diarization

**File**: `/home/cbird/repos/quickscribe/v2/backend/src/app/services/speaker_processor.py`, lines 104, 127, 200-210

A speaker in `needs_embedding_only` is NOT added to `skip_speakers` (line 104 shows the code falls through without adding to `skip_speakers` when there is no embedding). However, they ARE filtered into `active_speakers` (line 127 -- they are not in `skip_speakers`). But then on line 200-210, the code checks `if speaker_label in needs_embedding_only` and writes an "embedding_only" result. The problem: the `needs_embedding_only` check happens AFTER centroid computation. If a verified speaker has no segments long enough to produce embeddings, they won't appear in `centroids` at all, so the `needs_embedding_only` check on line 200 will never trigger for that speaker. This is a silent failure -- no error, but no embedding extracted either. The logging on line 121 says "Need embedding for verified Speaker X" but there will be no follow-up log indicating the extraction failed due to insufficient segments.

---

## Summary: Prioritized Action Items

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | **HIGH** | `assign_speaker` does not train profiles | `recording_service.py:501-552` |
| 2 | **HIGH** | Thresholds in config are dead (not wired to processor) | `speaker_processor.py:36-38`, `config.py:42-43` |
| 3 | **MEDIUM** | Lock is acquired by callers, not internally -- fragile | `speaker_processor.py:33`, `recordings.py:211,278` |
| 4 | **MEDIUM** | `rebuild_all_profiles` participant query missing user_id | `profile_store.py:369` |
| 5 | **MEDIUM** | `rerate_speakers` loads all recordings without SQL filter | `speaker_processor.py:480-484` |
| 6 | **MEDIUM** | `needs_embedding_only` silently fails for short-segment speakers | `speaker_processor.py:200-210` |
| 7 | **MEDIUM** | No dismiss endpoint | Router gap |
| 8 | **LOW** | Duplicate camelCase/snake_case fields in mapping writes | `speaker_processor.py:406-447` |
| 9 | **LOW** | `max_speaker_id_per_user` config not enforced | `config.py:53` |
| 10 | **LOW** | `get_profiles` deserializes all embeddings even for matching | `profile_store.py:77-109` |
| 11 | **LOW** | `embedding_std` computed but never used | `profile_store.py:69-74` |
