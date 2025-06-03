# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

QuickScribe is a full-stack audio transcription application with three main components:
- **Backend**: Flask API server with Azure integrations (`/backend/`)
- **Frontend**: React/TypeScript web app with Vite (`/vite-frontend/`)
- **Transcoder**: Containerized audio processing service (`/transcoder_container/`)

## Key Commands

### Backend Development
```bash
# Build shared models from TypeScript definitions
make build

# Run Flask development server
cd backend && python app.py

# Deploy to Azure production
make deploy_azure

# Deploy to test slot
make deploy_to_test

# Bump version
make bump_version
```

### Frontend Development
```bash
cd vite-frontend

# Install dependencies
yarn install

# Start development server
yarn dev

# Build for production
yarn build

# Deploy built assets to backend
yarn deploy_local

# Run tests
yarn test

# Type checking
yarn typecheck

# Linting
yarn lint
```

### Transcoder Container
```bash
cd transcoder_container

# Build Docker image
make build

# Run locally
make run

# Deploy to Azure Container Apps
make azure-deploy

# Bump version and deploy
make bump-deploy

# View logs
make logs
```

## Architecture

### Microservices Communication
1. **Web API** → **Azure Storage Queue** → **Transcoder Service**
2. **Transcoder** processes audio files from blob storage
3. **Transcoder** → **Callback API** → **CosmosDB** update

### Shared Models
- TypeScript models in `vite-frontend/src/api/models.ts`
- Generated Python models in `backend/src/models/api_models.py`
- Build with `make build` in backend directory

### Database Structure
- **CosmosDB** containers: `recordings`, `users`, `transcripts`
- Partition keys: `userId` for recordings/transcripts, `id` for users
- Handlers in `backend/src/db_handlers/`

### Authentication Flow
- Azure AD authentication via MSAL
- Frontend acquires token → Backend validates with Azure
- User info stored in CosmosDB on first login

### Queue Processing
- Audio files uploaded to Azure Blob Storage
- Message sent to `audio-processing-queue`
- Transcoder picks up message, processes file
- Status updates via callback to `/api/transcoder/callback`

## Environment Configuration

### Backend (.env)
Critical variables:
- `AZURE_COSMOS_ENDPOINT`, `AZURE_COSMOS_KEY`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
- `ASSEMBLYAI_API_KEY`, `OPENAI_API_KEY`
- `CALLBACK_URL` (for transcoder callbacks)

### Frontend (.env)
- `VITE_API_URL` (backend URL)
- `VITE_AZURE_CLIENT_ID` (for MSAL)

### Transcoder (.env)
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_QUEUE_NAME`
- `CALLBACK_URL`, `CALLBACK_API_KEY`

## Testing Strategy

### Frontend Testing
- Unit tests with Vitest: `yarn test`
- Component testing with React Testing Library
- Run specific test: `yarn test <filename>`

### Backend Testing
- No automated tests currently implemented
- Manual testing via `/test` endpoint
- Use `test_api.http` for API testing

## Deployment Process

### Production Deployment
1. Frontend: `yarn build` → assets copied to `backend/static/`
2. Backend: `make deploy_azure` → deploys to App Service
3. Transcoder: `make azure-deploy` → deploys to Container Apps

### Version Management
- API version in `backend/src/api_version.py`
- Transcoder version in `transcoder_container/app_version.py`
- Bump with respective `make bump_version` commands

## Key Implementation Details

### Audio Processing Flow
1. User uploads/records audio → stored in blob container
2. Queue message created with blob reference
3. Transcoder downloads, converts to MP3, uploads result
4. Callback updates recording status in CosmosDB
5. Frontend polls for status updates

### Transcription Services
- **Azure Speech Services**: Default transcription provider
- **AssemblyAI**: Alternative provider with speaker diarization
- Service selection in `backend/src/services/transcription_service.py`

### Plaud Device Integration
- Sync endpoint: `/api/plaud/sync`
- Downloads recordings from Plaud API
- Creates recording entries in CosmosDB
- Queues for transcription processing