# QuickScribe

<!-- Last updated for commit: 0b5c14dba1691c16fd9cfef10ae6bccfd3490170 -->

A full-stack audio transcription application with AI-powered analysis, built with modern cloud-native architecture on Azure.

## Overview

QuickScribe is a comprehensive audio transcription platform that integrates with Plaud recording devices, provides AI-powered transcript analysis, and features a modern glassmorphism UI design. The application is built as a microservices architecture deployed on Azure.

## Key Features

### 🎙️ Audio Transcription
- High-quality transcription using Azure Speech Services
- Speaker diarization and identification
- Support for multiple audio formats (MP3, M4A, WAV, OPUS)
- Real-time transcription status tracking

### 🤖 AI-Powered Analysis
- Dynamic analysis types system for modular AI operations
- Automatic post-processing (title, description, speaker inference)
- Speaker inference and labeling with reasoning
- Content summarization and insights
- Customizable analysis workflows
- Integration with Azure OpenAI with async processing

### 📱 Plaud Device Integration
- Automatic sync with Plaud recording devices
- Direct recording import and management
- Progress monitoring and error recovery
- Timezone-aware timestamp handling

### 🎨 Modern UI Design
- Glassmorphism design system with frosted glass effects
- Responsive layout with resizable panels
- Real-time updates and optimistic UI
- Comprehensive tag management system
- AI workspace with multi-panel layout

### ☁️ Cloud-Native Architecture
- Microservices design on Azure
- Scalable queue-based processing
- Secure blob storage for audio files
- Azure AD authentication
- Comprehensive monitoring with Application Insights

## Architecture

QuickScribe consists of three main components:

### Backend API Server
- Flask-based REST API with AI post-processing pipeline
- Azure Cosmos DB for data storage
- Azure service integrations
- Comprehensive handler pattern for data access
- Async LLM infrastructure for concurrent processing

### Frontend Application
- **Frontend**: Modern React app with glassmorphism design
- TypeScript-based with comprehensive component library

### Transcoder Microservice
- Containerized audio processing service
- Azure Storage Queue consumer
- FFmpeg-based transcoding
- Deployed on Azure Container Apps

## Tech Stack

### Backend
- Python 3.11 with Flask
- Pydantic for data validation
- Azure SDK for cloud services
- Gunicorn for production serving

### Frontend (New)
- React 18 with TypeScript
- Tailwind CSS for styling
- Zustand for state management
- Vite for fast development

### Infrastructure
- Azure Cosmos DB (NoSQL database)
- Azure Blob Storage (audio files)
- Azure Storage Queues (job processing)
- Azure Container Apps (microservices)
- Azure App Service (web hosting)
- Docker for containerization

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ and npm
- Python 3.11+
- Azure account (for cloud deployment)

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/cabird/quickscribe.git
cd quickscribe
```

2. Set up environment variables:
```bash
# Copy example environment files
cp backend/example.env backend/.env
cp frontend_new/.env.example frontend_new/.env
cp transcoder_container/env.local.template transcoder_container/.env

# Edit the .env files with your Azure credentials
```

3. Start the application with Docker Compose:
```bash
docker-compose up
```

This will start:
- Backend API on http://localhost:8000
- Frontend on http://localhost:5173
- Transcoder service (processing queue messages)

### Development Workflow

#### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

#### Frontend Development
```bash
cd frontend_new
npm install
npm run dev
```

#### Running Tests
```bash
# Backend tests
cd backend
python run_tests.py all

# Frontend tests
cd frontend_new
npm test
```

## Documentation

- **[DIRECTORY_MAPPING.md](./DIRECTORY_MAPPING.md)** - Comprehensive guide to the codebase structure
- **[CLAUDE.md](./CLAUDE.md)** - Instructions for AI-assisted development
- **[TODOs](./TODOs)** - Current development priorities
- **Component Documentation**:
  - [Backend Architecture](./backend/ARCHITECTURE.md)
  - [Frontend Architecture](./frontend_new/ARCHITECTURE.md)
  - [Transcoder Architecture](./transcoder_container/ARCHITECTURE.md)

## Deployment

### Azure Deployment

1. Build and deploy the backend:
```bash
cd backend
make deploy_azure
```

2. Build and deploy the frontend:
```bash
cd frontend_new
npm run build
npm run deploy
```

3. Deploy the transcoder:
```bash
cd transcoder_container
make azure-deploy
```

### Infrastructure Setup

Use the provided Terraform scripts to set up Azure resources:
```bash
cd infrastructure/terraform
./create_resources.sh
```

## Contributing

1. Create a feature branch from `main`
2. Follow the existing code style and patterns
3. Add tests for new functionality
4. Update documentation as needed
5. Submit a pull request

## License

[License information to be added]

## Support

For issues and feature requests, please use the GitHub issue tracker.