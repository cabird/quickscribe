// shared/types.ts

// Represents a user in the system
export interface User {
    id: string; // Unique identifier for the user
    name?: string; // Assumption: Not explicitly mentioned, possibly available from user handling methods
    email?: string; // Assumption: May be included depending on authentication setup
    role?: string; // Admin or user
    created_at?: string; // DateTime of when the user was created
    last_login?: string; // DateTime of when the user last logged in
    partitionKey: string;
}

// Represents a recording entity
export interface Recording {
    id: string; // Unique identifier for the recording
    user_id: string; // References the user who uploaded the recording
    transcription_id: string; // References the transcription id for this recording if one exists
    original_filename: string; // Original filename of the uploaded file
    unique_filename: string; // Unique filename assigned to the uploaded file
    duration?: number; // Duration of the recording in seconds (may be unknown)
    transcription_status: "not_started" | "in_progress" | "completed" | "failed"; // Transcription status with specific values
    transcription_status_updated_at?: string; // ISO timestamp for when transcription status last updated
    az_transcription_id?: string; // Azure transcription ID if in progress or completed
    upload_timestamp?: string; // DateTime of when the recording was uploaded
    transcription_error_message?: string; // Error message if transcription fails
    partitionKey: string;
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
