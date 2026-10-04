"""Detailed minutes generation for recordings.

A chunked pipeline (ported from experiments/detailed_minutes/minutes.py):

1. ``transcript_json`` phrases become speaker turns, one ``[mm:ss] Name: text``
   line each.
2. Turns are split into ~2,000-token chunks on turn boundaries.
3. Each chunk is minuted by one LLM call that also sees the meeting header, the
   minutes written so far (read-only) and the last two minutes of transcript
   before the chunk (read-only).
4. A final call writes the overview from the minutes alone.

The document is header line + overview + ``## Minutes`` + the chunk outputs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass

import tiktoken
from openai import AsyncAzureOpenAI, RateLimitError

from app.config import get_settings
from app.database import get_db
from app.prompts import render

logger = logging.getLogger(__name__)

CHUNK_PROMPT = "minutes_chunk"
ROLLUP_PROMPT = "minutes_rollup"

# Consecutive phrases by one speaker are merged into a turn unless there is a
# long pause or the turn gets long, so timestamps stay reasonably fine-grained.
TURN_MAX_GAP_MS = 4_000
TURN_MAX_LEN_MS = 60_000

CHUNK_TOKENS = 2_000
CONTEXT_MS = 2 * 60_000
MAX_COMPLETION_TOKENS = 32_000

# Rate-limit backoff: the SDK's own retries are short; the per-minute token
# quota needs a longer wait.
RATE_LIMIT_ATTEMPTS = 10

# Above this many chunks a run gets slow and costly; warn but do not refuse.
CHUNK_WARN_THRESHOLD = 40

_enc: tiktoken.Encoding | None = None

# Recording ids with a generation in flight in this process.
_generating: set[str] = set()


def is_generating(recording_id: str) -> bool:
    """True when this process is currently generating minutes for the recording."""
    return recording_id in _generating


def ntok(text: str) -> int:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("o200k_base")
    return len(_enc.encode(text or ""))


def ts(ms: int) -> str:
    """Format milliseconds as mm:ss, or h:mm:ss from one hour on."""
    s = ms // 1000
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


_TS_RE = re.compile(r"^(?:(\d+):)?(\d{1,3}):(\d{2})$")


def parse_ts(text: str) -> int:
    """Parse "mm:ss" or "h:mm:ss" (the format ``ts`` writes) into milliseconds.

    Raises ValueError on anything else, including seconds >= 60 or, in
    h:mm:ss form, minutes >= 60.
    """
    m = _TS_RE.match(text.strip())
    if not m:
        raise ValueError(f"not a mm:ss or h:mm:ss timestamp: {text!r}")
    h, mins, secs = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
    if secs >= 60 or (m.group(1) is not None and mins >= 60):
        raise ValueError(f"out-of-range timestamp: {text!r}")
    return ((h * 60 + mins) * 60 + secs) * 1000


# "### [mm:ss] Topic" or "### [mm:ss] (cont.) Topic" in the minutes body.
_TOPIC_RE = re.compile(
    r"^###\s+\[(?P<ts>\d+:\d{2}(?::\d{2})?)\]\s*(?P<cont>\(cont\.?\)\s*)?(?P<title>.*?)\s*$",
    re.IGNORECASE,
)


def parse_topics(document: str) -> list[dict]:
    """Topic index from a minutes document's ``### [ts] Topic`` headings.

    Only headings under ``## Minutes`` are read (the whole document when that
    heading is missing). Returns [{start_ms, timestamp, title, continued}].
    """
    lines = (document or "").splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == "## minutes":
            lines = lines[i + 1:]
            break
    topics = []
    for line in lines:
        m = _TOPIC_RE.match(line.strip())
        if not m:
            continue
        try:
            start_ms = parse_ts(m.group("ts"))
        except ValueError:
            continue
        topics.append({
            "start_ms": start_ms,
            "timestamp": m.group("ts"),
            "title": m.group("title"),
            "continued": bool(m.group("cont")),
        })
    return topics


def minutes_token_count(document: str | None, meta_json: str | None) -> int | None:
    """Token count of a minutes document: meta's minutes_tokens, else counted."""
    if not document:
        return None
    try:
        meta = json.loads(meta_json or "{}")
    except (json.JSONDecodeError, TypeError):
        meta = {}
    if isinstance(meta, dict) and isinstance(meta.get("minutes_tokens"), int):
        return meta["minutes_tokens"]
    return ntok(document)


@dataclass
class Turn:
    start_ms: int
    end_ms: int
    speaker: str
    text: str

    def line(self) -> str:
        return f"[{ts(self.start_ms)}] {self.speaker}: {self.text}"


