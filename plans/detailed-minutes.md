# Detailed minutes: build plan

Status: **in progress** · Branch: `cabird/detailed-minutes-experiment` · Process: agentic
(implement → review → fix → tests → test review → verify → commit, one commit per task)

## Goal

Add **detailed minutes** to QuickScribe: a per-recording artifact between a summary and a
transcript that keeps every substantive point (facts, numbers, attribution, hedging,
decisions, commitments, loose ends) in terse shorthand, about 35% of transcript tokens.
Agents read it instead of transcripts; Chris reads it in the recording view.

The pipeline is the one validated in `v2/backend/experiments/detailed_minutes/`
(9 recordings, 164 questions): ~84% question-answering vs 86–91% for the full transcript
and 39% for existing `meeting_notes`, ~94% of sampled statements grounded.

## Pipeline (fixed for this build)

- Model: Azure OpenAI deployment `gpt-5.6-luna` (same resource/key as today), reasoning
  effort `low`.
- Input: `transcript_json.recognizedPhrases` → speaker turns (merge same speaker, gap ≤ 4 s,
  turn ≤ 60 s), each line `[mm:ss] Name: text` with names from `speaker_mapping`.
- Chunks of ~2,000 transcript tokens (o200k_base), on turn boundaries; final remainder under
  a third of a chunk folds into the previous one.
- Each chunk call: meeting header + minutes so far (read-only) + last 2 min of transcript
  (read-only) + new chunk; prompt `chunk_v4`. Then one overview call from the minutes alone,
  prompt `rollup_v2`. Document = header line + overview + `## Minutes` + chunk outputs.
- Transcript links: per-topic `### [mm:ss] Topic` headings (and `[mm:ss]` in the overview)
  are the anchors. No per-line citations.

## Decisions (from Chris, 2026-10-04)

| # | Decision |
|---|---|
| D1 | Stored in new columns on `recordings` (not replacing `meeting_notes`). |
| D2 | MCP gets a `get_minutes` tool; `synthesize_recordings` prefers minutes > meeting_notes > transcript. |
| D3 | Shown in the recording view via a new icon in the top-right action bar: shows minutes if present, otherwise clicking starts generation. |
| D4 | Minutes are included in keyword search. |
| D5 | Generated automatically for new recordings only; older ones on demand via the button. No bulk backfill. |
| D6 | Model fixed to gpt-5.6-luna for now. |
| D7 | When speaker names change after generation, minutes regenerate automatically (as meeting notes do). |
| D8 | Keep generating `meeting_notes` for now. |
| D9 | Timestamps: per-topic only, rendered as links back into the transcript (UI) and fetchable by time range (MCP). |
| D10 | Agentic process; orchestrator deploys to quickscribe.cabird.com after verification. |

## Tasks

### T1 — Backend: schema, config, minutes service  ☑
- Columns: `detailed_minutes TEXT`, `detailed_minutes_generated_at TEXT`,
  `detailed_minutes_status TEXT` (NULL | `generating` | `ready` | `failed`),
  `detailed_minutes_error TEXT`, `detailed_minutes_meta TEXT` (JSON: model, effort, prompt
  versions, chunk count, transcript/minutes tokens, LLM token usage, seconds). Add to
  `SCHEMA_SQL` and `_migrate_schema`.
- Config: `azure_openai_minutes_deployment: str = "gpt-5.6-luna"`, `minutes_reasoning_effort = "low"`.
- `services/minutes_service.py`: port of the experiment pipeline (no import from
  `experiments/`); prompts as `prompts/minutes_chunk.j2` and `prompts/minutes_rollup.j2`
  copied verbatim from `chunk_v4.md` / `rollup_v2.md`. `generate_minutes(recording_id, user_id)`
  sets status `generating`, runs, writes result + status `ready` in one UPDATE+commit (shared
  aiosqlite connection: no await between write and commit), or `failed` + error. Rate-limit
  backoff on 429. In-process guard so the same recording never generates twice concurrently.
