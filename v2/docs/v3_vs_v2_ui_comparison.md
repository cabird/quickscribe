# V3 vs V2 Frontend UI Comparison

This document catalogs UI functionality and interaction details present in v3 (old) that are missing or different in v2 (new rewrite). Each item is tagged with a priority:
- **HIGH** -- Core UX that users rely on
- **MEDIUM** -- Nice-to-have feature that improves workflow
- **LOW** -- Minor detail or polish item

---

## 1. Transcript Viewer (Recording Detail)

### 1.1 Header / Metadata

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Info popover with IDs and speaker mapping table | Has an `<Info24Regular>` button that opens a Popover showing: Recording ID (copyable), Transcription ID (copyable), and a full speaker mapping table (label, display name, verified status, participant ID with copy button) | **Missing entirely** -- no info popover, no way to view IDs or speaker mapping details | MEDIUM |
| Description collapse on mobile | Description is wrapped in an animated collapsible (max-height transition) with a "Show/Hide details" toggle button on mobile | V2 shows description as a static `line-clamp-2` paragraph, no collapse toggle | LOW |
| Speaker list in meta row | Desktop meta row shows a comma-separated speakers list from `speaker_mapping` | V2 shows speaker names too (from `speaker_mapping`), but as a simple comma-separated string in the meta area -- roughly equivalent | LOW |
| Status badge | V2 shows a status badge (pending, transcoding, etc.) when status is not "ready" | V3 does not show recording status in the header | -- (V2 addition) |
| Tags display | V2 shows colored tag badges below description | V3 has no tag system at all | -- (V2 addition) |
| Analysis templates dropdown (FlaskConical icon) | Not present in V3 | V2 has a dropdown of analysis templates with inline result display | -- (V2 addition) |
| Export button | V3: Export is in the TopActionBar (recording list level), not in transcript header | V2: Export (Download icon) is in the recording detail header -- more accessible | LOW |

### 1.2 Action Buttons

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Chat toggle | Chat button in header toggles side panel (desktop) or full-screen overlay (mobile) | Chat button toggles side panel (desktop) or bottom Sheet at 90vh (mobile) -- functionally equivalent | LOW |
| Copy transcript | Copy button in header, copies `diarized_transcript || text` | Copy button in header, copies `diarized_text || transcript_text` -- equivalent | -- |
| Delete recording | Delete button with `confirm()` dialog | Delete button with AlertDialog component (proper dialog, not browser confirm) -- V2 is better UX | LOW |
| Postprocess/Re-analyze | Not visible as a dedicated button in V3 header (done via other routes) | V2 has analysis templates dropdown in header | -- (V2 addition) |

---

## 2. Transcript Entries

### 2.1 Speaker Display

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Left border color coding | 6 distinct colors: Blue, Purple, Green, Amber, Red, Indigo (hex values) | 6 matching Tailwind colors: blue-500, purple-500, green-500, amber-500, red-500, indigo-500 -- equivalent | -- |
| Speaker name color | Speaker name text uses matching color from SPEAKER_COLORS (darker shade) | Speaker name uses matching Tailwind text color class -- equivalent | -- |
| Full name tooltip | If `fullName` differs from `speaker` (display name), shows a Tooltip with the full name on hover | **Missing** -- no full name tooltip on speaker name | LOW |
| SpeakerConfidenceBadge | Rich inline badge system showing: **auto** (green checkmark + percentage), **suggest** (yellow ? with suggested name + accept/reject buttons + expandable candidate chips), **unknown** (gray ? with expandable candidate chips) | **Missing entirely** -- V2 has no speaker identification status badges, no accept/reject suggestion flow, no candidate chips | HIGH |
| Training toggle (brain icon) | For `auto` status speakers: a brain icon badge that toggles `useForTraining` flag (blue when enabled, gray when disabled) | **Missing** -- no training toggle | MEDIUM |
| Accept/reject suggestion inline | `suggest` status shows inline accept (checkmark) and reject (dismiss) buttons next to the badge | **Missing** -- no suggestion acceptance flow in transcript entries | HIGH |
| Top candidates expandable | Clicking suggest/unknown badge expands a row of candidate chips (up to 5) showing name + similarity %, clickable to assign | **Missing** -- no candidate chips | HIGH |

