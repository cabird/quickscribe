"""User profile and settings endpoints."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    AnalysisTemplate,
    AnalysisTemplateCreate,
    AnalysisTemplateUpdate,
    PlaudSettingsUpdate,
    User,
    UserProfile,
)

router = APIRouter(prefix="/api/me", tags=["settings"])

CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------


@router.get("", response_model=UserProfile)
async def get_profile(user: CurrentUser):
    """Get the current user's profile (excludes sensitive fields)."""
    return UserProfile(**user.model_dump())


@router.put("/settings", response_model=UserProfile)
async def update_settings(body: PlaudSettingsUpdate, user: CurrentUser):
    """Update Plaud settings."""
    db = await get_db()
    updates: list[str] = []
    params: list = []
    if body.plaud_enabled is not None:
        updates.append("plaud_enabled = ?")
        params.append(int(body.plaud_enabled))
    if body.plaud_token is not None:
        updates.append("plaud_token = ?")
        params.append(body.plaud_token)
    if not updates:
        return user
    params.append(user.id)
    await db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
    )
    await db.commit()
    row = await db.execute_fetchall("SELECT * FROM users WHERE id = ?", (user.id,))
    return UserProfile(**dict(row[0]))


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------


@router.post("/api-key")
async def generate_api_key(user: CurrentUser):
    """Generate a new API key for the current user (replaces any existing key)."""
    api_key = secrets.token_hex(16)
    db = await get_db()
    await db.execute("UPDATE users SET api_key = ? WHERE id = ?", (api_key, user.id))
    await db.commit()
    return {"api_key": api_key}


@router.delete("/api-key", status_code=204)
async def revoke_api_key(user: CurrentUser):
    """Remove the current user's API key."""
    db = await get_db()
    await db.execute("UPDATE users SET api_key = NULL WHERE id = ?", (user.id,))
    await db.commit()


# ---------------------------------------------------------------------------
# Analysis templates
# ---------------------------------------------------------------------------


@router.get("/analysis-templates", response_model=list[AnalysisTemplate])
async def list_analysis_templates(user: CurrentUser):
    """List the user's analysis templates."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM analysis_templates WHERE user_id = ? ORDER BY name",
        (user.id,),
    )
    return [AnalysisTemplate(**dict(r)) for r in rows]


@router.post("/analysis-templates", response_model=AnalysisTemplate, status_code=201)
async def create_analysis_template(body: AnalysisTemplateCreate, user: CurrentUser):
    """Create an analysis template."""
    import uuid

    template_id = str(uuid.uuid4())
    db = await get_db()
    await db.execute(
        """INSERT INTO analysis_templates (id, user_id, name, prompt)
           VALUES (?, ?, ?, ?)""",
        (template_id, user.id, body.name, body.prompt),
    )
    await db.commit()
    row = await db.execute_fetchall(
        "SELECT * FROM analysis_templates WHERE id = ?", (template_id,)
    )
    return AnalysisTemplate(**dict(row[0]))


@router.put("/analysis-templates/{template_id}", response_model=AnalysisTemplate)
async def update_analysis_template(
    template_id: str, body: AnalysisTemplateUpdate, user: CurrentUser
):
    """Update an analysis template."""
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM analysis_templates WHERE id = ? AND user_id = ?",
        (template_id, user.id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Analysis template not found")
    updates: list[str] = []
    params: list = []
    if body.name is not None:
        updates.append("name = ?")
        params.append(body.name)
    if body.prompt is not None:
        updates.append("prompt = ?")
        params.append(body.prompt)
    if not updates:
        return AnalysisTemplate(**dict(row[0]))
    updates.append("updated_at = datetime('now')")
    params.append(template_id)
    params.append(user.id)
    await db.execute(
        f"UPDATE analysis_templates SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
        params,
    )
    await db.commit()
    row = await db.execute_fetchall(
        "SELECT * FROM analysis_templates WHERE id = ?", (template_id,)
    )
    return AnalysisTemplate(**dict(row[0]))


# ---------------------------------------------------------------------------
# Speaker profiles
# ---------------------------------------------------------------------------


@router.post("/speaker-profiles/rebuild")
async def rebuild_speaker_profiles(user: CurrentUser):
    """Rebuild all speaker profiles from verified speaker_mapping data.

    Deletes existing profiles and reconstructs them from manually verified
    speaker_mapping embeddings across all recordings.
    """
    from app.services import profile_store

    count = await profile_store.rebuild_all_profiles(user.id)
    return {"profiles_rebuilt": count}


@router.delete("/analysis-templates/{template_id}", status_code=204)
async def delete_analysis_template(template_id: str, user: CurrentUser):
    """Delete an analysis template."""
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM analysis_templates WHERE id = ? AND user_id = ?",
        (template_id, user.id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Analysis template not found")
    await db.execute(
        "DELETE FROM analysis_templates WHERE id = ? AND user_id = ?",
        (template_id, user.id),
    )
    await db.commit()
