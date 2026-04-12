"""Participant business logic — CRUD, search, merge, find-or-create."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.database import get_db
from app.models import Participant, ParticipantCreate, ParticipantUpdate

logger = logging.getLogger(__name__)


def _row_to_participant(row: dict) -> Participant:
    """Convert a DB row to a Participant model."""
    return Participant(**row)


async def list_participants(user_id: str) -> list[Participant]:
    """List all participants for a user, ordered by display_name."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM participants WHERE user_id = ? ORDER BY display_name",
        (user_id,),
    )
    return [_row_to_participant(dict(r)) for r in rows]


async def get_participant(user_id: str, participant_id: str) -> Participant:
    """Get a single participant with recent recordings.

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM participants WHERE id = ? AND user_id = ?",
        (participant_id, user_id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Participant not found")

    return _row_to_participant(dict(rows[0]))


async def create_participant(
    user_id: str, data: ParticipantCreate
) -> Participant:
    """Create a new participant.

    Returns:
        The created Participant.
    """
    db = await get_db()
    participant_id = str(uuid.uuid4())

    aliases_json = json.dumps(data.aliases) if data.aliases else None

    await db.execute(
        """INSERT INTO participants (
            id, user_id, display_name, first_name, last_name, aliases,
            email, role, organization, relationship, notes, is_user,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  datetime('now'), datetime('now'))""",
        (
            participant_id, user_id, data.display_name,
            data.first_name, data.last_name, aliases_json,
            data.email, data.role, data.organization,
            data.relationship, data.notes, int(data.is_user),
        ),
    )
    await db.commit()

    return await get_participant(user_id, participant_id)


async def update_participant(
    user_id: str, participant_id: str, data: ParticipantUpdate
) -> Participant:
    """Update a participant's fields.

    Only updates fields that are explicitly set (not None).

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    # Verify ownership
    await get_participant(user_id, participant_id)

    db = await get_db()
    set_clauses: list[str] = []
    params: list = []

    if data.display_name is not None:
        set_clauses.append("display_name = ?")
        params.append(data.display_name)
    if data.first_name is not None:
        set_clauses.append("first_name = ?")
        params.append(data.first_name)
    if data.last_name is not None:
        set_clauses.append("last_name = ?")
        params.append(data.last_name)
    if data.aliases is not None:
        set_clauses.append("aliases = ?")
        params.append(json.dumps(data.aliases))
    if data.email is not None:
        set_clauses.append("email = ?")
        params.append(data.email)
    if data.role is not None:
        set_clauses.append("role = ?")
        params.append(data.role)
    if data.organization is not None:
        set_clauses.append("organization = ?")
        params.append(data.organization)
    if data.relationship is not None:
        set_clauses.append("relationship = ?")
        params.append(data.relationship)
    if data.notes is not None:
        set_clauses.append("notes = ?")
        params.append(data.notes)
    if data.is_user is not None:
        set_clauses.append("is_user = ?")
        params.append(int(data.is_user))

    if not set_clauses:
        return await get_participant(user_id, participant_id)

    set_clauses.append("updated_at = datetime('now')")
    sql = f"UPDATE participants SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?"
    params.extend([participant_id, user_id])

    await db.execute(sql, params)
    await db.commit()

    return await get_participant(user_id, participant_id)