### 2.2 Hover Actions

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Play/Pause button on hover | Shows Play16Regular/Pause16Regular icon on hover; shows Pause when this entry is currently playing (based on `currentTimeMs` range check) | Shows Play/Pause icon on hover -- functionally equivalent, also tracks `isPlaying` state | -- |
| Edit/Rename speaker button | Shows Edit16Regular icon on hover, opens SpeakerDropdown inline | Shows Pencil icon on hover, opens SpeakerDropdown inline -- equivalent | -- |
| Hover icon visibility | Uses opacity transition (0 to 1) on the entire hover icons container; also stays visible when dropdown is open | Uses conditional rendering (`isHovered &&`) rather than opacity -- functionally similar but less smooth | LOW |

### 2.3 Timestamp Display

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Timestamp column | V3 TranscriptEntry has a `time` prop with a dedicated 50px-wide column for timestamps | V2 does not display timestamps as a visible column in the entry | MEDIUM |

---

## 3. Audio Player

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Play/pause button | Button with Play24/Pause24 icons | Button with Play/Pause lucide icons -- equivalent | -- |
| Time display | `MM:SS / MM:SS` format, monospace, min-width 100px | `M:SS / M:SS` format, monospace -- equivalent | -- |
| Progress bar | Custom div-based progress bar (4px height, click to seek) | Slider component (shadcn/ui) -- V2 is more accessible (proper range input semantics, drag support) | -- (V2 better) |
| Volume slider | Custom range input (`<input type="range">`) with styled thumb | Slider component (shadcn/ui) -- equivalent | -- |
| Mute toggle | Speaker/SpeakerMute icons, toggles mute state, restores previous volume | Volume2/VolumeX icons, toggles mute -- equivalent | -- |
| Conditional display | Only shows when `audioUrl && hasTimestamps` | Only shows when `src` is truthy (no timestamp check) -- V2 shows player even without timestamps | LOW |
| Auto-scroll to playing entry | V3 TranscriptView auto-scrolls to the entry whose time range contains `currentTimeMs` | V2 TranscriptView also auto-scrolls to `playingEntryId` -- equivalent | -- |

---

## 4. Speaker Dropdown

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Search/filter | Filters `knownSpeakers` (string array) by case-insensitive substring match | Filters `participants` (full Participant objects) by display_name, first_name, last_name, aliases, email | -- (V2 richer) |
| "Add new" option | Shows `+ Add "name"` when typed text doesn't match any existing speaker | Shows `+ Add "name"` with Plus icon -- equivalent | -- |
| Keyboard navigation | ArrowDown/ArrowUp cycle through items (wrapping), Enter/Tab selects highlighted, Escape closes | ArrowDown/ArrowUp (clamped, no wrapping), Enter/Tab selects, Escape closes -- equivalent | LOW |
| Auto-focus input | Focuses input via `setTimeout` when dropdown opens | Focuses input via `useEffect` on mount -- equivalent | -- |
| Click-outside-to-close | mousedown listener on document | mousedown listener on document -- equivalent | -- |
| Participant display in list | Shows just the name string | Shows avatar initial circle + name + organization subtitle -- V2 is richer | -- (V2 better) |
| Dropdown placeholder text | `"Search or add speaker..."` | `Rename "{currentName}"...` -- V2 shows context of what's being renamed | -- (V2 better) |

---

## 5. Chat

### 5.1 Layout

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Desktop: side panel | Fixed 40% width via `chatDrawerWidth` state, in a flex container next to transcript | Fixed `w-[40%] min-w-[300px] max-w-[500px]` -- roughly equivalent | -- |
| Mobile: overlay | Full-screen absolute overlay (z-index 200) covering transcript | Bottom Sheet at 90vh via shadcn Sheet component | LOW |
| Header buttons | Clear (Delete24Regular), Minimize (Subtract24Regular), Close (Dismiss24Regular) | Clear (Trash2), Minimize (Minimize2, desktop only), Close (X) -- equivalent | -- |

