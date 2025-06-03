// transcoder_container/schemas/container-schemas.ts
// Message and response schemas for the transcoding container

// ============================================================================
// Common Types
// ============================================================================

export interface CallbackInfo {
    url: string;        // The callback URL to send the response to
    token: string;      // UUID token for authentication
  }
  
  export interface AudioMetadata {
    duration?: number;   // Duration in seconds
    format?: string;     // Audio format (mp3, m4a, etc.)
    size_bytes?: number; // File size in bytes
    bitrate?: string;    // Bitrate (e.g., "128k")
    codec?: string;      // Audio codec (e.g., "aac", "mp3")
  }
  
  // ============================================================================
  // Input Message Schemas
  // ============================================================================
  
  // Base message interface - all messages must have action and callbacks
  export interface BaseMessage {
    action: string;
    callbacks: CallbackInfo[];
  }
  
  // Test action message
  export interface TestMessage extends BaseMessage {
    action: "test";
    content: string;     // Content to echo back in the response
  }
  
  // Transcode action message  
  export interface TranscodeMessage extends BaseMessage {
    action: "transcode";
    recording_id: string;        // ID of the recording being transcoded
    original_filename: string;   // Original filename for reference
    source_sas_url: string;      // SAS URL to download the source file
    target_sas_url: string;      // SAS URL to upload the transcoded file
    user_id: string;             // ID of the user who owns the recording
    dry_run?: boolean;           // Optional flag to indicate if this is a dry run
  }

  export interface PlaudSyncMessage extends BaseMessage {
    action: "plaud_sync";
    user_id: string;
    bearerToken: string;
    lastSyncTimestamp?: string;
    processedPlaudIds?: string[];
    dry_run?: boolean;
  }
  
  // Union type for all possible messages
  export type ContainerMessage = TestMessage | TranscodeMessage | PlaudSyncMessage;
  
  // ============================================================================
  // Output Response Schemas
  // ============================================================================
  
  // Base response interface - all responses have these fields
  export interface BaseResponse {
    action: string;
    status: "in_progress" | "completed" | "failed" | "recording_processed";
    callback_token: string;      // Token from the callback info
    container_version: string;   // Version of the container that processed the message
    timestamp?: string;          // ISO timestamp of when response was generated
    dry_run?: boolean;           // Optional flag to indicate if this was a dry run
  }
  
  // Test action response
  export interface TestResponse extends BaseResponse {
    action: "test";
    content: string;             // Original content from the message
    message: string;             // Status message from the container
  }
  
  // Transcode action response - in progress
  export interface TranscodeInProgressResponse extends BaseResponse {
    action: "transcode";
    recording_id: string;
    status: "in_progress";
  }
  
  // Transcode action response - completed
  export interface TranscodeCompletedResponse extends BaseResponse {
    action: "transcode";
    recording_id: string;
    status: "completed";
    processing_time: number;     // Time taken to process in seconds
    input_metadata: AudioMetadata;
    output_metadata: AudioMetadata;
  }
  
  // Transcode action response - failed
  export interface TranscodeFailedResponse extends BaseResponse {
    action: "transcode";
    recording_id: string;
    status: "failed";
    error_message: string;       // Description of what went wrong
    processing_time?: number;    // Time spent before failure (optional)
    input_metadata?: AudioMetadata;  // May be available even if transcoding failed
  }
  
  // Union type for all transcode responses
  export type TranscodeResponse = 
    | TranscodeInProgressResponse 
    | TranscodeCompletedResponse 
    | TranscodeFailedResponse;

    export interface PlaudSyncInProgressResponse extends BaseResponse {
      action: "plaud_sync";
      status: "in_progress";
      user_id: string;
      message: string;
    }
    
    export interface PlaudSyncRecordingProcessedResponse extends BaseResponse {
      action: "plaud_sync";
      status: "recording_processed";
      user_id: string;
      plaud_id: string;
      recording_id: string;
      original_filename: string;
      duration: number;
      original_timestamp: string;
      processing_time: number;
    }
    
    export interface PlaudSyncCompletedResponse extends BaseResponse {
      action: "plaud_sync";
      status: "completed";
      user_id: string;
      total_recordings_found: number;
      new_recordings_processed: number;
      skipped_recordings: number;
      error_count: number;
      errors: string[];
      processing_time: number;
      processed_recordings: Array<{
        recording_id: string;
        plaud_id: string;
        original_filename: string;
        duration: number;
        original_timestamp: string;
      }>;
    }

  export type PlaudSyncResponse = PlaudSyncInProgressResponse | PlaudSyncRecordingProcessedResponse | PlaudSyncCompletedResponse;
  
  // Union type for all possible responses
  export type ContainerResponse = TestResponse | TranscodeResponse | PlaudSyncResponse;
  
  // ============================================================================
  // Type Guards (useful for TypeScript consumers)
  // ============================================================================
  
  export function isTestMessage(message: ContainerMessage): message is TestMessage {
    return message.action === "test";
  }
  
  export function isTranscodeMessage(message: ContainerMessage): message is TranscodeMessage {
    return message.action === "transcode";
  }
  
  export function isTestResponse(response: ContainerResponse): response is TestResponse {
    return response.action === "test";
  }
  
  export function isTranscodeResponse(response: ContainerResponse): response is TranscodeResponse {
    return response.action === "transcode";
  }
  
  // ============================================================================
  // Example Messages and Responses
  // ============================================================================
  
  // Example test message
  export const exampleTestMessage: TestMessage = {
    action: "test",
    content: "health check from api server",
    callbacks: [
      {
        url: "https://app.com/api/test_callback",
        token: "test-token-uuid-123"
      }
    ]
  };
  
  // Example transcode message
  export const exampleTranscodeMessage: TranscodeMessage = {
    action: "transcode", 
    recording_id: "recording-123",
    original_filename: "audio.m4a",
    source_sas_url: "https://storage.blob.core.windows.net/recordings/source.m4a?sas=...",
    target_sas_url: "https://storage.blob.core.windows.net/recordings/target.mp3?sas=...",
    user_id: "user-456",
    callbacks: [
      {
        url: "https://app.com/api/transcoding_callback",
        token: "callback-token-uuid-789"
      },
      {
        url: "https://monitoring.com/events",
        token: "monitoring-token-abc"
      }
    ]
  };
  
  // Example test response
  export const exampleTestResponse: TestResponse = {
    action: "test",
    status: "completed",
    callback_token: "test-token-uuid-123",
    container_version: "1.0.0",
    content: "health check from api server", 
    message: "Container is healthy and operational",
    timestamp: "2024-01-01T12:00:00.000Z"
  };
  
  // Example transcode completed response
  export const exampleTranscodeCompletedResponse: TranscodeCompletedResponse = {
    action: "transcode",
    recording_id: "recording-123",
    status: "completed",
    callback_token: "callback-token-uuid-789",
    container_version: "1.0.0",
    processing_time: 45.2,
    input_metadata: {
      duration: 180.5,
      format: "m4a",
      size_bytes: 13107200,
      codec: "aac"
    },
    output_metadata: {
      duration: 180.5,
      format: "mp3", 
      size_bytes: 8388608,
      bitrate: "128k",
      codec: "mp3"
    }
  };