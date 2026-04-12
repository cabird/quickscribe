"""MCP search service — cascading FTS5 search with filters."""

from __future__ import annotations

import json
import logging
import re

from app.database import get_db

logger = logging.getLogger(__name__)

# Columns selected for MCP search results (lightweight, no transcript text)
_MCP_COLUMNS = """
    r.id, r.title, r.description, r.duration_seconds,
    r.recorded_at, r.source, r.status, r.speaker_mapping,
    r.token_count, r.created_at
"""


def _sanitize_fts_query(query: str) -> str | None:
    """Sanitize a user query for FTS5 MATCH.

    Strips special characters except alphanumeric, spaces, and hyphens.
    Wraps each term in double quotes for literal matching.
    Returns None if the sanitized query is empty.
    """
    # Strip everything except alphanumeric, spaces, hyphens
    cleaned = re.sub(r"[^\w\s\-]", "", query)
    terms = cleaned.split()
    if not terms:
        return None
    return " ".join(f'"{term}"' for term in terms)


def _extract_speaker_names(speaker_mapping_raw: str | None) -> list[str]:
    """Extract display names from speaker_mapping JSON."""
    if not speaker_mapping_raw:
        return []
    try:
        mapping = json.loads(speaker_mapping_raw)
        names = []
        for entry in mapping.values():
            name = entry.get("displayName")
            if name:
                names.append(name)
        return names
    except (json.JSONDecodeError, AttributeError):
        return []


def _row_to_mcp_result(row: dict, tag_ids: list[str] | None = None, match_tier: str | None = None) -> dict:
    """Convert a DB row to the MCP search result shape."""
    result = {
        "id": row["id"],
        "title": row.get("title"),
        "description": row.get("description"),
        "duration_seconds": row.get("duration_seconds"),
        "recorded_at": row.get("recorded_at"),
        "source": row.get("source"),
        "status": row.get("status"),
        "speaker_names": _extract_speaker_names(row.get("speaker_mapping")),
        "tag_ids": tag_ids or [],
        "token_count": row.get("token_count"),
    }
    if match_tier is not None:
        result["match_tier"] = match_tier
    return result


async def _get_tag_ids_bulk(recording_ids: list[str]) -> dict[str, list[str]]:
    """Fetch tag IDs for multiple recordings in one query."""
    if not recording_ids:
        return {}
    db = await get_db()
    placeholders = ",".join("?" for _ in recording_ids)
    rows = await db.execute_fetchall(
        f"SELECT recording_id, tag_id FROM recording_tags WHERE recording_id IN ({placeholders})",
        recording_ids,
    )
    result: dict[str, list[str]] = {rid: [] for rid in recording_ids}
    for row in rows:
        r = dict(row)
        result[r["recording_id"]].append(r["tag_id"])
    return result


def _build_base_where(
    user_id: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    title_filter: str | None = None,
) -> tuple[str, list]:
    """Build WHERE clause fragments and params for common filters.

    Returns (where_clause, params) where where_clause starts with 'WHERE'.
    """
    clauses = ["r.user_id = ?", "r.status = 'ready'"]
    params: list = [user_id]

    if participant_id:
        clauses.append(
            """r.id IN (
                SELECT r2.id FROM recordings r2, json_each(r2.speaker_mapping) AS je
                WHERE r2.id = r.id
                  AND json_extract(je.value, '$.participantId') = ?
            )"""
        )
        params.append(participant_id)

    if date_from:
        clauses.append("COALESCE(r.recorded_at, r.created_at) >= ?")
        params.append(date_from)

    if date_to:
        clauses.append("COALESCE(r.recorded_at, r.created_at) <= ?")
        params.append(date_to)

    if title_filter:
        clauses.append("LOWER(r.title) LIKE ?")
        params.append(f"%{title_filter.lower()}%")

    return "WHERE " + " AND ".join(clauses), params


