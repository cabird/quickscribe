# QuickScribe Frontend Architecture

<!-- Last updated for commit: 0b5c14dba1691c16fd9cfef10ae6bccfd3490170 -->

## Overview

This document describes the complete architecture of the new QuickScribe frontend, built from scratch to replace the existing Mantine-based frontend with a modern, well-structured application that matches the provided UI mockup while preserving all existing functionality.

## Technology Stack

### Core Technologies
- **React 18** - Modern React with hooks and functional components
- **TypeScript** - Full type safety throughout the application
- **Vite** - Fast development server and build tool
- **Tailwind CSS** - Utility-first CSS framework with glassmorphism design
- **Lucide React** - Modern icon library replacing Fluent UI
- **Zustand** - Lightweight state management
- **React Router v6** - Client-side routing
- **Axios** - HTTP client for API communication

### Development Tools
- **PostCSS** - CSS processing with Mantine preset
- **ESLint** - Code linting
- **TypeScript Compiler** - Type checking and compilation

## Project Structure

```
frontend_new/
├── src/
│   ├── api/                    # API client functions
│   │   ├── recordings.ts       # Recording CRUD operations
│   │   ├── tags.ts            # Tag management operations
│   │   └── plaud.ts           # Plaud device sync and progress monitoring
│   ├── components/            # React components
│   │   ├── Layout/            # Application layout components
│   │   │   ├── AppLayout.tsx          # Main app shell with sidebar/content
│   │   │   ├── Sidebar.tsx            # Tabbed sidebar navigation
│   │   │   ├── MainContent.tsx        # Main content area with filtering
│   │   │   ├── UploadTab.tsx          # File upload interface
│   │   │   ├── BrowseTab.tsx          # Filtering and search interface
│   │   │   └── SettingsTab.tsx        # Application settings
│   │   ├── RecordingCard/     # Recording display components
│   │   │   └── RecordingCard.tsx      # Enhanced recording card with actions
│   │   ├── AIWorkspace/       # Enhanced AI analysis workspace
│   │   │   ├── AIWorkspaceModal.tsx   # Main modal container with resizable layout
│   │   │   ├── TranscriptPanel.tsx    # Transcript display with header
│   │   │   ├── AnalysisPanel.tsx      # Tabbed analysis container
│   │   │   ├── TabNavigation.tsx      # Dynamic tab management with badges
│   │   │   ├── ToolsTab.tsx          # Enhanced analysis tool grid
│   │   │   ├── ResultsOverviewTab.tsx # Analysis results dashboard
│   │   │   ├── ResultTab.tsx         # Individual analysis display
│   │   │   ├── ResizableHandle.tsx   # Panel resize component
│   │   │   └── mockAnalysisData.ts   # Mock data for development
│   │   └── Tags/              # Tag management components
│   │       ├── TagBadge.tsx           # Color-coded tag display
│   │       └── TagManager.tsx         # Tag CRUD interface
│   ├── stores/                # Zustand state management
│   │   ├── useRecordingStore.ts       # Recording state and operations
│   │   ├── useTagStore.ts             # Tag state and operations
│   │   └── useUIStore.ts              # UI state (filters, modals, etc.)
│   ├── types/                 # TypeScript type definitions
│   │   └── index.ts                   # All application types
│   ├── utils/                 # Utility functions
│   │   └── index.ts                   # Helper functions and formatters
│   ├── App.tsx                # Root application component
│   └── main.tsx               # Application entry point
├── public/                    # Static assets
├── dist/                      # Build output
├── package.json               # Dependencies and scripts
├── vite.config.ts            # Vite configuration with proxy
├── tsconfig.json             # TypeScript configuration
├── postcss.config.cjs        # PostCSS with Mantine preset
├── README.md                 # Usage and setup instructions
└── ARCHITECTURE.md           # This document
```

## Component Architecture

### Layout System

**AppLayout.tsx** - Main application shell
- Provides the overall layout structure using Mantine's `AppShell`
- Manages sidebar/main content split (340px sidebar width)
- Handles responsive behavior for mobile devices
- Loads initial data (recordings and tags) on mount
- Maintains the existing `recordingUpdated` event system for backward compatibility

**Sidebar.tsx** - Navigation and branding
- Displays QuickScribe logo with orange accent
- Tab-based navigation (Upload, Browse, Settings)
- Responsive tab switching with visual indicators
- Uses Mantine's design tokens for consistent styling

