# Detailed minutes experiment

Standalone experiment for a per-recording artifact between a summary and a
transcript: **detailed minutes** that keep every substantive point (facts,
numbers, attribution, hedging, decisions, commitments, loose ends) and drop the
filler, so an agent can answer questions about a meeting without reading the
transcript. Length should scale with how much was said, not be capped like a
summary.

Nothing here imports from `app`; it reads a copy of the production DB and will
be merged into QuickScribe once the quality is settled.

## How it works

1. **`fetch.py`** downloads the newest Litestream snapshot of the production DB
   (`cache/app.db`, at most an hour stale; read-only, never a second writer)
   and caches recordings as JSON: timed phrases from `transcript_json`, speaker
   names from `speaker_mapping`, and the `search_summary` / `meeting_notes`
   baselines.
2. **`minutes.py`** merges phrases into speaker turns with `[mm:ss]` stamps and
   splits them into N-minute windows. Each window is one call that sees the
   meeting header, the minutes so far (read-only), the last couple of minutes of
   transcript (read-only), and the new window, and writes minutes for the new
   window only. Optionally a coverage pass per window re-reads the transcript
   and fills gaps. A final call writes the overview (gist, topics, decisions,
   action items, open questions) from the minutes alone.
3. **`evaluate.py`** scores a run. A separate model writes factual questions
   from the transcript (cached, so runs are comparable); an answer model answers
   them from the transcript, `search_summary`, `meeting_notes`, and the minutes;
   a judge grades them. It also spot-checks minutes bullets against the
   transcript for unsupported or misattributed statements.

Prompts are in `prompts/` and versioned by filename; each output records the
model, settings and a hash of the prompts used.

## Running

```bash
uv run fetch.py --download                         # refresh the DB snapshot
uv run fetch.py --list --since 2026-07-28          # candidates
uv run fetch.py --sample 9 --since 2026-07-28      # cache a spread of lengths
uv run minutes.py --all                            # luna, medium effort, 10-min chunks
uv run minutes.py --all --chunk-minutes 5 --coverage
uv run evaluate.py runs/<run>
```

Needs `.env` here with `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`
(the `cabir-mffq823a-eastus2` resource), and `az` logged in for `--download`.

`cache/` and `runs/` are gitignored: they contain meeting content.
