"""MCP search service — cascading FTS5 search with filters.

This module owns the read-side query plumbing for MCP. The router layer
provides the HTTP/MCP surface, validates parameters, and shapes the response
envelope; this module owns SQL, FTS5, projection, and pagination math.

Public functions:

  search_recordings(...)
      Returns (results, has_more, total). `total` is None when:
        - paginated=False (caller doesn't need it), or
        - mode == cascade (computing it would require a second UNION-CTE
          query — deferred; see plan).

  fetch_recordings_bulk(...)
      Bulk lookup for get_recordings. Returns (results, missing_ids).

The shape of each row in `results` depends on `view` and `fields`. Field
selection rules live in models.view_field_set() and ALLOWED_RECORDING_FIELDS.
"""

from __future__ import annotations

import json
import logging
import re

from app.database import get_db
from app.models import (
    ALLOWED_RECORDING_FIELDS,
    McpSortOrder,
    McpTagMatch,
    McpView,
    view_field_set,
)

logger = logging.getLogger(__name__)


# Columns selected for MCP search results. We over-select compared to the
# narrowest view (compact) because views/fields are decided per-row in
# Python, and the cost of a few extra columns is far less than running
# multiple SQL queries with different projections.
_MCP_COLUMNS = """
    r.id, r.title, r.description, r.duration_seconds,
    r.recorded_at, r.source, r.status, r.speaker_mapping,
    r.token_count, r.created_at, r.updated_at,
    r.search_summary, r.search_keywords
"""

_BATCH_COLUMNS = _MCP_COLUMNS + """,
    r.meeting_notes, r.meeting_notes_generated_at
"""


# Map sort enum -> SQL ORDER BY fragment. NULLs are pushed last consistently.
_SORT_SQL: dict[McpSortOrder, str] = {
    McpSortOrder.recorded_at_desc:
        "COALESCE(r.recorded_at, r.created_at) DESC",
    McpSortOrder.recorded_at_asc:
        "COALESCE(r.recorded_at, r.created_at) ASC",
    McpSortOrder.duration_desc:
        "r.duration_seconds DESC NULLS LAST",
    McpSortOrder.duration_asc:
        "r.duration_seconds ASC NULLS LAST",
    McpSortOrder.token_count_desc:
        "r.token_count DESC NULLS LAST",
    McpSortOrder.token_count_asc:
        "r.token_count ASC NULLS LAST",
}

# Python sort keys for cascade-flat-sort (when sort != recorded_at_desc, the
# default). Each key returns a tuple where None comes last regardless of
# direction so that None-trailing matches the SQL.
_SORT_PY: dict[McpSortOrder, tuple[str, bool]] = {
    # field name in row dict, reverse?
    McpSortOrder.recorded_at_desc: ("_sort_recorded_at", True),
    McpSortOrder.recorded_at_asc: ("_sort_recorded_at", False),
    McpSortOrder.duration_desc: ("duration_seconds", True),
    McpSortOrder.duration_asc: ("duration_seconds", False),
    McpSortOrder.token_count_desc: ("token_count", True),
    McpSortOrder.token_count_asc: ("token_count", False),
}

# Cap per-tier fetch in cascade-flat mode to avoid unbounded memory growth
# at deep offsets. Three tiers × 2000 = 6000 rows max materialized in Python.
# Practical agent pagination rarely reaches this.
_CASCADE_FLAT_TARGET_CAP = 2000


def _sanitize_fts_query(query: str) -> str | None:
    """Sanitize a user query for FTS5 MATCH.

    Strips special characters except alphanumeric, spaces, and hyphens.
    Wraps each term in double quotes for literal matching.
    Returns None if the sanitized query is empty.
    """
    cleaned = re.sub(r"[^\w\s\-]", "", query)
    terms = cleaned.split()
    if not terms:
        return None
    return " ".join(f'"{term}"' for term in terms)


