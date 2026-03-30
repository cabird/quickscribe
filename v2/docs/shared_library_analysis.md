# Shared Library Analysis: shared_quickscribe_py

Comprehensive analysis of the `shared_quickscribe_py` package for rewrite planning.

---

## 1. Package Structure

```
shared_quickscribe_py/
  setup.py                          # Package definition (setuptools, not pyproject.toml)
  shared_quickscribe_py/
    __init__.py                     # Version "0.1.0"
    config/
      __init__.py                   # Re-exports settings classes
      settings.py                   # Pydantic-based settings with feature flags
    cosmos/
      __init__.py                   # Heavy re-export layer (models, handlers, factories)
      models.py                     # AUTO-GENERATED Pydantic models from TypeScript
      recording_handler.py          # RecordingHandler + extended Recording model
      transcription_handler.py      # TranscriptionHandler + extended Transcription model
      user_handler.py               # UserHandler + extended User/PlaudSettings models
      analysis_type_handler.py      # AnalysisTypeHandler + extended AnalysisType model
      participant_handler.py        # ParticipantHandler + extended Participant model
      sync_progress_handler.py      # SyncProgressHandler + extended SyncProgress model
      job_execution_handler.py      # JobExecutionHandler (uses base model directly)
      manual_review_handler.py      # ManualReviewItemHandler (uses base model directly)
      deleted_items_handler.py      # DeletedItemsHandler + extended DeletedItems model
      locks_handler.py              # LocksHandler (distributed locking, no model)
      handler_factory.py            # Flask request-scoped handler factories (uses flask.g)
      util.py                       # filter_cosmos_fields() - strips _rid, _self, _etag, etc.
      helpers.py                    # slugify() utility
    azure_services/
      __init__.py                   # Re-exports all service clients
      blob_storage.py               # BlobStorageClient, QueueStorageClient, send_transcoding_job()
      azure_openai.py               # AzureOpenAIClient with sync/async/concurrent/timing variants
      speech_service.py             # AzureSpeechClient - PLACEHOLDER, all methods raise NotImplementedError
    plaud/
      __init__.py                   # Re-exports PlaudClient, AudioFile, PlaudResponse
      client.py                     # PlaudClient - fetches recordings, downloads files from Plaud.AI
    logging/
      __init__.py                   # Re-exports get_logger
      config.py                     # get_logger() - thin wrapper around Python logging
    speaker_profiles/
      __init__.py                   # Re-exports profile classes
      profile_store.py              # SpeakerProfile, SpeakerProfileDB, SpeakerProfileStore (blob-backed)
```

### Key Observations
- The package uses `setup.py` (not `pyproject.toml`) for packaging
- Models are auto-generated from TypeScript via a two-step process
- Each handler file defines an "extended" model that subclasses the generated base model, adding datetime parsing, serialization, and defaults
- The handler_factory.py is tightly coupled to Flask (`flask.g`) for request-scoped instances
- Two separate factory patterns exist: `get_*_handler()` (Flask request-scoped) and `create_*_handler()` (standalone)

---

## 2. TypeScript-to-Python Model Generation

### Pipeline

```
shared/Models.ts
    |
    | typescript-json-schema (npm package)
    v
shared/models.schema.json
    |
    | datamodel-codegen (Python package)
    v
shared_quickscribe_py/cosmos/models.py
```

### Makefile (shared_quickscribe_py/Makefile)
```makefile
build: shared_quickscribe_py/cosmos/models.py

shared_quickscribe_py/cosmos/models.py: $(SHARED_DIR)/Models.ts
    typescript-json-schema $(SHARED_DIR)/Models.ts "*" --propOrder --required \
        --out $(SHARED_DIR)/models.schema.json
    datamodel-codegen --input $(SHARED_DIR)/models.schema.json \
        --input-file-type jsonschema --output-model-type pydantic_v2.BaseModel \
        --use-subclass-enum --output shared_quickscribe_py/cosmos/models.py
```

### Problems with This Approach
1. **Generated code has ugly enum names**: `Status`, `Status1`, `Status11`, `Status12`, `Status13`, `Status15`, `Status16` -- these are meaningless
2. **`Integer` type becomes `RootModel[float]`** -- TypeScript's `type integer = number` confuses the generator
3. **`T` generic becomes empty class** -- `ApiResponse<T>` generates as `class T(BaseModel): pass`
4. **Duplicated Status enums** -- same success/error pattern generates multiple identical enums
5. **API request/response types are generated but mostly unused in Python** -- they exist only because they're in the same TS file
6. **Manual patches required** -- After generation, several fields are manually added to models.py (e.g., `SpeakerMapping.embedding`, `SpeakerMapping.identificationHistory`, `Recording.speaker_identification_status`)

---

## 3. Data Models (Complete Field Definitions)

