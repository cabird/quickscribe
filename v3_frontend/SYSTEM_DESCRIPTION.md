# System Description
**Git commit:** 5b007ef08f5714d19faf318994f63082d90698fd

## 1. Repository Structure

This is the **v3_frontend** directory of the QuickScribe project - a modern React + TypeScript web application for audio transcription management.

```
v3_frontend/
├── docs/                       # Design and planning documentation
│   ├── API_SPECIFICATION.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── SYSTEM_DESCRIPTION.md
│   ├── spec.md
│   ├── tech_guidance.md
│   └── fluent_ui_mock.jsx
├── public/                     # Static assets
│   ├── favicon.png
│   ├── quickscribe-icon.png
│   ├── quickscribe-icon-full.png
│   └── quickscribe-icon-orig.png
├── scripts/                    # Build and automation scripts
│   └── sync-models.js          # Auto-sync TypeScript models from /shared
├── src/                        # Application source code
│   ├── auth/                   # Authentication module (NEW)
│   │   └── msalInstance.ts     # Azure AD MSAL client initialization
│   ├── components/             # React UI components
│   │   ├── auth/               # Authentication components (NEW)
│   │   │   └── AuthButton.tsx  # Login/logout user menu
│   │   ├── jobs/               # Job monitoring views
│   │   ├── layout/             # Core layout (MainLayout, NavigationRail, TopActionBar)
│   │   ├── logs/               # Placeholder for future logging UI
│   │   ├── search/             # Placeholder for search functionality
│   │   ├── settings/           # User settings (NEW)
│   │   │   └── SettingsView.tsx
│   │   └── transcripts/        # Recording and transcript views (enhanced)
│   │       ├── AudioPlayer.tsx         # Audio playback with seek (NEW)
│   │       ├── SpeakerDropdown.tsx     # Speaker selection/creation (NEW)
│   │       └── useTranscriptParser.ts  # Transcript parsing hook (NEW)
│   ├── config/                 # Application configuration
│   │   ├── authConfig.ts       # MSAL/Azure AD configuration (NEW)
│   │   ├── constants.ts
│   │   └── styles.ts
│   ├── hooks/                  # Custom React hooks
│   ├── services/               # API client and service layers
│   │   ├── api.ts              # Axios API client with MSAL auth (ENHANCED)
│   │   ├── participantsService.ts  # Participant CRUD operations (NEW)
│   │   ├── userService.ts      # Current user and settings API (NEW)
│   │   └── ...                 # Other services
│   ├── styles/                 # Global CSS
│   ├── theme/                  # Fluent UI theme customization
│   ├── types/                  # TypeScript type definitions
│   └── utils/                  # Utility functions
├── ADDING_AUTH.md              # Authentication implementation guide (NEW)
├── AUTH_IMPLEMENTATION.md      # Detailed auth architecture (NEW)
├── API_CONFIGURATION.md
├── DEPLOYMENT.md
├── README.md
├── index.html                  # Vite HTML template
├── package.json
└── vite.config.ts              # Vite build configuration
```

## 2. Languages, Size & Composition

- **Primary Language**: TypeScript (React/TSX)
- **File Count**: 54 TypeScript/TSX source files
- **Total Lines of Code**: ~5,663 lines (excluding node_modules)
- **Configuration**: JSON (package.json, tsconfig.json)
- **Build Tool**: Vite 7.2.2
- **Styling**: CSS + Fluent UI makeStyles API

**File Distribution**:
- Components: 24 TSX files (including new auth, settings, audio player)
- Services: 8 TypeScript modules (added participants, user services)
- Hooks: 5 custom React hooks (added useTranscriptParser)
- Utils: 5 utility modules
- Auth: 2 TypeScript modules (MSAL instance, auth config)
- Configuration & Build: 7 files

## 3. Key Components and Modules

### Core Application Structure

**Entry Points**:
- `main.tsx` - React root rendering with StrictMode, conditional MsalProvider wrapping
- `App.tsx` - Root component with FluentProvider, theme, and toast container

**Authentication System** (`src/auth/`, `src/config/authConfig.ts`, `src/components/auth/`):
- `msalInstance.ts` - Azure AD MSAL PublicClientApplication initialization
  - Handles redirect promise on app load
  - Event callbacks for login/logout/token events
  - Active account management
