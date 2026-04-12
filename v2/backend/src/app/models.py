"""Pydantic models — single source of truth for all data shapes.

TypeScript types are generated from the OpenAPI spec that FastAPI produces from these models.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RecordingSource(str, Enum):
    plaud = "plaud"
    upload = "upload"
    paste = "paste"


class RecordingStatus(str, Enum):
    pending = "pending"
    transcoding = "transcoding"
    transcribing = "transcribing"
    processing = "processing"  # AI post-processing (title, description, speaker ID)
    ready = "ready"
    failed = "failed"


class SyncRunStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    aborted = "aborted"


class SyncTrigger(str, Enum):
    scheduled = "scheduled"
    manual = "manual"


class IdentificationStatus(str, Enum):
    auto = "auto"
    suggest = "suggest"
    unknown = "unknown"
    dismissed = "dismissed"


# ---------------------------------------------------------------------------
# Speaker mapping (stored as JSON in recordings.speaker_mapping)
# ---------------------------------------------------------------------------


class TopCandidate(BaseModel):
    """A candidate speaker match."""

    participantId: str = ""
    displayName: str = ""
    similarity: float = 0.0


class SpeakerMappingEntry(BaseModel):
    """Speaker identification data for one speaker label.

    All fields use camelCase. Legacy snake_case data should be migrated
    via the normalize_speaker_mappings.py script.
    """

    participantId: str | None = None
    displayName: str | None = None
    confidence: float | None = None
    manuallyVerified: bool = False
    identificationStatus: IdentificationStatus | str | None = None
    similarity: float | None = None
    suggestedParticipantId: str | None = None
    suggestedDisplayName: str | None = None
    topCandidates: list[TopCandidate] | None = None
    identifiedAt: str | None = None
    useForTraining: bool = False
    embedding: list[float] | None = None  # 192-dim ECAPA-TDNN


SpeakerMapping = dict[str, SpeakerMappingEntry]


# ---------------------------------------------------------------------------
# Plaud metadata (stored as JSON in recordings.plaud_metadata_json)
# ---------------------------------------------------------------------------


class PlaudMetadata(BaseModel):
    plaud_id: str
    original_timestamp: int | None = None  # unix ms
    filename: str | None = None
    file_size: int | None = None
    duration_ms: int | None = None
    file_type: str | None = None
    synced_at: str | None = None


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class User(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None
    role: str = "user"
    azure_oid: str | None = None
    plaud_enabled: bool = False
    plaud_token: str | None = None
    plaud_last_sync: datetime | None = None
    settings_json: str | None = None
    api_key: str | None = None
    created_at: datetime | None = None
    last_login: datetime | None = None


class UserProfile(BaseModel):
    """User profile for API responses. Includes plaud_token since this is a personal app."""

    id: str
    name: str | None = None
    email: str | None = None
    role: str = "user"
    plaud_enabled: bool = False
    plaud_token: str | None = None
    plaud_last_sync: datetime | None = None
    api_key: str | None = None
    created_at: datetime | None = None
    last_login: datetime | None = None


class Recording(BaseModel):
    id: str
    user_id: str

    # Audio metadata
    title: str | None = None
    description: str | None = None
    original_filename: str
    file_path: str | None = None
    duration_seconds: float | None = None
    recorded_at: datetime | None = None
    source: RecordingSource

    # Plaud
    plaud_id: str | None = None
    plaud_metadata_json: str | None = None

    # Processing
    status: RecordingStatus = RecordingStatus.pending
    status_message: str | None = None
    provider_job_id: str | None = None
    processing_started: datetime | None = None
    processing_completed: datetime | None = None
    retry_count: int = 0

    # Transcript
    transcript_text: str | None = None
    diarized_text: str | None = None
    transcript_json: str | None = None
    token_count: int | None = None
    speaker_mapping: str | None = None  # JSON string of SpeakerMapping

    # Search (AI-generated)
    search_summary: str | None = None
    search_keywords: str | None = None  # JSON array

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Participant(BaseModel):
    id: str
    user_id: str
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    aliases: str | None = None  # JSON array
    email: str | None = None
    role: str | None = None
    organization: str | None = None
    relationship: str | None = None
    notes: str | None = None
    is_user: bool = False
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Tag(BaseModel):
    id: str
    user_id: str
    name: str
    color: str
    created_at: datetime | None = None


class AnalysisTemplate(BaseModel):
    id: str
    user_id: str
    name: str
    prompt: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SyncRun(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: SyncRunStatus
    trigger: SyncTrigger
    type: str | None = Field(default="plaud_sync")
    stats_json: str | None = None
    error_message: str | None = None
    logs_json: str | None = None
    users_processed: str | None = None  # JSON array
    created_at: datetime | None = None


class DeletedPlaudId(BaseModel):
    user_id: str
    plaud_id: str
    deleted_at: datetime | None = None


# ---------------------------------------------------------------------------
# API request/response schemas
# ---------------------------------------------------------------------------


class RecordingSummary(BaseModel):
    """Lightweight recording for list views — no transcript text."""

    id: str
    user_id: str
    title: str | None = None
    description: str | None = None
    original_filename: str
    duration_seconds: float | None = None
    recorded_at: datetime | None = None
    source: RecordingSource
    status: RecordingStatus
    token_count: int | None = None
    plaud_id: str | None = None
    speaker_names: list[str] | None = None
    tag_ids: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecordingDetail(BaseModel):
    """Full recording with transcript data."""

    id: str
    user_id: str
    title: str | None = None
    description: str | None = None
    original_filename: str
    file_path: str | None = None
    duration_seconds: float | None = None
    recorded_at: datetime | None = None
    source: RecordingSource
    status: RecordingStatus
    status_message: str | None = None
    token_count: int | None = None
    plaud_id: str | None = None

    # Transcript
    transcript_text: str | None = None
    diarized_text: str | None = None
    transcript_json: str | None = None
    speaker_mapping: SpeakerMapping | None = None

    # Search (AI-generated)
    search_summary: str | None = None
    search_keywords: list[str] | None = None

    # Tags
    tag_ids: list[str] | None = None

    # Collections this recording belongs to
    collections: list[dict] | None = None  # [{id, name}]

    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaginatedResponse(BaseModel):
    data: list = []
    total: int = 0
    page: int = 1
    per_page: int = 50


class RecordingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    recorded_at: datetime | None = None


class SpeakerAssignment(BaseModel):
    participant_id: str
    manually_verified: bool = True
    use_for_training: bool = False


class PasteTranscriptRequest(BaseModel):
    title: str | None = None
    transcript_text: str
    source_app: str | None = None  # "zoom", "teams", etc.
    recorded_at: datetime | None = None


class ParticipantCreate(BaseModel):
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    aliases: list[str] | None = None
    email: str | None = None
    role: str | None = None
    organization: str | None = None
    relationship: str | None = None
    notes: str | None = None
    is_user: bool = False


class ParticipantUpdate(BaseModel):
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    aliases: list[str] | None = None
    email: str | None = None
    role: str | None = None
    organization: str | None = None
    relationship: str | None = None
    notes: str | None = None
    is_user: bool | None = None


class TagCreate(BaseModel):
    name: str = Field(max_length=32)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class AnalysisTemplateCreate(BaseModel):
    name: str
    prompt: str  # Must contain {transcript}


class AnalysisTemplateUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None


class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str


class ChatRequest(BaseModel):
    recording_id: str
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    message: str
    usage: dict | None = None
    response_time_ms: int | None = None


class AnalysisRequest(BaseModel):
    template_id: str


class PlaudSettingsUpdate(BaseModel):
    plaud_enabled: bool | None = None
    plaud_token: str | None = None


class SyncRunType(str, Enum):
    plaud_sync = "plaud_sync"
    speaker_id = "speaker_id"
    profile_rebuild = "profile_rebuild"
    transcription_poll = "transcription_poll"


class RunLogEntry(BaseModel):
    id: int
    timestamp: str
    level: str
    message: str


class SyncRunSummary(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: SyncRunStatus
    trigger: SyncTrigger
    type: str | None = Field(default="plaud_sync")
    stats_json: str | None = None
    error_message: str | None = None
    users_processed: str | None = None
    created_at: datetime | None = None


class SyncRunDetail(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: SyncRunStatus
    trigger: SyncTrigger
    type: str | None = Field(default="plaud_sync")
    stats_json: str | None = None
    error_message: str | None = None
    logs_json: str | None = None
    users_processed: str | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Deep search
# ---------------------------------------------------------------------------


class DeepSearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class TagMapEntry(BaseModel):
    recording_id: str
    title: str
    date: str | None = None
    speakers: list[str] | None = None


class DeepSearchResult(BaseModel):
    answer: str
    tag_map: dict[str, TagMapEntry]
    sources: list[str]


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class Collection(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    item_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionItem(BaseModel):
    recording_id: str
    title: str | None = None
    date: datetime | None = None
    speakers: list[str] | None = None
    added_at: datetime | None = None


class CollectionDetail(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    item_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items: list[CollectionItem] = []


class CollectionSearchRecord(BaseModel):
    id: str
    collection_id: str
    question: str
    answer_preview: str | None = None
    item_count: int | None = None
    item_set_hash: str | None = None
    search_id: str | None = None
    created_at: datetime | None = None


class CreateCollection(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class UpdateCollection(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class AddItemsRequest(BaseModel):
    recording_ids: list[str]


class SearchToAddRequest(BaseModel):
    query: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    speaker: str | None = None


class CreateFromCandidatesRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    recording_ids: list[str]


# ---------------------------------------------------------------------------
# MCP Tokens
# ---------------------------------------------------------------------------


class McpTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class McpTokenResponse(BaseModel):
    id: str
    token_name: str
    token_prefix: str
    raw_token: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None


class McpSpeaker(BaseModel):
    label: str
    display_name: str | None = None
    participant_id: str | None = None
