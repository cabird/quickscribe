# System Description
**Git commit:** 798b46476c2d52dc8c006a9bbfdf98d8c1623415

## 1. Repository Structure

The backend directory contains the Flask API server for QuickScribe, organized as follows:

```
backend/
├── src/                          # Main source code directory
│   ├── app.py                    # Flask application factory and configuration
│   ├── config.py                 # Configuration management wrapper
│   ├── auth.py                   # Azure AD authentication with MSAL
│   ├── blob_util.py              # Azure Blob Storage operations
│   ├── llms.py                   # Azure OpenAI integration
│   ├── ai_postprocessing.py      # AI post-processing orchestration
│   ├── user_util.py              # User session management
│   ├── util.py                   # General utility functions
│   ├── logging_config.py         # Centralized logging configuration
│   ├── api_version.py            # API version tracking (0.1.65)
│   │
│   ├── db_handlers/              # Data access layer
│   │   ├── models.py             # Auto-generated Pydantic models
│   │   ├── handler_factory.py   # Singleton handler creation
│   │   ├── user_handler.py      # User CRUD operations
│   │   ├── recording_handler.py # Recording management
│   │   ├── transcription_handler.py # Transcription data
│   │   ├── sync_progress_handler.py # Progress tracking
│   │   ├── analysis_type_handler.py # AI analysis types
│   │   ├── participant_handler.py   # Participant management
│   │   └── util.py              # Database utilities
│   │
│   ├── routes/                   # API blueprints
│   │   ├── api.py               # Main REST API endpoints
│   │   ├── ai_routes.py         # AI analysis endpoints
│   │   ├── local_routes.py      # Development-only routes
│   │   ├── admin.py             # Admin endpoints
│   │   └── participant_routes.py # Participant endpoints
│   │
│   ├── templates/                # Jinja2 templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── recordings.html
│   │   ├── upload.html
│   │   └── view_transcription.html
│   │
│   ├── static/                   # Static assets
│   │   └── styles.css
│   │
│   └── frontend-dist/            # Built frontend assets
│       ├── assets/
│       ├── index.html
│       └── vite.svg
│
├── tests/                        # Test suite
│   ├── conftest.py              # Pytest configuration
│   ├── unit/                    # Unit tests
│   │   └── test_user_handler.py
│   ├── integration/             # Integration tests
│   │   ├── test_api_endpoints.py
│   │   ├── test_analysis_execution.py
│   │   └── test_analysis_types_real_db.py
│   ├── e2e/                     # End-to-end tests
│   │   └── test_complete_workflows.py
│   └── fixtures/                # Test utilities
│       └── test_utils.py
│
├── migrations/                   # Database migrations
│   ├── 001_normalize_diarized_transcripts.py
│   ├── 002_create_participant_profiles.py
│   ├── README.md
│   └── migration_runner.py
│
├── Makefile                      # Build automation
├── Dockerfile                    # Container configuration
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
├── startup.sh                    # Container startup script
├── run_tests.py                  # Test runner
├── prompts.yaml                  # AI prompt templates
├── example.env                   # Environment template
├── README.md                     # Setup and usage guide
├── ARCHITECTURE.md               # Detailed architecture documentation
└── API_SPECIFICATION.md          # API endpoint documentation
```

## 2. Languages, Size & Composition

### Primary Language
- **Python 3.11** - 7,422 total lines of code in src/ directory

### File Types Distribution
- **Python (.py)**: Core application logic, handlers, routes
- **YAML (.yaml)**: Prompt templates for AI operations
- **JSON (.json)**: Configuration and schema files
- **Markdown (.md)**: Documentation files
- **HTML**: Jinja2 templates for web interface
- **CSS**: Styling for templates
- **Shell (.sh)**: Deployment and startup scripts

### Code Organization
- Source code: `src/` directory with modular organization
- Tests: `tests/` with unit, integration, and e2e subdirectories
- Configuration: Environment-based with shared settings library
- Documentation: Comprehensive README, ARCHITECTURE, and API docs

## 3. Key Components and Modules

### Core Application (src/)

**app.py** - Flask application factory
- Creates Flask app with CORS configuration
- Registers all blueprints with URL prefixes
- Initializes Azure services (Blob Storage, Cosmos DB)
- Sets up logging with Application Insights
- Hot-reload support for development