**MainContent.tsx** - Primary content display
- Grid/List view toggle for recordings
- Real-time filtering based on UI store state
- Responsive grid layout (1-3 columns based on screen size)
- Empty state handling for no recordings/filtered results

### Tab Components

**UploadTab.tsx** - File upload interface
- Mantine Dropzone for drag-and-drop file uploads
- Processing options (auto-transcribe, speaker ID, noise removal)
- Auto-tagging preferences
- Plaud device sync integration with real-time progress monitoring
- Optimistic UI updates during upload

**BrowseTab.tsx** - Filtering and search
- Status-based filtering (All, Recent, Processing, Completed)
- Tag-based filtering with real-time counts
- Search functionality across recording titles
- Tag management modal integration
- Active filter indicators

**SettingsTab.tsx** - Application preferences
- Transcription settings toggles
- Tagging preferences
- Notification settings
- Appearance options (dark mode ready)
- Uses Mantine Switch components

### Recording Management

**RecordingCard.tsx** - Enhanced recording display
- Status badges with color coding
- Tag display with remove functionality
- Action menu with view/download/delete options
- Real-time transcription status polling
- AI indicators for completed transcriptions
- Optimistic updates for tag operations
- Workspace access button

### AI Analysis Workspace

The AI Workspace has been completely redesigned with a sophisticated tabbed interface and resizable layout system.

**AIWorkspaceModal.tsx** - Main workspace container
- Resizable two-panel layout (transcript + analysis)
- State management for analysis results and panel sizing
- Optimistic UI updates for analysis execution
- Integration with mock data system for development

**TranscriptPanel.tsx** - Enhanced transcript display
- Recording header with metadata, tags, and status
- Scrollable transcript content with speaker formatting
- Copy transcript functionality
- View full transcript option
- AI Enhance button for post-processing (title, description, speaker names)

**AnalysisPanel.tsx** - Tabbed analysis container
- Dynamic tab management based on completed analyses
- Auto-navigation to result tabs after completion
- State management for active tab and content
- Coordinated workflow between tools and results

**TabNavigation.tsx** - Dynamic tab system
- Always-visible Tools and Results tabs
- Dynamic tabs for completed analyses (Summary, Keywords, etc.)
- Badge system showing analysis count
- Status indicators (dots) for completed analyses
- Hover effects for better UX

**ToolsTab.tsx** - Enhanced analysis tool grid
- Six analysis types: Summary, Keywords, Q&A, Sentiment, Action Items, Topic Detection
- Visual status indicators (completed ✓, running ⏳, idle)
- Hover effects with color changes and elevation
- Disabled state for running analyses
- Responsive grid layout

**ResultsOverviewTab.tsx** - Analysis dashboard
- Card-based layout for completed analyses
- Clickable cards with hover effects
- Time-based sorting (most recent first)
- Preview text with truncation
- Navigation to individual analysis tabs

**ResultTab.tsx** - Individual analysis display
- Markdown-style formatting for analysis content
- Action buttons (Copy, Export, Re-run, Delete)
- Error state handling for failed analyses
- Pending state for in-progress analyses
- Rich text formatting with headers, lists, and emphasis

**ResizableHandle.tsx** - Panel resize functionality
- Horizontal drag handle between transcript and analysis panels
- Smooth resize interaction with constraints (150px min, 70% max)
- Visual feedback on hover and drag
- Preserves user's preferred layout

**Data Architecture:**
```typescript
interface AnalysisResult {
  analysisType: 'summary' | 'keywords' | 'sentiment' | 'qa' | 'action-items' | 'topic-detection';
  content: string;
  createdAt: string;
  status: 'pending' | 'completed' | 'failed';
  errorMessage?: string;
}

interface Transcription {
  // ... existing fields
  analysisResults?: AnalysisResult[];
}
```

**User Experience Enhancements:**
- **Resizable Layout**: User controls transcript vs analysis space (150px-70% range)
- **Optimistic UI**: Immediate pending state when starting analyses
- **Smart Navigation**: Auto-switches to results after completion
- **Visual Feedback**: Hover effects on all interactive elements
- **Status Management**: Clear indicators for tool states and analysis progress
- **Workflow Integration**: Seamless flow from tools → overview → detailed results

### Progress Monitoring System

**Real-Time Sync Progress (UploadTab.tsx)**
- **Progress UI Display**: Inline progress display below sync button
- **Status Messaging**: Clear communication of queue vs processing states
- **Progress Bars**: Visual progress indicators when total count is known
- **Error Handling**: Displays failed recordings with specific error messages
- **Multi-Device Recovery**: Automatically resumes monitoring on app load
- **Polling Strategy**: 10-second intervals with intelligent cleanup

