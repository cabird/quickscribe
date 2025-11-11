# Plaud Sync Service

Azure Functions-based service for automated Plaud recording synchronization, transcoding, and transcription submission.

## Overview

This service replaces the previous queue-based transcoder container with a scheduled, observable job orchestrator that:

- **Runs automatically every 15 minutes** (timer trigger)
- **Can be triggered manually** via HTTP endpoint (from frontend or API)
- **Checks pending transcriptions** and updates completed ones
- **Fetches new Plaud recordings** for all users
- **Downloads, transcodes, and uploads** audio files
- **Submits to Azure Speech Services** for transcription
- **Handles large files** by automatically chunking (>300MB or >2 hours)
- **Tracks all execution** with full logs stored in Cosmos DB
- **Manages failures** with auto-retry (up to 3 attempts) and manual review queue

## Architecture

### Components

1. **function_app.py** - Azure Functions entry point with timer and HTTP triggers
2. **job_executor.py** - Main orchestration logic
3. **transcription_poller.py** - Checks Azure Speech Services status
4. **plaud_processor.py** - Downloads, transcodes, chunks, and submits recordings
5. **logging_handler.py** - Dual logging (stdout + Cosmos DB)

### Data Models

New models added to `shared/Models.ts`:

- **JobExecution** - Tracks each sync run with logs and statistics
- **ManualReviewItem** - Queue for recordings that failed 3+ times
- **FailureRecord** - Individual failure tracking
- **JobLogEntry** - Log entries for job execution
- **JobExecutionStats** - Statistics summary

### Execution Flow

```
Timer/HTTP Trigger
    ↓
1. Check for concurrent jobs (locking)
2. Create JobExecution record (status: running)
3. For each user with Plaud sync:
    a. Check pending transcriptions
       → Poll Azure Speech Services
       → Update completed transcriptions
    b. Fetch new Plaud recordings
       → Download from Plaud
       → Check if chunking needed (>300MB or >2hr)
       → Transcode to MP3
       → Upload to Azure Blob Storage
       → Submit to Azure Speech Services
       → Create Recording in Cosmos DB
4. Update JobExecution (status: completed, logs, stats)
```

## Prerequisites

### Local Development

1. **Azure Functions Core Tools** (v4.x)
   ```bash
   npm install -g azure-functions-core-tools@4
   ```

2. **FFmpeg** (for audio transcoding)
   ```bash
   # Linux
   sudo apt-get install ffmpeg

   # macOS
   brew install ffmpeg
   ```

3. **Python 3.11+** with virtual environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Shared QuickScribe Library**
   ```bash
   cd ../shared_quickscribe_py
   pip install -e .
   ```

### Azure Services

- Azure Cosmos DB (for recordings, users, transcriptions, job executions)
- Azure Blob Storage (for audio files)
- Azure Speech Services (for transcription)
- Azure Application Insights (for monitoring)

## Configuration

### Local Settings

Copy `local.settings.json.example` to `local.settings.json` and configure:

```json
{
  "Values": {
    "AZURE_COSMOS_ENDPOINT": "https://your-cosmos.documents.azure.com:443/",
    "AZURE_COSMOS_KEY": "your-key",
    "COSMOS_DB_NAME": "quickscribe",
    "COSMOS_CONTAINER_NAME": "recordings",
    "AZURE_STORAGE_CONNECTION_STRING": "your-connection-string",
    "AZURE_STORAGE_CONTAINER_NAME": "recordings",
    "AZURE_SPEECH_SERVICES_KEY": "your-key",
    "AZURE_SPEECH_SERVICES_REGION": "westus2",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "your-connection-string"
  }
}
```

## Local Testing

### Quick Start

```bash
# Run the test script
./test_local.sh
```

This will:
1. Check prerequisites
2. Install dependencies
3. Start Azure Functions runtime
4. Make endpoints available at http://localhost:7071

### Manual Testing

```bash
# Health check
curl http://localhost:7071/api/health

# Trigger sync for all users
curl -X POST http://localhost:7071/api/sync/trigger

# Trigger sync for specific user
curl -X POST 'http://localhost:7071/api/sync/trigger?user_id=<USER_ID>'
```

### Running with Docker

```bash
# Build image
docker build -t plaud-sync-service .

# Run container
docker run -p 7071:80 --env-file local.settings.json plaud-sync-service
```

## Deployment

### Azure Container Registry

```bash
# Login to Azure
az login

# Build and push to ACR
az acr build --registry <your-registry> \
  --image plaud-sync-service:latest \
  --file Dockerfile .
```