- `authConfig.ts` - MSAL configuration
  - `msalConfig` - Client ID, tenant, redirect URI, cache settings
  - `loginRequest` - Required OAuth scopes (user_impersonation)
  - `authEnabled` flag - Toggle authentication on/off via env var
- `AuthButton.tsx` - User authentication UI component
  - Shows "Sign In" button when not authenticated
  - Shows user avatar/menu with logout when authenticated
  - Only renders when `authEnabled=true`

**Layout System** (`src/components/layout/`):
- `MainLayout.tsx` - Top-level layout with navigation and view switching
- `NavigationRail.tsx` - Left sidebar navigation (transcripts/jobs/settings views)
- `TopActionBar.tsx` - Top action bar with controls and AuthButton
- `ResizableSplitter.tsx` - Drag-to-resize panel divider

### Feature Modules

**Transcripts View** (`src/components/transcripts/`):
- `TranscriptsView.tsx` - Three-column Outlook-style layout (list, viewer, chat)
- `RecordingsList.tsx` - List of recording cards with filtering
- `RecordingCard.tsx` - Individual recording card with metadata and actions
- `TranscriptViewer.tsx` - Full transcript display with speaker diarization
- `TranscriptEntry.tsx` - Individual transcript segment with speaker renaming
- `ChatDrawer.tsx` - AI chat interface for recordings
- `ChatMessage.tsx` - Individual chat message component
- `ChatInput.tsx` - Chat input with send functionality
- `AudioPlayer.tsx` - **NEW** Audio playback component with play/pause, seek, progress bar
  - Exposes `seekTo(timeMs)` via ref for click-to-seek from transcript
- `SpeakerDropdown.tsx` - **NEW** Dropdown for selecting/creating speakers
  - Typeahead search with keyboard navigation
  - Inline "Add new" option for creating participants
- `useTranscriptParser.ts` - **NEW** Hook for parsing transcript data

**Settings View** (`src/components/settings/`) - **NEW**:
- `SettingsView.tsx` - User settings and preferences
  - Profile card (name, email, role, Azure AD ID)
  - Plaud Integration settings (enable sync toggle, bearer token input)
  - Save changes with toast feedback

**Jobs View** (`src/components/jobs/`):
- `JobsView.tsx` - Job monitoring view with list and details
- `JobsList.tsx` - List of running/completed jobs
- `JobCard.tsx` - Individual job card
- `JobViewer.tsx` - Detailed job log viewer
- `JobsFilterBar.tsx` - Filter controls for job list
- `JobLogEntry.tsx` - Individual log entry component

**Placeholder Views**:
- `LogsPlaceholder.tsx` - Future logs UI (Phase 2)
- `SearchPlaceholder.tsx` - Future search UI (Phase 2)

### Service Layer (`src/services/`)

**API Client**:
- `api.ts` - Axios instance with MSAL token acquisition
  - Development: proxies through Vite dev server
  - Production: uses relative URLs (served by Flask backend)
  - Request interceptor: acquires Azure AD access token via MSAL
    - Silent acquisition with cached/refresh tokens
    - Falls back to interactive popup if silent fails
    - Redirects to login if no accounts exist
  - Response interceptor: handles 401 with login redirect
  - `authEnabled` flag controls whether auth is applied

**Domain Services**:
- `recordingsService.ts` - Recording CRUD operations
- `transcriptionsService.ts` - Fetch transcription data with segments
- `jobsService.ts` - Job monitoring and filtering
- `chatService.ts` - AI chat conversation API
- `versionService.ts` - API version checking
- `userService.ts` - **NEW** Current user profile and settings
  - `getCurrentUser()` - Fetch authenticated user's profile
  - `updatePlaudSettings()` - Update Plaud integration settings
- `participantsService.ts` - **NEW** Participant management
  - `getParticipants()` - List all user's participants
  - `createParticipant()` - Create new participant
  - `searchParticipants()` - Fuzzy search by name
  - `findOrCreateParticipant()` - Helper for speaker assignment

### Custom Hooks (`src/hooks/`)

- `useRecordings.ts` - Fetch and manage recordings list
- `useTranscription.ts` - Fetch transcription data for a recording
- `useJobs.ts` - Fetch and manage jobs list with filtering
- `useJobDetails.ts` - Fetch detailed job logs

### Type System (`src/types/`)

