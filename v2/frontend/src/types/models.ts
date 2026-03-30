// =============================================================================
// QuickScribe v2 — TypeScript types matching backend Pydantic models
// =============================================================================

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type RecordingStatus =
  | "pending"
  | "transcoding"
  | "transcribing"
  | "processing"
  | "ready"
  | "failed";

export type RecordingSource = "plaud" | "upload" | "paste";

export type SyncRunStatus = "running" | "completed" | "failed" | "aborted";

export type SyncRunTrigger = "scheduled" | "manual";

export type SpeakerAssignmentStatus = "auto" | "suggested" | "manual" | "unknown";

// ---------------------------------------------------------------------------
// Core entities
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  name: string | null;
  email: string | null;
  role: string;
  azure_oid: string | null;
  plaud_enabled: boolean;
  plaud_last_sync: string | null;
  created_at: string;
  last_login: string | null;
  settings: UserSettings | null;
}

export interface UserSettings {
  plaud_token?: string;
  [key: string]: unknown;
}

export interface UserProfile {
  id: string;
  name: string | null;
  email: string | null;
  role: string;
  plaud_enabled: boolean;
  plaud_token: string | null;
  plaud_last_sync: string | null;
  api_key: string | null;
  created_at: string | null;
  last_login: string | null;
}

export interface Recording {
  id: string;
  user_id: string;
  title: string | null;
  description: string | null;
  original_filename: string;
  file_path: string | null;
  duration_seconds: number | null;
  recorded_at: string | null;
  source: RecordingSource;
  plaud_id: string | null;
  status: RecordingStatus;
  status_message: string | null;
  provider_job_id: string | null;
  processing_started: string | null;
  processing_completed: string | null;
  retry_count: number;
  transcript_text: string | null;
  diarized_text: string | null;
  transcript_json: unknown | null;
  token_count: number | null;
  speaker_mapping: Record<string, SpeakerMappingEntry> | null;
  search_summary: string | null;
  search_keywords: string[] | null;
  tags: Tag[];
  collections?: Array<{ id: string; name: string }>;
  created_at: string;
  updated_at: string;
}

/** Lightweight recording for list views (no transcript data). */
export interface RecordingSummary {
  id: string;
  user_id: string;
  title: string | null;
  description: string | null;
  original_filename: string;
  duration_seconds: number | null;
  recorded_at: string | null;
  source: RecordingSource;
  status: RecordingStatus;
  token_count: number | null;
  plaud_id: string | null;
  speaker_names: string[] | null;
  tag_ids: string[] | null;
  created_at: string;
  updated_at: string;
}

/** Full recording with transcript for detail view. */
export type RecordingDetail = Recording;

export interface TopCandidate {
  participantId: string;
  displayName?: string;
  similarity: number;
}

export interface IdentificationHistoryEntry {
  timestamp: string;
  action: string;
  participantId?: string;
  displayName?: string;
  similarity?: number;
  candidatesPresented?: TopCandidate[];
  source?: string;
}

export interface SpeakerMappingEntry {
  participantId?: string | null;
  displayName?: string | null;
  confidence?: number | null;
  manuallyVerified?: boolean;
  identificationStatus?: "auto" | "suggest" | "unknown" | "dismissed";
  similarity?: number | null;
  suggestedParticipantId?: string | null;
  suggestedDisplayName?: string | null;
  topCandidates?: TopCandidate[];
  identifiedAt?: string | null;
  useForTraining?: boolean;
  identificationHistory?: IdentificationHistoryEntry[];
  embedding?: number[] | null;
}

// ---------------------------------------------------------------------------
// Participants
// ---------------------------------------------------------------------------

export interface Participant {
  id: string;
  user_id: string;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  aliases: string[];
  email: string | null;
  role: string | null;
  organization: string | null;
  relationship: string | null;
  notes: string | null;
  is_user: boolean;
  first_seen: string | null;
  last_seen: string | null;
  created_at: string;
  updated_at: string;
}

export interface ParticipantWithRecordings extends Participant {
  recent_recordings: RecordingSummary[];
}

// ---------------------------------------------------------------------------
// Tags
// ---------------------------------------------------------------------------

export interface Tag {
  id: string;
  user_id: string;
  name: string;
  color: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Sync runs / jobs
// ---------------------------------------------------------------------------

export type SyncRunType = "plaud_sync" | "speaker_id" | "profile_rebuild" | "transcription_poll";

export interface SyncRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: SyncRunStatus;
  trigger: SyncRunTrigger;
  type: SyncRunType;
  stats: SyncRunStats | null;
  error_message: string | null;
  logs: SyncRunLogEntry[] | null;
  users_processed: string[] | null;
  created_at: string;
}

export interface SyncRunSummary {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: SyncRunStatus;
  trigger: SyncRunTrigger;
  type: SyncRunType;
  stats: SyncRunStats | null;
  error_message: string | null;
  created_at: string;
}

export type SyncRunDetail = SyncRun;

