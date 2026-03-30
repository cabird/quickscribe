"""Participant endpoints — CRUD, search, merge."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.models import (
    PaginatedResponse,
    Participant,
    ParticipantCreate,
    ParticipantUpdate,
    User,
)
from app.services import participant_service

router = APIRouter(prefix="/api/participants", tags=["participants"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=PaginatedResponse)
async def list_participants(
    user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(500, ge=1, le=500),
):
    """List all participants for the current user."""
    participants = await participant_service.list_participants(user_id=user.id)
    # Apply pagination in-memory (service returns full list)
    total = len(participants)
    start = (page - 1) * per_page
    page_items = participants[start : start + per_page]
    return PaginatedResponse(data=page_items, total=total, page=page, per_page=per_page)


@router.get("/search", response_model=PaginatedResponse)
async def search_participants(
    user: CurrentUser,
    name: str = Query(..., min_length=1),
    fuzzy: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """Search participants by name."""
    participants = await participant_service.search_participants(
        user_id=user.id,
        name=name,
        fuzzy=fuzzy,
    )
    # Apply pagination in-memory (service returns full list)
    total = len(participants)
    start = (page - 1) * per_page
    page_items = participants[start : start + per_page]
    return PaginatedResponse(data=page_items, total=total, page=page, per_page=per_page)


@router.get("/{participant_id}", response_model=Participant)
async def get_participant(participant_id: str, user: CurrentUser):
    """Get a participant with recent recordings."""
    participant = await participant_service.get_participant(user.id, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant


@router.post("", response_model=Participant, status_code=201)
async def create_participant(body: ParticipantCreate, user: CurrentUser):
    """Create a new participant."""
    participant = await participant_service.create_participant(user.id, body)
    return participant


@router.put("/{participant_id}", response_model=Participant)
async def update_participant(
    participant_id: str, body: ParticipantUpdate, user: CurrentUser
):
    """Update participant details."""
    existing = await participant_service.get_participant(user.id, participant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Participant not found")
    updated = await participant_service.update_participant(user.id, participant_id, body)
    return updated


@router.delete("/{participant_id}", status_code=204)
async def delete_participant(participant_id: str, user: CurrentUser):
    """Delete a participant."""
    existing = await participant_service.get_participant(user.id, participant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Participant not found")
    await participant_service.delete_participant(user.id, participant_id)


@router.post("/{participant_id}/merge/{other_id}", response_model=Participant)
async def merge_participants(participant_id: str, other_id: str, user: CurrentUser):
    """Merge other_id into participant_id. The other participant is deleted."""
    primary = await participant_service.get_participant(user.id, participant_id)
    if not primary:
        raise HTTPException(status_code=404, detail="Primary participant not found")
    other = await participant_service.get_participant(user.id, other_id)
    if not other:
        raise HTTPException(status_code=404, detail="Other participant not found")
    merged = await participant_service.merge_participants(user.id, participant_id, other_id)
    return merged
