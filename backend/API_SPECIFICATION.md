# QuickScribe Backend API Specification

**Version:** See `/api/get_api_version`
**Base URL:** `https://your-backend-url.com` (configured via environment)
**Last Updated:** 2025-01-14

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Common Response Patterns](#common-response-patterns)
- [API Endpoints](#api-endpoints)
  - [System](#system)
  - [User Management](#user-management)
  - [Recordings](#recordings)
  - [Transcriptions](#transcriptions)
  - [AI Analysis](#ai-analysis)
  - [Participants](#participants)
  - [Tags](#tags)
  - [Plaud Integration](#plaud-integration)
  - [Azure Transcription](#azure-transcription)
  - [Admin](#admin)
  - [Job Executions](#job-executions)
  - [Local Development](#local-development)

---

## Overview

The QuickScribe backend is a Flask-based REST API that handles audio transcription processing, user management, and Azure services integration. It follows microservices principles with clean separation of concerns and scalable cloud-native design.

### Technology Stack

- **Flask** with Blueprint routing
- **Azure Cosmos DB** for data storage
- **Azure Blob Storage** for audio files
- **Azure Speech Services** for transcription
- **Azure OpenAI** for AI analysis
- **Pydantic** for data validation

---

## Authentication

### Authentication Methods

**Production (Azure):**
- Azure AD authentication via MSAL
- Bearer token required in `Authorization` header
- Token format: `Bearer <azure_ad_token>`

**Local Development:**
- Local session-based authentication
- Must set `LOCAL_AUTH_ENABLED=true` in environment
- Use `/api/local/login` endpoint to set user session

### Authenticated Requests

Most endpoints require authentication. Include the token in the request header:

```http
Authorization: Bearer <your_token_here>
```

Endpoints marked with `🔒` require authentication.

---

## Common Response Patterns

### Success Response

```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### Error Response

```json
{
  "status": "error",
  "error": "Error message describing what went wrong"
}
```

### HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource already exists or conflict
- `500 Internal Server Error` - Server error

---

## API Endpoints

## System

### Get API Version

**Endpoint:** `GET /api/get_api_version`
**Authentication:** None required

Returns the current API version.

**Response:**
```json
{
  "version": "1.0.0"
}
```

---

## User Management

### Get User by ID

**Endpoint:** `GET /api/user/<user_id>`
**Authentication:** 🔒 Required

Retrieves a user's profile information by their unique ID.

**URL Parameters:**
- `user_id` (string) - Unique user identifier

**Response:**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "user",
  "created_at": "2025-01-01T00:00:00Z",
  "last_login": "2025-01-14T10:00:00Z",
  "plaudSettings": {
    "bearerToken": "token",
    "lastSyncTimestamp": "2025-01-14T09:00:00Z",
    "enableSync": true
  },
  "tags": [
    {"id": "meeting", "name": "Meeting", "color": "#4444FF"}
  ],
  "partitionKey": "user",
  "is_test_user": false
}
```

### List All Users

**Endpoint:** `GET /api/users`
**Authentication:** 🔒 Required

Returns a list of all users in the system.

**Response:**
```json
[
  {
    "id": "user-uuid-1",
    "email": "user1@example.com",
    "name": "John Doe",
    ...
  },
  {
    "id": "user-uuid-2",
    "email": "user2@example.com",
    "name": "Jane Smith",
    ...
  }
]
```

### Get Users by IDs

**Endpoint:** `POST /api/users`
**Authentication:** 🔒 Required

Retrieves multiple users by their IDs.

**Request Body:**
```json
{
  "ids": ["user-uuid-1", "user-uuid-2"]
}
```

**Response:**
```json
[
  {
    "id": "user-uuid-1",
    "email": "user1@example.com",
    "name": "John Doe",
    ...
  }
]
```

### Update User

**Endpoint:** `PUT /api/user/<user_id>`
**Authentication:** 🔒 Required

Updates user profile information.

**URL Parameters:**
- `user_id` (string) - User ID to update

**Request Body:**
```json
{
  "name": "Updated Name",
  "email": "newemail@example.com",
  "plaudSettings": {
    "bearerToken": "new-token",
    "enableSync": true
  }
}
```

**Response:**
```json
{
  "id": "user-uuid",
  "name": "Updated Name",
  "email": "newemail@example.com",
  ...
}
```

### Delete User

**Endpoint:** `GET /api/delete_user/<user_id>`
**Authentication:** 🔒 Required

Deletes a user from the system.

**URL Parameters:**
- `user_id` (string) - User ID to delete

**Response:**
```json
{
  "message": "User deleted successfully"
}
```

---

## Recordings

### List User Recordings

**Endpoint:** `GET /api/recordings`
**Authentication:** 🔒 Required

Returns all recordings for the authenticated user.

**Response:**
```json
[
  {
    "id": "recording-uuid",
    "user_id": "user-uuid",
    "title": "Team Meeting Q1 Planning",
    "description": "Discussion about Q1 goals and objectives",
    "original_filename": "meeting_20250101.mp3",
    "unique_filename": "abc123.mp3",
    "blob_name": "recordings/user-uuid/recording-uuid.mp3",
    "duration": 3600,
    "recorded_timestamp": "2025-01-01T09:00:00Z",
    "upload_timestamp": "2025-01-01T09:05:00Z",
    "source": "upload",
    "transcoding_status": "completed",
    "transcription_status": "completed",
    "transcription_id": "transcript-uuid",
    "participants": ["John Doe", "Jane Smith"],
    "tagIds": ["meeting"],
    "partitionKey": "recording"
  }
]
```

### Get Recording by ID

**Endpoint:** `GET /api/recording/<recording_id>`
**Authentication:** 🔒 Required

Retrieves details for a specific recording.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Response:**
```json
{
  "id": "recording-uuid",
  "user_id": "user-uuid",
  "title": "Team Meeting",
  "original_filename": "meeting.mp3",
  ...
}
```

### Get Recording Audio URL

**Endpoint:** `GET /api/recording/<recording_id>/audio-url`
**Authentication:** 🔒 Required

Generates a time-limited SAS URL for streaming the recording's audio file.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Response:**
```json
{
  "audio_url": "https://storage.blob.core.windows.net/recordings/...",
  "expires_in": 86400,
  "content_type": "audio/mpeg"
}
```

**Errors:**
- `401` - User not authenticated
- `403` - Recording does not belong to current user
- `400` - Recording audio is not ready yet
- `404` - Recording not found

### Get Recordings by IDs

**Endpoint:** `POST /api/recordings`
**Authentication:** 🔒 Required

Retrieves multiple recordings by their IDs.

**Request Body:**
```json
{
  "ids": ["recording-uuid-1", "recording-uuid-2"]
}
```

**Response:**
```json
[
  {
    "id": "recording-uuid-1",
    "title": "Meeting 1",
    ...
  },
  {
    "id": "recording-uuid-2",
    "title": "Meeting 2",
    ...
  }
]
```

### Upload Audio File

**Endpoint:** `POST /api/upload`
**Authentication:** 🔒 Required

Uploads an audio file for transcription processing.

**Request:** Multipart form data
- `file` (file) - Audio file to upload

**Response:**
```json
{
  "message": "File uploaded successfully and queued for transcoding!",
  "filename": "meeting.mp3",
  "recording_id": "recording-uuid",
  "transcoding_status": "queued",
  "token": "callback-token-uuid"
}
```

**Process Flow:**
1. File uploaded to Azure Blob Storage
2. Recording created in database with status `queued`
3. Message sent to transcoding queue
4. Transcoder processes file asynchronously
5. Callback updates recording status
6. AI post-processing triggered on completion

### Upload from iOS Share

**Endpoint:** `POST /api/upload_from_ios_share`
**Authentication:** 🔒 Required

Handles audio uploads from iOS share context menu.

**Request:** Multipart form data
- `audio_file` (file) - Audio file from iOS

**Response:**
```json
{
  "success": "File uploaded successfully!",
  "filename": "recording.m4a",
  "recording_id": "recording-uuid",
  "transcoding_status": "queued"
}
```

### Get Transcoding Status

**Endpoint:** `GET /api/transcoding_status/<recording_id>`
**Authentication:** 🔒 Required

Checks the transcoding status for a recording.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Response:**
```json
{
  "recording_id": "recording-uuid",
  "transcoding_status": "completed",
  "transcoding_started_at": "2025-01-14T10:00:00Z",
  "transcoding_completed_at": "2025-01-14T10:02:30Z",
  "transcoding_error_message": null,
  "transcoding_retry_count": 0
}
```

**Transcoding Status Values:**
- `not_started` - Not yet queued
- `queued` - Waiting for processing
- `in_progress` - Currently transcoding
- `completed` - Successfully transcoded
- `failed` - Transcoding failed

### Transcoding Callback

**Endpoint:** `POST /api/transcoding_callback`
**Authentication:** None (uses callback token)

Receives callbacks from the transcoding container. **Internal use only.**

**Request Body:**
```json
{
  "action": "transcode",
  "recording_id": "recording-uuid",
  "status": "completed",
  "callback_token": "token-uuid",
  "output_metadata": {
    "duration": 3600
  },
  "processing_time": 45.2
}
```

**Status Values:**
- `in_progress` - Transcoding started
- `completed` - Transcoding successful (triggers AI post-processing)
- `failed` - Transcoding failed

### Update Recording

**Endpoint:** `PUT /api/recording/<recording_id>`
**Authentication:** 🔒 Required

Updates recording metadata.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Request Body:**
```json
{
  "title": "Updated Title",
  "description": "Updated description",
  "participants": ["Alice", "Bob"]
}
```

**Response:**
```json
{
  "id": "recording-uuid",
  "title": "Updated Title",
  "description": "Updated description",
  ...
}
```

### Delete Recording

**Endpoint:** `GET /api/delete_recording/<recording_id>`
**Authentication:** 🔒 Required

Deletes a recording and its associated data.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Response:**
```json
{
  "message": "Recording deleted successfully"
}
```

### Manual Post-Processing

**Endpoint:** `POST /api/recording/<recording_id>/postprocess`
**Authentication:** 🔒 Required

Manually triggers AI post-processing for a completed recording.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Process:**
1. Generates title from transcript content
2. Creates description (1-2 sentences)
3. Infers speaker names and updates mapping

**Response:**
```json
{
  "recording_id": "recording-uuid",
  "status": "completed",
  "results": {
    "title_generated": true,
    "description_generated": true,
    "speakers_updated": true
  },
  "updated_recording": { ... },
  "updated_transcription": { ... },
  "errors": []
}
```

**Errors:**
- `401` - User not authenticated
- `403` - Recording does not belong to user
- `400` - Recording must be transcribed first
- `404` - Recording not found

### Update Speakers

**Endpoint:** `POST /api/recording/<recording_id>/update_speakers`
**Authentication:** 🔒 Required

Updates speaker names for a recording. Supports both legacy string format and new participant format.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Request Body (Legacy Format):**
```json
{
  "Speaker 1": "Alice Johnson",
  "Speaker 2": "Bob Smith"
}
```

**Request Body (Participant Format):**
```json
{
  "Speaker 1": {
    "participantId": "participant-uuid-1",
    "displayName": "Alice Johnson"
  },
  "Speaker 2": {
    "participantId": "participant-uuid-2",
    "displayName": "Bob Smith"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Speaker mapping updated successfully",
  "updated_recording": { ... },
  "updated_transcription": { ... },
  "speaker_results": {
    "speakers_updated": 2,
    "mapping": { ... }
  }
}
```

**Validation:**
- Speaker names max 50 characters
- Participant ID required for new format
- Display name required and non-empty

---

## Transcriptions

### Get Transcription by ID

**Endpoint:** `GET /api/transcription/<transcription_id>`
**Authentication:** 🔒 Required

Retrieves a specific transcription.

**URL Parameters:**
- `transcription_id` (string) - Transcription UUID

**Response:**
```json
{
  "id": "transcription-uuid",
  "user_id": "user-uuid",
  "recording_id": "recording-uuid",
  "text": "Full transcript text...",
  "diarized_transcript": "Speaker 1: Hello...\nSpeaker 2: Hi...",
  "speaker_mapping": {
    "Speaker 1": {
      "name": "John Doe",
      "displayName": "John Doe",
      "participantId": "participant-uuid",
      "reasoning": "Mentioned by name at 2:15",
      "confidence": 0.95,
      "manuallyVerified": false
    }
  },
  "analysisResults": [
    {
      "analysisType": "summary",
      "analysisTypeId": "analysis-type-uuid",
      "content": "Meeting summary...",
      "createdAt": "2025-01-14T10:30:00Z",
      "status": "completed",
      "llmResponseTimeMs": 1250,
      "promptTokens": 2500,
      "responseTokens": 300
    }
  ],
  "created_at": "2025-01-14T10:00:00Z",
  "partitionKey": "transcription"
}
```

### Get Transcriptions by IDs

**Endpoint:** `POST /api/transcriptions`
**Authentication:** 🔒 Required

Retrieves multiple transcriptions by their IDs.

**Request Body:**
```json
{
  "ids": ["transcription-uuid-1", "transcription-uuid-2"]
}
```

**Response:**
```json
[
  {
    "id": "transcription-uuid-1",
    "text": "Transcript 1...",
    ...
  }
]
```

### Get User Transcriptions

**Endpoint:** `GET /api/user/<user_id>/transcriptions`
**Authentication:** 🔒 Required

Returns all transcriptions for a specific user.

**URL Parameters:**
- `user_id` (string) - User UUID

**Response:**
```json
[
  {
    "id": "transcription-uuid-1",
    "recording_id": "recording-uuid-1",
    ...
  }
]
```

### Update Transcription

**Endpoint:** `PUT /api/transcription/<transcription_id>`
**Authentication:** 🔒 Required

Updates transcription data.

**URL Parameters:**
- `transcription_id` (string) - Transcription UUID

**Request Body:**
```json
{
  "text": "Updated transcript text",
  "speaker_mapping": { ... }
}
```

**Response:**
```json
{
  "id": "transcription-uuid",
  "text": "Updated transcript text",
  ...
}
```

### Delete Transcription

**Endpoint:** `GET /api/delete_transcription/<transcription_id>`
**Authentication:** 🔒 Required

Deletes a transcription.

**URL Parameters:**
- `transcription_id` (string) - Transcription UUID

**Response:**
```json
{
  "message": "Transcription deleted successfully"
}
```

### Update Single Speaker

**Endpoint:** `POST /api/transcription/<transcription_id>/speaker`
**Authentication:** 🔒 Required

Updates a single speaker assignment in a transcription.

**URL Parameters:**
- `transcription_id` (string) - Transcription UUID

**Request Body:**
```json
{
  "speaker_label": "Speaker 1",
  "participant_id": "participant-uuid",
  "manually_verified": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Speaker 1 assigned to John Doe",
  "speaker_data": {
    "participantId": "participant-uuid",
    "displayName": "John Doe",
    "name": "John Doe",
    "reasoning": "Manual assignment by user",
    "confidence": 1.0,
    "manuallyVerified": true
  }
}
```

---

## AI Analysis

### Test AI Route

**Endpoint:** `GET /api/ai/test`
**Authentication:** None required

Health check for AI routes.

**Response:**
```json
{
  "status": "up"
}
```

### Get Speaker Summaries

**Endpoint:** `GET /api/ai/get_speaker_summaries/<transcription_id>`
**Authentication:** 🔒 Required

Generates AI summaries for each speaker in a diarized transcript.

**URL Parameters:**
- `transcription_id` (string) - Transcription UUID

**Response:**
```json
{
  "Speaker 1": "Project manager who discussed Q1 goals and timeline concerns.",
  "Speaker 2": "Lead developer who presented technical architecture and raised security questions.",
  "Speaker 3": "Product owner who clarified feature priorities and user feedback."
}
```

**Process:**
- Normalizes speaker labels to "Speaker 1", "Speaker 2", etc.
- Sends normalized transcript to LLM for analysis
- Returns personality/role summaries for each speaker

### Infer Speaker Names

**Endpoint:** `GET /api/ai/infer_speaker_names/<transcription_id>`
**Authentication:** 🔒 Required

Uses AI to infer speaker names from conversation context.

**URL Parameters:**
- `transcription_id` (string) - Transcription UUID

**Response:**
```json
{
  "message": "Speaker names successfully inferred"
}
```

**Side Effects:**
- Updates transcription's `speaker_mapping` with inferred names
- Updates transcription's `diarized_transcript` with name replacements

### Get Analysis Types

**Endpoint:** `GET /api/ai/analysis-types`
**Authentication:** 🔒 Required

Returns all available analysis types (built-in + custom for the user).

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "summary-uuid",
      "name": "summary",
      "title": "Generate Summary",
      "shortTitle": "Summary",
      "description": "Create a concise summary of the conversation",
      "icon": "document-text",
      "prompt": "Summarize the following transcript: {transcript}",
      "userId": null,
      "isActive": true,
      "isBuiltIn": true,
      "createdAt": "2025-01-01T00:00:00Z",
      "updatedAt": "2025-01-01T00:00:00Z",
      "partitionKey": "global"
    }
  ],
  "count": 5
}
```

### Create Analysis Type

**Endpoint:** `POST /api/ai/analysis-types`
**Authentication:** 🔒 Required

Creates a custom analysis type for the user.

**Request Body:**
```json
{
  "name": "meeting-notes",
  "title": "Generate Meeting Notes",
  "shortTitle": "Notes",
  "description": "Extract key points and action items",
  "icon": "clipboard-list",
  "prompt": "Extract meeting notes from: {transcript}"
}
```

**Validation:**
- `shortTitle` max 12 characters
- `prompt` must include `{transcript}` placeholder

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "analysis-type-uuid",
    "name": "meeting-notes",
    "userId": "user-uuid",
    "isBuiltIn": false,
    ...
  },
  "message": "Analysis type created successfully"
}
```

### Update Analysis Type

**Endpoint:** `PUT /api/ai/analysis-types/<type_id>`
**Authentication:** 🔒 Required

Updates a custom analysis type. Users can only update their own types.

**URL Parameters:**
- `type_id` (string) - Analysis type UUID

**Request Body:**
```json
{
  "title": "Updated Title",
  "shortTitle": "Updated",
  "prompt": "New prompt with {transcript}"
}
```

**Response:**
```json
{
  "status": "success",
  "data": { ... },
  "message": "Analysis type updated successfully"
}
```

### Delete Analysis Type

**Endpoint:** `DELETE /api/ai/analysis-types/<type_id>`
**Authentication:** 🔒 Required

Deletes a custom analysis type. Users can only delete their own types.

**URL Parameters:**
- `type_id` (string) - Analysis type UUID

**Response:**
```json
{
  "status": "success",
  "message": "Analysis type deleted successfully"
}
```

### Execute Analysis

**Endpoint:** `POST /api/ai/execute-analysis`
**Authentication:** 🔒 Required

Executes AI analysis on a transcription using a specified analysis type.

**Request Body:**
```json
{
  "transcriptionId": "transcription-uuid",
  "analysisTypeId": "analysis-type-uuid",
  "customPrompt": "Optional custom prompt override with {transcript}"
}
```

**Process:**
1. Retrieves transcription and verifies ownership
2. Gets analysis type (checks user custom types, then global types)
3. Uses custom prompt if provided, otherwise uses analysis type's prompt
4. Replaces `{transcript}` with actual transcript text
5. Sends to LLM with timing tracking
6. Stores result in transcription's `analysisResults` array

**Response (Success):**
```json
{
  "status": "success",
  "message": "Analysis completed successfully",
  "data": {
    "analysisType": "summary",
    "analysisTypeId": "analysis-type-uuid",
    "content": "This meeting covered Q1 planning and resource allocation...",
    "createdAt": "2025-01-14T11:00:00Z",
    "status": "completed",
    "llmResponseTimeMs": 1450,
    "promptTokens": 3200,
    "responseTokens": 450
  }
}
```

**Response (Failure):**
```json
{
  "status": "error",
  "message": "Analysis failed",
  "data": {
    "analysisType": "summary",
    "analysisTypeId": "analysis-type-uuid",
    "content": "",
    "createdAt": "2025-01-14T11:00:00Z",
    "status": "failed",
    "errorMessage": "LLM timeout after 30 seconds"
  }
}
```

---

## Participants

### Get All Participants

**Endpoint:** `GET /api/participants`
**Authentication:** 🔒 Required

Returns all participant profiles for the authenticated user.

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "participant-uuid",
      "userId": "user-uuid",
      "firstName": "John",
      "lastName": "Smith",
      "displayName": "John Smith",
      "aliases": ["Johnny", "J. Smith"],
      "email": "john@example.com",
      "role": "Project Manager",
      "organization": "Acme Corp",
      "relationshipToUser": "Colleague",
      "notes": "Lead on the Phoenix project",
      "isUser": false,
      "firstSeen": "2025-01-01T10:00:00Z",
      "lastSeen": "2025-01-14T15:30:00Z",
      "createdAt": "2025-01-01T10:00:00Z",
      "updatedAt": "2025-01-14T15:30:00Z",
      "partitionKey": "user-uuid"
    }
  ],
  "count": 15
}
```

### Get Participant by ID

**Endpoint:** `GET /api/participants/<participant_id>`
**Authentication:** 🔒 Required

Retrieves a specific participant profile.

**URL Parameters:**
- `participant_id` (string) - Participant UUID

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "participant-uuid",
    "displayName": "John Smith",
    ...
  }
}
```

### Create Participant

**Endpoint:** `POST /api/participants`
**Authentication:** 🔒 Required

Creates a new participant profile.

**Request Body:**
```json
{
  "displayName": "John Smith",
  "firstName": "John",
  "lastName": "Smith",
  "email": "john@example.com",
  "role": "Project Manager",
  "organization": "Acme Corp",
  "relationshipToUser": "Colleague",
  "notes": "Lead on Phoenix project",
  "aliases": ["Johnny", "J. Smith"]
}
```

**Required Fields:**
- `displayName` (string) - How the participant should be displayed

**Optional Fields:**
- `firstName`, `lastName`, `email`, `role`, `organization`, `relationshipToUser`, `notes`
- `aliases` (array of strings)

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "participant-uuid",
    "displayName": "John Smith",
    "firstSeen": "2025-01-14T16:00:00Z",
    "lastSeen": "2025-01-14T16:00:00Z",
    ...
  }
}
```

### Update Participant

**Endpoint:** `PUT /api/participants/<participant_id>`
**Authentication:** 🔒 Required

Updates an existing participant profile.

**URL Parameters:**
- `participant_id` (string) - Participant UUID

**Request Body:**
```json
{
  "displayName": "John A. Smith",
  "role": "Senior Project Manager",
  "notes": "Promoted to senior role"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "participant-uuid",
    "displayName": "John A. Smith",
    "updatedAt": "2025-01-14T16:30:00Z",
    ...
  }
}
```

### Delete Participant

**Endpoint:** `DELETE /api/participants/<participant_id>`
**Authentication:** 🔒 Required

Deletes a participant profile.

**URL Parameters:**
- `participant_id` (string) - Participant UUID

**Response:**
```json
{
  "status": "success",
  "message": "Participant deleted successfully"
}
```

---

## Tags

### Get User Tags

**Endpoint:** `GET /api/tags/get`
**Authentication:** 🔒 Required

Returns all tags for the authenticated user.

**Response:**
```json
[
  {
    "id": "meeting",
    "name": "Meeting",
    "color": "#4444FF"
  },
  {
    "id": "personal",
    "name": "Personal",
    "color": "#BB44BB"
  }
]
```

### Create Tag

**Endpoint:** `POST /api/tags/create`
**Authentication:** 🔒 Required

Creates a new tag for the user.

**Request Body:**
```json
{
  "name": "Project Alpha",
  "color": "#FF5733"
}
```

**Validation:**
- Name max 32 characters
- Color must be valid hex code (e.g., `#FF5733`)

**Response:**
```json
{
  "id": "project-alpha",
  "name": "Project Alpha",
  "color": "#FF5733"
}
```

**Status Codes:**
- `201 Created` - Tag created successfully
- `409 Conflict` - Tag with this name already exists

### Update Tag

**Endpoint:** `POST /api/tags/update`
**Authentication:** 🔒 Required

Updates an existing tag.

**Request Body:**
```json
{
  "tagId": "project-alpha",
  "name": "Project Alpha v2",
  "color": "#00FF00"
}
```

**Response:**
```json
{
  "id": "project-alpha",
  "name": "Project Alpha v2",
  "color": "#00FF00"
}
```

### Delete Tag

**Endpoint:** `GET /api/tags/delete/<tag_id>`
**Authentication:** 🔒 Required

Deletes a tag and removes it from all recordings.

**URL Parameters:**
- `tag_id` (string) - Tag ID

**Response:**
```json
{
  "message": "Tag deleted successfully"
}
```

### Add Tag to Recording

**Endpoint:** `GET /api/recordings/<recording_id>/add_tag/<tag_id>`
**Authentication:** 🔒 Required

Adds a tag to a recording.

**URL Parameters:**
- `recording_id` (string) - Recording UUID
- `tag_id` (string) - Tag ID

**Response:**
```json
{
  "id": "recording-uuid",
  "tagIds": ["meeting", "project-alpha"],
  ...
}
```

### Remove Tag from Recording

**Endpoint:** `GET /api/recordings/<recording_id>/remove_tag/<tag_id>`
**Authentication:** 🔒 Required

Removes a tag from a recording.

**URL Parameters:**
- `recording_id` (string) - Recording UUID
- `tag_id` (string) - Tag ID

**Response:**
```json
{
  "id": "recording-uuid",
  "tagIds": ["meeting"],
  ...
}
```

---

## Plaud Integration

### Get Plaud Settings

**Endpoint:** `GET /plaud/user/plaud_settings`
**Authentication:** 🔒 Required

Returns Plaud settings for the current user (without exposing bearer token).

**Response:**
```json
{
  "hasToken": true,
  "lastSyncTimestamp": "2025-01-14T09:00:00Z",
  "enableSync": true
}
```

### Update Plaud Settings

**Endpoint:** `PUT /plaud/user/plaud_settings`
**Authentication:** 🔒 Required

Updates Plaud integration settings.

**Request Body:**
```json
{
  "bearerToken": "plaud-api-token",
  "enableSync": true,
  "lastSyncTimestamp": "2025-01-14T09:00:00Z"
}
```

**Response:**
```json
{
  "message": "Plaud settings updated successfully"
}
```

### Start Plaud Sync

**Endpoint:** `POST /plaud/sync/start`
**Authentication:** 🔒 Required

Triggers a Plaud device sync operation.

**Request Body:**
```json
{
  "dry_run": false
}
```

**Process:**
1. Validates Plaud settings and bearer token
2. Checks for active sync (returns error if already running)
3. Generates sync token
4. Queues sync job to transcoding queue
5. Creates progress tracking record
6. Updates user's `activeSyncToken` and `activeSyncStarted`

**Response:**
```json
{
  "message": "Plaud sync operation started",
  "sync_token": "sync-token-uuid",
  "dry_run": false
}
```

**Errors:**
- `400` - Plaud settings not configured or sync disabled
- `409` - Sync already in progress

### Get Sync Progress

**Endpoint:** `GET /plaud/sync/progress/<sync_token>`
**Authentication:** 🔒 Required

Retrieves detailed sync progress for a specific sync operation.

**URL Parameters:**
- `sync_token` (string) - Sync token from start sync response

**Response:**
```json
{
  "id": "sync-token-uuid",
  "syncToken": "sync-token-uuid",
  "userId": "user-uuid",
  "status": "processing",
  "totalRecordings": 15,
  "processedRecordings": 8,
  "failedRecordings": 1,
  "currentStep": "Processing recordings (8/15)",
  "errors": [
    "recording1.mp3: Download failed - network timeout"
  ],
  "startTime": "2025-01-14T10:00:00Z",
  "lastUpdate": "2025-01-14T10:05:30Z",
  "progressPercentage": 60.0,
  "partitionKey": "user-uuid"
}
```

**Status Values:**
- `queued` - Sync request queued, waiting for processing
- `processing` - Actively syncing recordings
- `completed` - Sync finished successfully
- `failed` - Sync failed with errors

### Check Active Sync

**Endpoint:** `GET /plaud/sync/check_active`
**Authentication:** 🔒 Required

Checks if current user has an active sync and returns its status. Used on app load for multi-device recovery.

**Response (Active Sync):**
```json
{
  "has_active_sync": true,
  "sync_token": "sync-token-uuid",
  "progress": {
    "status": "processing",
    "processedRecordings": 5,
    "totalRecordings": 10,
    ...
  }
}
```

**Response (No Active Sync):**
```json
{
  "has_active_sync": false
}
```

**Side Effects:**
- Clears completed/failed sync tokens automatically
- Clears orphaned sync tokens (no progress record)

### Get Plaud Sync Status

**Endpoint:** `GET /plaud/plaud_sync/status/<user_id>`
**Authentication:** 🔒 Required

Returns Plaud sync status for a user.

**URL Parameters:**
- `user_id` (string) - User UUID (must match authenticated user)

**Response:**
```json
{
  "hasSettings": true,
  "syncEnabled": true,
  "lastSyncTimestamp": "2025-01-14T09:00:00Z",
  "currentSyncActive": true,
  "activeSyncToken": "sync-token-uuid"
}
```

### Plaud Callback

**Endpoint:** `POST /plaud/plaud_callback`
**Authentication:** None (uses callback token)

Receives callbacks from the transcoding container for Plaud operations. **Internal use only.**

**Callback Actions:**

#### Register Plaud Recording
```json
{
  "action": "register_plaud_recording",
  "callback_token": "sync-token-uuid",
  "user_id": "user-uuid",
  "plaud_id": "plaud-recording-id",
  "original_filename": "recording.opus",
  "original_timestamp": "2025-01-14T08:00:00Z",
  "duration": 1800,
  "filesize": 5242880,
  "filetype": "opus",
  "dry_run": false
}
```

**Response:**
```json
{
  "success": true,
  "recording_id": "recording-uuid",
  "sas_url": "https://storage.blob.core.windows.net/..."
}
```

#### Plaud Sync Status Update
```json
{
  "action": "plaud_sync",
  "callback_token": "sync-token-uuid",
  "user_id": "user-uuid",
  "status": "in_progress|recording_processed|recording_failed|completed|failed",
  "message": "Sync in progress",
  "total_recordings_found": 15,
  "plaud_id": "recording-id",
  "recording_id": "recording-uuid",
  "error_message": "Error details"
}
```

### Cleanup Stale Syncs

**Endpoint:** `POST /plaud/admin/cleanup_stale_syncs`
**Authentication:** 🔒 Required (Admin)

Cleans up sync operations that have been queued for more than 2 hours.

**Response:**
```json
{
  "message": "Cleaned up 3 stale sync operations",
  "stale_syncs_failed": 3,
  "user_tokens_cleared": 3
}
```

---

## Azure Transcription

### Start Transcription

**Endpoint:** `POST /az_transcription/start_transcription/<recording_id>`
**Authentication:** 🔒 Required

Initiates Azure Speech Services transcription for a recording.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Process:**
1. Validates recording belongs to user
2. Checks if transcription already in progress
3. Generates SAS URL for audio blob
4. Submits to Azure Speech Services
5. Updates recording with Azure transcription ID

**Response:**
```json
{
  "message": "Transcription started"
}
```

**Errors:**
- `400` - Transcription already exists or in progress
- `404` - Recording not found or doesn't belong to user

### Check Transcription Status

**Endpoint:** `GET /az_transcription/check_transcription_status/<recording_id>`
**Authentication:** 🔒 Required

Checks the status of an Azure Speech Services transcription.

**URL Parameters:**
- `recording_id` (string) - Recording UUID

**Response:**
```json
{
  "status": "completed",
  "error": ""
}
```

**Status Values:**
- `not_started` - No transcription initiated
- `in_progress` - Transcription running
- `completed` - Transcription finished (transcript available)
- `failed` - Transcription failed

**Process (on Completion):**
1. Retrieves transcript from Azure
2. Generates diarized transcript with speaker labels
3. Updates transcription in database
4. Updates recording status to `completed`

---

## Admin

### Get Admin Overview

**Endpoint:** `GET /api/admin/overview`
**Authentication:** 🔒 Required (Admin)

Returns system-wide statistics and overview.

**Response:**
```json
{
  "status": "success",
  "data": {
    "counts": {
      "users": 150,
      "recordings": 3420,
      "transcriptions": 3200,
      "tags": 45,
      "analysisTypes": 12
    },
    "statistics": {
      "recordingsWithTranscriptions": 3200,
      "recordingsInProgress": 15,
      "recordingsFailed": 5,
      "averageRecordingsPerUser": 22.8
    },
    "recentActivity": {
      "lastRecordingDate": "2025-01-14T15:30:00Z",
      "activeUsers24h": 42
    }
  }
}
```

### Get All Users (Admin)

**Endpoint:** `GET /api/admin/users`
**Authentication:** 🔒 Required (Admin)

Returns all users with summary information including recording counts.

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "user-uuid",
      "name": "John Doe",
      "email": "john@example.com",
      "created_at": "2025-01-01T00:00:00Z",
      "recording_count": 25,
      "last_recording": "2025-01-14T10:00:00Z"
    }
  ]
}
```

---

## Job Executions

### List Job Executions

**Endpoint:** `GET /api/admin/jobs`
**Authentication:** 🔒 Required (Admin)

Returns paginated list of job executions with advanced filtering and sorting.

**Query Parameters:**
- `limit` (integer, optional) - Items per page (default: 50, max: 100)
- `offset` (integer, optional) - Items to skip for pagination (default: 0)
- `min_duration` (integer, optional) - Minimum duration in seconds
- `has_activity` (boolean, optional) - Filter for jobs with activity (recordings/transcriptions/errors > 0)
- `status` (string, optional) - Comma-separated status values (e.g., "completed,failed")
- `trigger_source` (string, optional) - Filter by trigger source ("scheduled" or "manual")
- `user_id` (string, optional) - Filter by specific user ID
- `start_date` (string, optional) - ISO timestamp - jobs started after this date
- `end_date` (string, optional) - ISO timestamp - jobs started before this date
- `sort_by` (string, optional) - Field to sort by: "startTime" (default), "endTime", "duration", "errors"
- `sort_order` (string, optional) - Sort order: "asc" or "desc" (default)

**Example Request:**
```
GET /api/admin/jobs?limit=20&offset=0&has_activity=true&min_duration=30&status=completed,failed&sort_by=startTime&sort_order=desc
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "job-uuid-1",
      "userId": "user-uuid",
      "status": "completed",
      "triggerSource": "scheduled",
      "startTime": "2025-01-14T10:00:00Z",
      "endTime": "2025-01-14T10:05:30Z",
      "duration": 330,
      "durationFormatted": "5m 30s",
      "stats": {
        "transcriptions_checked": 10,
        "transcriptions_completed": 5,
        "recordings_found": 3,
        "recordings_downloaded": 3,
        "recordings_transcoded": 3,
        "recordings_uploaded": 3,
        "recordings_skipped": 0,
        "transcriptions_submitted": 3,
        "errors": 0,
        "chunks_created": 0
      },
      "errorMessage": null,
      "usersProcessed": ["user-1", "user-2"],
      "ttl": 2592000,
      "partitionKey": "job_execution"
    }
  ],
  "pagination": {
    "total": 156,
    "count": 20,
    "limit": 20,
    "offset": 0,
    "hasMore": true,
    "nextOffset": 20
  }
}
```

**Notes:**
- Logs are **not included** in list response (metadata only)
- `duration` and `durationFormatted` are computed server-side
- Use `nextOffset` for fetching the next page
- `hasMore` indicates if more pages are available

### Get Job Execution Details

**Endpoint:** `GET /api/admin/jobs/<job_id>`
**Authentication:** 🔒 Required (Admin)

Returns complete job execution details including full logs.

**URL Parameters:**
- `job_id` (string) - Job execution UUID

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": "job-uuid",
    "userId": "user-uuid",
    "status": "completed",
    "triggerSource": "scheduled",
    "startTime": "2025-01-14T10:00:00Z",
    "endTime": "2025-01-14T10:05:30Z",
    "duration": 330,
    "durationFormatted": "5m 30s",
    "logs": [
      {
        "timestamp": "2025-01-14T10:00:01Z",
        "level": "info",
        "message": "Job execution started",
        "recordingId": null
      },
      {
        "timestamp": "2025-01-14T10:00:15Z",
        "level": "info",
        "message": "Processing recording rec-123",
        "recordingId": "rec-123"
      },
      {
        "timestamp": "2025-01-14T10:02:30Z",
        "level": "error",
        "message": "Failed to download recording rec-456: Network timeout",
        "recordingId": "rec-456"
      },
      {
        "timestamp": "2025-01-14T10:05:30Z",
        "level": "info",
        "message": "Job execution completed",
        "recordingId": null
      }
    ],
    "stats": {
      "transcriptions_checked": 10,
      "transcriptions_completed": 5,
      "recordings_found": 3,
      "recordings_downloaded": 3,
      "recordings_transcoded": 3,
      "recordings_uploaded": 3,
      "recordings_skipped": 0,
      "transcriptions_submitted": 3,
      "errors": 1,
      "chunks_created": 0
    },
    "errorMessage": null,
    "usersProcessed": ["user-1", "user-2"],
    "ttl": 2592000,
    "partitionKey": "job_execution"
  }
}
```

