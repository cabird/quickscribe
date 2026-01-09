# People/Participants Management Page Implementation Plan

## Overview

Add a new People management page to the v3_frontend with master-detail layout for viewing, editing, and managing participants.

**Navigation**: New "People" icon in NavigationRail using `People24Regular`

**Layout**: Two-panel master-detail (consistent with TranscriptsView)
- Left panel: Searchable, sortable, filterable list of participants
- Right panel: Participant details, stats, and recordings

**Terminology**: "organization" field displayed as "Group" in UI

---

## Architecture Decisions

### URL Synchronization
Selection state stored in URL params (not just React state) for:
- Page refresh preserves selection
- Back button works correctly
- Shareable links to specific participants

Pattern: `?selected=<participantId>` query param, synced with state on mount

### Component Patterns
- **Use Fluent UI `Persona` component** for avatars (handles initials, presence badges automatically)
- **Extract filter/sort logic** into `usePeopleList` hook (keeps PeopleView focused on layout)
- **Keep ParticipantDetailPanel presentational** - fetch data in parent, pass as props (avoids waterfall loading)

### List Performance
For large participant lists (>500), add hard render limit: "Showing top 100 matches" with option to load more.

### "Me" Singleton Constraint
When marking a participant as "Me" (`isUser=true`):
- Check if another participant is already marked as "Me"
- Show confirmation: "This will remove 'Me' status from [Current Name]"
- Backend should enforce only one isUser=true per userId

### Merge Strategy
Use "fill-empty-only" approach:
- Primary's non-null fields are kept
- Secondary's fields only fill in where Primary is null/empty
- Aliases are combined (union)
- Notes are concatenated

---

## Phase 1: List with Search, Sort, Filter

### New Files to Create

| File | Purpose |
|------|---------|
| `src/components/people/PeopleView.tsx` | Main container (master-detail layout) |
| `src/components/people/PeopleList.tsx` | Left panel - scrollable participant list |
| `src/components/people/ParticipantCard.tsx` | Individual list item (uses Persona) |
| `src/components/people/PeopleActionBar.tsx` | Top bar with search, sort, filter controls |
| `src/components/people/ParticipantDetailPanel.tsx` | Right panel (stub - "Select a person") |
| `src/hooks/useParticipants.ts` | Data fetching hook |
| `src/hooks/usePeopleList.ts` | Filter/sort logic hook |

### Files to Modify

| File | Changes |
|------|---------|
| `src/components/layout/NavigationRail.tsx` | Add 'people' to NavItem id type, add navItem |
| `src/components/layout/MainLayout.tsx` | Add 'people' to activeView type, render PeopleView |

### Component Details

**PeopleView.tsx** - State management with URL sync:
```typescript
// URL-synced selection (read on mount, update on change)
const [searchParams, setSearchParams] = useSearchParams();
const selectedParticipantId = searchParams.get('selected');

const setSelectedParticipantId = (id: string | null) => {
  const newParams = new URLSearchParams(searchParams);
  if (id) newParams.set('selected', id);
  else newParams.delete('selected');
  setSearchParams(newParams, { replace: true });
};

// Local UI state
const [searchQuery, setSearchQuery] = useState('');
const [sortBy, setSortBy] = useState<'name' | 'lastSeen' | 'firstSeen'>('name');
const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
const [groupFilter, setGroupFilter] = useState<string>('');
const [listPanelWidth, setListPanelWidth] = useState(35);

// Use extracted hook for filtering/sorting
const { filteredParticipants, uniqueGroups } = usePeopleList(
  participants, searchQuery, sortBy, sortOrder, groupFilter
);
```

**usePeopleList.ts** - Extracted filter/sort hook:
```typescript
export function usePeopleList(
  participants: Participant[],
  searchQuery: string,
  sortBy: 'name' | 'lastSeen' | 'firstSeen',
  sortOrder: 'asc' | 'desc',
  groupFilter: string
): { filteredParticipants: Participant[]; uniqueGroups: string[] } {
  return useMemo(() => {
    // Filter, sort logic here
    // Also extract unique groups for filter dropdown
  }, [participants, searchQuery, sortBy, sortOrder, groupFilter]);
}
```

**ParticipantCard.tsx** - Display using Fluent UI Persona:
```typescript
import { Persona } from '@fluentui/react-components';

<Persona
  name={participant.displayName}
  secondaryText={participant.organization || participant.role}
  presence={participant.isUser ? { status: 'available' } : undefined}
  avatar={{ color: 'colorful' }}
/>
// Plus: lastSeen date, "Me" badge if isUser
```