### 3.1 User
```python
# Base (generated): models.User
class User(BaseModel):
    id: str                              # "user-{uuid4}"
    type: Optional[str] = None           # "user"
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None           # "user" | "admin"
    created_at: Optional[str] = None     # ISO datetime
    last_login: Optional[str] = None     # ISO datetime
    azure_oid: Optional[str] = None      # Azure AD Object ID
    plaudSettings: Optional[PlaudSettings] = None
    is_test_user: Optional[bool] = None
    tags: Optional[List[Tag]] = None     # User's custom tags (stored inline)
    partitionKey: str                    # Always "user"

# Extended (user_handler.py): Adds datetime parsing + updated_at field
class User(models.User):
    plaudSettings: Optional[PlaudSettings] = None  # Uses extended PlaudSettings
    created_at: Optional[datetime] = None           # Parsed to datetime objects
    last_login: Optional[datetime] = None
    updated_at: Optional[datetime] = None           # Not in TypeScript source!
```

### 3.2 PlaudSettings (embedded in User)
```python
class PlaudSettings(BaseModel):
    bearerToken: str
    lastSyncTimestamp: Optional[str] = None
    enableSync: Optional[bool] = None
    activeSyncToken: Optional[str] = None
    activeSyncStarted: Optional[str] = None

# Extended: Overrides datetime fields to actual datetime objects
```

### 3.3 Tag (embedded in User)
```python
class Tag(BaseModel):
    id: str       # Slugified name (e.g., "meeting", "self-memos")
    name: str     # Display name
    color: str    # Hex color code
```

### 3.4 Recording
```python
class Recording(BaseModel):
    id: str                                          # uuid4
    type: Optional[str] = None                       # "recording"
    user_id: str                                     # FK to User.id
    original_filename: str
    unique_filename: str                             # Blob storage filename
    title: Optional[str] = None                      # Defaults to original_filename
    description: Optional[str] = None                # AI-generated
    recorded_timestamp: Optional[str] = None         # When actually recorded
    duration: Optional[float] = None                 # Seconds
    participants: Optional[Union[List[str], List[RecordingParticipant]]] = None  # DEPRECATED

    # Transcription tracking
    transcription_status: Optional[TranscriptionStatus] = None    # not_started|in_progress|completed|failed
    transcription_status_updated_at: Optional[str] = None
    transcription_id: Optional[str] = None           # FK to Transcription.id
    token_count: Optional[float] = None              # Denormalized from transcription
    az_transcription_id: Optional[str] = None
    transcription_error_message: Optional[str] = None
    transcription_job_id: Optional[str] = None
    transcription_job_status: Optional[TranscriptionJobStatus] = None
    last_check_time: Optional[str] = None

    # Transcoding tracking
    transcoding_status: Optional[TranscodingStatus] = None       # not_started|queued|in_progress|completed|failed
    transcoding_started_at: Optional[str] = None
    transcoding_completed_at: Optional[str] = None
    transcoding_error_message: Optional[str] = None
    transcoding_retry_count: Optional[int] = None
    transcoding_token: Optional[str] = None

    upload_timestamp: Optional[str] = None
    source: Optional[Source] = None                  # "upload"|"plaud"|"stream"
    plaudMetadata: Optional[PlaudMetadata] = None

    # Processing failure tracking
    processing_failure_count: Optional[int] = None
    needs_manual_review: Optional[bool] = None
    last_failure_message: Optional[str] = None

    partitionKey: str                                # Always "recording"
    tagIds: Optional[List[str]] = None               # References Tag.id
    is_dummy_recording: Optional[bool] = None
    testRunId: Optional[str] = None
    chunkGroupId: Optional[str] = None               # Links chunks from same original
    speaker_identification_status: Optional[str] = None  # Manually added, not in generated code
```

**Note**: Recording has 35+ fields, many of which are status/error tracking for the async pipeline. This is a very wide document.

### 3.5 Transcription
```python
class Transcription(BaseModel):
    id: str                                          # uuid4
    type: Optional[str] = None                       # "transcription"
    user_id: str                                     # FK to User.id
    recording_id: str                                # FK to Recording.id
    diarized_transcript: Optional[str] = None        # Full text with "Speaker N:" labels
    text: Optional[str] = None                       # Non-diarized text
    transcript_json: Optional[str] = None            # Raw JSON transcription data
    az_raw_transcription: Optional[str] = None       # Raw Azure result JSON string
    az_transcription_id: Optional[str] = None
    token_count: Optional[float] = None              # Calculated via tiktoken
    speaker_mapping: Optional[Dict[str, SpeakerMapping]] = None  # "Speaker 1" -> mapping
    analysisResults: Optional[List[AnalysisResult]] = None       # AI analyses stored inline
    partitionKey: str                                # Always "transcription"
    testRunId: Optional[str] = None
```

### 3.6 SpeakerMapping (embedded in Transcription.speaker_mapping values)
```python
class SpeakerMapping(BaseModel):
    # Core mapping
    participantId: Optional[str] = None              # FK to Participant.id
    confidence: Optional[float] = None               # 0-1
    manuallyVerified: Optional[bool] = None
    displayName: Optional[str] = None                # Enriched at query time

    # Speaker identification
    identificationStatus: Optional[str] = None       # "auto"|"suggest"|"unknown"|"dismissed"
    similarity: Optional[float] = None               # Cosine similarity
    suggestedParticipantId: Optional[str] = None
    suggestedDisplayName: Optional[str] = None
    topCandidates: Optional[List[TopCandidate]] = None
    identifiedAt: Optional[str] = None
    embedding: Optional[List[float]] = None          # 192-dim voice embedding (excluded from API)
    useForTraining: Optional[bool] = None
    identificationHistory: Optional[List[IdentificationHistoryEntry]] = None

    # Legacy
    name: Optional[str] = None                       # @deprecated
    reasoning: Optional[str] = None                  # @deprecated
```