# ---------------------------------------------------------------------------
# Transcript -> turns
# ---------------------------------------------------------------------------


def speaker_names(mapping_json: str | None) -> dict[str, str]:
    """'Speaker 1' -> display name, falling back to the label itself."""
    try:
        mapping = json.loads(mapping_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(mapping, dict):
        return {}
    names: dict[str, str] = {}
    for label, info in mapping.items():
        name = None
        if isinstance(info, dict):
            name = info.get("displayName") or info.get("display_name")
        names[label] = name or label
    return names


def _ms(phrase: dict, ms_key: str, ticks_key: str) -> int:
    """Read a time from either the milliseconds or the ticks (100 ns) field."""
    if phrase.get(ms_key) is not None:
        return int(phrase[ms_key])
    if phrase.get(ticks_key) is not None:
        return int(phrase[ticks_key]) // 10_000
    return 0


def parse_phrases(transcript_json: str) -> list[dict]:
    """Azure Speech JSON -> [{t_ms, dur_ms, speaker, text}] sorted by offset."""
    data = json.loads(transcript_json)
    if not isinstance(data, dict) or not isinstance(data.get("recognizedPhrases"), list):
        raise ValueError("transcript_json is not Azure Speech JSON (no recognizedPhrases list)")
    out = []
    for p in data["recognizedPhrases"]:
        if not isinstance(p, dict):
            continue
        best = (p.get("nBest") or [{}])[0]
        text = (best.get("display") or "").strip()
        if not text:
            continue
        out.append({
            "t_ms": _ms(p, "offsetMilliseconds", "offsetInTicks"),
            "dur_ms": _ms(p, "durationMilliseconds", "durationInTicks"),
            "speaker": f"Speaker {p['speaker']}" if p.get("speaker") is not None else "Unknown",
            "text": text,
        })
    out.sort(key=lambda p: p["t_ms"])
    return out


def build_turns(phrases: list[dict], names: dict[str, str]) -> list[Turn]:
    turns: list[Turn] = []
    for p in phrases:
        speaker = names.get(p["speaker"], p["speaker"])
        end = p["t_ms"] + p["dur_ms"]
        last = turns[-1] if turns else None
        if (last and last.speaker == speaker
                and p["t_ms"] - last.end_ms <= TURN_MAX_GAP_MS
                and end - last.start_ms <= TURN_MAX_LEN_MS):
            last.text += " " + p["text"]
            last.end_ms = end
        else:
            turns.append(Turn(p["t_ms"], end, speaker, p["text"]))
    return turns


def transcript_turns(transcript_json: str, speaker_mapping: str | None) -> list[Turn]:
    """Speaker turns exactly as the minutes pipeline builds them, so their
    timestamps line up with the minutes' ``[mm:ss]`` headings. Raises
    ValueError when transcript_json is not Azure Speech JSON."""
    return build_turns(parse_phrases(transcript_json), speaker_names(speaker_mapping))


def chunk_turns(turns: list[Turn], chunk_tokens: int = CHUNK_TOKENS) -> list[list[Turn]]:
    """Split into windows of about chunk_tokens of transcript, on turn
    boundaries. A short final remainder (under a third of a window) is folded
    into the previous chunk."""
    chunks: list[list[Turn]] = []
    cur: list[Turn] = []
    cur_tok = 0
    for t in turns:
        n = ntok(t.line())
        if cur and cur_tok + n > chunk_tokens:
            chunks.append(cur)
            cur, cur_tok = [], 0
        cur.append(t)
        cur_tok += n
    if cur:
        if chunks and cur_tok / chunk_tokens < 1 / 3:
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return chunks


def tail(turns: list[Turn], ms: int) -> list[Turn]:
    if not turns:
        return []
    cutoff = turns[-1].end_ms - ms
    return [t for t in turns if t.end_ms > cutoff]


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


@dataclass
class MeetingInfo:
    title: str
    recorded_at: str
    duration_min: int
    speakers: list[str]

    @property
    def date(self) -> str:
        return (self.recorded_at or "")[:16].replace("T", " ")


def header(info: MeetingInfo) -> str:
    speakers = info.speakers or ["(unlabelled)"]
    return (f"Title: {info.title}\n"
            f"Date: {info.date}\n"
            f"Duration: {info.duration_min} min\n"
            f"Speakers (from voice matching, may be wrong): {', '.join(speakers)}")


def chunk_user_message(
    info: MeetingInfo, chunks: list[list[Turn]], i: int, parts: list[str]
) -> str:
    """User message for chunk i (0-based), given the minutes written so far."""
    chunk = chunks[i]
    prev = [t for c in chunks[:i] for t in c]
    context = tail(prev, CONTEXT_MS)
    new = "\n".join(t.line() for t in chunk)
    return (
        f"# MEETING\n{header(info)}\n\n"
        f"# MINUTES SO FAR (read-only)\n{chr(10).join(parts) or '(none: this is the first segment)'}\n\n"
        f"# RECENT CONTEXT (read-only, already covered above)\n"
        f"{chr(10).join(t.line() for t in context) or '(none)'}\n\n"
        f"# NEW SEGMENT {i + 1} of {len(chunks)}: "
        f"[{ts(chunk[0].start_ms)}] to [{ts(chunk[-1].end_ms)}]\n{new}\n"
    )


def rollup_user_message(info: MeetingInfo, body: str) -> str:
    return f"# MEETING\n{header(info)}\n\n# MINUTES\n{body}\n"


def assemble_document(info: MeetingInfo, overview: str, body: str) -> str:
    return (f"# {info.title}\n\n"
            f"**Date:** {info.date} · "
            f"**Duration:** {info.duration_min} min · "
            f"**Speakers:** {', '.join(info.speakers) or 'unlabelled'}\n\n"
            f"{overview}\n\n## Minutes\n\n{body}\n")


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------


def _get_client() -> AsyncAzureOpenAI:
    settings = get_settings()
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


async def _call(client: AsyncAzureOpenAI, system: str, user: str, calls: list[dict], label: str) -> str:
    settings = get_settings()
    t0 = time.monotonic()
    for attempt in range(RATE_LIMIT_ATTEMPTS):
        try:
            r = await client.chat.completions.create(
                model=settings.azure_openai_minutes_deployment,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                reasoning_effort=settings.minutes_reasoning_effort,
            )
            break
        except RateLimitError:
            if attempt == RATE_LIMIT_ATTEMPTS - 1:
                raise
            delay = min(20 + 10 * attempt, 90)
            logger.info("Minutes %s rate-limited; retrying in %ds", label, delay)
            await asyncio.sleep(delay)
    u = r.usage
    details = getattr(u, "completion_tokens_details", None) if u else None
    finish_reason = r.choices[0].finish_reason
    content = (r.choices[0].message.content or "").strip()
    if not content:
        raise ValueError(f"empty LLM response for {label} (finish_reason={finish_reason})")
    if finish_reason == "length":
        logger.warning("Minutes %s hit the completion token limit; output may be truncated", label)
    calls.append({
        "label": label,
        "seconds": round(time.monotonic() - t0, 1),
        "prompt_tokens": (getattr(u, "prompt_tokens", 0) or 0) if u else 0,
        "completion_tokens": (getattr(u, "completion_tokens", 0) or 0) if u else 0,
        "reasoning_tokens": (getattr(details, "reasoning_tokens", 0) or 0) if details else 0,
        "finish_reason": finish_reason,
    })
    return content


async def run_pipeline(client: AsyncAzureOpenAI, info: MeetingInfo, turns: list[Turn]) -> tuple[str, dict]:
    """Run chunk calls then the rollup. Returns (document, meta)."""
    settings = get_settings()
    chunks = chunk_turns(turns)
    if len(chunks) > CHUNK_WARN_THRESHOLD:
        logger.warning("Minutes for %r need %d chunks (> %d)", info.title, len(chunks),
                       CHUNK_WARN_THRESHOLD)
    chunk_prompt = render(CHUNK_PROMPT)
    rollup_prompt = render(ROLLUP_PROMPT)
    calls: list[dict] = []
    parts: list[str] = []
    for i in range(len(chunks)):
        user = chunk_user_message(info, chunks, i, parts)
        parts.append(await _call(client, chunk_prompt, user, calls, f"chunk{i + 1}"))

    body = "\n\n".join(parts)
    overview = await _call(client, rollup_prompt, rollup_user_message(info, body), calls, "rollup")
    doc = assemble_document(info, overview, body)
    transcript = "\n".join(t.line() for t in turns)
    meta = {
        "model": settings.azure_openai_minutes_deployment,
        "effort": settings.minutes_reasoning_effort,
        "prompts": [CHUNK_PROMPT, ROLLUP_PROMPT],
        "prompt_hash": hashlib.sha256((chunk_prompt + rollup_prompt).encode()).hexdigest()[:12],
        "chunk_tokens": CHUNK_TOKENS,
        "chunks": len(chunks),
        "transcript_tokens": ntok(transcript),
        "minutes_tokens": ntok(doc),
        "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
        "completion_tokens": sum(c["completion_tokens"] for c in calls),
        "reasoning_tokens": sum(c["reasoning_tokens"] for c in calls),
        "seconds": round(sum(c["seconds"] for c in calls), 1),
        "calls": calls,
    }
    return doc, meta


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def spawn_generation(recording_id: str, user_id: str) -> None:
    """Start ``generate_minutes`` as a background task.

    Uses the shared sync_service task set so the run is not garbage collected
    and is cancelled at shutdown (generate_minutes then marks it failed).
    """
    from app.services import sync_service

    sync_service.spawn_background(generate_minutes(recording_id, user_id))


async def generate_minutes(recording_id: str, user_id: str) -> bool:
    """Generate and store detailed minutes for a recording.

    Returns True on success. Returns False (without touching the DB) when a
    generation for this recording is already running in this process, the
    recording is not the user's, or it has no transcript_json; returns False
    with status 'failed' when the pipeline fails. Previous minutes text is kept
    on failure.
    """
    if recording_id in _generating:
        logger.info("Minutes already generating for %s", recording_id)
        return False
    _generating.add(recording_id)
    try:
        return await _generate(recording_id, user_id)
    finally:
        _generating.discard(recording_id)


async def _generate(recording_id: str, user_id: str) -> bool:
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, title, original_filename, recorded_at, duration_seconds,
                  transcript_json, speaker_mapping,
                  datetime('now') AS read_at
           FROM recordings WHERE id = ? AND user_id = ?""",
        (recording_id, user_id),
    )
    if not rows:
        logger.warning("Recording %s not found for minutes generation", recording_id)
        return False
    rec = dict(rows[0])
    # generated_at records when speaker names were read, not when the run
    # ended, so a rename during a multi-minute run still leaves the minutes
    # stale for refresh_detailed_minutes_job. Same format as
    # speaker_mapping_updated_at (SQLite datetime('now')).
    read_at = rec["read_at"]
    if not rec.get("transcript_json"):
        logger.warning("Recording %s has no transcript_json for minutes", recording_id)
        return False

    await db.execute(
        """UPDATE recordings SET detailed_minutes_status = 'generating',
                  detailed_minutes_error = NULL
           WHERE id = ? AND user_id = ?""",
        (recording_id, user_id),
    )
    await db.commit()

    client: AsyncAzureOpenAI | None = None
    try:
        names = speaker_names(rec.get("speaker_mapping"))
        turns = build_turns(parse_phrases(rec["transcript_json"]), names)
        if not turns:
            raise ValueError("transcript has no recognized phrases")
        duration_s = rec.get("duration_seconds") or turns[-1].end_ms / 1000
        info = MeetingInfo(
            title=rec.get("title") or rec.get("original_filename") or "Untitled",
            recorded_at=rec.get("recorded_at") or "",
            duration_min=round(duration_s / 60),
            speakers=sorted(set(names.values())),
        )
        client = _get_client()
        doc, meta = await run_pipeline(client, info, turns)

        await db.execute(
            """UPDATE recordings
               SET detailed_minutes = ?, detailed_minutes_generated_at = ?,
                   detailed_minutes_status = 'ready', detailed_minutes_error = NULL,
                   detailed_minutes_meta = ?, updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (doc, read_at, json.dumps(meta), recording_id, user_id),
        )
        await db.commit()
        logger.info(
            "Generated detailed minutes for %s (%d chunks, %d -> %d tokens, %.0fs)",
            recording_id[:8], meta["chunks"], meta["transcript_tokens"],
            meta["minutes_tokens"], meta["seconds"],
        )
        return True
    except asyncio.CancelledError:
        logger.warning("Minutes generation cancelled for %s", recording_id)
        try:
            await db.execute(
                """UPDATE recordings SET detailed_minutes_status = 'failed',
                          detailed_minutes_error = 'cancelled'
                   WHERE id = ? AND user_id = ?""",
                (recording_id, user_id),
            )
            await db.commit()
        except Exception:
            logger.exception("Could not mark cancelled minutes run for %s", recording_id)
        raise
    except Exception as e:
        logger.exception("Failed to generate detailed minutes for %s", recording_id)
        error = f"{type(e).__name__}: {e}"[:500]
        await db.execute(
            """UPDATE recordings SET detailed_minutes_status = 'failed',
                      detailed_minutes_error = ?
               WHERE id = ? AND user_id = ?""",
            (error, recording_id, user_id),
        )
        await db.commit()
        return False
    finally:
        if client is not None:
            await client.close()
