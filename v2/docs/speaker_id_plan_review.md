# Speaker ID Implementation Plan Review

**Reviewer**: Claude Opus 4.6
**Date**: 2026-03-25
**Scope**: ECAPA-TDNN speaker identification port from v1 to v2

---

## 1. Issues with the Plan

### 1a. The "processing" status is overloaded

The current `RecordingStatus` enum uses `processing` for "AI post-processing (title, description, speaker ID)." The sync pipeline in `_handle_transcription_complete` sets status to `processing`, runs AI title/description, then sets status to `ready`. Speaker ID needs to run *after* transcription completes but the pipeline currently goes straight to `ready` once AI enrichment finishes.

You need to decide: does speaker ID run as part of `_handle_transcription_complete` (blocking the status transition to `ready`), or does it run as a separate background pass? If it runs inline, a slow embedding extraction (downloading audio, loading model, extracting 15 segments) will delay the recording appearing as `ready` by 30-60 seconds. If it runs as a separate pass, you need either a new status (e.g., `identifying`) or a separate `speaker_id_status` field, which is exactly the kind of multi-status complexity the rewrite was trying to eliminate.

**Recommendation**: Run speaker ID inline during `_handle_transcription_complete`, as part of the `processing` phase. The recording is already in `processing` status. Users will not notice a 30-60 second delay on a background sync job. This keeps the single-status model clean.

### 1b. No plan for handling missing audio

The plan assumes audio is always available for embedding extraction. But v2 supports `source='paste'` (pasted transcripts with no audio). Speaker ID cannot run on these recordings. The pipeline needs an explicit check: skip speaker ID when `file_path` is NULL or `source == 'paste'`.

### 1c. Re-rate timing is underspecified

The plan says "Phase C: re-rate" but the current v2 sync pipeline has no phase structure -- it is `run_sync` (fetch new recordings) and `poll_pending_transcriptions` (check Azure Speech jobs). Re-rating needs to be a third scheduled job or appended to one of the existing ones. Since re-rating is pure math (no audio, no ML inference), it should be fast enough to run on every poll cycle, after `poll_pending_transcriptions` completes.

### 1d. Profile loading happens too often in the v1 design

In v1, profiles are loaded from blob storage for every user on every sync run. With SQLite, this is a non-issue for reads (just a query), but profile *writes* during identification (when an auto-match with training enabled is found) need to be batched. Do not save profiles after every single recording -- accumulate changes in memory and write once per user per sync run, like v1 does.

### 1e. The max_speaker_id_per_user cap (10) needs to survive

The v2 config already has `max_speaker_id_per_user: int = 10`. Good. But the plan does not mention it explicitly. Make sure the implementation respects this cap and prioritizes newly completed recordings over backlog, exactly as v1 does.

---

## 2. Implementation Watch-Outs

### 2a. PyTorch + asyncio: the critical constraint

PyTorch operations are CPU-bound and hold the GIL. You absolutely must run all embedding extraction in `asyncio.to_thread()`. The current codebase already does this for ffmpeg (see `_transcode_to_mp3`), so the pattern is established. The entire `process_recording` call -- audio loading, segment extraction, model inference -- should be a single `asyncio.to_thread()` call wrapping a synchronous function. Do not try to make the embedding engine async internally; it gains nothing and adds complexity.

### 2b. Thread safety of the SpeechBrain model

`EncoderClassifier.encode_batch()` is NOT thread-safe. The model holds internal state (batch normalization running stats, etc.). Since you are running a single-instance app with one background scheduler, you will only have one speaker ID job running at a time (the `_sync_running` guard prevents concurrent syncs). This means you are fine as long as you never call embedding extraction from an API endpoint concurrently with a sync job.

The plan mentions a "manual trigger endpoint." If this endpoint runs speaker ID synchronously or kicks off a background task, you must ensure it cannot overlap with a scheduled sync. The existing `_sync_running` guard covers this for sync, but a standalone "re-identify recording" endpoint would bypass it. Either:
- Route all speaker ID work through the sync pipeline (set status to trigger re-processing on next sync), or
- Add a separate lock for the embedding engine itself.

