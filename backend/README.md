# QuickScribe Backend

<!-- Last updated for commit: 1f262a350a8810ff29c5898620c0b6d23a2161a7 -->

A Flask API server for the QuickScribe audio transcription application, built with Python, Azure services integration, and comprehensive data management.

## Features

✅ **Complete API Implementation**
- RESTful API endpoints for recordings, users, and transcriptions
- File upload handling with Azure Blob Storage integration
- Real-time transcription status tracking
- Comprehensive tag management system
- Dynamic AI analysis types system for modular operations

✅ **Azure Services Integration**
- Azure Cosmos DB for scalable document storage
- Azure Blob Storage for audio file management
- Azure Speech Services for transcription processing
- Azure Storage Queues for asynchronous processing
- Azure OpenAI for AI-powered analysis features
- Azure Container Apps for microservices deployment

✅ **Authentication & Security**
- Azure AD integration with MSAL
- Local development authentication support
- Secure blob access with SAS tokens
- User-based data isolation and security

✅ **Database Management**
- Pydantic models with automatic validation
- Handler pattern for clean data access
- Extended models with serialization support
- Database migration and backward compatibility
- Analysis types and results storage for AI operations
- Sync progress tracking for Plaud device integration

✅ **Microservices Architecture**
- Queue-based communication with transcoder
- Callback system for status updates
- Scalable container deployment
- Comprehensive logging and monitoring

## Tech Stack

- **Flask** - Python web framework
- **Pydantic** - Data validation and serialization
- **Azure SDK** - Cloud services integration
- **Azure Cosmos DB** - NoSQL document database
- **Azure Blob Storage** - File storage service
- **Azure Speech Services** - Transcription processing
- **Azure OpenAI** - AI analysis capabilities
- **Gunicorn** - WSGI HTTP server for production

## Getting Started

### Prerequisites
- Python 3.11+
- Azure subscription with configured services
- Docker (for containerized deployment)

### Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Configuration

Create a `.env` file based on `example.env`:

```bash
# Copy example configuration
cp example.env .env

# Edit with your Azure service credentials
# Required variables:
AZURE_COSMOS_ENDPOINT=your_cosmos_endpoint
AZURE_COSMOS_KEY=your_cosmos_key
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
AZURE_TENANT_ID=your_tenant_id
```

### Development

```bash
# Run Flask development server
python app.py
```

The backend will start on http://localhost:5000 with hot reloading enabled.

### Building Shared Models

```bash
# Generate Python models from TypeScript definitions
make build
```

### Testing

```bash
# Run all tests
python run_tests.py all

# Run specific test categories
python run_tests.py unit
python run_tests.py integration
python run_tests.py e2e
python run_tests.py fast
```

### Deployment

```bash
# Deploy to Azure App Service
make deploy_azure

# Deploy to test slot
make deploy_to_test

# Local deployment testing
make deploy_local
```

## Architecture

### Directory Structure

```
backend/
├── db_handlers/           # Database access layer
│   ├── models.py         # Auto-generated Pydantic models
│   ├── handler_factory.py # Handler creation and caching
│   ├── user_handler.py   # User data operations
│   ├── recording_handler.py # Recording data operations
│   └── transcription_handler.py # Transcription data operations
├── routes/               # API route blueprints
│   ├── api.py           # Main API endpoints
│   ├── ai_routes.py     # AI analysis endpoints
│   ├── az_transcription_routes.py # Azure Speech Services
│   ├── plaud.py         # Plaud device integration
│   └── local_routes.py  # Development-only routes
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/            # End-to-end tests
├── app.py              # Flask application entry point
├── config.py           # Configuration management
├── auth.py             # Authentication handling
├── blob_util.py        # Azure Blob Storage operations
├── llms.py             # Azure OpenAI integration
├── user_util.py        # User session management
└── requirements.txt    # Python dependencies
```

### API Endpoints

All endpoints support proper authentication and error handling:

- **Recordings**: `/api/recordings/*` - CRUD operations for audio recordings
- **Transcriptions**: `/api/transcription/*` - Transcript data management
- **Tags**: `/api/tags/*` - Tag system with full CRUD support
- **AI Analysis**: `/api/ai/*` - AI-powered analysis features
- **Azure Speech**: `/az_transcription/*` - Transcription service integration
- **Plaud Integration**: `/plaud/*` - Plaud device sync and management
- **Development**: `/local/*` - Local development utilities

### Database Design

**Cosmos DB Containers:**
- `users` - User profiles and settings (partitioned by `id`)
- `recordings` - Audio recording metadata (partitioned by `userId`)
- `transcripts` - Transcription data and analysis (partitioned by `userId`)

**Data Models:**
- Type-safe Pydantic models with validation
- Automatic serialization for datetime fields
- Extended models for complex field handling
- Migration support for schema evolution

## Key Features Implemented

✅ **File Upload System**: Multi-format audio upload with Azure Blob Storage integration  
✅ **Transcription Pipeline**: Asynchronous processing with status tracking  
✅ **Tag Management**: Complete CRUD system with color coding and filtering  
✅ **AI Integration**: Speaker inference and content analysis with Azure OpenAI  
✅ **Plaud Integration**: Device sync and automatic recording import  
✅ **Authentication**: Azure AD with local development support  
✅ **Error Handling**: Comprehensive error responses and logging  
✅ **Testing Framework**: Unit, integration, and E2E test coverage  

## Configuration Management

The backend uses environment-based configuration with automatic detection:

- **Production**: Azure App Service with managed identity
- **Development**: Local `.env` file with service credentials
- **Testing**: Isolated test database configuration
- **Container**: Docker environment variable injection

## Monitoring & Logging

- **Azure Application Insights** integration for telemetry
- **Structured JSON logging** with correlation IDs
- **Request tracing** throughout the processing pipeline
- **Error tracking** with automatic alerting
- **Performance metrics** for optimization

## Security Features

- **Azure AD authentication** with JWT token validation
- **User data isolation** with partition-based access control
- **SAS token generation** for secure blob access
- **Input validation** with Pydantic models
- **SQL injection prevention** with parameterized queries
- **CORS configuration** for cross-origin security

## Future Enhancements

- WebSocket support for real-time updates
- Advanced caching with Redis integration
- Rate limiting and API throttling
- Enhanced AI analysis capabilities
- Multi-language transcription support
- Advanced search and indexing
- Performance optimization with connection pooling

## Deployment

### Production (Azure App Service)
```bash
make deploy_azure
```

### Development (Local Docker)
```bash
make deploy_local
```

### Testing Environment
```bash
make deploy_to_test
```

The backend is designed for scalable, secure, and maintainable audio transcription processing with comprehensive Azure services integration.