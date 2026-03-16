// shared/types.ts

type integer = number;

// Plaud settings stored in user profile
export interface PlaudSettings {
    bearerToken: string;          // Authentication token for Plaud API
    lastSyncTimestamp?: string;   // ISO date of last successful sync
    enableSync?: boolean;         // Whether sync is enabled (for future automatic sync)
    activeSyncToken?: string;     // Token for current active sync operation
    activeSyncStarted?: string;   // ISO date when current sync started
}

// Metadata for a recording from Plaud
export interface PlaudMetadata {
    plaudId: string;              // Original ID from Plaud (for deduplication)
    originalTimestamp: string;    // When the recording was made according to Plaud
    plaudFilename: string;        // Original filename in Plaud
    plaudFileSize: number;        // Size in bytes of original file
    plaudDuration: number;        // Duration in milliseconds from Plaud
    plaudFileType: string;        // Original file type/extension
    syncedAt: string;             // When this recording was imported to QuickScribe
}

// Represents a tag that can be applied to recordings
export interface Tag {
    id: string;        // Unique identifier (slugified name)
    name: string;      // Display name
    color: string;     // Hex color code (e.g., "#FF5733")
}

// Default tags for new users
export const DEFAULT_TAGS: Tag[] = [
    { id: "meeting", name: "Meeting", color: "#4444FF" },
    { id: "personal", name: "Personal", color: "#BB44BB" },
    { id: "self-memos", name: "Self Memos", color: "#44BB44" }
];

// Represents a participant in conversations (first-class entity)
export interface Participant {
    id: string;                    // UUID for participant
    type?: string;                 // Document type discriminator (always "participant")
    userId: string;                // Owner of this participant profile
    firstName?: string;            // First name
    lastName?: string;             // Last name
    displayName: string;           // How they should be displayed (e.g., "John Smith", "Dr. Johnson")
    aliases: string[];             // Alternative names/spellings they've been called
    email?: string;                // Contact info if known
    role?: string;                 // Their role/title (e.g., "CEO", "Project Manager")
    organization?: string;         // Company/org they belong to
    relationshipToUser?: string;   // "Colleague", "Boss", "Client", "Friend", etc.
    notes?: string;                // User notes about this person
    isUser?: boolean;              // True if this participant is the user themselves
    
    // Tracking (basic, not analytics)
    firstSeen: string;             // ISO date of first appearance
    lastSeen: string;              // ISO date of most recent appearance
    
    // Metadata
    createdAt: string;
    updatedAt: string;
    partitionKey: string;          // userId for partitioning
}

// Represents a participant's involvement in a specific recording
export interface RecordingParticipant {
    participantId: string;         // References Participant.id
    displayName: string;           // Denormalized for quick display
    speakerLabel: string;          // "Speaker 1", "Speaker 2", etc.
    confidence: number;            // AI confidence in identification (0-1)
    manuallyVerified: boolean;     // User confirmed this mapping
}

// Represents a user in the system
export interface User {
    id: string; // Unique identifier for the user
    type?: string; // Document type discriminator (always "user")
    name?: string; // Assumption: Not explicitly mentioned, possibly available from user handling methods
    email?: string; // Assumption: May be included depending on authentication setup
    role?: string; // Admin or user
    created_at?: string; // DateTime of when the user was created
    last_login?: string; // DateTime of when the user last logged in
    azure_oid?: string; // Azure AD Object ID for linking AAD accounts
    plaudSettings?: PlaudSettings; // Plaud integration settings
    partitionKey: string;
    is_test_user?: boolean; // Indicates if this is a test user for local development
    tags?: Tag[]; // User's custom tags
}

// Represents a recording entity
export interface Recording {
    id: string; // Unique identifier for the recording
    type?: string; // Document type discriminator (always "recording")
    user_id: string; // References the user who uploaded the recording
    original_filename: string; // Original filename of the uploaded file
    unique_filename: string; // Unique filename assigned to the uploaded file
    title?: string; // User-editable title for the recording (defaults to original_filename)
    description?: string; // AI-generated description (1-2 sentences about recording content)
    recorded_timestamp?: string; // ISO timestamp when the recording was actually made
    duration?: number; // Duration of the recording in seconds (may be unknown)
    participants?: string[] | RecordingParticipant[]; // DEPRECATED: Do not use. Speaker mappings are now stored in transcription.speaker_mapping only.
    