- Tests: turn building, chunking, prompt assembly, status transitions, failure path, with the
  OpenAI client mocked.

### T2 — Triggers: endpoint, post-transcription hook, staleness job  ☑
- `POST /api/recordings/{id}/generate-minutes` → 202 and spawns generation in the background
  (reuse the `_spawn` pattern so shutdown cancels it); 409 if already generating; 400 if no
  `transcript_json`. Status via the recording detail payload.
- New recordings: run after speaker identification in `_handle_transcription_complete`
  (so the first generation already has names), only when AI is enabled.
- Scheduler job `refresh_detailed_minutes_job` (60 min, `max_instances=1`): regenerate when
  `detailed_minutes IS NOT NULL AND speaker_mapping_updated_at > detailed_minutes_generated_at`
  (D7). Never generates for recordings that have no minutes (D5).
- `RecordingDetail` model + row mapping expose the minutes fields.

### T3 — MCP, search, synthesis  ☑
- `get_minutes(recording_id)`: minutes markdown, generated_at, token count, and a topic
  index `[{start_ms, timestamp, title}]` parsed from the headings; clear message if none.
- `get_transcript_window(recording_id, start, end)`: transcript lines with `[mm:ss]` and
  speaker names for a time range, from `transcript_json` (D9).
- `get_recording`: add `has_minutes`, `minutes_token_count`; update tool descriptions so
  agents use summary → minutes → transcript window.
- `synthesize_recordings`: per-recording context = minutes > meeting_notes > transcript.
- Search: add minutes to `search_docs`, `SEARCH_INDEX_COLUMNS`, `_SEARCH_WATCHED`, BM25 weight;
  update `tests/test_search.py` column list. Rebuild happens automatically via schema hash.

### T4 — Frontend: minutes button and viewer  ☑
- New icon in the recording action bar next to meeting notes: tooltip "View detailed
  minutes" / "Generate detailed minutes" / spinner while `generating` (polls the recording
  until done); error state with retry.
- Viewer: large dialog or side panel rendering markdown with `react-markdown`.
- `[mm:ss]` / `[h:mm:ss]` in headings and overview become links: close/keep viewer, seek the
  audio player and scroll/highlight the transcript entry containing that time (extend the
  existing `handleHighlightEntry`).
- Types in `models.ts`, API/query hooks in `api.ts` / `queries.ts`.

### Verify + deploy (orchestrator)  ☐
- Full backend suite (compare against the known pre-existing failures), `make lint`,
  frontend build.
- `make deploy`; confirm version; generate minutes for one recording from the UI and via
  MCP; check search finds a minutes-only phrase.

## Decision log

- 2026-10-04: Plan drafted from experiment results and Chris's answers (D1–D10).
- 2026-10-04: Plan approved by Chris.
- T1 review: interrupted runs are reset `generating` → `failed` in `init_db` at startup (single
  instance, so any such row is dead) instead of a 30-min timeout in T2's job. Verified
  gpt-5.6-luna accepts `reasoning_effort` on api versions 2024-06-01 and 2025-01-01-preview, so
  no separate api-version setting. Empty LLM output fails the run; `length` truncation only warns.
- T2 review: `generated_at` = time speaker names were read (not run end), so renames during a
  run still trigger D7. Refresh job also retries stale rows whose last refresh `failed`.
  Re-transcribed old recordings regenerate minutes (accepted: new content). Pasted-text
  recordings have no `transcript_json`, so they can't get minutes (no timestamps); T4 hides
  the button when the recording has no timed transcript.
- T3 review: MCP `search_recordings` still uses the legacy `recordings_fts` index, which does not
  include minutes; only the Search page / `/api/search` index covers them. Follow-up: move MCP
  search onto `search_service`. Minutes BM25 weight 1.0 (same as transcript) so recordings with
  minutes don't outrank older ones just for having them. Transcript windows include any turn
  overlapping the range; `next_start` is millisecond-exact for gap-free paging.