### 3.7 AnalysisResult (embedded in Transcription.analysisResults)
```python
class AnalysisResult(BaseModel):
    analysisType: str                                # References AnalysisType.name
    analysisTypeId: str                              # References AnalysisType.id
    content: str                                     # Generated text
    createdAt: str
    status: Status                                   # "completed"|"failed"|"pending"
    errorMessage: Optional[str] = None
    llmResponseTimeMs: Optional[float] = None
    promptTokens: Optional[float] = None
    responseTokens: Optional[float] = None
```

### 3.8 Participant
```python
class Participant(BaseModel):
    id: str                                          # uuid4
    type: Optional[str] = None                       # "participant"
    userId: str                                      # Owner
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    displayName: str
    aliases: List[str]
    email: Optional[str] = None
    role: Optional[str] = None                       # Job title
    organization: Optional[str] = None
    relationshipToUser: Optional[str] = None
    notes: Optional[str] = None
    isUser: Optional[bool] = None                    # Is this the user themselves?
    firstSeen: str                                   # ISO datetime
    lastSeen: str                                    # ISO datetime
    createdAt: str
    updatedAt: str
    partitionKey: str                                # userId (actual user-based partitioning)
```

### 3.9 AnalysisType
```python
class AnalysisType(BaseModel):
    id: str                                          # uuid4
    type: Optional[str] = None                       # "analysis_type"
    name: str                                        # Slug identifier
    title: str                                       # Display name
    shortTitle: str                                  # Max 12 chars, for tabs
    description: str
    icon: str                                        # Icon identifier
    prompt: str                                      # LLM prompt template with {transcript}
    userId: Optional[str] = None                     # null for built-in
    isActive: bool
    isBuiltIn: bool
    createdAt: str
    updatedAt: str
    partitionKey: str                                # "global" for built-in, userId for custom
```

### 3.10 SyncProgress
```python
class SyncProgress(BaseModel):
    id: str                                          # Same as syncToken
    type: Optional[str] = None                       # "sync_progress"
    syncToken: str
    userId: str
    status: Status15                                 # queued|processing|completed|failed
    totalRecordings: Optional[float] = None
    processedRecordings: float
    failedRecordings: float
    currentStep: str
    estimatedCompletion: Optional[str] = None
    errors: List[str]
    startTime: str
    lastUpdate: str
    ttl: Optional[float] = None                      # TTL in seconds
    partitionKey: str                                # userId
```

### 3.11 JobExecution
```python
class JobExecution(BaseModel):
    id: str                                          # uuid4
    type: Optional[str] = None                       # "job_execution"
    userId: Optional[str] = None
    status: Status11                                 # running|completed|failed
    triggerSource: TriggerSource                     # scheduled|manual
    startTime: str
    endTime: Optional[str] = None
    logs: Optional[List[JobLogEntry]] = None
    stats: JobExecutionStats                         # All the counters
    errorMessage: Optional[str] = None
    usersProcessed: Optional[List[str]] = None
    ttl: int                                         # 30 days
    partitionKey: str                                # Always "job_execution"
    testRunId: Optional[str] = None
    duration: Optional[int] = None                   # Computed, not stored
    durationFormatted: Optional[str] = None          # Computed, not stored
```

### 3.12 ManualReviewItem
```python
class ManualReviewItem(BaseModel):
    id: str
    type: Optional[str] = None                       # "manual_review"
    userId: str
    recordingId: str                                 # FK to Recording.id
    recordingTitle: str                              # Denormalized
    failureCount: int                                # >= 3
    lastError: str
    failureHistory: List[FailureRecord]
    status: Status12                                 # pending|in_progress|resolved|dismissed
    assignedTo: Optional[str] = None
    resolution: Optional[str] = None
    createdAt: str
    updatedAt: str
    resolvedAt: Optional[str] = None
    partitionKey: str                                # userId
    testRunId: Optional[str] = None
```

### 3.13 DeletedItems
```python
class DeletedItems(BaseModel):
    id: str                                          # "deleted_items_{userId}"
    type: Optional[str] = None                       # "deleted_items"
    userId: str
    items: Items                                     # Contains category arrays
    partitionKey: str                                # Always "deleted_items"
    createdAt: str
    updatedAt: str

class Items(BaseModel):
    plaud_recording: Optional[List[str]] = None      # Plaud IDs
    manual_upload: Optional[List[str]] = None        # Future use
    transcription: Optional[List[str]] = None        # Future use
    participant: Optional[List[str]] = None          # Future use
```

### 3.14 SpeakerProfile (not in Models.ts -- Python-only)
```python
class SpeakerProfile:
    participant_id: str
    display_name: str
    centroid: Optional[np.ndarray]     # Mean of L2-normalized embeddings (192-dim)
    n_samples: int
    embeddings: List[np.ndarray]       # Raw embeddings (up to 500)
    recording_ids: List[str]           # Provenance tracking
    embedding_std: Optional[float]     # Spread metric
```

