# QuickScribe Backend Architecture

<!-- Last updated for commit: 0b5c14dba1691c16fd9cfef10ae6bccfd3490170 -->

## Overview

This document describes the complete architecture of the QuickScribe backend, a Flask-based API server that handles audio transcription processing, user management, and Azure services integration. The backend follows microservices principles with clean separation of concerns and scalable cloud-native design.

## Technology Stack

### Core Technologies
- **Flask** - Lightweight Python web framework with blueprint routing
- **Pydantic** - Data validation and serialization with type safety
- **Azure SDK for Python** - Comprehensive cloud services integration
- **Gunicorn** - Production WSGI HTTP server with multi-worker support
- **Python 3.11** - Modern Python with enhanced type hints and performance

### Azure Services Integration
- **Azure Cosmos DB** - NoSQL document database with global distribution
- **Azure Blob Storage** - Scalable object storage for audio files
- **Azure Speech Services** - AI-powered transcription with speaker diarization
- **Azure Storage Queues** - Asynchronous message processing
- **Azure OpenAI** - GPT-based AI analysis and content processing
- **Azure Application Insights** - Telemetry and performance monitoring
- **Azure Active Directory** - Enterprise authentication and authorization

### Development & Operations
- **Docker** - Containerization for consistent deployment
- **Pytest** - Comprehensive testing framework with fixtures
- **Azure CLI** - Deployment automation and resource management
- **Make** - Build automation and task management

## Project Structure

```
backend/
├── app.py                          # Flask application entry point and configuration
├── startup.sh                     # Container startup script with environment detection
├── config.py                      # Configuration management with environment detection
├── requirements.txt               # Python dependencies with version pinning
├── Dockerfile                     # Multi-stage container build configuration
├── Makefile                       # Build automation and deployment tasks
├── pytest.ini                     # Test configuration and pytest settings
│
├── db_handlers/                   # Data access layer with handler pattern
│   ├── __init__.py               # Package initialization
│   ├── models.py                 # Auto-generated Pydantic models (from TypeScript)
│   ├── handler_factory.py       # Singleton handler creation with request context
│   ├── user_handler.py          # User CRUD operations with extended models
│   ├── recording_handler.py     # Recording management with migration support
│   ├── transcription_handler.py # Transcription data with speaker mapping
│   ├── sync_progress_handler.py # Progress tracking for long-running operations
│   ├── analysis_type_handler.py # Dynamic AI analysis types and results management
│   └── util.py                  # Database utility functions and field filtering
│
├── routes/                       # API blueprints with modular routing
│   ├── api.py                   # Main REST API endpoints for core functionality
│   ├── ai_routes.py             # AI analysis endpoints with OpenAI integration
│   ├── az_transcription_routes.py # Azure Speech Services integration
│   ├── plaud.py                 # Plaud device sync and webhook handling
│   └── local_routes.py          # Development-only authentication and utilities
│
├── tests/                       # Comprehensive test suite with multiple layers
│   ├── conftest.py             # Pytest configuration and shared fixtures
│   ├── unit/                   # Unit tests for individual components
│   │   └── test_user_handler.py # Database handler unit tests
│   ├── integration/            # API endpoint integration tests
│   │   └── test_api_endpoints.py # Route testing with mock dependencies
│   ├── e2e/                    # End-to-end workflow tests
│   │   └── test_complete_workflows.py # Full user journey testing
│   └── fixtures/               # Test utilities and data factories
│       └── test_utils.py       # Shared test helper functions
│
├── templates/                  # Jinja2 templates for web interface
│   ├── base.html              # Base template with common layout
│   ├── index.html             # Landing page template
│   ├── recordings.html        # Recording list interface
│   ├── upload.html            # File upload interface
│   └── view_transcription.html # Transcription display template
│
├── static/                     # Static assets for web interface
│   └── styles.css             # CSS styling for templates
│
├── frontend-dist/              # Built frontend assets (deployment target)
├── azure_speech/              # Azure Speech Services Python SDK
├── local_packages/            # Local Python package dependencies
│
├── auth.py                    # Azure AD authentication with MSAL integration
├── blob_util.py              # Azure Blob Storage operations and SAS tokens
├── llms.py                   # Azure OpenAI integration with async infrastructure
├── ai_postprocessing.py      # AI post-processing orchestration (title, description, speakers)
├── user_util.py              # User session management and resolution
├── util.py                   # General utility functions and helpers
├── logging_config.py         # Centralized logging with Application Insights
├── manage.py                 # CLI management tools for administration
├── prompts.yaml              # AI prompt templates for post-processing
│
├── deploy-to-azure.sh        # Azure deployment automation script
├── deploy-local.sh           # Local deployment testing script
├── startup.sh                # Container startup with environment detection
└── run_tests.py              # Test runner with category support
```