**Progress Flow:**
```typescript
// On component mount - check for active sync
useEffect(() => {
  const checkForActiveSync = async () => {
    const activeSync = await checkActiveSync();
    if (activeSync.has_active_sync) {
      setSyncToken(activeSync.sync_token);
      setSyncProgress(activeSync.progress);
      startPolling(activeSync.sync_token);
    }
  };
  checkForActiveSync();
}, []);

// Real-time polling with automatic cleanup
const startPolling = (token: string) => {
  const interval = setInterval(async () => {
    const progress = await getSyncProgress(token);
    setSyncProgress(progress);
    
    if (progress.status === 'completed' || progress.status === 'failed') {
      stopPolling();
      if (progress.status === 'completed') {
        refreshRecordings();
      }
    }
  }, 10000);
};
```

**Conflict Resolution:**
- 409 errors automatically resume existing sync monitoring
- Prevents multiple concurrent sync operations
- Graceful handling of transcoder downtime

### Tag System

**TagBadge.tsx** - Tag display component
- Color-coded visual representation
- Optional remove functionality
- Size variants (xs, sm, md, lg)
- Consistent styling across contexts

**TagManager.tsx** - Tag CRUD interface
- Create new tags with color selection
- Edit existing tags (name and color)
- Delete tags with confirmation
- Optimistic UI updates
- Color palette selection

## State Management

### Store Architecture (Zustand)

**useRecordingStore.ts** - Recording state management
```typescript
{
  recordings: Recording[],           // All user recordings
  loading: boolean,                  // Loading state
  error: string | null,             // Error state
  
  // Actions
  setRecordings,                    // Replace all recordings
  addRecording,                     // Add new recording
  updateRecording,                  // Update existing recording
  removeRecording,                  // Remove recording
  
  // Selectors
  getRecordingById,                 // Find by ID
  getRecordingsByTag,               // Filter by tag
  getRecordingsByStatus             // Filter by status
}
```

**useTagStore.ts** - Tag state management
```typescript
{
  tags: Tag[],                      // All user tags
  loading: boolean,                 // Loading state
  error: string | null,             // Error state
  
  // Actions
  setTags,                          // Replace all tags
  addTag,                           // Add new tag
  updateTag,                        // Update existing tag
  removeTag,                        // Remove tag
  
  // Selectors
  getTagById,                       // Find by ID
  getTagsByIds                      // Get multiple by IDs
}
```

**useUIStore.ts** - UI state management
```typescript
{
  sidebarTab: 'upload' | 'browse' | 'settings',  // Active sidebar tab
  
  filters: {                        // Recording filters
    status: string,                 // Status filter
    tags: string[],                 // Selected tag IDs
    search: string                  // Search query
  },
  
  aiWorkspace: {                    // Workspace modal state
    isOpen: boolean,
    recordingId: string | null
  },
  
  viewMode: 'grid' | 'list',        // Display mode
  uploadLoading: boolean            // Upload progress
}
```

## API Integration

### Recording Operations
- `GET /api/recordings` - Fetch all user recordings
- `GET /api/recording/:id` - Fetch single recording
- `GET /api/transcription/:id` - Fetch transcript data
- `POST /api/upload` - Upload new recording
- `POST /az_transcription/start_transcription/:id` - Start transcription
- `GET /api/delete_recording/:id` - Delete recording
- `GET /az_transcription/check_transcription_status/:id` - Poll status
- `POST /api/recording/:id/postprocess` - Trigger AI post-processing (title, description, speakers)

### Tag Operations
- `GET /api/tags/get` - Fetch all user tags
- `POST /api/tags/create` - Create new tag
- `POST /api/tags/update` - Update existing tag
- `GET /api/tags/delete/:id` - Delete tag
- `GET /api/recordings/:recordingId/add_tag/:tagId` - Add tag to recording
- `GET /api/recordings/:recordingId/remove_tag/:tagId` - Remove tag from recording

### Proxy Configuration
Vite development server proxies API calls:
- `/api/*` → `http://localhost:5000/api/*`
- `/plaud/*` → `http://localhost:5000/plaud/*`
- `/az_transcription/*` → `http://localhost:5000/az_transcription/*`

## User Workflows