**PeopleActionBar.tsx** - Controls:
- Search input (filters by displayName, firstName, lastName, aliases)
- Sort dropdown: Name (A-Z), Name (Z-A), Last Seen, First Seen
- Group filter dropdown (populated from uniqueGroups)
- Refresh button

### Phase 1 Implementation Notes ✅ COMPLETED

**Implemented on:** 2026-01-09

**Files Created:**
- `src/hooks/useParticipants.ts` - Data fetching hook with loading/error states
- `src/hooks/usePeopleList.ts` - Filter/sort logic with useMemo optimization
- `src/components/people/PeopleView.tsx` - Main container with URL-synced selection
- `src/components/people/PeopleList.tsx` - Scrollable list with loading/empty states
- `src/components/people/ParticipantCard.tsx` - Card using Fluent UI Persona component
- `src/components/people/PeopleActionBar.tsx` - Search, sort, filter controls
- `src/components/people/ParticipantDetailPanel.tsx` - Stub for Phase 2
- `src/components/people/index.ts` - Barrel export

**Files Modified:**
- `src/App.tsx` - Added BrowserRouter wrapper for URL sync
- `src/components/layout/NavigationRail.tsx` - Added 'people' nav item
- `src/components/layout/MainLayout.tsx` - Added 'people' view rendering

**Code Review Feedback Addressed:**
- Fixed ParticipantCard organization display logic (used strict equality instead of `includes()`)

**Known Limitations (Acceptable for Phase 1):**
- View selection not persisted on page refresh (affects all views equally - architectural issue for future)
- No list virtualization (acceptable for current data sizes, consider for Phase 2 if >500 participants)

---

## Phase 2: Detail Panel (Read-Only)

### Backend Addition Required

**New endpoint**: `GET /api/participants/<id>/recordings`

Location: `backend/src/routes/participant_routes.py`

Returns recordings where participant appears in speaker_mapping, with pagination.

Query params: `limit` (default 5), `offset` (default 0)

Response:
```json
{
  "status": "success",
  "data": [Recording],
  "count": 5,
  "total": 42
}
```

### New Files to Create

| File | Purpose |
|------|---------|
| `src/hooks/useParticipantDetails.ts` | Fetch participant + their recordings |

### Files to Modify

| File | Changes |
|------|---------|
| `src/services/participantsService.ts` | Add `getParticipantById()`, `getParticipantRecordings()` |
| `src/components/people/ParticipantDetailPanel.tsx` | Full implementation (presentational) |
| `src/components/people/PeopleView.tsx` | Add data fetching for selected participant |

### Data Fetching Pattern

Fetch in PeopleView (parent), pass to detail panel as props:
```typescript
// In PeopleView.tsx
const { participant, recordings, totalRecordings, loading } = useParticipantDetails(selectedParticipantId);

<ParticipantDetailPanel
  participant={participant}
  recordings={recordings}
  totalRecordings={totalRecordings}
  loading={loading}
/>
```

### ParticipantDetailPanel Sections (Presentational)

Props:
```typescript
interface ParticipantDetailPanelProps {
  participant: Participant | null;
  recordings: Recording[];
  totalRecordings: number;
  loading: boolean;
}
```

1. **Header**: Persona avatar, displayName, "Me" badge, Edit button (disabled until Phase 3)

2. **Info Grid** (read-only):
   - Full Name (firstName + lastName)
   - Email
   - Role
   - Group (organization)
   - Relationship
   - First Seen / Last Seen
   - Aliases

3. **Notes**: Multi-line text display

4. **Stats**:
   - Total recordings count
   - Most common co-speakers (derived from recordings)

5. **Recent Recordings** (limit 5):
   - Mini cards with title, date
   - Click → navigate to TranscriptsView with that recording selected
   - "Show all (N)" link

### Navigation to TranscriptsView

Use window event dispatch (consistent with existing pattern):
```typescript
window.dispatchEvent(new CustomEvent('navigateToRecording', {
  detail: { recordingId: recording.id }
}));
```
MainLayout listens and switches view + sets selection.

---

## Phase 3: Editing + Add Person + Mark as "Me"

### Files to Modify