### 5.2 Reference Links

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Reference format | Uses `[[ref_XX##]]` format, maps refs to transcript entry indices via `generateRefId()` helper, renders as superscript clickable `[N]` links | Uses `[[ref_XX]]` format, maps to entry IDs via regex, renders as inline styled button `[N]` | -- |
| Tooltip on reference hover | Shows tooltip with `"{speaker}: {first 200 chars of text}..."` for each reference | **Missing** -- no tooltip on reference hover, just a title attribute "Click to scroll to referenced transcript section" | MEDIUM |
| Click scrolls to entry | Scrolls to transcript entry and highlights with yellow background for 2 seconds | Scrolls to entry and highlights for 2 seconds -- equivalent | -- |
| Multi-transcript support | Supports passing multiple `transcriptionIds`, labels each entry with `[Transcript N]` prefix in system message | **Missing** -- V2 chat only works with a single `recordingId` | MEDIUM |

### 5.3 Messages

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Message display | User/Assistant icons (Person24/Bot24) with role-colored text, pre-wrap whitespace | User messages as blue bubbles (right-aligned), assistant as gray bubbles (left-aligned) -- different style, both functional | -- |
| Loading indicator | Shows "Thinking..." message with Spinner | Shows animated bouncing dots (...) -- equivalent | -- |
| System message handling | System message is the first message in the array, hidden from display (`.slice(1)`) | No system message in local state; system context handled server-side | -- |

---

## 6. Recording List

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Multi-select with checkboxes | Ctrl/Cmd+Click toggles checkbox; checkbox appears on hover or when checked; dedicated checkbox UI in corner of each card | **Missing entirely** -- no multi-select, no checkboxes | HIGH |
| Selection info bar | Shows count of selected recordings, total token count (with warning if >100k), clear button, "Chat" button to chat with multiple transcripts | **Missing** -- no selection bar | HIGH |
| Search type toggle (basic vs full-text) | Dropdown to switch between basic (title/description) and full-text search | **Missing** -- V2 has only one search input on the list page (basic), full-text is a separate Search page | MEDIUM |
| Date range filter | Dropdown: All, Past Week, Past Month, Past Quarter -- applied client-side | Dropdown: All time, Past week, Past month, Past quarter -- applied via API query param `date_from`. Equivalent | -- |
| Tag filter | Not present in V3 | V2 has tag filter dropdown when tags exist | -- (V2 addition) |
| Export button in action bar | Export button in TopActionBar exports currently selected recording transcript | V2 has export on recording detail page instead | LOW |
| Refresh button | Button in TopActionBar | Button in list action bar -- equivalent | -- |
| Description tooltip on card | Card wrapped in Tooltip (showDelay 1000ms) showing full description when description exists | Tooltip on description text (shadcn Tooltip) -- equivalent | -- |
| Token count on card | Shows token count with NumberSymbol icon | Shows token count with Hash icon -- equivalent | -- |
| Virtual scrolling | Not implemented (renders all cards) | Uses `@tanstack/react-virtual` for efficient rendering of large lists -- V2 is better for performance | -- (V2 better) |
| Upload / Paste buttons | Not present in V3 | V2 has Upload and Paste buttons with dialogs for adding recordings | -- (V2 addition) |
| Resizable splitter | Custom ResizableSplitter component with drag handle | Custom drag-based splitter (mousedown/mousemove/mouseup) -- equivalent | -- |

---

## 7. People View

