# Meeting Notes Feature — Implementation Plan

## Overview

Add a structured "meeting notes" extraction to every recording. These are richer than `search_summary` (which is optimized for retrieval) — they capture discussion threads, decisions, action items, key quotes, next steps, and parking lot items with full speaker attribution.

Meeting notes serve two purposes:
1. **Human consumption** — viewable in the recording detail UI alongside the transcript
2. **LLM synthesis** — used as the default input for `synthesize_recordings` instead of raw transcripts, giving much better information density per token

## Data Model

### New columns on `recordings` table

```sql
ALTER TABLE recordings ADD COLUMN meeting_notes TEXT;
ALTER TABLE recordings ADD COLUMN meeting_notes_generated_at TEXT;
ALTER TABLE recordings ADD COLUMN meeting_notes_tags TEXT;  -- JSON array
ALTER TABLE recordings ADD COLUMN speaker_mapping_updated_at TEXT;
```

- `meeting_notes` — the full structured markdown output
- `meeting_notes_generated_at` — ISO timestamp of when notes were last generated
- `meeting_notes_tags` — JSON array of topic tags extracted from notes (stored separately for filtering/clustering)
- `speaker_mapping_updated_at` — ISO timestamp, set whenever speaker_mapping is modified. Used by the background job to detect when notes need regeneration (more precise than `updated_at` which is bumped by title edits, tag changes, etc.)

### Schema addition in `database.py`

Add columns to `SCHEMA_SQL` and add a migration block in `_migrate_schema()` that ALTERs existing databases.

### Update speaker mapping writes

Everywhere `speaker_mapping` is updated in `recording_service.py` and `sync_service.py`, also set `speaker_mapping_updated_at = datetime('now')`.

## Generation

### Model

GPT 5 mini with `reasoning_effort="medium"`. The extraction requires real reasoning (distinguishing decisions from discussions, identifying deferred items, attributing statements correctly) but doesn't need the full GPT 5.

### Prompt

New Jinja2 template: `src/app/prompts/generate_meeting_notes.j2`

The prompt adapts the structure from the summarize-meeting skill. Context variables passed to the template:

- `title` — recording title
- `date` — recording date
- `duration` — formatted duration string (e.g., "53m")
- `speakers` — comma-separated speaker names from speaker_mapping
- `transcript` — full diarized_text (or transcript_text fallback)

The prompt instructs the model to extract and return **markdown** (not JSON) with these sections:

#### Meeting Header
- Duration, attendees, one-sentence purpose

#### Executive Summary
- 2-4 sentences capturing the full arc: why the meeting was held, what the group worked through, what was resolved, what remains open
- Must stand alone — someone reading only this paragraph should understand the meeting's outcome

#### Discussion Threads
- One subsection per major topic
- Each opens with a framing sentence, summarizes key points with speaker attribution, and closes with an explicit outcome: Resolved (and how), Deferred, or Still open
- Depth scaled to significance (25-minute topic gets a full paragraph, 2-minute topic gets 2-3 sentences)

#### Decisions
- Numbered list of clear, unambiguous statements in active voice with attribution
- Omit section if no decisions were made (note in executive summary instead)

#### Action Items
- Table with columns: Action, Owner, Deadline, Notes
- Every row should have a named owner when stated in the transcript. If no clear owner was stated, use "Unassigned" and note the ambiguity in the Notes column
- Omit section if no clear action items

#### Key Quotes
- Verbatim statements worth preserving, cleaned of filler
- No hard limit — include as many as genuinely warrant preservation
- Each quote attributed to speaker with brief context

#### Open Questions
- Questions raised but not answered during the meeting
- Includes who raised each question
- Distinct from parking lot (which is explicitly deferred)

#### Next Steps
- What happens after this meeting — the overall forward motion
- Includes next meeting date/topic if mentioned

#### Parking Lot
- Items explicitly deferred to a future meeting
- Includes who raised each item

