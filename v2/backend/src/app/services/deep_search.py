"""3-Tier Deep Search Engine for QuickScribe.

Flow:
1. Tier 1 Router: Pack all summaries -> LLM answers directly OR returns candidate recordings
2. Tier 2 Extract: For each candidate, query full transcript in parallel
3. Tier 3 Synthesize: Combine all extracts into a single answer

Supports SSE streaming for progress reporting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import string
import time
import uuid
from typing import AsyncGenerator

import tiktoken
from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.database import get_db
from app.prompts import render_messages

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"[A-Z]{2}\d{2}")

_enc: tiktoken.Encoding | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_encoding() -> tiktoken.Encoding:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def count_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def _ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def generate_unique_tag(used_tags: set) -> str:
    """Generate a unique short tag like AB12."""
    for _ in range(10_000):
        letters = "".join(random.choices(string.ascii_uppercase, k=2))
        numbers = "".join(random.choices(string.digits, k=2))
        tag = f"{letters}{numbers}"
        if tag not in used_tags:
            return tag
    raise RuntimeError(f"Failed to generate unique tag ({len(used_tags)} in use)")


def _filter_tag_map(tag_map: dict, text: str) -> dict:
    """Return only tag_map entries whose tags appear in the text."""
    used = set(_TAG_RE.findall(text))
    return {k: v for k, v in tag_map.items() if k in used}


def _get_client() -> AsyncAzureOpenAI:
    settings = get_settings()
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


def _extract_reasoning_tokens(usage) -> int | None:
    """Extract reasoning_tokens from usage if available."""
    if not usage:
        return None
    try:
        details = usage.completion_tokens_details
        if details and hasattr(details, "reasoning_tokens"):
            return details.reasoning_tokens
    except (AttributeError, TypeError):
        pass
    return None


async def _persist_trace(
    search_id: str,
    question: str,
    entry: dict,
) -> None:
    """Insert a trace entry into the search_traces table."""
    try:
        db = await get_db()
        await db.execute(
            """INSERT INTO search_traces
               (search_id, question, tier, step, model,
                prompt_tokens, completion_tokens, reasoning_tokens,
                duration_ms, input_text, output_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                search_id,
                question,
                entry.get("tier", ""),
                entry.get("step", ""),
                entry.get("model", ""),
                entry.get("prompt_tokens", 0),
                entry.get("completion_tokens", 0),
                entry.get("reasoning_tokens"),
                entry.get("duration_ms", 0),
                entry.get("input_text", ""),
                entry.get("output_text", ""),
            ),
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist trace entry: {e}")


async def _call_llm_json(
    messages: list[dict],
    model: str,
    *,
    trace_log: list[dict] | None = None,
    trace_tier: str = "",
    trace_step: str = "",
    search_id: str = "",
    question: str = "",
) -> dict:
    """Call LLM and parse JSON response."""
    client = _get_client()
    start = time.time()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        duration_ms = _ms(start)

        if trace_log is not None:
            prompt_text = "\n".join(m.get("content", "") for m in messages)
            usage = response.usage
            reasoning_tokens = _extract_reasoning_tokens(usage)
            entry = {
                "tier": trace_tier,
                "step": trace_step,
                "model": model,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "reasoning_tokens": reasoning_tokens,
                "duration_ms": duration_ms,
                "input_preview": prompt_text[:500],
                "output_preview": content[:500],
                "output_raw": content,
                "input_text": prompt_text,
                "output_text": content,
                "search_id": search_id,
            }
            trace_log.append(entry)

            if search_id:
                await _persist_trace(search_id, question, entry)

        # Try parsing JSON; if it fails, ask the model to fix it
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"JSON parse failed for {trace_step}, attempting repair")
            # Strip markdown fences
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # One-shot repair call
                repair_response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": f"I expected valid JSON but got this response. Please return ONLY valid JSON that preserves the content:\n\n{content[:2000]}"},
                    ],
                    response_format={"type": "json_object"},
                )
                repaired = repair_response.choices[0].message.content or "{}"
                logger.info(f"JSON repair succeeded for {trace_step}")
                return json.loads(repaired)
    finally:
        await client.close()