## Core Architecture Patterns

### Handler Pattern for Data Access

**handler_factory.py** - Centralized handler creation
- Singleton pattern within Flask request context
- Automatic dependency injection for database connections
- Consistent configuration across all handlers
- Memory efficient with request-scoped caching

**Extended Model Pattern** - Enhanced Pydantic models
```python
class User(BaseUser):
    """Extended User model with datetime serialization."""
    
    @field_validator('created_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        # Handle ISO string → datetime conversion
        
    @field_serializer('created_at')
    def serialize_datetime(self, value) -> str:
        # Handle datetime → ISO string conversion
```

### Blueprint-based Routing Architecture

**Route Organization:**
- `api.py` - Core REST endpoints (`/api/*`)
- `ai_routes.py` - AI analysis endpoints (`/api/ai/*`)
- `az_transcription_routes.py` - Azure Speech Services (`/az_transcription/*`)
- `plaud.py` - Device integration (`/plaud/*`)
- `local_routes.py` - Development utilities (`/local/*`)

**Authentication Flow:**
```python
@api_bp.route('/recordings', methods=['GET'])
@require_auth  # Azure AD token validation
def get_recordings():
    user = get_current_user()  # Resolve from token
    handler = get_recording_handler()  # Factory pattern
    return handler.get_recordings_for_user(user.id)
```

### Microservices Communication

**Queue-based Processing:**
1. Frontend uploads audio → Backend stores in Blob Storage
2. Backend queues transcoding message → Azure Storage Queue
3. Transcoder processes audio → Converts and analyzes
4. Transcoder callbacks Backend → Status updates via webhook
5. Backend updates database → Frontend polls for completion

**Message Schema:**
```python
{
    "recording_id": "uuid",
    "blob_name": "audio_file.mp3",
    "user_id": "user_uuid",
    "callback_url": "https://api/transcoder/callback",
    "processing_options": {
        "speaker_diarization": true,
        "noise_reduction": false
    }
}
```

## Data Architecture

### Database Design (Azure Cosmos DB)

**Container Structure:**
- **users** (partition: `id`) - User profiles, settings, authentication
- **recordings** (partition: `userId`) - Audio metadata, processing status
- **transcripts** (partition: `userId`) - Transcription data, AI analysis
- **sync_progress** (partition: `partitionKey`) - Real-time progress tracking for long-running operations

**Document Examples:**
```json
// User Document
{
    "id": "user-uuid",
    "email": "user@example.com",
    "created_at": "2025-01-01T00:00:00Z",
    "plaudSettings": {
        "apiToken": "encrypted_token",
        "lastSyncTimestamp": "2025-01-01T12:00:00Z",
        "activeSyncStarted": null
    },
    "tags": [
        {"id": "tag-1", "name": "Meeting", "color": "#4DABF7"},
        {"id": "tag-2", "name": "Personal", "color": "#69DB7C"}
    ]
}

// Recording Document  
{
    "id": "recording-uuid",
    "userId": "user-uuid",
    "title": "Team Meeting Q1 Planning",
    "original_filename": "meeting_20250101.mp3",
    "blob_name": "recordings/user-uuid/recording-uuid.mp3",
    "duration": 3600,
    "transcription_status": "completed",
    "transcription_id": "transcript-uuid",
    "tagIds": ["tag-1"],
    "recorded_timestamp": "2025-01-01T09:00:00Z",
    "upload_timestamp": "2025-01-01T09:05:00Z",
    "source": "upload"
}

// Transcription Document
{
    "id": "transcript-uuid", 
    "userId": "user-uuid",
    "recording_id": "recording-uuid",
    "text": "Full transcription text...",
    "diarized_transcript": "Speaker 1: Hello everyone...",
    "speaker_mapping": {
        "Speaker 1": {"name": "John Doe", "confidence": 0.95},
        "Speaker 2": {"name": "Jane Smith", "confidence": 0.88}
    },
    "created_at": "2025-01-01T09:10:00Z"
}

// Sync Progress Document
{
    "id": "sync-token-uuid",
    "syncToken": "sync-token-uuid", 
    "userId": "user-uuid",
    "status": "processing",
    "totalRecordings": 15,
    "processedRecordings": 8,
    "failedRecordings": 1,
    "currentStep": "Processing recordings (8/15)",
    "errors": ["file1.mp3: Download failed - network timeout"],
    "startTime": "2025-01-01T10:00:00Z",
    "lastUpdate": "2025-01-01T10:05:30Z",
    "ttl": 1735732800,
    "partitionKey": "user-uuid"
}
```