#### Topic Tags
- Short list of 3-8 topic labels/categories for this meeting (e.g., "Azure Search", "hiring", "paper submission")
- Useful for downstream LLM synthesis to cluster meetings by theme
- **Must be the last section**, formatted as a comma-separated list on a single line after the heading, so it can be reliably parsed and stored in the separate `meeting_notes_tags` JSON column

### Quality Instructions in Prompt

The prompt includes these quality checks:
- Every action item has a named owner
- Every decision stated as fact, not description of discussion
- Every discussion thread has an explicit outcome
- Executive summary stands alone
- No transcript artifacts (filler words, false starts)
- If speakers are "Speaker 1", "Speaker 2" etc., use those labels consistently
- If real names are available, use names throughout

### Service

New file: `src/app/services/meeting_notes_service.py`

```python
async def generate_meeting_notes(recording_id: str, user_id: str) -> str | None:
```

Follows the `search_summary_service.py` pattern:
1. Fetch recording (diarized_text, title, recorded_at, duration_seconds, speaker_mapping)
2. Extract speaker names from speaker_mapping
3. Render the Jinja2 prompt template with context
4. Call Azure OpenAI (mini deployment, reasoning_effort="medium")
5. Store result in `meeting_notes` column, set `meeting_notes_generated_at` to now
6. Return the generated notes (or None on failure)

Token budget: use `_truncate_transcript()` with the default 190K token limit. Even the longest recording (24K tokens) fits easily.

No JSON parsing needed — the output is markdown stored as-is.

## When Notes Are Generated

### 1. Post-processing (immediate)

In `sync_service._handle_transcription_complete()`, add a call to `meeting_notes_service.generate_meeting_notes()` after the search summary generation step but **before** speaker identification. The ordering in the pipeline is:

1. Title + description generation
2. Store transcript, set status = ready
3. Search summary generation
4. **Meeting notes generation** (new)
5. Speaker identification

At step 4, speakers are "Speaker 1", "Speaker 2" — that's fine. The user gets notes immediately. After speaker ID runs (step 5), `speaker_mapping_updated_at` is set, and the hourly background job detects the notes are stale and regenerates them with real speaker names.

Non-fatal — if note generation fails, the recording still completes.

### 2. Background refresh job (periodic)

New scheduled job in `scheduler/jobs.py`: `refresh_meeting_notes_job`, runs every hour.

Query to find recordings needing notes:
```sql
SELECT id, user_id FROM recordings
WHERE status = 'ready'
  AND (diarized_text IS NOT NULL OR transcript_text IS NOT NULL)
  AND (
    meeting_notes IS NULL
    OR (speaker_mapping_updated_at IS NOT NULL
        AND meeting_notes_generated_at < speaker_mapping_updated_at)
  )
ORDER BY COALESCE(recorded_at, created_at) DESC
LIMIT 10
```

Logic:
- `meeting_notes IS NULL` — never generated (e.g., old recordings from before this feature)
- `meeting_notes_generated_at < speaker_mapping_updated_at` — speakers were reassigned since notes were generated (uses dedicated timestamp, not `updated_at` which is bumped by title edits, tags, etc.)
- `ORDER BY ... DESC` — most recent recordings first
- `LIMIT 10` — cap per run to avoid hammering the API

Job uses `max_instances=1` on the APScheduler registration to prevent overlapping runs.

For each matching recording, call `generate_meeting_notes()`. Log success/failure. Skip on error and continue to the next.

### 3. Manual trigger (API endpoint)

New endpoint: `POST /api/recordings/{recording_id}/generate-meeting-notes`

Follows the pattern of the existing `POST /api/search/recordings/{recording_id}/generate-summary` endpoint. Allows manual regeneration from the UI.

## Backfill

The hourly background job handles backfill automatically — it picks up recordings with `meeting_notes IS NULL`, most recent first, 10 per hour. For 473 existing recordings, full backfill takes ~47 hours. This is fine for gradual rollout.

