# QuickScribe v1 Speaker Identification System: Complete Deep Dive

This document is an exhaustive reference for the speaker identification system in QuickScribe v1. It covers every component, data flow, threshold, and decision point end-to-end.

---

## Table of Contents

- [A. Where Do Speaker Samples/Embeddings Come From?](#a-where-do-speaker-samplesembeddings-come-from)
- [B. The Full Identification Pipeline](#b-the-full-identification-pipeline)
- [C. The Review/Labeling Flow](#c-the-reviewlabeling-flow)
- [D. Training Data Management](#d-training-data-management)
- [E. Re-rating](#e-re-rating)
- [F. Speaker Profile Data Model](#f-speaker-profile-data-model)
- [G. All API Endpoints Involved](#g-all-api-endpoints-involved)
- [H. Data Flows Between Frontend, Backend, and Sync Service](#h-data-flows-between-frontend-backend-and-sync-service)

---

## A. Where Do Speaker Samples/Embeddings Come From?

### ML Model

The system uses **ECAPA-TDNN** from SpeechBrain, pretrained on VoxCeleb:

```python
# embedding_engine.py
self.model = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir=os.path.join(cache_dir, "spkrec-ecapa-voxceleb"),
    run_opts={"device": self.device},
)
```

This produces **192-dimensional** speaker embedding vectors. The model is lazy-loaded only when speaker identification is actually needed (to avoid the torch import cost on runs that only sync Plaud recordings).

### When Are Embeddings Extracted?

Embeddings are extracted in two scenarios:

1. **During speaker identification** (Phase B of `JobExecutor`): When a recording has a completed transcription but no speaker identification (`speaker_identification_status` is `null`, `not_started`, or missing). The sync service downloads the audio, extracts embeddings from diarized segments, and builds per-speaker centroids.

2. **For training-requested verified speakers** ("embedding_only" path): When a speaker has already been manually verified (`manuallyVerified=True`) and `useForTraining=True` but has no stored embedding. The processor extracts the embedding without running identification, purely to feed the training loop.

### Audio Loading

```python
# embedding_engine.py
def load_audio_mono_16k(self, path: str) -> Tuple[torch.Tensor, int]:
```

- MP3 files are converted to WAV via ffmpeg (`ffmpeg -y -i path -ar 16000 -ac 1`)
- Other formats loaded via torchaudio
- Always resampled to **16kHz mono**

### Segment Selection and Processing

**Source: `speaker_processor.py`**

The diarization segments come from `transcription.transcript_json`, which contains Azure Speech Services output (either `recognizedPhrases` format or a list of segment objects).

#### Step 1: Merge Adjacent Segments

```python
# embedding_engine.py
def merge_adjacent_segments(diarization, max_gap_s=0.35, min_keep_s=0.6):
```

- Segments from the same speaker with a gap of **<= 0.35 seconds** are merged into one
- After merging, segments shorter than **0.6 seconds** are dropped
- Purpose: Creates better embedding windows from rapid turn-taking

#### Step 2: Skip Verified/Dismissed Speakers

Before extraction, the processor checks the existing `speaker_mapping`:
- **`identificationStatus == 'dismissed'`**: Skipped entirely
- **`manuallyVerified == True`**: Skipped unless `useForTraining == True` AND `embedding` is missing (in which case, embedding-only extraction is triggered)

#### Step 3: Select Best Segments Per Speaker

```python
MAX_SEGMENTS_PER_SPEAKER = 15
MIN_DURATION = 2.0  # seconds minimum per segment
```

- Segments shorter than **2.0 seconds** are discarded
- For each speaker, segments are sorted by duration (longest first)
- The top **15 longest segments** are selected per speaker

#### Step 4: Edge Trimming on Long Segments

```python
EDGE_TRIM = 3.0       # seconds to trim from each edge
TRIM_THRESHOLD = 10.0  # only trim if segment >= 10s
```

- Segments >= **10 seconds** have **3 seconds** trimmed from the start and end
- Purpose: Avoids crosstalk and boundary artifacts at speaker turn boundaries

#### Step 5: Center Windowing

```python
if dur > 10.0:
    mid = (start_s + end_s) / 2.0
    start_s = mid - 5.0
    end_s = mid + 5.0
```

- After edge trimming, if the remaining segment is still > **10 seconds**, only the center **10 seconds** are used
- Purpose: ECAPA-TDNN works best on segments of a few seconds

#### Step 6: Extract Embedding

```python
@torch.inference_mode()
def embedding_from_waveform(self, wav_16k_mono: torch.Tensor) -> np.ndarray:
    sig = wav_16k_mono.squeeze(0)
    emb = self.model.encode_batch(sig.unsqueeze(0))
    emb = emb.squeeze().detach().cpu().numpy()
    return emb.astype(np.float32)
```

- Each selected segment produces one 192-dim embedding
- A final min-duration check ensures the waveform slice has at least `MIN_DURATION * sr` samples

#### Step 7: L2 Normalize Each Embedding

```python
def l2_normalize(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-12)
```

Every individual segment embedding is L2-normalized before aggregation.

### Per-Speaker Centroid Construction

```python
centroids = {}
for spk, embs in local_embs.items():
    mat = np.stack(embs, axis=0)           # shape: (N, 192)
    centroids[spk] = l2_normalize(mat.mean(axis=0))  # mean then normalize
```

- Stack all L2-normalized segment embeddings for one speaker
- Take the **element-wise mean** across all segments
- **L2-normalize** the mean to produce the final centroid
- This centroid is stored in `speaker_mapping[label].embedding` as a list of 192 floats

### What Happens When a Segment Is Too Short?

- Segments < **2.0 seconds** after merging are never selected
- If a segment's waveform slice has fewer than `MIN_DURATION * sr` samples after trimming/windowing, the embedding is silently skipped (no error, just not included in the centroid)
- If NO valid segments exist for a speaker, that speaker gets no centroid and is not included in the results

---

## B. The Full Identification Pipeline

### Trigger: Job Executor Phase B

The sync service runs as an Azure Container Apps Job on a cron schedule. For each user, it executes four phases in order:

1. **Phase A**: Poll pending transcriptions from Azure Speech Services
2. **Phase B**: Speaker identification for newly completed + backlog recordings
3. **Phase C**: Re-rate existing suggest/unknown speakers against updated profiles
4. **Phase D**: Fetch new Plaud recordings

### Step-by-Step: Phase B (`_run_speaker_id_for_user`)

**Source: `job_executor.py` lines 324-408**

#### 1. Gather Work

```python
recording_ids_to_process = set(completed_recording_ids)  # from Phase A
```

Plus a backlog query:

```sql
SELECT c.id FROM c
WHERE c.type = 'recording'
AND c.user_id = @user_id
AND c.transcription_status = 'completed'
AND (
    NOT IS_DEFINED(c.speaker_identification_status)
    OR c.speaker_identification_status = null
    OR c.speaker_identification_status = 'not_started'
)
```

- Combines newly completed recordings from Phase A with any backlog
- Capped at **`MAX_SPEAKER_ID_PER_USER` = 10** recordings per user per run (env var override available)
- Newly completed recordings get priority; backlog fills remaining slots

#### 2. Load User's Speaker Profiles

```python
profile_db = self.profile_manager.load_profiles(user.id)
```

Loads from Azure Blob Storage: `speaker-profiles/{userId}/profiles.json`

#### 3. Process Each Recording

For each recording in the work set, `_identify_recording` is called:

##### 3a. Mark Processing

```python
recording.speaker_identification_status = "processing"
self.recording_handler.update_recording(recording)
```

##### 3b. Run SpeakerProcessor

`speaker_processor.process_recording()` does:
1. Parse diarization from `transcript_json`
2. Merge adjacent segments
3. Determine which speakers to skip (verified/dismissed)
4. Select top segments, download audio, extract embeddings (see Section A)
5. Build per-speaker centroids
6. Match each speaker against profiles

##### 3c. Matching: `profile_db.match_with_confidence()`

```python
# Thresholds defined in speaker_processor.py
AUTO_THRESHOLD = 0.78
SUGGEST_THRESHOLD = 0.68
MIN_CANDIDATE_THRESHOLD = 0.40
```

The matching algorithm:

```python
def match_with_confidence(self, embedding, high_threshold=0.78, low_threshold=0.68, top_n=5):
    top_candidates = self.match_top_n(embedding, n=top_n)
    # top_candidates sorted by cosine similarity descending

    best = top_candidates[0]
    best_sim = best["similarity"]

    if best_sim >= high_threshold:   # >= 0.78
        status = "auto"              # Auto-assign, high confidence
    elif best_sim >= low_threshold:  # >= 0.68
        status = "suggest"           # Suggest to user for review
    else:
        status = "unknown"           # Below threshold, no suggestion
        best_id = None               # Clear participant ID for unknown
```

- Cosine similarity is computed between the recording's per-speaker centroid and each profile's centroid
- Both vectors are L2-normalized before the dot product
- Top 5 candidates are returned; candidates below `MIN_CANDIDATE_THRESHOLD` (0.40) are filtered out of the `topCandidates` list

##### 3d. Duplicate Auto-Match Detection

```python
auto_matches = {}  # Track: participant_id -> speaker_label

if match["status"] == "auto" and match["participant_id"]:
    pid = match["participant_id"]
    if pid in auto_matches:
        # Two speakers matched to same participant
        prev_label = auto_matches[pid]
        prev_sim = results[prev_label]["similarity"]
        curr_sim = match["similarity"]

        if curr_sim > prev_sim:
            results[prev_label]["status"] = "suggest"  # Demote previous
            auto_matches[pid] = speaker_label           # Keep current
        else:
            result["status"] = "suggest"                # Demote current
```

- If two different speakers in the same recording auto-match to the same participant, the one with **lower similarity** is demoted from `auto` to `suggest`
- The higher-confidence match keeps `auto` status

#### 4. Merge Results into speaker_mapping

Back in `_identify_recording` (`job_executor.py` lines 600-701), results are merged into the transcription's `speaker_mapping`:

**For `auto` matches:**
```python
merged_mapping[speaker_label] = {
    "participantId": result["participant_id"],
    "confidence": result["similarity"],
    "manuallyVerified": False,
    "identificationStatus": "auto",
    "similarity": result["similarity"],
    "topCandidates": result["top_candidates"],
    "identifiedAt": now,
    "embedding": result["embedding"],   # 192-dim centroid stored
    "identificationHistory": [...],
}
```

**For `suggest` matches:**
```python
merged_mapping[speaker_label] = {
    "identificationStatus": "suggest",
    "similarity": result["similarity"],
    "suggestedParticipantId": result["participant_id"],
    "topCandidates": result["top_candidates"],
    "identifiedAt": now,
    "embedding": result["embedding"],
    "identificationHistory": [...],
}
```

**For `unknown` matches:**
```python
merged_mapping[speaker_label] = {
    "identificationStatus": "unknown",
    "similarity": result["similarity"],
    "topCandidates": result["top_candidates"],
    "identifiedAt": now,
    "embedding": result["embedding"],
    "identificationHistory": [...],
}
```

**For `embedding_only`** (verified + training, no embedding):
- Only updates `embedding` and appends `embedding_extracted` to history
- Also calls `profile.update([centroid], recording_id=recording_id)` to immediately update the speaker profile

#### 5. Set Recording Status

```python
final_status = "needs_review" if has_suggestions else "completed"
recording.speaker_identification_status = final_status
```

- `has_suggestions` is `True` if ANY speaker got `suggest` or `unknown` status
- `needs_review` means the recording will appear in the review queue
- `completed` means all speakers were auto-matched

#### 6. Save Profiles

After processing all recordings for a user, profiles are saved once:
```python
if profiles_dirty:
    self.profile_manager.save_profiles(user.id, profile_db)
```

### speaker_mapping Structure After Identification

The `transcription.speaker_mapping` is a `Dict[str, SpeakerMapping]` where keys are speaker labels (e.g., `"Speaker 1"`, `"Speaker 2"`).

Each value is a `SpeakerMapping` Pydantic model with these fields:

```python
class SpeakerMapping(BaseModel):
    confidence: Optional[float] = None
    displayName: Optional[str] = None           # enriched at query time, not stored
    manuallyVerified: Optional[bool] = None
    name: Optional[str] = None                  # legacy field
    participantId: Optional[str] = None
    reasoning: Optional[str] = None             # legacy field
    identificationStatus: Optional[str] = None  # "auto", "suggest", "unknown", "dismissed"
    similarity: Optional[float] = None          # cosine similarity
    suggestedParticipantId: Optional[str] = None
    suggestedDisplayName: Optional[str] = None  # enriched at query time
    topCandidates: Optional[List[TopCandidate]] = None
    identifiedAt: Optional[str] = None          # ISO timestamp
    embedding: Optional[List[float]] = None     # 192-dim centroid (stripped from API responses)
    useForTraining: Optional[bool] = None
    identificationHistory: Optional[List[IdentificationHistoryEntry]] = None
```

---

## C. The Review/Labeling Flow

### Review UI Structure

The frontend has two places where speaker identification results are surfaced:

1. **`SpeakerReviewView`** (`v3_frontend/src/components/reviews/SpeakerReviewView.tsx`): A dedicated review queue showing all recordings with pending speaker reviews. Split-panel layout: recording list on the left, speaker cards on the right.

2. **`TranscriptEntry` + `SpeakerConfidenceBadge`** (`v3_frontend/src/components/transcripts/`): Inline badges on each transcript entry showing identification status with accept/reject actions.

### What Happens When a User ACCEPTS a Suggestion

**Frontend (SpeakerReviewView.tsx `handleAccept`):**
1. Optimistic local state update: sets `identificationStatus: 'auto'`, `manuallyVerified: true`, `participantId` from the suggestion
2. Reads the `trainingFlags[speakerLabel]` state (checkbox value) to determine `useForTraining`
3. Calls `transcriptionsService.acceptSuggestion(transcriptionId, speakerLabel, participantId, useForTraining)`

**Frontend service call:**
```typescript
POST /api/transcription/{transcriptionId}/speaker/{speakerLabel}/accept
Body: { participantId?: string, useForTraining: boolean }
```

**Backend (`accept_speaker_suggestion` in api.py lines 1476-1600):**
1. Validates transcription exists and belongs to current user
2. Gets `participantId` from request body OR `suggestedParticipantId` from the mapping
3. Verifies participant exists in the database
4. Appends audit history entry with `action='accepted'`, `source='user_review_queue'`
5. Updates speaker_mapping entry:
   - `participantId = participant_id`
   - `manuallyVerified = True`
   - `confidence = similarity`
   - `identificationStatus = 'auto'`
   - `useForTraining = body.useForTraining` (default `False`)
   - Removes `suggestedParticipantId` and `suggestedDisplayName`
6. Saves updated mapping via `update_transcription_speaker_data_with_participants()`
7. **If `useForTraining` is True and embedding exists**: Calls `update_profile_from_mapping()` which loads the user's profile DB from blob storage, adds the embedding to the participant's profile, recalculates the centroid, and saves back
8. Checks if recording still has pending reviews; if not, updates `speaker_identification_status` to `'completed'`

### What Happens When a User REJECTS a Suggestion

**Frontend (`handleReject`):**
1. Optimistic update: `identificationStatus: 'unknown'`, clears suggestion fields
2. Calls `transcriptionsService.rejectSuggestion(transcriptionId, speakerLabel)`

**Backend (`reject_speaker_suggestion` in api.py lines 1605-1671):**
1. Validates ownership
2. Appends history entry: `action='rejected'`, `source='user_review_queue'`
3. Updates mapping:
   - `identificationStatus = 'unknown'`
   - Removes `suggestedParticipantId` and `suggestedDisplayName`
4. Saves via `update_transcription_speaker_data_with_participants()`
5. Does NOT trigger any profile update
6. Does NOT update recording review status (speaker remains pending)

### What Happens When a User DISMISSES a Speaker

**Frontend (`handleDismiss`):**
1. Optimistic update: `identificationStatus: 'dismissed'`
2. Calls `transcriptionsService.dismissSpeaker(transcriptionId, speakerLabel)`

**Backend (`dismiss_speaker` in api.py lines 1676-1743):**
1. Validates ownership
2. Appends history: `action='dismissed'`, `source='user_review_queue'`
3. Updates mapping:
   - `identificationStatus = 'dismissed'`
   - Removes suggestion fields
4. Saves mapping
5. Checks if recording still needs review (dismissed speakers don't count as pending)
6. **Important**: Dismissed speakers are permanently skipped by the sync service. When the worker processes this recording again, it checks:
   ```python
   if ex.get('identificationStatus') == 'dismissed':
       skip_speakers.add(label)
   ```

### What Happens When a User REASSIGNS a Speaker

**Frontend (SpeakerReviewView.tsx):**
- User can click a top candidate chip to accept that specific candidate (calls `handleAccept` with a specific `participantId`)
- Or use the `SpeakerAssignDropdown` to search for/create a participant and assign them (also calls `handleAccept`)
- From the audit view, there's a dedicated reassign endpoint

**Backend (`reassign_speaker` in api.py lines 1748-1846):**
```
POST /api/transcription/{transcriptionId}/speaker/{speakerLabel}/reassign
Body: { participantId: string, useForTraining: boolean }
```

1. Validates participant exists
2. Records old `participantId` for the response
3. Appends history: `action='reassigned'`, `source='user_audit_view'`
4. Updates mapping:
   - `participantId = new_participant_id`
   - `manuallyVerified = True`
   - `confidence = 1.0`
   - `identificationStatus = 'auto'`
   - `useForTraining = body.useForTraining`
5. If `useForTraining`, triggers profile update with stored embedding
6. Returns previous participant ID in response

### What Happens When a User Renames via Transcript Dropdown

**Frontend (TranscriptEntry.tsx):**
- The `SpeakerDropdown` component lets users type or select a name
- Calls `onSpeakerRename(speakerLabel, newName)` which propagates up to the transcript view
- This follows a different code path (legacy name-based assignment) that updates the speaker_mapping with participant linkage

---

## D. Training Data Management

### The "Use for Training" Toggle

**Where it appears:**

1. **SpeakerReviewView** (`SpeakerReviewView.tsx`): A `<Checkbox label="Use for training">` appears below each speaker card. It's available for all non-dismissed speakers.

2. **SpeakerConfidenceBadge** (`SpeakerConfidenceBadge.tsx`): For `auto`-identified speakers, a brain icon (`BrainCircuit20Regular`) badge appears next to the confidence badge. Blue when enabled, gray when disabled. Clicking toggles training.

**UI behavior:**
- The checkbox reads from `trainingFlags[label] ?? mapping.useForTraining ?? false`
- When changed on an already-resolved speaker, it immediately calls the toggle API
- When set before accepting (during review), the flag is passed with the accept call

### When Training Is Enabled: Immediate Effects

**Frontend:**
```typescript
await transcriptionsService.toggleTraining(transcriptionId, speakerLabel, newVal);
```

**Backend (`toggle_speaker_training` in api.py lines 1851-1954):**

```
POST /api/transcription/{transcriptionId}/speaker/{speakerLabel}/training
Body: { useForTraining: true/false }
```

1. Appends history entry: `action='training_approved'` or `action='training_revoked'`
2. Sets `useForTraining` on the speaker_mapping entry
3. **If enabling training** (`useForTraining=True`):
   - Gets the stored `embedding` (192-dim centroid) from the speaker_mapping
   - Gets the `participantId` from the speaker_mapping
   - Calls `update_profile_from_mapping(user_id, participant_id, embedding, recording_id, display_name)`
4. **If disabling training**: Only sets the flag. Does NOT remove the embedding from the existing profile (this is a deliberate design decision).

### Profile Update Process

**Source: `speaker_profile_updater.py`**

```python
def update_profile_from_mapping(user_id, participant_id, embedding_list, recording_id=None, display_name=""):
    store = get_profile_store()
    embedding = np.array(embedding_list, dtype=np.float32)
    store.update_profile(user_id, participant_id, embedding, recording_id=recording_id, display_name=display_name)
```

Which calls `SpeakerProfileStore.update_profile()`:

```python
def update_profile(self, user_id, participant_id, embedding, recording_id=None, display_name=""):
    db = self.load_profiles(user_id)          # Load from blob
    profile = db.get_or_create(participant_id, display_name)
    profile.update([embedding], recording_id=recording_id)
    self.save_profiles(user_id, db)           # Save back to blob
```

Which calls `SpeakerProfile.update()`:

```python
def update(self, new_embs, recording_id=None, keep_max=500):
    if recording_id and recording_id not in self.recording_ids:
        self.recording_ids.append(recording_id)

    for e in new_embs:
        self.embeddings.append(l2_normalize(e))

    if len(self.embeddings) > keep_max:
        self.embeddings = self.embeddings[-keep_max:]  # Keep most recent

    mat = np.stack(self.embeddings, axis=0)
    centroid = mat.mean(axis=0)
    self.centroid = l2_normalize(centroid)
    self.n_samples = len(self.embeddings)

    if len(self.embeddings) > 1:
        distances = [1.0 - cosine_similarity(e, self.centroid) for e in self.embeddings]
        self.embedding_std = float(np.std(distances))
```

Key details:
- The embedding being added is itself a centroid (mean of up to 15 segment embeddings from one recording)
- It gets L2-normalized before being added to the profile's embedding list
- **Max samples: 500** (`keep_max=500`), keeping the most recent when exceeded
- After adding, the centroid is recalculated: mean of all stored embeddings, then L2-normalized
- `embedding_std` is recalculated: standard deviation of (1 - cosine_similarity) between each stored embedding and the new centroid

### Profile Rebuild Process

**Triggered by:** `POST /api/speaker-profiles/rebuild` (user-initiated from the review UI "Rebuild Profiles" button)

**Source: `speaker_profile_updater.py` `rebuild_all_profiles()`**

1. Starts with a completely **empty** `SpeakerProfileDB`
2. Queries ALL recordings for the user with completed transcriptions
3. For each recording's transcription, iterates through `speaker_mapping`:
   - Only includes speakers where **both** `manuallyVerified=True` AND `useForTraining=True`
   - Must have both `participantId` and `embedding`
4. For each qualifying speaker, calls `profile.update([embedding], recording_id=...)`
5. Saves the rebuilt profile DB, completely replacing the old one

This is a destructive operation -- it throws away the old profiles and rebuilds from scratch using only the embeddings currently stored in speaker_mappings.

---

## E. Re-rating

### What Triggers Re-rating?

Re-rating runs as **Phase C** of the job executor, after Phase B (speaker identification). It runs on every sync cycle for every user.

### How It Works

**Source: `job_executor.py` `_rerate_speakers_for_user()` (lines 410-562)**

Re-rating is **pure math** -- no ML inference, no audio download. It uses the 192-dim embeddings already stored in the `speaker_mapping` entries.

```python
AUTO_THRESHOLD = 0.78
SUGGEST_THRESHOLD = 0.68
```

#### Process:

1. Load current profiles for the user
2. Query all recordings with `speaker_identification_status IN ('needs_review', 'completed')`
3. For each recording's transcription, iterate through `speaker_mapping` entries
4. Only process speakers with `identificationStatus` of `'suggest'` or `'unknown'`
5. Only process speakers that have a stored `embedding`
6. Re-match the stored embedding against the **current** profile DB:

```python
match = profile_db.match_with_confidence(
    embedding,
    high_threshold=AUTO_THRESHOLD,    # 0.78
    low_threshold=SUGGEST_THRESHOLD,  # 0.68
)
```

#### What Can Change (Only Upgrades, Never Downgrades):

```python
# Only upgrade, never downgrade
if status == 'unknown' and new_status in ('suggest', 'auto'):
    pass  # upgrade allowed
elif status == 'suggest' and new_status == 'auto':
    pass  # upgrade allowed
else:
    continue  # no improvement, skip
```

Possible transitions:
- `unknown` -> `suggest` (profile improved, now above 0.68)
- `unknown` -> `auto` (profile improved, now above 0.78)
- `suggest` -> `auto` (profile improved, now above 0.78)
- `auto` -> anything: **NEVER** (not re-rated at all, since auto speakers don't match the filter)
- `suggest` -> `unknown`: **NEVER** (downgrade blocked)

#### When Upgraded:

For a `suggest` -> `auto` upgrade:
```python
d['identificationStatus'] = 'auto'
d['similarity'] = match['similarity']
d['topCandidates'] = match.get('top_candidates', [])
d['participantId'] = match['participant_id']
d['confidence'] = match['similarity']
d['manuallyVerified'] = False
d.pop('suggestedParticipantId', None)
```

For an `unknown` -> `suggest` upgrade:
```python
d['identificationStatus'] = 'suggest'
d['suggestedParticipantId'] = match['participant_id']
```

Each upgrade gets an audit trail entry with `action='rerated_{old}_to_{new}'`, `source='worker'`.

After updating the transcription, the recording's `speaker_identification_status` is checked. If no more `suggest`/`unknown` speakers remain, it's updated from `'needs_review'` to `'completed'`.

### Why Re-rating Matters

As users verify speakers and approve training, the profile centroids improve. A speaker that was `unknown` (similarity 0.55) when first identified might now match at 0.72 (suggest) or 0.80 (auto) because the profile has more/better training data. Re-rating catches these improvements without needing to re-download and re-process the audio.

---

## F. Speaker Profile Data Model

### SpeakerProfile Fields

```python
class SpeakerProfile:
    participant_id: str            # Links to participant entity
    display_name: str              # Human-readable name
    centroid: Optional[np.ndarray] # 192-dim L2-normalized mean embedding
    n_samples: int                 # Number of embeddings in the profile
    embeddings: List[np.ndarray]   # All stored embeddings (up to 500)
    recording_ids: List[str]       # Provenance: which recordings contributed
    embedding_std: Optional[float] # Standard deviation of distances to centroid
```

### Centroid Calculation

The centroid is a **running mean of L2-normalized embeddings**:

```python
mat = np.stack(self.embeddings, axis=0)    # (N, 192) matrix
centroid = mat.mean(axis=0)                 # element-wise mean
self.centroid = l2_normalize(centroid)       # L2-normalize the mean
```

This is NOT a weighted average -- every embedding counts equally.

### Max Samples

**500 embeddings** per profile (`keep_max=500`). When exceeded, the oldest embeddings are dropped:
```python
if len(self.embeddings) > keep_max:
    self.embeddings = self.embeddings[-keep_max:]
```

### embedding_std Calculation

```python
if len(self.embeddings) > 1:
    distances = [1.0 - cosine_similarity(e, self.centroid) for e in self.embeddings]
    self.embedding_std = float(np.std(distances))
```

- For each stored embedding, compute `1 - cosine_similarity(embedding, centroid)`
- Take the standard deviation of these distances
- This measures how consistent/varied the speaker's voice samples are
- Lower values = more consistent voice profile
- Currently computed but not actively used in matching decisions

### Storage Format

Stored as a single JSON blob per user in Azure Blob Storage:

- **Container**: `speaker-profiles`
- **Path**: `{userId}/profiles.json`
- **Format**: JSON (~1.5KB per profile)

```json
{
  "profiles": {
    "participant-uuid-1": {
      "participant_id": "participant-uuid-1",
      "display_name": "John Smith",
      "centroid": [0.123, -0.456, ...],  // 192 floats
      "n_samples": 5,
      "recording_ids": ["rec-1", "rec-2", "rec-3"],
      "embedding_std": 0.0234
    }
  }
}
```

**Important**: The individual embeddings are NOT stored in the JSON blob -- only the centroid. However, the profile's in-memory `embeddings` list is maintained during a sync run. When `rebuild_all_profiles` runs, it reconstructs from the embeddings stored in each transcription's `speaker_mapping.embedding`.

Wait -- reviewing the code more carefully: `SpeakerProfile.to_dict()` only serializes `centroid`, NOT `embeddings`. This means:

1. During a single sync run, the in-memory profile accumulates all embeddings and maintains a proper centroid
2. When saved to blob, only the centroid is persisted
3. On next load, `n_samples` is preserved but the individual embeddings list is NOT restored
4. When `update()` is called after loading, new embeddings are added to an empty list, so the centroid becomes biased toward newer samples
5. The `rebuild_all_profiles` function correctly handles this by reconstructing from scratch

This is a known design trade-off: the blob stays small (~1.5KB per profile), but incremental updates after reload effectively weight recent embeddings more heavily.

### SpeakerProfileDB

```python
class SpeakerProfileDB:
    profiles: dict[str, SpeakerProfile]  # participant_id -> SpeakerProfile
```

Methods:
- `get_or_create(participant_id, display_name)` -- get existing or create new
- `match(embedding)` -- find best match (returns participant_id, similarity)
- `match_top_n(embedding, n=5)` -- find top N matches sorted by similarity
- `match_with_confidence(embedding, high_threshold=0.78, low_threshold=0.68, top_n=5)` -- match with confidence bands

---

## G. All API Endpoints Involved

### GET /api/speaker-reviews

**Purpose:** Get recordings with pending speaker identification reviews.

**Query params:** `status` (suggest|unknown|all, default 'all'), `limit` (default 50, max 100), `offset`

**Returns:** Paginated list of `{ recording, transcription (enriched), suggestCount, unknownCount }`

**Side effects:** None (read-only). Enriches transcription with participant displayNames at query time. Strips embeddings from API response.

---

### POST /api/transcription/{id}/speaker/{label}/accept

**Purpose:** Accept a speaker identification suggestion.

**Body:** `{ participantId?: string, useForTraining: boolean }`

**What it does:**
1. Sets `participantId`, `manuallyVerified=True`, `identificationStatus='auto'`
2. Appends `'accepted'` to identification history
3. If `useForTraining=True` and embedding exists, updates speaker profile in blob storage
4. Checks if recording still needs review

**Side effects:** May update speaker profile blob, may update recording status

---

### POST /api/transcription/{id}/speaker/{label}/reject

**Purpose:** Reject a speaker suggestion.

**Body:** None

**What it does:**
1. Sets `identificationStatus='unknown'`, clears suggestion fields
2. Appends `'rejected'` to identification history

**Side effects:** None beyond transcription update. Speaker remains in review queue.

---

### POST /api/transcription/{id}/speaker/{label}/dismiss

**Purpose:** Permanently skip a speaker ("don't care").

**Body:** None

**What it does:**
1. Sets `identificationStatus='dismissed'`
2. Appends `'dismissed'` to identification history
3. Checks if recording still needs review

**Side effects:** Speaker will be permanently skipped by the sync service worker in future runs.

---

### POST /api/transcription/{id}/speaker/{label}/reassign

**Purpose:** Reassign a speaker to a different participant (from audit view).

**Body:** `{ participantId: string, useForTraining: boolean }`

**What it does:**
1. Sets `participantId` to new value, `manuallyVerified=True`, `confidence=1.0`, `identificationStatus='auto'`
2. Appends `'reassigned'` to identification history with `source='user_audit_view'`
3. If `useForTraining=True`, updates speaker profile

**Side effects:** May update speaker profile blob. Returns `previousParticipantId` in response.

---

### POST /api/transcription/{id}/speaker/{label}/training

**Purpose:** Toggle whether a speaker's embedding is used for voice profile training.

**Body:** `{ useForTraining: boolean }`

**What it does:**
1. Sets `useForTraining` flag
2. Appends `'training_approved'` or `'training_revoked'` to history
3. If enabling: triggers immediate profile update with stored embedding
4. If disabling: only sets the flag (does NOT remove from profile)

**Side effects:** When enabling, loads profile DB from blob, adds embedding, recalculates centroid, saves.

---

### POST /api/transcription/{id}/reidentify

**Purpose:** Re-queue a transcription for speaker identification by the worker.

**Body:** None

**What it does:**
1. Clears identification data for non-verified, non-dismissed speakers (removes `identificationStatus`, `similarity`, `embedding`, `participantId`, etc.)
2. Keeps manually verified and dismissed speakers untouched
3. Sets `recording.speaker_identification_status = 'not_started'`

**Side effects:** The worker will pick this up on its next run and re-process the recording (Phase B). Requires audio re-download and ML inference.

---

### POST /api/speaker-profiles/rebuild

**Purpose:** Rebuild all speaker profiles from scratch using stored embeddings.

**Body:** None

**What it does:**
1. Creates empty `SpeakerProfileDB`
2. Iterates ALL transcriptions for the user
3. For each speaker with `manuallyVerified=True` AND `useForTraining=True` AND has `embedding`, adds to profile
4. Saves rebuilt profiles, replacing old blob entirely

**Side effects:** Destructive -- old profiles are completely replaced. Returns stats: `{ profiles_rebuilt, embeddings_processed, errors }`.

---

### GET /api/speaker-audit

**Purpose:** Get the audit trail of all speaker identification actions.

**Query params:** `limit` (default 100, max 200), `offset`

**Returns:** Flattened list of history entries across all recordings/speakers, enriched with recording/speaker context.

**Side effects:** None (read-only).

---

## H. Data Flows Between Frontend, Backend, and Sync Service

### Flow 1: New Recording Completes Transcription

```
Sync Service (cron)
  |
  +--> Phase A: Poll Azure Speech Services
  |      Result: recording marked transcription_status='completed'
  |
  +--> Phase B: Speaker Identification
  |      1. Download audio from Azure Blob Storage
  |      2. Load diarization from transcript_json
  |      3. Extract ECAPA-TDNN embeddings
  |      4. Build per-speaker centroids
  |      5. Load user's speaker profiles (from speaker-profiles/{userId}/profiles.json)
  |      6. Match centroids against profiles (cosine similarity)
  |      7. Write results to transcription.speaker_mapping in CosmosDB
  |      8. Set recording.speaker_identification_status ('completed' or 'needs_review')
  |
  +--> Phase C: Re-rate existing recordings
  |      (pure math, no audio needed)
  |
  +--> Phase D: Fetch new Plaud recordings
```

### Flow 2: User Reviews Speaker in UI

```
Frontend (SpeakerReviewView)
  |
  +--> GET /api/speaker-reviews
  |      Backend queries recordings with needs_review status
  |      Enriches transcription with participant displayNames
  |      Strips embeddings from response
  |
  +--> User clicks "Accept" on a suggestion
  |      POST /api/transcription/{id}/speaker/{label}/accept
  |      Body: { participantId: "...", useForTraining: true }
  |      |
  |      Backend:
  |        1. Updates speaker_mapping in CosmosDB
  |        2. If useForTraining:
  |           - Reads embedding from speaker_mapping (already in CosmosDB)
  |           - Loads speaker-profiles/{userId}/profiles.json from blob
  |           - Adds embedding to profile, recalculates centroid
  |           - Saves profiles.json back to blob
  |        3. Checks if recording still needs_review
  |
  +--> Next sync service run (cron, typically every 15 minutes):
         Phase C re-rates all suggest/unknown speakers
         The improved profile may cause upgrades (unknown->suggest, suggest->auto)
```

### Flow 3: User Toggles Training on Existing Speaker

```
Frontend (SpeakerConfidenceBadge brain icon click)
  |
  +--> POST /api/transcription/{id}/speaker/{label}/training
  |      Body: { useForTraining: true }
  |      |
  |      Backend:
  |        1. Sets useForTraining flag in speaker_mapping
  |        2. If enabling AND embedding exists AND participantId exists:
  |           - Loads profile from blob storage
  |           - Adds embedding to profile
  |           - Saves profile back
  |        3. If disabling: only sets flag, no profile change
```

### Flow 4: User Rebuilds Profiles

```
Frontend (SpeakerReviewView "Rebuild Profiles" button)
  |
  +--> POST /api/speaker-profiles/rebuild
  |      |
  |      Backend:
  |        1. Creates empty SpeakerProfileDB
  |        2. Scans ALL transcriptions for user
  |        3. Collects embeddings where manuallyVerified=True AND useForTraining=True
  |        4. Builds profiles from scratch
  |        5. Saves to speaker-profiles/{userId}/profiles.json (replaces old)
  |
  +--> Next sync service run:
         Phase B: New recordings matched against rebuilt profiles
         Phase C: Existing recordings re-rated against rebuilt profiles
```

### Flow 5: User Triggers Re-identification

```
Frontend
  |
  +--> POST /api/transcription/{id}/reidentify
  |      |
  |      Backend:
  |        1. Clears auto/suggest identification data (keeps verified/dismissed)
  |        2. Sets recording.speaker_identification_status = 'not_started'
  |
  +--> Next sync service run:
         Phase B picks up recording (matches 'not_started' query)
         Re-downloads audio, re-extracts embeddings, re-matches
```

### Key Data Locations

| Data | Storage | Accessed By |
|------|---------|-------------|
| Speaker mapping (identification results) | CosmosDB `transcriptions` container, `speaker_mapping` field | All three tiers |
| Speaker embeddings (192-dim centroids) | CosmosDB inside `speaker_mapping.embedding` | Backend + Sync Service |
| Speaker profiles (aggregated centroids) | Azure Blob `speaker-profiles/{userId}/profiles.json` | Backend + Sync Service |
| Recording status | CosmosDB `recordings` container, `speaker_identification_status` | All three tiers |
| Participant data | CosmosDB `recordings` container (type='participant') | Backend (enrichment at query time) |

### Data NOT Shared

- Raw audio segments: Only accessed transiently by the sync service during embedding extraction
- Individual per-segment embeddings: Discarded after centroid calculation; only the centroid is stored
- Profile embeddings list: NOT persisted to blob (only centroid is serialized)
- Torch model: Only loaded in the sync service container
