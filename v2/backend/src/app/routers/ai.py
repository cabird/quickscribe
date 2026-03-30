"""AI endpoints — chat and analysis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models import ChatRequest, ChatResponse, User
from app.services import ai_service, recording_service

router = APIRouter(prefix="/api/ai", tags=["ai"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: CurrentUser):
    """Chat with transcript context."""
    recording = await recording_service.get_recording(user.id, body.recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    transcript_context = recording.diarized_text or recording.transcript_text or ""
    return await ai_service.chat(
        messages=[{"role": m.role, "content": m.content} for m in body.messages],
        transcript_context=transcript_context,
    )