---

## 4. CosmosDB Handlers -- Complete Method Inventory

### 4.1 RecordingHandler
**Container**: `recordings` | **Partition Key**: `"recording"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_recording` | `(user_id, original_filename, unique_filename, transcription_status?, transcoding_status?, source?, title?, recorded_timestamp?) -> Recording` | Creates with uuid4 ID |
| `get_recording` | `(recording_id) -> Optional[Recording]` | Point read by ID |
| `get_user_recordings` | `(user_id) -> List[Recording]` | Query by user_id |
| `get_all_recordings` | `(user_id?) -> List[Recording]` | All recordings, optionally filtered, ordered by recorded_timestamp DESC |
| `get_recording_summaries` | `(user_id) -> List[dict]` | Projected query (subset of fields) for list view |
| `get_recordings_by_ids` | `(recording_ids) -> List[Recording]` | Batch get with chunked IN clause (100 per chunk) |
| `get_user_plaud_ids` | `(user_id) -> List[str]` | Projected query for just plaudMetadata.plaudId |
| `delete_recording` | `(recording_id) -> None` | Point delete |
| `update_recording` | `(recording) -> Recording` | Replace item |
| `add_tags_to_recording` | `(recording_id, tag_ids) -> Optional[Recording]` | Read-modify-write |
| `remove_tags_from_recording` | `(recording_id, tag_ids) -> Optional[Recording]` | Read-modify-write |
| `remove_tag_from_all_user_recordings` | `(user_id, tag_id) -> int` | Bulk query + update |

**Note**: RecordingHandler internally creates a TranscriptionHandler (unused in most paths). Each handler creates its own `CosmosClient` instance.

### 4.2 TranscriptionHandler
**Container**: `recordings` (SAME container as recordings) | **Partition Key**: `"transcription"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_transcription` | `(user_id, recording_id, test_run_id?) -> Transcription` | Creates with uuid4 ID |
| `get_transcription` | `(transcription_id) -> Optional[Transcription]` | Point read |
| `get_transcription_by_recording` | `(recording_id) -> Optional[Transcription]` | Query by recording_id |
| `get_transcription_by_az_id` | `(az_transcription_id) -> Optional[Transcription]` | Query by Azure Speech ID |
| `get_transcriptions_by_ids` | `(transcription_ids) -> List[Transcription]` | Batch query |
| `update_transcription` | `(transcription) -> Transcription` | Upsert with auto token_count calculation |
| `delete_transcription` | `(transcription_id) -> None` | Point delete |
| `get_all_transcriptions` | `() -> List[Transcription]` | All transcriptions |
| `get_transcriptions_for_user` | `(user_id) -> List[Transcription]` | Query by user_id |
| `get_speaker_mappings_for_user` | `(user_id) -> List[Dict]` | Projected query for just recording_id + speaker_mapping |
| `calculate_token_count` | `(text) -> int` | Static method using tiktoken (o200k_base encoding) |
| `transform_transcript_with_speaker_names` | `(transcript_text, speaker_mapping) -> str` | Static method: replaces "Speaker N:" with names |

### 4.3 UserHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `"user"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_user` | `(email, name, role?) -> User` | ID format: "user-{uuid4}" |
| `get_user` | `(user_id) -> Optional[User]` | Point read |
| `get_user_by_name` | `(name) -> List[User]` | Query by name |
| `get_user_by_azure_oid` | `(azure_oid) -> Optional[User]` | Query by Azure AD OID |
| `get_all_users` | `() -> List[User]` | All users |
| `save_user` | `(user) -> Optional[User]` | Replace item |
| `update_user` | `(user_id, email?, name?, role?, plaudSettingsDict?) -> Optional[User]` | Legacy method |
| `delete_user` | `(user_id) -> None` | Point delete |
| `get_user_files` | `(user_id) -> List[Recording]` | Cross-partition query |
| `get_user_transcriptions` | `(user_id) -> List[Transcription]` | Cross-partition query |
| `get_test_users` | `() -> List[Dict]` | Projected query for test users |
| `ensure_default_tags` | `(user) -> User` | Adds default tags if none exist |
| `get_user_tags` | `(user_id) -> List[Tag]` | Get tags with auto-default |
| `create_tag` | `(user_id, name, color) -> Optional[Tag]` | Duplicate check + slugify |
| `update_tag` | `(user_id, tag_id, name?, color?) -> Optional[Tag]` | Read-modify-write |
| `delete_tag` | `(user_id, tag_id) -> bool` | **BUG**: References `db_handlers.recording_handler` which doesn't exist in the shared lib |

### 4.4 ParticipantHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `userId` (actual user-based partitioning)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_participant` | `(user_id, **participant_data) -> Participant` | Creates with uuid4 |
| `get_participant` | `(user_id, participant_id) -> Optional[Participant]` | Point read with user partition |
| `get_participants_for_user` | `(user_id) -> List[Participant]` | Query ordered by displayName |
| `update_participant` | `(user_id, participant_id, updates) -> Optional[Participant]` | Read-modify-write |
| `delete_participant` | `(user_id, participant_id) -> bool` | Point delete |
| `find_participants_by_name` | `(user_id, name, fuzzy?) -> List[Participant]` | Complex query with fuzzy/exact matching, multi-word support |
| `save_participant` | `(participant) -> Participant` | Upsert |
| `update_participant_last_seen` | `(user_id, participant_id, timestamp?) -> bool` | Convenience method |