### Azure Functions App

```bash
# Create Function App with container
az functionapp create \
  --resource-group QuickScribeResourceGroup \
  --name quickscribe-plaud-sync \
  --storage-account quickscribestorage \
  --plan QuickScribeAppServicePlan \
  --deployment-container-image-name <your-registry>.azurecr.io/plaud-sync-service:latest \
  --functions-version 4

# Configure app settings (environment variables)
az functionapp config appsettings set \
  --name quickscribe-plaud-sync \
  --resource-group QuickScribeResourceGroup \
  --settings @production.settings.json
```

## Monitoring

### Application Insights

All logs are sent to Application Insights. View in Azure Portal:
- Function executions
- Errors and exceptions
- Performance metrics
- Custom events

### Cosmos DB Queries

Query job executions:
```sql
-- Recent job executions
SELECT * FROM c
WHERE c.partitionKey = 'job_execution'
ORDER BY c.startTime DESC

-- Failed jobs
SELECT * FROM c
WHERE c.partitionKey = 'job_execution'
AND c.status = 'failed'

-- Manual review queue
SELECT * FROM c
WHERE c.needs_manual_review = true
```

## Error Handling

### Failure Retry Logic

- **Per-recording failures**: Logged but don't fail entire job
- **Auto-retry**: Failed recordings retry on next sync (up to 3 attempts)
- **Manual review**: After 3 failures, recording marked with `needs_manual_review = true`
- **Critical failures**: Plaud API auth errors, database unavailable → fail entire job

### Chunking Large Files

Files are automatically chunked if:
- Size > 300MB, OR
- Duration > 2 hours

Chunks are created as:
- Max 200MB per chunk
- Max 1.5 hours per chunk
- Each chunk is an independent Recording
- Title includes "Part X of Y"
- Timestamp adjusted for chunk offset

## Troubleshooting

### Common Issues

**1. FFmpeg not found**
```bash
# Install FFmpeg
sudo apt-get install ffmpeg  # Linux
brew install ffmpeg          # macOS
```

**2. shared_quickscribe_py not installed**
```bash
cd ../shared_quickscribe_py
pip install -e .
```

**3. Azure Functions Core Tools not found**
```bash
npm install -g azure-functions-core-tools@4
```

**4. Cosmos DB connection timeout**
- Check network connectivity
- Verify AZURE_COSMOS_ENDPOINT and AZURE_COSMOS_KEY
- Check Cosmos DB firewall rules

**5. Plaud API rate limiting**
- Service includes 5-second delay between downloads
- If still seeing rate limits, increase delay in plaud_processor.py

**6. Lock acquisition failure: "Lock already exists, cannot acquire"**
This error occurs when a distributed lock from a previous sync job hasn't been released. Common causes:
- Previous job crashed or was killed without releasing lock
- Stale lock from TTL not yet cleaned up by Cosmos DB

Diagnosis and fix:
```bash
# Check lock status
python manage_locks.py status

# Force release if lock is stale
python manage_locks.py force-release

# Run diagnostic to verify locking works
python diagnose_lock_issue.py
```

The lock has a 30-minute TTL and should auto-expire, but Cosmos DB's TTL cleanup can be delayed. Force-releasing a stale lock is safe if you're certain no other sync job is actually running.

### Debug Logging

Set `LOG_LEVEL=DEBUG` in local.settings.json for verbose logging.

## Development

### Running Tests

```bash
# Unit tests (TODO: implement)
pytest tests/

# Integration tests (TODO: implement)
pytest tests/integration/
```

### Code Structure

```
plaud_sync_service/
├── function_app.py           # Azure Functions entry point
├── job_executor.py           # Main orchestration
├── transcription_poller.py   # Azure Speech Services polling
├── plaud_processor.py        # Audio processing & chunking
├── logging_handler.py        # Dual logging handler
├── requirements.txt          # Python dependencies
├── host.json                 # Functions configuration
├── Dockerfile                # Container definition
├── local.settings.json       # Local config (gitignored)
├── test_local.sh            # Local testing script
└── README.md                 # This file
```

## Future Enhancements

- [ ] Implement proper distributed locking for concurrent job prevention
- [ ] Add retry backoff strategy for transient failures
- [ ] Support for manual upload processing (not just Plaud)
- [ ] Real-time progress updates via SignalR
- [ ] Configurable chunking thresholds per user
- [ ] Admin UI for manual review queue
- [ ] Metrics dashboard in frontend
- [ ] Automated integration tests
- [ ] Support for additional transcription providers

## License

[License information to be added]