**Log Levels:**
- `debug` - Detailed debugging information
- `info` - General informational messages
- `warning` - Warning messages (non-critical issues)
- `error` - Error messages (operation failures)

**Errors:**
- `404` - Job execution not found

---

## Local Development

**Note:** All local development endpoints require `LOCAL_AUTH_ENABLED=true` in the environment. These endpoints return `403 Forbidden` in production.

### Get Test Users

**Endpoint:** `GET /api/local/users`
**Authentication:** Local only

Returns list of test users for local development.

**Response:**
```json
[
  {
    "id": "test-user-1",
    "name": "Test User 1",
    "email": "test1@example.com",
    "is_test_user": true
  }
]
```

### Local Login

**Endpoint:** `POST /api/local/login`
**Authentication:** Local only

Sets the current user session for local development.

**Request Body:**
```json
{
  "user_id": "test-user-1"
}
```

**Response:**
```json
{
  "message": "Logged in successfully",
  "user": {
    "id": "test-user-1",
    "name": "Test User 1"
  }
}
```

### Create Test User

**Endpoint:** `POST /api/local/create_test_user`
**Authentication:** Local only

Creates a new test user.

**Request Body:**
```json
{
  "name": "Test User",
  "email": "test@example.com"
}
```

**Response:**
```json
{
  "message": "Test user created successfully",
  "user": {
    "id": "test-user-uuid",
    "name": "Test User",
    "email": "test@example.com",
    "is_test_user": true
  }
}
```