**Note**: ParticipantHandler is the ONLY handler using actual user-based partitioning. All others use static partition keys.

### 4.5 AnalysisTypeHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `"global"` (built-in) or `userId` (custom)

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_analysis_types_for_user` | `(user_id) -> List[AnalysisType]` | Two queries: global + user-specific |
| `create_analysis_type` | `(name, title, short_title, description, icon, prompt, user_id) -> Optional[AnalysisType]` | With name uniqueness check |
| `update_analysis_type` | `(type_id, user_id, updates) -> Optional[AnalysisType]` | Ownership + built-in check |
| `delete_analysis_type` | `(type_id, user_id) -> bool` | Ownership + built-in check |
| `get_analysis_type_by_id` | `(type_id, partition_key) -> Optional[AnalysisType]` | Point read |
| `get_builtin_analysis_types` | `() -> List[AnalysisType]` | Query global partition |
| `create_builtin_analysis_type` | `(name, title, short_title, description, icon, prompt) -> Optional[AnalysisType]` | Admin/seeding |
| `get_all_analysis_types` | `() -> List[AnalysisType]` | Cross-partition query |
| `_is_name_taken` | `(name, user_id) -> bool` | Checks both user + global namespaces |

### 4.6 SyncProgressHandler
**Container**: `sync_progress` (DIFFERENT container) | **Partition Key**: `userId`

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_progress` | `(sync_token, user_id, status?, current_step?) -> SyncProgress` | With container auto-create |
| `get_progress` | `(sync_token, user_id) -> Optional[SyncProgress]` | Query by token + userId |
| `update_progress` | `(sync_token, user_id, **updates) -> Optional[SyncProgress]` | Read-modify-write |
| `add_error` | `(sync_token, user_id, error_message) -> Optional[SyncProgress]` | Append error + increment counter |
| `mark_completed` | `(sync_token, user_id) -> Optional[SyncProgress]` | Status update |
| `mark_failed` | `(sync_token, user_id, error_message?) -> Optional[SyncProgress]` | Status update |
| `check_stale_syncs` | `() -> int` | Find and fail syncs queued > 2 hours |
| `cleanup_expired_progress` | `() -> int` | Delete records > 24 hours old |

**Note**: SyncProgressHandler takes a pre-built `CosmosClient` (different constructor pattern from all other handlers).

### 4.7 JobExecutionHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `"job_execution"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_job_execution` | `(job_execution) -> JobExecution` | Takes pre-built model |
| `get_job_execution` | `(job_id) -> Optional[JobExecution]` | Point read |
| `update_job_execution` | `(job_execution) -> JobExecution` | Upsert |
| `get_recent_jobs` | `(limit?) -> List[JobExecution]` | TOP N ordered by startTime |
| `get_jobs_by_user` | `(user_id, limit?) -> List[JobExecution]` | Filtered by userId |
| `delete_job_execution` | `(job_id) -> None` | Point delete |
| `query_jobs` | `(limit, offset, min_duration?, has_activity?, status?, trigger_source?, user_id?, start_date?, end_date?, sort_by?, sort_order?) -> Tuple[List[Dict], int]` | Advanced filtering with client-side post-processing |

**Note**: `query_jobs` fetches ALL matching records then filters client-side for complex conditions and pagination. This is wasteful.

### 4.8 ManualReviewItemHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `"manual_review"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_manual_review_item` | `(manual_review_item) -> ManualReviewItem` | Takes pre-built model |
| `get_manual_review_item` | `(item_id) -> Optional[ManualReviewItem]` | Point read |
| `get_by_recording_id` | `(recording_id) -> Optional[ManualReviewItem]` | Query by recordingId |
| `update_manual_review_item` | `(manual_review_item) -> ManualReviewItem` | Upsert |
| `get_pending_items` | `(limit?) -> List[ManualReviewItem]` | Filtered by status='pending' |
| `get_items_by_user` | `(user_id, limit?) -> List[ManualReviewItem]` | Filtered by userId |
| `delete_manual_review_item` | `(item_id) -> None` | Point delete |

### 4.9 LocksHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `"locks"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `acquire_lock` | `(lock_id, owner_id, ttl_seconds?) -> bool` | Create-if-not-exists with expiry check |
| `release_lock` | `(lock_id, owner_id) -> bool` | Delete with ownership verification |
| `is_lock_held` | `(lock_id) -> bool` | Existence check |
| `get_lock_owner` | `(lock_id) -> Optional[str]` | Read owner field |