def _extract_speakers_full(
    speaker_mapping_raw: str | None,
) -> tuple[list[dict], list[str], int, int]:
    """Parse speaker_mapping JSON into structured speakers + legacy names.

    Returns (speakers, speaker_names, speaker_count, unresolved_speaker_count).

    Production speaker_mapping uses camelCase keys (`displayName`,
    `participantId`). Some legacy fixtures use snake_case; we tolerate both.
    Malformed JSON or non-dict structures are treated as zero speakers and
    logged at WARNING level rather than raising.
    """
    if not speaker_mapping_raw:
        return [], [], 0, 0

    try:
        mapping = json.loads(speaker_mapping_raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Malformed speaker_mapping JSON (truncated): %r",
            (speaker_mapping_raw or "")[:80],
        )
        return [], [], 0, 0

    if not isinstance(mapping, dict):
        logger.warning(
            "speaker_mapping is not a dict: %s", type(mapping).__name__,
        )
        return [], [], 0, 0

    speakers: list[dict] = []
    names: list[str] = []
    unresolved = 0

    for label, entry in mapping.items():
        if not isinstance(entry, dict):
            continue
        # Tolerate both camelCase (production) and snake_case (some fixtures)
        display_name = entry.get("displayName") or entry.get("display_name")
        participant_id = entry.get("participantId") or entry.get("participant_id")

        speakers.append({
            "label": label,
            "display_name": display_name,
            "participant_id": participant_id,
        })
        if display_name:
            names.append(display_name)
        if not participant_id:
            unresolved += 1

    return speakers, names, len(speakers), unresolved


def _project_recording(
    row: dict,
    *,
    field_set: tuple[str, ...] | frozenset[str],
    tag_ids: list[str] | None = None,
    match_tier: str | None = None,
) -> dict:
    """Project a DB row to the MCP response shape using the given field set.

    `field_set` is an iterable of valid field names from
    ALLOWED_RECORDING_FIELDS. `id` is always included.
    """
    fs = frozenset(field_set)
    out: dict = {"id": row["id"]}

    # Cheap pass-through fields
    for field in (
        "title", "description", "duration_seconds", "recorded_at",
        "source", "status", "token_count", "created_at", "updated_at",
        "search_summary",
    ):
        if field in fs:
            out[field] = row.get(field)

    if "search_keywords" in fs:
        kw_raw = row.get("search_keywords")
        if kw_raw:
            try:
                out["search_keywords"] = json.loads(kw_raw)
            except (json.JSONDecodeError, TypeError):
                out["search_keywords"] = None
        else:
            out["search_keywords"] = None

    if "meeting_notes" in fs:
        out["meeting_notes"] = row.get("meeting_notes")
    if "meeting_notes_generated_at" in fs:
        out["meeting_notes_generated_at"] = row.get("meeting_notes_generated_at")

    # Speakers — parsed once, distributed to whichever fields were requested
    needs_speakers = any(
        f in fs for f in (
            "speakers", "speaker_names", "speaker_count",
            "unresolved_speaker_count",
        )
    )
    if needs_speakers:
        speakers, names, count, unresolved = _extract_speakers_full(
            row.get("speaker_mapping"),
        )
        if "speakers" in fs:
            out["speakers"] = speakers
        if "speaker_names" in fs:
            out["speaker_names"] = names
        if "speaker_count" in fs:
            out["speaker_count"] = count
        if "unresolved_speaker_count" in fs:
            out["unresolved_speaker_count"] = unresolved

    if "tag_ids" in fs:
        out["tag_ids"] = tag_ids or []

    if "match_tier" in fs:
        # Always include the key when requested, even if value is None,
        # so the LLM can rely on shape consistency.
        out["match_tier"] = match_tier

    return out