### Reset Test User

**Endpoint:** `POST /api/local/reset-user/<user_id>`
**Authentication:** Local only

Resets all data for a test user (deletes recordings, transcriptions, clears settings).

**URL Parameters:**
- `user_id` (string) - Test user UUID

**Response:**
```json
{
  "message": "User data reset successfully",
  "deleted_recordings": 15,
  "deleted_transcriptions": 12
}
```

### Delete Test User

**Endpoint:** `POST /api/local/delete_test_user/<user_id>`
**Authentication:** Local only

Deletes a test user and all associated data.

**URL Parameters:**
- `user_id` (string) - Test user UUID

**Response:**
```json
{
  "message": "Test user deleted successfully",
  "deleted_recordings": 15,
  "deleted_transcriptions": 12,
  "deleted_blobs": 13
}
```

### Create Dummy Recording

**Endpoint:** `POST /api/local/create_dummy_recording`
**Authentication:** 🔒 Required (Local only)

Creates a dummy recording for testing (no actual audio file).

**Request Body:**
```json
{
  "title": "Test Recording",
  "original_filename": "test.mp3"
}
```

**Response:**
```json
{
  "message": "Dummy recording created successfully",
  "recording": {
    "id": "dummy-recording-uuid",
    "title": "Test Recording",
    "is_dummy_recording": true,
    "transcoding_status": "completed",
    "transcription_status": "not_started",
    ...
  }
}
```

