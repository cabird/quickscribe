# QuickScribe Transcoder Container Architecture

<!-- Last updated for commit: 1f262a350a8810ff29c5898620c0b6d23a2161a7 -->

## Overview

The QuickScribe transcoder container is a focused microservice that processes Azure Storage Queue messages for audio transcoding and Plaud device synchronization. It's designed as a simple, stateless worker that can be scaled based on queue depth.

## Technology Stack

### Core Technologies
- **Python 3.11** - Runtime environment
- **FFmpeg** - Audio processing and transcoding
- **Azure Storage Queue** - Message-based job processing
- **Azure Storage Blob** - File download/upload operations
- **Docker** - Containerization

### Key Dependencies
- `azure-storage-queue` - Queue message processing
- `requests` - HTTP operations for file transfer and callbacks
- `python-dotenv` - Environment configuration

## Project Structure

```
transcoder_container/
├── main.py                    # Main queue processor and transcoding logic
├── plaud_sync.py             # Plaud device synchronization handling
├── container_app_version.py  # Version tracking
├── logging_setup.py          # Azure Application Insights logging
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container build configuration
├── Makefile                 # Build and deployment automation
├── container-app-python.yaml # Azure Container Apps configuration
├── container-job.yaml       # Azure Container Jobs configuration
└── env.local.template       # Environment template
```

## Core Architecture

### Message Processing Pipeline

**TranscodingProcessor Class** (`main.py`)

The main worker processes three types of messages from Azure Storage Queues:

1. **`test`** - Health check and connectivity validation
2. **`transcode`** - Audio file conversion to MP3 format
3. **`plaud_sync`** - Plaud device recording synchronization

### Message Types

**Test Action**
```json
{
    "action": "test",
    "content": "test_payload",
    "callbacks": [{"url": "callback_url", "token": "auth_token"}]
}
```

**Transcode Action**
```json
{
    "action": "transcode",
    "recording_id": "uuid",
    "source_sas_url": "https://storage.blob.core.windows.net/...",
    "target_sas_url": "https://storage.blob.core.windows.net/...",
    "original_filename": "audio.m4a",
    "user_id": "user_uuid",
    "callbacks": [{"url": "callback_url", "token": "auth_token"}]
}
```

**Plaud Sync Action**
```json
{
    "action": "plaud_sync",
    "user_id": "user_uuid",
    "plaud_token": "api_token",
    "last_sync_timestamp": "ISO_datetime",
    "callbacks": [{"url": "callback_url", "token": "auth_token"}]
}
```

## Audio Processing

### FFmpeg Integration

The transcoder uses FFmpeg for audio conversion with specific parameters:

```python
def convert_to_mp3(self, source_file_path: str, target_file_path: str) -> None:
    cmd = [
        'ffmpeg', '-i', source_file_path,
        '-c:a', 'libmp3lame',  # MP3 encoder
        '-q:a', '2',           # Quality level 2 (good quality)
        '-ac', '1',            # Mono output
        '-ar', '44100',        # 44.1kHz sample rate
        target_file_path, '-y' # Overwrite output
    ]
```

**Supported Input Formats**: MP3, M4A  
**Output Format**: MP3 (mono, 44.1kHz, quality level 2)

### Metadata Extraction

Uses `ffprobe` to extract audio file information:

- Duration (seconds)
- File size (bytes)
- Format name
- Bitrate
- Codec information

## Processing Workflow

### Transcode Workflow

1. **Message Receipt** - Parse queue message with file URLs and metadata
2. **Download** - Fetch source audio file from Azure Blob using SAS URL
3. **Validation** - Check file format and extract metadata
4. **Transcoding** - Convert to MP3 using FFmpeg
5. **Upload** - Upload processed file to target blob location
6. **Callback** - Notify backend of completion with metadata
7. **Cleanup** - Remove temporary files

### Error Handling

- **Timeout Protection** - 30-minute processing limit
- **Format Validation** - Only MP3/M4A input files accepted
- **Callback Delivery** - HTTP callbacks with retry logic
- **Temporary File Cleanup** - Automatic cleanup in finally blocks

### Callback System

**Success Callback**
```json
{
    "action": "transcode",
    "recording_id": "uuid",
    "status": "completed",
    "container_version": "0.1.35",
    "processing_time": 12.34,
    "input_metadata": {...},
    "output_metadata": {...}
}
```

**Error Callback**
```json
{
    "action": "transcode",
    "recording_id": "uuid", 
    "status": "failed",
    "container_version": "0.1.35",
    "error_message": "Error description",
    "traceback": "Python stack trace"
}
```

## Plaud Integration

### AudioFile Data Structure

The `plaud_sync.py` module defines an `AudioFile` dataclass representing Plaud recordings:

```python
@dataclass
class AudioFile:
    id: str
    filename: str
    filesize: int
    filetype: str
    duration: int  # milliseconds
    start_time: int
    end_time: int
    timezone: int
    zonemins: int
    # ... additional metadata fields
```