### Model Synchronization System

**Shared Models Workflow:**
1. Edit `shared/Models.ts` (TypeScript source of truth)
2. Run `make build` in backend directory
3. Auto-generates `db_handlers/models.py` via datamodel-codegen
4. Manual copy to `frontend_new/src/types/index.ts`
5. Extended models in handlers add runtime behavior

**Type Safety Benefits:**
- Compile-time validation in TypeScript
- Runtime validation in Python with Pydantic
- Automatic serialization/deserialization
- API contract enforcement across services

## API Architecture

### Authentication & Authorization

**Azure AD Integration:**
```python
from msal import ConfidentialClientApplication

def validate_token(token):
    """Validate Azure AD JWT token."""
    app = ConfidentialClientApplication(
        client_id=config.AZURE_CLIENT_ID,
        client_credential=config.AZURE_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{config.AZURE_TENANT_ID}"
    )
    return app.acquire_token_silent(scopes=['user.read'], account=account)
```

**Local Development Support:**
```python
@local_bp.route('/login/<user_id>')
def local_login(user_id):
    """Development-only user switching."""
    if not config.LOCAL_AUTH_ENABLED:
        abort(404)
    session['user_id'] = user_id
    return redirect('/')
```

### Error Handling & Response Patterns

**Standardized API Responses:**
```python
class ApiResponse:
    def success(data=None, message=None):
        return {"status": "success", "data": data, "message": message}
    
    def error(error_msg, code=400):
        return {"status": "error", "error": error_msg}, code

# Usage in routes
@api_bp.route('/recordings', methods=['POST'])
def create_recording():
    try:
        recording = handler.create_recording(data)
        return ApiResponse.success(recording.dict(), "Recording created")
    except ValidationError as e:
        return ApiResponse.error(str(e), 400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return ApiResponse.error("Internal server error", 500)
```

### File Upload & Storage Architecture

**Multi-stage Upload Process:**
1. **Frontend Validation** - File type, size, format checking
2. **Backend Receiving** - Multipart form parsing with Flask
3. **Blob Storage Upload** - Azure SDK with progress tracking
4. **Database Recording** - Metadata storage with status tracking
5. **Queue Message** - Transcoding job creation
6. **Status Polling** - Real-time frontend updates

**Blob Storage Integration:**
```python
def upload_audio_file(file_data, user_id, recording_id):
    """Upload audio file to Azure Blob Storage."""
    blob_name = f"recordings/{user_id}/{recording_id}.{file_extension}"
    
    blob_client = get_blob_client(blob_name)
    blob_client.upload_blob(file_data, overwrite=True)
    
    # Generate SAS URL for transcoder access
    sas_url = generate_sas_url(blob_name, permissions=['read'])
    
    # Queue transcoding job
    queue_message = {
        "recording_id": recording_id,
        "blob_name": blob_name,
        "sas_url": sas_url,
        "callback_url": f"{config.BASE_URL}/transcoder/callback"
    }
    send_queue_message("audio-processing", queue_message)
```

## Progress Monitoring Architecture

### Real-Time Sync Progress System

The backend implements a comprehensive progress monitoring system for long-running operations like Plaud device synchronization, providing real-time visibility into processing status.

**Key Components:**
- **SyncProgressHandler** - Database operations for progress tracking
- **Progress API Endpoints** - REST endpoints for status polling and management
- **Multi-Device Recovery** - Cross-device sync state restoration
- **Timeout Management** - Automatic cleanup of stale operations

