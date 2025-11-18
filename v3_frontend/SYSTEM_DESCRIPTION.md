# System Description
**Git commit:** 798b46476c2d52dc8c006a9bbfdf98d8c1623415

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
│   └── vite.svg
├── scripts/                    # Build and automation scripts
│   └── sync-models.js          # Auto-sync TypeScript models from /shared
├── src/                        # Application source code
│   ├── components/             # React UI components
│   │   ├── jobs/               # Job monitoring views (JobsList, JobCard, JobViewer)
│   │   ├── layout/             # Core layout (MainLayout, NavigationRail, TopActionBar, ResizableSplitter)
│   │   ├── logs/               # Placeholder for future logging UI
│   │   ├── search/             # Placeholder for search functionality
│   │   └── transcripts/        # Recording and transcript views (RecordingCard, TranscriptViewer, ChatDrawer)
│   ├── config/                 # Application configuration
│   │   ├── constants.ts
│   │   └── styles.ts
│   ├── hooks/                  # Custom React hooks
│   │   ├── useJobDetails.ts
│   │   ├── useJobs.ts
│   │   ├── useRecordings.ts
│   │   └── useTranscription.ts
│   ├── services/               # API client and service layers
│   │   ├── api.ts              # Axios API client with interceptors
│   │   ├── chatService.ts      # Chat/conversation API
│   │   ├── jobsService.ts      # Job monitoring API
│   │   ├── recordingsService.ts
│   │   ├── transcriptionsService.ts
│   │   └── versionService.ts
│   ├── styles/                 # Global CSS
│   │   └── globals.css
│   ├── theme/                  # Fluent UI theme customization
│   │   └── customTheme.ts
│   ├── types/                  # TypeScript type definitions
│   │   ├── api.ts              # API-specific types
│   │   ├── index.ts            # Exported type definitions
│   │   └── models.ts           # Auto-generated from /shared/Models.ts
│   ├── utils/                  # Utility functions
│   │   ├── chatUtils.ts
│   │   ├── dateUtils.ts
│   │   ├── exportTranscript.ts
│   │   ├── formatters.ts
│   │   └── toast.ts
│   ├── App.tsx                 # Root application component
│   └── main.tsx                # Application entry point
├── API_CONFIGURATION.md
├── DEPLOYMENT.md
├── README.md
├── deploy.sh
├── index.html                  # Vite HTML template
├── package.json
├── package-lock.json
├── tsconfig.json               # TypeScript compiler config
├── tsconfig.node.json
└── vite.config.ts              # Vite build configuration
```

## 2. Languages, Size & Composition

- **Primary Language**: TypeScript (React/TSX)
- **File Count**: 43 TypeScript/TSX source files
- **Total Lines of Code**: ~3,484 lines (excluding node_modules)
- **Configuration**: JSON (package.json, tsconfig.json)
- **Build Tool**: Vite 7.2.2
- **Styling**: CSS + Fluent UI makeStyles API

**File Distribution**:
- Components: 20 TSX files
- Services: 6 TypeScript modules
- Hooks: 4 custom React hooks
- Utils: 5 utility modules
- Configuration & Build: 7 files

## 3. Key Components and Modules

### Core Application Structure

**Entry Points**:
- `main.tsx` - React root rendering with StrictMode
- `App.tsx` - Root component with FluentProvider, theme, and toast container

**Layout System** (`src/components/layout/`):
- `MainLayout.tsx` - Top-level layout with navigation and view switching
- `NavigationRail.tsx` - Left sidebar navigation (transcripts/logs/search views)
- `TopActionBar.tsx` - Top action bar with controls
- `ResizableSplitter.tsx` - Drag-to-resize panel divider

### Feature Modules

**Transcripts View** (`src/components/transcripts/`):
- `TranscriptsView.tsx` - Three-column Outlook-style layout (list, viewer, chat)
- `RecordingsList.tsx` - List of recording cards with filtering
- `RecordingCard.tsx` - Individual recording card with metadata and actions
- `TranscriptViewer.tsx` - Full transcript display with speaker diarization
- `TranscriptEntry.tsx` - Individual transcript segment display
- `ChatDrawer.tsx` - AI chat interface for recordings
- `ChatMessage.tsx` - Individual chat message component
- `ChatInput.tsx` - Chat input with send functionality

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
- `api.ts` - Axios instance with interceptors, base URL configuration
  - Development: proxies through Vite dev server
  - Production: uses relative URLs (served by Flask backend)
  - Interceptors for auth (placeholder) and error handling

**Domain Services**:
- `recordingsService.ts` - Recording CRUD operations
- `transcriptionsService.ts` - Fetch transcription data with segments
- `jobsService.ts` - Job monitoring and filtering
- `chatService.ts` - AI chat conversation API
- `versionService.ts` - API version checking

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
1. `main.tsx` renders `<App />` into `#root` element
2. `App.tsx` wraps application in FluentProvider (theme) and ToastContainer
3. `MainLayout.tsx` manages view state (transcripts/logs/search)