### 4.10 DeletedItemsHandler
**Container**: `recordings` (SAME container) | **Partition Key**: `"deleted_items"` (static string)

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_user_deleted_items` | `(user_id) -> Optional[DeletedItems]` | Point read |
| `get_deleted_plaud_ids` | `(user_id) -> List[str]` | Extract plaud_recording list |
| `add_deleted_plaud_id` | `(user_id, plaud_id) -> bool` | Append to list, create doc if needed |
| `remove_deleted_plaud_id` | `(user_id, plaud_id) -> bool` | Remove from list |
| `delete_user_deleted_items` | `(user_id) -> bool` | Delete entire doc |

---

## 5. Database Schema Summary

### Container Layout

Almost everything is in a SINGLE container (`recordings`) with different `partitionKey` values acting as "logical tables":

| Logical Entity | Partition Key Value | partitionKey Field | Note |
|---------------|--------------------|--------------------|------|
| Recording | `"recording"` | Static | All recordings in one partition |
| Transcription | `"transcription"` | Static | All transcriptions in one partition |
| User | `"user"` | Static | All users in one partition |
| Participant | `userId` | Dynamic | Properly partitioned per user |
| AnalysisType | `"global"` or `userId` | Mixed | Built-in types vs custom |
| JobExecution | `"job_execution"` | Static | All jobs in one partition |
| ManualReviewItem | `"manual_review"` | Static | All review items in one partition |
| Lock | `"locks"` | Static | All locks in one partition |
| DeletedItems | `"deleted_items"` | Static | All deleted tracking in one partition |

**Separate Container**:
| Container | Partition Key | Note |
|-----------|-------------|------|
| `sync_progress` | `userId` | Only one with its own container |

### Entity Relationships
```
User (1) ----< (N) Recording
User (1) ----< (N) Participant
User (1) ----< (N) AnalysisType (custom)
Recording (1) ----> (1) Transcription
Transcription.speaker_mapping[label] ----> Participant (via participantId)
Transcription.analysisResults[].analysisTypeId ----> AnalysisType
Recording.tagIds[] ----> User.tags[].id
Recording ----< ManualReviewItem (via recordingId)
User.plaudSettings ----> PlaudMetadata (on recordings with source="plaud")
```

---

## 6. Azure Service Clients

### 6.1 BlobStorageClient
```python
class BlobStorageClient:
    __init__(connection_string, container_name)
    upload_file(file_path, blob_filename) -> None
    download_file(blob_filename, local_file_path) -> None
    generate_sas_url(filename, read?, write?, hours?) -> str
    delete_blob(filename) -> None
    blob_exists(filename) -> bool
    delete_file(filename) -> None  # Alias for delete_blob
```

### 6.2 QueueStorageClient
```python
class QueueStorageClient:
    __init__(connection_string, queue_name)
    send_message(message: Dict) -> None  # JSON encodes dict and sends
```

### 6.3 send_transcoding_job (standalone function)
Generates SAS URLs for source and target blobs, then queues a transcoding message.

### 6.4 AzureOpenAIClient
```python
class AzureOpenAIClient:
    __init__(endpoint, api_key, deployment_name, api_version?)

    # Sync
    send_prompt(prompt, system_message?) -> str
    send_prompt_with_timing(prompt, system_message?) -> Dict  # {content, llmResponseTimeMs, promptTokens, responseTokens}
    send_messages_with_timing(messages: List[Dict]) -> Dict    # Raw messages array

    # Async (aiohttp)
    send_prompt_async(prompt, system_message?) -> str
    send_prompt_async_with_timing(prompt, system_message?) -> Dict
    send_multiple_prompts_concurrent(prompts, system_message?) -> List[str]
    send_multiple_prompts_concurrent_with_timing(prompts, system_message?) -> List[Dict]
```

Also provides backward-compatible module-level functions (`send_prompt_to_llm`, etc.) using a global default client.

### 6.5 AzureSpeechClient
**PLACEHOLDER ONLY** -- all methods raise `NotImplementedError`. The actual implementation lives in `plaud_sync_service/azure_speech/` using a swagger-generated client.

---

## 7. Configuration System

### Feature Flag Pattern
```python
settings = QuickScribeSettings()

# Feature flags (bool, env var driven)
settings.ai_enabled              # AZURE_OPENAI_* vars required when True
settings.cosmos_enabled           # AZURE_COSMOS_* vars required when True
settings.blob_storage_enabled     # AZURE_STORAGE_* vars required when True
settings.speech_services_enabled  # AZURE_SPEECH_* vars required when True
settings.plaud_enabled            # PLAUD_API_* vars required when True
settings.azure_ad_auth_enabled    # AZ_AUTH_* vars required when True
settings.assemblyai_enabled       # ASSEMBLYAI_* vars required when True
settings.plaud_sync_trigger_enabled  # PLAUD_SYNC_TRIGGER_* vars required when True