**Recommendation**: Use a module-level `asyncio.Lock` for the embedding engine, separate from the sync lock. Any code path that touches PyTorch must acquire it.

### 2c. Memory usage

ECAPA-TDNN via SpeechBrain with CPU-only PyTorch uses roughly:
- ~150MB for the model weights
- ~50-100MB for PyTorch runtime overhead
- ~50MB transient during inference per segment

Total: ~300MB resident when loaded, ~400MB peak during extraction. For a personal app on Azure App Service B1 (1.75GB RAM), this is significant but workable. The lazy-load approach is correct -- do not load the model until the first speaker ID request.

**Important**: Once loaded, the model should stay in memory for the lifetime of the process. Do not unload/reload it between sync runs. The v1 code does lazy-load-once, which is right.

### 2d. Startup time

First model load takes 5-15 seconds depending on disk speed (downloading from cache vs. HuggingFace). The `speaker_id_model_path` config points to `/app/pretrained_models/spkrec-ecapa-voxceleb`, which assumes the model is pre-baked into the Docker image. Make sure the Dockerfile copies the model files during build, not at runtime. This is how v1 works and it should carry over.

### 2e. numpy/torch tensor lifecycle

Be careful about holding references to torch tensors after extraction. The v1 code correctly does `.detach().cpu().numpy()` and casts to `float32`. Make sure the v2 port does the same. Torch tensors that accidentally stay on a computation graph will leak memory.

---

## 3. Improvements Over v1

### 3a. Fix the profile persistence bug (CRITICAL)

The deep dive document identifies a real design flaw in v1: `SpeakerProfile.to_dict()` only serializes the centroid, not individual embeddings. When profiles are loaded from blob storage on the next sync run, the embeddings list is empty. New embeddings then form a centroid biased toward recent samples rather than being a true running average.

v2 should fix this. The `speaker_profiles` table already has an `embeddings_json` column. **Use it.** Store all individual embeddings (as centroids-per-recording, not per-segment) so that the centroid can be correctly recomputed at any time. This eliminates the need for the "rebuild profiles" escape hatch as a regular maintenance operation.

### 3b. Make training automatic for manually verified speakers

The v1 opt-in `useForTraining` toggle is a UX anti-pattern. When a user manually verifies a speaker ("yes, Speaker 2 is Alice"), they are *by definition* providing ground truth. Requiring a separate checkbox to use that verification for training means most users will never train profiles effectively.

**Recommendation**: When a speaker is manually verified (accepted, reassigned), automatically add their embedding to the profile. Drop the `useForTraining` toggle entirely. If a user reassigns a speaker (correcting a mistake), remove the old participant's embedding for that recording from the profile and add it to the new one. This gives you a clean, friction-free training loop:

1. System identifies speakers (auto/suggest/unknown)
2. User corrects mistakes
3. Corrections automatically improve profiles
4. Future identifications improve

The only case where you might NOT want to train is a deliberate test or adversarial scenario, which does not apply to a personal app.

### 3c. Drop identificationHistory

The v1 system maintains a per-speaker audit trail (`identificationHistory`) with entries for every accept, reject, reassign, re-rate. The rewrite spec already says "drop audit log." Apply this to speaker ID too. The history adds JSON bloat to every speaker_mapping entry and nobody reads it. Keep a simple `identified_at` timestamp and `identification_status` -- that is sufficient.

### 3d. Simplify the review flow

v1 has five separate endpoints: accept, reject, dismiss, reassign, toggle-training. v2 should have one:

```
PUT /api/recordings/{id}/speakers/{label}
Body: { participant_id: string | null, status: "auto" | "dismissed" }
```

- Setting `participant_id` with `status: "auto"` = accept/reassign (automatically trains)
- Setting `participant_id: null` with no status change = reject (clears suggestion, keeps unknown)
- Setting `status: "dismissed"` = dismiss