async def _fts_search(
    user_id: str,
    fts_query: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    exclude_ids: set[str] | None = None,
    title_filter: str | None = None,
) -> list[dict]:
    """Run an FTS5 MATCH query with filters. Returns list of row dicts."""
    db = await get_db()
    where_clause, params = _build_base_where(user_id, participant_id, date_from, date_to, title_filter=title_filter)

    # Add FTS match
    fts_condition = "r.rowid IN (SELECT rowid FROM recordings_fts WHERE recordings_fts MATCH ?)"
    where_clause += f" AND {fts_condition}"
    params.append(fts_query)

    # Exclude already-found IDs (for cascade)
    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        where_clause += f" AND r.id NOT IN ({placeholders})"
        params.extend(exclude_ids)

    sql = f"""
        SELECT {_MCP_COLUMNS}
        FROM recordings r
        {where_clause}
        ORDER BY COALESCE(r.recorded_at, r.created_at) DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    try:
        rows = await db.execute_fetchall(sql, params)
        return [dict(r) for r in rows]
    except Exception as e:
        # FTS5 syntax errors should not crash the endpoint
        logger.warning("FTS5 query failed: %s (query=%s)", e, fts_query)
        return []


async def search_recordings(
    user_id: str,
    query: str | None = None,
    mode: str = "cascade",
    participant_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
    title_filter: str | None = None,
) -> list[dict]:
    """Search or list recordings with optional FTS5 search and filters.

    Args:
        user_id: Authenticated user's ID.
        query: Optional search text.
        mode: Search mode — title, summary, full, or cascade.
        participant_id: Optional participant filter.
        date_from: Optional ISO date string (inclusive).
        date_to: Optional ISO date string (inclusive).
        limit: Max results (1-100).
        offset: Pagination offset.
        title_filter: Optional title substring filter (LIKE match, case-insensitive).

    Returns:
        List of result dicts matching the MCP response shape.
    """
    db = await get_db()
    limit = max(1, min(limit, 100))

    # If no query, just list with filters
    if not query:
        return await _list_recordings(user_id, participant_id, date_from, date_to, limit, offset, title_filter=title_filter)

    sanitized = _sanitize_fts_query(query)
    if not sanitized:
        return await _list_recordings(user_id, participant_id, date_from, date_to, limit, offset, title_filter=title_filter)

    if mode == "cascade":
        return await _cascade_search(user_id, sanitized, participant_id, date_from, date_to, limit, offset, title_filter=title_filter)

    # Single-tier search
    if mode == "title":
        fts_query = f"title:{sanitized}"
        tier_label = "title"
    elif mode == "summary":
        fts_query = f"{{title description search_summary}}:{sanitized}"
        tier_label = "summary"
    else:  # full
        fts_query = sanitized
        tier_label = "transcript"

    rows = await _fts_search(user_id, fts_query, participant_id, date_from, date_to, limit, offset, title_filter=title_filter)
    recording_ids = [r["id"] for r in rows]
    tag_map = await _get_tag_ids_bulk(recording_ids)
    return [
        _row_to_mcp_result(r, tag_ids=tag_map.get(r["id"]), match_tier=tier_label)
        for r in rows
    ]


async def _cascade_search(
    user_id: str,
    sanitized: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    title_filter: str | None = None,
) -> list[dict]:
    """Run cascading search: title -> summary -> full, deduplicating.

    Offset is applied to the combined result set across all tiers,
    not to individual tier queries. We fetch up to (offset + limit)
    results across tiers, then slice [offset:offset+limit].
    """
    total_needed = offset + limit
    all_results: list[tuple[dict, str]] = []
    seen_ids: set[str] = set()

    # Tier 1: title
    tier1_query = f"title:{sanitized}"
    tier1_rows = await _fts_search(
        user_id, tier1_query, participant_id, date_from, date_to,
        total_needed, 0, title_filter=title_filter,
    )
    for r in tier1_rows:
        if len(all_results) >= total_needed:
            break
        seen_ids.add(r["id"])
        all_results.append((r, "title"))

    # Tier 2: summary (title + description + search_summary)
    if len(all_results) < total_needed:
        remaining = total_needed - len(all_results)
        tier2_query = f"{{title description search_summary}}:{sanitized}"
        tier2_rows = await _fts_search(
            user_id, tier2_query, participant_id, date_from, date_to,
            remaining, 0, exclude_ids=seen_ids, title_filter=title_filter,
        )
        for r in tier2_rows:
            if len(all_results) >= total_needed:
                break
            seen_ids.add(r["id"])
            all_results.append((r, "summary"))

    # Tier 3: full text
    if len(all_results) < total_needed:
        remaining = total_needed - len(all_results)
        tier3_query = sanitized
        tier3_rows = await _fts_search(
            user_id, tier3_query, participant_id, date_from, date_to,
            remaining, 0, exclude_ids=seen_ids, title_filter=title_filter,
        )
        for r in tier3_rows:
            if len(all_results) >= total_needed:
                break
            seen_ids.add(r["id"])
            all_results.append((r, "transcript"))

    # Apply offset to the combined results
    page = all_results[offset:offset + limit]

    # Enrich with tags
    recording_ids = [r["id"] for r, _ in page]
    tag_map = await _get_tag_ids_bulk(recording_ids)
    return [
        _row_to_mcp_result(r, tag_ids=tag_map.get(r["id"]), match_tier=tier)
        for r, tier in page
    ]


async def _list_recordings(
    user_id: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    title_filter: str | None = None,
) -> list[dict]:
    """List recordings with filters (no FTS search)."""
    db = await get_db()
    where_clause, params = _build_base_where(user_id, participant_id, date_from, date_to, title_filter=title_filter)

    sql = f"""
        SELECT {_MCP_COLUMNS}
        FROM recordings r
        {where_clause}
        ORDER BY COALESCE(r.recorded_at, r.created_at) DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = await db.execute_fetchall(sql, params)
    row_dicts = [dict(r) for r in rows]
    recording_ids = [r["id"] for r in row_dicts]
    tag_map = await _get_tag_ids_bulk(recording_ids)
    return [
        _row_to_mcp_result(r, tag_ids=tag_map.get(r["id"]))
        for r in row_dicts
    ]