async def _get_tag_ids_bulk(recording_ids: list[str]) -> dict[str, list[str]]:
    """Fetch tag IDs for multiple recordings in one query."""
    if not recording_ids:
        return {}
    db = await get_db()
    placeholders = ",".join("?" for _ in recording_ids)
    rows = await db.execute_fetchall(
        f"SELECT recording_id, tag_id FROM recording_tags "
        f"WHERE recording_id IN ({placeholders})",
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
    tag_ids: list[str] | None = None,
    tag_match: McpTagMatch = McpTagMatch.any,
) -> tuple[str, list]:
    """Build WHERE clause fragments and params for common filters.

    Returns (where_clause, params) where where_clause starts with 'WHERE'.
    Tags are filtered through the recording_tags join table; tenant isolation
    is achieved indirectly because the recording_id ultimately joins back to
    `recordings` which is already user_id-filtered.
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

    if tag_ids:
        placeholders = ",".join("?" for _ in tag_ids)
        if tag_match == McpTagMatch.all:
            clauses.append(
                f"""r.id IN (
                    SELECT recording_id FROM recording_tags
                    WHERE tag_id IN ({placeholders})
                    GROUP BY recording_id
                    HAVING COUNT(DISTINCT tag_id) = ?
                )"""
            )
            params.extend(tag_ids)
            params.append(len(set(tag_ids)))
        else:  # any (default)
            clauses.append(
                f"""r.id IN (
                    SELECT recording_id FROM recording_tags
                    WHERE tag_id IN ({placeholders})
                )"""
            )
            params.extend(tag_ids)

    return "WHERE " + " AND ".join(clauses), params


async def _fts_search(
    user_id: str,
    fts_query: str,
    *,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    sort_sql: str,
    exclude_ids: set[str] | None = None,
    title_filter: str | None = None,
    tag_ids: list[str] | None = None,
    tag_match: McpTagMatch = McpTagMatch.any,
) -> list[dict]:
    """Run an FTS5 MATCH query with filters. Returns list of row dicts."""
    db = await get_db()
    where_clause, params = _build_base_where(
        user_id, participant_id, date_from, date_to,
        title_filter=title_filter, tag_ids=tag_ids, tag_match=tag_match,
    )

    fts_condition = (
        "r.rowid IN (SELECT rowid FROM recordings_fts "
        "WHERE recordings_fts MATCH ?)"
    )
    where_clause += f" AND {fts_condition}"
    params.append(fts_query)

    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        where_clause += f" AND r.id NOT IN ({placeholders})"
        params.extend(exclude_ids)

    sql = f"""
        SELECT {_MCP_COLUMNS}
        FROM recordings r
        {where_clause}
        ORDER BY {sort_sql}
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


def _validate_fields(fields: list[str] | None) -> list[str] | None:
    """Validate a `fields` whitelist. Returns the (deduplicated) list, or
    None if the input was None.

    Raises ValueError with a useful message on unknown field names.
    """
    if fields is None:
        return None
    seen: list[str] = []
    seen_set: set[str] = set()
    bad: list[str] = []
    for f in fields:
        if f in seen_set:
            continue
        if f not in ALLOWED_RECORDING_FIELDS:
            bad.append(f)
            continue
        seen.append(f)
        seen_set.add(f)
    if bad:
        raise ValueError(
            f"Unknown fields: {bad!r}. Valid: {sorted(ALLOWED_RECORDING_FIELDS)!r}"
        )
    return seen


def _resolve_field_set(
    fields: list[str] | None,
    view: McpView | None,
    *,
    batch: bool,
) -> tuple[str, ...]:
    """Resolve `fields` (whitelist) + `view` (preset) into the final field set.

    `fields` wins over `view`. If both are None, fall back to the default view.
    Empty list explicitly means "minimal" (id only).
    """
    if fields is not None:
        # Empty list → just `id`. The projection function always emits `id`.
        return tuple(fields)
    return view_field_set(view, batch=batch)


