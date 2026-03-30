"""Tag endpoints — CRUD."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models import Tag, TagCreate, TagUpdate, User
from app.services import tag_service

router = APIRouter(prefix="/api/tags", tags=["tags"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[Tag])
async def list_tags(user: CurrentUser):
    """List all tags for the current user."""
    return await tag_service.list_tags(user.id)


@router.post("", response_model=Tag, status_code=201)
async def create_tag(body: TagCreate, user: CurrentUser):
    """Create a new tag."""
    return await tag_service.create_tag(user.id, body)


@router.put("/{tag_id}", response_model=Tag)
async def update_tag(tag_id: str, body: TagUpdate, user: CurrentUser):
    """Update an existing tag."""
    existing = await tag_service.get_tag(user.id, tag_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Tag not found")
    return await tag_service.update_tag(user.id, tag_id, body)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(tag_id: str, user: CurrentUser):
    """Delete a tag (also removes from all recordings)."""
    existing = await tag_service.get_tag(user.id, tag_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Tag not found")
    await tag_service.delete_tag(user.id, tag_id)