# Sub-settings (conditionally loaded based on flags)
settings.azure_openai: Optional[AzureOpenAISettings]
settings.cosmos: Optional[CosmosDBSettings]
settings.blob_storage: Optional[BlobStorageSettings]
settings.speech_services: Optional[SpeechServicesSettings]
settings.plaud_api: Optional[PlaudAPISettings]
settings.azure_ad_auth: Optional[AzureADAuthSettings]
settings.assemblyai: Optional[AssemblyAISettings]
settings.flask: Optional[FlaskSettings]           # Always loaded
settings.plaud_sync_trigger: Optional[PlaudSyncTriggerSettings]
```

Each sub-settings class uses `pydantic_settings.BaseSettings` with env prefixes (e.g., `AZURE_COSMOS_ENDPOINT`, `AZURE_COSMOS_KEY`).

**Problem**: The handler_factory.py does NOT use this settings system. It imports `from config import config` -- a different Flask-specific config module in the backend. This means the shared settings system and the factory are disconnected.

---

## 8. Plaud Client

```python
class PlaudClient:
    __init__(bearer_token, logger_instance?)

    fetch_recordings(limit?, skip?, is_trash?, sort_by?, is_desc?) -> Optional[PlaudResponse]
    get_file_download_url(file_id) -> str
    download_file(audio_file: AudioFile, output_dir) -> Optional[str]
    filter_recordings_by_ids(recordings, processed_ids) -> List[AudioFile]
    filter_recordings_by_timestamp(recordings, after_timestamp) -> List[AudioFile]
```

Key details:
- Uses hardcoded Plaud API URLs (`https://api.plaud.ai/file/simple/web`)
- Spoofs browser headers to appear as a Chrome web client
- Files with `.opus` extension are actually MP3 (handled in `download_file`)
- `AudioFile` is a dataclass (not Pydantic) with computed properties
- `to_metadata()` converts to PlaudMetadata format for storage

---

## 9. Speaker Profile System

Stored in Azure Blob Storage (not CosmosDB):

```
speaker-profiles/{userId}/profiles.json
```

- `SpeakerProfile`: Per-participant voice profile with running centroid (mean of L2-normalized 192-dim embeddings)
- `SpeakerProfileDB`: In-memory dictionary of profiles with matching methods
- `SpeakerProfileStore`: Blob Storage wrapper (load/save entire DB per user)

Matching confidence bands:
- `>= 0.78`: "auto" -- high confidence, auto-assign
- `>= 0.68`: "suggest" -- medium confidence, show candidates
- `< 0.68`: "unknown" -- no match

---

## 10. Dependencies

From `setup.py`:

| Package | Version | Purpose |
|---------|---------|---------|
| `azure-cosmos` | >= 4.7.0 | CosmosDB SDK |
| `azure-storage-blob` | >= 12.23.0 | Blob Storage SDK |
| `azure-storage-queue` | >= 12.12.0 | Queue Storage SDK |
| `azure-identity` | >= 1.19.0 | Azure auth (imported but not directly used in shared lib) |
| `pydantic` | >= 2.9.0 | Data models |
| `pydantic-settings` | >= 2.0.0 | Settings from env vars |
| `httpx` | >= 0.27.0 | Listed but NOT used (requests is used instead) |
| `requests` | >= 2.32.0 | HTTP client for Plaud API and OpenAI |
| `python-dotenv` | >= 1.0.0 | Env file loading |
| `mutagen` | >= 1.47.0 | Audio metadata (listed but NOT used in shared lib) |
| `tiktoken` | >= 0.5.0 | Token counting for transcriptions |
| `typer[all]` | >= 0.9.0 | CLI framework (listed but NOT used in shared lib) |
| `aiohttp` | (unlisted) | Used by AzureOpenAIClient async methods but not in install_requires |
| `numpy` | (unlisted) | Used by speaker_profiles but not in install_requires |
| `python-dateutil` | (unlisted) | Used by LocksHandler but not in install_requires |

**Missing from install_requires**: `aiohttp`, `numpy`, `python-dateutil`
**Unnecessary in install_requires**: `httpx`, `mutagen`, `typer[all]`, `azure-identity` (for shared lib scope)

---

## 11. Technical Debt & Issues

### 11.1 Is CosmosDB Overkill?

**Yes, significantly.** For a 1-few user app:

- **Cost**: CosmosDB charges per RU (Request Unit) plus storage. Even at minimum provisioning (~$25/mo for 400 RU/s), this is expensive for a personal/small-team tool.
- **Complexity**: The SDK requires partition keys, cross-partition queries, manual system field filtering, and explicit client management.
- **Single-container design**: Almost everything is crammed into one container with static partition keys like `"recording"`, `"user"`, `"transcription"`. This means:
  - ALL recordings for ALL users are in a single partition -- no horizontal scaling benefit
  - Cross-partition queries are used for many operations (defeats CosmosDB's strength)
  - Only Participant uses actual user-based partitioning

**Better alternatives for 1-few users**:
- **SQLite**: Zero-cost, embedded, perfect for single-server deployment. With WAL mode, handles concurrent reads fine.
- **PostgreSQL**: If you want a proper server DB. JSONB columns can handle flexible schema. Free tier on most cloud providers.
- **DuckDB**: If analytics/querying matters. Embedded like SQLite but with better analytical query support.
- **Even JSON files on disk**: For this scale, you could literally store recordings metadata as JSON files and it would work.

### 11.2 Separate Containers for Recordings and Transcriptions?

Recordings and transcriptions are already in the SAME container (both in `recordings` container, differentiated by `partitionKey`). The question is whether they should be merged at the data model level.

**Case for merging**:
- 1:1 relationship (every recording has at most one transcription)
- `recording.transcription_id` is just a FK to the same container
- Many operations need both (display recording + transcript text)
- Would eliminate the cross-document join and reduce read operations
- The separate-document design adds complexity with no clear benefit

**Case for keeping separate**:
- Transcription documents can be large (full transcript text + raw JSON + speaker mappings)
- Recording list views don't need transcript text
- The existing `get_recording_summaries()` already does field projection

**Recommendation**: Merge them. The "summaries" pattern can be handled by SQL projections or a view. Having them separate creates consistency issues (orphaned transcriptions, syncing transcription_status).

### 11.3 Over-Engineering & Unnecessary Complexity

1. **Model generation pipeline**: TypeScript -> JSON Schema -> Python is fragile and produces ugly code. Just define Python models directly (or use a shared schema format like OpenAPI/JSON Schema as the source of truth instead of TypeScript).

2. **Double model hierarchy**: Every handler file re-defines the model as a subclass of the generated model just to add datetime parsing. This is ~50 lines per handler of boilerplate. A single `DatetimeModel` mixin or model config would suffice.

3. **Handler factory pattern**: Two factory patterns exist (Flask request-scoped `get_*()` and standalone `create_*()`), and the Flask one imports from a backend-specific config module. The shared lib shouldn't depend on Flask.

4. **Every handler creates its own CosmosClient**: Each handler instantiates `CosmosClient(cosmos_url, cosmos_key)` in its `__init__`. With 10 handlers, that's 10 CosmosClient instances, each with their own connection pool. Should share a single client.

5. **`filter_cosmos_fields` on every read**: Every single read operation runs `filter_cosmos_fields()` to strip `_rid`, `_self`, etc. This should happen once in a base handler class.

6. **Error handling via print()**: Several handlers use `print(f"Error: ...")` instead of proper logging or exception propagation. Mixed with actual `logger.error()` calls in newer handlers.

7. **RecordingHandler creates TranscriptionHandler**: Line 59 of recording_handler.py: `self.transcription_handler = TranscriptionHandler(...)` -- but this is never used.

8. **`exclude_unset=True` inconsistency**: Some handlers use `model_dump(exclude_unset=True)` (which skips fields not set during construction), others use `model_dump()` (which includes all defaults). This causes subtle bugs where fields get dropped on update.

9. **Token count as float**: `token_count` is `Optional[float]` in the model (because TypeScript `number` -> JSON Schema `number` -> Python `float`), but `calculate_token_count()` returns `int`. The model should be `int`.

10. **Static partition keys**: Using `"recording"`, `"user"`, `"transcription"` as partition keys puts ALL documents of each type into a single partition. This provides zero scalability benefit from CosmosDB partitioning. For a 1-user app this doesn't matter, but it's architecturally wrong.

11. **`UserHandler.delete_tag` has an import bug**: It imports `from db_handlers.recording_handler import RecordingHandler` which is a backend-local path, not the shared lib path. This method will crash at runtime.

12. **Unused `httpx` dependency**: Listed in setup.py but never imported. `requests` is used everywhere instead.

13. **Missing dependencies**: `aiohttp`, `numpy`, and `python-dateutil` are used but not listed in `setup.py`.

### 11.4 Inconsistencies

- **Naming conventions**: Mix of `snake_case` (`user_id`, `recording_id`), `camelCase` (`partitionKey`, `userId`, `displayName`), reflecting the TypeScript origin
- **Handler constructor signatures**: SyncProgressHandler takes `CosmosClient` object; all others take `(cosmos_url, cosmos_key, database_name, container_name)` strings
- **Error patterns**: Some handlers return `None` on error, some raise exceptions, some do both
- **Partition key field**: Some models use `partitionKey` as a stored field value, some handlers hardcode it in queries
- **Datetime handling**: Some extended models parse strings to `datetime` objects (User, PlaudSettings), others keep ISO strings. The generated base models all use `str`.

---

## 12. What Actually Matters for a Rewrite

### Core Data Entities (keep)
1. **User** -- auth identity, settings, tags
2. **Recording** -- audio file metadata, processing status
3. **Transcription** -- transcript text, speaker mapping, analyses (consider merging into Recording)
4. **Participant** -- people profiles for speaker identification
5. **AnalysisType** -- configurable AI analysis templates

### Supporting Entities (simplify or eliminate)
6. **SyncProgress** -- only needed if keeping Plaud sync. Could be in-memory or a simple table.
7. **JobExecution** -- operational logging. Could be replaced with structured file logging.
8. **ManualReviewItem** -- failure queue. Rarely used, could be a simple flag on Recording.
9. **DeletedItems** -- Plaud-specific. One row per user tracking deleted IDs.
10. **Locks** -- distributed locking. With SQLite, use built-in transactions instead.

### Services to Keep
- **BlobStorageClient** -- still need cloud storage for audio files (or switch to local filesystem)
- **AzureOpenAIClient** -- or replace with a generic LLM client (OpenAI SDK, litellm, etc.)
- **PlaudClient** -- if keeping Plaud integration
- **SpeakerProfileStore** -- if keeping voice identification (could use local files)

### Services to Drop
- **QueueStorageClient + send_transcoding_job** -- if simplifying the transcoding pipeline
- **AzureSpeechClient** -- already a placeholder, real implementation is elsewhere
- **Settings system** -- vastly over-engineered for the number of config values. A simple `.env` + `os.getenv()` would suffice