---

## Data Models

### User
```typescript
{
  id: string;
  email?: string;
  name?: string;
  role?: string;
  created_at?: string;
  last_login?: string;
  plaudSettings?: PlaudSettings;
  tags?: Tag[];
  partitionKey: string;
  is_test_user?: boolean;
}
```

### Recording
```typescript
{
  id: string;
  user_id: string;
  original_filename: string;
  unique_filename: string;
  title?: string;
  description?: string;
  recorded_timestamp?: string;
  upload_timestamp?: string;
  duration?: number;
  source?: "upload" | "plaud" | "stream";
  transcoding_status?: "not_started" | "queued" | "in_progress" | "completed" | "failed";
  transcription_status?: "not_started" | "in_progress" | "completed" | "failed";
  transcription_id?: string;
  participants?: string[] | RecordingParticipant[];
  tagIds?: string[];
  plaudMetadata?: PlaudMetadata;
  partitionKey: string;
}
```

### Transcription
```typescript
{
  id: string;
  user_id: string;
  recording_id: string;
  text?: string;
  diarized_transcript?: string;
  speaker_mapping?: {
    [speakerLabel: string]: {
      name: string;
      displayName?: string;
      participantId?: string;
      reasoning: string;
      confidence: number;
      manuallyVerified?: boolean;
    }
  };
  analysisResults?: AnalysisResult[];
  created_at?: string;
  partitionKey: string;
}
```