### 7.1 List Panel

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Search | Dedicated search in PeopleActionBar | Search input in list header -- equivalent | -- |
| Sort controls | Sort by: name, lastSeen, firstSeen with asc/desc toggle | Sort by: name, last_seen, first_seen -- equivalent (V2 missing sortOrder toggle) | LOW |
| Group/Organization filter | Dropdown to filter by unique organizations | **Missing** -- no organization filter in V2 | MEDIUM |
| Bulk selection checkboxes | Ctrl/Cmd+Click toggles checkbox, checkbox on hover; bulk delete of selected participants | **Missing** -- no multi-select on people list | MEDIUM |
| Selection bar | Shows count of selected people, clear button, delete selected button | **Missing** | MEDIUM |
| Refresh button | In PeopleActionBar | **Missing** -- no explicit refresh button (relies on React Query cache) | LOW |
| Resizable splitter | ResizableSplitter between list and detail | Fixed 380px width for list panel -- no resizing | LOW |
| Participant card detail | Shows Persona component (Fluent UI) with avatar, display name, secondary text, "Me" badge, last seen date, organization | Shows initials circle, display name, "Me" badge, organization, relative last seen -- roughly equivalent | LOW |

### 7.2 Detail Panel

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Avatar | Large 72px Avatar with colorful initials | 56px circle with initials -- equivalent | -- |
| Info grid | 2-column grid: Email, Role, Group, Relationship, First Seen, Last Seen, ID (with icons) | 2-column grid: Email, Role, Organization, Relationship, First Seen, Last Seen -- equivalent (V2 missing ID field) | LOW |
| Aliases display | Chips with rounded pill style | Badge components -- equivalent | -- |
| Notes display | Styled box with background color | Styled div with border and muted background -- equivalent | -- |
| Statistics section | Shows "Total Recordings" count | **Missing** -- no statistics section in V2 | MEDIUM |
| Recent recordings | Card list with title + date, clickable (navigates to transcript via CustomEvent) | Card list with title + relative date, clickable (navigates via React Router) -- equivalent, V2 approach is better (proper routing) | -- |
| "Show all" link | When `totalRecordings > recordings.length`, shows "Show all (N)" link | Shows `+N more recordings` text when >5 recordings | LOW |
| Edit mode | Dedicated edit mode with full form (all fields editable), Save/Cancel buttons | Inline edit mode with full form -- equivalent | -- |
| "This is me" toggle | Switch with explanation text; confirmation dialog when changing from existing "Me" participant | Switch with label -- V2 **missing** the confirmation dialog when switching "Me" from another participant | MEDIUM |
| Delete button | In detail header with confirmation dialog | In detail header with AlertDialog -- equivalent | -- |
| Merge button | In detail header, opens MergeParticipantDialog | In detail header, opens MergeDialog -- equivalent | -- |

### 7.3 Merge Dialog

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Merge preview visualization | Shows Persona avatars with arrow: `[Secondary] -> [Primary]` | Shows avatar circles with arrow and "will be removed" / "will be kept" labels -- V2 is more descriptive | -- (V2 better) |
| Search behavior | Shows all participants by default, filters on search | Only shows results when search query is typed (no results on empty query) | LOW |
| Warning text | Shows explanatory text about what merging does (combines aliases, notes, updates timestamps, updates speaker mappings) | V2 dialog description mentions removal but doesn't detail the merge behavior | LOW |

### 7.4 Add Participant Dialog

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Fields | Display Name (required), First/Last Name, Email, Role, Group, Relationship, Aliases, Notes | Display Name (required), First/Last Name, Email, Role, Organization, Aliases, Notes -- V2 missing Relationship field | LOW |
| Saving indicator | Spinner in button text "Creating..." | Button text "Creating..." -- equivalent | -- |

---

## 8. Speaker Review System

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Entire Speaker Review View | Full dedicated view with: pending reviews list showing recordings with suggest/unknown speaker counts, per-speaker review cards with accept/reject/dismiss/reassign actions, audio playback for specific speaker segments, "Rebuild Profiles" button, toggle between "Pending Reviews" and "Audit Log" tabs | **Not implemented at all** -- V2 has no speaker review system | HIGH |
| Review list | Shows recordings needing review with badge counts (N suggested, N unknown) | **Missing** | HIGH |
| Per-speaker review card | Shows speaker label, mapped name, confidence badge, top candidate chips, accept/reject/skip buttons, assign dropdown, training checkbox | **Missing** | HIGH |
| Audio playback for speaker segments | Finds longest audio segment for a speaker from transcript_json, plays just that segment | **Missing** | MEDIUM |
| Audit Log view | Dedicated sub-view showing all speaker identification history: action badges (auto_assigned, accepted, rejected, dismissed, reassigned, etc.), timestamps, source, similarity scores, candidates presented, current assignment, reassign functionality | **Missing** | MEDIUM |
| Rebuild Profiles button | Triggers `speakerReviewService.rebuildProfiles()` to re-run speaker identification | **Missing** | LOW |
| Optimistic updates | Accept/reject/dismiss actions update local state immediately, show "Saving..." / "Confirmed" status per speaker | **Missing** | MEDIUM |