async def _call_llm_text(
    messages: list[dict],
    model: str,
    *,
    trace_log: list[dict] | None = None,
    trace_tier: str = "",
    trace_step: str = "",
    search_id: str = "",
    question: str = "",
) -> str:
    """Call LLM and return text response."""
    client = _get_client()
    start = time.time()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
        )
        content = response.choices[0].message.content or ""
        duration_ms = _ms(start)

        if trace_log is not None:
            prompt_text = "\n".join(m.get("content", "") for m in messages)
            usage = response.usage
            reasoning_tokens = _extract_reasoning_tokens(usage)
            entry = {
                "tier": trace_tier,
                "step": trace_step,
                "model": model,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "reasoning_tokens": reasoning_tokens,
                "duration_ms": duration_ms,
                "input_preview": prompt_text[:500],
                "output_preview": content[:500],
                "output_raw": content,
                "input_text": prompt_text,
                "output_text": content,
                "search_id": search_id,
            }
            trace_log.append(entry)

            if search_id:
                await _persist_trace(search_id, question, entry)

        return content
    finally:
        await client.close()


def _extract_speaker_names_list(speaker_mapping_json: str | None) -> list[str]:
    """Extract speaker display names from JSON string."""
    if not speaker_mapping_json:
        return []
    try:
        mapping = json.loads(speaker_mapping_json)
        names = []
        for label, entry in mapping.items():
            name = entry.get("displayName") or label
            if name:
                names.append(name)
        return names
    except (json.JSONDecodeError, AttributeError):
        return []


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "?"
    minutes = int(seconds / 60)
    return f"{minutes}m" if minutes >= 1 else f"{int(seconds)}s"