| File | Changes |
|------|---------|
| `src/services/participantsService.ts` | Add `updateParticipant()` |
| `src/components/people/ParticipantDetailPanel.tsx` | Add edit mode |
| `src/components/people/PeopleActionBar.tsx` | Add "Add Person" button |
| `src/components/people/PeopleView.tsx` | Handle edit callbacks, refetch |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/components/people/AddParticipantDialog.tsx` | Dialog for creating new participant |

### Edit Mode in ParticipantDetailPanel

State (lifted to PeopleView or local):
```typescript
const [isEditing, setIsEditing] = useState(false);
const [editForm, setEditForm] = useState<UpdateParticipantRequest>({});
```

Editable fields (inline in detail panel):
- displayName (required)
- firstName, lastName
- email
- role
- organization (Group)
- relationshipToUser
- notes (textarea)
- isUser (toggle - "This is me")

**"Me" Toggle Logic**:
```typescript
const handleMeToggle = async (checked: boolean) => {
  if (checked && existingMeParticipant) {
    const confirmed = await showConfirmDialog(
      `This will remove "Me" status from ${existingMeParticipant.displayName}`
    );
    if (!confirmed) return;
  }
  // Proceed with update
};
```

Save flow:
1. Validate displayName not empty
2. Call `updateParticipant(id, editForm)`
3. Show success toast
4. Exit edit mode, refetch data

### AddParticipantDialog

Trigger: "Add Person" button in PeopleActionBar

Form fields: displayName (required), firstName, lastName, email, role, organization, relationshipToUser, notes

On submit: Call `createParticipant()`, close dialog, refetch list, select new participant

---

## Phase 4: Merge, Bulk Operations, Delete

### Files to Modify

| File | Changes |
|------|---------|
| `src/services/participantsService.ts` | Add `deleteParticipant()`, `mergeParticipants()` |
| `src/components/people/ParticipantCard.tsx` | Add checkbox for bulk selection |
| `src/components/people/PeopleView.tsx` | Add checkedParticipantIds state |
| `src/components/people/PeopleActionBar.tsx` | Add bulk action buttons |
| `src/components/people/ParticipantDetailPanel.tsx` | Add Delete and Merge buttons |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/components/people/MergeParticipantDialog.tsx` | Select participant to merge into current |
| `src/components/people/DeleteConfirmDialog.tsx` | Confirmation with warning about unlinking |

### Delete Flow

1. Click Delete button in detail panel header
2. Show confirmation dialog:
   - "Delete [Name]?"
   - "Speaker mappings in recordings will be unlinked (reverted to 'Speaker X')"
3. On confirm: Call `deleteParticipant(id)`, clear selection, refetch list, show toast

### Merge Flow

1. Click Merge button in detail panel
2. Open MergeParticipantDialog
3. Search/select secondary participant to merge INTO current (current = primary)
4. Confirm: "Merge [Secondary] into [Primary]?"
5. Call `mergeParticipants(primaryId, secondaryId)`
6. Secondary deleted, primary updated with combined data (fill-empty-only strategy)
7. Refetch list, show toast

### Bulk Operations

State in PeopleView:
```typescript
const [checkedParticipantIds, setCheckedParticipantIds] = useState<Set<string>>(new Set());
```

ParticipantCard: Checkbox visible on hover (like RecordingCard)

PeopleActionBar shows when selections exist:
- Selection count: "3 selected"
- Clear button
- Delete Selected button (with confirmation for all)

---

## Service Methods Summary

### Phase 1 (existing)
- `getParticipants()` ✓

### Phase 2 (add)
- `getParticipantById(id): Promise<Participant>`
- `getParticipantRecordings(id, limit?): Promise<{recordings, total}>`

### Phase 3 (add)
- `updateParticipant(id, data): Promise<Participant>`

### Phase 4 (add)
- `deleteParticipant(id): Promise<void>`
- `mergeParticipants(primaryId, secondaryId): Promise<Participant>`

---

## Verification

### Phase 1
1. Run `npm run dev`
2. Click People icon in navigation rail
3. Verify list loads with all participants
4. Test search: type name, verify filtering
5. Test sort: change sort option, verify order
6. Test group filter: select a group, verify filtering
7. Click participant: verify selection highlight
8. **Refresh page: verify selection persists (URL sync)**
9. **Use back button: verify navigation works**

### Phase 2
1. Select a participant
2. Verify detail panel shows all fields
3. Verify recordings list shows (requires backend endpoint)
4. Click a recording: verify navigation to TranscriptsView

### Phase 3
1. Click Edit button, verify fields become editable
2. Modify a field, click Save, verify update persists
3. Toggle "This is me" when another is "Me": verify confirmation dialog
4. Click Add Person, fill form, submit, verify new participant appears

### Phase 4
1. Click Delete, confirm, verify participant removed
2. Select participant, click Merge, select another, confirm, verify merge
3. Use checkboxes to select multiple, verify bulk delete works

---

## Required Context Files

**Before starting implementation, read these files to understand patterns and existing code.**

### System Descriptions (Read First)

| File | Purpose |
|------|---------|
| `v3_frontend/SYSTEM_DESCRIPTION.md` | Frontend architecture, components, services, patterns |
| `backend/SYSTEM_DESCRIPTION.md` | Backend API routes, handlers, database patterns |
| `shared_quickscribe_py/SYSTEM_DESCRIPTION.md` | Shared library: CosmosDB handlers, models |

