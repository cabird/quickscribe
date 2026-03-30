# QuickScribe v3 Frontend - Comprehensive Functionality Analysis

**Date:** 2026-03-24
**Source:** `v3_frontend/` directory analysis
**Purpose:** Complete inventory of all frontend functionality for rewrite planning

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [All Pages & Views](#2-all-pages--views)
3. [UI Component Hierarchy](#3-ui-component-hierarchy)
4. [Data Flow & State Management](#4-data-flow--state-management)
5. [Authentication Flow](#5-authentication-flow)
6. [Audio Playback](#6-audio-playback)
7. [Transcript Display](#7-transcript-display)
8. [Recording Management](#8-recording-management)
9. [People/Speaker Management](#9-peoplespeaker-management)
10. [Speaker Review System](#10-speaker-review-system)
11. [AI Features](#11-ai-features)
12. [Jobs Monitoring](#12-jobs-monitoring)
13. [Settings](#13-settings)
14. [Responsive Design](#14-responsive-design)
15. [Technical Debt & Issues](#15-technical-debt--issues)
16. [Dependencies](#16-dependencies)
17. [API Endpoints Used](#17-api-endpoints-used)
18. [Type System](#18-type-system)

---

## 1. Architecture Overview

### Stack
- **React 18.3.1** with TypeScript 5.9.3
- **Vite 7.2.2** for build/dev server
- **Fluent UI v9** (`@fluentui/react-components` 9.72.7) for component library
- **Axios 1.13.2** for HTTP
- **MSAL** (`@azure/msal-browser` 4.26.1, `@azure/msal-react` 3.0.21) for Azure AD auth
- **react-toastify** 11.0.5 for notifications
- **react-router-dom** 7.9.6 (installed but barely used -- only `BrowserRouter` wrapper and `useSearchParams` in PeopleView)

### Entry Point Chain
```
index.html
  -> main.tsx (conditional MsalProvider wrap based on authEnabled)
    -> App.tsx (BrowserRouter + FluentProvider + ToastContainer)
      -> MainLayout.tsx (navigation + view switching)
```

### View Routing
There is **no URL-based routing**. View switching is done via `activeView` state in `MainLayout`:
- `'transcripts'` -> `TranscriptsView`
- `'people'` -> `PeopleView`
- `'reviews'` -> `SpeakerReviewView`
- `'logs'` -> `JobsView`
- `'search'` -> `SearchPlaceholder`
- `'settings'` -> `SettingsView`

Exception: `PeopleView` uses `useSearchParams` to sync selected participant ID to the URL (`?selected=<id>`), but this is the only URL-aware component.

### File Structure Summary
- 24 TSX component files
- 8 service modules
- 7 custom hooks (useRecordings, useTranscription, useJobs, useJobDetails, useParticipants, useParticipantDetails, usePeopleList, useIsMobile)
- 5 utility modules
- 2 auth modules
- 3 config modules

---

## 2. All Pages & Views

### 2.1 Transcripts View (`TranscriptsView.tsx`)
**The primary view.** Outlook-style three-column layout on desktop.

**Desktop layout:**
- Top: `TopActionBar` (search, filters, selection info, export, refresh)
- Left panel: `RecordingsList` (scrollable list of `RecordingCard` components)
- Splitter: `ResizableSplitter` (drag to resize)
- Right panel: `TranscriptViewer` (header + audio player + transcript entries + optional chat drawer)

**Mobile layout:**
- Shows either list OR detail, not both
- Back button navigation between list and detail
- No splitter on mobile

**State managed:**
- `selectedRecordingId` (single selection for viewing)
- `checkedRecordingIds` (Set<string> for multi-select with checkboxes)
- `searchQuery`, `searchType` ('basic' | 'fulltext'), `dateRange` ('all' | 'week' | 'month' | 'quarter')
- `listPanelWidth` (percentage, 20-60% range)

**Cross-view navigation:** Listens for `navigateToRecording` CustomEvent (dispatched from PeopleView) to select a specific recording.

### 2.2 People View (`PeopleView.tsx`)
**Participant management.** Similar two-panel layout to Transcripts.

**Desktop layout:**
- Top: `PeopleActionBar` (search, sort, group filter, add person, bulk actions)
- Left panel: `PeopleList` (scrollable list of `ParticipantCard` components)
- Splitter: `ResizableSplitter`
- Right panel: `ParticipantDetailPanel` (read-only view with edit mode toggle)

**Mobile layout:** Same list-or-detail pattern as Transcripts.

**Features:**
- Search by displayName, firstName, lastName, aliases, email
- Sort by name, lastSeen, firstSeen (ascending/descending)
- Filter by group (organization)
- Bulk select with checkboxes (Ctrl/Cmd+Click or checkbox)
- Bulk delete with confirmation dialog
- Add new participant dialog
- Edit participant details (inline form)
- "This is me" toggle (only one participant can be marked as user)
- Merge participants dialog
- Delete single participant with confirmation
- View recent recordings for a participant
- Click recording to navigate to Transcripts view

**Dialogs:**
- `AddParticipantDialog` - Create new participant (displayName required, optional: firstName, lastName, email, role, organization, relationship, notes, aliases)
- `DeleteConfirmDialog` - Single or bulk delete confirmation
- `MergeParticipantDialog` - Search and select a secondary participant to merge into the primary; shows merge preview

### 2.3 Speaker Review View (`SpeakerReviewView.tsx`)
**Two sub-views toggled by buttons:** "Pending Reviews" and "Audit Log"

**Pending Reviews sub-view:**
- Left panel: List of recordings with speakers needing review, showing suggest/unknown counts as badges
- Right panel: Speaker cards for the selected recording, each showing:
  - Play button to listen to speaker audio segment
  - Speaker label and current name
  - `SpeakerConfidenceBadge` showing identification status
  - Accept/Reject buttons for suggestions
  - Top candidate chips (clickable to assign)
  - "Assign speaker..." dropdown (search + add new)
  - "Use for training" checkbox
  - Skip/Dismiss button
- Optimistic UI updates with pending/confirmed status indicators
- "Rebuild Profiles" button calls `POST /api/speaker-profiles/rebuild`

**Audit Log sub-view (`AuditLogView.tsx`):**
- Left panel: Chronological list of all speaker identification events
- Right panel: Event details including action type, timestamp, source, similarity, candidates presented
- Play speaker audio button
- Reassign dropdown to change speaker assignment
- "Use for training" checkbox

**Action types tracked:** auto_assigned, accepted, rejected, dismissed, reassigned, training_approved, training_revoked, suggest, unknown

### 2.4 Jobs View (`JobsView.tsx`)
**Plaud sync job monitoring.**

**Desktop layout:**
- Top: `JobsFilterBar` (activity-only toggle, duration filter, status filter, trigger source filter, "Sync Now" button, refresh)
- Left panel: `JobsList` (infinite scroll)
- Splitter: `ResizableSplitter`
- Right panel: `JobViewer` (job details + log entries)

**JobCard shows:** Job ID (first 8 chars), status badge (completed/failed/running), trigger badge (scheduled/manual), start time, duration, activity stats (recordings processed, transcriptions processed, errors)

**JobViewer shows:**
- Full job ID, status, source, start/end times, duration
- Error message if failed
- Stats grid: transcriptions checked/completed, recordings found/downloaded/transcoded/uploaded/skipped, transcriptions submitted, errors, chunks created
- Scrollable log entries (`JobLogEntry`) with timestamp, level (color-coded), message
- Copy logs button

**Filter options:**
- Activity Only toggle (default: on)
- Duration: Any, >=30s, >=1m, >=5m
- Status: All, Completed, Failed, Running, Completed+Failed
- Trigger: Both, Scheduled, Manual

**"Sync Now" button** triggers `POST /api/admin/plaud-sync/trigger`, then refreshes job list after 2 seconds.

### 2.5 Settings View (`SettingsView.tsx`)
Two cards:

**Profile Card (read-only):**
- Name, Email, Role, Member Since, Last Login, User ID, Azure AD ID

**Plaud Integration Card:**
- Enable Plaud Sync toggle
- Bearer Token input (password field with show/hide toggle)
- Help dialog explaining how to get Plaud token (4-step instructions with code block)
- Save Changes button (disabled when no changes or saving)

### 2.6 Search Placeholder (`SearchPlaceholder.tsx`)
Static placeholder text: "RAG Search View - Coming in Phase 2"

---

## 3. UI Component Hierarchy

```
App
  BrowserRouter
    FluentProvider (lightTheme)
      MainLayout
        NavigationRail (desktop: left sidebar / mobile: bottom tab bar)
        [Active View]:
          TranscriptsView
            TopActionBar
            RecordingsList
              RecordingCard (x N)
            ResizableSplitter
            TranscriptViewer
              AudioPlayer
              TranscriptEntry (x N)
                SpeakerDropdown
                SpeakerConfidenceBadge
              ChatDrawer
                ChatMessage (x N)
                ChatInput
          PeopleView
            PeopleActionBar
            PeopleList
              ParticipantCard (x N)
            ResizableSplitter
            ParticipantDetailPanel
            AddParticipantDialog
            DeleteConfirmDialog
            MergeParticipantDialog
          SpeakerReviewView
            [Pending Reviews panel]
              SpeakerConfidenceBadge
              SpeakerAssignDropdown (inline, not shared)
            AuditLogView
              ReassignDropdown (inline, not shared)
          JobsView
            JobsFilterBar
            JobsList
              JobCard (x N)
            ResizableSplitter
            JobViewer
              JobLogEntry (x N)
          SettingsView
          SearchPlaceholder
      ToastContainer
```

### Shared/Reused Components
- `ResizableSplitter` - Used in TranscriptsView, PeopleView, JobsView
- `SpeakerConfidenceBadge` - Used in TranscriptEntry and SpeakerReviewView
- `NavigationRail` - Shared layout component (desktop sidebar + mobile bottom bar)
- `TopActionBar` - Only used in TranscriptsView (PeopleView has its own `PeopleActionBar`)

---

## 4. Data Flow & State Management

### State Architecture
**No external state library.** All state is React hooks (useState, useEffect, useMemo, useCallback).

### Data Fetching Pattern
Custom hooks wrap service calls:

```
Component -> useHook() -> service.method() -> apiClient.get/post() -> Backend API
```

**Hooks:**
| Hook | Service | Fetches | Caching |
|------|---------|---------|---------|
| `useRecordings` | `recordingsService.getAllRecordings()` | All recordings on mount | None, re-fetches on `refetch()` call |
| `useTranscription(id)` | `transcriptionsService.getTranscriptionById(id)` | Single transcription when ID changes | None |
| `useJobs(filters)` | `jobsService.getJobs(filters)` | Paginated jobs, re-fetches when filters change | Appends on loadMore, resets on filter change |
| `useJobDetails(id)` | `jobsService.getJobDetails(id)` | Single job when ID changes | None |
| `useParticipants` | `participantsService.getParticipants()` | All participants on mount | None |
| `useParticipantDetails(id)` | `participantsService.getParticipantById(id)` + `getParticipantRecordings(id)` | Parallel fetch on ID change | None |
| `usePeopleList(...)` | Pure computation (no API) | Filters/sorts participant array | useMemo |
| `useIsMobile` | None (media query) | Viewport width check | matchMedia listener |

### Cross-Component Communication
Uses **CustomEvents on window** for cross-view communication:
- `navigateToRecording` - PeopleView -> MainLayout -> TranscriptsView (navigate to specific recording)
- `recordingDeleted` - TranscriptViewer -> TranscriptsView (clear selection, refetch)
- `transcriptionUpdated` - TranscriptViewer -> useTranscription hook (refetch transcription after speaker update)

### Transcript Parsing
`useTranscriptParser` hook parses transcription data with priority:
1. `transcript_json` (has timestamps, merges consecutive same-speaker phrases)
2. `diarized_transcript` (regex-parsed `SpeakerName: text` format, no timestamps)
3. `text` (plain text fallback, no speaker info)

Returns `TranscriptEntryData[]` with speakerLabel, displayName, text, startTimeMs, endTimeMs.

---

## 5. Authentication Flow

### Configuration
- `authEnabled` flag from `VITE_AUTH_ENABLED` env var
- Client ID from `VITE_AZURE_CLIENT_ID`
- Tenant ID from `VITE_AZURE_TENANT_ID`
- Scope: `api://{clientId}/user_impersonation`

### Flow
1. `main.tsx` conditionally wraps `<App>` in `<MsalProvider>` if `authEnabled`
2. `msalInstance.ts` initializes MSAL PublicClientApplication with top-level `await`
3. `handleRedirectPromise()` processes redirect responses on load
4. `api.ts` request interceptor calls `getAccessToken()` before every API call:
   - If no accounts: triggers `loginRedirect()`
   - If accounts exist: `acquireTokenSilent()` first, fallback to `acquireTokenPopup()`, then redirect
5. Response interceptor: 401 triggers automatic login redirect
6. Token attached as `Bearer <token>` header

### UI
- `NavigationRail` renders user section at bottom:
  - Authenticated: Avatar with name, menu with Sign Out
  - Not authenticated: "Sign In" clickable area
  - Auth disabled: "Guest" placeholder
- No standalone `AuthButton` component is used in the current layout (it exists at `components/auth/AuthButton.tsx` but `NavigationRail` handles auth UI directly via `useMsal()` and `useIsAuthenticated()` hooks)

### Token Storage
MSAL stores tokens in `localStorage` (configured in `msalConfig.cache.cacheLocation`).

---

## 6. Audio Playback

### AudioPlayer Component (`AudioPlayer.tsx`)
- Uses native HTML5 `<audio>` element with `preload="metadata"`
- Exposed via `forwardRef` + `useImperativeHandle` with `AudioPlayerHandle`:
  - `seekTo(timeMs)` - Seek to time and start playing
  - `pause()` - Pause playback
  - `getIsPlaying()` - Check play state
  - `getCurrentTimeMs()` - Get current position

### UI Controls
- Play/Pause button
- Time display: `MM:SS / MM:SS` (current / total)
- Progress bar (clickable to seek)
- Volume: Mute/unmute button + slider (0-1 range)

### Integration with Transcript
- `TranscriptViewer` loads audio URL via `recordingsService.getRecordingAudioUrl(recordingId)` which returns a SAS URL
- Audio player only shown when `audioUrl` exists AND transcript has timestamps
- Each `TranscriptEntry` can:
  - **Play from here**: Click play icon to seek audio to entry's `startTimeMs`
  - **Pause**: If the entry is currently playing (determined by `currentTimeMs` being between `startTimeMs` and `endTimeMs`)
- `onPlayStateChange` callback propagates play state and current time up to TranscriptViewer, which passes it down to every TranscriptEntry

### No Waveform Visualization
There is no waveform/spectrogram display. Just a simple progress bar.

---

## 7. Transcript Display

### TranscriptViewer (`TranscriptViewer.tsx`)
**Header section:**
- Recording title (or original_filename fallback)
- Metadata: date, time, duration, speaker names (from speaker_mapping)
- Action buttons: Chat, Copy transcript, Info popover, Delete
- On mobile: collapsible description section

**Info Popover shows:**
- Recording ID and Transcription ID (with copy buttons)
- Speaker Mapping table: speaker number, name, verified status, participant ID

**Transcript area:**
- List of `TranscriptEntry` components
- Highlighted entry support (yellow background, auto-scroll, 2-second timeout)
- Empty state: "No transcript available"

### TranscriptEntry (`TranscriptEntry.tsx`)
Each entry displays:
- Color-coded left border (6 distinct colors cycling by speaker index)
- Speaker name (colored to match border)
- Full name tooltip if different from display name
- `SpeakerConfidenceBadge` if identification data exists
- Hover icons: Play/Pause (if timestamps), Edit (pencil icon to rename speaker)
- Text content

**Speaker Colors:** Blue, Purple, Green, Amber, Red, Indigo (6 colors, cycling)

### SpeakerDropdown (`SpeakerDropdown.tsx`)
- Positioned absolutely below trigger element
- Text input for search/add
- Filtered list of known speakers (from participants list)
- "Add new" option when typed name doesn't match existing
- Keyboard navigation: Arrow keys, Enter/Tab to select, Escape to close
- Closes on click outside

### SpeakerConfidenceBadge (`SpeakerConfidenceBadge.tsx`)
Renders differently based on `identificationStatus`:
- **`auto`**: Green badge with checkmark and similarity percentage + training toggle (brain icon)
- **`suggest`**: Yellow badge with question mark, suggested name, accept/reject buttons. Clickable to expand top candidates as chips.
- **`unknown`**: Gray badge with "?". Clickable to expand top candidate chips.
- **`dismissed`**: Not rendered (returns null for dismissed in the badge, but handled in review view)

**Candidate chips:** Show participant name + similarity percentage, clickable to assign.

### Speaker Rename Flow
1. User clicks edit icon -> `SpeakerDropdown` opens
2. User selects existing speaker or types new name
3. `handleSpeakerRename` in TranscriptViewer:
   - Optimistic local state update
   - `participantsService.findOrCreateParticipant(name)` - searches, creates if not found
   - `transcriptionsService.updateSpeaker(transcriptionId, label, participantId, true)`
   - Dispatches `transcriptionUpdated` event
   - Toast notification
   - Reverts on error

### Accept/Reject Suggestion Flow
- **Accept**: `transcriptionsService.acceptSuggestion()` -> refetch transcription -> update local mappings
- **Reject**: `transcriptionsService.rejectSuggestion()` -> toast
- **Select candidate**: `transcriptionsService.acceptSuggestion(id, label, participantId)` -> refetch -> update

### Training Toggle
- `transcriptionsService.toggleTraining(transcriptionId, speakerLabel, boolean)` -> toast

### Transcript Export
`exportTranscriptToFile()` creates a .txt file with:
- Title header
- Metadata (date, duration, participants, description)
- Diarized transcript text
- Downloads via blob URL + click

### Copy Transcript
Copies `diarized_transcript || text` to clipboard via `navigator.clipboard.writeText()`.

---

## 8. Recording Management

### RecordingCard (`RecordingCard.tsx`)
Displays:
- Title (or original_filename)
- Date and time (from `recorded_timestamp`)
- Duration and token count
- Speaker names (from `speaker_names` enriched field)
- Description (truncated to 100 chars, full text in tooltip with 1s delay)

**Interactions:**
- Click: Select for viewing
- Ctrl/Cmd+Click: Toggle checkbox selection
- Hover: Show checkbox overlay (top-right)
- Checkbox click: Toggle multi-select

**Visual states:**
- Default: white background, subtle shadow
- Selected (single): Light blue background, left blue border
- Checked (multi): Same as selected
- Hover: Slightly darker background, stronger shadow

### RecordingsList (`RecordingsList.tsx`)
- Scrollable container with percentage-based width
- Loading state: Spinner
- Empty state: "No recordings found"
- No virtualization (renders all recordings)

### Search & Filter (in TopActionBar)
- **Search input**: Filters by title and description (client-side for basic mode)
- **Search type dropdown**: "Basic" (client-side) or "Full-text" (not implemented - passes through all)
- **Date range dropdown**: All, Past Week, Past Month, Past Quarter (client-side filtering)
- **Multi-select info**: Shows count of selected recordings + total token count with warning color > 100k tokens
- **Export button**: Exports selected recording's transcript
- **Refresh button**: Re-fetches recordings

### Delete Recording
- Confirmation via native `confirm()` dialog
- Calls `recordingsService.deleteRecording(id)` (GET request to `/api/delete_recording/<id>`)
- Dispatches `recordingDeleted` CustomEvent
- Toast notification

### No Upload UI
There is no frontend upload functionality. Recordings come from Plaud sync or other backend processes.

---

## 9. People/Speaker Management

### Participant Data Model
```typescript
interface Participant {
  id: string;
  userId: string;
  firstName?: string;
  lastName?: string;
  displayName: string;       // Required, primary display
  aliases: string[];         // Alternative names
  email?: string;
  role?: string;             // Job title
  organization?: string;     // Company/group
  relationshipToUser?: string; // "Colleague", "Client", etc.
  notes?: string;
  isUser?: boolean;          // "This is me" flag (only one allowed)
  firstSeen: string;
  lastSeen: string;
  createdAt: string;
  updatedAt: string;
}
```

### ParticipantCard (`ParticipantCard.tsx`)
- Fluent UI `Persona` component with avatar (colorful, initials-based)
- "Me" badge if `isUser` is true
- Last seen date
- Organization text
- Full name (italic) if different from displayName
- Same selection behaviors as RecordingCard (click, ctrl+click, checkbox)

### ParticipantDetailPanel (`ParticipantDetailPanel.tsx`)
**Read-only mode:**
- Large avatar with initials
- Display name + "Me" badge
- Full name if different
- Action buttons: Merge, Delete, Edit
- Info grid: Email, Role, Group, Relationship, First Seen, Last Seen, ID
- Aliases section (chips)
- Notes section (pre-formatted box)
- Statistics: Total Recordings count
- Recent Recordings list (clickable cards, max 5, "Show all" link if more)

**Edit mode:**
- Inline form replacing read-only fields
- Display name input (required)
- First/Last name, Email, Role, Group, Relationship inputs
- Aliases input (comma-separated)
- Notes textarea
- "This is me" toggle with confirmation dialog when reassigning
- Save/Cancel buttons
- Saving overlay with spinner

### Merge Flow
1. Click "Merge" on detail panel
2. `MergeParticipantDialog` opens with search for secondary participant
3. Visual merge preview: secondary -> primary with arrow
4. Confirm merges: combines aliases, notes, updates timestamps, redirects speaker mappings
5. Calls `participantsService.mergeParticipants(primaryId, secondaryId)`

### FindOrCreateParticipant Logic (`participantsService.ts`)
Used when assigning speakers from transcript:
1. Parse input name into firstName/lastName
2. Search existing participants via `searchParticipants(name, fuzzy=true)`
3. Match by: full name (firstName+lastName), displayName, or firstName for single names
4. If no match: create new participant with displayName, firstName, lastName

---

## 10. Speaker Review System

### Review Queue (`SpeakerReviewView.tsx`)
- Fetches from `GET /api/speaker-reviews?status=all&limit=100`
- Returns `ReviewItem[]` containing recording + transcription pairs with suggest/unknown speakers
- Per-speaker actions:
  - **Accept** suggestion (with optional training flag)
  - **Reject** suggestion (reverts to unknown)
  - **Skip/Dismiss** (permanently mark as dismissed, reduces opacity)
  - **Assign** via inline dropdown (search existing participants or create new)
  - **Training checkbox** for voice profile training
- Audio playback: finds longest segment for speaker from `transcript_json`, plays start-to-end
- Optimistic updates with pending/confirmed status tracking per speaker

### Audit Log (`AuditLogView.tsx`)
- Fetches from `GET /api/speaker-audit?limit=200`
- Chronological list of all identification events
- Detail panel shows: action type, timestamp, source, assigned name, similarity, candidates presented
- Audio playback (fetches transcription on demand to find segments)
- Reassign functionality with search dropdown + training checkbox

### Rebuild Profiles
Button calls `POST /api/speaker-profiles/rebuild` - server-side operation to rebuild all voice profiles.

---

## 11. AI Features

### Chat with Transcript (`ChatDrawer.tsx`)
- Right panel drawer (40% width on desktop, full-screen overlay on mobile)
- System message includes tagged transcript with reference IDs (`[[ref_AB01]]`)
- User sends messages via `ChatInput` (textarea + send button, Enter to send, Shift+Enter for newline)
- Calls `POST /api/ai/chat` with transcription_id(s) and full message history
- Assistant responses rendered in `ChatMessage` with clickable reference links
- References: `[[ref_XX##]]` tags replaced with numbered `[N]` links that:
  - Show tooltip with speaker name + transcript excerpt (200 chars)
  - Click scrolls to and highlights the referenced transcript entry
- Multi-transcript support: sends `transcription_ids` array
- Clear conversation button (keeps system message)
- Minimize/Close buttons

### Multi-Transcript Chat
`handleChatWithSelected` in TranscriptsView is a **TODO** - just logs to console. The chat infrastructure supports multiple transcription IDs but the UI to initiate multi-transcript chat is not wired up.

### AI-Generated Content (Backend-driven, not in UI)
- Recording `description` field is AI-generated (shown read-only)
- Recording `title` field may be AI-generated
- `AnalysisResult[]` type exists in models but there is no UI for viewing/triggering analysis

---

## 12. Jobs Monitoring

### Data Model
```typescript
interface JobExecution {
  id: string;
  status: "running" | "completed" | "failed";
  triggerSource: "scheduled" | "manual";
  startTime: string;
  endTime?: string;
  logs?: JobLogEntry[];
  stats: JobExecutionStats;  // 10 stat counters
  errorMessage?: string;
  duration?: number;
  durationFormatted?: string;
}
```

### JobsList with Infinite Scroll
- Scroll listener on container element
- Triggers `loadMore()` when within 100px of bottom
- `useJobs` hook manages offset-based pagination

### Job Filters
All filters are client-requested (sent as query params to backend):
- `has_activity`: boolean
- `min_duration`: number (seconds)
- `status`: comma-separated string
- `trigger_source`: 'scheduled' | 'manual'
- `sort_by`: 'startTime' (hardcoded)
- `sort_order`: 'desc' (hardcoded)
- `limit`: 50 (hardcoded)

### Log Display
- Monospace font, color-coded by level (debug=blue, info=gray, warning=orange, error=red)
- Timestamp in HH:MM:SS format
- Copy all logs button

---

## 13. Settings

### Profile Section
Read-only display of user data fetched from `GET /api/me`:
- Name, Email, Role, Created At, Last Login, User ID, Azure AD OID

### Plaud Integration
- Enable Sync toggle
- Bearer Token input (password/text toggle)
- Token help dialog with step-by-step instructions for extracting token from Plaud web app
- Save calls `PUT /api/me/plaud-settings` with `{ enableSync, bearerToken }`
- `hasChanges` flag enables Save button only when modified

---

## 14. Responsive Design

### Breakpoint
Single breakpoint at **768px** (`LAYOUT.mobileBreakpoint`).

`useIsMobile()` hook uses `window.matchMedia` with change listener.

### Mobile Navigation
- Desktop: Left sidebar (`NavigationRail`) with hover-to-expand (96px collapsed -> 240px expanded), pin button
- Mobile: Bottom tab bar (56px height) with 6 tabs (Transcripts, People, Reviews, Jobs, Search, Settings), using 20px icons + 10px labels

### Mobile View Patterns
All master-detail views follow the same pattern on mobile:
- Show list OR detail, never both
- Back button bar at top of detail view with truncated title
- Full-width list (100% instead of percentage)
- No ResizableSplitter

### Mobile-Specific Adaptations
- **TranscriptsView**: Mobile back bar, no splitter, full-width list
- **TranscriptViewer**: Smaller header padding, smaller title font, collapsible description with show/hide toggle, full-screen chat overlay instead of side panel
- **TopActionBar**: Wrapped layout, smaller controls, filter row below search
- **PeopleView**: Same list-or-detail pattern
- **SpeakerReviewView**: Full-width list panel, mobile back bar for detail
- **JobsView**: Same pattern
- **NavigationRail**: Renders as bottom bar with safe-area-inset-bottom padding

---

## 15. Technical Debt & Issues

### Architecture Issues

1. **No URL routing**: View switching via state means no deep linking, no browser back/forward, no bookmarkable URLs. `react-router-dom` is installed but barely used.

2. **CustomEvent-based communication**: Cross-view communication uses `window.dispatchEvent(new CustomEvent(...))` which is fragile, not type-safe, and hard to trace. Events used: `navigateToRecording`, `recordingDeleted`, `transcriptionUpdated`.

3. **No caching/state persistence**: Every view mount re-fetches all data. No SWR, React Query, or manual caching. Switching tabs re-fetches everything.

4. **No virtualization**: RecordingsList and PeopleList render all items. Will degrade with large datasets.

5. **Hardcoded colors**: Many components use hardcoded hex colors (#111827, #6B7280, etc.) instead of Fluent UI tokens, breaking theme consistency.

### Code Quality Issues

6. **Duplicated code**: `getInitials()` function is copy-pasted in `ParticipantCard.tsx`, `ParticipantDetailPanel.tsx`, and `MergeParticipantDialog.tsx`. Same for `findSpeakerSegment()` duplicated in `SpeakerReviewView.tsx` and `AuditLogView.tsx`.

7. **Inline dropdown components**: `SpeakerAssignDropdown` and `ReassignDropdown` are defined inline in `SpeakerReviewView.tsx` and `AuditLogView.tsx` respectively, with inline styles (not using makeStyles). These duplicate the `SpeakerDropdown` component's logic but aren't shared.

8. **Template literal class names**: Some components use `` `${styles.a} ${condition ? styles.b : ''}` `` instead of Fluent UI's `mergeClasses()`. Inconsistent with the project's own CLAUDE.md guidance.

9. **Missing error boundaries**: No React error boundaries. Component errors crash the entire app.

10. **Console.log debugging**: Many components have `console.log` statements for debugging (e.g., `[TranscriptEntry] Play clicked`, `[Speaker] Renaming`).

11. **Type safety gaps**: `showToast.apiError` takes `any` type. Some event handlers use `as EventListener` casts.

### Feature Gaps

12. **Full-text search not implemented**: The "Full-text" search type option exists in the UI but does nothing (passes through all results).

13. **Tag management not implemented**: `tagIds` field exists on Recording model, and Tag model is defined, but no UI for managing tags.

14. **Multi-transcript chat not wired**: `handleChatWithSelected` logs to console but doesn't open chat. Infrastructure exists (ChatDrawer supports multiple transcription IDs).

15. **"Show all recordings" link is a TODO**: In ParticipantDetailPanel, the "Show all" link has `// TODO: Navigate to filtered recordings view`.

16. **Delete uses GET endpoint**: `recordingsService.deleteRecording` calls `apiClient.get('/api/delete_recording/...')` instead of DELETE method.

17. **No upload UI**: There's no way to upload recordings from the frontend.

18. **Analysis results unused**: `AnalysisResult` and `AnalysisType` models exist but no UI displays or triggers them.

### Performance Concerns

19. **All recordings fetched at once**: `useRecordings` fetches all recordings with no pagination. Will be slow with hundreds of recordings.

20. **All participants fetched at once**: Same issue with `useParticipants`.

21. **Transcript parser runs on every mapping change**: `useTranscriptParser` re-parses entire transcript JSON when `speakerMappings` object changes.

22. **Audio URL fetched per recording select**: New SAS URL generated every time a recording is selected, even if previously loaded.

---

## 16. Dependencies

### Production Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `react` | 18.3.1 | UI framework |
| `react-dom` | 18.3.1 | React DOM rendering |
| `react-router-dom` | 7.9.6 | Client-side routing (barely used) |
| `@fluentui/react-components` | 9.72.7 | Microsoft Fluent UI v9 component library |
| `@fluentui/react-icons` | 2.0.314 | Fluent UI icons (large package) |
| `@azure/msal-browser` | 4.26.1 | Azure AD authentication for SPAs |
| `@azure/msal-react` | 3.0.21 | React bindings for MSAL |
| `axios` | 1.13.2 | HTTP client |
| `react-toastify` | 11.0.5 | Toast notifications |
| `vite` | 7.2.2 | Build tool (also in dependencies, should be devDep) |
| `@vitejs/plugin-react` | 5.1.1 | Vite React plugin (also should be devDep) |

### Dev Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `typescript` | 5.9.3 | Type checking |
| `eslint` | 9.39.1 | Linting |
| `prettier` | 3.6.2 | Formatting |
| `@types/react` | 19.2.4 | React type definitions |
| `@types/react-dom` | 19.2.3 | React DOM types |
| `@types/react-router-dom` | 5.3.3 | Router types (outdated - v5 types for v7 package) |
| `eslint-config-prettier` | 10.1.8 | ESLint/Prettier integration |
| `eslint-plugin-prettier` | 5.5.4 | Prettier as ESLint rule |

### Notable Dependency Issues
- `vite` and `@vitejs/plugin-react` are in `dependencies` instead of `devDependencies`
- `@types/react-router-dom` is v5.3.3 but `react-router-dom` is v7.9.6
- No test framework (no vitest, jest, or testing-library)

---

## 17. API Endpoints Used

### Recordings
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/recordings` | `getAllRecordings()` | `useRecordings` |
| GET | `/api/recording/:id` | `getRecordingById()` | Not currently called |
| GET | `/api/recording/:id/audio-url` | `getRecordingAudioUrl()` | `TranscriptViewer`, `SpeakerReviewView`, `AuditLogView` |
| PUT | `/api/recording/:id` | `updateRecording()` | Not currently called |
| GET | `/api/delete_recording/:id` | `deleteRecording()` | `TranscriptViewer` |

### Transcriptions
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/transcription/:id` | `getTranscriptionById()` | `useTranscription`, `TranscriptViewer` |
| POST | `/api/transcription/:id/speaker` | `updateSpeaker()` | `TranscriptViewer` |
| POST | `/api/transcription/:id/speaker/:label/accept` | `acceptSuggestion()` | `TranscriptViewer`, `SpeakerReviewView` |
| POST | `/api/transcription/:id/speaker/:label/reject` | `rejectSuggestion()` | `TranscriptViewer`, `SpeakerReviewView` |
| POST | `/api/transcription/:id/speaker/:label/dismiss` | `dismissSpeaker()` | `SpeakerReviewView` |
| POST | `/api/transcription/:id/speaker/:label/training` | `toggleTraining()` | `TranscriptViewer`, `SpeakerReviewView`, `AuditLogView` |
| POST | `/api/transcription/:id/speaker/:label/reassign` | via `speakerReviewService` | `AuditLogView` |
| POST | `/api/transcription/:id/reidentify` | `reidentify()` | Not currently called |

### Participants
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/participants` | `getParticipants()` | `useParticipants`, `TranscriptViewer`, `SpeakerReviewView`, `AuditLogView` |
| POST | `/api/participants` | `createParticipant()` | `PeopleView`, `participantsService.findOrCreateParticipant` |
| GET | `/api/participants/search?name=...&fuzzy=true` | `searchParticipants()` | `findOrCreateParticipant` |
| GET | `/api/participants/:id` | `getParticipantById()` | `useParticipantDetails` |
| GET | `/api/participants/:id/recordings` | `getParticipantRecordings()` | `useParticipantDetails` |
| PUT | `/api/participants/:id` | `updateParticipant()` | `PeopleView` |
| DELETE | `/api/participants/:id` | `deleteParticipant()` | `PeopleView` |
| POST | `/api/participants/:primaryId/merge/:secondaryId` | `mergeParticipants()` | `PeopleView` |

### AI/Chat
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| POST | `/api/ai/chat` | `chatService.chat()` | `ChatDrawer` |

### Speaker Reviews
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/speaker-reviews` | `getReviews()` | `SpeakerReviewView` |
| GET | `/api/speaker-audit` | `getAuditLog()` | `AuditLogView` |
| POST | `/api/speaker-profiles/rebuild` | `rebuildProfiles()` | `SpeakerReviewView` |

### Jobs/Admin
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/admin/jobs` | `getJobs()` | `useJobs` |
| GET | `/api/admin/jobs/:id` | `getJobDetails()` | `useJobDetails` |
| POST | `/api/admin/plaud-sync/trigger` | `triggerPlaudSync()` | `JobsView` |

### User
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/me` | `getCurrentUser()` | `SettingsView` |
| PUT | `/api/me/plaud-settings` | `updatePlaudSettings()` | `SettingsView` |

### Version
| Method | Endpoint | Service Method | Used By |
|--------|----------|----------------|---------|
| GET | `/api/get_api_version` | `getVersion()` | `NavigationRail` |

---

## 18. Type System

### Source of Truth
Models defined in `/shared/Models.ts` (TypeScript), synced to frontend via `scripts/sync-models.js`:
- Copies to `src/types/models.ts` with auto-generation header
- Runs before `dev` and `build` commands
- **Do not edit `models.ts` directly**

### Key Model Types
| Type | Fields (key) | Used For |
|------|-------------|----------|
| `Recording` | id, title, description, duration, recorded_timestamp, transcription_id, speaker_names, token_count | Recording list/detail |
| `Transcription` | id, diarized_transcript, text, transcript_json, speaker_mapping, analysisResults | Transcript display |
| `Participant` | id, displayName, firstName, lastName, aliases, email, role, organization, isUser | People management |
| `User` | id, name, email, role, plaudSettings | Settings |
| `JobExecution` | id, status, triggerSource, startTime, endTime, logs, stats | Job monitoring |
| `SpeakerMappingEntry` | participantId, displayName, identificationStatus, similarity, topCandidates, useForTraining | Speaker identification |
| `SpeakerMapping` | `{ [speakerLabel: string]: SpeakerMappingEntry }` | Per-transcription speaker data |

### Frontend-Only Types (`types/api.ts`)
- `ApiResponse<T>` - Generic response wrapper
- `PaginatedResponse<T>` - Pagination (not used yet)
- `RecordingFilters` - Search/filter params
- `TranscriptionSegment` - Parsed transcript segment

### Service-Specific Types
- `ChatMessage` (chatService.ts): `{ role, content }`
- `ChatResponse` (chatService.ts): `{ message, usage?, responseTimeMs? }`
- `ReviewItem` (speakerReviewService.ts): `{ recording, transcription, suggestCount, unknownCount }`
- `AuditEntry` (speakerReviewService.ts): Full audit trail entry
- `JobsFilters` (jobsService.ts): Query parameters for job list
- `TranscriptEntryData` (useTranscriptParser.ts): `{ speakerLabel, displayName, text, startTimeMs, endTimeMs }`

---

## Appendix: Configuration Constants

### Layout (`config/styles.ts`)
```typescript
LAYOUT = {
  navRailWidth: 96,           // Collapsed sidebar width (px)
  navRailExpandedWidth: 240,  // Expanded sidebar width (px)
  listPanelWidthPercent: 35,  // Default list panel width (%)
  mobileBreakpoint: 768,      // Mobile breakpoint (px)
  mobileBottomBarHeight: 56,  // Mobile bottom nav height (px)
}
```

### Theme (`theme/customTheme.ts`)
Custom Fluent UI brand variant ("QuickScribe blue") applied via `createLightTheme()`. 16 shades from near-black (#020305) to light (#CDD8EF).

### Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `VITE_API_URL` | Backend API URL | `''` (relative, for production) |
| `VITE_AUTH_ENABLED` | Enable Azure AD auth | `'false'` |
| `VITE_AZURE_CLIENT_ID` | Azure AD client ID | `''` |
| `VITE_AZURE_TENANT_ID` | Azure AD tenant ID | `'common'` |