If faster backfill is desired, a one-time script can be run to process recordings in bulk (with rate limiting to stay within API quotas).

## MCP Changes

### synthesize_recordings

Update the router to prefer `meeting_notes` over raw transcript when building the context for synthesis:

```python
# Current:
text = r.get("diarized_text") or r.get("transcript_text") or ""

# New:
text = r.get("meeting_notes") or r.get("diarized_text") or r.get("transcript_text") or ""
```

This is the key efficiency gain: structured meeting notes are ~2-5K tokens vs 7K+ median for raw transcripts, and they contain pre-extracted decisions, action items, and attributed discussion summaries.

### get_recording

Add `meeting_notes` and `meeting_notes_generated_at` to the response so MCP clients can see whether notes are available and how fresh they are.

### No MCP generation tool

MCP is strictly read-only. Meeting notes generation is a backend job, not something MCP clients trigger. If notes don't exist for a recording, the MCP client sees `meeting_notes: null` and works with the transcript instead. The background job will eventually generate notes for all recordings.

## Frontend Changes

### Recording Detail Page (`RecordingDetailPage.tsx`)

Add a `MeetingNotesButton` component following the exact `SearchSummaryButton` pattern:

- **Trigger:** A button in the header action bar (next to the existing search summary button), using a `NotebookPen` or `FileText` icon
- **Dialog:** Opens a modal with the meeting notes rendered as markdown
- **Regenerate:** A "Regenerate" button in the dialog footer that calls the manual trigger endpoint
- **Loading state:** Spinner while generating
- **Empty state:** If `meeting_notes` is null, show "No meeting notes yet" with a "Generate" button

### API additions (`api.ts`)

```typescript
export async function generateMeetingNotes(recordingId: string): Promise<{ meeting_notes: string }> {
  const { data } = await apiClient.post(`/api/recordings/${recordingId}/generate-meeting-notes`);
  return data;
}
```

### Types (`models.ts`)

Add to `RecordingDetail`:
```typescript
meeting_notes: string | null;
meeting_notes_generated_at: string | null;
```

### Query invalidation

After generating meeting notes, invalidate the recording query so the detail view refreshes.

## File Summary

### New files
- `src/app/services/meeting_notes_service.py` — generation logic
- `src/app/prompts/generate_meeting_notes.j2` — Jinja2 prompt template

### Modified files
- `src/app/database.py` — new columns + migration
- `src/app/scheduler/jobs.py` — new hourly job
- `src/app/services/sync_service.py` — add notes generation to post-processing pipeline
- `src/app/routers/mcp_tools.py` — update synthesize_recordings and get_recording (read-only, no new MCP tools)
- `src/app/services/recording_service.py` — set speaker_mapping_updated_at when speaker_mapping changes
- `src/app/services/sync_service.py` (speaker ID section) — set speaker_mapping_updated_at after speaker processing
- `src/app/routers/recordings.py` — add manual trigger endpoint
- `src/app/models.py` — update RecordingDetail, add any needed request/response models
- `src/app/services/ai_service.py` — (no changes, reuse existing client/truncation)
- Frontend: `RecordingDetailPage.tsx`, `api.ts`, `queries.ts`, `types/models.ts`

## Implementation Order

1. Database schema (columns + migration)
2. Jinja2 prompt template
3. Meeting notes service
4. Manual trigger endpoint (for testing)
5. Post-processing integration
6. Background refresh job
7. MCP changes (synthesize fallback, get_recording, generate tool)
8. Frontend (modal, button, API calls)
9. Tests

## Cost Estimate

GPT 5 mini with medium thinking, ~7K token median input + ~2K output per recording:
- Per recording: ~9K tokens ≈ small cost
- Full backfill (473 recordings): ~4.3M tokens
- Ongoing: ~2-5 recordings/day from normal usage, plus occasional regenerations from speaker assignments