### Participant
```typescript
{
  id: string;
  userId: string;
  firstName?: string;
  lastName?: string;
  displayName: string;
  aliases: string[];
  email?: string;
  role?: string;
  organization?: string;
  relationshipToUser?: string;
  notes?: string;
  isUser?: boolean;
  firstSeen: string;
  lastSeen: string;
  createdAt: string;
  updatedAt: string;
  partitionKey: string;
}
```

### AnalysisType
```typescript
{
  id: string;
  name: string;
  title: string;
  shortTitle: string;
  description: string;
  icon: string;
  prompt: string;
  userId?: string;
  isActive: boolean;
  isBuiltIn: boolean;
  createdAt: string;
  updatedAt: string;
  partitionKey: string;
}
```

### AnalysisResult
```typescript
{
  analysisType: string;
  analysisTypeId: string;
  content: string;
  createdAt: string;
  status: "pending" | "completed" | "failed";
  errorMessage?: string;
  llmResponseTimeMs?: number;
  promptTokens?: number;
  responseTokens?: number;
}
```

### SyncProgress
```typescript
{
  id: string;
  syncToken: string;
  userId: string;
  status: "queued" | "processing" | "completed" | "failed";
  totalRecordings?: number;
  processedRecordings: number;
  failedRecordings: number;
  currentStep: string;
  errors: string[];
  startTime: string;
  lastUpdate: string;
  ttl?: number;
  partitionKey: string;
}
```