    // Transcription related fields
    transcription_status?: "not_started" | "in_progress" | "completed" | "failed"; // Transcription status with specific values
    transcription_status_updated_at?: string; // ISO timestamp for when transcription status last updated
    transcription_id?: string; // References the transcription id for this recording if one exists
    token_count?: number; // Approximate token count of transcript (denormalized from Transcription)
    az_transcription_id?: string; // Azure transcription ID if in progress or completed
    transcription_error_message?: string; // Error message if transcription fails
    transcription_job_id?: string; // Azure Speech Services batch job ID for tracking async transcription
    transcription_job_status?: "not_started" | "submitted" | "processing" | "completed" | "failed"; // Batch transcription job status
    last_check_time?: string; // ISO timestamp of last status check for pending transcription
    
    // Transcoding related fields
    transcoding_status?: "not_started" | "queued" | "in_progress" | "completed" | "failed"; // Transcoding status with specific values
    transcoding_started_at?: string; // ISO timestamp for when transcoding started
    transcoding_completed_at?: string; // ISO timestamp for when transcoding completed
    transcoding_error_message?: string; // Error message if transcoding fails
    transcoding_retry_count?: integer; // Number of times transcoding has been retried (default: 0)
    transcoding_token?: string // token used in the callback once the transcoding has completed
    
    upload_timestamp?: string; // DateTime of when the recording was uploaded
    source?: "upload" | "plaud" | "stream"; // Source of the recording
    plaudMetadata?: PlaudMetadata;          // Plaud-specific metadata (only present for Plaud recordings)

    // Processing failure tracking
    processing_failure_count?: integer; // Number of times processing has failed (default: 0)
    needs_manual_review?: boolean; // True if processing failed 3+ times and requires manual intervention
    last_failure_message?: string; // Most recent failure error message

    partitionKey: string;
    tagIds?: string[]; // Array of tag IDs assigned to this recording
    is_dummy_recording?: boolean; // Indicates if this is a dummy recording for testing
    testRunId?: string; // Test run identifier for cleanup purposes (only set during test runs)
    chunkGroupId?: string; // UUID linking all chunks from the same original recording (only set for chunked recordings)

    // Speaker identification
    speaker_identification_status?: 'not_started' | 'processing' | 'completed' | 'needs_review' | 'failed';

    // Enriched fields (API response only, not stored in database)
    speaker_names?: string[]; // Speaker display names enriched from transcription.speaker_mapping
}

// Progress tracking for Plaud sync operations
export interface SyncProgress {
    id: string; // Unique identifier (same as syncToken)
    type?: string; // Document type discriminator (always "sync_progress")
    syncToken: string; // Token identifying this sync operation
    userId: string; // User who initiated the sync
    status: 'queued' | 'processing' | 'completed' | 'failed'; // Current status
    totalRecordings?: number; // Total recordings found (set when processing starts)
    processedRecordings: number; // Number of recordings successfully processed
    failedRecordings: number; // Number of recordings that failed
    currentStep: string; // Current operation description
    estimatedCompletion?: string; // ISO timestamp of estimated completion
    errors: string[]; // Array of error messages for failed recordings
    startTime: string; // ISO timestamp when sync was initiated
    lastUpdate: string; // ISO timestamp of last progress update
    ttl?: number; // TTL for automatic cleanup (24 hours from start)
    partitionKey: string; // For CosmosDB partitioning
}

