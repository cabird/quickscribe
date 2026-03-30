# QuickScribe v2 Frontend Review

**Reviewer**: Claude Opus 4.6 (1M context)
**Date**: 2026-03-24
**Scope**: All `.ts`/`.tsx` files in `v2/frontend/src/` (excluding `ui/` directory), cross-referenced against the backend routers in `v2/backend/src/app/routers/` and the rewrite spec at `v2/docs/REWRITE_SPEC.md`.

---

## 1. Critical Issues

### 1.1 Response envelope mismatch: `SingleResponse<T>` wrapper does not exist in the backend

**Files**: `lib/api.ts`, `lib/queries.ts`, `types/models.ts`, every page that reads `.data`

The frontend wraps every non-list API return in `SingleResponse<T>` (defined as `{ data: T }`), e.g.:

```ts
const { data } = await apiClient.get<SingleResponse<RecordingDetail>>(`/api/recordings/${id}`);
```

The backend returns the model **directly** -- `GET /api/recordings/{id}` has `response_model=RecordingDetail` and `return recording`. There is no `{ data: ... }` wrapper. Every component that does `recordingResponse?.data` will get `undefined` because the actual payload *is* the recording, not an object containing it.

**Affected surfaces**: RecordingDetailPage, PersonDetailPage, JobDetailPage, SettingsPage (user profile), ChatPanel (chat response), all mutations (upload, paste, update, delete-refetch, reprocess, assign speaker, create participant, merge participants, update settings).

**Fix**: Either add middleware on the backend to wrap responses in `{ data: ... }`, or remove the `SingleResponse<T>` wrapper from all frontend API calls and query hooks.

---

### 1.2 `PaginatedResponse` structure mismatch

**Files**: `lib/api.ts` (line 90), `types/models.ts` (line 242-251)

The frontend defines:
```ts
interface PaginatedResponse<T> { data: T[]; meta: { total: number; page: number; per_page: number } }
```

The backend defines:
```python
class PaginatedResponse(BaseModel):
    data: list = []
    total: int = 0
    page: int = 1
    per_page: int = 50
```

Backend sends `{ data: [...], total: N, page: N, per_page: N }`. Frontend expects `{ data: [...], meta: { total, page, per_page } }`. The `data` array will work, but `meta` will be `undefined`. This currently has no visible crash because no component reads `meta` -- but it means pagination is completely non-functional (there is no "load more" or "next page" button anywhere).

---

### 1.3 ChatPanel reads `response.data.message.content` but backend returns `{ message: string }`

**File**: `components/recordings/ChatPanel.tsx` (line 93)

```ts
const response = await chatMutation.mutateAsync({ ... });
setMessages([...newMessages, { role: "assistant", content: response.data.message.content }]);
```

Two problems compound here:
1. `response.data` will be `undefined` (no `SingleResponse` wrapper -- see issue 1.1).
2. Even if the wrapper existed, `response.data.message` is a `string` in the backend (`ChatResponse.message: str`), not a `ChatMessage` object. Accessing `.content` on a string returns `undefined`.

The chat panel will always show `undefined` as the assistant message (or crash if the `.data` access throws).

---

### 1.4 `searchRecordings` calls the wrong endpoint

**File**: `lib/api.ts` (lines 407-421)

```ts
export async function searchRecordings(query, page, perPage) {
  const params = new URLSearchParams({ q: query });
  const { data } = await apiClient.get<PaginatedResponse<RecordingSummary>>(`/api/recordings`, { params });
  return data;
}
```

This sends `GET /api/recordings?q=...` but the backend `list_recordings` endpoint accepts `search`, not `q`. The search parameter will be silently ignored and the user will get an unfiltered list.

The backend has a dedicated `GET /api/recordings/search?q=...` endpoint that performs FTS5 full-text search. The frontend search function should call `/api/recordings/search` instead.

---

### 1.5 `searchParticipants` sends `q` param but backend expects `name`

**File**: `lib/api.ts` (lines 225-233)

```ts
export async function searchParticipants(query: string) {
  const { data } = await apiClient.get<PaginatedResponse<Participant>>(
    `/api/participants/search`, { params: { q: query } },
  );
```

The backend participant search endpoint expects `name` as the query parameter, not `q`. This will return a 422 validation error because `name` is required (`Query(..., min_length=1)`).

---

### 1.6 Analysis templates endpoint path mismatch

**File**: `lib/api.ts` (lines 317-349)

The frontend calls `/api/analysis-templates` but the backend mounts these at `/api/me/analysis-templates` (under the settings router with prefix `/api/me`). All four analysis template endpoints (list, create, update, delete) will return 404.

---

### 1.7 Sync trigger response shape mismatch

**File**: `lib/api.ts` (line 374)