async def search_recordings(
    user_id: str,
    *,
    query: str | None = None,
    mode: str = "cascade",
    participant_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
    title_filter: str | None = None,
    tag_ids: list[str] | None = None,
    tag_match: McpTagMatch = McpTagMatch.any,
    sort: McpSortOrder = McpSortOrder.recorded_at_desc,
    view: McpView | None = None,
    fields: list[str] | None = None,
    compute_total: bool = False,
) -> tuple[list[dict], bool, int | None]:
    """Search or list recordings.

    Returns (results, has_more, total).

    has_more is computed via a limit+1 fetch and is always populated.
    total is None unless compute_total=True AND mode != "cascade".
    """
    limit = max(1, min(limit, 100))
    field_set = _resolve_field_set(fields, view, batch=False)

    # Cascade with default sort preserves tier-major ordering. With explicit
    # non-default sort we flatten and apply globally (Opus review's
    # recommendation: explicit sort overrides implicit tier order).
    flat_cascade = (mode == "cascade") and (sort != McpSortOrder.recorded_at_desc)

    sort_sql = _SORT_SQL[sort]

    if not query or _sanitize_fts_query(query) is None:
        rows, has_more = await _list_recordings(
            user_id, participant_id, date_from, date_to,
            limit, offset, sort_sql=sort_sql,
            title_filter=title_filter,
            tag_ids=tag_ids, tag_match=tag_match,
        )
        total = None
        if compute_total:
            total = await _count_recordings(
                user_id, participant_id, date_from, date_to,
                title_filter=title_filter,
                tag_ids=tag_ids, tag_match=tag_match,
            )
        return _project_rows(rows, field_set), has_more, total

    sanitized = _sanitize_fts_query(query)
    assert sanitized is not None  # narrowed above

    if mode == "cascade":
        if flat_cascade:
            rows_with_tier, has_more = await _cascade_search_flat(
                user_id, sanitized, participant_id, date_from, date_to,
                limit, offset, sort=sort, sort_sql=sort_sql,
                title_filter=title_filter,
                tag_ids=tag_ids, tag_match=tag_match,
            )
        else:
            rows_with_tier, has_more = await _cascade_search_tiered(
                user_id, sanitized, participant_id, date_from, date_to,
                limit, offset, sort_sql=sort_sql,
                title_filter=title_filter,
                tag_ids=tag_ids, tag_match=tag_match,
            )
        return (
            _project_rows_with_tier(rows_with_tier, field_set),
            has_more,
            None,  # cascade total is deferred
        )

    # Single-tier modes
    if mode == "title":
        fts_query = f"title:{sanitized}"
        tier_label = "title"
    elif mode == "summary":
        fts_query = f"{{title description search_summary}}:{sanitized}"
        tier_label = "summary"
    else:  # full
        fts_query = sanitized
        tier_label = "transcript"

    # limit+1 fetch for has_more
    rows = await _fts_search(
        user_id, fts_query,
        participant_id=participant_id, date_from=date_from, date_to=date_to,
        limit=limit + 1, offset=offset, sort_sql=sort_sql,
        title_filter=title_filter,
        tag_ids=tag_ids, tag_match=tag_match,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]

    total = None
    if compute_total:
        total = await _count_recordings(
            user_id, participant_id, date_from, date_to,
            title_filter=title_filter,
            tag_ids=tag_ids, tag_match=tag_match,
            fts_query=fts_query,
        )

    rows_with_tier = [(r, tier_label) for r in rows]
    return (
        _project_rows_with_tier(rows_with_tier, field_set),
        has_more,
        total,
    )


def _project_rows(rows: list[dict], field_set: tuple[str, ...]) -> list[dict]:
    """Async-free row projection for non-search results (no match_tier)."""
    # NOTE: tag enrichment must be done by the caller before passing to
    # this function — we read row["_tag_ids"] if it was attached.
    return [
        _project_recording(r, field_set=field_set, tag_ids=r.get("_tag_ids"))
        for r in rows
    ]


def _project_rows_with_tier(
    rows: list[tuple[dict, str]],
    field_set: tuple[str, ...],
) -> list[dict]:
    """Project rows that carry a (row, match_tier) pair."""
    return [
        _project_recording(
            r, field_set=field_set,
            tag_ids=r.get("_tag_ids"), match_tier=tier,
        )
        for r, tier in rows
    ]


async def _enrich_with_tags(rows: list[dict]) -> None:
    """Attach `_tag_ids` to each row in place by bulk-fetching tags."""
    rec_ids = [r["id"] for r in rows]
    tag_map = await _get_tag_ids_bulk(rec_ids)
    for r in rows:
        r["_tag_ids"] = tag_map.get(r["id"], [])


