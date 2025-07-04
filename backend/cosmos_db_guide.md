# QuickScribe CosmosDB Query Guide

This guide explains the structure of data in QuickScribe's CosmosDB and how to query it effectively.

## Connection Configuration

### Environment Variables
The connection details are stored in the backend's `.env` file (or `.env.local` for local development). You need these environment variables:

```bash
# CosmosDB Connection
COSMOS_URL=<your-cosmos-endpoint>          # The CosmosDB account endpoint URL
COSMOS_KEY=<your-cosmos-key>               # The primary or secondary key
COSMOS_DB_NAME=QuickScribeDatabase         # Database name (default: QuickScribeDatabase)
COSMOS_CONTAINER_NAME=QuickScribeContainer # Main container name (default: QuickScribeContainer)

# Azure Blob Storage Connection (for related file storage)
AZURE_STORAGE_CONNECTION_STRING=<connection-string>  # Full connection string
AZURE_RECORDING_BLOB_CONTAINER=recordings            # Container name for audio files
```

### Loading Configuration
The backend uses `config.py` to load these values:
```python
from dotenv import load_dotenv
import os

# Load appropriate .env file
load_dotenv('.env.local')  # or .env.production

# Access configuration
cosmos_url = os.getenv('COSMOS_URL')
cosmos_key = os.getenv('COSMOS_KEY')
database_name = os.getenv('COSMOS_DB_NAME', 'QuickScribeDatabase')
container_name = os.getenv('COSMOS_CONTAINER_NAME', 'QuickScribeContainer')
```

## Database Structure Overview

QuickScribe uses Azure Cosmos DB with the following structure:
- **Database Name**: `QuickScribeDatabase` (configured via `COSMOS_DB_NAME`)
- **Main Container**: `QuickScribeContainer` (configured via `COSMOS_CONTAINER_NAME`)
- **Additional Containers**: `participants`, `analysis_types`, `sync_progress`

## Document Types and Schemas

### 1. Users (in main container)
**Partition Key**: `"user"`  
**Document ID Pattern**: `user-{uuid}`

#### Schema:
```json
{
  "id": "user-123e4567-e89b-12d3-a456-426614174000",
  "partitionKey": "user",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "user",
  "created_at": "2024-01-15T10:30:00Z",
  "last_login": "2024-01-20T14:22:00Z",
  "updated_at": "2024-01-20T14:22:00Z",
  "is_test_user": false,
  "tags": [
    {
      "id": "tag-001",
      "name": "meetings",
      "color": "#FF5733"
    }
  ],
  "plaudSettings": {
    "plaudEmail": "user@plaud.com",
    "plaudPassword": "encrypted",
    "activeSyncToken": "token123",
    "activeSyncStarted": "2024-01-20T10:00:00Z",
    "lastSyncTimestamp": "2024-01-20T12:00:00Z"
  }
}
```

#### Common Queries:
```sql
-- Get all users
SELECT * FROM c WHERE c.partitionKey = 'user'

-- Get user by email
SELECT * FROM c WHERE c.partitionKey = 'user' AND c.email = 'user@example.com'

-- Get users with Plaud integration
SELECT * FROM c WHERE c.partitionKey = 'user' AND IS_DEFINED(c.plaudSettings)

-- Get test users
SELECT * FROM c WHERE c.partitionKey = 'user' AND c.is_test_user = true

-- Get users created after a date
SELECT * FROM c WHERE c.partitionKey = 'user' AND c.created_at > '2024-01-01'
```

### 2. Recordings (in main container)
**Partition Key**: `"recording"`  
**Document ID Pattern**: `{uuid}`

#### Schema:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "partitionKey": "recording",
  "user_id": "user-123e4567-e89b-12d3-a456-426614174000",
  "original_filename": "meeting_notes.mp3",
  "unique_filename": "550e8400-e29b-41d4-a716-446655440000.mp3",
  "blob_name": "recordings/user-123/550e8400-e29b-41d4-a716-446655440000.mp3",
  "title": "Weekly Team Meeting",
  "description": "Discussion about Q1 goals and project updates",
  "duration": 1800,
  "recorded_timestamp": "2024-01-20T10:00:00Z",
  "upload_timestamp": "2024-01-20T11:00:00Z",
  "transcription_status": "completed",
  "transcoding_status": "completed",
  "source": "upload",
  "participants": [
    {
      "id": "part-001",
      "displayName": "John Doe",
      "speakerLabel": "Speaker 1"
    }
  ],
  "tagIds": ["tag-001", "tag-002"],
  "plaudMetadata": {
    "deviceId": "plaud-device-123",
    "originalRecordingId": "plaud-rec-456"
  }
}
```

#### Common Queries:
```sql
-- Get all recordings for a user
SELECT * FROM c WHERE c.partitionKey = 'recording' AND c.user_id = 'user-123'

