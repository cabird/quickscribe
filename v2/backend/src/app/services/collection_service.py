"""Collection service — CRUD, item management, search-to-add, and search history."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.database import get_db

logger = logging.getLogger(__name__)


def _extract_speaker_names(speaker_mapping_json: str | None) -> list[str]:
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


# ---------------------------------------------------------------------------
# Collections CRUD
# ---------------------------------------------------------------------------


async def list_collections(user_id: str) -> list[dict]:
    """Return all collections for a user with item counts."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT c.id, c.user_id, c.name, c.description, c.created_at, c.updated_at,
                  COUNT(ci.recording_id) AS item_count
           FROM collections c
           LEFT JOIN collection_items ci ON ci.collection_id = c.id
           WHERE c.user_id = ?
           GROUP BY c.id
           ORDER BY c.updated_at DESC""",
        (user_id,),
    )
    return [dict(r) for r in rows]


async def create_collection(
    user_id: str, name: str, description: str | None = None
) -> dict:
    """Create a new collection and return it."""
    db = await get_db()
    collection_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """INSERT INTO collections (id, user_id, name, description, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (collection_id, user_id, name, description, now, now),
    )
    await db.commit()
    return {
        "id": collection_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "item_count": 0,
        "created_at": now,
        "updated_at": now,
    }