### Recording Upload Workflow
1. User navigates to Upload tab in sidebar
2. Selects processing options (transcription, speaker ID, etc.)
3. Drops files or clicks to browse
4. Files are uploaded via `/api/upload`
5. Recording appears immediately in main content (optimistic update)
6. Real-time polling begins for transcription status
7. Status badge updates as transcription progresses

### Tag Management Workflow
1. User clicks "Manage" in Browse tab tags section
2. TagManager modal opens showing all existing tags
3. User can:
   - Create new tag with name and color
   - Edit existing tag properties
   - Delete tag (with confirmation)
4. Changes are applied optimistically to UI
5. API calls happen in background
6. Error handling reverts optimistic changes if needed

### AI Analysis Workflow
1. User clicks "📝 Open Recording Workspace" on completed recording
2. AIWorkspaceModal opens with resizable two-panel layout
3. TranscriptPanel loads with recording metadata and fetches transcript
4. User starts with "Tools" tab showing all available analysis types
5. User clicks analysis tool (e.g., "Generate Summary")
6. Tool shows loading state (⏳) and pending result is created
7. Auto-switches to "Results" tab showing progress
8. After 2 seconds, analysis completes and result appears
9. New tab appears for the specific analysis type (e.g., "Summary")
10. User can click result card to view detailed analysis
11. Individual result tab shows formatted content with action buttons
12. User can copy, export, re-run, or delete analysis
13. Results persist in session and can be accessed via tabs

**Enhanced Features:**
- **Panel Resizing**: User drags horizontal handle to adjust transcript/analysis space
- **Multiple Analyses**: Run multiple analysis types, each gets its own tab
- **Result Management**: Edit, copy, export individual analyses
- **Status Tracking**: Visual indicators for tool completion state
- **Dashboard View**: Results tab provides overview of all completed analyses

### Filtering and Search Workflow
1. User interacts with filters in Browse tab:
   - Status filters (All, Recent, Processing, Completed)
   - Tag filters (click to toggle)
   - Search input for text search
2. UI store updates filter state
3. MainContent recalculates filtered recordings
4. Grid updates immediately with new results
5. Filter counts update in real-time

## Design Patterns

### Optimistic Updates
- Tag operations update UI immediately, revert on API failure
- Recording updates happen optimistically with CustomEvent dispatch
- Error boundaries handle failed state recovery

### Real-time Updates
- Transcription status polling every 15 seconds during processing
- CustomEvent system maintains compatibility with existing code
- Automatic status badge updates

### Error Handling
- Comprehensive try-catch blocks in all async operations
- User-friendly error notifications via Mantine notifications
- Graceful degradation for missing data

### Type Safety
- Complete TypeScript coverage with strict mode
- Shared types between components
- API response typing
- Store state typing

## Performance Considerations

### Optimizations Implemented
- Zustand for efficient state updates
- Memoized selectors in stores
- Optimistic UI updates
- Efficient re-renders with proper state structure

### Future Optimizations
- React.memo for expensive components
- useMemo for complex computations
- Dynamic imports for code splitting
- Virtual scrolling for large lists

## Integration Points

### Backward Compatibility
- Maintains existing `recordingUpdated` CustomEvent system
- Preserves all existing API endpoints
- Same error handling patterns
- Compatible notification system

### Extension Points
- Modular component structure for easy feature addition
- Store pattern allows easy state expansion
- API client structure supports new endpoints
- Theme system ready for dark mode

## Deployment

### Development
```bash
npm run dev  # Starts on localhost:5173 with proxy to localhost:5000
```

### Production Build
```bash
npm run build  # Creates optimized bundle in dist/
```

### Integration with Backend
```bash
npm run build
cp -r dist/* ../backend/frontend-dist/
```

## Future Enhancements

### Ready to Implement
- Authentication integration (auth store + route guards)
- Dark mode toggle (Mantine theme switching)
- Real AI analysis endpoints (replace mock analysis tools with backend integration)
- Analysis result persistence (save/load from transcription model)
- Keyboard shortcuts (hotkeys library)
- Advanced filtering (date ranges, duration, etc.)
- Batch analysis operations (run multiple analyses at once)
- Enhanced AI post-processing integration (completed recordings automatically processed)

### Architecture Supports
- Progressive Web App features
- Offline functionality
- Real-time WebSocket updates
- Advanced search with full-text indexing
- Multi-user collaboration features

---

This architecture provides a solid foundation for the QuickScribe frontend, balancing modern development practices with practical requirements for maintainability and extensibility.