-- Get recordings by transcription status
SELECT * FROM c WHERE c.partitionKey = 'recording' AND c.transcription_status = 'completed'

-- Get recordings from Plaud devices
SELECT * FROM c WHERE c.partitionKey = 'recording' AND c.source = 'plaud'

-- Get recordings with specific tags
SELECT * FROM c WHERE c.partitionKey = 'recording' AND ARRAY_CONTAINS(c.tagIds, 'tag-001')

-- Get recordings longer than 30 minutes
SELECT * FROM c WHERE c.partitionKey = 'recording' AND c.duration > 1800

-- Get recordings by date range
SELECT * FROM c 
WHERE c.partitionKey = 'recording' 
  AND c.recorded_timestamp >= '2024-01-01' 
  AND c.recorded_timestamp < '2024-02-01'
```

### 3. Transcriptions (in main container)
**Partition Key**: `"transcription"`  
**Document ID Pattern**: `{uuid}`

#### Schema:
```json
{
  "id": "650e8400-e29b-41d4-a716-446655440001",
  "partitionKey": "transcription",
  "user_id": "user-123e4567-e89b-12d3-a456-426614174000",
  "recording_id": "550e8400-e29b-41d4-a716-446655440000",
  "az_transcription_id": "azure-trans-789",
  "text": "Full transcript text here...",
  "diarized_transcript": [
    {
      "speaker": "Speaker 1",
      "text": "Hello everyone, let's start the meeting.",
      "start": 0.0,
      "end": 3.5
    }
  ],
  "transcript_json": "{\"recognizedPhrases\":[...],\"duration\":\"PT53M34.35S\",...}",
  "speaker_mapping": {
    "Speaker 1": "part-001",
    "Speaker 2": "part-002"
  },
  "analysisResults": [
    {
      "analysisTypeId": "analysis-001",
      "result": "Meeting summary...",
      "createdAt": "2024-01-20T12:00:00Z"
    }
  ],
  "created_at": "2024-01-20T11:30:00Z",
  "updated_at": "2024-01-20T12:00:00Z"
}
```

#### transcript_json Field Structure:
The `transcript_json` field contains a JSON string (escaped) with the raw Azure Speech Services transcription result. When parsed, it has this structure:

```json
{
  "source": "https://quickscribestorage.blob.core.windows.net/recordings/[blob_name]",
  "timestamp": "2025-05-07T21:01:55Z",
  "duration": "PT53M34.35S",              // ISO 8601 duration format
  "durationInTicks": 32143500000,         // Duration in 100-nanosecond units
  "durationMilliseconds": 3214350,        // Duration in milliseconds
  "combinedRecognizedPhrases": [          // Full transcript combined
    {
      "channel": 0,
      "display": "Full formatted transcript text with punctuation...",
      "itn": "full transcript without punctuation all lowercase...",
      "lexical": "raw words as spoken...",
      "maskedITN": "Full transcript with Proper Case formatting..."
    }
  ],
  "recognizedPhrases": [                  // Individual phrases/segments
    {
      "channel": 0,
      "speaker": 1,                       // Speaker ID (1, 2, 3, etc.)
      "offset": "PT0.12S",                // Start time in ISO 8601
      "offsetInTicks": 1200000,
      "offsetMilliseconds": 120,
      "duration": "PT3.32S",              // Phrase duration
      "durationInTicks": 33200000,
      "durationMilliseconds": 3320,
      "recognitionStatus": "Success",
      "nBest": [                          // Recognition alternatives
        {
          "confidence": 0.89710826,       // Confidence score (0-1)
          "display": "It's come up recently to be able to share some of that.",
          "itn": "it's come up recently to be able to share some of that",
          "lexical": "it's come up recently to be able to share some of that",
          "maskedITN": "It's come up recently to be able to share some of that"
        }
      ]
    }
    // ... hundreds more phrases
  ]
}
```

**Key Fields in transcript_json:**
- `recognizedPhrases`: Array of all spoken segments with speaker identification
- `speaker`: Integer ID for each speaker (1, 2, 3, etc.)
- `confidence`: Float between 0-1 indicating transcription confidence
- `display`: Formatted text with punctuation and capitalization
- `itn`: "Inverse Text Normalization" - lowercase without punctuation
- `lexical`: Raw words exactly as recognized
- `maskedITN`: Display text with standardized capitalization

#### Common Queries:
```sql
-- Get transcription for a recording
SELECT * FROM c WHERE c.partitionKey = 'transcription' AND c.recording_id = 'recording-123'