### Frontend - Navigation & Layout

| File | Why Read It |
|------|-------------|
| `v3_frontend/src/components/layout/NavigationRail.tsx` | How nav items are defined, view switching pattern |
| `v3_frontend/src/components/layout/MainLayout.tsx` | How views are rendered based on activeView state |
| `v3_frontend/src/components/layout/ResizableSplitter.tsx` | Drag-to-resize panel divider |
| `v3_frontend/src/components/layout/TopActionBar.tsx` | Action bar pattern (search, filters) |

### Frontend - Master-Detail Pattern (Primary Reference)

| File | Why Read It |
|------|-------------|
| `v3_frontend/src/components/transcripts/TranscriptsView.tsx` | **Main pattern to follow** - state management, layout, filtering |
| `v3_frontend/src/components/transcripts/RecordingsList.tsx` | List component with selection |
| `v3_frontend/src/components/transcripts/RecordingCard.tsx` | Card with selection highlight, checkbox, hover states |
| `v3_frontend/src/components/transcripts/TranscriptViewer.tsx` | Detail panel pattern |

### Frontend - Hooks & Services

| File | Why Read It |
|------|-------------|
| `v3_frontend/src/hooks/useRecordings.ts` | Data fetching hook pattern |
| `v3_frontend/src/hooks/useTranscription.ts` | Single-item fetching hook pattern |
| `v3_frontend/src/services/participantsService.ts` | **Extend this** - existing participant API methods |
| `v3_frontend/src/services/api.ts` | API client configuration, auth handling |

### Frontend - Types

| File | Why Read It |
|------|-------------|
| `v3_frontend/src/types/models.ts` | Participant interface (lines 43-67), API types |
| `v3_frontend/src/types/api.ts` | Request/response type patterns |

### Frontend - Styling

| File | Why Read It |
|------|-------------|
| `v3_frontend/src/config/styles.ts` | APP_COLORS, shared style constants |
| `v3_frontend/src/theme/customTheme.ts` | Fluent UI theme configuration |

### Backend - Participant Routes & Handlers

| File | Why Read It |
|------|-------------|
| `backend/src/routes/participant_routes.py` | Existing participant endpoints (CRUD, search, merge) |
| `backend/src/routes/api.py` | Route patterns, response format |
| `shared_quickscribe_py/cosmos/participant_handler.py` | Database operations for participants |
| `shared_quickscribe_py/cosmos/models.py` | Pydantic Participant model |
| `shared_quickscribe_py/cosmos/recording_handler.py` | For Phase 2: querying recordings by participant |

### Backend - Patterns

| File | Why Read It |
|------|-------------|
| `backend/src/routes/ai_routes.py` | Route decorator patterns, error handling |
| `backend/src/auth.py` | get_current_user() pattern |

---

## Quick Start Checklist

Before coding Phase 1:
1. [ ] Read `v3_frontend/SYSTEM_DESCRIPTION.md`
2. [ ] Read `TranscriptsView.tsx` thoroughly (main pattern)
3. [ ] Read `NavigationRail.tsx` and `MainLayout.tsx`
4. [ ] Read `participantsService.ts` and `types/models.ts`
5. [ ] Understand the Persona component from Fluent UI docs

Before coding Phase 2:
1. [ ] Read `backend/SYSTEM_DESCRIPTION.md`
2. [ ] Read `participant_routes.py` and `participant_handler.py`
3. [ ] Read `recording_handler.py` for querying recordings

---

## Implementation Notes

### Fluent UI Components to Use

```typescript
// From @fluentui/react-components
import {
  Persona,           // Avatar with name, secondary text, presence
  Input,             // Search input
  Dropdown,          // Sort/filter dropdowns
  Button,            // Actions
  Spinner,           // Loading states
  Text,              // Typography
  Card,              // Recording cards in detail panel
  Dialog,            // Add/Delete/Merge dialogs
  Checkbox,          // Bulk selection
  Badge,             // "Me" indicator
} from '@fluentui/react-components';

// From @fluentui/react-icons
import {
  People24Regular,   // Nav icon
  Search20Regular,   // Search icon
  ArrowSort20Regular, // Sort icon
  Filter20Regular,   // Filter icon
  Add20Regular,      // Add person
  Edit20Regular,     // Edit button
  Delete20Regular,   // Delete button
  // etc.
} from '@fluentui/react-icons';
```

### URL Routing Note

The app uses `react-router-dom` but currently doesn't use routes for views. For URL sync:
```typescript
import { useSearchParams } from 'react-router-dom';
```
This requires the app to be wrapped in `<BrowserRouter>` (check `main.tsx` or `App.tsx`).