async def get_collection(user_id: str, collection_id: str) -> dict | None:
    """Return a collection with its items (each with recording summary info)."""
    db = await get_db()

    # Fetch collection
    rows = await db.execute_fetchall(
        "SELECT * FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        return None
    col = dict(rows[0])

    # Fetch items with recording metadata
    item_rows = await db.execute_fetchall(
        """SELECT ci.recording_id, ci.added_at,
                  r.title, r.recorded_at, r.speaker_mapping
           FROM collection_items ci
           JOIN recordings r ON r.id = ci.recording_id
           WHERE ci.collection_id = ?
           ORDER BY r.recorded_at DESC""",
        (collection_id,),
    )
    items = []
    for ir in item_rows:
        ir = dict(ir)
        items.append({
            "recording_id": ir["recording_id"],
            "title": ir.get("title"),
            "date": ir.get("recorded_at"),
            "speakers": _extract_speaker_names(ir.get("speaker_mapping")),
            "added_at": ir.get("added_at"),
        })

    col["items"] = items
    col["item_count"] = len(items)
    return col


async def update_collection(
    user_id: str, collection_id: str, name: str | None = None, description: str | None = None
) -> dict | None:
    """Update a collection's name/description. Returns updated collection or None if not found."""
    db = await get_db()

    # Verify ownership
    rows = await db.execute_fetchall(
        "SELECT * FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        return None
    col = dict(rows[0])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if name is not None:
        col["name"] = name
    if description is not None:
        col["description"] = description
    col["updated_at"] = now

    await db.execute(
        "UPDATE collections SET name = ?, description = ?, updated_at = ? WHERE id = ?",
        (col["name"], col["description"], now, collection_id),
    )
    await db.commit()

    # Get item count
    count_rows = await db.execute_fetchall(
        "SELECT COUNT(*) AS cnt FROM collection_items WHERE collection_id = ?",
        (collection_id,),
    )
    col["item_count"] = dict(count_rows[0])["cnt"] if count_rows else 0
    return col


async def delete_collection(user_id: str, collection_id: str) -> bool:
    """Delete a collection. Returns True if deleted, False if not found."""
    db = await get_db()

    # Verify ownership
    rows = await db.execute_fetchall(
        "SELECT id FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        return False

    await db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Collection items
# ---------------------------------------------------------------------------


async def add_items(
    user_id: str, collection_id: str, recording_ids: list[str]
) -> dict:
    """Bulk add recordings to a collection. Skips duplicates. Returns counts."""
    db = await get_db()

    # Verify ownership
    rows = await db.execute_fetchall(
        "SELECT id FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        return {"error": "not_found"}

    added = 0
    skipped = 0
    for rec_id in recording_ids:
        # Verify recording belongs to user
        rec_rows = await db.execute_fetchall(
            "SELECT id FROM recordings WHERE id = ? AND user_id = ?",
            (rec_id, user_id),
        )
        if not rec_rows:
            skipped += 1
            continue

        try:
            await db.execute(
                "INSERT INTO collection_items (collection_id, recording_id) VALUES (?, ?)",
                (collection_id, rec_id),
            )
            added += 1
        except sqlite3.IntegrityError:
            # Duplicate — skip
            skipped += 1

    # Touch updated_at
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        "UPDATE collections SET updated_at = ? WHERE id = ?",
        (now, collection_id),
    )
    await db.commit()
    return {"added": added, "skipped": skipped}


async def remove_item(
    user_id: str, collection_id: str, recording_id: str
) -> bool:
    """Remove a recording from a collection. Returns True if removed."""
    db = await get_db()

    # Verify ownership
    rows = await db.execute_fetchall(
        "SELECT id FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        return False

    cursor = await db.execute(
        "DELETE FROM collection_items WHERE collection_id = ? AND recording_id = ?",
        (collection_id, recording_id),
    )
    removed = cursor.rowcount > 0

    if removed:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "UPDATE collections SET updated_at = ? WHERE id = ?",
            (now, collection_id),
        )

    await db.commit()
    return removed


# ---------------------------------------------------------------------------
# Search-to-add (FTS + filters)
# ---------------------------------------------------------------------------


async def search_to_add(
    user_id: str,
    collection_id: str,
    query: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    speaker: str | None = None,
) -> list[dict]:
    """Search user's recordings via FTS + filters. Mark which are already in collection."""
    db = await get_db()

    # Verify ownership — raise 404 if collection doesn't exist
    rows = await db.execute_fetchall(
        "SELECT id FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Build query
    params: list = [user_id]
    where_clauses = ["r.user_id = ?", "r.status = 'ready'"]

    if query:
        # FTS match — join with FTS table
        fts_join = """JOIN recordings_fts fts ON fts.rowid = r.rowid"""
        where_clauses.append("recordings_fts MATCH ?")
        params.append(query)
        select_extra = ", bm25(recordings_fts) AS rank"
        order_by = "ORDER BY rank ASC"
    else:
        fts_join = ""
        select_extra = ""
        order_by = "ORDER BY r.recorded_at DESC"

    if date_from:
        where_clauses.append("r.recorded_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("r.recorded_at <= ?")
        params.append(date_to)
    if speaker:
        # Search in speaker_mapping JSON for display name
        where_clauses.append("r.speaker_mapping LIKE ?")
        params.append(f"%{speaker}%")

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT r.id, r.title, r.description, r.original_filename,
               r.recorded_at, r.speaker_mapping,
               r.search_summary, r.duration_seconds,
               r.source, r.status{select_extra}
        FROM recordings r
        {fts_join}
        WHERE {where_sql}
        {order_by}
        LIMIT 50
    """

    result_rows = await db.execute_fetchall(sql, params)

    # Get current collection items for in_collection flag
    ci_rows = await db.execute_fetchall(
        "SELECT recording_id FROM collection_items WHERE collection_id = ?",
        (collection_id,),
    )
    in_collection_ids = {dict(r)["recording_id"] for r in ci_rows}

    results = []
    for row in result_rows:
        row = dict(row)
        summary = row.get("search_summary") or ""
        results.append({
            "id": row["id"],
            "title": row.get("title"),
            "description": row.get("description"),
            "original_filename": row.get("original_filename", ""),
            "recorded_at": row.get("recorded_at"),
            "duration_seconds": row.get("duration_seconds"),
            "source": row.get("source", "upload"),
            "status": row.get("status", "ready"),
            "speaker_names": _extract_speaker_names(row.get("speaker_mapping")),
            "search_summary_snippet": summary[:150] if summary else None,
            "in_collection": row["id"] in in_collection_ids,
        })

    return results


# ---------------------------------------------------------------------------
# Create from candidates
# ---------------------------------------------------------------------------


async def create_from_candidates(
    user_id: str, name: str, recording_ids: list[str]
) -> dict:
    """Create a new collection pre-populated with given recordings."""
    col = await create_collection(user_id, name)
    if recording_ids:
        await add_items(user_id, col["id"], recording_ids)
    # Re-fetch to get accurate item_count
    full = await get_collection(user_id, col["id"])
    return full or col


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------


async def get_search_history(
    user_id: str, collection_id: str
) -> list[dict]:
    """Return past searches for a collection."""
    db = await get_db()

    # Verify ownership — raise 404 if collection doesn't exist
    rows = await db.execute_fetchall(
        "SELECT id FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Collection not found")

    search_rows = await db.execute_fetchall(
        """SELECT id, collection_id, question, answer, item_count,
                  item_set_hash, search_id, created_at
           FROM collection_searches
           WHERE collection_id = ?
           ORDER BY created_at DESC""",
        (collection_id,),
    )

    results = []
    for row in search_rows:
        row = dict(row)
        answer = row.get("answer") or ""
        results.append({
            "id": row["id"],
            "collection_id": row["collection_id"],
            "question": row["question"],
            "answer_preview": answer[:200] if answer else None,
            "item_count": row.get("item_count"),
            "item_set_hash": row.get("item_set_hash"),
            "search_id": row.get("search_id"),
            "created_at": row.get("created_at"),
        })

    return results


# ---------------------------------------------------------------------------
# Download transcripts
# ---------------------------------------------------------------------------


async def get_collection_transcripts(user_id: str, collection_id: str) -> list[dict]:
    """Return transcript data for every recording in a collection.

    Each dict contains: title, date, speakers, duration_seconds, transcript_text.
    """
    db = await get_db()

    # Verify ownership
    rows = await db.execute_fetchall(
        "SELECT id, name FROM collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    if not rows:
        return []

    item_rows = await db.execute_fetchall(
        """SELECT r.title, r.recorded_at, r.speaker_mapping,
                  r.duration_seconds, r.diarized_text, r.transcript_text
           FROM collection_items ci
           JOIN recordings r ON r.id = ci.recording_id
           WHERE ci.collection_id = ?
           ORDER BY r.recorded_at DESC""",
        (collection_id,),
    )

    results = []
    for row in item_rows:
        row = dict(row)
        results.append({
            "title": row.get("title") or "Untitled",
            "date": row.get("recorded_at") or "",
            "speakers": _extract_speaker_names(row.get("speaker_mapping")),
            "duration_seconds": row.get("duration_seconds"),
            "transcript_text": row.get("diarized_text") or row.get("transcript_text") or "",
        })
    return results


# ---------------------------------------------------------------------------
# Item set hash
# ---------------------------------------------------------------------------


async def compute_item_set_hash(collection_id: str) -> str:
    """Compute a sha256 hash of sorted recording IDs in a collection."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT recording_id FROM collection_items WHERE collection_id = ? ORDER BY recording_id",
        (collection_id,),
    )
    ids = [dict(r)["recording_id"] for r in rows]
    return hashlib.sha256(",".join(ids).encode()).hexdigest()