---

## Webhooks & Callbacks

The backend uses a callback system for asynchronous processing:

### Transcoding Callbacks
- **URL:** `POST /api/transcoding_callback`
- **Authentication:** Callback token validation
- **Triggers:** Transcoding container sends status updates
- **Actions:** Updates recording status, triggers AI post-processing

### Plaud Callbacks
- **URL:** `POST /plaud/plaud_callback`
- **Authentication:** Callback token validation
- **Triggers:** Plaud sync service sends progress updates
- **Actions:** Registers recordings, updates sync progress

---

## Rate Limiting & Quotas

**Azure Speech Services:**
- Concurrent transcription limit: Based on Azure tier
- Transcription timeout: 30 days for in-progress jobs

**Plaud Sync:**
- Sync timeout: 1 hour
- Stale sync cleanup: 2 hours

**Storage:**
- Blob SAS URLs expire after 24 hours
- Sync progress records TTL: 24 hours

---

## Error Handling Best Practices

### Client Implementation

1. **Authentication Errors (401):**
   - Refresh Azure AD token
   - Re-attempt request with new token
   - Redirect to login if token refresh fails

2. **Not Found Errors (404):**
   - Verify resource ID is correct
   - Check user has access to resource

3. **Conflict Errors (409):**
   - Handle duplicate resource creation
   - Wait for existing operation to complete

4. **Server Errors (500):**
   - Implement exponential backoff retry
   - Log error details for debugging
   - Show user-friendly error message

### Polling Patterns

For long-running operations (transcoding, transcription, sync):

```javascript
// Poll every 2 seconds for status updates
const pollInterval = 2000;
const maxAttempts = 150; // 5 minutes max

async function pollStatus(recordingId) {
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`/api/transcoding_status/${recordingId}`);
    const status = await response.json();

    if (status.transcoding_status === 'completed') {
      return status;
    } else if (status.transcoding_status === 'failed') {
      throw new Error(status.transcoding_error_message);
    }

    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }

  throw new Error('Timeout waiting for transcoding');
}
```

---

## Changelog

### Version History

See `/api/get_api_version` for current version.

**Recent Changes:**
- Added participant management system
- Added custom analysis types
- Added Plaud sync progress tracking
- Enhanced speaker mapping with participant IDs
- Added AI post-processing automation