### Plaud Processing with Progress Monitoring

**Enhanced Sync Workflow** (`handle_plaud_sync` function):

1. **Initialization**
   - Validates bearer token and sync parameters
   - Sends initial `in_progress` callback to backend
   - Creates temporary processing directory

2. **Recording Discovery**
   - Fetches recordings list from Plaud API
   - Filters by processed IDs and last sync timestamp  
   - Sends progress update with `total_recordings_found`

3. **Per-Recording Processing** (with detailed callbacks)
   ```python
   for recording in new_recordings:
       # Download from Plaud
       downloaded_path = plaud_manager.download_file(recording)
       
       # Transcode to MP3
       transcode_func(downloaded_path, mp3_output_path)
       
       # Register with backend (get SAS URL)
       registration_response = requests.post(callback_url, {
           "action": "register_plaud_recording",
           "plaud_id": recording.id,
           "original_filename": recording.filename,
           # ... metadata
       })
       
       # Upload to blob storage
       requests.put(sas_url, mp3_file_data)
       
       # Send success callback
       send_callbacks_func(callbacks, {
           "status": "recording_processed",
           "plaud_id": recording.id,
           "recording_id": recording_id,
           "filename": recording.filename,
           "processing_time": elapsed_time
       })
   ```

4. **Error Handling & Progress Updates**
   - Individual recording failures send `recording_failed` callbacks
   - Includes specific error messages and filename
   - Continues processing remaining recordings
   - Rate limiting: 60-second delays between recordings

5. **Completion Summary**
   - Sends final `completed` callback with statistics
   - Includes total processed, failed count, processing time
   - Comprehensive error list for failed recordings

**Progress Callback Types:**
- `in_progress` - Initial sync start + total count updates
- `recording_processed` - Per-recording success with metadata
- `recording_failed` - Per-recording errors with details
- `completed` - Final summary with statistics
- `failed` - Overall operation failure

**Timeout & Recovery:**
- 60-second rate limiting prevents API abuse
- Individual file download/processing timeouts
- Comprehensive error logging and callback delivery
- Handles network interruptions gracefully

## Container Deployment

### Dockerfile Configuration

Simple multi-layer build:

1. **Base**: Python 3.11 slim image
2. **System Dependencies**: FFmpeg installation
3. **Python Dependencies**: Requirements installation
4. **Application Code**: Copy source files
5. **Runtime**: Execute `main.py`

### Environment Configuration

**Required Variables**:
- `AZURE_STORAGE_CONNECTION_STRING` - Azure Storage access
- `TRANSCODING_QUEUE_NAME` - Queue name for message processing

**Optional Variables**:
- `ENVIRONMENT` - Deployment environment (`local` vs production)
- Logging and monitoring configuration

## Execution Modes

### Production Mode
- Single queue processing run
- Processes all available messages and exits
- Suitable for Azure Container Jobs

### Development Mode (Local)
- Daemon mode with continuous polling
- 60-second sleep between processing cycles
- Automatic error recovery and restart

```python
def main():
    if os.environ.get('ENVIRONMENT') == "local":
        processor.run_as_daemon()  # Continuous polling
    else:
        processor.run()            # Single run
```

## Logging & Monitoring

### Azure Application Insights Integration

- Context-aware logging with recording/user IDs
- Performance metrics and timing data
- Error tracking with full stack traces
- Container version tracking

### Key Metrics Tracked

- Processing time per operation
- Success/failure rates
- File size and duration statistics
- Container version and instance information

## Auto-scaling Design

### Queue-based Scaling

The container is designed to work with Azure Container Apps auto-scaling:

- **Scale Trigger**: Azure Storage Queue depth
- **Scale Target**: Messages per instance ratio
- **Resource Limits**: CPU and memory constraints
- **Zero-scale**: Scales to zero when queue is empty

### Resource Efficiency

- **Stateless Design** - No persistent state between jobs
- **Temporary File Management** - Automatic cleanup prevents disk bloat
- **Memory Management** - Processes one file at a time
- **Quick Startup** - Minimal initialization for fast scaling

## Security & Best Practices

### Data Handling
- Uses SAS URLs for secure blob access
- Temporary files with restricted permissions
- No persistent storage of sensitive data
- Secure cleanup of processed files

### Error Resilience
- Comprehensive exception handling
- Timeout protection for long-running operations
- Graceful degradation on failures
- Detailed error reporting for debugging

## Future Considerations

### Potential Enhancements
- Support for additional audio formats
- Parallel processing of multiple files
- Advanced audio quality settings
- Real-time processing capabilities

### Scalability Improvements
- Batch processing optimization
- Enhanced memory management for large files
- Advanced retry and circuit breaker patterns
- Performance monitoring and optimization

---

This architecture provides a focused, reliable foundation for audio processing while maintaining simplicity and operational efficiency in a containerized microservice environment.