The frontend expects `SingleResponse<SyncRunDetail>` from `POST /api/sync/trigger`. The backend returns `{"run_id": "...", "message": "Sync started"}` with status 202. The `data` extraction will fail, and the return type is completely different from `SyncRunDetail`.

---

### 1.8 Tags endpoint response mismatch

**File**: `lib/api.ts` (lines 247-276)

The frontend expects `PaginatedResponse<Tag>` from `GET /api/tags`, but the backend returns `list[Tag]` (a plain array). This means `fetchTags()` will return an array, not `{ data: [...], meta: {...} }`, and `tagsResponse?.data` will be `undefined` because arrays don't have a `.data` property.

Similarly, `POST /api/tags` and `PUT /api/tags/{id}` return `Tag` directly, not `SingleResponse<Tag>`.

---

## 2. Major Issues

### 2.1 `RecordingsPage` uses `useParams` for `selectedId` but route does not have `:id` param

**File**: `pages/RecordingsPage.tsx` (line 26)

```ts
const { id: selectedId } = useParams<{ id: string }>();
```

The route for RecordingsPage is `<Route path="recordings" element={<RecordingsPage />} />`. This route does not include an `:id` parameter, so `selectedId` will always be `undefined`. The desktop split-view detail panel will never show because the condition `selectedId ? <RecordingDetailPage /> : <placeholder>` always evaluates to the placeholder.

The `recordings/:id` route renders `RecordingDetailPage` directly, not through `RecordingsPage`. So the intended desktop list+detail pattern is broken -- clicking a recording navigates to a full-page detail view even on desktop.

The same issue applies to `PeoplePage` (line 38) and `JobsPage` (line 22).

**Fix**: Either use nested routes (`recordings` with an `Outlet` for `recordings/:id`) or use a `useMatch`/location-based approach to read the id from the URL.

---

### 2.2 Date range filter is non-functional

**File**: `pages/RecordingsPage.tsx` (lines 28, 101-111)

The `dateRange` state is maintained and rendered as a dropdown, but it is never passed to the `useRecordings` hook or included in the API request. Selecting "Past week" / "Past month" etc. does nothing.

---

### 2.3 Sync runs `trigger` filter is silently ignored by backend

**File**: `pages/JobsPage.tsx` (line 25), `lib/api.ts` (line 387)

The frontend sends a `trigger` query param to `GET /api/sync/runs`, but the backend endpoint only accepts `status` as a filter parameter. The trigger filter dropdown will appear functional but have no effect on the results.

---

### 2.4 Upload progress is faked

**File**: `components/recordings/UploadDialog.tsx` (lines 155-162)

```tsx
{uploadMutation.isPending && (
  <div className="space-y-1">
    <Progress value={50} />
    <p>Uploading...</p>
  </div>
)}
```

The progress bar is hardcoded to 50%. For large audio files (up to 300MB per the UI text), users will see a static halfway progress bar with no indication of actual progress. This should use axios' `onUploadProgress` callback to report real progress, or the progress bar should be replaced with an indeterminate spinner.

---

### 2.5 Audio state relay via DOM mutation (`__updatePlayState`)

**File**: `pages/RecordingDetailPage.tsx` (lines 145-158), `components/recordings/TranscriptView.tsx` (lines 124-136)

The audio play state is communicated from `RecordingDetailPage` to `TranscriptView` by attaching a `__updatePlayState` function to a DOM element via a ref:

```ts
(el as HTMLDivElement & { __updatePlayState?: ... }).__updatePlayState = updatePlayState;
```