// Tracks deleted items to prevent re-syncing from external sources (e.g., Plaud cloud)
export interface DeletedItems {
    id: string; // Format: "deleted_items_{userId}"
    type?: string; // Document type discriminator (always "deleted_items")
    userId: string; // Owner of these deleted items
    items: {
        plaud_recording?: string[]; // Array of deleted Plaud IDs
        manual_upload?: string[]; // Array of deleted manual upload IDs (future use)
        transcription?: string[]; // Array of deleted transcription IDs (future use)
        participant?: string[]; // Array of deleted participant IDs (future use)
    };
    partitionKey: string; // Always "deleted_items"
    createdAt: string; // ISO timestamp when document was created
    updatedAt: string; // ISO timestamp of last modification
}

// Failure tracking for recordings that need manual review
export interface FailureRecord {
    timestamp: string; // ISO timestamp when the failure occurred
    error: string; // Error message
    step: string; // Which step failed (download, transcode, submit_transcription, etc.)
    attemptNumber: integer; // Which attempt this was (1, 2, 3, etc.)
}

// Manual review queue for recordings that failed 3+ times
export interface ManualReviewItem {
    id: string; // Unique identifier (UUID)
    type?: string; // Document type discriminator (always "manual_review")
    userId: string; // Owner of this recording
    recordingId: string; // References Recording.id
    recordingTitle: string; // Denormalized for quick display
    failureCount: integer; // Number of failures (always >= 3)
    lastError: string; // Most recent error message
    failureHistory: FailureRecord[]; // Complete failure history
    status: "pending" | "in_progress" | "resolved" | "dismissed"; // Review status
    assignedTo?: string; // Admin user handling this review
    resolution?: string; // Notes about how it was resolved
    createdAt: string; // ISO timestamp when first added to review queue
    updatedAt: string; // ISO timestamp of last update
    resolvedAt?: string; // ISO timestamp when resolved/dismissed
    partitionKey: string; // userId for efficient user-scoped queries
    testRunId?: string; // Test run identifier for cleanup purposes (only set during test runs)
}

// Log entry for job execution tracking
export interface JobLogEntry {
    timestamp: string; // ISO timestamp
    level: "debug" | "info" | "warning" | "error"; // Log level
    message: string; // Log message
    recordingId?: string; // Optional recording ID if log relates to specific recording
}

// Statistics for job execution
export interface JobExecutionStats {
    transcriptions_checked: integer; // Number of pending transcriptions checked
    transcriptions_completed: integer; // Number of transcriptions that completed
    recordings_found: integer; // New recordings from Plaud
    recordings_downloaded: integer; // Successfully downloaded
    recordings_transcoded: integer; // Successfully transcoded
    recordings_uploaded: integer; // Successfully uploaded to blob storage
    recordings_skipped: integer; // Skipped (already exist in database)
    transcriptions_submitted: integer; // Successfully submitted to Azure Speech
    errors: integer; // Total number of errors encountered
    chunks_created: integer; // Number of chunks created from large files
}

// Job execution tracking for Plaud sync service
export interface JobExecution {
    id: string; // Unique job identifier (UUID)
    type?: string; // Document type discriminator (always "job_execution")
    userId?: string; // User who triggered (null for scheduled jobs that process all users)
    status: "running" | "completed" | "failed"; // Execution status
    triggerSource: "scheduled" | "manual"; // How the job was triggered
    startTime: string; // ISO timestamp when execution began
    endTime?: string; // ISO timestamp when execution finished
    logs?: JobLogEntry[]; // Array of log entries (included in detail view, excluded from list view)
    stats: JobExecutionStats; // Summary statistics
    errorMessage?: string; // Critical error message if job failed
    usersProcessed?: string[]; // List of user IDs processed (for scheduled runs)
    ttl: integer; // Time-to-live in seconds (30 days = 2,592,000)
    partitionKey: string; // "job_execution" for all job execution records
    testRunId?: string; // Test run identifier for cleanup purposes (only set during test runs)

    // Computed fields (added by API, not stored in database)
    duration?: integer; // Duration in seconds (computed from startTime and endTime)
    durationFormatted?: string; // Human-readable duration (e.g., "5m 30s")
}

// API Response types for Plaud operations
export interface PlaudSyncResponse {
    message: string;
    sync_token: string;
    dry_run: boolean;
}

