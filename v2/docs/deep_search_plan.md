# QuickScribe Deep Search — Implementation Plan

**Date**: 2026-03-25
**Status**: Plan
**Informed by**: Podcast KB implementation, GPT-5.4 architecture review

---

## Overview

A multi-stage LLM-powered search system that lets you ask natural language questions across all your transcribed recordings and get synthesized answers with citations.

**Example**: "When did we decide to change the deployment strategy?" → searches summaries, drills into relevant transcripts, synthesizes an answer citing specific recordings.

---

## Architecture: 3-Tier Fan-Out / Fan-In (Map-Reduce)

Adapted from the Podcast KB pattern (`/home/cbird/side_projects/podcast_kb/src/core/qa.py`).

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Tier 1: Router (Map over summaries)              │
│                                                  │
│  Batch summaries into chunks of ~50K tokens      │
│  Fan-out: parallel LLM calls per batch           │
│  Each returns candidate recordings with scores   │
│  Fan-in: merge, dedup, rank globally             │
│  Select top-K candidates                         │
└──────────────────────┬──────────────────────────┘
                       │ top-K recording IDs
                       ▼
┌─────────────────────────────────────────────────┐
│ Tier 2: Transcript Extraction (Fan-out)          │
│                                                  │
│  For each candidate recording, in parallel:      │
│  Send query + full transcript → LLM             │
│  Extract relevant information                    │
└──────────────────────┬──────────────────────────┘
                       │ per-recording extracts
                       ▼
┌─────────────────────────────────────────────────┐
│ Tier 3: Synthesis (Fan-in)                       │
│                                                  │
│  Combine all extracts → one final answer         │
│  With [[TAG]] citations to specific recordings   │
└─────────────────────────────────────────────────┘
```

### Why this approach (for now)
- No embeddings or chunking infrastructure needed
- Same cost whether 1 batch or N batches (parallel = same total tokens)
- Proven pattern from Podcast KB
- Can add FAISS/embedding pre-filtering later as Stage 0

---

## Tag System

Following the Podcast KB pattern (`/home/cbird/side_projects/podcast_kb/src/utils.py`):

- **Tag format**: 2 uppercase letters + 2 digits (e.g., `AB12`, `KE88`)
- **Tag space**: 26² × 10² = 67,600 possible values
- **Ephemeral**: Generated fresh per query, not persisted
- **Collision-free**: Checked against `used_tags` set within each query
- **Tag map**: `{tag: {recording_id, title, date, speakers}}` — maps tags back to recordings for frontend rendering

Tags are embedded in prompt text: `[[AB12]] Meeting Title ...` so the LLM cites them in its response.

---

## Search Summary Design

### New database columns on `recordings` table

```sql
search_summary    TEXT,    -- Semi-structured retrieval-optimized summary (150-300 words)
search_keywords   TEXT,    -- JSON: extracted entities, keywords, projects, etc.
```

### Summary format (semi-structured sections)

```
Topics: Specific topics and subtopics discussed
Decisions: Concrete outcomes, approvals, changes, agreements
Action items: Who committed to do what
Key facts: Numbers, dates, deadlines, metrics, specific data points
Entities: People mentioned (beyond speakers), projects, products, companies, technologies, tools
Open questions: Unresolved issues, blockers, unknowns, follow-ups needed
Context: References to prior meetings, future plans, dependencies, related work
```

**Target length**: 150-300 words. Dense, entity-rich, no filler.

### What goes in structured metadata (NOT in summary)

These are passed alongside the summary in Tier 1 prompts but stored separately:
- Title
- Date
- Speakers (resolved names)
- Duration
- Source (plaud/upload/paste)

### What the summary should NOT include

- Generic filler ("general discussion", "various topics", "team updates")
- Speaker-by-speaker narration
- Greetings, small talk, agenda-setting
- Incidental mentions without substance
- Speculation or inferred intent
- Transcript artifacts (ums, ASR noise)
- Redundant restatement of the same topic

---

## Summary Generation Prompt

```
You generate retrieval-optimized summaries for conversation transcripts.
These summaries are used by another AI model to decide whether a recording
is relevant to future search queries. Optimize for retrievability and
information density, not human readability.

