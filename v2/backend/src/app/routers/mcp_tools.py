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

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_or_api_key
from app.config import get_settings
from app.database import get_db
from app.models import (
    ALLOWED_RECORDING_FIELDS,
    McpBatchRequest,
    McpBatchResponse,
    McpSortOrder,
    McpSpeaker,
    McpSynthesizeRequest,
    McpTagMatch,
    McpTagSummary,
    McpView,
    User,
)
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
    """Body for ai_chat (POST /api/mcp/recordings/{recording_id}/chat)."""

    message: str = Field(
        ...,
        min_length=1,
        description=(
            "The question or instruction to ask about the recording. "
            "Stateless — provide all needed context in this single message; "
            "no prior conversation history is kept between calls. Best for "
            "targeted questions: summaries, action items, decisions, or "
            "speaker-specific points."
        ),
    )


# ---------------------------------------------------------------------------
# Field catalog (LLM-facing) — kept here so docstrings stay in sync.
# ---------------------------------------------------------------------------


_FIELD_CATALOG_DOC = """
    Available fields (request via `fields=...` or via a `view` preset):

      Always-included:
        id                          UUID string (~10 tok)

      Identity & metadata (small, ~10–30 tok each):
        title                       User-visible title; AI-generated if absent
        recorded_at                 ISO 8601 timestamp
        duration_seconds            Float seconds
        source                      "plaud" | "upload" | "paste"
        status                      "ready" | "failed" | "processing" | …
        token_count                 Transcript token estimate (integer)
        created_at, updated_at      ISO 8601 timestamps

      Summaries (small to medium):
        description                 1-sentence AI summary, also shown in UI
                                      (~30–80 tok)
        search_summary              3–5 sentence retrieval-optimized AI summary
                                      (~80–200 tok)
        search_keywords             AI-extracted JSON keyword array
                                      (~20–60 tok)

      People & tags (scales with N):
        speakers                    [{label, display_name, participant_id}, …]
                                      ~30 tok per speaker
        speaker_count               Integer count of labels in transcript
        unresolved_speaker_count    Integer count where participant_id is null
        speaker_names               (legacy) flat string array; prefer `speakers`
                                      ~5 tok per name
        tag_ids                     UUID array; resolve names via list_tags
                                      ~10 tok per tag

      Heavy fields — request only when needed:
        meeting_notes               Full markdown notes (~500–3000+ tok) ⚠
                                      Available only on get_recordings.
        meeting_notes_generated_at  ISO timestamp

      Search-only:
        match_tier                  "title" | "summary" | "transcript"
                                      (only present on search_recordings)

    View presets:
      compact   id, title, recorded_at, duration_seconds, speakers,
                speaker_count, unresolved_speaker_count, match_tier,
                token_count                         (~80–150 tok / row)
      summary   compact + description, search_summary, tag_ids
                                                    (~200–400 tok / row)
      full      every field above except meeting_notes
                (search_recordings default — backwards-compatible)
                                                    (~300–500 tok / row)

    Tip: for triage at scale, fields=["title","search_summary","speakers"]
    is ~150 tok/recording. ["title","meeting_notes"] at 50 IDs can exceed
    100K tokens.
"""


def _validate_fields_or_400(fields: list[str] | None) -> list[str] | None:
    """Apply fields whitelist validation, raising 400 with a useful body."""
    try:
        return mcp_search_service._validate_fields(fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _resolve_view(view: str | None) -> McpView | None:
    """Parse a `view` query string. None / empty -> None (use default)."""
    if not view:
        return None
    try:
        return McpView(view)
    except ValueError:
        valid = sorted(v.value for v in McpView)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view: {view!r}. Valid: {valid}",
        )


# ---------------------------------------------------------------------------
# 1. Search recordings
# ---------------------------------------------------------------------------