This pattern is fragile and non-idiomatic in React. It relies on timing (the effect in TranscriptView must run before the parent's callback fires), breaks if the DOM ref changes, and bypasses React's data flow. A simple callback prop or React Context would be cleaner and more reliable.

---

### 2.6 Recordings list/detail mobile pattern relies on broken `useParams`

**File**: `pages/RecordingsPage.tsx` (lines 71-73)

```ts
if (isMobile && selectedId) {
  return <RecordingDetailPage />;
}
```

Since `selectedId` is always `undefined` (see issue 2.1), the mobile detail-in-list pattern never activates. On mobile, tapping a recording navigates to `/recordings/:id` which renders `RecordingDetailPage` as a standalone page (correct behavior), but the back button in `RecordingDetailPage` navigates to `/recordings`, losing any scroll position or filter state.

---

### 2.7 `TranscriptView` still uses `CustomEvent` for cross-component communication

**File**: `components/recordings/TranscriptView.tsx` (lines 114-121), `components/recordings/ChatPanel.tsx` (lines 42-47)

The spec explicitly says "No CustomEvents" (section 6, decision 3), but the chat reference links dispatch a `highlightTranscriptEntry` CustomEvent, and TranscriptView listens for it. This is the exact pattern the rewrite was supposed to eliminate.

---

### 2.8 Participant search on backend uses `name` param but `SpeakerDropdown` doesn't call it

**File**: `components/recordings/SpeakerDropdown.tsx`

The `SpeakerDropdown` filters participants **client-side** from the full list fetched by `useParticipants()`. This is fine for a small number of participants but doesn't use the backend search endpoint. This is a minor design concern for now but will degrade if the participant list grows.

---

## 3. Minor Issues

### 3.1 `useRecording(id!)` called with non-null assertion when `id` might be undefined

**File**: `pages/RecordingDetailPage.tsx` (line 50)

```ts
const { id } = useParams<{ id: string }>();
const { data: recordingResponse, isLoading } = useRecording(id!);
```

If `id` is `undefined` (which it will be due to issue 2.1), the `!` assertion hides the problem. `useRecording` does check `enabled: !!id` which prevents the query from firing, but the type is still misleading. Same pattern in `PersonDetailPage` (line 53) and `JobDetailPage` (line 26).

---

### 3.2 Missing debounce on recording search input

**File**: `pages/RecordingsPage.tsx` (lines 82-87)

The search input fires `setSearchQuery` on every keystroke, which directly triggers a new `useRecordings` query. This will cause excessive API calls. A debounce of 300-500ms would be appropriate.

---

### 3.3 `handleDelete` in `RecordingDetailPage` does not handle errors gracefully

**File**: `pages/RecordingDetailPage.tsx` (line 71-74)

```ts
const handleDelete = useCallback(async () => {
  if (!id) return;
  await deleteMutation.mutateAsync(id);
  navigate("/recordings");
}, [id, deleteMutation, navigate]);
```

If `mutateAsync` throws, `navigate("/recordings")` is never called and the user is stuck on the detail page of a recording that may or may not have been deleted. Should wrap in try/catch or use `deleteMutation.mutate` with `onSuccess`.

---

### 3.4 `PasteDialog` captures `source` state but never sends it to the API

**File**: `components/recordings/PasteDialog.tsx` (lines 32, 54, 103-112)

The `source` dropdown (Zoom/Teams/Other) is rendered and the state is maintained, but it is not included in the `PasteTranscriptRequest` sent to the backend. The field does exist in the `PasteTranscriptRequest` type either -- so the source selection is purely decorative.

---

### 3.5 `ProfileCard` shows `plaud_last_sync` as "Member Since"

**File**: `pages/SettingsPage.tsx` (lines 63-68)

```ts
<InfoRow label="Member Since" value={user.plaud_last_sync ? format(...) : "-"} />
```

This displays the Plaud last sync date as the "Member Since" date, which is semantically wrong. The `UserProfile` type doesn't include a `created_at` field, which is likely the real issue.

---

### 3.6 `handleBulkDelete` in `PeoplePage` awaits deletions sequentially

**File**: `pages/PeoplePage.tsx` (lines 107-113)

```ts
for (const id of ids) {
  await deleteParticipantMutation.mutateAsync(id);
}
```

Deleting N participants makes N sequential API calls. Consider `Promise.all` for parallel deletion, or a batch endpoint.

---

### 3.7 Missing `aria-label` on icon-only buttons

**Files**: Throughout (`RecordingDetailPage.tsx`, `TranscriptEntry.tsx`, `ChatPanel.tsx`, etc.)

Many buttons use only an icon with `title` for description, but lack `aria-label`. Screen readers will not announce the button's purpose. The `title` attribute provides tooltip text but is not read by most screen readers. Example: `RecordingDetailPage.tsx` line 228 (chat toggle), line 237 (copy), line 247 (export).

---

### 3.8 `highlightText` uses `dangerouslySetInnerHTML`

**File**: `pages/SearchPage.tsx` (lines 136-174)

The function does escape HTML entities before highlighting, so this is safe in practice. However, it would be more robust to use React elements (like the chat reference rendering does) rather than innerHTML.

---

### 3.9 Inconsistent `formatDuration` implementations

**Files**: `RecordingDetailPage.tsx` (line 345), `RecordingCard.tsx` (line 105), `JobCard.tsx` (line 93), `JobDetailPage.tsx` (line 144)

There are four separate `formatDuration`/`formatDurationMs` functions across the codebase, with slightly different formatting logic (some show "Xh Xm", others "X:XX:XX"). These should be consolidated into a shared utility.

---

### 3.10 `useIsMobile` has a potential flash of incorrect state

**File**: `hooks/useIsMobile.ts` (lines 10-13)

```ts
const [isMobile, setIsMobile] = useState(() =>
  typeof window !== "undefined" ? window.innerWidth <= MOBILE_BREAKPOINT : false,
);
```

The initial state uses `window.innerWidth <= 768` but the effect uses `matchMedia(max-width: 768px)`. These should agree. With the `<=` vs CSS `max-width` (which is `<=`), they do match at 768px. This is fine, but worth noting that the initial state is set before the layout effect, so there could be a single-frame flash on SSR (not an issue here since this is a client-only SPA).

---

### 3.11 `ToastContainer` is inside `TooltipProvider` but outside `BrowserRouter`

**File**: `App.tsx` (lines 54-63)

The `ToastContainer` is a sibling of `BrowserRouter`, which is fine functionally, but no toast is ever shown in the codebase. None of the mutations call `toast.success()` or `toast.error()`. The `react-toastify` dependency is imported but never used for user feedback. All errors are either silently swallowed or shown inline. Consider either using toasts for mutation feedback or removing the dependency.

---

### 3.12 Missing error boundaries

No error boundary component exists. If any component throws during render (e.g., from an unexpected null in the transcript data), the entire app will crash with a white screen.

---

### 3.13 Recordings virtualizer `estimateSize` is static

**File**: `pages/RecordingsPage.tsx` (line 55)

```ts
estimateSize: () => 100
```

The `RecordingCard` height varies based on content (description, tags, speakers). A static 100px estimate will cause visual jumping when items are measured. The virtualizer should use `measureElement` or a more accurate estimate.

---

## 4. Positive Observations

### 4.1 Clean architecture and separation of concerns
The three-layer pattern of `api.ts` (HTTP calls) -> `queries.ts` (TanStack Query hooks) -> pages/components is well-structured. Query key factories are properly defined and cache invalidation is thorough.

### 4.2 Type safety
TypeScript types are comprehensive. The model file covers all API entities, request types, and response envelopes. The types just need to match the actual backend (the envelope mismatch is the problem, not the type definitions themselves).

### 4.3 Mobile-first responsive design (in concept)
The `useIsMobile` hook, bottom navigation bar, mobile Sheet for chat, and list-or-detail pattern are all correct design decisions. The implementation just needs the routing fix (issue 2.1) to work.

### 4.4 Transcript parser is well-implemented
`use-transcript-parser.ts` handles three input formats (JSON with timestamps, diarized text, plain text) with proper fallback chain. The JSON parser handles both millisecond offsets and ISO 8601 duration strings. Speaker merging for consecutive entries is a good UX touch.

### 4.5 Speaker assignment UX is thoughtful
The `SpeakerDropdown` with keyboard navigation (arrows, Enter, Escape), inline search, "Create new participant" option, and click-outside dismissal is a polished interaction.

### 4.6 Authentication is well-structured
The MSAL integration with silent-first -> popup -> redirect fallback chain, proper interceptors for token attachment and 401 handling, and the feature flag toggle are all solid.

### 4.7 Chat panel
The desktop side-panel / mobile full-screen Sheet pattern is correct per the spec. Message history is maintained. The typing indicator animation is a nice touch.

### 4.8 Consistent visual design
The use of Tailwind tokens throughout (no hardcoded hex colors), consistent spacing, dark mode support via CSS variables, and proper use of shadcn/ui components all align with spec requirements.

---

## Summary: Priority Order

| # | Severity | Issue | Impact |
|---|----------|-------|--------|
| 1.1 | Critical | `SingleResponse<T>` wrapper mismatch | All detail views, all mutations broken |
| 1.2 | Critical | `PaginatedResponse.meta` mismatch | Pagination data lost (lists still work) |
| 1.8 | Critical | Tags/Templates return bare arrays, not paginated | Tags filter broken, template list broken |
| 1.3 | Critical | Chat response `.message.content` on a string | Chat completely broken |
| 1.4 | Critical | Search calls wrong endpoint | Full-text search non-functional |
| 1.5 | Critical | Participant search sends `q` not `name` | Participant search returns 422 |
| 1.6 | Critical | Analysis templates wrong path | All template CRUD returns 404 |
| 1.7 | Critical | Sync trigger response mismatch | Sync trigger JS error |
| 2.1 | Major | Route params not available in list pages | Desktop split-view broken |
| 2.2 | Major | Date range filter disconnected | Filter UI is decorative |
| 2.3 | Major | Trigger filter ignored by backend | Filter UI is decorative |
| 2.4 | Major | Upload progress hardcoded to 50% | Poor UX for large files |
| 2.5 | Major | DOM mutation for audio state relay | Fragile, may silently fail |
| 2.7 | Major | CustomEvent still used (spec violation) | Spec non-compliance |
| 3.11 | Minor | Toast library imported but never used | Dead dependency |
| 3.12 | Minor | No error boundaries | White-screen crashes |
| 3.2 | Minor | No search debounce | Excessive API calls |
| 3.5 | Minor | "Member Since" shows wrong data | Misleading UI |
| 3.7 | Minor | Missing aria-labels | Accessibility gap |
| 3.9 | Minor | Duplicated format functions | Code quality |
