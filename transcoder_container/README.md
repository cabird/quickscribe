# QuickScribe Transcoder Container

A containerized audio processing service for the QuickScribe application, designed to handle audio transcoding, Plaud device synchronization, and Azure queue-based processing in a scalable microservice architecture.

## Features

✅ **Audio Processing Pipeline**
- Multi-format audio transcoding (MP3, M4A, WAV, OPUS)
- FFmpeg integration for high-quality audio conversion
- Automatic file format detection and optimization
- Progress tracking and error handling

✅ **Azure Queue Processing**
- Azure Storage Queue message consumption
- Reliable message processing with retry logic
- Dead letter queue handling for failed jobs
- Scalable worker pattern for concurrent processing

✅ **Plaud Device Integration**
- Automated device sync with rate limiting
- Recording download and metadata extraction
- Timezone-aware timestamp handling
- Error recovery and sync state management

✅ **Callback & Notification System**
- HTTP callback system for status updates
- Secure API key authentication
- Retry logic for failed notifications
- Comprehensive logging and monitoring

✅ **Container Deployment**
- Azure Container Apps/Jobs integration
- Auto-scaling based on queue depth
- Resource-efficient container design
- Health checks and monitoring endpoints

## Tech Stack

- **Python 3.11** - Modern Python runtime
- **FFmpeg** - Audio/video processing library
- **Azure SDK** - Queue and blob storage integration
- **Requests** - HTTP client for API communication
- **Azure Container Apps/Jobs** - Serverless container platform
- **Docker** - Containerization and deployment

## Getting Started

### Prerequisites
- Docker installed locally
- Azure subscription with configured services
- Access to QuickScribe backend API

### Local Development

```bash
cd transcoder_container

# Copy environment template
cp env.local.template .env

# Edit with your Azure credentials
# Required variables:
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection
AZURE_STORAGE_QUEUE_NAME=audio-processing-queue
CALLBACK_URL=http://localhost:5000/api/transcoder/callback
CALLBACK_API_KEY=your_api_key
```

### Building

```bash
# Build Docker image
make build

# Run locally
make run

# Run with custom environment
docker run --env-file .env quickscribe-transcoder
```

### Testing

```bash
# Send test message to queue
python send_test_message.py

# Test callback functionality
python test_callback.py

# Monitor processing logs
make logs
```

### Deployment

```bash
# Deploy to Azure Container Apps
make azure-deploy

# Deploy with version bump
make bump-deploy

# View deployment logs
make logs
```

## Architecture

### Directory Structure

```
transcoder_container/
├── main.py                    # Primary queue processing worker
├── plaud_sync.py             # Plaud device integration logic
├── container_app_version.py  # Version management
├── logging_setup.py          # Azure Application Insights integration
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container build configuration
├── Makefile                 # Build and deployment automation
│
├── container-app-python.yaml # Azure Container Apps configuration
├── container-job.yaml       # Azure Container Jobs configuration
├── deploy_simple.sh         # Deployment automation script
├── env.local.template       # Environment configuration template
│
├── send_test_message.py     # Queue testing utility
├── test_callback.py         # Callback testing utility
├── callback_testing_guide.md # Testing documentation
├── implementation_summary.md # Architecture overview
│
└── message_schemas.ts       # TypeScript message definitions
```

### Processing Workflows

**Audio Transcoding Workflow:**
1. Receive queue message with recording details
2. Download audio file from Azure Blob Storage
3. Analyze file format and encoding parameters
4. Transcode to optimized MP3 format using FFmpeg
5. Upload processed file back to blob storage
6. Send completion callback to backend API
7. Update processing status and cleanup temporary files

**Plaud Sync Workflow:**
1. Receive Plaud sync request from queue
2. Authenticate with Plaud API using stored credentials
3. Fetch new recordings since last sync timestamp
4. Download each recording with metadata extraction
5. Upload to blob storage with proper naming convention
6. Register recordings with backend via callback API
7. Update sync timestamp and status tracking

## Queue Message Processing

### Message Types

The transcoder processes different message types from Azure Storage Queues:

```python
# Audio Processing Message
{
    "action": "process_audio",
    "recording_id": "uuid",
    "blob_name": "recordings/user-id/audio.mp3",
    "user_id": "user-uuid",
    "callback_url": "https://api/transcoder/callback",
    "processing_options": {
        "target_format": "mp3",
        "quality": "high",
        "normalize_audio": true
    }
}

# Plaud Sync Message
{
    "action": "plaud_sync", 
    "user_id": "user-uuid",
    "plaud_token": "encrypted_token",
    "last_sync_timestamp": "2025-01-01T00:00:00Z",
    "callback_url": "https://api/plaud/callback"
}

# Test Message
{
    "action": "test",
    "test_data": "verification_payload"
}
```

### Error Handling & Retry Logic

