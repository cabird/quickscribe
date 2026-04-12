"""MCP tool endpoints — read-only access to recordings, transcripts, participants, and AI chat.

All endpoints are tagged "mcp" so fastapi-mcp discovers them. Auth via
get_current_user_or_api_key (supports MCP bearer tokens, JWT, and API keys).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user_or_api_key
from app.config import get_settings
from app.database import get_db
from app.models import McpSpeaker, User
from app.services import mcp_search_service

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

CurrentUser = Annotated[User, Depends(get_current_user_or_api_key)]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums / request models
# ---------------------------------------------------------------------------


class SearchMode(str, Enum):
    title = "title"
    summary = "summary"
    full = "full"
    cascade = "cascade"


class McpChatRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# 1. Search recordings
# ---------------------------------------------------------------------------


@router.get("/recordings")
async def search_recordings(
    user: CurrentUser,
    query: str | None = None,
    mode: SearchMode = SearchMode.cascade,
    participant_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search or list recordings with optional FTS5 search and filters."""
    results = await mcp_search_service.search_recordings(
        user_id=user.id,
        query=query,
        mode=mode.value,
        participant_id=participant_id,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        limit=limit,
        offset=offset,
    )
    return results


# ---------------------------------------------------------------------------
# 2. Get recording
# ---------------------------------------------------------------------------


@router.get("/recordings/{recording_id}")
async def get_recording(recording_id: str, user: CurrentUser):
    """Get full metadata for a single recording, including AI summary and speakers."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, title, description, duration_seconds, recorded_at,
                  source, status, search_summary, search_keywords,
                  speaker_mapping, token_count
           FROM recordings
           WHERE id = ? AND user_id = ? AND status = 'ready'""",
        (recording_id, user.id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    row = dict(rows[0])

    # Parse speakers from speaker_mapping
    speakers: list[dict] = []
    mapping_raw = row.get("speaker_mapping")
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw)
            for label, entry in mapping.items():
                if isinstance(entry, dict):
                    speakers.append(
                        McpSpeaker(
                            label=label,
                            display_name=entry.get("displayName"),
                            participant_id=entry.get("participantId"),
                        ).model_dump()
                    )
        except (json.JSONDecodeError, AttributeError):
            pass

    # Parse search_keywords from JSON
    search_keywords = None
    keywords_raw = row.get("search_keywords")
    if keywords_raw:
        try:
            search_keywords = json.loads(keywords_raw)
        except (json.JSONDecodeError, Exception):
            pass

    # Fetch tag IDs
    tag_rows = await db.execute_fetchall(
        "SELECT tag_id FROM recording_tags WHERE recording_id = ?",
        (recording_id,),
    )
    tag_ids = [dict(r)["tag_id"] for r in tag_rows]

    return {
        "id": row["id"],
        "title": row.get("title"),
        "description": row.get("description"),
        "duration_seconds": row.get("duration_seconds"),
        "recorded_at": row.get("recorded_at"),
        "source": row.get("source"),
        "status": row.get("status"),
        "search_summary": row.get("search_summary"),
        "search_keywords": search_keywords,
        "speakers": speakers,
        "tag_ids": tag_ids,
        "token_count": row.get("token_count"),
    }


# ---------------------------------------------------------------------------
# 3. Get transcription
# ---------------------------------------------------------------------------