export interface PlaudSyncStatusResponse {
    hasSettings: boolean;
    syncEnabled: boolean;
    lastSyncTimestamp?: string;
    currentSyncActive: boolean;
    activeSyncToken?: string;
}

export interface PlaudSettingsResponse {
    plaudSettings: PlaudSettings;
}

export interface ActiveSyncCheckResponse {
    has_active_sync: boolean;
    sync_token?: string;
    progress?: SyncProgress;
}

// Represents an analysis type that can be applied to transcriptions
export interface AnalysisType {
    id: string; // Unique identifier (UUID)
    type?: string; // Document type discriminator (always "analysis_type")
    name: string; // Internal identifier (slug-like: "summary", "custom-meeting-notes")
    title: string; // Display name ("Generate Summary", "Custom Meeting Notes")
    shortTitle: string; // Short title for tabs ("Summary", "Keywords") - max 12 chars
    description: string; // User-facing description
    icon: string; // Icon identifier from predefined library
    prompt: string; // LLM prompt template with {transcript} placeholder
    userId?: string; // null for built-in types, userId for custom types
    isActive: boolean; // Admin can disable types
    isBuiltIn: boolean; // true for system defaults, false for user-created
    createdAt: string; // ISO timestamp
    updatedAt: string; // ISO timestamp
    partitionKey: string; // "global" for built-in, userId for custom
}

// Analysis result for AI-generated content from transcriptions
export interface AnalysisResult {
    analysisType: string; // Changed from enum to string (references AnalysisType.name)
    analysisTypeId: string; // References AnalysisType.id for data integrity
    content: string; // The generated analysis content
    createdAt: string; // ISO timestamp when analysis was generated
    status: 'pending' | 'completed' | 'failed'; // Status of the analysis
    errorMessage?: string; // Error message if status is 'failed'
    
    // Performance tracking fields
    llmResponseTimeMs?: number; // Time spent waiting for LLM response in milliseconds
    promptTokens?: number; // Number of tokens in the prompt
    responseTokens?: number; // Number of tokens in the response
}

// Audit trail entry for speaker identification actions
export interface IdentificationHistoryEntry {
    timestamp: string;          // ISO timestamp
    action: string;             // "auto_assigned", "accepted", "rejected", "dismissed", "training_approved", "training_revoked", "manual_assigned", "reidentified"
    participantId?: string;     // Who was assigned/suggested
    displayName?: string;       // Display name at time of action
    similarity?: number;        // Similarity score at time of action
    candidatesPresented?: TopCandidate[];  // Top candidates shown to user
    source?: string;            // "worker", "user_inline", "user_review_queue"
}

// Top candidate for speaker identification quick-pick UI
export interface TopCandidate {
    participantId: string;
    displayName?: string;
    similarity: number;
}

// Speaker mapping entry for a single speaker label
export interface SpeakerMappingEntry {
    participantId?: string;     // References Participant.id (primary link)
    confidence?: number;        // AI confidence in identification (0-1)
    manuallyVerified?: boolean; // User confirmed this mapping
    displayName?: string;       // Enriched from Participant at query time (not stored)
    // Speaker identification fields
    identificationStatus?: 'auto' | 'suggest' | 'unknown' | 'dismissed';  // Result of speaker ID
    similarity?: number;        // Cosine similarity score from speaker ID
    suggestedParticipantId?: string;  // Top candidate for "suggest" status
    suggestedDisplayName?: string;    // Enriched at query time
    topCandidates?: TopCandidate[];   // Top N matches for quick-pick UI
    identifiedAt?: string;      // ISO timestamp of identification
    useForTraining?: boolean;   // User explicitly approved this embedding for voice profile training
    identificationHistory?: IdentificationHistoryEntry[];  // Audit trail of all actions
    // Legacy fields (read-only, not written to new data)
    name?: string;              // @deprecated - use displayName from enrichment
    reasoning?: string;         // @deprecated - AI debug artifact, no longer stored
}