```python
def process_queue_message(message, max_retries=3):
    """Process queue message with retry logic."""
    for attempt in range(max_retries + 1):
        try:
            result = handle_message(message)
            if result.success:
                delete_message(message)
                return result
        except TemporaryError as e:
            if attempt < max_retries:
                logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logger.error(f"Failed after {max_retries} retries: {e}")
                move_to_dead_letter_queue(message)
        except PermanentError as e:
            logger.error(f"Permanent failure: {e}")
            move_to_dead_letter_queue(message)
            break
```

## Audio Processing Engine

### FFmpeg Integration

**Audio Transcoding Pipeline:**
```python
def transcode_audio(input_path, output_path, target_format='mp3'):
    """Transcode audio using FFmpeg with optimized settings."""
    ffmpeg_cmd = [
        'ffmpeg', '-i', input_path,
        '-acodec', 'libmp3lame',      # MP3 encoder
        '-ab', '128k',                # 128kbps bitrate
        '-ar', '44100',               # 44.1kHz sample rate
        '-ac', '2',                   # Stereo output
        '-f', 'mp3',                  # Output format
        '-y',                         # Overwrite output
        output_path
    ]
    
    process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if process.returncode != 0:
        raise TranscodingError(f"FFmpeg failed: {process.stderr}")
    
    return get_audio_info(output_path)
```

**Audio Analysis & Optimization:**
```python
def analyze_audio_file(file_path):
    """Extract audio metadata and determine optimal processing."""
    probe_cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_format', '-show_streams',
        file_path
    ]
    
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    metadata = json.loads(result.stdout)
    
    audio_stream = next(s for s in metadata['streams'] if s['codec_type'] == 'audio')
    
    return {
        'duration': float(metadata['format']['duration']),
        'bitrate': int(metadata['format']['bit_rate']),
        'sample_rate': int(audio_stream['sample_rate']),
        'channels': int(audio_stream['channels']),
        'codec': audio_stream['codec_name']
    }
```

## Plaud Device Integration

### API Communication

**Authentication & Session Management:**
```python
class PlaudAPIClient:
    def __init__(self, api_token):
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'User-Agent': 'QuickScribe/1.0'
        })
    
    def get_recordings(self, since_timestamp=None):
        """Fetch recordings from Plaud API with pagination."""
        url = "https://api.plaud.ai/recordings"
        params = {'since': since_timestamp} if since_timestamp else {}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def download_recording(self, recording_id, output_path):
        """Download recording file with progress tracking."""
        url = f"https://api.plaud.ai/recordings/{recording_id}/download"
        
        with self.session.get(url, stream=True) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('Content-Length', 0))
            
            with open(output_path, 'wb') as file:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
                    downloaded += len(chunk)
                    progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                    logger.debug(f"Download progress: {progress:.1f}%")
        
        return output_path
```

### Sync State Management

**Timestamp Handling & Recovery:**
```python
def sync_plaud_recordings(user_id, plaud_token, last_sync_timestamp):
    """Sync Plaud recordings with comprehensive error handling."""
    client = PlaudAPIClient(plaud_token)
    sync_results = {
        'new_recordings': 0,
        'failed_downloads': 0,
        'sync_timestamp': last_sync_timestamp
    }
    
    try:
        # Fetch recordings since last sync
        recordings = client.get_recordings(since_timestamp=last_sync_timestamp)
        
        for recording in recordings:
            try:
                # Download and process each recording
                local_path = download_plaud_recording(client, recording)
                blob_name = upload_to_blob_storage(local_path, user_id, recording['id'])
                
                # Register with backend
                register_recording_with_backend(user_id, recording, blob_name)
                
                sync_results['new_recordings'] += 1
                sync_results['sync_timestamp'] = recording['created_at']
                
            except Exception as e:
                logger.error(f"Failed to process recording {recording['id']}: {e}")
                sync_results['failed_downloads'] += 1
                continue
    
    except PlaudAPIError as e:
        logger.error(f"Plaud API error for user {user_id}: {e}")
        raise
    
    return sync_results
```

## Deployment Architecture

### Azure Container Apps Configuration

**Container Apps Deployment** (`container-app-python.yaml`):
```yaml
properties:
  configuration:
    secrets:
      - name: storage-connection-string
        value: "Azure Storage connection string"
      - name: callback-api-key
        value: "API authentication key"
    
    registries:
      - server: quickscribecontainerregistry.azurecr.io
        identity: system
    
  template:
    containers:
      - image: quickscribecontainerregistry.azurecr.io/quickscribe-transcoder:latest
        name: transcoder
        resources:
          cpu: 1.0
          memory: 2Gi
        env:
          - name: AZURE_STORAGE_CONNECTION_STRING
            secretRef: storage-connection-string
          - name: CALLBACK_API_KEY
            secretRef: callback-api-key
    
    scale:
      minReplicas: 0
      maxReplicas: 10
      rules:
        - name: queue-scaling
          azureQueue:
            queueName: audio-processing-queue
            queueLength: 5
            auth:
              secretRef: storage-connection-string
```