**View Routing**:
- No traditional routing library usage in MainLayout
- View switching via state: `activeView` state controls which view renders
- Views: `TranscriptsView`, `JobsView`, `SearchPlaceholder`

**Data Flow Pattern**:
1. Custom hooks (useRecordings, useJobs, useTranscription) fetch data via services
2. Services use `apiClient` (Axios instance) to call backend APIs
3. Components receive data from hooks, render UI
4. User actions trigger service calls, state updates via hooks

**API Communication**:
- **Development Mode**:
  - Frontend runs on `localhost:3000`
  - Vite proxy forwards `/api`, `/plaud`, `/az_transcription` to `localhost:5050`
- **Production Mode**:
  - Frontend served as static files by Flask backend
  - Uses relative URLs (empty `VITE_API_URL`)
  - All requests go to same origin

**State Management**:
- React hooks (useState, useEffect) - no external state library
- Component-local state for UI interactions
- Custom hooks for data fetching and caching

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
- `GET /api/recording/<id>/audio-url` - Get audio playback URL (planned)
- `GET /api/jobs` - List jobs (with filters)
- `GET /api/jobs/<id>` - Get job details with logs
- `POST /api/chat` - Chat with AI about recordings

**Error Handling**:
- API client interceptor logs errors to console
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

### Code-Level TODOs

**Authentication** (`src/services/api.ts:21`):
```typescript
// TODO: Add Azure AD token when auth is implemented
```
- Azure AD authentication deferred to Phase 2
- Request interceptor has placeholder for Bearer token

**Documentation** (`docs/IMPLEMENTATION_PLAN.md:276`):
- Same TODO mentioned in implementation plan

### Feature Gaps (from README.md)

**Phase 1 Complete** ✅:
- Recordings list with metadata
- Search/filter by title/description/date
- Transcript viewer with speaker diarization
- Export transcript functionality
- Three-panel Outlook-style layout
- Jobs monitoring view

**Phase 2 Planned**:
- Tag management and filtering
- Advanced full-text search
- Service logs view
- RAG semantic search
- Azure AD authentication

**Phase 3 Planned**:
- Speaker identification UI
- Participant management
- Speaker assignment workflow

**Phase 4 Planned**:
- Audio playback with transcript sync
- Click-to-seek timestamps
- Playback controls

### Current State

- **No authentication** - open API access
- **No state persistence** - all state in memory
- **Placeholder views** - Logs and Search not implemented
- **No audio playback** - audio URL endpoint exists but no player
- **No tag management** - tags displayed but not editable
- **Limited error handling** - basic console logging, toast for user errors

## 8. Suggested Improvements or Considerations for AI Agents

### Working with This Codebase

**Model Synchronization**:
- Always run `npm run sync-models` after editing `/shared/Models.ts`
- Do NOT edit `src/types/models.ts` directly (auto-generated file)
- Changes to shared models require backend rebuild: `cd ../backend && make build`

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
- Development: `VITE_API_URL=http://localhost:5050` (or use proxy)
- Production: `VITE_API_URL=` (empty, uses relative URLs)
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
