# Azure Speech Services Transcription Guide

This guide explains how to use Azure Speech Services Batch Transcription API to transcribe MP3 audio files with speaker diarization. It covers the complete workflow from preparing audio files to retrieving transcription results.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Audio File Preparation](#audio-file-preparation)
4. [Workflow](#workflow)
5. [Step 1: Prepare and Upload MP3 Files](#step-1-prepare-and-upload-mp3-files)
6. [Step 2: Submit Transcription Job](#step-2-submit-transcription-job)
7. [Step 3: Poll for Job Status](#step-3-poll-for-job-status)
8. [Step 4: Retrieve Transcription Results](#step-4-retrieve-transcription-results)
9. [Transcription Result Schema](#transcription-result-schema)
10. [Code Examples](#code-examples)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Azure Speech Services Batch Transcription API (v3.2) provides:
- **Asynchronous batch transcription** for large audio files
- **Speaker diarization** (identifying different speakers, 1-5 speakers supported)
- **High accuracy** speech-to-text conversion
- **RESTful API** for job submission and status polling
- **Structured JSON results** with timestamps and speaker labels

**Key Limitations:**
- Maximum file size: **~1 GB** (recommended max: 300 MB)
- Maximum duration: **~4 hours** (recommended max: 2 hours)
- Files exceeding these limits should be chunked (see [Audio File Preparation](#audio-file-preparation))

---

## Prerequisites

### 1. Azure Speech Services Resource

Create an Azure Speech Services resource:
```bash
# Azure CLI
az cognitiveservices account create \
  --name my-speech-service \
  --resource-group my-resource-group \
  --kind SpeechServices \
  --sku S0 \
  --location westus2
```

You'll need:
- **Subscription Key**: Found in Azure Portal → Resource → Keys and Endpoint
- **Region**: e.g., `westus2`, `eastus`, `northeurope`

### 2. Azure Blob Storage

Audio files must be accessible via HTTPS URL (typically Azure Blob Storage with SAS URL):

```bash
# Upload audio file to blob storage
az storage blob upload \
  --account-name mystorageaccount \
  --container-name audio-files \
  --name recording.mp3 \
  --file /path/to/recording.mp3

# Generate SAS URL (48-hour expiration recommended)
az storage blob generate-sas \
  --account-name mystorageaccount \
  --container-name audio-files \
  --name recording.mp3 \
  --permissions r \
  --expiry $(date -u -d '48 hours' '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --full-uri
```

### 3. Required Software

- **Python 3.8+** (for Python implementation)
- **Azure Speech Client Package**
  ```bash
  # Install from the python-client directory
  pip install -e /path/to/azure_speech/python-client

  # Or install the pre-built wheel
  pip install /path/to/azure_speech/python-client/dist/azure_speech_client-3.2.0-py3-none-any.whl
  ```
- **FFmpeg** (for audio transcoding)
  ```bash
  # Linux
  sudo apt-get install ffmpeg

  # macOS
  brew install ffmpeg

  # Windows (with Chocolatey)
  choco install ffmpeg
  ```

---

## Audio File Preparation

Azure Speech Services requires properly encoded MP3 files. Even if your files are already MP3, transcoding ensures compatibility and prevents errors.

### FFmpeg Transcoding Command

**Standard transcoding for maximum compatibility:**

```bash
ffmpeg -i input.mp3 \
  -acodec libmp3lame \
  -b:a 128k \
  output_transcoded.mp3
```

**Parameters explained:**
- `-i input.mp3`: Input file
- `-acodec libmp3lame`: Use MP3 LAME encoder (industry standard)
- `-b:a 128k`: Audio bitrate of 128 kbps (good balance of quality/size)
- `output_transcoded.mp3`: Output file

**Optional quality settings:**
```bash
# Higher quality (192 kbps)
ffmpeg -i input.mp3 -acodec libmp3lame -b:a 192k output.mp3

# Lower quality/smaller size (96 kbps)
ffmpeg -i input.mp3 -acodec libmp3lame -b:a 96k output.mp3

# Preserve original bitrate
ffmpeg -i input.mp3 -acodec libmp3lame output.mp3
```

### Why Transcode?

Even if files are already MP3:
1. **Codec compatibility**: Ensures MP3 LAME encoding (most compatible)
2. **Metadata cleanup**: Removes problematic tags/metadata
3. **Bitrate standardization**: Consistent audio quality
4. **Container normalization**: Fixes malformed MP3 containers

### Handling Large Files (Chunking)

Files larger than **300 MB** or longer than **2 hours** should be split into chunks:

```bash
# Get duration first
ffprobe -i input.mp3 -show_entries format=duration -v quiet -of csv="p=0"

# Split into 90-minute chunks (5400 seconds)
# Chunk 1: 0 to 90 minutes
ffmpeg -i input.mp3 -ss 0 -t 5400 \
  -acodec libmp3lame -b:a 128k chunk1.mp3

# Chunk 2: 90 to 180 minutes
ffmpeg -i input.mp3 -ss 5400 -t 5400 \
  -acodec libmp3lame -b:a 128k chunk2.mp3

# Chunk 3: remainder
ffmpeg -i input.mp3 -ss 10800 \
  -acodec libmp3lame -b:a 128k chunk3.mp3
```

**Parameters:**
- `-ss <seconds>`: Start time (seek to position)
- `-t <seconds>`: Duration to extract
- `-codec copy`: Fast copy without re-encoding (use only if already compatible MP3)

**Automated chunking script (Python):**
```python
import ffmpeg

def split_audio(input_file, num_chunks, total_duration):
    """Split audio into equal chunks."""
    chunk_duration = total_duration / num_chunks
    chunk_files = []

    for i in range(num_chunks):
        start_time = i * chunk_duration
        output_file = f"chunk_{i+1}.mp3"

        (
            ffmpeg
            .input(input_file, ss=start_time, t=chunk_duration)
            .output(output_file, acodec='libmp3lame', audio_bitrate='128k')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        chunk_files.append(output_file)

    return chunk_files
```

---

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Transcription Workflow                        │
└─────────────────────────────────────────────────────────────────┘

1. PREPARE AUDIO
   ├─ Transcode MP3 with FFmpeg (libmp3lame, 128k)
   ├─ Check file size (<300 MB) and duration (<2 hours)
   └─ Split into chunks if needed

2. UPLOAD TO BLOB STORAGE
   ├─ Upload transcoded MP3 to Azure Blob Storage
   └─ Generate SAS URL with read permissions (48-hour expiry)

3. SUBMIT TRANSCRIPTION JOB
   ├─ POST to Azure Speech Services API
   ├─ Include blob SAS URL as content_url
   ├─ Enable speaker diarization (1-5 speakers)
   └─ Receive transcription job ID

4. POLL FOR STATUS (async)
   ├─ GET job status every 30-60 seconds
   ├─ Status: NotStarted → Running → Succeeded/Failed
   └─ Typical duration: 30-50% of audio length

5. RETRIEVE RESULTS
   ├─ GET transcription files list
   ├─ Find file with kind="Transcription"
   ├─ Download JSON from content_url
   └─ Parse recognizedPhrases with speaker labels
```

---

## Step 1: Prepare and Upload MP3 Files

### 1.1 Transcode Audio

```bash
# Process directory of MP3 files
for file in /path/to/mp3s/*.mp3; do
    filename=$(basename "$file" .mp3)
    ffmpeg -i "$file" \
      -acodec libmp3lame \
      -b:a 128k \
      "/path/to/output/${filename}_transcoded.mp3"
done
```

### 1.2 Upload to Blob Storage

```python
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

# Initialize client
blob_service_client = BlobServiceClient.from_connection_string(
    "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;"
)
container_client = blob_service_client.get_container_client("audio-files")

# Upload file
with open("transcoded.mp3", "rb") as data:
    blob_client = container_client.upload_blob(
        name="recordings/file1.mp3",
        data=data,
        overwrite=True
    )

# Generate SAS URL (48-hour expiration)
sas_token = generate_blob_sas(
    account_name="mystorageaccount",
    container_name="audio-files",
    blob_name="recordings/file1.mp3",
    account_key="your-account-key",
    permission=BlobSasPermissions(read=True),
    expiry=datetime.utcnow() + timedelta(hours=48)
)

blob_url_with_sas = f"https://mystorageaccount.blob.core.windows.net/audio-files/recordings/file1.mp3?{sas_token}"
print(f"SAS URL: {blob_url_with_sas}")
```

---

## Step 2: Submit Transcription Job

### 2.1 API Endpoint

```
POST https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions
```

### 2.2 Headers

```
Ocp-Apim-Subscription-Key: YOUR_SUBSCRIPTION_KEY
Content-Type: application/json
```

### 2.3 Request Body

```json
{
  "displayName": "Transcription of recording.mp3",
  "description": "Transcription started at 2025-01-21 14:30:00",
  "locale": "en-US",
  "contentUrls": [
    "https://mystorageaccount.blob.core.windows.net/audio-files/recording.mp3?sp=r&se=..."
  ],
  "properties": {
    "punctuationMode": "DictatedAndAutomatic",
    "diarizationEnabled": true,
    "diarization": {
      "speakers": {
        "minCount": 1,
        "maxCount": 5
      }
    }
  }
}
```

**Key properties:**
- `displayName`: Human-readable name for the job
- `locale`: Language code (e.g., `en-US`, `en-GB`, `es-ES`)
- `contentUrls`: Array of blob SAS URLs (can submit multiple files in one job)
- `punctuationMode`: `DictatedAndAutomatic` adds punctuation automatically
- `diarizationEnabled`: Enable speaker identification
- `diarization.speakers.minCount/maxCount`: Expected speaker range (1-5)

### 2.4 Python Example

```python
import azure_speech_client

# Configure API client
configuration = azure_speech_client.Configuration()
configuration.api_key["Ocp-Apim-Subscription-Key"] = "YOUR_SUBSCRIPTION_KEY"
configuration.host = "https://westus2.api.cognitive.microsoft.com/speechtotext/v3.2"
api_client = azure_speech_client.ApiClient(configuration)
api = azure_speech_client.CustomSpeechTranscriptionsApi(api_client)

# Create transcription properties
properties = azure_speech_client.TranscriptionProperties()
properties.punctuation_mode = "DictatedAndAutomatic"
properties.diarization_enabled = True
properties.diarization = azure_speech_client.DiarizationProperties(
    azure_speech_client.DiarizationSpeakersProperties(min_count=1, max_count=5)
)

# Create transcription request
transcription_definition = azure_speech_client.Transcription(
    display_name="Transcription of recording.mp3",
    description="Transcription started at 2025-01-21 14:30:00",
    locale="en-US",
    content_urls=[blob_url_with_sas],
    properties=properties
)

# Submit transcription
created_transcription, status, headers = api.transcriptions_create_with_http_info(
    transcription=transcription_definition
)

# Extract transcription ID from location header
transcription_id = headers["location"].split("/")[-1]
print(f"Transcription submitted: {transcription_id}")
```

### 2.5 cURL Example

```bash
curl -X POST \
  "https://westus2.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions" \
  -H "Ocp-Apim-Subscription-Key: YOUR_SUBSCRIPTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "displayName": "Transcription of recording.mp3",
    "description": "Transcription started at 2025-01-21 14:30:00",
    "locale": "en-US",
    "contentUrls": [
      "https://mystorageaccount.blob.core.windows.net/audio-files/recording.mp3?sp=r&se=..."
    ],
    "properties": {
      "punctuationMode": "DictatedAndAutomatic",
      "diarizationEnabled": true,
      "diarization": {
        "speakers": {
          "minCount": 1,
          "maxCount": 5
        }
      }
    }
  }'
```

**Response:**
```
HTTP/1.1 201 Created
Location: https://westus2.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions/12345678-abcd-1234-abcd-123456789abc

{
  "self": "https://westus2.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions/12345678-abcd-1234-abcd-123456789abc",
  "displayName": "Transcription of recording.mp3",
  "description": "Transcription started at 2025-01-21 14:30:00",
  "locale": "en-US",
  "createdDateTime": "2025-01-21T14:30:05Z",
  "lastActionDateTime": "2025-01-21T14:30:05Z",
  "status": "NotStarted",
  ...
}
```

---

## Step 3: Poll for Job Status

Transcription jobs are asynchronous. Poll the status endpoint until the job completes.

### 3.1 Status API Endpoint

```
GET https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions/{transcriptionId}
```

### 3.2 Status Progression

```
NotStarted → Running → Succeeded
                    ↘ Failed
```

**Typical timing:**
- **NotStarted**: 0-30 seconds (queued)
- **Running**: 30-50% of audio duration (e.g., 10-minute audio = 3-5 minutes processing)
- **Succeeded/Failed**: Final state

### 3.3 Polling Strategy

**Recommended polling interval: 30-60 seconds**

```python
import time

def poll_transcription_status(api, transcription_id, interval=30, timeout=3600):
    """Poll transcription status until completion or timeout."""
    start_time = time.time()

    while True:
        # Check if timeout exceeded
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Transcription {transcription_id} timed out after {timeout}s")

        # Get current status
        transcription = api.transcriptions_get(transcription_id)
        status = transcription.status

        print(f"Status: {status}")

        if status == "Succeeded":
            print("Transcription completed successfully!")
            return transcription
        elif status == "Failed":
            error = transcription.properties.error if transcription.properties else None
            error_msg = f"{error.code}: {error.message}" if error else "Unknown error"
            raise Exception(f"Transcription failed: {error_msg}")
        elif status in ["NotStarted", "Running"]:
            print(f"Still processing... waiting {interval}s")
            time.sleep(interval)
        else:
            print(f"Unknown status: {status}")
            time.sleep(interval)

# Usage
transcription = poll_transcription_status(api, transcription_id)
```

### 3.4 Status Response Fields

```json
{
  "self": "https://.../transcriptions/12345678-abcd-...",
  "displayName": "Transcription of recording.mp3",
  "createdDateTime": "2025-01-21T14:30:05Z",
  "lastActionDateTime": "2025-01-21T14:35:22Z",
  "status": "Succeeded",
  "properties": {
    "duration": "PT41M46.3S",
    "durationInTicks": 25063000000,
    "channels": [0],
    "successfulChannelsCount": 1
  },
  "links": {
    "files": "https://.../transcriptions/12345678-abcd-.../files"
  }
}
```

**Key fields:**
- `status`: Current job status
- `properties.duration`: Audio duration in ISO 8601 format (`PT41M46.3S` = 41 minutes 46.3 seconds)
- `properties.durationInTicks`: Duration in .NET ticks (10,000 ticks = 1 millisecond)
- `links.files`: URL to retrieve transcription result files

---

## Step 4: Retrieve Transcription Results

### 4.1 List Files Endpoint

```
GET https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions/{transcriptionId}/files
```

### 4.2 Find Transcription File

Response contains multiple files (report, transcription, etc.). Look for `kind: "Transcription"`.

```python
def download_transcript(api, transcription_id):
    """Download transcription JSON result."""
    # Get list of files
    pag_files = api.transcriptions_list_files(transcription_id)

    for file_data in pag_files.values:
        print(f"File: kind={file_data.kind}, name={file_data.name}")

        if file_data.kind == "Transcription":
            # Download transcription JSON
            results_url = file_data.links.content_url

            import requests
            response = requests.get(results_url, timeout=30)
            response.raise_for_status()

            transcript_json = response.content.decode('utf-8')
            return transcript_json

    raise Exception("No transcription file found")

# Usage
transcript_json = download_transcript(api, transcription_id)
```

### 4.3 Parse JSON Result

```python
import json

transcript_data = json.loads(transcript_json)

# Access key fields
source_url = transcript_data["source"]
duration = transcript_data["duration"]
phrases = transcript_data["recognizedPhrases"]

print(f"Source: {source_url}")
print(f"Duration: {duration}")
print(f"Phrases: {len(phrases)}")
```

---

## Transcription Result Schema

### Top-Level Structure

```json
{
  "source": "https://mystorageaccount.blob.core.windows.net/recordings/file.mp3?...",
  "timestamp": "2025-01-21T14:38:12Z",
  "durationInTicks": 25063000000,
  "durationMilliseconds": 2506300.0,
  "duration": "PT41M46.3S",
  "combinedRecognizedPhrases": [...],
  "recognizedPhrases": [...]
}
```

**Fields:**
- `source`: Original blob URL
- `timestamp`: Processing completion time (ISO 8601)
- `duration`: Audio duration in ISO 8601 format
- `durationInTicks`: Duration in .NET ticks (10,000 ticks = 1 ms)
- `durationMilliseconds`: Duration in milliseconds
- `combinedRecognizedPhrases`: Full transcript per channel (no speaker info)
- `recognizedPhrases`: **Main data** - array of phrases with speaker labels

### Recognized Phrases Array

Each phrase represents a segment of speech from one speaker:

```json
{
  "recognitionStatus": "Success",
  "channel": 0,
  "speaker": 1,
  "offset": "PT0S",
  "duration": "PT15.5S",
  "offsetInTicks": 0,
  "durationInTicks": 155000000,
  "nBest": [
    {
      "confidence": 0.92847656,
      "lexical": "are two kind of similar but slightly different project ideas",
      "itn": "are 2 kind of similar but slightly different project ideas",
      "maskedITN": "are 2 kind of similar but slightly different project ideas",
      "display": "Are two kind of similar but slightly different project ideas.",
      "words": [
        {
          "word": "are",
          "offset": "PT0.32S",
          "duration": "PT0.08S",
          "offsetInTicks": 3200000,
          "durationInTicks": 800000,
          "confidence": 0.9648438
        },
        ...
      ]
    }
  ]
}
```

### Phrase-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `recognitionStatus` | string | `Success`, `NoMatch`, `InitialSilenceTimeout`, `BabbleTimeout`, `Error` |
| `channel` | integer | Audio channel (0-indexed) |
| `speaker` | integer | Speaker ID (1-indexed, e.g., 1, 2, 3...) |
| `offset` | string | Start time in ISO 8601 duration format |
| `duration` | string | Phrase duration in ISO 8601 format |
| `offsetInTicks` | integer | Start time in .NET ticks |
| `durationInTicks` | integer | Duration in .NET ticks |
| `nBest` | array | Recognition alternatives (sorted by confidence) |

### nBest Array (Recognition Results)

The `nBest` array contains recognition alternatives. The first element (`nBest[0]`) is the highest-confidence result:

| Field | Type | Description |
|-------|------|-------------|
| `confidence` | float | Confidence score (0.0 to 1.0) |
| `lexical` | string | Lexical form (lowercase, no punctuation) |
| `itn` | string | Inverse Text Normalization (numbers as digits) |
| `maskedITN` | string | ITN with profanity masked |
| `display` | string | **Display text** - properly capitalized with punctuation |
| `words` | array | Word-level timestamps and confidence |

**Use `display` for user-facing transcripts.**

### Word-Level Data

Each word in the `words` array:

```json
{
  "word": "project",
  "offset": "PT12.5S",
  "duration": "PT0.44S",
  "offsetInTicks": 125000000,
  "durationInTicks": 4400000,
  "confidence": 0.9765625
}
```

---

## Code Examples

### Complete End-to-End Example

```python
#!/usr/bin/env python3
"""
Complete Azure Speech Services transcription workflow.
"""
import os
import json
import time
import ffmpeg
import requests
import azure_speech_client
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta, UTC

# Configuration
SUBSCRIPTION_KEY = os.getenv("AZURE_SPEECH_SUBSCRIPTION_KEY")
REGION = os.getenv("AZURE_SPEECH_REGION", "westus2")
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "audio-files"

def transcode_mp3(input_file, output_file):
    """Transcode MP3 to standard format."""
    print(f"Transcoding {input_file}...")
    (
        ffmpeg
        .input(input_file)
        .output(output_file, acodec='libmp3lame', audio_bitrate='128k')
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )
    print(f"Transcoded to {output_file}")

def upload_to_blob(file_path, blob_name):
    """Upload file to Azure Blob Storage and return SAS URL."""
    print(f"Uploading {file_path} to blob storage...")

    blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Upload
    with open(file_path, "rb") as data:
        container_client.upload_blob(name=blob_name, data=data, overwrite=True)

    # Generate SAS URL
    account_name = blob_service_client.account_name
    account_key = blob_service_client.credential.account_key

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(UTC) + timedelta(hours=48)
    )

    blob_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}?{sas_token}"
    print(f"Uploaded: {blob_url[:80]}...")
    return blob_url

def submit_transcription(blob_url, display_name):
    """Submit transcription job to Azure Speech Services."""
    print(f"Submitting transcription job: {display_name}")

    # Configure API client
    configuration = azure_speech_client.Configuration()
    configuration.api_key["Ocp-Apim-Subscription-Key"] = SUBSCRIPTION_KEY
    configuration.host = f"https://{REGION}.api.cognitive.microsoft.com/speechtotext/v3.2"
    api_client = azure_speech_client.ApiClient(configuration)
    api = azure_speech_client.CustomSpeechTranscriptionsApi(api_client)

    # Create transcription properties
    properties = azure_speech_client.TranscriptionProperties()
    properties.punctuation_mode = "DictatedAndAutomatic"
    properties.diarization_enabled = True
    properties.diarization = azure_speech_client.DiarizationProperties(
        azure_speech_client.DiarizationSpeakersProperties(min_count=1, max_count=5)
    )

    # Submit transcription
    transcription_definition = azure_speech_client.Transcription(
        display_name=display_name,
        description=f"Transcription started at {datetime.now(UTC).isoformat()}",
        locale="en-US",
        content_urls=[blob_url],
        properties=properties
    )

    created_transcription, status, headers = api.transcriptions_create_with_http_info(
        transcription=transcription_definition
    )

    transcription_id = headers["location"].split("/")[-1]
    print(f"Transcription ID: {transcription_id}")
    return api, transcription_id

def poll_transcription(api, transcription_id):
    """Poll until transcription completes."""
    print("Polling for completion...")

    while True:
        transcription = api.transcriptions_get(transcription_id)
        status = transcription.status

        print(f"  Status: {status}")

        if status == "Succeeded":
            print("✓ Transcription completed!")
            return transcription
        elif status == "Failed":
            error = transcription.properties.error if transcription.properties else None
            error_msg = f"{error.code}: {error.message}" if error else "Unknown error"
            raise Exception(f"Transcription failed: {error_msg}")
        elif status in ["NotStarted", "Running"]:
            time.sleep(30)
        else:
            raise Exception(f"Unknown status: {status}")

def download_transcript(api, transcription_id):
    """Download transcription JSON."""
    print("Downloading transcript...")

    pag_files = api.transcriptions_list_files(transcription_id)

    for file_data in pag_files.values:
        if file_data.kind == "Transcription":
            results_url = file_data.links.content_url
            response = requests.get(results_url, timeout=30)
            response.raise_for_status()

            transcript_json = response.content.decode('utf-8')
            print(f"Downloaded {len(transcript_json)} characters")
            return transcript_json

    raise Exception("No transcription file found")

def generate_diarized_transcript(transcript_json):
    """Generate human-readable diarized transcript."""
    data = json.loads(transcript_json)
    transcript_lines = []
    last_speaker = None
    last_text = []

    for phrase in data.get("recognizedPhrases", []):
        speaker = phrase.get("speaker")
        text = phrase.get("nBest", [{}])[0].get("display", "")

        if speaker == last_speaker:
            last_text.append(text)
        else:
            if last_text:
                transcript_lines.append(f"Speaker {last_speaker}: {' '.join(last_text)}")
            last_speaker = speaker
            last_text = [text]

    if last_text:
        transcript_lines.append(f"Speaker {last_speaker}: {' '.join(last_text)}")

    return "\n\n".join(transcript_lines)

def main():
    """Main transcription workflow."""
    # Input file
    input_file = "recording.mp3"

    # Step 1: Transcode
    transcoded_file = "recording_transcoded.mp3"
    transcode_mp3(input_file, transcoded_file)

    # Step 2: Upload to blob
    blob_name = f"transcriptions/{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.mp3"
    blob_url = upload_to_blob(transcoded_file, blob_name)

    # Step 3: Submit transcription
    api, transcription_id = submit_transcription(blob_url, "My Recording")

    # Step 4: Poll for completion
    transcription = poll_transcription(api, transcription_id)

    # Step 5: Download results
    transcript_json = download_transcript(api, transcription_id)

    # Step 6: Generate readable transcript
    diarized_transcript = generate_diarized_transcript(transcript_json)

    # Save results
    with open("transcript.json", "w") as f:
        f.write(transcript_json)

    with open("transcript.txt", "w") as f:
        f.write(diarized_transcript)

    print("\n" + "="*60)
    print("TRANSCRIPTION COMPLETE")
    print("="*60)
    print(diarized_transcript[:500] + "...")
    print("\nFull results saved to transcript.json and transcript.txt")

if __name__ == "__main__":
    main()
```

### Batch Processing Multiple Files

```python
def batch_transcode_and_upload(input_dir, output_dir):
    """Process multiple MP3 files."""
    import glob

    mp3_files = glob.glob(os.path.join(input_dir, "*.mp3"))
    print(f"Found {len(mp3_files)} MP3 files")

    jobs = []

    for input_file in mp3_files:
        filename = os.path.basename(input_file)
        transcoded_file = os.path.join(output_dir, filename)

        # Transcode
        transcode_mp3(input_file, transcoded_file)

        # Upload
        blob_name = f"batch/{filename}"
        blob_url = upload_to_blob(transcoded_file, blob_name)

        # Submit
        api, transcription_id = submit_transcription(blob_url, filename)

        jobs.append({
            "filename": filename,
            "transcription_id": transcription_id,
            "api": api
        })

    print(f"\nSubmitted {len(jobs)} transcription jobs")

    # Poll all jobs
    for job in jobs:
        print(f"\nProcessing {job['filename']}...")
        transcription = poll_transcription(job["api"], job["transcription_id"])
        transcript_json = download_transcript(job["api"], job["transcription_id"])

        # Save
        output_file = os.path.join(output_dir, f"{job['filename']}.json")
        with open(output_file, "w") as f:
            f.write(transcript_json)

        print(f"Saved to {output_file}")
```

---

## Troubleshooting

### Common Errors

#### 1. "InvalidAudioFormat" or "UnsupportedAudioFormat"

**Cause:** Audio file not properly encoded or corrupted.

**Solution:**
```bash
# Always transcode with FFmpeg
ffmpeg -i input.mp3 -acodec libmp3lame -b:a 128k output.mp3
```

#### 2. "ContentUrlInvalid" or "403 Forbidden"

**Cause:** SAS URL expired, missing permissions, or blob not accessible.

**Solution:**
```python
# Ensure SAS URL has:
# - Read permission (sp=r)
# - Future expiry (se=2025-...)
# - HTTPS protocol

# Regenerate SAS URL with longer expiry
sas_token = generate_blob_sas(
    account_name=account_name,
    container_name=container_name,
    blob_name=blob_name,
    account_key=account_key,
    permission=BlobSasPermissions(read=True),
    expiry=datetime.now(UTC) + timedelta(hours=48)  # 48 hours
)
```

#### 3. "FileTooLarge" or Timeout Errors

**Cause:** File exceeds size/duration limits.

**Solution:** Chunk the file (see [Audio File Preparation](#audio-file-preparation)).

#### 4. Transcription Stuck in "NotStarted"

**Cause:** Azure service backlog or quota limits.

**Solution:**
- Check Azure Portal → Speech Services → Metrics for throttling
- Increase polling interval to reduce API calls
- Verify subscription quota hasn't been exceeded

#### 5. No Speaker Diarization in Results

**Cause:** Diarization not enabled or audio quality too poor.

**Solution:**
```python
# Ensure diarization is enabled
properties.diarization_enabled = True
properties.diarization = azure_speech_client.DiarizationProperties(
    azure_speech_client.DiarizationSpeakersProperties(min_count=1, max_count=5)
)

# Check if audio has clear speakers (background noise affects accuracy)
```

#### 6. Low Confidence Scores

**Cause:** Poor audio quality, background noise, accents.

**Solution:**
- Use higher bitrate: `-b:a 192k` instead of 128k
- Noise reduction (FFmpeg):
  ```bash
  ffmpeg -i input.mp3 -af "highpass=f=200,lowpass=f=3000" output.mp3
  ```
- Consider custom speech models for domain-specific vocabulary

---

## Best Practices

1. **Always transcode** - Even if files are MP3, transcode for compatibility
2. **Use SAS URLs** - Generate with 48-hour expiry for safety margin
3. **Poll responsibly** - 30-60 second intervals to avoid throttling
4. **Handle failures gracefully** - Implement retry logic with exponential backoff
5. **Save raw JSON** - Keep original transcription JSON for future reprocessing
6. **Monitor costs** - Azure Speech Services charges per hour of audio processed
7. **Use batch API** - More cost-effective than real-time API for large files
8. **Test with small files** - Validate workflow with short recordings first
9. **Check quotas** - Monitor Azure subscription limits and request increases if needed
10. **Clean up jobs** - Delete old transcriptions to avoid hitting storage quotas

---

## Package Information

This guide uses the **azure-speech-client** package, a Python client for Azure Speech Services API v3.2.

### Installation

```bash
# Install from the python-client directory
pip install -e /path/to/azure_speech/python-client

# Or install the pre-built wheel
pip install /path/to/azure_speech/python-client/dist/azure_speech_client-3.2.0-py3-none-any.whl
```

### Package Details

- **Package name**: `azure-speech-client` (for pip)
- **Module name**: `azure_speech_client` (for import)
- **Version**: 3.2.0
- **API Version**: Azure Speech Services v3.2

For more information, see:
- `python-client/README.md` - Installation and usage
- `python-client/BUILD_GUIDE.md` - Build instructions
- `python-client/PACKAGE_INFO.md` - Package details

---

## References

- [Azure Speech Services Documentation](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/)
- [Batch Transcription API Reference](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-transcription)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Azure Blob Storage SDK](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python)

---

## Support

For issues or questions:
- Azure Speech Services: [Azure Support Portal](https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade)
- FFmpeg: [FFmpeg Community](https://ffmpeg.org/contact.html)
- This codebase: See `plaud_sync_service/SYSTEM_DESCRIPTION.md` for implementation details