async def _cascade_search_tiered(
    user_id: str,
    sanitized: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    *,
    sort_sql: str,
    title_filter: str | None,
    tag_ids: list[str] | None,
    tag_match: McpTagMatch,
) -> tuple[list[tuple[dict, str]], bool]:
    """Tier-major cascade. Used when sort == default (recorded_at_desc).

    Fetches up to (offset + limit + 1) rows across tiers — the +1 lets us
    determine has_more without an extra COUNT.
    """
    target = offset + limit + 1
    all_results: list[tuple[dict, str]] = []
    seen_ids: set[str] = set()

    tiers = [
        (f"title:{sanitized}", "title"),
        (f"{{title description search_summary}}:{sanitized}", "summary"),
        (sanitized, "transcript"),
    ]

    for fts_query, label in tiers:
        if len(all_results) >= target:
            break
        remaining = target - len(all_results)
        rows = await _fts_search(
            user_id, fts_query,
            participant_id=participant_id, date_from=date_from, date_to=date_to,
            limit=remaining, offset=0, sort_sql=sort_sql,
            exclude_ids=seen_ids, title_filter=title_filter,
            tag_ids=tag_ids, tag_match=tag_match,
        )
        for r in rows:
            if r["id"] in seen_ids:
                continue
            seen_ids.add(r["id"])
            all_results.append((r, label))
            if len(all_results) >= target:
                break

    page = all_results[offset:offset + limit + 1]
    has_more = len(page) > limit
    page = page[:limit]

    rows_only = [r for r, _ in page]
    await _enrich_with_tags(rows_only)
    return page, has_more


async def _cascade_search_flat(
    user_id: str,
    sanitized: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    *,
    sort: McpSortOrder,
    sort_sql: str,
    title_filter: str | None,
    tag_ids: list[str] | None,
    tag_match: McpTagMatch,
) -> tuple[list[tuple[dict, str]], bool]:
    """Flat cascade. Used when sort != default — flatten tiers and sort
    globally across the deduplicated set.

    Strategy: fetch enough rows from each tier to cover offset + limit + 1,
    deduplicate, sort globally, slice.

    Bounded by `min(offset + limit + 1, _CASCADE_FLAT_TARGET_CAP)` per tier
    to prevent unbounded memory growth at deep offsets. At very deep
    pagination, the dedup window may underrepresent later tiers — this is
    an acceptable tradeoff vs. the alternative (UNION-CTE query, deferred).

    Caveat: `match_tier` reflects the tier whose query window the row was
    *first observed in*, not provably the strongest tier. A title-matching
    recording ranked below the per-tier window in tier 1 can be picked up
    by tier 2 and labeled "summary". For non-default sorts this is rare and
    bounded; treat `match_tier` here as a hint, not a guarantee.
    """
    target = min(offset + limit + 1, _CASCADE_FLAT_TARGET_CAP)
    seen: dict[str, tuple[dict, str]] = {}

    tiers = [
        (f"title:{sanitized}", "title"),
        (f"{{title description search_summary}}:{sanitized}", "summary"),
        (sanitized, "transcript"),
    ]

    for fts_query, label in tiers:
        rows = await _fts_search(
            user_id, fts_query,
            participant_id=participant_id, date_from=date_from, date_to=date_to,
            limit=target, offset=0, sort_sql=sort_sql,
            exclude_ids=set(seen.keys()), title_filter=title_filter,
            tag_ids=tag_ids, tag_match=tag_match,
        )
        for r in rows:
            if r["id"] not in seen:
                seen[r["id"]] = (r, label)

    py_field, py_reverse = _SORT_PY[sort]

    def _val(item: tuple[dict, str]):
        row, _tier = item
        if py_field == "_sort_recorded_at":
            return row.get("recorded_at") or row.get("created_at")
        return row.get(py_field)

    # Partition then sort: keeps NULLs trailing in BOTH directions.
    # (`sorted(..., reverse=True)` flips Python's tuple-trailing trick, so
    # we have to handle nulls explicitly.)
    items = list(seen.values())
    non_null = [it for it in items if _val(it) is not None]
    nulls = [it for it in items if _val(it) is None]
    non_null.sort(key=_val, reverse=py_reverse)
    sorted_items = non_null + nulls

    page = sorted_items[offset:offset + limit + 1]
    has_more = len(page) > limit
    page = page[:limit]

    rows_only = [r for r, _ in page]
    await _enrich_with_tags(rows_only)
    return page, has_more