## Recording Metadata
Title: {title}
Date: {date}
Speakers: {speakers}
Duration: {duration}

## Transcript
{diarized_text}

## Instructions

Produce a search-optimized summary using these sections. Be specific and
concrete. Include actual names, numbers, and details — not vague references.

**Topics:** What specific subjects, projects, or issues were discussed?
**Decisions:** What was decided, agreed upon, approved, or rejected?
**Action items:** What did people commit to doing? Include who and what.
**Key facts:** Any specific numbers, dates, deadlines, metrics, or data points mentioned.
**Entities:** People mentioned (beyond speakers), projects, products, companies, technologies, tools.
**Open questions:** What was left unresolved? Blockers? Follow-ups needed?
**Context:** References to prior meetings, future plans, or related work.

Rules:
- 150-300 words total
- Be specific: "discussed Q3 launch timeline for Project Aurora" not "discussed project timelines"
- Include terms someone might search for, even if briefly mentioned
- Do not include filler, greetings, small talk, or generic commentary
- Do not speculate or infer beyond what was said
- If transcript quality is poor, note it briefly
- Omit sections that have no content (e.g., skip "Action items:" if none were discussed)

Also extract keywords as a JSON array. Include: project names, product names,
company names, technology names, people mentioned, and key topic terms.

Return JSON:
{"summary": "Topics: ...\nDecisions: ...\n...", "keywords": ["keyword1", "keyword2", ...]}
```

---

## Tier 1: Router Prompt (Batch)

Following the Podcast KB batch pattern. Each summary is tagged with `[[TAG]]`:

```
[[AB12]] Meeting Title
date:2026-03-20 | speakers:Chris, Carmen | duration:63m
Topics: Discussed Azure deployment strategy...
Decisions: Agreed to use Litestream for SQLite replication...
...

---

[[CD34]] Another Meeting
...
```

**Batch prompt** (adapted from `qa_from_summaries_batch.j2`):

```
You are searching through a batch of {num_recordings} meeting transcript
summaries (batch {batch_index} of {total_batches}) to find recordings
relevant to a request.

## Request
{question}

## Recording Summaries
{summaries}

## Instructions
Identify which recordings are most relevant to the request.

Return JSON:
{"candidates": [
  {"tag": "AB12", "score": 0.95, "why": "Brief reason this recording is relevant"}
]}

Rules:
- Use the [[TAG]] codes shown before each summary
- score from 0.0 (not relevant) to 1.0 (highly relevant)
- Only include recordings with score >= 0.3
- Select at most {max_candidates} candidates
- Order by score descending
- Balance relevance with diversity
- If none are relevant, return {"candidates": []}
```

**Single-batch prompt** (when all summaries fit in one batch, can answer directly — adapted from `qa_from_summaries.j2`):

```
Same as batch, but with Option A (answer directly from summaries) and
Option B (return candidates for deeper search).
```

### Batching Strategy

- **Token budget per batch**: ~50,000 tokens
- Pack summaries into batches until budget is exceeded, then start a new batch
- All batches sent to LLM in parallel (ThreadPoolExecutor or asyncio)
- Fan-in: merge candidates from all batches, dedup by recording_id, sort by score, take top-K
- **K = configurable**, default 8

---

## Tier 2: Transcript Extraction Prompt

For each candidate recording, in parallel:

```
You are extracting information from a meeting transcript to answer a request.

## Request
{question}

## Recording: {title} [[{tag}]]
Date: {date}
Speakers: {speakers}

## Transcript
{diarized_text}

## Instructions
Extract information relevant to the request from the transcript above.

- If relevant, provide a detailed response with specific quotes and details
- If NOT relevant, respond with exactly: NOT_RELEVANT
- Attribute statements to specific speakers when possible
- Use Markdown formatting (headers, bullets, blockquotes for quotes)
- Cite this recording as [[{tag}]] at least once
- Keep under ~300 words unless unusually dense
- Include 1-3 direct quotes as blockquotes when they support key claims
```

---

## Tier 3: Synthesis Prompt

```
You are synthesizing responses from multiple meeting transcript sources
into one coherent answer.