-- Get all transcriptions for a user
SELECT * FROM c WHERE c.partitionKey = 'transcription' AND c.user_id = 'user-123'

-- Get transcriptions with speaker diarization
SELECT * FROM c WHERE c.partitionKey = 'transcription' AND IS_DEFINED(c.diarized_transcript)

-- Get transcriptions with analysis results
SELECT * FROM c WHERE c.partitionKey = 'transcription' AND ARRAY_LENGTH(c.analysisResults) > 0

-- Search transcriptions by text content (partial match)
SELECT * FROM c WHERE c.partitionKey = 'transcription' AND CONTAINS(c.text, 'project deadline')
```

### 4. Participants (separate container)
**Container Name**: `participants`  
**Partition Key**: `userId`

#### Schema:
```json
{
  "id": "part-001",
  "userId": "user-123e4567-e89b-12d3-a456-426614174000",
  "displayName": "John Doe",
  "firstName": "John",
  "lastName": "Doe",
  "email": "john.doe@company.com",
  "aliases": ["JD", "John D"],
  "organization": "Acme Corp",
  "role": "Engineering Manager",
  "relationshipToUser": "self",
  "notes": "Prefers morning meetings",
  "isUser": true,
  "firstSeen": "2024-01-01T10:00:00Z",
  "lastSeen": "2024-01-20T14:00:00Z",
  "createdAt": "2024-01-01T10:00:00Z",
  "updatedAt": "2024-01-20T14:00:00Z"
}
```

#### Common Queries:
```sql
-- Get all participants for a user
SELECT * FROM c WHERE c.userId = 'user-123'

-- Find participant by email
SELECT * FROM c WHERE c.email = 'john.doe@company.com'

-- Find participants by organization
SELECT * FROM c WHERE c.organization = 'Acme Corp'

-- Find the user's own participant record
SELECT * FROM c WHERE c.userId = 'user-123' AND c.isUser = true

-- Search participants by name or alias
SELECT * FROM c 
WHERE c.userId = 'user-123' 
  AND (CONTAINS(c.displayName, 'John') OR ARRAY_CONTAINS(c.aliases, 'JD'))
```

### 5. Analysis Types (separate container)
**Container Name**: `analysis_types`  
**Partition Key**: `partitionKey` (value: `"global"` for built-in, `userId` for custom)

#### Schema:
```json
{
  "id": "analysis-001",
  "partitionKey": "global",
  "name": "meeting_summary",
  "title": "Meeting Summary",
  "shortTitle": "Summary",
  "description": "Generates a concise summary of the meeting including key points and decisions",
  "icon": "DocumentTextIcon",
  "prompt": "Summarize this meeting transcript...",
  "isBuiltIn": true,
  "isActive": true,
  "userId": null,
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T00:00:00Z"
}
```

#### Common Queries:
```sql
-- Get all built-in analysis types
SELECT * FROM c WHERE c.partitionKey = 'global'

-- Get active analysis types
SELECT * FROM c WHERE c.isActive = true

-- Get custom analysis types for a user
SELECT * FROM c WHERE c.partitionKey = 'user-123'

-- Get analysis type by name
SELECT * FROM c WHERE c.name = 'meeting_summary'
```

### 6. Sync Progress (separate container)
**Container Name**: `sync_progress`  
**Partition Key**: `userId`  
**Note**: Documents have TTL and auto-expire after 24 hours

#### Schema:
```json
{
  "id": "sync-token-abc123",
  "syncToken": "sync-token-abc123",
  "userId": "user-123e4567-e89b-12d3-a456-426614174000",
  "partitionKey": "user-123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "currentStep": "Downloading recording 5 of 20",
  "processedRecordings": 5,
  "failedRecordings": 1,
  "totalRecordings": 20,
  "errors": [
    "Failed to download recording plaud-rec-789: Network timeout"
  ],
  "startTime": "2024-01-20T10:00:00Z",
  "lastUpdate": "2024-01-20T10:05:00Z",
  "estimatedCompletion": "2024-01-20T10:30:00Z",
  "ttl": 1705834800
}
```

#### Common Queries:
```sql
-- Get active sync for a user
SELECT * FROM c WHERE c.userId = 'user-123' AND c.status IN ('queued', 'processing')

-- Get sync by token
SELECT * FROM c WHERE c.syncToken = 'sync-token-abc123'