def _build_trace_summary(trace_log: list[dict], start: float) -> dict:
    """Build a trace_summary SSE event from accumulated trace entries."""
    total_input = sum(t.get("prompt_tokens", 0) for t in trace_log)
    total_output = sum(t.get("completion_tokens", 0) for t in trace_log)
    total_dur = sum(t.get("duration_ms", 0) for t in trace_log)
    return {
        "event": "trace_summary",
        "data": {
            "total_calls": len(trace_log),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_duration_ms": total_dur,
            "traces": trace_log,
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def search_collection(
    question: str, collection_id: str, user_id: str
) -> AsyncGenerator[dict, None]:
    """Run deep search on a collection's recordings (Tier 2 + 3 only).

    Skips Tier 1 entirely — all collection items are treated as candidates.
    Yields the same SSE events as regular deep_search.
    """
    settings = get_settings()
    qa_start = time.time()
    q_short = question[:80] + ("..." if len(question) > 80 else "")
    logger.info(f"Collection search start | collection={collection_id} | q=\"{q_short}\"")

    search_id = str(uuid.uuid4())
    _trace_log: list[dict] = []

    try:
        db = await get_db()

        # Verify collection ownership
        col_rows = await db.execute_fetchall(
            "SELECT id FROM collections WHERE id = ? AND user_id = ?",
            (collection_id, user_id),
        )
        if not col_rows:
            yield {"event": "error", "data": "Collection not found"}
            yield {"event": "done", "data": ""}
            return

        # Load collection recordings
        yield {"event": "status", "data": "Loading collection recordings..."}

        item_rows = await db.execute_fetchall(
            """SELECT ci.recording_id, r.title, r.recorded_at, r.speaker_mapping,
                      r.search_summary, r.duration_seconds
               FROM collection_items ci
               JOIN recordings r ON r.id = ci.recording_id
               WHERE ci.collection_id = ? AND r.user_id = ? AND r.status = 'ready'
               ORDER BY r.recorded_at DESC""",
            (collection_id, user_id),
        )

        if not item_rows:
            yield {
                "event": "result",
                "data": {
                    "answer": "This collection has no recordings to search.",
                    "tag_map": {},
                    "sources": [],
                    "search_id": search_id,
                },
            }
            yield {"event": "done", "data": ""}
            return

        # Build tag_map for collection items (same tag system as regular search)
        used_tags: set[str] = set()
        tag_map: dict[str, dict] = {}
        all_items: list[dict] = []

        for row in item_rows:
            row = dict(row)
            tag = generate_unique_tag(used_tags)
            used_tags.add(tag)

            speakers = _extract_speaker_names_list(row.get("speaker_mapping"))
            tag_map[tag] = {
                "recording_id": row["recording_id"],
                "title": row.get("title") or "Untitled",
                "date": row.get("recorded_at") or "",
                "speakers": speakers,
            }
            all_items.append({
                "tag": tag,
                "recording_id": row["recording_id"],
                "title": row.get("title") or "Untitled",
                "date": row.get("recorded_at") or "",
                "speakers": speakers,
                "summary": row.get("search_summary") or "",
                "duration_seconds": row.get("duration_seconds"),
                "score": 1.0,
                "why": "In collection",
            })

        # Curated collections skip Tier 1 — user chose these recordings, use all of them
        candidates = all_items
        logger.info(f"Collection search | all {len(candidates)} items go to Tier 2 (curated collection)")

        # Emit candidates
        yield {
            "event": "candidates",
            "data": [
                {
                    "tag": c["tag"],
                    "title": c["title"],
                    "date": c["date"],
                    "score": c["score"],
                    "why": c["why"],
                    "recording_id": c["recording_id"],
                }
                for c in candidates
            ],
        }
        yield {
            "event": "status",
            "data": f"Extracting details from {len(candidates)} recordings...",
        }

        # ----- Tier 2: Extract -----
        trace_before_t2 = len(_trace_log)
        extracts = await _tier2_extract(
            question, candidates, tag_map, user_id, trace_log=_trace_log,
            search_id=search_id,
        )

        for entry in _trace_log[trace_before_t2:]:
            yield {"event": "trace", "data": {**entry, "search_id": search_id}}

        for ext in extracts:
            yield {
                "event": "extract",
                "data": {
                    "tag": ext.get("tag"),
                    "title": ext.get("title"),
                    "date": ext.get("date"),
                    "answer": ext.get("answer", "")[:500],
                },
            }

        if not extracts:
            logger.info(f"Collection search done | no relevant extracts | {_ms(qa_start)}ms")
            yield {
                "event": "result",
                "data": {
                    "answer": "I found the recordings in this collection but couldn't extract useful information for your question.",
                    "tag_map": {},
                    "sources": [],
                    "search_id": search_id,
                },
            }
            yield _build_trace_summary(_trace_log, qa_start)
            yield {"event": "done", "data": ""}
            return

        # ----- Tier 3: Synthesize -----
        yield {"event": "status", "data": f"Synthesizing answer from {len(extracts)} recordings..."}

        trace_before_t3 = len(_trace_log)
        result = await _tier3_synthesize(
            question, extracts, tag_map, trace_log=_trace_log,
            search_id=search_id,
        )

        for entry in _trace_log[trace_before_t3:]:
            yield {"event": "trace", "data": {**entry, "search_id": search_id}}

        logger.info(
            f"Collection search done | {len(extracts)} extracts synthesized | {_ms(qa_start)}ms"
        )

        # Save to collection_searches
        try:
            from app.services.collection_service import compute_item_set_hash
            item_set_hash = await compute_item_set_hash(collection_id)
            answer_text = result.get("answer", "")
            cs_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO collection_searches
                   (id, collection_id, question, answer, item_count, item_set_hash, search_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cs_id, collection_id, question, answer_text, len(candidates), item_set_hash, search_id),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to save collection search record: {e}")

        # Create a sync_run entry for tracing
        try:
            run_id = str(uuid.uuid4())
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                """INSERT INTO sync_runs (id, started_at, finished_at, status, trigger, type, stats_json)
                   VALUES (?, ?, ?, 'completed', 'manual', 'collection_search', ?)""",
                (run_id, now, now, json.dumps({"search_id": search_id, "collection_id": collection_id})),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to save collection search sync_run: {e}")

        yield {"event": "tag_map", "data": result["tag_map"]}
        yield {"event": "result", "data": {**result, "search_id": search_id}}
        yield _build_trace_summary(_trace_log, qa_start)
        yield {"event": "done", "data": ""}

    except Exception as exc:
        logger.error(f"Collection search error: {exc}", exc_info=True)
        yield {"event": "error", "data": str(exc)}
        yield _build_trace_summary(_trace_log, qa_start)
        yield {"event": "done", "data": ""}


async def deep_search(question: str, user_id: str) -> AsyncGenerator[dict, None]:
    """Run the 3-tier deep search pipeline, yielding SSE events for progress.

    Event types:
    - {"event": "status", "data": "..."}           Progress messages
    - {"event": "tag_map", "data": {...}}           Tag map for citation rendering
    - {"event": "result", "data": {"answer": ..., "tag_map": ..., "sources": [...]}}
    - {"event": "error", "data": "..."}
    - {"event": "done", "data": ""}
    """
    settings = get_settings()
    qa_start = time.time()
    q_short = question[:80] + ("..." if len(question) > 80 else "")
    logger.info(f"Deep search start | q=\"{q_short}\"")

    # Generate a unique search_id for this search session
    search_id = str(uuid.uuid4())

    # Accumulate trace entries for debugging
    _trace_log: list[dict] = []

    try:
        # ----- Tier 1: Router -----
        yield {"event": "status", "data": "Searching recording summaries..."}

        router_result, tag_map = await _tier1_router(
            question, user_id, trace_log=_trace_log,
            search_id=search_id,
        )

        # Emit trace events for tier 1 calls
        for entry in _trace_log:
            yield {"event": "trace", "data": {**entry, "search_id": search_id}}

        if router_result.get("answered"):
            # Answered directly from summaries
            answer = router_result["answer"]
            filtered_tags = _filter_tag_map(tag_map, answer)
            sources = router_result.get("sources", [])
            logger.info(f"Deep search done | answered from summaries | {_ms(qa_start)}ms")
            yield {"event": "tag_map", "data": filtered_tags}
            yield {
                "event": "result",
                "data": {"answer": answer, "tag_map": filtered_tags, "sources": sources, "search_id": search_id},
            }
            yield _build_trace_summary(_trace_log, qa_start)
            yield {"event": "done", "data": ""}
            return

        candidates = router_result.get("candidates", [])
        if not candidates:
            logger.info(f"Deep search done | no candidates | {_ms(qa_start)}ms")
            yield {
                "event": "result",
                "data": {
                    "answer": "I couldn't find any recordings relevant to your question.",
                    "tag_map": {},
                    "sources": [],
                    "search_id": search_id,
                },
            }
            yield _build_trace_summary(_trace_log, qa_start)
            yield {"event": "done", "data": ""}
            return

        # Emit detailed candidate info
        yield {
            "event": "candidates",
            "data": [
                {
                    "tag": c.get("tag"),
                    "title": c.get("title"),
                    "date": c.get("date"),
                    "score": c.get("score"),
                    "why": c.get("why"),
                    "recording_id": c.get("recording_id"),
                }
                for c in candidates
            ],
        }
        yield {
            "event": "status",
            "data": f"Found {len(candidates)} relevant recordings. Extracting details...",
        }

        # ----- Tier 2: Extract -----
        trace_before_t2 = len(_trace_log)
        extracts = await _tier2_extract(
            question, candidates, tag_map, user_id, trace_log=_trace_log,
            search_id=search_id,
        )

        # Emit trace events for tier 2 calls
        for entry in _trace_log[trace_before_t2:]:
            yield {"event": "trace", "data": {**entry, "search_id": search_id}}

        # Emit each extract so UI can show per-recording results
        for ext in extracts:
            yield {
                "event": "extract",
                "data": {
                    "tag": ext.get("tag"),
                    "title": ext.get("title"),
                    "date": ext.get("date"),
                    "answer": ext.get("answer", "")[:500],  # truncate for SSE
                },
            }

        if not extracts:
            logger.info(f"Deep search done | no relevant extracts | {_ms(qa_start)}ms")
            yield {
                "event": "result",
                "data": {
                    "answer": "I found potentially relevant recordings but couldn't extract useful information from them.",
                    "tag_map": {},
                    "sources": [],
                    "search_id": search_id,
                },
            }
            yield _build_trace_summary(_trace_log, qa_start)
            yield {"event": "done", "data": ""}
            return

        # ----- Tier 3: Synthesize -----
        yield {"event": "status", "data": f"Synthesizing answer from {len(extracts)} recordings..."}

        trace_before_t3 = len(_trace_log)
        result = await _tier3_synthesize(
            question, extracts, tag_map, trace_log=_trace_log,
            search_id=search_id,
        )

        # Emit trace events for tier 3 calls
        for entry in _trace_log[trace_before_t3:]:
            yield {"event": "trace", "data": {**entry, "search_id": search_id}}

        logger.info(
            f"Deep search done | {len(extracts)} extracts synthesized | {_ms(qa_start)}ms"
        )
        yield {"event": "tag_map", "data": result["tag_map"]}
        yield {"event": "result", "data": {**result, "search_id": search_id}}
        yield _build_trace_summary(_trace_log, qa_start)
        yield {"event": "done", "data": ""}

    except Exception as exc:
        logger.error(f"Deep search error: {exc}", exc_info=True)
        yield {"event": "error", "data": str(exc)}
        yield _build_trace_summary(_trace_log, qa_start)
        yield {"event": "done", "data": ""}


# ---------------------------------------------------------------------------
# Tier 1: Router
# ---------------------------------------------------------------------------


async def _tier1_router(
    question: str, user_id: str, *, trace_log: list[dict] | None = None,
    search_id: str = "",
) -> tuple[dict, dict]:
    """Load summaries, assign tags, batch, and route via LLM.

    Returns (result, tag_map).
    """
    settings = get_settings()
    db = await get_db()

    # Load all recordings with summary data for this user
    rows = await db.execute_fetchall(
        """SELECT id, title, description, search_summary, duration_seconds,
                  recorded_at, speaker_mapping
           FROM recordings
           WHERE user_id = ? AND status = 'ready'
           ORDER BY recorded_at DESC""",
        (user_id,),
    )

    if not rows:
        logger.warning("Tier 1 router | no recordings found")
        return {"answered": False, "candidates": []}, {}

    # Assign tags and build tagged lines
    used_tags: set[str] = set()
    tag_map: dict[str, dict] = {}
    tagged_lines: list[tuple[str, str, int]] = []  # (tag, text, token_count)

    for row in rows:
        row = dict(row)
        summary = row.get("search_summary") or row.get("description") or ""
        if not summary:
            continue

        tag = generate_unique_tag(used_tags)
        used_tags.add(tag)

        speakers = _extract_speaker_names_list(row.get("speaker_mapping"))
        tag_map[tag] = {
            "recording_id": row["id"],
            "title": row.get("title") or "Untitled",
            "date": row.get("recorded_at") or "",
            "speakers": speakers,
        }

        line = (
            f"[[{tag}]] {row.get('title') or 'Untitled'}\n"
            f"date:{row.get('recorded_at') or '?'} | "
            f"speakers:{', '.join(speakers) if speakers else '?'} | "
            f"duration:{_format_duration(row.get('duration_seconds'))}\n"
            f"{summary}"
        )
        tagged_lines.append((tag, line, count_tokens(line)))

    if not tagged_lines:
        logger.warning("Tier 1 router | no summaries available")
        return {"answered": False, "candidates": []}, {}

    # Pack into batches
    budget = settings.deep_search_batch_token_limit
    _SEP_OVERHEAD = 4
    question_tokens = count_tokens(question)
    # Reserve space for prompt template + question + response
    effective_budget = budget - question_tokens - 2000

    batches: list[list[tuple[str, str]]] = []
    current_batch: list[tuple[str, str]] = []
    current_tokens = 0

    for tag, line, tok in tagged_lines:
        item_cost = tok + (_SEP_OVERHEAD if current_batch else 0)
        if current_tokens + item_cost > effective_budget and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
            item_cost = tok
        current_batch.append((tag, line))
        current_tokens += item_cost
    if current_batch:
        batches.append(current_batch)

    num_batches = len(batches)
    logger.info(
        f"Tier 1 router | {len(tagged_lines)} summaries -> {num_batches} batch(es)"
    )

    model = settings.azure_openai_mini_deployment
    max_candidates = settings.deep_search_max_candidates

    if num_batches == 1:
        return await _router_single(
            question, batches[0], tag_map, max_candidates, model,
            trace_log=trace_log, search_id=search_id,
        )
    else:
        return await _router_batched(
            question, batches, tag_map, max_candidates, model,
            trace_log=trace_log, search_id=search_id,
        )


async def _router_single(
    question: str,
    batch: list[tuple[str, str]],
    tag_map: dict,
    max_candidates: int,
    model: str,
    *,
    trace_log: list[dict] | None = None,
    search_id: str = "",
) -> tuple[dict, dict]:
    """Single-batch: can answer directly or return candidates."""
    packed = "\n\n---\n\n".join(line for _, line in batch)
    messages = render_messages("deep_search_router_single",
        num_recordings=len(batch),
        question=question,
        summaries=packed,
        max_candidates=max_candidates,
    )

    logger.info(
        f"Tier 1 single | {len(batch)} recordings | ~{count_tokens(packed):,} tokens"
    )

    try:
        data = await _call_llm_json(
            messages=messages,
            model=model,
            trace_log=trace_log,
            trace_tier="tier1",
            trace_step="router_single",
            search_id=search_id,
            question=question,
        )
    except Exception as e:
        logger.error(f"Tier 1 router LLM error: {e}")
        # Fallback: return first few as candidates
        fallback = [
            {**tag_map[t], "tag": t, "score": 0.5, "why": "Router failed; fallback"}
            for t in list(tag_map.keys())[:5]
        ]
        return {"answered": False, "candidates": fallback}, tag_map

    if data.get("answered"):
        # Resolve source tags
        sources = []
        for src_tag in data.get("sources", []):
            src_tag = src_tag.strip("[]")
            if src_tag in tag_map:
                sources.append(src_tag)
        logger.info(f"Tier 1 single | answered directly | {len(sources)} sources")
        return {
            "answered": True,
            "answer": data["answer"],
            "sources": sources,
        }, tag_map
    else:
        candidates = _resolve_candidates(data.get("candidates", []), tag_map, max_candidates)
        logger.info(f"Tier 1 single | {len(candidates)} candidates returned")
        return {"answered": False, "candidates": candidates}, tag_map


async def _router_batched(
    question: str,
    batches: list[list[tuple[str, str]]],
    tag_map: dict,
    max_candidates: int,
    model: str,
    *,
    trace_log: list[dict] | None = None,
    search_id: str = "",
) -> tuple[dict, dict]:
    """Multi-batch: candidates-only, run in parallel, merge results."""
    total_batches = len(batches)

    async def run_batch(batch_idx: int, batch: list[tuple[str, str]]) -> list[dict]:
        packed = "\n\n---\n\n".join(line for _, line in batch)
        messages = render_messages("deep_search_router_batch",
            num_recordings=len(batch),
            batch_index=batch_idx + 1,
            total_batches=total_batches,
            question=question,
            summaries=packed,
            max_candidates=max_candidates,
        )
        try:
            data = await _call_llm_json(
                messages=messages,
                model=model,
                trace_log=trace_log,
                trace_tier="tier1",
                trace_step=f"router_batch_{batch_idx + 1}",
                search_id=search_id,
                question=question,
            )
            return data.get("candidates", [])
        except Exception as e:
            logger.error(f"Tier 1 batch {batch_idx+1} error: {e}")
            return []

    # Run all batches in parallel
    tasks = [run_batch(i, b) for i, b in enumerate(batches)]
    results = await asyncio.gather(*tasks)

    # Merge all candidates
    all_candidates = []
    for batch_candidates in results:
        all_candidates.extend(batch_candidates)

    # Dedup by recording_id (via tag), keep highest score
    seen_ids: dict[str, dict] = {}
    for c in all_candidates:
        tag = c.get("tag", "")
        if tag not in tag_map:
            continue
        rec_id = tag_map[tag]["recording_id"]
        score = c.get("score", 0)
        if rec_id not in seen_ids or score > seen_ids[rec_id].get("score", 0):
            seen_ids[rec_id] = {**c, "tag": tag}

    # Sort by score, take top K
    sorted_candidates = sorted(
        seen_ids.values(), key=lambda x: x.get("score", 0), reverse=True
    )[:max_candidates]

    candidates = _resolve_candidates(sorted_candidates, tag_map, max_candidates)
    logger.info(
        f"Tier 1 batched | {total_batches} batches | {len(candidates)} candidates after merge"
    )
    return {"answered": False, "candidates": candidates}, tag_map


def _resolve_candidates(
    raw_candidates: list[dict], tag_map: dict, max_candidates: int
) -> list[dict]:
    """Resolve raw LLM candidates against tag_map, adding recording metadata."""
    resolved = []
    for c in raw_candidates[:max_candidates]:
        tag = c.get("tag", "")
        if tag in tag_map:
            resolved.append(
                {
                    "tag": tag,
                    "recording_id": tag_map[tag]["recording_id"],
                    "title": tag_map[tag]["title"],
                    "date": tag_map[tag].get("date", ""),
                    "speakers": tag_map[tag].get("speakers", []),
                    "score": c.get("score", 0),
                    "why": c.get("why", ""),
                }
            )
    return resolved


# ---------------------------------------------------------------------------
# Tier 2: Extract
# ---------------------------------------------------------------------------


async def _tier2_extract(
    question: str,
    candidates: list[dict],
    tag_map: dict,
    user_id: str,
    *,
    trace_log: list[dict] | None = None,
    search_id: str = "",
) -> list[dict]:
    """For each candidate recording, extract relevant info from the full transcript.

    Runs in parallel with a concurrency cap of 8.
    Returns list of {tag, title, date, answer} for relevant extracts.
    """
    settings = get_settings()
    db = await get_db()
    model = settings.azure_openai_mini_deployment

    sem = asyncio.Semaphore(8)  # Cap concurrent LLM calls

    async def extract_one(candidate: dict) -> dict | None:
        async with sem:
            rec_id = candidate["recording_id"]
            tag = candidate["tag"]

            # Load full transcript
            row = await db.execute_fetchall(
                "SELECT diarized_text, transcript_text FROM recordings WHERE id = ?",
                (rec_id,),
            )
            if not row:
                return None

            rec = dict(row[0])
            transcript = rec.get("diarized_text") or rec.get("transcript_text") or ""
            if not transcript:
                return None

            # Truncate very long transcripts
            max_chars = 100_000
            if len(transcript) > max_chars:
                half = max_chars // 2
                transcript = (
                    transcript[:half]
                    + "\n\n[... transcript truncated ...]\n\n"
                    + transcript[-half:]
                )

            messages = render_messages("deep_search_extract",
                question=question,
                title=candidate.get("title", "Untitled"),
                date=candidate.get("date", "unknown"),
                speakers=", ".join(candidate.get("speakers", [])) or "unknown",
                transcript=transcript,
            )

            try:
                answer = await _call_llm_text(
                    messages=messages,
                    model=model,
                    trace_log=trace_log,
                    trace_tier="tier2",
                    trace_step=f"extract_{tag}_{(candidate.get('title') or 'Untitled')[:20]}",
                    search_id=search_id,
                    question=question,
                )

                stripped = answer.strip()
                if not stripped or stripped.upper() == "NOT_RELEVANT":
                    logger.info(f"Tier 2 | {tag} ({candidate.get('title', '?')[:30]}) -> NOT_RELEVANT")
                    return None

                logger.info(
                    f"Tier 2 | {tag} ({candidate.get('title', '?')[:30]}) -> "
                    f"{len(stripped.split())} words"
                )
                return {
                    "tag": tag,
                    "title": candidate.get("title", "Untitled"),
                    "date": candidate.get("date", ""),
                    "speakers": candidate.get("speakers", []),
                    "answer": stripped,
                }
            except Exception as e:
                logger.error(f"Tier 2 extract error for {tag}: {e}")
                return None

    # Run all extractions in parallel
    tasks = [extract_one(c) for c in candidates]
    results = await asyncio.gather(*tasks)

    # Filter None results
    extracts = [r for r in results if r is not None]
    logger.info(f"Tier 2 complete | {len(extracts)}/{len(candidates)} relevant")
    return extracts


# ---------------------------------------------------------------------------
# Tier 3: Synthesize
# ---------------------------------------------------------------------------


async def _tier3_synthesize(
    question: str,
    extracts: list[dict],
    tag_map: dict,
    *,
    trace_log: list[dict] | None = None,
    search_id: str = "",
) -> dict:
    """Combine per-recording extracts into a single synthesized answer.

    Returns {"answer": str, "tag_map": dict, "sources": list[str]}.
    """
    settings = get_settings()

    # Single extract: skip synthesis LLM call
    if len(extracts) == 1:
        extract = extracts[0]
        answer = extract["answer"]
        tag = extract["tag"]
        # Ensure the tag is cited
        if f"[[{tag}]]" not in answer:
            answer = answer.rstrip() + f"\n\nSource: [[{tag}]]"
        filtered_tags = _filter_tag_map(tag_map, answer)
        return {
            "answer": answer,
            "tag_map": filtered_tags,
            "sources": [tag],
        }

    # Build per-recording section
    per_recording_answers = ""
    for ext in extracts:
        speakers = ", ".join(ext.get("speakers", [])) if ext.get("speakers") else ""
        header = f"### [[{ext['tag']}]] {ext['title']} ({ext.get('date') or 'Unknown date'})"
        if speakers:
            header += f"\nSpeakers: {speakers}"
        per_recording_answers += f"{header}\n{ext['answer']}\n\n"

    messages = render_messages("deep_search_synthesize",
        question=question,
        per_recording_answers=per_recording_answers,
    )

    # Use the main model for synthesis quality
    model = settings.azure_openai_mini_deployment

    try:
        answer = await _call_llm_text(
            messages=messages,
            model=model,
            trace_log=trace_log,
            trace_tier="tier3",
            trace_step="synthesis",
            search_id=search_id,
            question=question,
        )
    except Exception as e:
        logger.error(f"Tier 3 synthesis error: {e}")
        # Fallback: concatenate extracts
        answer = "## Search Results\n\n"
        for ext in extracts:
            answer += f"### [[{ext['tag']}]] {ext['title']}\n{ext['answer']}\n\n"

    filtered_tags = _filter_tag_map(tag_map, answer)
    sources = [ext["tag"] for ext in extracts if f"[[{ext['tag']}]]" in answer]
    if not sources:
        # If synthesis didn't cite any tags, include all extract tags
        sources = [ext["tag"] for ext in extracts]

    return {
        "answer": answer,
        "tag_map": filtered_tags,
        "sources": sources,
    }