## Request
{question}

## Answers from Individual Recordings
{per_recording_answers}

## Instructions
Synthesize into a single, comprehensive answer:

- Combine insights into a coherent narrative
- Note where sources agree or offer different perspectives
- Note contradictions or evolution over time
- Weight sources by relevance and detail
- Cite recordings inline using [[TAG]] codes
- Preserve 1-3 direct quotes as blockquotes when impactful
- Use Markdown formatting
- Target 400-800 words
- Sort evidence chronologically when relevant
- Do not invent facts not present in the source answers
```

---

## Implementation Plan

### Phase 1: Search Summary Generation

1. Add `search_summary` and `search_keywords` columns to `recordings` table
2. Create `search_service.py` with `generate_search_summary(recording_id)` function
3. Add summary generation prompt to `prompts.yaml`
4. Wire into post-processing pipeline (after title/description generation)
5. Create backfill script to generate summaries for all existing recordings
6. Add `search_summary` to the recording detail API response (shown in UI)

### Phase 2: Deep Search Pipeline

1. Create `deep_search_service.py` with the 3-tier pipeline:
   - `search(question)` — main entry point
   - `_tier1_router(question)` — batch summaries, fan-out, fan-in
   - `_tier2_extract(question, candidates)` — parallel transcript extraction
   - `_tier3_synthesize(question, extracts)` — final synthesis
2. Tag generation utility (port from Podcast KB `utils.py`)
3. Prompt templates (Jinja2 or YAML)
4. API endpoint: `POST /api/search/deep` — accepts question, returns answer with citations
5. Streaming via SSE for real-time progress (Tier 1 complete → extracting → synthesizing)

### Phase 3: Frontend

1. Search page redesign: natural language input
2. Show progress through tiers (searching summaries → extracting from N recordings → synthesizing)
3. Render [[TAG]] citations as clickable badges linking to recordings
4. Tag map for resolving tags to recording metadata
5. Search history (optional)

### Phase 4: Future Enhancements (not in v1)

- FAISS embedding pre-filter as Stage 0 (reduce candidates before LLM)
- Chunk-level embeddings for fine-grained retrieval
- Query classification (factual/decision/timeline/person lookup)
- Hybrid retrieval (embeddings + FTS5 + LLM reranking)

---

## Configuration

```python
# deep_search settings
deep_search_batch_token_limit: int = 50_000
deep_search_max_candidates: int = 8
deep_search_model: str = ""  # default to azure_openai_deployment
deep_search_synthesis_model: str = ""  # can use a stronger model for synthesis
```

---

## Cost Estimate (per query)

With ~450 recordings at ~200 words/summary:
- Tier 1: ~90K input tokens across all batches + ~2K output per batch (2 batches × ~45K) = ~92K input, ~4K output
- Tier 2: ~8 recordings × ~10K tokens/transcript = ~80K input, ~2.4K output
- Tier 3: ~2.4K input (extracts) + ~1K output
- **Total**: ~175K input + ~7.5K output per query
- **Cost at gpt-4o-mini**: ~$0.03 per query
- **Cost at gpt-4o**: ~$0.50 per query

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `database.py` | Add `search_summary`, `search_keywords` columns |
| `services/search_service.py` | New — summary generation + deep search pipeline |
| `services/prompts.yaml` | Add search summary, router, extract, synthesis prompts |
| `services/ai_service.py` | Add batch LLM calls, parallel execution |
| `routers/search_router.py` | New — `POST /api/search/deep`, SSE streaming |
| `config.py` | Add deep search settings |
| `frontend/src/pages/SearchPage.tsx` | Redesign with deep search UI |
| `frontend/src/lib/api.ts` | Add deep search API calls |
| `tools/backfill_summaries.py` | New — generate summaries for existing recordings |