@router.get("/recordings/{recording_id}/transcript")
async def get_transcription(
    recording_id: str,
    user: CurrentUser,
    token_offset: int = Query(0, ge=0),
    token_limit: int = Query(10000, ge=1),
):
    """Get diarized transcript text with token-based pagination."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT diarized_text, transcript_text, token_count
           FROM recordings
           WHERE id = ? AND user_id = ? AND status = 'ready'""",
        (recording_id, user.id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    row = dict(rows[0])
    text = row.get("diarized_text") or row.get("transcript_text") or ""
    total_tokens = row.get("token_count") or (len(text) // 4)

    if not text:
        return {
            "recording_id": recording_id,
            "total_tokens": 0,
            "returned_tokens": 0,
            "token_offset": token_offset,
            "has_more": False,
            "text": "",
        }

    # Token offset exceeds total
    if token_offset >= total_tokens:
        return {
            "recording_id": recording_id,
            "total_tokens": total_tokens,
            "returned_tokens": 0,
            "token_offset": token_offset,
            "has_more": False,
            "text": "",
        }

    # Approximate character positions from token counts (~4 chars per token)
    chars_per_token = len(text) / total_tokens if total_tokens > 0 else 4.0
    char_offset = int(token_offset * chars_per_token)
    char_limit = int(token_limit * chars_per_token)

    # Split text into speaker turns (lines)
    turns = text.split("\n")

    # Find the first turn that starts at or after char_offset
    current_pos = 0
    start_turn_idx = 0
    for i, turn in enumerate(turns):
        turn_end = current_pos + len(turn)
        if turn_end > char_offset:
            start_turn_idx = i
            break
        current_pos = turn_end + 1  # +1 for the newline
    else:
        # Past the end
        return {
            "recording_id": recording_id,
            "total_tokens": total_tokens,
            "returned_tokens": 0,
            "token_offset": token_offset,
            "has_more": False,
            "text": "",
        }

    # Collect turns up to char_limit
    collected_turns: list[str] = []
    collected_chars = 0
    for i in range(start_turn_idx, len(turns)):
        turn = turns[i]
        turn_chars = len(turn)

        if collected_turns and collected_chars + turn_chars > char_limit:
            break

        # Always include the first eligible turn even if it exceeds the limit
        collected_turns.append(turn)
        collected_chars += turn_chars + 1  # +1 for newline

    result_text = "\n".join(collected_turns)
    returned_tokens = max(1, int(collected_chars / chars_per_token))
    has_more = (token_offset + returned_tokens) < total_tokens

    return {
        "recording_id": recording_id,
        "total_tokens": total_tokens,
        "returned_tokens": returned_tokens,
        "token_offset": token_offset,
        "has_more": has_more,
        "text": result_text,
    }


# ---------------------------------------------------------------------------
# 4. List participants
# ---------------------------------------------------------------------------


@router.get("/participants")
async def list_participants(user: CurrentUser):
    """List all participants for the authenticated user with recording counts."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT p.id, p.display_name, p.aliases, p.email, p.role, p.organization,
                  (
                      SELECT COUNT(DISTINCT r.id)
                      FROM recordings r, json_each(r.speaker_mapping) AS je
                      WHERE r.user_id = p.user_id
                        AND r.status = 'ready'
                        AND json_extract(je.value, '$.participantId') = p.id
                  ) AS recording_count
           FROM participants p
           WHERE p.user_id = ?
           ORDER BY p.display_name ASC""",
        (user.id,),
    )

    results = []
    for row in rows:
        r = dict(row)
        aliases = None
        if r.get("aliases"):
            try:
                aliases = json.loads(r["aliases"])
            except (json.JSONDecodeError, Exception):
                pass
        results.append({
            "id": r["id"],
            "display_name": r["display_name"],
            "aliases": aliases,
            "email": r.get("email"),
            "role": r.get("role"),
            "organization": r.get("organization"),
            "recording_count": r.get("recording_count", 0),
        })

    return results


# ---------------------------------------------------------------------------
# 5. Search participants
# ---------------------------------------------------------------------------


@router.get("/participants/search")
async def search_participants(
    user: CurrentUser,
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Fuzzy search participants by display_name and aliases. High recall."""
    db = await get_db()

    # Build search patterns: full query + individual words
    patterns = {query.lower()}
    words = query.split()
    if len(words) > 1:
        for word in words:
            word = word.strip()
            if word:
                patterns.add(word.lower())

    # Collect matching participant IDs with match quality
    # We'll query once with OR conditions for all patterns
    like_conditions = []
    params: list = [user.id]
    for pattern in patterns:
        like_val = f"%{pattern}%"
        like_conditions.append("(LOWER(p.display_name) LIKE ? OR LOWER(p.aliases) LIKE ?)")
        params.extend([like_val, like_val])

    where_likes = " OR ".join(like_conditions)

    rows = await db.execute_fetchall(
        f"""SELECT p.id, p.display_name, p.aliases, p.email, p.role, p.organization,
                   (
                       SELECT COUNT(DISTINCT r.id)
                       FROM recordings r, json_each(r.speaker_mapping) AS je
                       WHERE r.user_id = p.user_id
                         AND r.status = 'ready'
                         AND json_extract(je.value, '$.participantId') = p.id
                   ) AS recording_count
            FROM participants p
            WHERE p.user_id = ? AND ({where_likes})
            LIMIT ?""",
        params + [limit * 3],  # over-fetch for ranking
    )

    # Rank results
    query_lower = query.lower()
    scored: list[tuple[int, dict]] = []
    for row in rows:
        r = dict(row)
        name_lower = (r["display_name"] or "").lower()

        # Score: lower is better
        if name_lower == query_lower:
            score = 0  # exact match
        elif name_lower.startswith(query_lower):
            score = 1  # prefix match
        elif query_lower in name_lower:
            score = 2  # substring match
        else:
            score = 3  # alias match

        aliases = None
        if r.get("aliases"):
            try:
                aliases = json.loads(r["aliases"])
            except (json.JSONDecodeError, Exception):
                pass

        scored.append((score, {
            "id": r["id"],
            "display_name": r["display_name"],
            "aliases": aliases,
            "email": r.get("email"),
            "role": r.get("role"),
            "organization": r.get("organization"),
            "recording_count": r.get("recording_count", 0),
        }))

    scored.sort(key=lambda x: (x[0], (x[1]["display_name"] or "").lower()))
    return [item for _, item in scored[:limit]]


# ---------------------------------------------------------------------------
# 6. AI chat
# ---------------------------------------------------------------------------


@router.post("/recordings/{recording_id}/chat")
async def ai_chat(recording_id: str, body: McpChatRequest, user: CurrentUser):
    """Ask a question about a recording's transcript using AI."""
    settings = get_settings()
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="AI is not configured")

    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT diarized_text, transcript_text
           FROM recordings
           WHERE id = ? AND user_id = ? AND status = 'ready'""",
        (recording_id, user.id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    row = dict(rows[0])
    transcript_context = row.get("diarized_text") or row.get("transcript_text") or ""

    if not transcript_context:
        raise HTTPException(status_code=400, detail="Recording has no transcript")

    from app.services import ai_service

    chat_response = await ai_service.chat(
        messages=[{"role": "user", "content": body.message}],
        transcript_context=transcript_context,
    )

    return {
        "response": chat_response.message,
        "usage": chat_response.usage,
        "response_time_ms": chat_response.response_time_ms,
    }