-- Get failed syncs
SELECT * FROM c WHERE c.userId = 'user-123' AND c.status = 'failed'

-- Get syncs with errors
SELECT * FROM c WHERE c.userId = 'user-123' AND ARRAY_LENGTH(c.errors) > 0
```

## Python Query Examples

### Basic Connection and Query
```python
from azure.cosmos import CosmosClient
import os
from dotenv import load_dotenv

# Load environment variables from backend/.env.local
load_dotenv('../backend/.env.local')

# Connection using environment variables
client = CosmosClient(
    url=os.getenv('COSMOS_URL'),
    credential=os.getenv('COSMOS_KEY')
)
database = client.get_database_client(os.getenv('COSMOS_DB_NAME', 'QuickScribeDatabase'))
container = database.get_container_client(os.getenv('COSMOS_CONTAINER_NAME', 'QuickScribeContainer'))

# Simple query
query = "SELECT * FROM c WHERE c.partitionKey = 'user'"
users = list(container.query_items(
    query=query,
    enable_cross_partition_query=True
))
```

### Query with Parameters
```python
# Parameterized query to prevent injection
query = "SELECT * FROM c WHERE c.partitionKey = @partitionKey AND c.email = @email"
parameters = [
    {"name": "@partitionKey", "value": "user"},
    {"name": "@email", "value": "user@example.com"}
]
users = list(container.query_items(
    query=query,
    parameters=parameters,
    enable_cross_partition_query=True
))
```

### Efficient Partition Query
```python
# When you know the partition key, specify it for better performance
recordings = list(container.query_items(
    query="SELECT * FROM c WHERE c.user_id = 'user-123'",
    partition_key="recording"
))
```

### Complex Query with Joins
```python
# Get recordings with their transcription status
query = """
SELECT 
    r.id,
    r.title,
    r.duration,
    t.id as transcription_id,
    ARRAY_LENGTH(t.analysisResults) as analysis_count
FROM recordings r
JOIN transcriptions t ON r.id = t.recording_id
WHERE r.user_id = @userId
"""
```

## Performance Tips

1. **Always use partition keys** when possible to avoid cross-partition queries
2. **Use parameterized queries** to prevent injection and improve caching
3. **Limit result sets** with TOP clause for better performance
4. **Project only needed fields** instead of SELECT *
5. **Use indexes** for frequently queried fields
6. **Consider using change feed** for real-time updates

## Common Patterns

### Get User's Complete Data
```python
def get_user_data(user_id):
    # Get user
    user = container.read_item(item=f"user-{user_id}", partition_key="user")
    
    # Get recordings
    recordings = list(container.query_items(
        query="SELECT * FROM c WHERE c.partitionKey = 'recording' AND c.user_id = @userId",
        parameters=[{"name": "@userId", "value": user_id}],
        enable_cross_partition_query=True
    ))
    
    # Get transcriptions
    recording_ids = [r['id'] for r in recordings]
    transcriptions = list(container.query_items(
        query="SELECT * FROM c WHERE c.partitionKey = 'transcription' AND ARRAY_CONTAINS(@recordingIds, c.recording_id)",
        parameters=[{"name": "@recordingIds", "value": recording_ids}],
        enable_cross_partition_query=True
    ))
    
    return {
        "user": user,
        "recordings": recordings,
        "transcriptions": transcriptions
    }
```

### Search Across Transcriptions
```python
def search_transcriptions(user_id, search_term):
    query = """
    SELECT 
        t.id,
        t.recording_id,
        t.text,
        SUBSTRING(t.text, 0, 200) as preview
    FROM c t
    WHERE t.partitionKey = 'transcription' 
        AND t.user_id = @userId
        AND CONTAINS(LOWER(t.text), LOWER(@searchTerm))
    """
    
    return list(container.query_items(
        query=query,
        parameters=[
            {"name": "@userId", "value": user_id},
            {"name": "@searchTerm", "value": search_term}
        ],
        enable_cross_partition_query=True
    ))
```

## Useful System Properties

CosmosDB adds these system properties to all documents:
- `_rid`: Resource ID
- `_self`: Self link
- `_etag`: Entity tag for optimistic concurrency
- `_attachments`: Attachments link
- `_ts`: Timestamp (Unix epoch)

Filter these out when returning data to users:
```python
COSMOS_SYSTEM_FIELDS = {"_rid", "_self", "_etag", "_attachments", "_ts"}

def filter_cosmos_fields(document):
    return {k: v for k, v in document.items() if k not in COSMOS_SYSTEM_FIELDS}
```