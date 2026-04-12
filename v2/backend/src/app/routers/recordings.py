"""Recording endpoints — CRUD, upload, audio, search, speakers, tags."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.auth import get_current_user, get_current_user_or_api_key
from app.models import (
    AnalysisRequest,
    PaginatedResponse,
    PasteTranscriptRequest,
    RecordingDetail,
    RecordingUpdate,
    SpeakerAssignment,
    User,
)
from app.services import ai_service, recording_service, tag_service

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOrApiKey = Annotated[User, Depends(get_current_user_or_api_key)]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# List / Search
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse)
async def list_recordings(
    user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: str | None = None,
    date_range: str | None = None,
    sort: str | None = None,
):
    """List the current user's recordings (paginated)."""
    result = await recording_service.list_recordings(
        user_id=user.id,
        page=page,
        per_page=per_page,
        search=search,
        date_from=date_range,  # date_range maps to date_from; date_to not exposed here
    )
    return result


@router.get("/search", response_model=PaginatedResponse)
async def search_recordings(
    user: CurrentUser,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """Full-text search across recordings."""
    recordings = await recording_service.search_recordings(
        user_id=user.id,
        query=q,
    )
    # Apply pagination in-memory (service returns full list)
    total = len(recordings)
    start = (page - 1) * per_page
    page_items = recordings[start : start + per_page]
    return PaginatedResponse(data=page_items, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# Speaker reviews (must be before /{recording_id} to avoid route conflict)
# ---------------------------------------------------------------------------


@router.get("/speaker-reviews")
async def get_speaker_reviews(user: CurrentUser):
    """Get recordings that have speakers needing review (suggest/unknown status).

    Returns recordings with their full speaker_mapping for the reviews UI.
    """
    reviews = await recording_service.get_recordings_for_review(user.id)
    return {"data": reviews}


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@router.get("/{recording_id}", response_model=RecordingDetail)
async def get_recording(recording_id: str, user: CurrentUser):
    """Get a single recording with full transcript data."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=201)
async def upload_recording(
    user: CurrentUserOrApiKey,
    file: UploadFile | None = File(None),
    audio_file: UploadFile | None = File(None),
    title: str | None = None,
):
    """Upload an audio file for transcription. Accepts 'file' or 'audio_file' field name."""
    upload = file or audio_file
    if not upload:
        raise HTTPException(status_code=400, detail="No file provided. Use form field 'file' or 'audio_file'.")

    auth_method = "api_key" if not hasattr(user, '_auth_method') else "bearer"
    logger.info(
        "Upload request: user=%s, auth=%s, filename=%s, content_type=%s, title=%s",
        user.id[:12], auth_method, upload.filename, upload.content_type, title,
    )

    try:
        recording = await recording_service.upload_recording(
            user_id=user.id,
            file=upload,
            title=title,
        )
        logger.info("Upload complete: recording=%s, status=%s", recording.id[:12], recording.status)
        return {
            "success": "File uploaded successfully!",
            "filename": upload.filename,
            "recording_id": recording.id,
            "status": recording.status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload failed for user=%s, filename=%s: %s", user.id[:12], upload.filename, e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.post("/paste", response_model=RecordingDetail, status_code=201)
async def paste_transcript(user: CurrentUser, body: PasteTranscriptRequest):
    """Create a recording from pasted transcript text (no audio)."""
    recording = await recording_service.paste_transcript(
        user_id=user.id,
        request=body,
    )
    return recording


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------


@router.put("/{recording_id}", response_model=RecordingDetail)
async def update_recording(
    recording_id: str, body: RecordingUpdate, user: CurrentUser
):
    """Update recording metadata (title, description, recorded_at)."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    updated = await recording_service.update_recording(user.id, recording_id, body)
    return updated


@router.delete("/{recording_id}", status_code=204)
async def delete_recording(recording_id: str, user: CurrentUser):
    """Delete a recording and block Plaud re-import if applicable."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    await recording_service.delete_recording(user.id, recording_id)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


@router.get("/{recording_id}/audio")
async def get_audio_url(recording_id: str, user: CurrentUser):
    """Get a time-limited SAS URL for audio streaming."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    url = await recording_service.get_audio_url(user.id, recording_id)
    if not url:
        raise HTTPException(status_code=404, detail="Audio file not available")
    return {"url": url}


# ---------------------------------------------------------------------------
# Reprocess
# ---------------------------------------------------------------------------


@router.post("/{recording_id}/reprocess", response_model=RecordingDetail)
async def reprocess_recording(recording_id: str, user: CurrentUser):
    """Retry processing on a failed recording."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    updated = await recording_service.reprocess_recording(user.id, recording_id)
    return updated


# ---------------------------------------------------------------------------
# Speakers
# ---------------------------------------------------------------------------


@router.put("/{recording_id}/speakers/{label}", response_model=RecordingDetail)
async def assign_speaker(
    recording_id: str, label: str, body: SpeakerAssignment, user: CurrentUser
):
    """Assign a participant to a speaker label in a recording."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    updated = await recording_service.assign_speaker(
        user_id=user.id,
        recording_id=recording_id,
        speaker_label=label,
        participant_id=body.participant_id,
        manually_verified=body.manually_verified,
        use_for_training=body.use_for_training,
    )
    return updated


@router.post("/{recording_id}/speakers/{label}/dismiss", response_model=RecordingDetail)
async def dismiss_speaker(
    recording_id: str, label: str, user: CurrentUser
):
    """Dismiss a speaker from reviews by setting identificationStatus to dismissed."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    updated = await recording_service.dismiss_speaker(
        user_id=user.id,
        recording_id=recording_id,
        speaker_label=label,
    )
    return updated


@router.post("/{recording_id}/identify-speakers", response_model=RecordingDetail)
async def identify_speakers(recording_id: str, user: CurrentUser):
    """Manually trigger speaker identification for a recording."""
    from app.config import get_settings
    from app.services import speaker_processor

    settings = get_settings()
    if not settings.speaker_id_enabled:
        raise HTTPException(status_code=400, detail="Speaker identification is disabled")

    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.source == "paste":
        raise HTTPException(status_code=400, detail="Cannot identify speakers for pasted transcripts")

    async with speaker_processor._speaker_id_lock:
        identified = await speaker_processor.process_recording(user.id, recording_id)
        if identified:
            await speaker_processor.rerate_speakers(user.id)

    return await recording_service.get_recording(user.id, recording_id)


@router.post("/{recording_id}/generate-meeting-notes")
async def generate_meeting_notes(recording_id: str, user: CurrentUser):
    """Manually trigger meeting notes generation for a recording."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if not recording.diarized_text and not recording.transcript_text:
        raise HTTPException(status_code=400, detail="Recording has no transcript")

    from app.services import meeting_notes_service

    notes = await meeting_notes_service.generate_meeting_notes(recording_id, user.id)
    if notes is None:
        raise HTTPException(status_code=500, detail="Meeting notes generation failed")

    # Re-fetch to get meeting_notes_tags
    updated = await recording_service.get_recording(user.id, recording_id)
    return {
        "meeting_notes": updated.meeting_notes,
        "meeting_notes_tags": updated.meeting_notes_tags,
    }


@router.post("/{recording_id}/reidentify", response_model=RecordingDetail)
async def reidentify_speakers(recording_id: str, user: CurrentUser):
    """Clear auto/suggest speaker data and re-run identification.

    Resets non-verified, non-dismissed speaker entries and triggers a fresh
    identification pass.
    """
    import json

    from app.config import get_settings
    from app.database import get_db
    from app.services import speaker_processor

    settings = get_settings()
    if not settings.speaker_id_enabled:
        raise HTTPException(status_code=400, detail="Speaker identification is disabled")

    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.source == "paste":
        raise HTTPException(status_code=400, detail="Cannot identify speakers for pasted transcripts")

    # Clear non-verified, non-dismissed speaker data
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT speaker_mapping FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user.id),
    )
    mapping_raw = dict(rows[0]).get("speaker_mapping") if rows else None
    if mapping_raw:
        mapping = json.loads(mapping_raw)
        for label, entry in mapping.items():
            if not isinstance(entry, dict):
                continue
            verified = entry.get("manuallyVerified", False)
            dismissed = entry.get("identificationStatus") == "dismissed"
            if not verified and not dismissed:
                # Reset identification fields
                for key in [
                    "participantId",
                    "confidence", "similarity",
                    "identificationStatus",
                    "suggestedParticipantId",
                    "suggestedDisplayName",
                    "topCandidates",
                    "identifiedAt",
                    "embedding",
                ]:
                    entry.pop(key, None)

        await db.execute(
            """UPDATE recordings SET speaker_mapping = ?, speaker_mapping_updated_at = datetime('now'),
               updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (json.dumps(mapping), recording_id, user.id),
        )
        await db.commit()

    # Re-run identification
    async with speaker_processor._speaker_id_lock:
        identified = await speaker_processor.process_recording(user.id, recording_id)
        if identified:
            await speaker_processor.rerate_speakers(user.id)

    return await recording_service.get_recording(user.id, recording_id)


# ---------------------------------------------------------------------------
# Tags (on recordings)
# ---------------------------------------------------------------------------


@router.post("/{recording_id}/tags/{tag_id}", status_code=204)
async def add_tag(recording_id: str, tag_id: str, user: CurrentUser):
    """Add a tag to a recording."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    await tag_service.add_tag_to_recording(user.id, recording_id, tag_id)


@router.delete("/{recording_id}/tags/{tag_id}", status_code=204)
async def remove_tag(recording_id: str, tag_id: str, user: CurrentUser):
    """Remove a tag from a recording."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    await tag_service.remove_tag_from_recording(user.id, recording_id, tag_id)


# ---------------------------------------------------------------------------
# Analyze (AI)
# ---------------------------------------------------------------------------


@router.post("/{recording_id}/analyze")
async def analyze_recording(
    recording_id: str, body: AnalysisRequest, user: CurrentUser
):
    """Run an analysis template against a recording's transcript."""
    recording = await recording_service.get_recording(user.id, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if not recording.diarized_text and not recording.transcript_text:
        raise HTTPException(status_code=400, detail="Recording has no transcript")

    # Fetch the analysis template
    from app.database import get_db
    db = await get_db()
    template_rows = await db.execute_fetchall(
        "SELECT * FROM analysis_templates WHERE id = ? AND user_id = ?",
        (body.template_id, user.id),
    )
    if not template_rows:
        raise HTTPException(status_code=404, detail="Analysis template not found")
    template = dict(template_rows[0])

    transcript = recording.diarized_text or recording.transcript_text
    result = await ai_service.run_analysis(
        transcript=transcript,
        prompt_template=template["prompt"],
    )
    return {"result": result}
