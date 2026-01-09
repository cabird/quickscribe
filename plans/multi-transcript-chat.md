# Multi-Transcript Chat Feature Implementation Plan

## Feature Overview

Add the ability to select multiple transcripts and chat with an LLM about all of them together. This includes:
- Token count display on each transcript card
- Multi-select functionality with checkboxes
- Selection summary in the header
- Chat with multiple transcripts injected into context

---

## UI/UX Decisions Made

### Token Count Display
- Show on each card next to duration: `⏱ 16 min • # 2.1k`
- Use `NumberSymbol20Regular` icon from Fluent UI
- Format: abbreviated (2.1k, 15.2k, etc.)

### Multi-Select Mechanism
- **Ctrl/Cmd + Click** on a card toggles selection
- **Checkbox** appears on hover (top-left of card)
- **Checkbox always visible** when card is selected
- **Selected cards** get the same highlight styling as the "active" card
- Regular click (no modifier) still opens transcript in viewer as normal

### Selection UI in Header (TopActionBar)
When cards are selected, show in the header:
```
[Search...]  [Basic▼] [All▼]     ✓3 • #15.2k  [✕] [💬]     [Export] [Refresh]
```
- `✓3` = checkmark + count of selected
- `#15.2k` = total tokens (amber/warning color if >100k)
- `[✕]` = Clear selection button
- `[💬]` = Open chat with selected transcripts

### Chat Behavior
- Clicking "Chat" in header opens ChatDrawer with all selected transcripts
- The transcript viewer panel closes when chat opens
- Uses same ChatDrawer component, just with multiple transcripts in context

---

## Backend Changes Required

### 1. Add `token_count` to Transcription Model

**File to modify:** `shared/Models.ts`

Add to `Transcription` interface:
```typescript
token_count?: number; // Approximate token count of transcript text
```

Then run `make build` in backend to regenerate Python models.

### 2. Calculate Token Count

**Option A:** Calculate when transcription is saved (in transcription handler)
**Option B:** Add endpoint to calculate on-demand

Calculation: Use tiktoken or simple approximation (chars / 4).

**Files to read:**
- `backend/src/db_handlers/transcription_handler.py` - to see how transcriptions are saved
- `shared_quickscribe_py/cosmos/transcription_handler.py` - if using shared lib

### 3. Modify Chat Endpoint for Multiple Transcripts

**File to modify:** `backend/src/routes/ai_routes.py`

Change `/api/ai/chat` endpoint to:
- Accept `transcription_ids` (array) instead of `transcription_id` (string)
- Fetch all transcriptions
- Combine their text into the system prompt
- Validate user owns all transcriptions

**Current signature:**
```python
transcription_id = data.get('transcription_id')
```

**New signature:**
```python
transcription_ids = data.get('transcription_ids')  # array of IDs
```

---

## Frontend Changes Required

### 1. Add Token Count to Recording Model

**Files to read:**
- `shared/Models.ts` - source of truth for models
- `v3_frontend/src/types/models.ts` - auto-generated, will update via sync

The Recording model needs to expose `token_count` from its linked Transcription. Either:
- Add `token_count` to Recording model
- Or fetch it from transcription when loading recordings

**File to read:** `v3_frontend/src/services/recordingsService.ts` - see how recordings are fetched

### 2. Add Token Count Display to RecordingCard

**File to modify:** `v3_frontend/src/components/transcripts/RecordingCard.tsx`

Add:
- Import `NumberSymbol20Regular` icon
- Add token count to metaRow: `# 2.1k`
- Format function for abbreviating numbers (2100 → "2.1k")

### 3. Add Multi-Select State Management

**Files to modify:**
- `v3_frontend/src/components/transcripts/TranscriptsView.tsx` - add selection state
- `v3_frontend/src/components/transcripts/RecordingCard.tsx` - add checkbox + selection handling

Add state:
```typescript
const [selectedRecordingIds, setSelectedRecordingIds] = useState<Set<string>>(new Set());
```

Add props to RecordingCard:
```typescript
interface RecordingCardProps {
  recording: Recording;
  isSelected: boolean;      // existing - for viewer
  isChecked: boolean;       // new - for multi-select
  onCheckChange: (checked: boolean) => void;
  onClick: () => void;
}
```

Handle Ctrl/Cmd+Click in onClick handler.

### 4. Add Selection UI to TopActionBar

**File to modify:** `v3_frontend/src/components/layout/TopActionBar.tsx`

Add new props:
```typescript
interface TopActionBarProps {
  // ... existing props
  selectedCount: number;
  selectedTokenCount: number;
  onClearSelection: () => void;
  onChatWithSelected: () => void;
}
```

Render selection info when `selectedCount > 0`:
- Checkmark + count
- Token count (with warning if >100k)
- Clear button
- Chat button

### 5. Update ChatDrawer for Multiple Transcripts

**Files to read:**
- `v3_frontend/src/components/transcripts/ChatDrawer.tsx` - current implementation
- `v3_frontend/src/services/chatService.ts` - API client

**Changes:**
- Accept array of transcription IDs instead of single ID
- Build combined system prompt with all transcripts
- Update chatService to pass array to backend

### 6. Update chatService

**File to modify:** `v3_frontend/src/services/chatService.ts`

Change:
```typescript
// From:
chat(transcriptionId: string, messages: ChatMessage[])

// To:
chat(transcriptionIds: string[], messages: ChatMessage[])
```

---

## Implementation Order

1. **Backend: Add token_count to model** (shared/Models.ts + make build)
2. **Backend: Add token calculation** (when transcription saved or endpoint)
3. **Backend: Modify chat endpoint** for multiple IDs
4. **Frontend: Sync models** (npm run sync-models)
5. **Frontend: Add token count to cards**
6. **Frontend: Add multi-select state + checkboxes**
7. **Frontend: Add selection UI to header**
8. **Frontend: Update ChatDrawer + chatService**
9. **Test end-to-end**

---

## Key Files to Read Before Implementation

### Backend
- `shared/Models.ts` - Transcription interface (line ~303)
- `backend/src/routes/ai_routes.py` - Chat endpoint (line ~387)
- `backend/src/db_handlers/transcription_handler.py` or `shared_quickscribe_py/cosmos/transcription_handler.py`

### Frontend
- `v3_frontend/src/components/transcripts/RecordingCard.tsx` - Card component
- `v3_frontend/src/components/transcripts/TranscriptsView.tsx` - Parent view with state
- `v3_frontend/src/components/transcripts/RecordingsList.tsx` - List container
- `v3_frontend/src/components/layout/TopActionBar.tsx` - Header bar
- `v3_frontend/src/components/transcripts/ChatDrawer.tsx` - Chat UI
- `v3_frontend/src/services/chatService.ts` - Chat API client
- `v3_frontend/src/services/recordingsService.ts` - How recordings are fetched

---

## Token Count Formatting Function

```typescript
function formatTokenCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return count.toString();
}
```

---

## Warning Threshold

Show warning styling (amber/orange color) when total selected tokens > 100,000.