---

## 9. Jobs View

### 9.1 Filter Bar

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| "Activity Only" toggle | Switch to filter jobs that had actual activity (recordings uploaded, transcriptions completed, or errors) | **Missing** -- no activity filter | MEDIUM |
| Duration filter | Dropdown: Any, >=30s, >=1m, >=5m | **Missing** -- no duration filter | LOW |
| Status filter | Dropdown: All, Completed, Failed, Running, Completed+Failed | Dropdown: All status, Completed, Failed, Running -- missing "Completed+Failed" combo option | LOW |
| Trigger filter | Dropdown: Both, Scheduled, Manual | Dropdown: All triggers, Scheduled, Manual -- equivalent | -- |
| Sync Now button | CloudSync icon, triggers `jobsService.triggerPlaudSync()`, shows "Syncing..." state, refreshes list after 2s delay | Play icon, triggers `useTriggerSync()` mutation, refreshes after 2s -- equivalent | -- |
| Refresh button | ArrowClockwise icon | RefreshCw icon -- equivalent | -- |

### 9.2 Job Card

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Job ID display | First 8 chars, monospace, semibold | First 8 chars, monospace -- equivalent | -- |
| Status/trigger badges | Fluent UI Badge with icons (Checkmark, ErrorCircle) and colors | shadcn Badge with variant mapping -- equivalent | -- |
| Date/time display | Full date + time using formatDate/formatTime | Relative time using formatDistanceToNow -- different style, both useful | LOW |
| Duration | Shows formatted duration string | Shows formatted duration or "running..." -- equivalent | -- |
| Activity stats | Shows recordings uploaded, transcriptions completed, errors with icons (Mic, DocumentText, ErrorCircle) | Shows recordings downloaded, transcribed, errors as plain text | LOW |
| Error message | Shows inline error text in red | Not shown on card (only in detail) | LOW |

### 9.3 Job Detail

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Stats grid | 10 specific stats in a labeled grid: transcriptions_checked, completed, recordings_found, downloaded, transcoded, uploaded, skipped, transcriptions_submitted, errors, chunks_created | Dynamic grid showing all numeric keys from `stats` object as cards with formatted labels | -- (V2 more flexible) |
| Copy logs button | Tooltip button in header, copies all logs as formatted text | Copy button in LogViewer header -- equivalent | -- |
| Log viewer | Custom JobLogEntry component with color-coded levels, timestamp + level + message layout | LogViewer component with color-coded levels, timestamp + level + message -- equivalent | -- |
| Log entry count | Not shown | Shows "N log entries" header in LogViewer | -- (V2 addition) |

### 9.4 Load More / Pagination

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Load more | `hasMore` flag with `loadMore` callback for infinite scroll | Not implemented -- loads all jobs at once | LOW |

---

## 10. Settings

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Profile card | Shows: Name, Email, Role, Member Since, Last Login, User ID, Azure AD ID | Shows: Name, Email, Member Since (using plaud_last_sync date), User ID -- missing Role, Last Login, Azure AD ID | LOW |
| Plaud token help dialog | Detailed 4-step instructions dialog (open web.plaud.ai, open console, run localStorage command, copy token) with code block and warning note about token expiration | **Missing** -- no help dialog for Plaud token | MEDIUM |
| Plaud token show/hide | Eye/EyeOff toggle for password field | Eye/EyeOff toggle -- equivalent | -- |
| Enable sync toggle | Switch with label | Switch with label and description text -- V2 has better description | -- |
| Save button disabled state | Disabled when `!hasChanges || saving` | Disabled when `!isDirty || isPending` -- equivalent | -- |
| Last sync display | Not shown in V3 settings | V2 shows "Last sync: {date}" when available | -- (V2 addition) |
| Analysis Templates section | Not present in V3 | V2 has full CRUD for analysis templates (create, edit, delete with confirmation dialog) | -- (V2 addition) |

