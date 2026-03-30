"""Search endpoints — deep search (SSE), summary generation, and trace viewing."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.database import get_db
from app.models import DeepSearchRequest, User
from app.services import deep_search, search_summary_service

router = APIRouter(prefix="/api/search", tags=["search"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/deep")
async def deep_search_endpoint(body: DeepSearchRequest, user: CurrentUser):
    """Deep search across all recordings using the 3-tier LLM pipeline.

    Returns an SSE stream with progress events and the final result.
    """

    async def event_stream():
        async for event in deep_search.deep_search(body.question, user.id):
            event_type = event.get("event", "status")
            data = event.get("data", "")
            # Serialize data to JSON if it's a dict/list
            if isinstance(data, (dict, list)):
                data = json.dumps(data)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/recordings/{recording_id}/generate-summary")
async def generate_summary(recording_id: str, user: CurrentUser):
    """Generate or regenerate the search summary for a recording."""
    try:
        result = await search_summary_service.generate_search_summary(
            recording_id, user.id
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/history")
async def get_search_history(
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent deep search results."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT DISTINCT t1.search_id, t1.question, t1.created_at,
            (SELECT output_text FROM search_traces t2
             WHERE t2.search_id = t1.search_id AND t2.tier = 'tier3'
             LIMIT 1) as answer,
            (SELECT SUM(prompt_tokens) FROM search_traces t2
             WHERE t2.search_id = t1.search_id) as total_prompt_tokens,
            (SELECT SUM(completion_tokens) FROM search_traces t2
             WHERE t2.search_id = t1.search_id) as total_completion_tokens,
            (SELECT COUNT(*) FROM search_traces t2
             WHERE t2.search_id = t1.search_id) as call_count
        FROM search_traces t1
        GROUP BY t1.search_id
        ORDER BY MIN(t1.created_at) DESC
        LIMIT ?""",
        (limit,),
    )

    results = []
    for row in rows:
        r = dict(row)
        answer = r.get("answer") or ""
        results.append({
            "search_id": r["search_id"],
            "question": r["question"],
            "answer_preview": answer[:200] if answer else None,
            "answer": answer,
            "created_at": r["created_at"],
            "total_prompt_tokens": r.get("total_prompt_tokens", 0),
            "total_completion_tokens": r.get("total_completion_tokens", 0),
            "call_count": r.get("call_count", 0),
        })
    return {"data": results}


@router.get("/history/{search_id}")
async def get_search_history_detail(
    search_id: str,
    user: CurrentUser,
):
    """Get full details of a past search by search_id."""
    db = await get_db()

    # Get all trace entries for this search
    trace_rows = await db.execute_fetchall(
        """SELECT id, search_id, question, tier, step, model,
                  prompt_tokens, completion_tokens, reasoning_tokens,
                  duration_ms, input_text, output_text, created_at
           FROM search_traces
           WHERE search_id = ?
           ORDER BY id ASC""",
        (search_id,),
    )

    if not trace_rows:
        raise HTTPException(status_code=404, detail="Search not found")

    traces = [dict(t) for t in trace_rows]

    # Extract question from first trace
    question = traces[0]["question"]

    # Extract answer from tier3 synthesis trace
    answer = None
    for t in traces:
        if t["tier"] == "tier3":
            answer = t["output_text"]
            break

    # Reconstruct tag_map from tier1 traces (candidates step output)
    tag_map = {}
    for t in traces:
        if t["tier"] == "tier1" and t["step"] == "candidates" and t["output_text"]:
            try:
                parsed = json.loads(t["output_text"])
                if isinstance(parsed, dict) and "tag_map" in parsed:
                    tag_map = parsed["tag_map"]
                elif isinstance(parsed, dict):
                    # The output might be the tag_map itself
                    tag_map = parsed
            except (json.JSONDecodeError, TypeError):
                pass

    # Token totals
    total_prompt_tokens = sum(t.get("prompt_tokens") or 0 for t in traces)
    total_completion_tokens = sum(t.get("completion_tokens") or 0 for t in traces)

    return {
        "search_id": search_id,
        "question": question,
        "answer": answer,
        "tag_map": tag_map,
        "created_at": traces[0]["created_at"],
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "call_count": len(traces),
        "traces": traces,
    }


@router.get("/traces")
async def get_search_traces(
    user: CurrentUser,
    search_id: str = Query(..., description="The search_id to retrieve traces for"),
):
    """Return all traces for a given search_id."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, search_id, question, tier, step, model,
                  prompt_tokens, completion_tokens, reasoning_tokens,
                  duration_ms, input_text, output_text, created_at
           FROM search_traces
           WHERE search_id = ?
           ORDER BY id ASC""",
        (search_id,),
    )
    return [dict(row) for row in rows]


@router.get("/traces/recent")
async def get_recent_search_traces(
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100, description="Number of recent searches to return"),
):
    """Return recent search traces grouped by search_id.

    Returns the most recent searches (by first trace timestamp), with all
    their trace entries included.
    """
    db = await get_db()

    # Get the N most recent distinct search_ids
    search_id_rows = await db.execute_fetchall(
        """SELECT search_id, question, MIN(created_at) as started_at,
                  COUNT(*) as trace_count,
                  SUM(prompt_tokens) as total_prompt_tokens,
                  SUM(completion_tokens) as total_completion_tokens,
                  SUM(duration_ms) as total_duration_ms
           FROM search_traces
           GROUP BY search_id
           ORDER BY started_at DESC
           LIMIT ?""",
        (limit,),
    )

    results = []
    for row in search_id_rows:
        row = dict(row)
        # Fetch full traces for this search_id
        trace_rows = await db.execute_fetchall(
            """SELECT id, search_id, question, tier, step, model,
                      prompt_tokens, completion_tokens, reasoning_tokens,
                      duration_ms, input_text, output_text, created_at
               FROM search_traces
               WHERE search_id = ?
               ORDER BY id ASC""",
            (row["search_id"],),
        )
        results.append({
            "search_id": row["search_id"],
            "question": row["question"],
            "started_at": row["started_at"],
            "trace_count": row["trace_count"],
            "total_prompt_tokens": row["total_prompt_tokens"],
            "total_completion_tokens": row["total_completion_tokens"],
            "total_duration_ms": row["total_duration_ms"],
            "traces": [dict(t) for t in trace_rows],
        })

    return results