@router.get("/recordings", operation_id="search_recordings")
async def search_recordings(
    user: CurrentUser,
    query: str | None = Query(
        None,
        description=(
            "Free-text search. Matches are LITERAL terms — special characters "
            "are stripped (only alphanumerics, spaces, and hyphens survive) "
            "and FTS5 boolean operators are NOT supported. Multiple terms are "
            "AND-ed (a row must match every term). Examples that work: "
            "'authentication', 'design review', 'agent-framework'. Examples "
            "that DO NOT work as expected: 'auth OR login' (matches docs "
            "containing all three literal words including 'OR'); 'auth*' "
            "(the asterisk is stripped). Omit to list all recordings."
        ),
    ),
    mode: SearchMode = Query(
        SearchMode.cascade,
        description=(
            "Where to search. 'title' = titles only; 'summary' = titles + "
            "AI summaries/descriptions; 'full' = titles + summaries + full "
            "transcripts; 'cascade' (default) = title → summary → transcript "
            "in order, dedup across tiers, with `match_tier` annotated per "
            "result. Cascade is the recommended default."
        ),
    ),
    participant_id: str | None = Query(
        None,
        description=(
            "Restrict to recordings featuring this participant (UUID). "
            "Resolve a name to an ID via search_participants or list_participants."
        ),
    ),
    date_from: date | None = Query(
        None,
        description=(
            "Inclusive start date filter on `recorded_at` (ISO 8601, e.g. "
            "'2025-01-01'). Combine with `date_to` for a window."
        ),
    ),
    date_to: date | None = Query(
        None,
        description=(
            "Inclusive end date filter on `recorded_at` (ISO 8601). "
            "Combine with `date_from`."
        ),
    ),
    title: str | None = Query(
        None,
        description=(
            "Case-insensitive substring filter on the recording title. "
            "Independent of `query` — applied via SQL LIKE, not FTS5. "
            "Use to combine title-pattern filtering with content search."
        ),
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Max results per page (1–100). Default 20.",
    ),
    offset: int = Query(
        0,
        ge=0,
        description=(
            "Number of results to skip for pagination. Use with `paginated=true` "
            "for `has_more`/`next_offset` hints in the envelope."
        ),
    ),
    view: str | None = Query(
        None,
        description=(
            "Field-set preset: 'compact' | 'summary' | 'full'. "
            "Omit for backwards-compatible default ('full')."
        ),
    ),
    fields: list[str] | None = Query(
        None,
        description=(
            "Explicit field whitelist (overrides `view`). Unknown field "
            "names return 400. `id` is always included."
        ),
    ),
    sort: McpSortOrder = Query(
        McpSortOrder.recorded_at_desc,
        description=(
            "Sort order. On cascade mode, default sort preserves "
            "tier-major ordering (title > summary > transcript). Any "
            "explicit non-default sort flattens tiers and applies globally."
        ),
    ),
    tag_id: list[str] = Query(
        default_factory=list,
        description=(
            "Filter by tag IDs (repeatable). Combine with `tag_match`. "
            "Discover tag IDs via list_tags."
        ),
    ),
    tag_match: McpTagMatch = Query(
        McpTagMatch.any,
        description="How tag_ids combine: 'any' (default, OR) | 'all' (AND).",
    ),
    paginated: bool = Query(
        False,
        description=(
            "When true, return an envelope: "
            "{results, limit, offset, has_more, next_offset, total}. "
            "`total` is null in cascade mode (computing it is non-trivial). "
            "When false (default), return the bare list of results."
        ),
    ),
):
    """Search, filter, and list recordings across the QuickScribe library.

    Use this as the primary entry point to find relevant content. It supports
    broad discovery by free text, narrowing by participant, tag, and date
    range, and paging through large result sets. For most tasks, call this
    first before inspecting individual recordings or fetching transcripts.

    The `mode` parameter controls where text search happens:
    - `title`: search only recording titles
    - `summary`: search titles + AI-generated summaries/descriptions
    - `full`: search all indexed text including full transcripts
    - `cascade` (default): search titles first, then summaries, then transcripts,
      deduplicating across tiers. Results include `match_tier` showing where
      each hit came from. This is usually the best default.

    ⚠ Query syntax: `query` is sanitized for SQLite FTS5 — special characters
    are stripped (only alphanumerics, spaces, hyphens survive) and each term
    is wrapped as a literal phrase. Multiple terms are AND-ed (every term must
    match). FTS5 boolean operators (OR / NOT / NEAR / *) are NOT supported.
    To approximate OR, run multiple searches and merge client-side.

    Use `participant_id` to restrict results to recordings featuring a specific
    speaker (get participant IDs from list_participants or search_participants).
    Use `tag_id` (repeatable) + `tag_match` ('any'|'all') to filter by tags
    (discover tag IDs via list_tags). Use `date_from`/`date_to` to limit by
    recording date. Use `title` to filter by a case-insensitive substring
    match on the recording title (independent of the FTS `query`).

    Field selection — control payload size with one of two knobs:
    - `view`: convenience preset ('compact', 'summary', or 'full').
    - `fields`: explicit whitelist; wins over `view`. Unknown names → 400.
    `id` is always returned. The legacy `speaker_names` field is preserved
    for backwards compatibility — prefer the structured `speakers` list.
    {field_catalog}

    Pagination — pass `paginated=true` to get an envelope with `has_more`,
    `next_offset`, and (for non-cascade modes) `total`. Otherwise the bare
    list of results is returned (the historical default).

    Response shapes:
      paginated=false (default): [ {recording}, {recording}, ... ]
      paginated=true: {
        "results":     [ {recording}, ... ],
        "limit":       int,
        "offset":      int,
        "has_more":    bool,
        "next_offset": int | null,
        "total":       int | null   // null in cascade mode
      }

    After identifying promising candidates, call get_recording for one or
    get_recordings for many."""
    fields = _validate_fields_or_400(fields)
    view_enum = _resolve_view(view)

    results, has_more, total = await mcp_search_service.search_recordings(
        user_id=user.id,
        query=query,
        mode=mode.value,
        participant_id=participant_id,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        limit=limit,
        offset=offset,
        title_filter=title,
        tag_ids=list(tag_id) if tag_id else None,
        tag_match=tag_match,
        sort=sort,
        view=view_enum,
        fields=fields,
        compute_total=paginated,
    )

    if paginated:
        return {
            "results": results,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "total": total,
        }
    return results