**config.py** - Configuration wrapper
- Wraps shared_quickscribe_py.config for backward compatibility
- Environment detection (Azure vs local development)
- Configuration for all Azure services
- Property-based access to nested settings

**auth.py** - Azure AD authentication
- MSAL integration for token validation
- User token extraction and verification
- JWT token handling

**llms.py** - Azure OpenAI integration
- Async infrastructure for AI operations
- Speaker mapping inference
- Speaker summary generation
- Prompt templating from prompts.yaml

**ai_postprocessing.py** - Post-processing orchestration
- Automatic title generation from transcripts
- Description generation
- Speaker inference coordination
- Triggered on transcription completion

**blob_util.py** - Azure Blob Storage operations
- File upload/download handling
- SAS token generation for secure access
- Container management

**user_util.py** - User session management
- Current user resolution from request context
- User data retrieval and caching

**logging_config.py** - Centralized logging
- Application Insights integration
- Structured JSON logging
- Correlation ID tracking

### Data Access Layer (src/db_handlers/)

**models.py** - Pydantic models (auto-generated)
- Generated from TypeScript definitions in ../shared/Models.ts
- Type-safe data validation
- Used across backend, frontend, and transcoder

**handler_factory.py** - Handler creation
- Singleton pattern within Flask request context
- Factory functions for all handler types
- Consistent configuration across handlers
- Request-scoped caching

**user_handler.py** - User operations
- Extended Pydantic models with datetime serialization
- CRUD operations for user profiles
- PlaudSettings management
- Field validators and serializers

**recording_handler.py** - Recording management
- Recording CRUD operations
- Migration support for backward compatibility
- Tag association and management
- Status tracking

**transcription_handler.py** - Transcription data
- Transcription CRUD operations
- Speaker mapping storage
- Analysis results management

**sync_progress_handler.py** - Progress tracking
- Long-running operation status
- Plaud sync progress monitoring

**analysis_type_handler.py** - AI analysis types
- Dynamic analysis type registration
- Analysis result storage
- Modular AI operation framework

**participant_handler.py** - Participant management
- Participant profile operations
- Recording/transcription associations

### API Routes (src/routes/)

**api.py** - Main REST API (`/api/*`)
- Recording endpoints (CRUD)
- Transcription endpoints
- Tag management
- File upload handling
- Transcoder callback endpoint
- Azure AD authenticated

**ai_routes.py** - AI analysis (`/api/ai/*`)
- Speaker inference endpoint
- Analysis type execution
- AI post-processing triggers
- OpenAI integration

**local_routes.py** - Development utilities (`/api/local/*`)
- Local authentication
- Test user management
- Development-only features

**admin.py** - Admin endpoints (`/api/admin/*`)
- Administrative operations
- System management

**participant_routes.py** - Participant API (`/api/participants/*`)
- Participant CRUD operations
- Participant merging (TODO)
- Recording associations

### Testing Suite (tests/)

**conftest.py** - Pytest configuration
- Shared fixtures
- Mock setup
- Test database configuration