- `models.ts` - **AUTO-GENERATED** from `/shared/Models.ts` via sync script
  - Contains: Recording, Transcription, User, Participant, Tag, TranscriptSegment, etc.
  - Synced before every `dev` and `build` command
- `api.ts` - API-specific types (responses, filters)
- `index.ts` - Exported type definitions

### Utilities (`src/utils/`)

- `dateUtils.ts` - Date formatting helpers
- `formatters.ts` - Duration, file size formatting
- `exportTranscript.ts` - Export transcript to .txt file
- `toast.ts` - Toast notification helpers
- `chatUtils.ts` - Chat-related utilities

### Theme & Styles

- `theme/customTheme.ts` - Fluent UI theme configuration (light theme)
- `styles/globals.css` - Global CSS reset and base styles
- Individual components use Fluent UI `makeStyles` API

## 4. Build, Tooling, and Dependencies

### Build System

**Vite Configuration** (`vite.config.ts`):
- Dev server on port 3000
- Proxy configuration for backend routes:
  - `/api` → `http://localhost:5050`
  - `/plaud` → `http://localhost:5050`
  - `/az_transcription` → `http://localhost:5050`
- Production build outputs to `dist/` directory
- Source maps disabled in production

**TypeScript Configuration**:
- Target: ES2020
- Module: ESNext (bundler mode)
- Strict mode enabled
- JSX: react-jsx (React 18)
- No unused locals/parameters enforcement

### Key Dependencies

**Core Framework** (from `package.json`):
- `react@18.3.1` - UI framework
- `react-dom@18.3.1` - React DOM rendering
- `react-router-dom@7.9.6` - Client-side routing
- `vite@7.2.2` - Build tool and dev server

**Authentication** (NEW):
- `@azure/msal-browser@4.26.1` - Microsoft Authentication Library for SPAs
- `@azure/msal-react@3.0.21` - React hooks and components for MSAL

**UI Library**:
- `@fluentui/react-components@9.72.7` - Microsoft Fluent UI v9
- `@fluentui/react-icons@2.0.314` - Fluent UI icons

**HTTP & State**:
- `axios@1.13.2` - HTTP client
- `react-toastify@11.0.5` - Toast notifications

**Development Dependencies**:
- `typescript@5.9.3` - Type system
- `eslint@9.39.1` - Code linting
- `prettier@3.6.2` - Code formatting
- `@types/react@19.2.4` - React type definitions

### Build Scripts

**NPM Scripts** (from `package.json`):
- `dev` - Sync models, start Vite dev server
- `build` - Sync models, TypeScript compile, Vite build
- `preview` - Preview production build
- `lint` - Run ESLint on .ts/.tsx files
- `format` - Format code with Prettier
- `sync-models` - Manually sync from `/shared/Models.ts`
- `deploy:copy` - Copy build to backend static directory
- `deploy:build-and-copy` - Build and deploy to backend

**Model Sync Script** (`scripts/sync-models.js`):
- Copies `/shared/Models.ts` → `src/types/models.ts`
- Adds auto-generation header with timestamp
- Runs automatically before `dev` and `build`
- Ensures type consistency across frontend/backend

## 5. Runtime Architecture

### Application Flow

**Initialization**:
1. `main.tsx` conditionally wraps `<App />` in `<MsalProvider>` based on `authEnabled`
2. MSAL instance initializes and handles any pending redirect responses
3. `App.tsx` wraps application in FluentProvider (theme) and ToastContainer
4. `MainLayout.tsx` manages view state (transcripts/jobs/settings)

**Authentication Flow** (when `authEnabled=true`):
1. App startup: MSAL instance initializes, processes redirect promise
2. First API call: `api.ts` interceptor calls `getAccessToken()`
3. If no accounts exist: triggers `loginRedirect()` to Azure AD
4. If accounts exist: attempts `acquireTokenSilent()` with cached tokens
5. On token failure: falls back to `acquireTokenPopup()`, then redirect
6. Token added to Authorization header as `Bearer <token>`
7. Backend validates JWT token against Azure AD

**View Routing**:
- No traditional routing library usage in MainLayout
- View switching via state: `activeView` state controls which view renders
- Views: `TranscriptsView`, `JobsView`, `SettingsView`, `SearchPlaceholder`