**Container: sync_progress**
```python
class SyncProgressHandler:
    def create_progress(self, sync_token, user_id, status='queued'):
        """Create new progress tracking record."""
        progress = SyncProgress(
            id=sync_token,
            syncToken=sync_token, 
            userId=user_id,
            status=status,
            processedRecordings=0,
            failedRecordings=0,
            currentStep="Initiating sync...",
            errors=[],
            startTime=datetime.now(UTC),
            ttl=int((datetime.now(UTC) + timedelta(hours=24)).timestamp())
        )
        return self._create_document(progress)
        
    def update_progress(self, sync_token, user_id, **updates):
        """Update progress with new status information."""
        updates['lastUpdate'] = datetime.now(UTC)
        return self._update_document(sync_token, updates)
```

**Progress API Endpoints:**
- `POST /plaud/sync/start` - Initialize sync with progress tracking
- `GET /plaud/sync/progress/{token}` - Poll current progress status  
- `GET /plaud/sync/check_active` - Check for active sync on app load
- `POST /plaud/admin/cleanup_stale_syncs` - Remove stale operations (2h timeout)

**Multi-Device Recovery Flow:**
1. Frontend loads → calls `/sync/check_active`
2. Backend checks user's `activeSyncToken` 
3. If found, returns current progress and sync token
4. Frontend resumes polling without user intervention
5. Works across devices, browser refreshes, tab switches

**Timeout & Cleanup Strategy:**
- **Stale Detection**: Operations queued >2 hours marked as failed
- **TTL Cleanup**: Progress records auto-deleted after 24 hours
- **Token Validation**: Prevents unauthorized callback processing
- **Orphan Handling**: Clears abandoned user sync tokens

## AI Integration Architecture

### Azure OpenAI Integration

**Speaker Inference System:**
```python
def infer_speaker_names(diarized_transcript, speaker_count):
    """Use GPT to infer speaker names from conversation context."""
    prompt = f"""
    Analyze this conversation and suggest likely names for each speaker:
    {diarized_transcript[:2000]}  # First 2000 chars for context
    
    Speakers to identify: {speaker_count}
    Return JSON: {{"Speaker 1": "Suggested Name", "Speaker 2": "..."}}
    """
    
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    return json.loads(response.choices[0].message.content)
```

**Content Analysis Pipeline:**
- **Summary Generation** - Key points extraction
- **Keyword Identification** - Topic and theme analysis
- **Sentiment Analysis** - Emotional tone assessment
- **Action Items** - Task and follow-up extraction

### Transcription Pipeline

**Azure Speech Services Integration:**
```python
def start_azure_transcription(blob_url, recording_id):
    """Initiate Azure Speech Services transcription job."""
    transcription_request = {
        "contentUrls": [blob_url],
        "properties": {
            "diarizationEnabled": True,
            "maxSpeakerCount": 10,
            "profanityFilterMode": "Masked",
            "punctuationMode": "DictatedAndAutomatic"
        },
        "locale": "en-US",
        "displayName": f"QuickScribe-{recording_id}"
    }
    
    job = speech_client.transcriptions.create(**transcription_request)
    return job.id
```

## Testing Architecture

### Test Categories & Strategy

**Unit Tests** (`tests/unit/`)
- Database handler testing with mocked Cosmos DB
- Model validation and serialization testing
- Utility function testing with edge cases
- Authentication and authorization logic testing

**Integration Tests** (`tests/integration/`)
- API endpoint testing with test database
- Azure service integration with mock responses
- File upload and processing workflow testing
- Authentication flow validation

**End-to-End Tests** (`tests/e2e/`)
- Complete user workflow testing
- Cross-service communication validation
- Real Azure service integration testing
- Performance and scalability testing

**Test Configuration:**
```python
# conftest.py
@pytest.fixture(scope="session")
def test_app():
    """Create Flask app configured for testing."""
    app = create_app(config_name='testing')
    app.config['TESTING'] = True
    app.config['COSMOS_DATABASE'] = 'quickscribe_test'
    return app

@pytest.fixture
def mock_cosmos_client():
    """Mock Cosmos DB client for unit tests."""
    with patch('azure.cosmos.CosmosClient') as mock:
        yield mock
```

### Test Execution Framework

**Test Runner** (`run_tests.py`):
```bash
python run_tests.py unit      # Fast unit tests only
python run_tests.py integration # API integration tests
python run_tests.py e2e       # End-to-end workflows
python run_tests.py fast      # Exclude slow integration tests
python run_tests.py all       # Complete test suite with coverage
```

## Deployment Architecture

### Container Configuration

