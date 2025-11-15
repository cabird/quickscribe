  Overview

  Modern React-based web application for audio transcription management with AI-powered
  features. Built with TypeScript, Vite, and Fluent UI v9 (Microsoft's design system).

  Tech Stack

  - Framework: React 18 with TypeScript (strict mode)
  - Build Tool: Vite
  - UI Library: Fluent UI v9 (@fluentui/react-components)
  - Styling: CSS-in-JS via Fluent UI's makeStyles API
  - State Management: React hooks (useState, useEffect, useRef, useCallback)
  - HTTP Client: Axios (via apiClient in src/services/api.ts)
  - Routing: React Router v6
  - Authentication: MSAL (Microsoft Authentication Library) for Azure AD

  Project Structure

  v3_frontend/
  ��� src/
  �   ��� components/          # React components organized by feature
  �   �   ��� layout/          # App layout components (MainLayout, NavigationRail)
  �   �   ��� recordings/      # Recording management UI
  �   �   ��� transcripts/     # Transcript viewer and chat interface
  �   �   ��� jobs/            # Job execution viewer (admin feature)
  �   ��� hooks/               # Custom React hooks (useRecordings, useJobs, etc.)
  �   ��� services/            # API service layer
  �   �   ��� api.ts           # Axios client configuration (exports apiClient)
  �   �   ��� recordingsService.ts
  �   �   ��� transcriptionService.ts
  �   �   ��� chatService.ts   # Chat with transcript (mock + real)
  �   �   ��� jobsService.ts   # Admin job execution API
  �   ��� utils/               # Utility functions
  �   �   ��� dateUtils.ts     # Date/time formatting
  �   �   ��� formatters.ts    # Display formatting
  �   �   ��� toast.ts         # Toast notifications
  �   �   ��� chatUtils.ts     # Reference ID generation and formatting
  �   ��� types/               # TypeScript type definitions
  �   �   ��� index.ts         # Synced from /shared/Models.ts
  �   ��� App.tsx              # Root component with routing
  �   ��� main.tsx             # Application entry point
  ��� shared/                  # (Root level) Shared models across backend/frontend
  �   ��� Models.ts            # Source of truth for data models
  ��� public/                  # Static assets

  Architecture Patterns

  API Service Layer

  All backend communication goes through service modules in src/services/:
  - Services export functions that return Promises
  - Use the shared apiClient (Axios instance) from api.ts
  - Endpoints follow /api/* pattern
  - Example:
  export const recordingsService = {
    async getRecordings(): Promise<Recording[]> {
      const response = await apiClient.get('/api/recordings');
      return response.data;
    }
  };

  Custom Hooks Pattern

  Hooks encapsulate data fetching and state management:
  - Named use[Feature] (e.g., useRecordings, useJobs)
  - Return state, loading flags, error handling, and refetch functions
  - Use useCallback for memoized functions
  - Example structure:
  export function useRecordings() {
    const [recordings, setRecordings] = useState<Recording[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchRecordings = useCallback(async () => {
      setLoading(true);
      const data = await recordingsService.getRecordings();
      setRecordings(data);
      setLoading(false);
    }, []);

    return { recordings, loading, fetchRecordings };
  }

  Component Styling

  Uses Fluent UI's makeStyles for CSS-in-JS:
  - makeStyles returns a hook that generates atomic CSS classes
  - CRITICAL: Use mergeClasses() utility to combine multiple classes, NOT template literals
  - Access design tokens via tokens object (colors, spacing, typography)
  - Example:
  import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';

  const useStyles = makeStyles({
    container: {
      padding: '24px',
      backgroundColor: tokens.colorNeutralBackground1,
    },
    title: {
      fontSize: tokens.fontSizeBase500,
      fontWeight: tokens.fontWeightSemibold,
    }
  });

  // In component:
  const styles = useStyles();
  <div className={mergeClasses(styles.container, isActive && styles.active)} />

  State Management Philosophy

  - Local state: Component-specific state via useState
  - Lifted state: Shared state lifted to nearest common ancestor
  - No global store: Uses prop drilling and React context where needed
  - Optimistic updates: UI updates immediately, syncs with server after

  Key Features

  1. Recording Management

  Location: src/components/recordings/
  - Upload audio files (drag-and-drop + file picker)
  - Record directly in browser (Web Audio API)
  - List view with search, filter, and pagination
  - Speaker assignment and metadata editing
  - Playback controls with audio preview

  2. Transcription Viewer

  Location: src/components/transcripts/
  - Displays diarized transcripts (speaker-separated)
  - Speaker name mapping from recording metadata
  - Copy to clipboard functionality
  - Fallback to plain text if no diarization available
  - Reference system for chat integration (each paragraph tagged with data-transcript-entry)

  3. Chat with Transcript

  Location: src/components/transcripts/Chat*.tsx
  - Side drawer interface (slides in from right)
  - Stateless chat: full conversation history sent with each request
  - Reference tagging system:
    - Each transcript paragraph has unique ID: ref_XX## (2 letters + 2 digits)
    - Formula: ref_${letter1}${letter2}${index%100} (supports up to 67,600 entries)
    - LLM includes tags inline: [[ref_AB05]]
    - Frontend replaces with clickable superscript links: [1], [2]
  - Clicking reference scrolls to transcript entry and highlights (yellow, 2 seconds)
  - Hover tooltips show preview of referenced text (200 char limit)
  - Clear conversation, minimize, and close controls
  - Chat state persists across re-renders (stored in parent TranscriptViewer)

  Chat Reference System Implementation:
  // Generate ref ID for transcript index
  generateRefId(300)  "ref_AD00"  // Letter pair AD, index 00

  // System message to LLM includes tagged transcript:
  [[ref_AA00]] Speaker 1: Hello everyone...
  [[ref_AA01]] Speaker 2: Hi there...
  [[ref_AA02]] Speaker 1: Let's discuss the project...

  // LLM response includes refs:
  "The project timeline was discussed in [[ref_AA02]] and [[ref_AA05]]."

  // Frontend replaces with clickable links:
  "The project timeline was discussed in [1] and [2]."

  4. Job Execution Viewer (Admin)

  Location: src/components/jobs/
  - Admin-only feature for monitoring Plaud sync jobs
  - Infinite scroll pagination
  - Filtering by status, date range, user
  - Color-coded log levels (DEBUG=blue, INFO=gray, WARNING=orange, ERROR=red)
  - Job stats display (recordings processed, transcriptions completed, errors)
  - Detail view with full log output

  5. Navigation & Layout

  Location: src/components/layout/
  - MainLayout: Main app shell with navigation rail
  - NavigationRail: Vertical icon-based navigation (Recordings, Job Logs, Search)
  - Active view highlighting
  - Responsive layout with flexbox

  Data Flow

  Typical Request Flow

  1. User interacts with UI component
  2. Component calls custom hook (e.g., useRecordings)
  3. Hook calls service function (e.g., recordingsService.getRecordings())
  4. Service uses apiClient to make HTTP request
  5. Backend responds with data
  6. Service returns typed data to hook
  7. Hook updates local state
  8. Component re-renders with new data

  Error Handling

  - Services throw errors on API failures
  - Hooks catch errors and set error state
  - Components display error via showToast.apiError(error)
  - Toast notifications use Fluent UI's toast system

  Model Synchronization

  Shared Models

  Source of Truth: /shared/Models.ts (repository root, outside v3_frontend)
  Frontend Copy: v3_frontend/src/types/index.ts

  Sync Process:
  1. Edit /shared/Models.ts
  2. Backend runs make build to generate Python models
  3. Frontend runs npm run sync-models (automatic before dev/build)
  4. Frontend models updated in src/types/index.ts

  Key Models:
  - Recording: Audio file metadata, upload info, transcription status
  - Transcription: Transcript text, diarization, speaker mapping
  - User: User profile, preferences, Plaud settings
  - JobExecution: Plaud sync job metadata, status, logs (admin)
  - ChatMessage: Chat message with role and content

  API Endpoint Patterns

  All API calls use /api/ prefix:
  - /api/recordings - Recording CRUD operations
  - /api/transcriptions/:id - Get transcription by recording ID
  - /api/ai/chat - Chat with transcript (stateless)
  - /api/admin/jobs - Job execution management (admin only)
  - /api/users/me - Current user profile

  Special Patterns & Gotchas

  1. CSS Class Merging

  WRONG: className={`${styles.base} ${styles.active}`}
  RIGHT: className={mergeClasses(styles.base, styles.active)}

  Fluent UI generates atomic CSS classes that must be merged with the mergeClasses utility to
  avoid class name conflicts.

  2. DOM Queries with Dynamic Classes

  WRONG: document.querySelector(.${styles.container})
  RIGHT: Use data attributes: <div data-container> and
  document.querySelector('[data-container]')

  Fluent UI class names are dynamically generated and unstable across renders.

  3. Safe Field Access

  Always provide fallbacks for optional fields:
  - {recording.title || recording.original_filename}
  - {field && <Component />} for conditional rendering
  - Use TypeScript optional chaining: recording?.description

  4. Date Formatting

  Use utilities from dateUtils.ts:
  - formatDate(timestamp)  "Jan 15, 2024"
  - formatTime(timestamp)  "2:30 PM"
  - formatDuration(seconds)  "5:23"

  5. Toast Notifications

  Import and use from utils/toast.ts:
  import { showToast } from '../../utils/toast';

  showToast.success('Recording uploaded');
  showToast.error('Failed to upload');
  showToast.apiError(error); // Auto-formats API errors
  showToast.warning('No changes made');

  6. Infinite Scroll Pattern

  Used in JobsList and RecordingsList:
  const observer = useRef<IntersectionObserver>();
  const lastItemRef = useCallback((node: HTMLElement | null) => {
    if (loading) return;
    if (observer.current) observer.current.disconnect();
    observer.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore) {
        loadMore();
      }
    });
    if (node) observer.current.observe(node);
  }, [loading, hasMore, loadMore]);

  Development Workflow

  Running Locally

  cd v3_frontend
  npm install
  npm run dev  # Starts dev server on http://localhost:5173

  Building for Production

  npm run build  # Output to dist/
  npm run preview  # Preview production build

  Type Checking

  npm run typecheck  # TypeScript type checking

  Model Sync

  npm run sync-models  # Sync from /shared/Models.ts

  Environment Configuration

  .env File

  VITE_API_URL=http://localhost:5000  # Backend API URL
  VITE_AZURE_CLIENT_ID=your-client-id  # Azure AD app ID

  Note: Vite requires VITE_ prefix for environment variables to be exposed to frontend code.

  Authentication Flow

  1. User loads app  MSAL checks for existing session
  2. If not authenticated  Redirect to Azure AD login
  3. User logs in  Azure redirects back with auth code
  4. MSAL exchanges code for access token
  5. Frontend stores token, includes in API requests (Authorization: Bearer <token>)
  6. Backend validates token with Azure
  7. User info stored in CosmosDB on first login

  Common Tasks for Developers

  Adding a New Feature

  1. Create types in /shared/Models.ts (if needed)
  2. Run make build in backend, npm run sync-models in frontend
  3. Create service in src/services/ with API calls
  4. Create custom hook in src/hooks/ for state management
  5. Create components in src/components/[feature]/
  6. Add route in App.tsx (if top-level view)
  7. Update NavigationRail.tsx (if adding to nav)

  Adding a New API Endpoint Integration

  1. Define types in /shared/Models.ts
  2. Add service function in appropriate src/services/*.ts file
  3. Use apiClient.get/post/put/delete with /api/ prefix
  4. Handle errors with try/catch and showToast.apiError()
  5. Create/update hook to manage state
  6. Update component to use hook

  Debugging Tips

  - Check browser console for errors
  - Use React DevTools to inspect component state
  - Network tab to verify API requests/responses
  - Check that apiClient is imported correctly (not default export)
  - Verify endpoint paths include /api/ prefix
  - Check that types match backend responses

  Known Issues & Workarounds

  1. Fluent UI class name warnings: Always use mergeClasses(), never template literals
  2. State loss on re-render: Lift state to parent component if it needs to persist across
  unmount/remount
  3. Optional chaining needed: Backend may return null/undefined for optional fields
  4. Date parsing: Backend returns ISO strings, parse with new Date() before displaying

  Performance Considerations

  - Infinite scroll prevents loading thousands of items at once
  - useCallback prevents unnecessary re-renders in hooks
  - Memoization with useMemo for expensive computations
  - Lazy loading for routes (can be added with React.lazy)
  - Image/audio optimization handled by browser

  Security Notes

  - All API requests require authentication token
  - CSRF protection via token-based auth (no cookies)
  - XSS prevention: React escapes content by default
  - File upload validation on backend (frontend does basic checks)
  - No sensitive data in localStorage (tokens in memory only via MSAL)

  ---