async def delete_participant(user_id: str, participant_id: str) -> None:
    """Delete a participant.

    Also clears speaker_mapping references in recordings that point to this
    participant (sets participant_id to None, clears display_name).

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    await get_participant(user_id, participant_id)

    db = await get_db()

    # Clear references in speaker_mapping JSON across recordings
    rows = await db.execute_fetchall(
        "SELECT id, speaker_mapping FROM recordings WHERE user_id = ? AND speaker_mapping IS NOT NULL",
        (user_id,),
    )
    for row in rows:
        r = dict(row)
        try:
            mapping = json.loads(r["speaker_mapping"])
            changed = False
            for label, entry in mapping.items():
                if entry.get("participantId") == participant_id:
                    entry["participantId"] = None
                    entry["displayName"] = None
                    changed = True
            if changed:
                await db.execute(
                    "UPDATE recordings SET speaker_mapping = ?, speaker_mapping_updated_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(mapping), r["id"]),
                )
        except (json.JSONDecodeError, AttributeError):
            continue

    await db.execute(
        "DELETE FROM participants WHERE id = ? AND user_id = ?",
        (participant_id, user_id),
    )
    await db.commit()

    logger.info("Deleted participant %s for user %s", participant_id, user_id)


async def search_participants(
    user_id: str, name: str, fuzzy: bool = False
) -> list[Participant]:
    """Search participants by name.

    Args:
        user_id: Owner's user ID.
        name: Search term.
        fuzzy: If True, use LIKE matching; otherwise prefix match.

    Returns:
        Matching participants ordered by display_name.
    """
    db = await get_db()

    if fuzzy:
        pattern = f"%{name}%"
    else:
        pattern = f"{name}%"

    rows = await db.execute_fetchall(
        """SELECT * FROM participants
           WHERE user_id = ? AND (
               display_name LIKE ? OR
               first_name LIKE ? OR
               last_name LIKE ? OR
               aliases LIKE ?
           )
           ORDER BY display_name
           LIMIT 25""",
        (user_id, pattern, pattern, pattern, pattern),
    )

    return [_row_to_participant(dict(r)) for r in rows]


async def merge_participants(
    user_id: str, primary_id: str, secondary_id: str
) -> Participant:
    """Merge secondary participant into primary.

    - Transfers all speaker_mapping references from secondary to primary.
    - Merges aliases from secondary into primary.
    - Copies missing fields (email, role, etc.) from secondary if primary lacks them.
    - Deletes the secondary participant.

    Raises:
        HTTPException 404 if either participant not found.
        HTTPException 400 if attempting to merge a participant with itself.
    """
    if primary_id == secondary_id:
        raise HTTPException(status_code=400, detail="Cannot merge a participant with itself")

    primary = await get_participant(user_id, primary_id)
    secondary = await get_participant(user_id, secondary_id)
    db = await get_db()

    # Merge aliases
    primary_aliases: list[str] = json.loads(primary.aliases) if primary.aliases else []
    secondary_aliases: list[str] = json.loads(secondary.aliases) if secondary.aliases else []

    # Add secondary display_name as an alias if different
    if secondary.display_name != primary.display_name:
        secondary_aliases.append(secondary.display_name)

    merged_aliases = list(set(primary_aliases + secondary_aliases))

    # Fill in missing fields from secondary
    updates: dict[str, str] = {"aliases": json.dumps(merged_aliases)}
    if not primary.email and secondary.email:
        updates["email"] = secondary.email
    if not primary.role and secondary.role:
        updates["role"] = secondary.role
    if not primary.organization and secondary.organization:
        updates["organization"] = secondary.organization
    if not primary.relationship and secondary.relationship:
        updates["relationship"] = secondary.relationship
    if not primary.notes and secondary.notes:
        updates["notes"] = secondary.notes

    set_clauses = [f"{k} = ?" for k in updates]
    set_clauses.append("updated_at = datetime('now')")
    params = list(updates.values()) + [primary_id, user_id]

    await db.execute(
        f"UPDATE participants SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        params,
    )

    # Transfer speaker_mapping references
    rows = await db.execute_fetchall(
        "SELECT id, speaker_mapping FROM recordings WHERE user_id = ? AND speaker_mapping IS NOT NULL",
        (user_id,),
    )
    for row in rows:
        r = dict(row)
        try:
            mapping = json.loads(r["speaker_mapping"])
            changed = False
            for label, entry in mapping.items():
                if entry.get("participantId") == secondary_id:
                    entry["participantId"] = primary_id
                    entry["displayName"] = primary.display_name
                    changed = True
            if changed:
                await db.execute(
                    "UPDATE recordings SET speaker_mapping = ?, speaker_mapping_updated_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(mapping), r["id"]),
                )
        except (json.JSONDecodeError, AttributeError):
            continue

    # Transfer speaker_profiles
    await db.execute(
        """UPDATE speaker_profiles SET participant_id = ?, display_name = ?, updated_at = datetime('now')
           WHERE user_id = ? AND participant_id = ?""",
        (primary_id, primary.display_name, user_id, secondary_id),
    )

    # Delete secondary
    await db.execute(
        "DELETE FROM participants WHERE id = ? AND user_id = ?",
        (secondary_id, user_id),
    )
    await db.commit()

    logger.info(
        "Merged participant %s into %s for user %s",
        secondary_id, primary_id, user_id,
    )
    return await get_participant(user_id, primary_id)


async def find_or_create(user_id: str, name: str) -> Participant:
    """Find an existing participant by exact display_name, or create a new one.

    Args:
        user_id: Owner's user ID.
        name: The display name to match or create.

    Returns:
        The matched or newly created Participant.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM participants WHERE user_id = ? AND display_name = ? COLLATE NOCASE",
        (user_id, name),
    )

    if rows:
        return _row_to_participant(dict(rows[0]))

    return await create_participant(
        user_id, ParticipantCreate(display_name=name)
    )