export interface SyncRunStats {
  transcriptions_checked: number;
  recordings_found: number;
  recordings_downloaded: number;
  recordings_transcribed: number;
  recordings_failed: number;
  [key: string]: number;
}

export interface SyncRunLogEntry {
  timestamp: string;
  level: "info" | "warning" | "error" | "debug";
  message: string;
}

export interface RunLogEntry {
  id: number;
  timestamp: string;
  level: string;
  message: string;
}

export interface RunLogsResponse {
  logs: RunLogEntry[];
  run_id: string;
}

// ---------------------------------------------------------------------------
// AI / Analysis
// ---------------------------------------------------------------------------

export interface AnalysisTemplate {
  id: string;
  user_id: string;
  name: string;
  prompt: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  recording_id: string;
  messages: ChatMessage[];
}

export interface ChatResponse {
  message: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  response_time_ms?: number;
}

export interface AnalysisRequest {
  template_id: string;
}

export interface AnalysisResponse {
  result: string;
}

// ---------------------------------------------------------------------------
// Deep Search
// ---------------------------------------------------------------------------

export interface DeepSearchTagMapEntry {
  recording_id: string;
  title: string;
  date?: string | null;
  speakers?: string[] | null;
}

export interface DeepSearchResult {
  answer: string;
  tag_map: Record<string, DeepSearchTagMapEntry>;
  sources: string[];
  search_id?: string;
}

export interface DeepSearchEvent {
  event: "status" | "tag_map" | "result" | "error" | "done";
  data: string | DeepSearchResult | Record<string, DeepSearchTagMapEntry>;
}

export interface SearchHistoryItem {
  search_id: string;
  question: string;
  answer_preview: string | null;
  answer: string | null;
  created_at: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  call_count: number;
}

export interface SearchHistoryDetail {
  search_id: string;
  question: string;
  answer: string | null;
  tag_map: Record<string, DeepSearchTagMapEntry>;
  created_at: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  call_count: number;
}

// ---------------------------------------------------------------------------
// API envelope types
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
  };
}

/** Response from POST /api/sync/trigger (202). */
export interface SyncTriggerResponse {
  run_id: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Request / filter types
// ---------------------------------------------------------------------------

export interface RecordingFilters {
  page?: number;
  per_page?: number;
  search?: string;
  status?: RecordingStatus;
  source?: RecordingSource;
  tag_id?: string;
  date_from?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface SyncRunFilters {
  page?: number;
  per_page?: number;
  status?: SyncRunStatus;
  trigger?: SyncRunTrigger;
  type?: SyncRunType;
}

export interface UpdateRecordingRequest {
  title?: string;
  description?: string;
}

export interface UploadRecordingRequest {
  file: File;
  title?: string;
  recorded_at?: string;
}

export interface PasteTranscriptRequest {
  title?: string;
  transcript_text: string;
  recorded_at?: string;
}

export interface CreateParticipantRequest {
  display_name: string;
  first_name?: string;
  last_name?: string;
  aliases?: string[];
  email?: string;
  role?: string;
  organization?: string;
  relationship?: string;
  notes?: string;
  is_user?: boolean;
}

export interface UpdateParticipantRequest {
  display_name?: string;
  first_name?: string;
  last_name?: string;
  aliases?: string[];
  email?: string;
  role?: string;
  organization?: string;
  relationship?: string;
  notes?: string;
  is_user?: boolean;
}

export interface CreateTagRequest {
  name: string;
  color: string;
}

export interface UpdateTagRequest {
  name?: string;
  color?: string;
}

export interface AssignSpeakerRequest {
  participant_id: string;
  use_for_training?: boolean;
}

export interface CreateAnalysisTemplateRequest {
  name: string;
  prompt: string;
}

export interface UpdateAnalysisTemplateRequest {
  name?: string;
  prompt?: string;
}

export interface UpdateSettingsRequest {
  plaud_enabled?: boolean;
  plaud_token?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Collections
// ---------------------------------------------------------------------------

export interface Collection {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionItem {
  recording_id: string;
  title: string | null;
  date: string | null;
  speakers: string[] | null;
  search_summary_snippet: string | null;
  in_collection: boolean;
  added_at: string;
}

export interface CollectionDetail extends Collection {
  items: CollectionItem[];
}

export interface CollectionSearchRecord {
  id: string;
  collection_id: string;
  question: string;
  answer_preview: string | null;
  item_count: number;
  item_set_hash: string | null;
  search_id: string | null;
  created_at: string;
}

export interface SearchToAddResult {
  id: string;
  title: string | null;
  description: string | null;
  original_filename: string;
  duration_seconds: number | null;
  recorded_at: string | null;
  source: RecordingSource;
  status: RecordingStatus;
  speaker_names: string[] | null;
  search_summary_snippet: string | null;
  in_collection: boolean;
}

export interface CreateCollectionRequest {
  name: string;
  description?: string;
}

export interface UpdateCollectionRequest {
  name?: string;
  description?: string;
}

export interface SearchToAddFilters {
  query?: string;
  date_from?: string;
  date_to?: string;
  speaker?: string;
}