This collapses five endpoints into one PUT, which aligns with the rewrite's goal of reducing endpoint count.

---

## 4. SQLite Profile Store

### 4a. Centroid as BLOB: yes, this is right

The `speaker_profiles` table stores `centroid BLOB`. This is correct for SQLite. A 192-dim float32 array is 768 bytes as a binary blob, versus ~2KB as a JSON array of floats. BLOB is more compact and avoids floating-point serialization precision loss.

**Serialization**: Use `numpy.ndarray.tobytes()` to write and `numpy.frombuffer(blob, dtype=np.float32)` to read. Do not use pickle -- it is fragile across numpy versions and a security risk. Raw float32 bytes are portable and fast.

### 4b. embeddings_json: store all, but cap at a reasonable number

Store all per-recording centroid embeddings, not per-segment embeddings. Each recording contributes one 192-dim centroid (the mean of up to 15 segment embeddings). For a participant who appears in 50 recordings, that is 50 embeddings x 192 floats x ~10 bytes/float-as-JSON = ~96KB. At 500 embeddings (the v1 cap), that would be ~960KB per profile. For ~70 participants, worst case is ~67MB total -- reasonable for SQLite but worth capping.

**Recommendation**: Cap at 100 embeddings per profile (not 500). For a personal app with ~450 recordings and ~70 participants, most participants will have 5-30 appearances. 100 is generous. Store as a JSON array of arrays (not a numpy-specific format) so it is human-readable and portable:

```json
[[0.123, -0.456, ...], [0.234, -0.567, ...], ...]
```

When the cap is exceeded, drop the oldest. Recompute the centroid from the remaining embeddings.

### 4c. Consider storing embeddings as BLOB too

An alternative to `embeddings_json TEXT` is storing the embedding matrix as a single BLOB column (`embeddings_blob BLOB`) using `np.stack(embeddings).tobytes()`. For 100 embeddings, that is 100 x 192 x 4 = 76.8KB as binary vs ~200KB as JSON text. The savings are modest at this scale, but binary is faster to load and avoids JSON parsing of thousands of floats.

**Recommendation**: Use BLOB for both centroid and embeddings. Add a helper class that handles serialization:

```python
def serialize_embeddings(embeddings: list[np.ndarray]) -> bytes:
    return np.stack(embeddings).astype(np.float32).tobytes()

def deserialize_embeddings(blob: bytes, dim: int = 192) -> list[np.ndarray]:
    mat = np.frombuffer(blob, dtype=np.float32).reshape(-1, dim)
    return [mat[i] for i in range(len(mat))]
```

### 4d. recording_ids column

The `recording_ids TEXT` column on `speaker_profiles` is fine as a JSON array of strings. Keep it for provenance tracking. When you drop an old embedding (cap exceeded), also drop its corresponding recording_id.

---

## 5. Training Model

### Automatic training, no opt-in

As argued in section 3b: make training automatic for all manually verified speakers. The decision flow should be:

1. **Auto-match (>= 0.78)**: System assigns participant. Embedding is NOT added to profile (no human verified it).
2. **User confirms auto-match**: Now it IS verified. Add embedding to profile.
3. **User accepts suggestion**: Verified. Add embedding to profile.
4. **User assigns participant (from unknown/dropdown)**: Verified. Add embedding to profile.
5. **User reassigns**: Remove old participant's embedding for this recording, add to new participant's profile.
6. **User dismisses**: No profile update.

This means auto-matched speakers only improve profiles when the user explicitly confirms them. This avoids feedback loops where a false positive auto-match reinforces itself.

Note: v1 does NOT auto-train on auto-matches either (requires `useForTraining` toggle). But v1 also does not auto-train on accepts. The v2 improvement is making accepts auto-train.

---

## 6. PyTorch in FastAPI

### 6a. Memory

As noted in 2c, expect ~300-400MB for PyTorch + model. The CPU-only PyTorch build (configured in `pyproject.toml` via the pytorch-cpu index) avoids the 2GB+ CUDA libraries. This is the right call.