**Data Flow Pattern**:
1. Custom hooks (useRecordings, useJobs, useTranscription) fetch data via services
2. Services use `apiClient` (Axios instance) to call backend APIs
3. API client automatically acquires and attaches auth tokens
4. Components receive data from hooks, render UI
5. User actions trigger service calls, state updates via hooks

**API Communication**:
- **Development Mode**:
  - Frontend runs on `localhost:3000`
  - Vite proxy forwards `/api`, `/plaud`, `/az_transcription` to `localhost:5050`
  - Set `VITE_AUTH_ENABLED=false` for no-auth development
- **Production Mode**:
  - Frontend served as static files by Flask backend
  - Uses relative URLs (empty `VITE_API_URL`)
  - Set `VITE_AUTH_ENABLED=true` for full Azure AD authentication
  - All requests go to same origin

**State Management**:
- React hooks (useState, useEffect) - no external state library
- Component-local state for UI interactions
- Custom hooks for data fetching and caching
- MSAL manages authentication state in localStorage

### Three-Column Layout (TranscriptsView)

**Left Column**: RecordingsList with search/filter
**Middle Column**: TranscriptViewer with full transcript
**Right Column**: ChatDrawer for AI conversations
- Resizable splitters between columns
- Independent scrolling per column

### Backend Integration

**API Endpoints Used**:
- `GET /api/recordings` - List all recordings
- `GET /api/recording/<id>` - Get recording details
- `GET /api/transcription/<id>` - Get transcription with segments
- `GET /api/recording/<id>/audio-url` - Get audio playback URL
- `GET /api/jobs` - List jobs (with filters)
- `GET /api/jobs/<id>` - Get job details with logs
- `POST /api/chat` - Chat with AI about recordings
- `GET /api/me` - Get current user profile (NEW)
- `PUT /api/me/plaud-settings` - Update Plaud settings (NEW)
- `GET /api/participants` - List user's participants (NEW)
- `POST /api/participants` - Create participant (NEW)
- `GET /api/participants/search` - Search participants by name (NEW)

**Error Handling**:
- API client interceptor logs errors to console
- 401 responses trigger automatic login redirect (when auth enabled)
- Individual services handle error display (toasts)
- No automatic retry logic

## 6. Development Workflows

### Local Development

**Starting Dev Server**:
```bash
npm run dev
# 1. Runs sync-models.js to copy /shared/Models.ts
# 2. Starts Vite dev server on port 3000
# 3. Hot module replacement enabled
```

**Building for Production**:
```bash
npm run build
# 1. Syncs models
# 2. Runs TypeScript compiler (tsc)
# 3. Builds with Vite to dist/
```

**Deploying to Backend**:
```bash
npm run deploy:build-and-copy
# 1. Builds production bundle
# 2. Removes old files from ../backend/frontend-dist/
# 3. Copies new dist/ to ../backend/frontend-dist/
```

### Type Safety Workflow

**Model Synchronization**:
1. Edit models in `/shared/Models.ts` (repository root)
2. Run `npm run sync-models` or trigger via `npm run dev`/`build`
3. TypeScript models auto-synced to `src/types/models.ts`
4. Import from `src/types/models` in components

**Type Checking**:
- Strict TypeScript mode enabled
- No implicit any
- Unused locals/parameters flagged as errors

### Code Quality

**Linting & Formatting**:
```bash
npm run lint      # ESLint check
npm run format    # Prettier format
```

**Development Practices**:
- Component library: Fluent UI v9
- Styling: `makeStyles` API (CSS-in-JS)
- All components and functions have explicit TypeScript types
- Toast notifications for user feedback

## 7. Known Limitations / TODOs

### Feature Gaps (from README.md)

**Phase 1 Complete** ✅:
- Recordings list with metadata
- Search/filter by title/description/date
- Transcript viewer with speaker diarization
- Export transcript functionality
- Three-panel Outlook-style layout
- Jobs monitoring view

**Phase 2 Complete** ✅:
- Azure AD authentication (MSAL integration)
- User settings view with Plaud integration
- Audio playback with click-to-seek from transcript

**Phase 3 Complete** ✅:
- Speaker identification UI (SpeakerDropdown)
- Participant management (participantsService)
- Speaker assignment workflow (inline renaming in TranscriptEntry)

**Remaining Planned**:
- Tag management and filtering
- Advanced full-text search
- Service logs view
- RAG semantic search

### Current State