**Container Jobs for Batch Processing:**
```yaml
properties:
  configuration:
    triggerType: Event
    eventTriggerConfig:
      scale:
        minExecutions: 0
        maxExecutions: 10
        pollingInterval: 30
        rules:
          - name: queue-trigger
            type: azure-queue
            metadata:
              queueName: audio-processing-queue
              queueLength: "1"
              connectionFromEnv: AZURE_STORAGE_CONNECTION_STRING
```

### Automated Deployment Pipeline

**Deployment Script** (`deploy_simple.sh`):
```bash
#!/bin/bash
set -e

# Version management
VERSION=$(python -c "from container_app_version import CONTAINER_APP_VERSION; print(CONTAINER_APP_VERSION)")
IMAGE_NAME="quickscribe-transcoder:$VERSION"

# Build and push container
docker build -t $IMAGE_NAME .
docker tag $IMAGE_NAME quickscribecontainerregistry.azurecr.io/$IMAGE_NAME
docker push quickscribecontainerregistry.azurecr.io/$IMAGE_NAME

# Deploy to Azure Container Apps
az containerapp update \
  --name quickscribe-transcoder \
  --resource-group quickscribe-rg \
  --image quickscribecontainerregistry.azurecr.io/$IMAGE_NAME

echo "Deployed version $VERSION successfully"
```

## Monitoring & Observability

### Logging Configuration

**Azure Application Insights Integration:**
```python
# logging_setup.py
import logging
from azure.monitor.opentelemetry import configure_azure_monitor

def setup_azure_logging():
    """Configure Application Insights telemetry."""
    configure_azure_monitor(
        connection_string=os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
    )
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Add custom attributes to all logs
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            AzureLogHandler()
        ]
    )
    
    return logger
```

**Custom Metrics & Telemetry:**
```python
def track_processing_metrics(processing_time, file_size, success=True):
    """Track custom metrics for monitoring."""
    telemetry_client.track_metric('ProcessingTime', processing_time)
    telemetry_client.track_metric('FileSizeProcessed', file_size)
    telemetry_client.track_metric('ProcessingSuccess', 1 if success else 0)
    
    telemetry_client.track_event('AudioProcessed', {
        'duration_seconds': processing_time,
        'file_size_mb': file_size / (1024 * 1024),
        'success': success
    })
```

### Health Checks & Monitoring

**Container Health Monitoring:**
```python
@app.route('/health')
def health_check():
    """Health check endpoint for container orchestration."""
    checks = {
        'storage_connection': test_storage_connection(),
        'queue_access': test_queue_access(),
        'ffmpeg_available': test_ffmpeg_installation(),
        'disk_space': check_disk_space()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return jsonify({
        'status': 'healthy' if all_healthy else 'unhealthy',
        'checks': checks,
        'version': CONTAINER_APP_VERSION
    }), status_code
```

## Performance & Scalability

### Resource Optimization

**Memory Management:**
- Streaming file processing to minimize memory usage
- Temporary file cleanup after processing
- Efficient blob storage operations with chunked uploads
- Connection pooling for HTTP requests

**CPU Optimization:**
- FFmpeg hardware acceleration when available
- Parallel processing for multiple queue messages
- Optimized container resource allocation
- Efficient audio processing algorithms

### Auto-scaling Configuration

**Queue-based Scaling:**
- Scale up when queue depth > 5 messages
- Scale down to zero when queue is empty
- Maximum 10 concurrent instances
- 30-second polling interval for responsive scaling

**Performance Metrics:**
- Average processing time per audio file
- Queue throughput and backlog monitoring
- Resource utilization tracking
- Error rate and retry statistics

## Security & Best Practices

### Secure Communication
- HTTPS-only API communication
- API key authentication for callbacks
- Secure environment variable management
- Azure Managed Identity for service authentication

### Data Protection
- Temporary file encryption during processing
- Secure deletion of local files after processing
- Audit logging for all file operations
- Access control for blob storage operations

## Future Enhancements

### Advanced Processing Features
- Real-time audio streaming processing
- Advanced audio enhancement algorithms
- Multiple output format support
- Batch processing optimization

### Integration Improvements
- WebSocket support for real-time updates
- Advanced retry and circuit breaker patterns
- Enhanced monitoring and alerting
- Performance optimization with caching

### Scalability Enhancements
- Multi-region deployment support
- Advanced load balancing strategies
- Optimized resource allocation
- Cost optimization with spot instances

The transcoder container provides a robust, scalable foundation for audio processing while maintaining security, performance, and reliability standards essential for production microservice architectures.