# Stitch the field catalog into the docstring at import time so we maintain
# a single source of truth.
search_recordings.__doc__ = (search_recordings.__doc__ or "").replace(
    "{field_catalog}", _FIELD_CATALOG_DOC,
)


# ---------------------------------------------------------------------------
# 2. Get recording
# ---------------------------------------------------------------------------


@router.get("/recordings/{recording_id}", operation_id="get_recording")
async def get_recording(
    recording_id: Annotated[
        str,
        Path(description="Recording UUID (from search_recordings results)."),
    ],
    user: CurrentUser,
):
    """Retrieve full metadata for a single recording, including AI summary and speakers.

    Use this after search_recordings when you have a candidate recording and want
    to decide whether it is worth deeper extraction. Returns the AI-generated
    search_summary and search_keywords (designed for retrieval and triage), plus
    normalized speaker information showing how transcript speakers map to known
    participants.

    This is the inspection step between search and transcript retrieval:
    1. Find candidates with search_recordings
    2. Inspect each with get_recording
    3. Only then fetch the transcript or ask targeted questions

    Returns ALL fields including heavy `meeting_notes` (~500–3000+ tokens). For
    bulk lookups or to control payload size, use get_recordings instead — it
    supports `view`/`fields` projection.

    Use the returned token_count to judge transcript size, search_summary to
    assess relevance, and speakers to understand who participated.

    Returns 404 if the recording doesn't exist OR isn't owned by the caller
    (combined intentionally to prevent existence probing)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, title, description, duration_seconds, recorded_at,
                  source, status, search_summary, search_keywords,
                  speaker_mapping, token_count, meeting_notes,
                  meeting_notes_generated_at
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
        "meeting_notes": row.get("meeting_notes"),
        "meeting_notes_generated_at": row.get("meeting_notes_generated_at"),
        "speakers": speakers,
        "tag_ids": tag_ids,
        "token_count": row.get("token_count"),
    }


# ---------------------------------------------------------------------------
# 2b. Get recordings (bulk)
# ---------------------------------------------------------------------------


@router.post("/recordings/batch", operation_id="get_recordings", response_model=McpBatchResponse)
async def get_recordings(body: McpBatchRequest, user: CurrentUser):
    """Fetch metadata for many recordings at once.

    Use this when you have a list of recording IDs (e.g. from search_recordings
    or your own correlation logic) and want to inspect them together without
    making N round-trips. Up to 50 IDs per call. Duplicates are deduped server-
    side; results preserve first-seen order.

    Field selection — control payload size:
      - `view`: convenience preset ('compact', 'summary', 'full'). Default
        for this endpoint is 'summary' (lean by default for batch).
      - `fields`: explicit whitelist; wins over `view`. Unknown names → 400.
        `id` is always returned.
      - `view='full'` includes `meeting_notes` (heavy: ~500–3000+ tok per
        recording). Use sparingly at scale, or request `meeting_notes`
        explicitly via `fields`.
    {field_catalog}

    Response:
      {
        "results":     [...],   // shape depends on view/fields
        "missing_ids": [...],   // IDs that don't exist OR aren't yours
                                // (combined intentionally to prevent probing)
      }

    Errors: empty `recording_ids` → 400. More than 50 → 422. Unknown field
    name in `fields` → 400 with the list of valid fields.
    """
    if not body.recording_ids:
        raise HTTPException(
            status_code=400,
            detail="recording_ids must not be empty",
        )

    fields = _validate_fields_or_400(body.fields)

    results, missing_ids = await mcp_search_service.fetch_recordings_bulk(
        user_id=user.id,
        recording_ids=body.recording_ids,
        view=body.view,
        fields=fields,
    )

    return {"results": results, "missing_ids": missing_ids}


# Stitch field catalog into get_recordings docstring (single source of truth).
get_recordings.__doc__ = (get_recordings.__doc__ or "").replace(
    "{field_catalog}", _FIELD_CATALOG_DOC,
)


# ---------------------------------------------------------------------------
# 3. Get transcription
# ---------------------------------------------------------------------------


@router.get("/recordings/{recording_id}/transcript", operation_id="get_transcription")
async def get_transcription(
    recording_id: Annotated[
        str,
        Path(description="Recording UUID (from search_recordings results)."),
    ],
    user: CurrentUser,
    token_offset: int = Query(
        0,
        ge=0,
        description=(
            "Token-based pagination offset. Use the returned `token_offset + "
            "returned_tokens` from a prior call as the next offset. The "
            "underlying slicing is approximate (token-to-character ratio), "
            "so a small overlap or undershoot is possible — always trust "
            "the returned `has_more` flag, not arithmetic."
        ),
    ),
    token_limit: int = Query(
        10000,
        ge=1,
        description=(
            "Approximate maximum tokens to return. Token boundaries are "
            "estimated, and full speaker turns are preserved, so "
            "`returned_tokens` may slightly exceed this."
        ),
    ),
):
    """Retrieve the diarized transcript text for a recording with token-based pagination.

    Use this when you need the actual source text: quotations, evidence, detailed
    reasoning, or information not fully captured in titles or AI summaries. The
    transcript is returned as diarized text preserving speaker turns, one per
    line, formatted as "Name: utterance".

    Speaker labels: raw transcripts use generic "Speaker 1:", "Speaker 2:" etc.
    This endpoint rewrites those to display names from the recording's
    speaker_mapping where available (e.g. "Chris:", "Emerson:"). Speakers
    without a resolved display_name keep their generic label. Use get_recording
    or the `speakers` field on search_recordings to see the full mapping.

    Pagination is token-based. Use token_offset and token_limit to page through
    long transcripts. To preserve complete speaker turns, returned_tokens may
    slightly exceed token_limit. Always use the returned pagination fields
    (returned_tokens, has_more) to compute the next offset rather than assuming
    exact token slicing.

    Check token_count via search_recordings or get_recording first to know how
    large the transcript is. If you want an answer about a recording without
    reading the full transcript, ai_chat may be more efficient; if you need
    verifiable wording or broader extraction, use this endpoint.

    Response shape:
      {
        "recording_id":    str,
        "total_tokens":    int,
        "returned_tokens": int,
        "token_offset":    int,
        "has_more":        bool,
        "text":            str   // diarized text with speaker name prefixes
      }"""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT diarized_text, transcript_text, token_count, speaker_mapping
           FROM recordings
           WHERE id = ? AND user_id = ? AND status = 'ready'""",
        (recording_id, user.id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    row = dict(rows[0])
    text = row.get("diarized_text") or row.get("transcript_text") or ""

    # Replace "Speaker N" labels with real names from speaker_mapping
    mapping_raw = row.get("speaker_mapping")
    if mapping_raw and text:
        try:
            mapping = json.loads(mapping_raw)
            for label, entry in mapping.items():
                if isinstance(entry, dict):
                    name = entry.get("displayName")
                    if name and name != label:
                        text = text.replace(f"{label}:", f"{name}:")
        except (json.JSONDecodeError, AttributeError):
            pass
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


@router.get("/participants", operation_id="list_participants")
async def list_participants(user: CurrentUser):
    """List all known participants/speakers in the QuickScribe library.

    Use this to browse the people directory when you want to understand who
    appears in recordings, discover canonical names, or select a participant
    for filtering. Results include aliases, contact context (email, role,
    organization), the user-curated `relationship` and `notes` fields, an
    `is_user` flag (true when this participant is the QuickScribe user
    themselves), `first_seen` / `last_seen` timestamps, and `recording_count`
    showing how frequently each person appears.

    Use this when you want the full directory. If you already have a partial
    or uncertain name, search_participants is often a better first step. Once
    you have a participant ID, pass it to search_recordings(participant_id=...)
    to find their recordings."""
    db = await get_db()
    # Single-pass GROUP BY query — replaces the prior correlated-subquery
    # pattern (one query per participant, an N+1).
    rows = await db.execute_fetchall(
        """SELECT p.id, p.display_name, p.aliases, p.email, p.role, p.organization,
                  p.relationship, p.notes, p.is_user, p.first_seen, p.last_seen,
                  COALESCE(rc.recording_count, 0) AS recording_count
           FROM participants p
           LEFT JOIN (
               SELECT json_extract(je.value, '$.participantId') AS pid,
                      COUNT(DISTINCT r.id) AS recording_count
               FROM recordings r, json_each(r.speaker_mapping) AS je
               WHERE r.user_id = ?
                 AND r.status = 'ready'
                 AND r.speaker_mapping IS NOT NULL
               GROUP BY pid
           ) rc ON rc.pid = p.id
           WHERE p.user_id = ?
           ORDER BY p.display_name ASC""",
        (user.id, user.id),
    )

    return [_participant_row_to_dict(dict(row)) for row in rows]


def _participant_row_to_dict(r: dict) -> dict:
    """Shape a participant DB row into the MCP response."""
    aliases = None
    if r.get("aliases"):
        try:
            aliases = json.loads(r["aliases"])
        except (json.JSONDecodeError, Exception):
            pass
    return {
        "id": r["id"],
        "display_name": r["display_name"],
        "aliases": aliases,
        "email": r.get("email"),
        "role": r.get("role"),
        "organization": r.get("organization"),
        "relationship": r.get("relationship"),
        "notes": r.get("notes"),
        "is_user": bool(r.get("is_user")),
        "first_seen": r.get("first_seen"),
        "last_seen": r.get("last_seen"),
        "recording_count": int(r.get("recording_count") or 0),
    }


# ---------------------------------------------------------------------------
# 4b. List tags
# ---------------------------------------------------------------------------


@router.get("/tags", operation_id="list_tags", response_model=list[McpTagSummary])
async def list_tags(user: CurrentUser):
    """List all tags in the QuickScribe library.

    Tags are user-defined labels applied to recordings (e.g. 'work',
    'personal', 'project-x'). Each result includes a UI color and the
    number of recordings carrying that tag.

    Use this to:
      - Discover available tags before filtering search_recordings(tag_id=...)
      - Show the user a list of tag categories
      - Get tag names — search_recordings returns only `tag_ids`, not names

    Returns: list of {id, name, color, recording_count}."""
    db = await get_db()
    # Single-query GROUP BY — same pattern as the rewritten list_participants.
    # Tag → recording_tags → recordings. The double join through
    # `recordings.user_id = t.user_id` is defense in depth: recording_tags
    # itself lacks user_id.
    rows = await db.execute_fetchall(
        """SELECT t.id, t.name, t.color,
                  COUNT(DISTINCT r.id) AS recording_count
           FROM tags t
           LEFT JOIN recording_tags rt ON rt.tag_id = t.id
           LEFT JOIN recordings r
                ON r.id = rt.recording_id
                AND r.user_id = t.user_id
                AND r.status = 'ready'
           WHERE t.user_id = ?
           GROUP BY t.id, t.name, t.color
           ORDER BY t.name ASC""",
        (user.id,),
    )

    return [
        {
            "id": r["id"] if isinstance(r, dict) else dict(r)["id"],
            "name": dict(r)["name"],
            "color": dict(r)["color"],
            "recording_count": int(dict(r).get("recording_count") or 0),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 5. Search participants
# ---------------------------------------------------------------------------


@router.get("/participants/search", operation_id="search_participants")
async def search_participants(
    user: CurrentUser,
    query: str = Query(
        ...,
        min_length=1,
        description=(
            "Name or alias to search for. Multi-word queries are split — each "
            "word is matched independently against display_name and aliases "
            "(case-insensitive substring). Results are ranked: exact match > "
            "prefix > substring > alias-only. Optimized for recall, not "
            "precision — handles partial names, misspellings loosely, and "
            "alternate forms."
        ),
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Max results to return (1–100). Default 20.",
    ),
):
    """Search for participants by name or alias using fuzzy, high-recall matching.

    Use this when you have an approximate person name and want to resolve it to
    a known participant record. Searches display_name and aliases; multi-word
    queries are split so each word is searched independently. Results are ranked:
    exact match > prefix > substring > alias match.

    This tool is designed for recall over precision — it returns more matches
    rather than fewer, which is useful when names may be incomplete, misspelled,
    or known by alternate forms. It is the best way to turn a natural-language
    reference like "Sam" or "Dr. Chen" into a participant_id you can use in
    search_recordings(participant_id=...).

    Returned fields match list_participants: aliases, email, role, organization,
    relationship, notes, is_user, first_seen, last_seen, recording_count."""
    db = await get_db()

    # Build search patterns: full query + individual words
    patterns = {query.lower()}
    words = query.split()
    if len(words) > 1:
        for word in words:
            word = word.strip()
            if word:
                patterns.add(word.lower())

    like_conditions = []
    params: list = [user.id, user.id]  # rc subquery + outer WHERE
    for pattern in patterns:
        like_val = f"%{pattern}%"
        like_conditions.append("(LOWER(p.display_name) LIKE ? OR LOWER(p.aliases) LIKE ?)")
        params.extend([like_val, like_val])

    where_likes = " OR ".join(like_conditions)

    # Same single-pass GROUP BY pattern as list_participants — recording_count
    # is computed once for all participants, then joined in.
    rows = await db.execute_fetchall(
        f"""SELECT p.id, p.display_name, p.aliases, p.email, p.role, p.organization,
                   p.relationship, p.notes, p.is_user, p.first_seen, p.last_seen,
                   COALESCE(rc.recording_count, 0) AS recording_count
            FROM participants p
            LEFT JOIN (
                SELECT json_extract(je.value, '$.participantId') AS pid,
                       COUNT(DISTINCT r.id) AS recording_count
                FROM recordings r, json_each(r.speaker_mapping) AS je
                WHERE r.user_id = ?
                  AND r.status = 'ready'
                  AND r.speaker_mapping IS NOT NULL
                GROUP BY pid
            ) rc ON rc.pid = p.id
            WHERE p.user_id = ? AND ({where_likes})
            LIMIT ?""",
        params + [limit * 3],  # over-fetch for ranking
    )

    # Rank results
    query_lower = query.lower()
    scored: list[tuple[int, dict]] = []
    for row in rows:
        r = dict(row)
        shaped = _participant_row_to_dict(r)
        name_lower = (shaped["display_name"] or "").lower()

        if name_lower == query_lower:
            score = 0
        elif name_lower.startswith(query_lower):
            score = 1
        elif query_lower in name_lower:
            score = 2
        else:
            score = 3

        scored.append((score, shaped))

    scored.sort(key=lambda x: (x[0], (x[1]["display_name"] or "").lower()))
    return [item for _, item in scored[:limit]]


# ---------------------------------------------------------------------------
# 6. AI chat
# ---------------------------------------------------------------------------


@router.post("/recordings/{recording_id}/chat", operation_id="ai_chat")
async def ai_chat(
    recording_id: Annotated[
        str,
        Path(description="Recording UUID (from search_recordings results)."),
    ],
    body: McpChatRequest,
    user: CurrentUser,
):
    """Ask a question about a specific recording using its transcript as context.

    Use this when you want a focused answer about one recording without manually
    reading the full transcript. Best for targeted questions such as summaries,
    action items, decisions, speaker-specific points, or clarifying what was said.

    The full diarized transcript is sent as context with speaker labels resolved
    to display names where the recording's speaker_mapping has them (e.g.
    "Chris:" instead of "Speaker 1:"). The AI sees attributed speech.

    This endpoint is stateless — each call is independent with no conversation
    history. Include all necessary context in the message. If you need exact
    wording or citations, use get_transcription instead; if you need a quick
    answer, use this tool. To ask across MULTIPLE recordings at once, use
    synthesize_recordings.

    Returns 400 if the recording has no transcript, 404 if the recording does
    not exist or isn't owned by the caller, 503 if AI is not configured.

    Response shape:
      {
        "response":         str,    // the AI's answer
        "usage":            dict,   // token usage details
        "response_time_ms": int
      }"""
    settings = get_settings()
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="AI is not configured")

    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT diarized_text, transcript_text, speaker_mapping
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

    # Replace "Speaker N" labels with real names from speaker_mapping
    mapping_raw = row.get("speaker_mapping")
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw)
            for label, entry in mapping.items():
                if isinstance(entry, dict):
                    name = entry.get("displayName")
                    if name and name != label:
                        transcript_context = transcript_context.replace(f"{label}:", f"{name}:")
        except (json.JSONDecodeError, AttributeError):
            pass

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


# ---------------------------------------------------------------------------
# 7. Synthesize across recordings
# ---------------------------------------------------------------------------


@router.post("/synthesize", operation_id="synthesize_recordings")
async def synthesize_recordings(body: McpSynthesizeRequest, user: CurrentUser):
    """Synthesize information across multiple recordings using AI.

    Use this when you need to combine information from several recordings to answer
    a question, identify patterns, compare discussions over time, or produce a
    unified summary. Pass a list of recording IDs (from search_recordings) and a
    question. The server packs each recording's full transcript and metadata into
    a single LLM call and returns a synthesized answer.

    This is ideal for questions like "what recurring themes appear across these
    meetings?" or "how did the discussion about X evolve over time?" where
    single-recording ai_chat would require many separate calls and manual synthesis.

    Per-recording context preference: meeting_notes (if present) > diarized
    transcript > plain transcript. Speaker names are extracted from each
    recording's speaker_mapping and attached to the AI prompt for attribution.

    Limit: 20 recordings per call (returns 400 if exceeded). Uses full
    transcripts (truncated by the AI service to fit context limits when
    necessary). Returns 400 if no valid recordings are found (IDs missing or
    not owned by caller), 503 if AI is not configured.

    Response shape:
      {
        "response":         str,    // the synthesized answer
        "usage":            dict,   // token usage
        "response_time_ms": int
      }"""
    settings = get_settings()
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="AI is not configured")

    if len(body.recording_ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 recordings per synthesis request")

    if not body.recording_ids:
        raise HTTPException(status_code=400, detail="No recording IDs provided")

    db = await get_db()

    # Fetch all requested recordings
    placeholders = ",".join("?" for _ in body.recording_ids)
    rows = await db.execute_fetchall(
        f"""SELECT id, title, recorded_at, speaker_mapping,
                   search_summary, diarized_text, transcript_text,
                   meeting_notes
            FROM recordings
            WHERE id IN ({placeholders}) AND user_id = ? AND status = 'ready'""",
        [*body.recording_ids, user.id],
    )

    if not rows:
        raise HTTPException(status_code=400, detail="No valid recordings found")

    # Build recording data for the AI service
    recordings_data: list[dict] = []
    for row in rows:
        r = dict(row)

        # Extract speaker names from speaker_mapping
        speaker_names: list[str] = []
        mapping_raw = r.get("speaker_mapping")
        if mapping_raw:
            try:
                mapping = json.loads(mapping_raw)
                for entry in mapping.values():
                    if isinstance(entry, dict):
                        name = entry.get("displayName")
                        if name:
                            speaker_names.append(name)
            except (json.JSONDecodeError, AttributeError):
                pass

        # Prefer meeting notes > diarized > plain text
        text = r.get("meeting_notes") or r.get("diarized_text") or r.get("transcript_text") or ""

        recordings_data.append({
            "title": r.get("title"),
            "recorded_at": r.get("recorded_at"),
            "speaker_names": speaker_names,
            "text": text,
        })

    from app.services import ai_service

    synth_response = await ai_service.synthesize(
        recordings=recordings_data,
        question=body.question,
    )

    return {
        "response": synth_response.message,
        "usage": synth_response.usage,
        "response_time_ms": synth_response.response_time_ms,
    }