---

## 11. Navigation

### 11.1 Desktop Sidebar

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Expand/collapse behavior | Hover to expand (width transition 200ms), click pin button to lock open | Click chevron button to toggle collapsed/expanded state | LOW |
| Pin button | Tooltip "Pin/Unpin sidebar", filled/outline pin icon, branded color when active | **Missing** -- no pin functionality, just toggle | LOW |
| Logo | 72x72px image (`quickscribe-icon.png`) + "QuickScribe" text (fades in on expand) | No logo image, just "QuickScribe" text in header | LOW |
| Nav items | 6 items: Transcripts, People, Reviews, Jobs, Search, Settings | 5 items: Recordings, People, Jobs, Search, Settings -- missing Reviews | HIGH (relates to missing Reviews feature) |
| Active item style | Brand background color with white text | White/20 background with white text -- equivalent styling | -- |
| Tooltip on collapsed items | Shows tooltip with item label when sidebar is collapsed | Shows tooltip when collapsed -- equivalent | -- |
| User section | Avatar (colorful), name, email; Menu with sign out option; Login redirect if not authenticated | **Missing** -- no user section, no sign out, no auth display in sidebar | HIGH |
| Version display | Shows API version at bottom of sidebar with tooltip | **Missing** -- no version display | MEDIUM |
| Sidebar background | Fluent UI neutral background with shadow | Solid brand blue (#0078D4) background -- V2 has more distinctive branding | -- |

### 11.2 Mobile Bottom Bar

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| Items | 6 items: Transcripts, People, Reviews, Jobs, Search, Settings | 4 items: Recordings, People, Jobs, Settings (Search excluded) | LOW |
| Active item style | Branded foreground color | Primary color -- equivalent | -- |
| Safe area inset | Includes `paddingBottom: env(safe-area-inset-bottom)` for iPhone notch | Not included -- may cause issues on iOS devices | MEDIUM |

---

## 12. Search

| Feature | V3 | V2 | Priority |
|---------|----|----|----------|
| V3 search | Search is a placeholder view (`SearchPlaceholder.tsx`) -- not actually implemented | V2 has a full dedicated SearchPage with: form submission, full-text search across transcripts, result cards with highlighted snippets, result count | -- (V2 addition) |

---

## 13. New V2 Features (Not in V3)

These are features present in V2 that did not exist in V3 -- not gaps to fill, but new additions:

| Feature | Description |
|---------|-------------|
| Upload dialog | Upload audio files via dialog |
| Paste dialog | Paste transcript text directly |
| Tag system | Tags with colors on recordings, tag filter in list |
| Analysis templates | CRUD for custom analysis prompts, run analysis on recordings |
| Full-text search page | Dedicated search page with snippet highlighting |
| Recording status display | Shows pending/transcoding/transcribing/processing/failed status badges |
| Virtual scrolling | TanStack Virtual for efficient rendering of large recording lists |
| URL-based routing | Uses React Router for all navigation (v3 uses CustomEvents and local state) |

---

## Summary of Critical Gaps (HIGH Priority)

1. **Speaker Review System** -- Entire feature is missing from V2 (pending reviews, accept/reject/dismiss, audit log)
2. **SpeakerConfidenceBadge** -- No speaker identification status display in transcript entries (auto/suggest/unknown badges, candidate chips, accept/reject inline)
3. **Multi-select recordings** -- No checkbox selection, selection bar, token count display, or multi-transcript chat
4. **User section in navigation** -- No avatar, sign out, auth status display in sidebar
5. **Nav item for Reviews** -- Missing from navigation (related to #1)
