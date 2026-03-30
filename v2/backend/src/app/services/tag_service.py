"""Tag business logic — CRUD and recording-tag assignment."""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException

from app.database import get_db
from app.models import Tag, TagCreate, TagUpdate

logger = logging.getLogger(__name__)


def _row_to_tag(row: dict) -> Tag:
    return Tag(**row)


async def get_tag(user_id: str, tag_id: str) -> Tag | None:
    """Get a single tag by ID and user.

    Returns:
        The Tag if found and owned by user, or None.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM tags WHERE id = ? AND user_id = ?",
        (tag_id, user_id),
    )
    if not rows:
        return None
    return _row_to_tag(dict(rows[0]))


async def list_tags(user_id: str) -> list[Tag]:
    """List all tags for a user, ordered by name."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM tags WHERE user_id = ? ORDER BY name",
        (user_id,),
    )
    return [_row_to_tag(dict(r)) for r in rows]


async def create_tag(user_id: str, data: TagCreate) -> Tag:
    """Create a new tag.

    Raises:
        HTTPException 409 if a tag with the same name already exists for this user.
    """
    db = await get_db()
    tag_id = str(uuid.uuid4())

    try:
        await db.execute(
            """INSERT INTO tags (id, user_id, name, color, created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (tag_id, user_id, data.name, data.color),
        )
        await db.commit()
    except Exception:
        # UNIQUE(user_id, name) constraint violation
        raise HTTPException(
            status_code=409,
            detail=f"Tag '{data.name}' already exists",
        )

    rows = await db.execute_fetchall("SELECT * FROM tags WHERE id = ?", (tag_id,))
    return _row_to_tag(dict(rows[0]))


async def update_tag(user_id: str, tag_id: str, data: TagUpdate) -> Tag:
    """Update a tag's name and/or color.

    Raises:
        HTTPException 404 if not found or not owned by user.
        HTTPException 409 if the new name conflicts with an existing tag.
    """
    db = await get_db()

    # Verify ownership
    rows = await db.execute_fetchall(
        "SELECT * FROM tags WHERE id = ? AND user_id = ?",
        (tag_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Tag not found")

    set_clauses: list[str] = []
    params: list = []

    if data.name is not None:
        set_clauses.append("name = ?")
        params.append(data.name)
    if data.color is not None:
        set_clauses.append("color = ?")
        params.append(data.color)

    if not set_clauses:
        return _row_to_tag(dict(rows[0]))

    sql = f"UPDATE tags SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?"
    params.extend([tag_id, user_id])

    try:
        await db.execute(sql, params)
        await db.commit()
    except Exception:
        raise HTTPException(
            status_code=409,
            detail=f"Tag name '{data.name}' already exists",
        )

    rows = await db.execute_fetchall("SELECT * FROM tags WHERE id = ?", (tag_id,))
    return _row_to_tag(dict(rows[0]))


async def delete_tag(user_id: str, tag_id: str) -> None:
    """Delete a tag and all its recording associations.

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    db = await get_db()

    rows = await db.execute_fetchall(
        "SELECT id FROM tags WHERE id = ? AND user_id = ?",
        (tag_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Tag not found")

    # recording_tags will cascade-delete due to FK
    await db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    await db.commit()

    logger.info("Deleted tag %s for user %s", tag_id, user_id)


async def add_tag_to_recording(
    user_id: str, recording_id: str, tag_id: str
) -> None:
    """Associate a tag with a recording.

    Validates that both the tag and recording belong to the user.

    Raises:
        HTTPException 404 if tag or recording not found.
    """
    db = await get_db()

    # Verify tag ownership
    tag_rows = await db.execute_fetchall(
        "SELECT id FROM tags WHERE id = ? AND user_id = ?",
        (tag_id, user_id),
    )
    if not tag_rows:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Verify recording ownership
    rec_rows = await db.execute_fetchall(
        "SELECT id FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )
    if not rec_rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    await db.execute(
        "INSERT OR IGNORE INTO recording_tags (recording_id, tag_id) VALUES (?, ?)",
        (recording_id, tag_id),
    )
    await db.commit()


async def remove_tag_from_recording(
    user_id: str, recording_id: str, tag_id: str
) -> None:
    """Remove a tag from a recording.

    Validates ownership of both the tag and recording.

    Raises:
        HTTPException 404 if tag or recording not found.
    """
    db = await get_db()

    # Verify tag ownership
    tag_rows = await db.execute_fetchall(
        "SELECT id FROM tags WHERE id = ? AND user_id = ?",
        (tag_id, user_id),
    )
    if not tag_rows:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Verify recording ownership
    rec_rows = await db.execute_fetchall(
        "SELECT id FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )
    if not rec_rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    await db.execute(
        "DELETE FROM recording_tags WHERE recording_id = ? AND tag_id = ?",
        (recording_id, tag_id),
    )
    await db.commit()