- **Authentication implemented** - Azure AD via MSAL (toggle with `VITE_AUTH_ENABLED`)
- **Audio playback implemented** - AudioPlayer with seek, integrated with transcript
- **Speaker management implemented** - Create/search participants, assign to transcript entries
- **Settings view implemented** - User profile and Plaud integration settings
- **No state persistence** - all state in memory (except MSAL tokens in localStorage)
- **Placeholder views** - Logs and Search not implemented
- **No tag management** - tags displayed but not editable
- **Limited error handling** - basic console logging, toast for user errors

## 8. Suggested Improvements or Considerations for AI Agents

### Working with This Codebase

**Model Synchronization**:
- Always run `npm run sync-models` after editing `/shared/Models.ts`
- Do NOT edit `src/types/models.ts` directly (auto-generated file)
- Changes to shared models require backend rebuild: `cd ../backend && make build`

**Authentication Considerations**:
- Authentication is controlled by `VITE_AUTH_ENABLED` environment variable
- For local development without auth: set `VITE_AUTH_ENABLED=false`
- For testing auth flow: set `VITE_AUTH_ENABLED=true` with valid Azure AD config
- MSAL instance is a singleton - access via `src/auth/msalInstance.ts`
- Use `useIsAuthenticated()` and `useMsal()` hooks from `@azure/msal-react`
- API client automatically handles token acquisition - no manual token handling needed

**Component Development**:
- Use Fluent UI v9 components from `@fluentui/react-components`
- Follow makeStyles pattern for styling (see existing components)
- Extract reusable logic into custom hooks in `src/hooks/`
- Keep services thin - just API calls, no business logic

**API Integration**:
- Add new API calls to appropriate service file in `src/services/`
- Create custom hook for data fetching patterns
- Use toast notifications for user feedback (`src/utils/toast.ts`)
- Handle loading/error states in components
- API client handles auth automatically - just make requests

**Type Safety**:
- Leverage TypeScript strict mode
- All props should have explicit interface definitions
- Use generated types from `src/types/models.ts` for backend data
- Create custom types in `src/types/api.ts` for API-specific shapes

### Common Patterns

**Data Fetching Hook Pattern**:
```typescript
export function useRecordings() {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch data via service
    // Update state
  }, []);

  return { recordings, loading, error };
}
```

**Service Pattern**:
```typescript
export const recordingsService = {
  async getAll(): Promise<Recording[]> {
    const response = await apiClient.get('/api/recordings');
    return response.data;
  }
};
```

**Component Pattern**:
```typescript
export function MyComponent() {
  const styles = useStyles(); // Fluent UI makeStyles
  const { data, loading, error } = useMyData(); // Custom hook

  if (loading) return <Spinner />;
  if (error) return <ErrorMessage />;

  return <div className={styles.container}>{/* ... */}</div>;
}
```

### Testing Considerations

**Current State**: No test suite implemented
- Consider adding Vitest + React Testing Library
- Component tests for UI logic
- Service mocks for API calls
- Hook tests for data fetching logic

### Deployment Considerations

**Production Build**:
- Ensure backend is configured to serve from `frontend-dist/`
- Static files include assets with hashed filenames
- No source maps in production build
- Vite handles code splitting automatically

**Environment Variables**:
- `VITE_API_URL` - Backend API URL (empty for production, `http://localhost:5050` for dev without proxy)
- `VITE_AUTH_ENABLED` - Enable Azure AD authentication (`true`/`false`)
- `VITE_AZURE_CLIENT_ID` - Azure AD application (client) ID
- `VITE_AZURE_TENANT_ID` - Azure AD tenant ID (or `common` for multi-tenant)
- Add `.env.development` and `.env.production` files as needed

### Architecture Recommendations

**State Management**:
- Current: React hooks only
- Consider: Zustand or React Query for complex state/caching needs
- Jobs view polling could benefit from React Query

**Routing**:
- `react-router-dom` is installed but not actively used
- Could implement proper routing for deep linking to recordings/transcripts

**Error Boundaries**:
- Add React error boundaries for graceful error handling
- Prevent full app crashes from component errors

**Accessibility**:
- Fluent UI components have built-in a11y
- Ensure custom components follow ARIA patterns
- Add keyboard navigation where needed

**Performance**:
- Large recording lists could benefit from virtualization
- Consider React.memo for expensive components
- Lazy load views with React.lazy + Suspense