// Speaker mapping: links speaker labels to participants
// Storage: only participantId, confidence, manuallyVerified are stored
// API Response: displayName is enriched at query time from Participant lookup
export type SpeakerMapping = {
    [speakerLabel: string]: SpeakerMappingEntry;
};

// Represents a transcription entity
export interface Transcription {
    id: string; // Unique identifier for the transcription
    type?: string; // Document type discriminator (always "transcription")
    user_id: string; // References the user who owns the transcription
    recording_id: string; // References the recording this transcription is associated with
    diarized_transcript?: string; // Transcript text with speaker separation if diarized
    text?: string; // Non-diarized transcript text (if available)
    transcript_json?: string; // Raw JSON transcription data
    az_raw_transcription?: string; // Raw Azure transcription result as a JSON string
    az_transcription_id?: string; // Azure transcription id
    token_count?: number; // Approximate token count of transcript text (chars / 4)
    partitionKey: string;
    testRunId?: string; // Test run identifier for cleanup purposes (only set during test runs)

    // Speaker mapping: links speaker labels to participants
    speaker_mapping?: SpeakerMapping;

    // AI-generated analysis results for this transcription
    analysisResults?: AnalysisResult[];
}

// =============================================================================
// API Request/Response Types
// =============================================================================

// Standard API response wrapper
export interface ApiResponse<T = any> {
    status: 'success' | 'error';
    data?: T;
    count?: number;
    message?: string;
    error?: string;
}

// Analysis Types API Messages
export interface CreateAnalysisTypeRequest {
    name: string;
    title: string;
    shortTitle: string;
    description: string;
    icon: string;
    prompt: string;
}

export interface UpdateAnalysisTypeRequest {
    title?: string;
    shortTitle?: string;
    description?: string;
    icon?: string;
    prompt?: string;
    isActive?: boolean;
}

export interface GetAnalysisTypesResponse extends ApiResponse<AnalysisType[]> {
    count: number;
}

export interface CreateAnalysisTypeResponse extends ApiResponse<AnalysisType> {}
export interface UpdateAnalysisTypeResponse extends ApiResponse<AnalysisType> {}
export interface DeleteAnalysisTypeResponse extends ApiResponse<null> {}

// Analysis Execution API Messages
export interface ExecuteAnalysisRequest {
    transcriptionId: string;
    analysisTypeId: string;
    customPrompt?: string;
}

export interface ExecuteAnalysisResponse extends ApiResponse<AnalysisResult> {}

// Participant API Messages
export interface CreateParticipantRequest {
    displayName: string;
    firstName?: string;
    lastName?: string;
    email?: string;
    role?: string;
    organization?: string;
    relationshipToUser?: string;
    notes?: string;
    aliases?: string[];
}

export interface UpdateParticipantRequest {
    displayName?: string;
    firstName?: string;
    lastName?: string;
    email?: string;
    role?: string;
    organization?: string;
    relationshipToUser?: string;
    notes?: string;
    aliases?: string[];
    isUser?: boolean;
}

export interface MergeParticipantsRequest {
    merge_fields?: {
        displayName?: string;
        aliases?: string[];
        notes?: string;
    };
}

export interface UpdateLastSeenRequest {
    timestamp?: string; // ISO date string, defaults to now
}

export interface SearchParticipantsResponse extends ApiResponse<Participant[]> {
    search_term: string;
    fuzzy_search: boolean;
}

export interface GetParticipantsResponse extends ApiResponse<Participant[]> {
    count: number;
}

export interface CreateParticipantResponse extends ApiResponse<Participant> {}
export interface UpdateParticipantResponse extends ApiResponse<Participant> {}
export interface GetParticipantResponse extends ApiResponse<Participant> {}
export interface DeleteParticipantResponse extends ApiResponse<null> {}
export interface MergeParticipantsResponse extends ApiResponse<Participant> {}

// Participant Recordings API - response includes total for pagination
export interface GetParticipantRecordingsResponse extends ApiResponse<Recording[]> {
    total: number;
}

// Common error response for failed requests
export interface ErrorResponse {
    error: string;
    details?: string;
}
