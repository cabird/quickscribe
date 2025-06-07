# QuickScribe - Comprehensive Directory Mapping

<!-- Last updated for commit: 1f262a350a8810ff29c5898620c0b6d23a2161a7 -->

This document provides a complete mapping of the QuickScribe repository structure with detailed summaries of key files and directories. This serves as a reference for understanding the codebase architecture and locating specific functionality.

## Repository Overview

QuickScribe is a full-stack audio transcription application built with:
- **Backend**: Flask API server with Azure integrations
- **Frontend (Old)**: React/TypeScript web app with Vite/Mantine UI
- **Frontend (New)**: Modern React/TypeScript app with glassmorphism design system
- **Transcoder**: Containerized audio processing microservice
- **Shared Models**: TypeScript/Python data models synchronized across services
- **AI Workspace**: Dynamic analysis types system for modular AI-powered operations

---

## Root Directory

### Configuration Files
- **CLAUDE.md** - Comprehensive development guidelines and architectural documentation for Claude Code interactions
- **TODOs** - Current development task list including UI improvements, testing enhancements, and API endpoints
- **docker-compose.yml** - Local development orchestration for backend, frontend, and transcoder services
- **dump_repo.py** - Repository analysis tool for generating file listings with configurable include/exclude patterns

### Documentation & Planning
- **ui_migration_plan.md** - Detailed migration plan for transforming the Mantine-based UI to match modern design mockups
- **ui_mockup_example.html** - HTML mockup example for UI design reference

### Plans Directory (`/plans/`)
- **commit-changes.md** - Plan for committing changes with AI-generated messages using Git commit history analysis
- **dynamic-analysis-types.md** - Plan for implementing dynamic analysis types system with modular AI operations
- **update-documentation.md** - Systematic plan for updating project documentation based on git commit history

---

## Backend Directory (`/backend/`)

### Main Application Files
- **app.py** - Main Flask application entry point that initializes the web server, registers all blueprints (API routes, Plaud integration, AI services), sets up Azure services (Cosmos DB, Blob Storage), and handles static file serving with client-side routing fallback
- **startup.sh** - Container startup script that handles environment setup (local vs production), installs Python dependencies, and launches the Flask app either with development server (local) or Gunicorn (production)
- **config.py** - Configuration management class that loads environment variables for Azure services (Storage, Cosmos DB, Speech Services, OpenAI), authentication settings, and determines container runtime environment

### Database Handlers (`/backend/db_handlers/`)
- **models.py** - Auto-generated Pydantic models from TypeScript definitions including Recording, User, Transcription, PlaudSettings, AnalysisType, AnalysisResult, and various enums (TranscriptionStatus, TranscodingStatus, Source)
- **handler_factory.py** - Factory pattern implementation that creates and caches database handler instances in Flask's request context to ensure singleton behavior per request
- **recording_handler.py** - Extended Recording model with migration handling and RecordingHandler class for CRUD operations on recordings, including Plaud-specific queries and tag management
- **transcription_handler.py** - TranscriptionHandler class for managing transcription records with methods to create, retrieve, and update transcriptions by recording ID or Azure transcription ID
- **user_handler.py** - Extended User and PlaudSettings models with datetime serialization, UserHandler class for user management, and comprehensive tag system with CRUD operations
- **analysis_type_handler.py** - Handler for managing AI analysis types (analysis configurations) and results, supporting CRUD operations for dynamic analysis types and their execution results
- **sync_progress_handler.py** - Handler for tracking and managing Plaud sync progress with real-time updates and comprehensive progress monitoring
- **util.py** - Utility function to filter out Cosmos DB system fields (_rid, _self, _etag, etc.) from documents before converting to Pydantic models
- **fixup_request.prompt** - Prompt template for AI-based request fixing and validation

### Route Files (`/backend/routes/`)
- **api.py** - Main API blueprint with comprehensive CRUD endpoints for users/recordings/transcriptions, file upload handling with Azure queue integration, transcoding callbacks, and full tag management system
- **ai_routes.py** - AI services blueprint providing speaker inference and summarization endpoints that use Azure OpenAI to analyze diarized transcripts and infer speaker names
- **az_transcription_routes.py** - Azure Speech Services integration providing transcription job management, status checking, and result processing with speaker diarization support
- **plaud.py** - Plaud device integration blueprint handling settings management, sync operations via Azure queues, callback processing for recording registration, and sync status tracking
- **local_routes.py** - Development-only routes for local authentication, test user management, data reset functionality, and dummy recording creation (only active when LOCAL_AUTH_ENABLED)