async def _list_recordings(
    user_id: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    *,
    sort_sql: str,
    title_filter: str | None = None,
    tag_ids: list[str] | None = None,
    tag_match: McpTagMatch = McpTagMatch.any,
) -> tuple[list[dict], bool]:
    """List recordings with filters (no FTS search). Returns (rows, has_more)."""
    db = await get_db()
    where_clause, params = _build_base_where(
        user_id, participant_id, date_from, date_to,
        title_filter=title_filter, tag_ids=tag_ids, tag_match=tag_match,
    )

    sql = f"""
        SELECT {_MCP_COLUMNS}
        FROM recordings r
        {where_clause}
        ORDER BY {sort_sql}
        LIMIT ? OFFSET ?
    """
    params.extend([limit + 1, offset])  # +1 for has_more

    rows = await db.execute_fetchall(sql, params)
    row_dicts = [dict(r) for r in rows]
    has_more = len(row_dicts) > limit
    row_dicts = row_dicts[:limit]
    await _enrich_with_tags(row_dicts)
    return row_dicts, has_more


async def _count_recordings(
    user_id: str,
    participant_id: str | None,
    date_from: str | None,
    date_to: str | None,
    *,
    title_filter: str | None = None,
    tag_ids: list[str] | None = None,
    tag_match: McpTagMatch = McpTagMatch.any,
    fts_query: str | None = None,
) -> int:
    """Count recordings matching the same filters (no LIMIT/OFFSET).

    Used to populate `total` in the paginated envelope. Not called for cascade
    mode (caller passes total=None for cascade).
    """
    db = await get_db()
    where_clause, params = _build_base_where(
        user_id, participant_id, date_from, date_to,
        title_filter=title_filter, tag_ids=tag_ids, tag_match=tag_match,
    )

    if fts_query is not None:
        where_clause += (
            " AND r.rowid IN (SELECT rowid FROM recordings_fts "
            "WHERE recordings_fts MATCH ?)"
        )
        params.append(fts_query)

    sql = f"SELECT COUNT(*) AS n FROM recordings r {where_clause}"
    try:
        rows = await db.execute_fetchall(sql, params)
        if rows:
            r = dict(rows[0])
            return int(r.get("n", 0))
    except Exception as e:
        logger.warning("Count query failed: %s", e)
    return 0


# ---------------------------------------------------------------------------
# Bulk lookup for get_recordings (POST /api/mcp/recordings/batch)
# ---------------------------------------------------------------------------


async def fetch_recordings_bulk(
    user_id: str,
    recording_ids: list[str],
    *,
    view: McpView | None = None,
    fields: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    """Fetch many recordings by ID in a single round-trip.

    Returns (results, missing_ids). missing_ids combines "doesn't exist" and
    "not yours" intentionally — no information leak about other users' IDs.

    Duplicates in `recording_ids` are deduplicated server-side; results
    preserve first-seen order from the input.

    The batch endpoint defaults to view=summary (lean by default) when
    neither `view` nor `fields` is provided. This intentionally differs
    from search_recordings where the default is view=full for backwards
    compatibility.
    """
    if not recording_ids:
        return [], []

    # Batch default: when nothing is specified, use summary (avoid payload
    # bombs from heavy meeting_notes when callers sweep many IDs).
    if fields is None and view is None:
        view = McpView.summary

    field_set = _resolve_field_set(fields, view, batch=True)

    # Dedupe input while preserving first-seen order
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for rid in recording_ids:
        if rid not in seen:
            seen.add(rid)
            ordered_ids.append(rid)

    db = await get_db()
    placeholders = ",".join("?" for _ in ordered_ids)

    sql = f"""
        SELECT {_BATCH_COLUMNS}
        FROM recordings r
        WHERE r.id IN ({placeholders})
          AND r.user_id = ?
          AND r.status = 'ready'
    """
    params = [*ordered_ids, user_id]
    rows = await db.execute_fetchall(sql, params)
    row_map = {dict(r)["id"]: dict(r) for r in rows}

    found_ids = [rid for rid in ordered_ids if rid in row_map]
    missing_ids = [rid for rid in ordered_ids if rid not in row_map]

    if not found_ids:
        return [], missing_ids

    # Tag enrichment if needed
    needs_tags = "tag_ids" in field_set
    if needs_tags:
        tag_map = await _get_tag_ids_bulk(found_ids)
    else:
        tag_map = {}

    results = [
        _project_recording(
            row_map[rid],
            field_set=field_set,
            tag_ids=tag_map.get(rid) if needs_tags else None,
        )
        for rid in found_ids
    ]

    return results, missing_ids