### 6b. Startup time

With lazy loading, the FastAPI app starts in ~2 seconds without loading PyTorch. The first speaker ID job will take an extra 5-15 seconds for model initialization. This is fine for a background job.

### 6c. asyncio.to_thread is the right pattern

The entire speaker processing pipeline (audio download, segment extraction, embedding computation, matching) should run in a single `asyncio.to_thread()` call. This prevents blocking the event loop for what could be 30-60 seconds of CPU-bound work per recording.

Structure it like this:

```python
async def identify_speakers_for_recording(recording_id: str, user_id: str):
    """Async wrapper that delegates to sync code via thread pool."""
    # Load data from DB (async)
    recording = await get_recording(recording_id)
    profiles = await load_profiles(user_id)
    audio_url = generate_audio_url(recording.file_path)

    # Run CPU-bound work in thread (sync)
    results = await asyncio.to_thread(
        _identify_speakers_sync,
        audio_url, recording.transcript_json, profiles
    )

    # Save results to DB (async)
    await save_speaker_mapping(recording_id, results)
    await update_profiles(user_id, results)
```

### 6d. Do not use FastAPI BackgroundTasks for speaker ID

`BackgroundTasks` runs after the response is sent but still on the event loop. For CPU-bound work, this would block all other requests. Always use `asyncio.to_thread()` or submit to a thread pool executor.

### 6e. APScheduler job wrapping

The scheduled jobs (`plaud_sync`, `poll_transcriptions`) already run as async functions on the event loop. When speaker ID is wired into `poll_pending_transcriptions` (inside `_handle_transcription_complete`), the `asyncio.to_thread()` call naturally prevents blocking. No special APScheduler configuration needed.

---

## 7. Missing Pieces

### 7a. No re-identification endpoint

The plan mentions "manual trigger endpoint" but does not specify a re-identification flow. In v1, `POST /api/transcription/{id}/reidentify` clears non-verified speaker data and sets status to `not_started` so the worker re-processes it. v2 needs this too. Implementation: clear `identification_status`, `similarity`, `confidence`, and `participant_id` for non-verified, non-dismissed speakers. On the next poll cycle, the recording will be picked up for re-processing.

### 7b. No plan for stripping embeddings from API responses

In v1, embeddings are stripped from speaker_mapping before returning to the frontend (192 floats per speaker would bloat responses). v2 needs to do this too. When serializing `RecordingDetail.speaker_mapping` for API responses, strip the `embedding` field from each `SpeakerMappingEntry`. The Pydantic model already has `embedding: list[float] | None = None` -- use a response model or a post-serialization hook to exclude it.

### 7c. No mention of participant display_name enrichment

In v1, speaker_mapping entries only store `participantId`. The `displayName` is populated at query time by looking up the participant. v2 needs this enrichment in the recording detail endpoint. The `SpeakerMappingEntry` model has `display_name` but the `_extract_speaker_mapping` function in sync_service.py sets it to `None`. The GET recording endpoint must join against the participants table to fill these in.

### 7d. Duplicate auto-match detection

The plan does not mention this but it is important. When two speakers in the same recording both auto-match to the same participant, the one with lower confidence must be demoted to `suggest`. This is a small but important piece of logic from v1 that prevents nonsensical results like "Speaker 1 is Alice, Speaker 2 is also Alice."

### 7e. No plan for the embedding_std field

The `speaker_profiles` table has `embedding_std REAL`. In v1, this is computed but never used in matching decisions. Either drop it (simplify) or commit to using it (e.g., as a profile quality indicator in the UI, or as a dynamic threshold adjuster). My recommendation: drop it. It is dead code.

### 7f. Speaker name inference (LLM-based) interaction

The rewrite spec mentions keeping "LLM-Assisted Speaker Name Inference" as a supplementary signal alongside ECAPA-TDNN. The plan does not address how these two systems interact. They should run independently: ECAPA-TDNN does voice matching, LLM infers names from conversational context. Results should be merged in the speaker_mapping -- ECAPA-TDNN sets participant_id/confidence, LLM can set `display_name` as a hint when no ECAPA-TDNN match exists.