**unit/** - Unit tests
- Individual component testing
- Database handler tests
- Isolated from external dependencies

**integration/** - Integration tests
- API endpoint testing
- Service integration validation
- Mock patching at route import level

**e2e/** - End-to-end tests
- Complete workflow testing
- Full user journey validation

**Test Runner (run_tests.py)**
- Category-based test execution
- Coverage reporting
- Virtual environment validation
- Categories: unit, integration, e2e, fast, all

### Migrations (migrations/)

**migration_runner.py** - Migration orchestration
- Schema evolution support
- Data migration execution

**001_normalize_diarized_transcripts.py** - Transcript normalization
**002_create_participant_profiles.py** - Participant schema

## 4. Build, Tooling, and Dependencies

### Build System (Makefile)

**Key Targets:**
- `make build` - Generate Python models from TypeScript
- `make build_container` - Build Docker image
- `make deploy_azure` - Deploy to Azure App Service
- `make deploy_local` - Local Docker deployment
- `make bump_version` - Increment version number
- `make compose_up/down` - Docker Compose orchestration
- `make local_run` - Run Flask development server

**Model Generation Pipeline:**
1. TypeScript definitions in `../shared/Models.ts`
2. `typescript-json-schema` generates JSON schema
3. `datamodel-codegen` creates Pydantic models
4. Output: `src/db_handlers/models.py`

### Python Dependencies (requirements.txt)

**Web Framework:**
- Flask 3.0.3 - Core web framework
- flask-cors 6.0.1 - CORS support
- Flask-SocketIO 5.4.1 - WebSocket support
- gunicorn 22.0.0 - Production WSGI server

**Azure Services:**
- azure-cosmos 4.7.0 - Cosmos DB client
- azure-storage-blob 12.23.1 - Blob storage
- azure-storage-queue 12.12.0 - Queue storage
- azure-cognitiveservices-speech 1.41.1 - Speech services
- azure-identity 1.19.0 - Authentication
- azure-keyvault-secrets 4.8.0 - Key vault
- opencensus-ext-azure 1.1.14 - Application Insights

**Data Validation:**
- pydantic 2.9.2 - Data validation
- pydantic_core 2.23.4 - Core validation

**AI/ML:**
- openai 1.51.2 - OpenAI API client
- assemblyai 0.34.0 - Alternative transcription
- tiktoken 0.8.0 - Token counting

**Testing:**
- pytest 8.3.3 - Test framework
- pytest-flask 1.3.0 - Flask testing
- pytest-asyncio 0.25.0 - Async testing
- pytest-cov 5.0.0 - Coverage reporting
- pytest-mock 3.14.0 - Mocking support
- coverage 7.8.2 - Coverage analysis

**Utilities:**
- python-dotenv 1.0.1 - Environment variables
- PyYAML 6.0.2 - YAML parsing
- requests 2.32.3 - HTTP client
- msal 1.31.0 - Microsoft authentication
- datamodel-code-generator 0.26.2 - Model generation

### Development Tools

**Docker** - Containerization
- Multi-stage Dockerfile
- Environment-based configuration (.env.local, .env.azure)
- Startup script with mode detection

**Pytest** - Testing framework
- 41% test coverage (target: 70%)
- Multiple test categories
- Fixture-based architecture

**bump2version** - Version management
- Automated version incrementing
- Synchronized with git tags

### Version Control Integration

**Current Version:** 0.1.65 (from api_version.py)
**Version Files:**
- `src/api_version.py` - API version constant
- Bumped via `make bump_version`

## 5. Runtime Architecture

### Application Startup Flow

**Container Startup (startup.sh):**
1. Detect environment (Azure vs Local)
   - Azure: Check WEBSITE_INSTANCE_ID
   - Local: Default behavior
2. Copy appropriate .env file
   - Azure: `.env.azure` → `src/.env`
   - Local: `.env.local` → `src/.env`
3. Install local packages from `local_packages/`
4. Start server:
   - Azure: Gunicorn with timeout 600s on port 8000
   - Local: Flask debug server with hot reload

**Flask Application Factory (app.py):**
1. Configure logging (logging_config.setup_logging)
2. Load environment variables
3. Create Flask app with static folder
4. Enable CORS based on environment
5. Register blueprints:
   - `/api` - Main API (api_bp)
   - `/api/ai` - AI routes (ai_bp)
   - `/api/local` - Local routes (local_bp)
   - `/api/admin` - Admin routes (admin_bp)
   - `/api/participants` - Participant routes (participant_bp)
6. Initialize Azure services:
   - Blob Storage client
   - Cosmos DB client
7. Setup Application Insights logging

### Request Processing Flow

**Authentication:**
1. Client sends request with Authorization header
2. `@require_auth` decorator validates Azure AD token
3. `get_current_user()` extracts user from token
4. User object stored in Flask request context

**Database Operations:**
1. Route handler calls `get_*_handler()` from handler_factory
2. Factory creates or retrieves cached handler
3. Handler performs Cosmos DB operations
4. Pydantic models validate data
5. Extended models handle datetime serialization
6. Response returned to client

**Audio Processing Pipeline:**
1. Client uploads audio → `/api/recordings/upload`
2. File stored in Azure Blob Storage
3. Queue message created with blob reference
4. Transcoder service picks up message
5. Transcoder processes audio, uploads MP3
6. Callback to `/api/transcoder/callback` updates status
7. AI post-processing triggered on completion:
   - Title generation
   - Description generation
   - Speaker inference

### Microservices Communication

**Queue-based Processing:**
- Backend → Azure Storage Queue → Transcoder
- Asynchronous, decoupled architecture
- Scalable processing

**Callback Pattern:**
- Transcoder → `/api/transcoder/callback` → Cosmos DB update
- Status updates propagated to frontend
- Error handling and retry logic

### Database Architecture

**Cosmos DB Containers:**
- `users` - Partitioned by `id`
- `recordings` - Partitioned by `userId`
- `transcripts` - Partitioned by `userId`
- `analysis_types` - Dynamic AI analysis types
- `participants` - Speaker/participant profiles

**Data Isolation:**
- User-based partitioning
- Secure data access
- Optimized query performance

### Logging and Monitoring

**Azure Application Insights:**
- Request tracing with correlation IDs
- Custom events for business metrics
- Exception tracking
- Performance monitoring

**Structured Logging:**
- JSON format for machine parsing
- API version included in all logs
- Error context preservation

## 6. Development Workflows

### Local Development Setup

```bash
# 1. Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp example.env .env
# Edit .env with Azure credentials

# 4. Build shared models
make build

# 5. Run development server
python src/app.py
# Or: make local_run
```

### Testing Workflow

```bash
# Activate virtual environment (required!)
source venv/bin/activate

# Run different test categories
python run_tests.py unit           # Unit tests only
python run_tests.py integration    # Integration tests
python run_tests.py e2e            # End-to-end tests
python run_tests.py fast           # Quick tests (excludes slow)
python run_tests.py all            # Full suite with coverage

# Run with options
python run_tests.py all --coverage --verbose
python run_tests.py fast --html    # Generate HTML coverage report
```

### Model Synchronization

```bash
# After editing ../shared/Models.ts
make build

# This runs:
# 1. typescript-json-schema on Models.ts
# 2. Generates models.schema.json
# 3. datamodel-codegen creates models.py
```

### Deployment Workflow

**Local Docker Testing:**
```bash
make build_container    # Build image
make deploy_local       # Run locally on port 5000
make docker_stop        # Stop container
```

**Azure Production Deployment:**
```bash
# 1. Bump version
make bump_version

# 2. Build and deploy
make deploy_azure

# Automated process:
# - Builds Docker image
# - Pushes to Azure Container Registry
# - Updates App Service
# - Configures environment
```

**Full Stack Development:**
```bash
# From repository root
make compose_up    # Start backend + frontend
make compose_logs  # Follow logs
make compose_down  # Stop all services
```

### Version Management

```bash
# Bump patch version (0.1.65 → 0.1.66)
make bump_version

# Version stored in:
# - src/api_version.py (API_VERSION constant)
# - Git tags (created by bump2version)
```

### Code Quality Checks

```bash
# Format code
black src/

# Sort imports
isort src/

# Run tests with coverage
python run_tests.py all --coverage --html
# View: htmlcov/index.html
```

## 7. Known Limitations / TODOs

### From Code Analysis

**src/routes/ai_routes.py:82**
- TODO: Uncomment restriction to prevent multiple speaker inference runs
- Currently allows re-inferring speakers multiple times

**src/routes/participant_routes.py:230**
- TODO: Add logic to clean up participant references in recordings/transcriptions
- Missing cleanup when participants are deleted

**src/routes/participant_routes.py:387**
- TODO: Update all recordings and transcriptions to point to primary participant
- Participant merging not fully implemented

### Testing Coverage

**Current: 41% | Target: 70%**
- Need more integration tests
- E2E workflow coverage incomplete
- Mock strategy needs refinement

### Architecture Considerations

**Pydantic Model Synchronization:**
- Manual build step required after TypeScript changes
- Could automate with file watchers
- Risk of models getting out of sync

**Database Migration:**
- Migration system exists but manual execution
- No automatic migration on deployment
- Need better migration tracking

**Error Handling:**
- Inconsistent error response formats across routes
- Could benefit from centralized error handler
- Need better validation error messages

### Performance Opportunities

**Connection Pooling:**
- No connection pooling for Cosmos DB
- Could optimize with connection reuse
- Reduce latency for database operations

**Caching:**
- No Redis or distributed caching
- Repeated database queries for same data
- Could cache user profiles, analysis types

**Async Processing:**
- Some blocking operations in request handlers
- Could benefit from async/await patterns
- Background task queue for AI operations

## 8. Suggested Improvements or Considerations for AI Agents

### Code Navigation Tips

1. **Entry Point:** Start at `src/app.py` to understand application structure
2. **API Routes:** Check `src/routes/api.py` for available endpoints
3. **Data Models:** Review `src/db_handlers/models.py` (auto-generated) and handler files for schema
4. **Configuration:** All settings in `src/config.py` wrapping shared_quickscribe_py.config
5. **Testing:** Look at `tests/conftest.py` for fixtures and test setup

### Architecture Patterns to Understand

**Handler Factory Pattern:**
- All database access goes through handlers
- Factory creates singleton instances per request
- Import from `handler_factory.py`, never instantiate directly
- Example: `get_recording_handler()` not `RecordingHandler()`

**Extended Pydantic Models:**
- Base models auto-generated in `models.py`
- Extended versions in handler files add serialization
- Use `save_user(user)` not manual dict conversion
- Datetime fields auto-serialize to ISO format

**Blueprint Routing:**
- Routes organized by domain/functionality
- Each blueprint has URL prefix
- Authentication via `@require_auth` decorator
- User context via `get_current_user()`

**Environment-based Configuration:**
- Production uses `.env.azure` (baked into Docker image)
- Local development uses `.env.local`
- startup.sh handles selection
- Shared settings library provides type-safe access

### Testing Strategy

**Mock Approach:**
- Mock at route import level to prevent database hits
- Use pytest fixtures from conftest.py
- Test categories via markers: @pytest.mark.unit, etc.
- Always activate venv before running tests

**Test Organization:**
- Unit: Individual components in isolation
- Integration: API endpoints with mocked services
- E2E: Complete workflows with minimal mocking
- Fast: Quick tests for CI/CD (excludes slow markers)

### Common Pitfalls

1. **Dictionary Access on Pydantic Models:**
   - ❌ `user.plaudSettings['field'] = value`
   - ✅ `user.plaudSettings.field = value`

2. **DateTime Serialization:**
   - ❌ Manual `.isoformat()` conversion
   - ✅ Let Pydantic serializers handle it

3. **Handler Instantiation:**
   - ❌ `handler = RecordingHandler(...)`
   - ✅ `handler = get_recording_handler()`

4. **Missing Virtual Environment:**
   - Scripts require `venv` activation
   - Tests will fail without proper environment
   - Check with `echo $VIRTUAL_ENV`

5. **Model Sync:**
   - After editing `../shared/Models.ts`
   - Must run `make build`
   - Frontend auto-syncs, backend needs manual build

### Integration Points

**With Frontend:**
- Built assets served from `src/frontend-dist/`
- API endpoints at `/api/*`
- CORS enabled for localhost:3000 in dev mode

**With Transcoder:**
- Queue messages via Azure Storage Queue
- Callback endpoint: `/api/transcoder/callback`
- Status updates propagate to Cosmos DB

**With Plaud Service:**
- Separate microservice handles Plaud device sync
- Webhook endpoint in plaud routes (not under `/api/plaud`)
- Shared models via shared_quickscribe_py

### Deployment Considerations

**Azure App Service:**
- Uses Gunicorn with 600s timeout
- Environment from baked `.env.azure`
- Managed identity for service access
- Application Insights auto-configured

**Local Development:**
- Flask debug server with hot reload
- Environment from `.env.local`
- Explicit credentials in .env file
- CORS allows localhost:3000

**Docker:**
- Multi-stage build not shown (single Dockerfile)
- Startup script handles environment selection
- Port 8000 internally, mapped externally
- Shared packages from local_packages/ directory

### AI Analysis Best Practices

When analyzing or modifying this codebase:

1. **Check ARCHITECTURE.md** for detailed design patterns
2. **Review API_SPECIFICATION.md** for endpoint contracts
3. **Examine existing tests** to understand expected behavior
4. **Use handler_factory** for all database operations
5. **Follow blueprint patterns** for new routes
6. **Add tests** for new functionality (aim for 70% coverage)
7. **Update models.py** only via `make build` from TypeScript
8. **Validate changes** with `python run_tests.py fast` before commit
9. **Check TODOs** in code for known incomplete features
10. **Consider backward compatibility** when modifying database models