**Multi-stage Dockerfile:**
```dockerfile
# Build stage - Dependencies and model generation
FROM python:3.11-slim as builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage - Minimal runtime
FROM python:3.11-slim
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . /app
WORKDIR /app
CMD ["./startup.sh"]
```

**Environment Detection:**
```bash
# startup.sh
if [ "$ENVIRONMENT" = "local" ]; then
    echo "Starting in development mode..."
    export FLASK_DEBUG=1
    python -m flask run --host=0.0.0.0 --port=$PORT --debug --reload
else
    echo "Starting in production mode..."
    gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 300 app:app
fi
```

### Azure Deployment Pipeline

**Automated Deployment** (`deploy-to-azure.sh`):
1. **Version Management** - Extract from `api_version.py`
2. **Container Build** - Docker image with version tag
3. **Registry Push** - Azure Container Registry upload
4. **App Service Deploy** - Blue-green deployment strategy
5. **Configuration Update** - Environment variables and settings
6. **Health Check** - Automated deployment verification

**Production Configuration:**
- **App Service Plan** - B2 tier with auto-scaling
- **Container Registry** - Private Azure Container Registry
- **Application Insights** - Telemetry and performance monitoring
- **Key Vault** - Secure configuration management
- **Managed Identity** - Passwordless Azure service authentication

## Security Architecture

### Data Protection & Privacy

**User Data Isolation:**
- Cosmos DB partition-based access control
- User ID validation in all data operations
- Blob storage path-based segregation
- Query filters preventing cross-user data access

**Secure Token Management:**
```python
def generate_sas_token(blob_name, permissions=['read'], hours=24):
    """Generate time-limited SAS token for blob access."""
    expiry = datetime.utcnow() + timedelta(hours=hours)
    
    return generate_blob_sas(
        account_name=storage_account,
        container_name=container_name,
        blob_name=blob_name,
        permission=BlobSasPermissions(**{p: True for p in permissions}),
        expiry=expiry
    )
```

### Input Validation & Sanitization

**Pydantic Model Validation:**
```python
class RecordingCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    file_type: str = Field(..., regex=r'^(mp3|m4a|wav|opus)$')
    duration: Optional[int] = Field(None, ge=0, le=86400)  # Max 24 hours
    tags: List[str] = Field(default=[], max_items=20)
```

## Performance & Scalability

### Optimization Strategies

**Database Performance:**
- Partition key optimization for query efficiency
- Indexed fields for fast lookups
- Connection pooling with singleton handlers
- Query result caching with TTL

**Blob Storage Optimization:**
- CDN integration for static content delivery
- Tiered storage for cost optimization
- Parallel upload/download with chunking
- Compression for bandwidth efficiency

**Application Performance:**
- Gunicorn multi-worker deployment
- Async processing with queue-based architecture
- Response caching for expensive operations
- Request/response compression

### Monitoring & Observability

**Application Insights Integration:**
```python
# logging_config.py
def setup_azure_logging():
    """Configure Application Insights telemetry."""
    handler = AzureLogHandler(
        connection_string=config.APPLICATIONINSIGHTS_CONNECTION_STRING
    )
    
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Custom telemetry tracking
    telemetry_client = TelemetryClient()
    telemetry_client.track_event('ApplicationStarted', {
        'version': API_VERSION,
        'environment': config.ENVIRONMENT
    })
```

**Metrics & Alerting:**
- Request latency and throughput monitoring
- Error rate tracking with automatic alerting
- Resource utilization metrics
- Custom business metrics (uploads, transcriptions, etc.)

## Future Architecture Considerations

### Scalability Enhancements
- **Microservices Decomposition** - Split monolith into focused services
- **Event-Driven Architecture** - Replace polling with WebSocket/SignalR
- **Caching Layer** - Redis for session and response caching
- **Load Balancing** - Azure Load Balancer for high availability

### Advanced Features
- **Multi-language Support** - Internationalization and localization
- **Advanced Search** - Azure Cognitive Search integration
- **Real-time Collaboration** - WebSocket-based shared workspaces
- **Advanced Analytics** - Business intelligence and reporting

### Infrastructure Evolution
- **Infrastructure as Code** - Terraform/ARM template automation
- **GitOps Deployment** - Git-based deployment workflows
- **Service Mesh** - Advanced microservices communication
- **Edge Computing** - Global content distribution

---

This architecture provides a robust, scalable foundation for audio transcription processing while maintaining security, performance, and maintainability standards essential for production enterprise applications.