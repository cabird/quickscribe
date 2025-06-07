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

// Represents a user in the system
export interface User {
    id: string; // Unique identifier for the user
    name?: string; // Assumption: Not explicitly mentioned, possibly available from user handling methods
    email?: string; // Assumption: May be included depending on authentication setup
    role?: string; // Admin or user
    created_at?: string; // DateTime of when the user was created
    last_login?: string; // DateTime of when the user last logged in
    plaudSettings?: PlaudSettings; // Plaud integration settings
    partitionKey: string;
    is_test_user?: boolean; // Indicates if this is a test user for local development
    tags?: Tag[]; // User's custom tags
}

// Represents a recording entity
export interface Recording {
    id: string; // Unique identifier for the recording
    user_id: string; // References the user who uploaded the recording
    original_filename: string; // Original filename of the uploaded file
    unique_filename: string; // Unique filename assigned to the uploaded file
    title?: string; // User-editable title for the recording (defaults to original_filename)
    recorded_timestamp?: string; // ISO timestamp when the recording was actually made
    duration?: number; // Duration of the recording in seconds (may be unknown)
    
    // Transcription related fields
    transcription_status?: "not_started" | "in_progress" | "completed" | "failed"; // Transcription status with specific values
    transcription_status_updated_at?: string; // ISO timestamp for when transcription status last updated
    transcription_id?: string; // References the transcription id for this recording if one exists
    az_transcription_id?: string; // Azure transcription ID if in progress or completed
    transcription_error_message?: string; // Error message if transcription fails
    
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
    partitionKey: string;
    tagIds?: string[]; // Array of tag IDs assigned to this recording
    is_dummy_recording?: boolean; // Indicates if this is a dummy recording for testing
}

// Progress tracking for Plaud sync operations
export interface SyncProgress {
    id: string; // Unique identifier (same as syncToken)
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

// Represents a transcription entity
export interface Transcription {
    id: string; // Unique identifier for the transcription
    user_id: string; // References the user who owns the transcription
    recording_id: string; // References the recording this transcription is associated with
    diarized_transcript?: string; // Transcript text with speaker separation if diarized
    text?: string; // Non-diarized transcript text (if available)
    transcript_json?: string; // Raw JSON transcription data
    az_raw_transcription?: string; // Raw Azure transcription result as a JSON string
    az_transcription_id?: string; // Azure transcription id
    partitionKey: string;

     // Detailed speaker mapping with inferred name and reasoning for each speaker
     speaker_mapping?: {
        [speakerLabel: string]: {
            name: string; // Inferred name or label for the speaker
            reasoning: string; // Concise reasoning for the inferred label
        };
    };
}