### Utility Files
- **util.py** - General utilities including audio duration calculation (MP3/M4A), duration formatting, text truncation, speaker label updates, and URL-safe slug generation for tags
- **auth.py** - Azure AD authentication using MSAL (Microsoft Authentication Library) with OAuth2 flow for production user authentication and session management
- **blob_util.py** - Azure Blob Storage operations including file upload/download, SAS URL generation with configurable permissions, queue message sending for transcoding jobs, and blob deletion
- **llms.py** - Azure OpenAI integration for AI-powered features including speaker name inference from transcripts, speaker summary generation, and JSON response parsing with prompt template management
- **user_util.py** - Current user resolution supporting both production Azure AD authentication and local development authentication with test user session management

### Configuration & Management
- **api_version.py** - Simple version tracking (currently 0.1.58) used throughout the application for logging and deployment tracking
- **logging_config.py** - Centralized logging configuration with Azure Application Insights integration, structured JSON logging, and custom metadata filtering for enhanced observability
- **manage.py** - CLI management tool using Click for administrative tasks including database/blob consistency checking, user management, Azure Speech Services job monitoring, and data cleanup operations

### Azure Integration
- **azure_speech/** - Azure Speech Services Python client SDK with comprehensive API bindings for custom speech models, endpoints, transcriptions, and webhooks

---

## Frontend (New) Directory (`/frontend_new/`)

### Overview
A complete redesign of the QuickScribe frontend using modern React with TypeScript, featuring a glassmorphism design system, AI workspace integration, and improved state management with Zustand.

### Main Application Files
- **src/main.tsx** - Application entry point with React 18 root rendering
- **src/App.tsx** - Root component with Tailwind CSS and application layout
- **ARCHITECTURE.md** - Comprehensive technical documentation of the new frontend architecture
- **README.md** - Setup and development instructions for the new frontend

### Components (`/frontend_new/src/components/`)
- **Layout/** - Main application layout components
  - **AppLayout.tsx** - Primary application shell with sidebar navigation and content area
  - **Sidebar.tsx** - Navigation sidebar with glassmorphism styling and icon-based navigation
  - **MainContent.tsx** - Content area wrapper with responsive design
  - **BrowseTab.tsx** - Recording browsing interface with search and filtering
  - **UploadTab.tsx** - File upload interface with drag-and-drop support
  - **SettingsTab.tsx** - Application settings and preferences
- **AIWorkspace/** - AI analysis workspace components
  - **AIWorkspaceModal.tsx** - Main modal container for AI workspace with multi-panel layout
  - **TranscriptPanel.tsx** - Transcript display with speaker separation and highlighting
  - **AnalysisPanel.tsx** - AI analysis configuration and execution interface
  - **TabNavigation.tsx** - Tab-based navigation for workspace sections
  - **ToolsTab.tsx** - AI tools selection and configuration
  - **ResultsOverviewTab.tsx** - Summary view of all analysis results
  - **ResultTab.tsx** - Individual analysis result display
  - **AIToolButton.tsx** - Reusable button component for AI tools
  - **AIResult.tsx** - Result display component with formatted output
  - **ResizableHandle.tsx** - Draggable handle for resizing panels
  - **mockAnalysisData.ts** - Mock data for development and testing
- **RecordingCard/** - Recording display components
  - **RecordingCard.tsx** - Modern card-based recording display with actions
- **Tags/** - Tag management components
  - **TagBadge.tsx** - Tag display component with glassmorphism styling
  - **TagManager.tsx** - Tag creation and management interface
- **IconRenderer.tsx** - Dynamic icon rendering component supporting Lucide icons
- **LocalAuthDropdown.tsx** - Development authentication dropdown

### API Integration (`/frontend_new/src/api/`)
- **recordings.ts** - Recording-related API endpoints
- **tags.ts** - Tag management API endpoints
- **plaud.ts** - Plaud device integration endpoints
- **analysisTypes.ts** - AI analysis types and results API endpoints

### State Management (`/frontend_new/src/stores/`)
- **useRecordingStore.ts** - Zustand store for recording state management
- **useTagStore.ts** - Zustand store for tag state management
- **useUIStore.ts** - Zustand store for UI state (modals, selections, etc.)
- **useAnalysisStore.ts** - Zustand store for AI analysis state and results

### Configuration & Styling
- **index.css** - Main CSS file with Tailwind directives and glassmorphism utilities
- **App.css** - Application-specific styles
- **vite.config.ts** - Vite configuration with React plugin and development settings
- **tailwind.config.js** - Tailwind CSS configuration with custom glassmorphism theme
- **postcss.config.cjs** - PostCSS configuration for Tailwind

### Types & Constants
- **src/types/index.ts** - TypeScript type definitions for frontend-specific types
- **src/constants/iconLibrary.ts** - Centralized icon mapping for Lucide icons
- **src/utils/index.ts** - Utility functions for the frontend

### Development & Documentation
- **glassmorphism-test.html** - Standalone HTML file for testing glassmorphism effects
- **workspace_update_docs/** - Documentation for AI workspace implementation
  - **description.md** - Detailed description of workspace features
  - **mockup.html** - Visual mockup of the AI workspace

---

## Frontend (Old) Directory (`/vite-frontend/`)

### Main Application Files  
- **src/main.tsx** - Entry point that renders the App component to the DOM root element
- **src/App.tsx** - Root application component that sets up Mantine theming, notifications, global styling, and conditional header with LocalAuthDropdown for development environments
- **src/Router.tsx** - React Router configuration defining four main routes: home (/), recordings list (/recordings), upload page (/upload), and transcription viewer (/view_transcription/:transcriptionId)

### Components (`/vite-frontend/src/components/`)
- **LocalAuthDropdown.tsx** - Development tool for local authentication that allows switching between test users, fetching user lists, handling login/logout, and resetting user data
- **Recording.tsx** - Table row component for individual recordings with transcription status monitoring, action buttons (start transcription, view, download, delete, etc.), and speaker labeling functionality
- **RecordingCard.tsx** - Card-based display component for recordings with similar functionality to Recording.tsx but in a more visual card format, featuring real-time transcription status updates and CustomEvent dispatching
- **RecordingCompleteDialog.tsx** - Modal dialog for saving recordings with title and description inputs, used after recording completion
- **SpeakerLabelDialog.tsx** - Basic dialog component for labeling speakers in transcriptions with input fields for each speaker and loading state handling
- **ColorSchemeToggle/** - Mantine color scheme toggle component for light/dark mode switching
- **Welcome/** - Template welcome component with Mantine branding and stories/tests

### Pages (`/vite-frontend/src/pages/`)
- **Home.page.tsx** - Landing page with gradient background, QuickScribe branding, navigation buttons to recordings/upload pages, Plaud sync functionality, and API version display
- **RecordingCardsPage.tsx** - Grid view of all recordings using RecordingCard components, with loading states, event listening for recording updates, and deletion handling
- **UploadPage.tsx** - File upload interface using Mantine's Dropzone component with progress tracking, drag-and-drop support for MP3/M4A files, and XMLHttpRequest-based upload with progress monitoring
- **ViewTranscriptionPage.tsx** - Displays individual transcriptions with speaker-separated dialogue formatting, copy-to-clipboard functionality, and navigation back to recordings list

### API Integration (`/vite-frontend/src/api/`)
- **recordings.ts** - Core API functions for recording operations including fetching recordings/individual records, starting transcriptions, deleting recordings/transcriptions, and checking transcription status with comprehensive error handling
- **util.ts** - Simple utility for fetching API version information from the backend

### Type Definitions & Interfaces
- **src/interfaces/Models.ts** - Comprehensive TypeScript interfaces for the entire application including User, Recording, Transcription, PlaudSettings, PlaudMetadata, and Tag models with detailed field documentation
- **src/types/global.d.ts** - Global type declarations

### Configuration
- **package.json** - Project dependencies including React, Mantine UI components, axios for API calls, FontAwesome icons, audio recording libraries, and comprehensive development tooling
- **vite.config.mjs** - Vite configuration with React plugin, TypeScript path resolution, development server proxy setup for backend API routes (/api, /az_transcription, /plaud), and Docker-compatible host settings
- **tsconfig.json** - TypeScript configuration with modern ES modules, strict type checking, path aliases (@/* for src, @test-utils), and DOM/testing library type support

### Styling & Utilities
- **src/Common.ts** - Shared utilities for API response handling and notification display with standardized success/error messaging
- **src/GlobalStyle.ts** - Styled-components global styling applying gradient background across the application
- **src/theme.ts** - Mantine theme configuration (currently minimal override)
- **src/util.ts** - Utility function for formatting duration display in human-readable format (hours/minutes/seconds)

---

## Transcoder Container (`/transcoder_container/`)

### Core Files
- **main.py** - Main transcoding processor that handles Azure Storage Queue messages for audio transcoding, Plaud sync operations, and test actions with comprehensive error handling, timeout management, and callback systems
- **plaud_sync.py** - Comprehensive Plaud device integration handling recording fetching, downloading, transcoding, registration with backend, and blob storage upload with rate limiting and error tracking
- **container_app_version.py** - Version tracking for the transcoder container (used in logging and deployment)
- **logging_setup.py** - Azure Application Insights logging configuration with context-aware logging for request tracking

### Configuration & Deployment
- **Dockerfile** - Multi-stage Docker build with Python 3.11, FFmpeg installation, and optimized dependency caching
- **Makefile** - Comprehensive build and deployment automation including version bumping, Azure Container Registry integration, Container Apps deployment, and local development support
- **requirements.txt** - Python dependencies including Azure SDK components, authentication libraries, HTTP clients, and monitoring tools

### Documentation & Testing
- **callback_testing_guide.md** - Testing procedures for transcoder callback functionality
- **implementation_summary.md** - High-level architecture and implementation details
- **send_test_message.py** - Utility for sending test messages to the transcoding queue
- **test_callback.py** - Callback endpoint testing functionality

---

## Shared Models (`/shared/`)

### Data Models
- **Models.ts** - Master TypeScript definitions for all data models including User, Recording, Transcription, PlaudSettings, PlaudMetadata, Tag, AnalysisType, and AnalysisResult interfaces with comprehensive field documentation and default values
- **models.py** - Auto-generated Python Pydantic models from TypeScript definitions, providing type-safe data validation and serialization for the backend
- **models.schema.json** - JSON Schema definitions derived from TypeScript models, used for validation and API documentation

---

## Scripts Directory (`/scripts/`)

### Testing & Development Tools
- **create-test-user.py** - Creates test users for local development with CosmosDB integration, proper partitioning, and test user flags for easy cleanup
- **debug_plaud_timestamps.py** - Debugging utility for investigating Plaud timestamp filtering issues with detailed timezone handling analysis
- **reset_plaud_sync_timestamp.py** - Management tool for resetting Plaud sync timestamps to force re-syncing of recordings with interactive options
- **monitor_docker_logs.py** - Real-time Docker container log monitor with color-coded output, JSON parsing, and service-specific formatting

### Test Suites
- **test_cosmosdb_serialization.py** - Comprehensive test suite for User and PlaudSettings CosmosDB serialization/deserialization with complete database round-trips
- **test_plaud_sync.py** - Full-featured integration test script for Plaud sync functionality with Docker log monitoring and real-time progress tracking
- **test_tags.py** - Complete test suite for tag functionality including API endpoints testing, CRUD operations, and error handling
- **test_user_models.py** - Pydantic model validation testing focused on User and PlaudSettings models without requiring database connections

### Configuration
- **requirements.txt** - Extensive dependency list for development environment including Azure services, machine learning libraries, and development tools
- **requirements_test.txt** - Minimal test-specific dependencies for Azure integration and HTTP testing
- **README_PLAUD_TEST.md** - Comprehensive documentation for Plaud sync integration testing including configuration, usage, and troubleshooting

---

## Infrastructure (`/infrastructure/`)

### Cloud Infrastructure
- **terraform/create_resources.sh** - Azure infrastructure provisioning script that creates the complete QuickScribe cloud environment including resource groups, Key Vault, storage accounts, Function Apps, App Service Plans, Web Apps, CosmosDB, and proper identity management with role assignments

---

## Architecture Summary

### Microservices Design
1. **Flask Backend** - Serves as the main API gateway with Azure service integrations
2. **React Frontend (Old)** - Mantine UI-based TypeScript SPA (being phased out)
3. **React Frontend (New)** - Modern glassmorphism design with AI workspace integration
4. **Transcoder Service** - Containerized audio processing with Azure Container Apps
5. **Shared Models** - Type-safe data models synchronized across all services

### Key Features
- **AI Workspace** - Dynamic analysis types system for modular AI operations on transcripts
- **Glassmorphism UI** - Modern frosted glass design system with blur effects
- **Real-time Progress Monitoring** - Comprehensive progress tracking for Plaud sync operations
- **Tag Management** - Full tagging system with optimistic updates and search
- **Speaker Diarization** - Advanced speaker separation and labeling

### Key Integrations
- **Azure CosmosDB** - Primary database with partition-based scaling
- **Azure Blob Storage** - Audio file storage with SAS token security
- **Azure Storage Queues** - Asynchronous processing coordination
- **Azure Speech Services** - Audio transcription with speaker diarization
- **Azure OpenAI** - AI-powered speaker inference, summarization, and dynamic analysis
- **Plaud Device API** - Direct integration with Plaud recording devices
- **Azure Container Apps** - Serverless container hosting for transcoder service

### Development Infrastructure
- **Docker Compose** - Local development orchestration with hot reloading
- **Comprehensive Testing** - Unit, integration, and end-to-end test suites
- **Azure DevOps** - CI/CD pipelines with Infrastructure as Code
- **Monitoring & Logging** - Azure Application Insights with structured logging
- **Authentication** - Azure AD integration with local development support
- **State Management** - Zustand for React state management in new frontend
- **Build Tools** - Vite for fast frontend development and building

This directory mapping provides a complete reference for understanding the QuickScribe codebase structure, making it easier for developers and AI assistants to navigate and work with the application.