---

## 8. Migration Strategy

### 8a. Migrating v1 profile blobs

The v1 profiles are stored in Azure Blob Storage at `speaker-profiles/{userId}/profiles.json`. Each profile has a centroid (192-dim) but NOT the individual embeddings (they are not serialized in `to_dict()`).

**Migration approach**: Read each profile JSON, insert into `speaker_profiles` table with:
- `centroid` = numpy array from the JSON floats, serialized as BLOB
- `embeddings_json` = NULL (we do not have the individual embeddings)
- `n_samples` = the `n_samples` value from the JSON
- `recording_ids` = the `recording_ids` list from the JSON

This gives you working profiles immediately -- the centroid is all you need for matching. The individual embeddings will accumulate over time as users verify speakers in v2.

### 8b. Bootstrapping from speaker_mapping embeddings

This is the more valuable migration. Every v1 recording's `speaker_mapping` has per-speaker `embedding` fields (192-dim centroids) for speakers that were identified. For speakers where `manuallyVerified == True`, these embeddings are ground-truth training data.

**Migration approach**:
1. For each recording with a speaker_mapping:
2. For each speaker entry where `manuallyVerified == True` and `embedding` is not null and `participantId` is not null:
3. Add the embedding to the corresponding participant's profile in `speaker_profiles`
4. Recompute the centroid from all collected embeddings

This is essentially running `rebuild_all_profiles` during migration, but without the `useForTraining` filter (since v2 drops that concept in favor of auto-training on verification).

**Important**: Do this AFTER migrating the profile blobs (8a), so you start with the existing centroids and then enrich with the individual embeddings. Actually, since you are collecting all individual embeddings and recomputing centroids, you should do this INSTEAD of 8a. The rebuilt profiles from speaker_mapping embeddings will be more accurate than the blob centroids (which suffered from the persistence bug).

**Recommended order**:
1. Migrate all recordings, participants, etc. to SQLite
2. For each user, iterate all recordings with speaker_mappings
3. Collect all `(participant_id, embedding, recording_id)` tuples where `manuallyVerified == True`
4. Build `speaker_profiles` rows: compute centroid from all embeddings, store embeddings as blob, set n_samples
5. Skip the v1 profile blob migration entirely -- the rebuilt profiles are strictly better

### 8c. Handle participants with no embeddings

Some participants may have been manually assigned in v1 but have no stored embeddings (very early recordings, or cases where the embedding was never computed). These participants should still get a `speaker_profiles` row with `centroid = NULL`, `n_samples = 0`. They will get profiles naturally as they appear in future recordings and the user verifies them.

### 8d. Migration should be part of the main migration script

Do not make speaker profile migration a separate tool. Include it as a step in `tools/migrate.py` after recording and participant migration, since it depends on both.

---

## Summary of Key Recommendations

| # | Recommendation | Priority |
|---|----------------|----------|
| 1 | Run speaker ID inline in `_handle_transcription_complete` | High |
| 2 | Fix the embedding persistence bug -- store individual embeddings in SQLite | High |
| 3 | Make training automatic on manual verification, drop `useForTraining` | High |
| 4 | Use `asyncio.to_thread()` for all PyTorch work, with a dedicated `asyncio.Lock` | High |
| 5 | Add duplicate auto-match detection | High |
| 6 | Strip embeddings from API responses | Medium |
| 7 | Skip paste recordings (`source='paste'`) for speaker ID | Medium |
| 8 | Bootstrap profiles from speaker_mapping embeddings during migration, skip blob migration | Medium |
| 9 | Cap embeddings at 100 per profile, store as BLOB | Medium |
| 10 | Collapse five review endpoints into one PUT | Medium |
| 11 | Drop `embedding_std`, `identificationHistory`, `useForTraining` | Low |
| 12 | Add re-identification endpoint | Low |
| 13 | Wire up re-rating as part of poll cycle | Low |
