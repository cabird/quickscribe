"""Recording business logic — CRUD, search, audio URLs, transcript paste."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.database import get_db
from app.models import (
    PaginatedResponse,
    PasteTranscriptRequest,
    Recording,
    RecordingDetail,
    RecordingSource,
    RecordingStatus,
    RecordingSummary,
    RecordingUpdate,
    SpeakerMapping,
    SpeakerMappingEntry,
)
from app.services import storage_service

logger = logging.getLogger(__name__)

# Columns selected for list views (no transcript text/JSON to keep responses light)
_SUMMARY_COLUMNS = """
    id, user_id, title, description, original_filename, duration_seconds,
    recorded_at, source, status, token_count, plaud_id, speaker_mapping,
    created_at, updated_at
"""


def _row_to_summary(
    row: dict,
    tag_ids: list[str] | None = None,
) -> RecordingSummary:
    """Convert a DB row to a RecordingSummary, extracting speaker names."""
    speaker_names: list[str] | None = None
    mapping_raw = row.get("speaker_mapping")
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw)
            names = []
            for label, entry in mapping.items():
                name = entry.get("displayName")
                if name:
                    names.append(name)
            speaker_names = names if names else None
        except (json.JSONDecodeError, AttributeError):
            pass

    return RecordingSummary(
        id=row["id"],
        user_id=row["user_id"],
        title=row.get("title"),
        description=row.get("description"),
        original_filename=row["original_filename"],
        duration_seconds=row.get("duration_seconds"),
        recorded_at=row.get("recorded_at"),
        source=row["source"],
        status=row["status"],
        token_count=row.get("token_count"),
        plaud_id=row.get("plaud_id"),
        speaker_names=speaker_names,
        tag_ids=tag_ids,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_detail(row: dict, tag_ids: list[str] | None = None) -> RecordingDetail:
    """Convert a full DB row to a RecordingDetail."""
    speaker_mapping = None
    mapping_raw = row.get("speaker_mapping")
    if mapping_raw:
        try:
            raw = json.loads(mapping_raw)
            # Parse through Pydantic models for validation
            speaker_mapping = {
                label: SpeakerMappingEntry.model_validate(entry)
                for label, entry in raw.items()
                if isinstance(entry, dict)
            }
        except (json.JSONDecodeError, Exception):
            pass

    # Parse search_keywords from JSON
    search_keywords = None
    keywords_raw = row.get("search_keywords")
    if keywords_raw:
        try:
            search_keywords = json.loads(keywords_raw)
        except (json.JSONDecodeError, Exception):
            pass

    return RecordingDetail(
        id=row["id"],
        user_id=row["user_id"],
        title=row.get("title"),
        description=row.get("description"),
        original_filename=row["original_filename"],
        file_path=row.get("file_path"),
        duration_seconds=row.get("duration_seconds"),
        recorded_at=row.get("recorded_at"),
        source=row["source"],
        status=row["status"],
        status_message=row.get("status_message"),
        token_count=row.get("token_count"),
        plaud_id=row.get("plaud_id"),
        transcript_text=row.get("transcript_text"),
        diarized_text=row.get("diarized_text"),
        transcript_json=row.get("transcript_json"),
        speaker_mapping=speaker_mapping,
        search_summary=row.get("search_summary"),
        search_keywords=search_keywords,
        tag_ids=tag_ids,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


async def _get_tag_ids(recording_id: str) -> list[str]:
    """Fetch tag IDs for a recording."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT tag_id FROM recording_tags WHERE recording_id = ?",
        (recording_id,),
    )
    return [dict(r)["tag_id"] for r in rows]


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


async def list_recordings(
    user_id: str,
    page: int = 1,
    per_page: int = 50,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> PaginatedResponse:
    """List recordings with pagination, optional search and date filtering.

    Args:
        user_id: Owner's user ID.
        page: 1-based page number.
        per_page: Results per page (max 100).
        search: Optional FTS5 search query.
        date_from: Optional ISO date string for start of date range.
        date_to: Optional ISO date string for end of date range.

    Returns:
        PaginatedResponse containing RecordingSummary items.
    """
    db = await get_db()
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page
    params: list = []

    if search:
        # Use FTS5 for text search
        base_query = f"""
            SELECT {_SUMMARY_COLUMNS}
            FROM recordings
            WHERE user_id = ? AND rowid IN (
                SELECT rowid FROM recordings_fts WHERE recordings_fts MATCH ?
            )
        """
        count_query = """
            SELECT COUNT(*) as cnt FROM recordings
            WHERE user_id = ? AND rowid IN (
                SELECT rowid FROM recordings_fts WHERE recordings_fts MATCH ?
            )
        """
        params = [user_id, search]
    else:
        base_query = f"SELECT {_SUMMARY_COLUMNS} FROM recordings WHERE user_id = ?"
        count_query = "SELECT COUNT(*) as cnt FROM recordings WHERE user_id = ?"
        params = [user_id]

    # Date range filters
    if date_from:
        base_query += " AND recorded_at >= ?"
        count_query += " AND recorded_at >= ?"
        params.append(date_from)
    if date_to:
        base_query += " AND recorded_at <= ?"
        count_query += " AND recorded_at <= ?"
        params.append(date_to)

    # Count total
    count_rows = await db.execute_fetchall(count_query, params)
    total = dict(count_rows[0])["cnt"] if count_rows else 0

    # Fetch page
    base_query += " ORDER BY recorded_at DESC NULLS LAST, created_at DESC LIMIT ? OFFSET ?"
    rows = await db.execute_fetchall(base_query, params + [per_page, offset])

    recording_ids = [dict(r)["id"] for r in rows]
    tag_map = await _get_tag_ids_bulk(recording_ids)

    data = [
        _row_to_summary(
            dict(r),
            tag_ids=tag_map.get(dict(r)["id"]),
        )
        for r in rows
    ]

    return PaginatedResponse(data=data, total=total, page=page, per_page=per_page)


async def get_recording(user_id: str, recording_id: str) -> RecordingDetail:
    """Get a single recording with full transcript data.

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    tag_ids = await _get_tag_ids(recording_id)
    detail = _row_to_detail(dict(rows[0]), tag_ids=tag_ids)

    # Strip embedding arrays from API responses (192-float arrays are large)
    if detail.speaker_mapping:
        for entry in detail.speaker_mapping.values():
            entry.embedding = None

    # Get collections this recording belongs to
    col_rows = await db.execute_fetchall(
        """SELECT c.id, c.name FROM collections c
           JOIN collection_items ci ON c.id = ci.collection_id
           WHERE ci.recording_id = ? AND c.user_id = ?""",
        (recording_id, user_id),
    )
    if col_rows:
        detail.collections = [{"id": dict(r)["id"], "name": dict(r)["name"]} for r in col_rows]

    return detail


async def create_recording(
    user_id: str,
    original_filename: str,
    source: RecordingSource,
    title: str | None = None,
    description: str | None = None,
    file_path: str | None = None,
    duration_seconds: float | None = None,
    recorded_at: str | None = None,
    plaud_id: str | None = None,
    plaud_metadata_json: str | None = None,
    status: RecordingStatus = RecordingStatus.pending,
    transcript_text: str | None = None,
    diarized_text: str | None = None,
    transcript_json: str | None = None,
    token_count: int | None = None,
    speaker_mapping: str | None = None,
) -> Recording:
    """Create a new recording row.

    Returns:
        The created Recording.
    """
    db = await get_db()
    recording_id = str(uuid.uuid4())

    await db.execute(
        """INSERT INTO recordings (
            id, user_id, original_filename, source, title, description,
            file_path, duration_seconds, recorded_at, plaud_id,
            plaud_metadata_json, status, transcript_text, diarized_text,
            transcript_json, token_count, speaker_mapping,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  datetime('now'), datetime('now'))""",
        (
            recording_id, user_id, original_filename, source.value,
            title, description, file_path, duration_seconds, recorded_at,
            plaud_id, plaud_metadata_json, status.value,
            transcript_text, diarized_text, transcript_json,
            token_count, speaker_mapping,
        ),
    )
    await db.commit()

    rows = await db.execute_fetchall(
        "SELECT * FROM recordings WHERE id = ?", (recording_id,)
    )
    return Recording(**dict(rows[0]))


async def update_recording(
    user_id: str,
    recording_id: str,
    updates: RecordingUpdate,
) -> RecordingDetail:
    """Update recording metadata (title, description, recorded_at).

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    # Verify ownership
    existing = await get_recording(user_id, recording_id)

    db = await get_db()
    set_clauses: list[str] = []
    params: list = []

    if updates.title is not None:
        set_clauses.append("title = ?")
        params.append(updates.title)
    if updates.description is not None:
        set_clauses.append("description = ?")
        params.append(updates.description)
    if updates.recorded_at is not None:
        set_clauses.append("recorded_at = ?")
        params.append(updates.recorded_at.isoformat())

    if not set_clauses:
        return existing

    set_clauses.append("updated_at = datetime('now')")
    sql = f"UPDATE recordings SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?"
    params.extend([recording_id, user_id])

    await db.execute(sql, params)
    await db.commit()

    return await get_recording(user_id, recording_id)


async def delete_recording(user_id: str, recording_id: str) -> None:
    """Delete a recording, its blob, and block Plaud re-import if applicable.

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, plaud_id, file_path FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    row = dict(rows[0])

    # Block Plaud re-import
    if row.get("plaud_id"):
        await db.execute(
            "INSERT OR IGNORE INTO deleted_plaud_ids (user_id, plaud_id) VALUES (?, ?)",
            (user_id, row["plaud_id"]),
        )

    # Delete blob if exists
    if row.get("file_path"):
        try:
            await storage_service.delete_blob(row["file_path"])
        except Exception:
            logger.warning("Failed to delete blob %s", row["file_path"])

    # Delete recording (cascade deletes recording_tags)
    await db.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
    await db.commit()

    logger.info("Deleted recording %s for user %s", recording_id, user_id)


async def get_audio_url(user_id: str, recording_id: str) -> str:
    """Generate a SAS URL for streaming the recording audio.

    Raises:
        HTTPException 404 if not found or no file_path.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT file_path FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Recording not found")

    file_path = dict(rows[0]).get("file_path")
    if not file_path:
        raise HTTPException(status_code=404, detail="No audio file for this recording")

    return storage_service.generate_sas_url(file_path, hours=4)


async def paste_transcript(
    user_id: str, request: PasteTranscriptRequest
) -> RecordingDetail:
    """Create a recording from pasted transcript text (no audio file).

    Used for importing Zoom/Teams transcripts etc.
    """
    title = request.title or "Pasted Transcript"
    source_suffix = f" ({request.source_app})" if request.source_app else ""
    filename = f"paste{source_suffix}"

    # Estimate token count (~4 chars per token)
    token_count = len(request.transcript_text) // 4

    recording = await create_recording(
        user_id=user_id,
        original_filename=filename,
        source=RecordingSource.paste,
        title=title,
        status=RecordingStatus.ready,
        transcript_text=request.transcript_text,
        diarized_text=request.transcript_text,
        token_count=token_count,
        recorded_at=request.recorded_at.isoformat() if request.recorded_at else None,
    )

    return await get_recording(user_id, recording.id)


async def reprocess_recording(
    user_id: str, recording_id: str
) -> RecordingDetail:
    """Reset a failed recording to pending status for reprocessing.

    Clears the error message and resets status to pending so the
    sync poller will pick it up again.

    Raises:
        HTTPException 404 if not found or not owned by user.
    """
    existing = await get_recording(user_id, recording_id)

    db = await get_db()
    await db.execute(
        """UPDATE recordings
           SET status = ?, status_message = NULL, retry_count = retry_count + 1,
               updated_at = datetime('now')
           WHERE id = ? AND user_id = ?""",
        (RecordingStatus.pending.value, recording_id, user_id),
    )
    await db.commit()

    return await get_recording(user_id, recording_id)


async def assign_speaker(
    user_id: str,
    recording_id: str,
    speaker_label: str,
    participant_id: str,
    manually_verified: bool = True,
    use_for_training: bool = False,
) -> RecordingDetail:
    """Assign a participant to a speaker label in a recording's speaker_mapping.

    Updates the speaker_mapping JSON to set the participant_id and display_name
    for the given speaker label.

    Raises:
        HTTPException 404 if recording not found or not owned by user.
        HTTPException 400 if speaker_label not found in mapping.
    """
    existing = await get_recording(user_id, recording_id)

    db = await get_db()

    # Get current speaker_mapping
    rows = await db.execute_fetchall(
        "SELECT speaker_mapping FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )
    mapping_raw = dict(rows[0]).get("speaker_mapping")
    mapping = json.loads(mapping_raw) if mapping_raw else {}

    if speaker_label not in mapping:
        mapping[speaker_label] = {}

    # Look up participant display name
    participant_rows = await db.execute_fetchall(
        "SELECT display_name FROM participants WHERE id = ? AND user_id = ?",
        (participant_id, user_id),
    )
    display_name = dict(participant_rows[0])["display_name"] if participant_rows else None

    mapping[speaker_label]["participantId"] = participant_id
    mapping[speaker_label]["displayName"] = display_name
    mapping[speaker_label]["manuallyVerified"] = manually_verified
    mapping[speaker_label]["identificationStatus"] = "auto" if manually_verified else "suggest"
    mapping[speaker_label]["useForTraining"] = use_for_training

    await db.execute(
        """UPDATE recordings
           SET speaker_mapping = ?, updated_at = datetime('now')
           WHERE id = ? AND user_id = ?""",
        (json.dumps(mapping), recording_id, user_id),
    )

    # Update speaker profile with embedding if available (training loop)
    embedding = mapping[speaker_label].get("embedding")
    if manually_verified and embedding and participant_id:
        try:
            from app.services import profile_store
            await profile_store.update_profile_with_embedding(
                user_id, participant_id, display_name or "Unknown",
                embedding, recording_id,
            )
        except Exception as e:
            logger.warning("Failed to update speaker profile: %s", e)
    await db.commit()

    return await get_recording(user_id, recording_id)


async def dismiss_speaker(
    user_id: str,
    recording_id: str,
    speaker_label: str,
) -> RecordingDetail:
    """Dismiss a speaker from reviews by setting identificationStatus to dismissed.

    Raises:
        HTTPException 404 if recording not found or not owned by user.
        HTTPException 400 if speaker_label not found in mapping.
    """
    existing = await get_recording(user_id, recording_id)

    db = await get_db()

    rows = await db.execute_fetchall(
        "SELECT speaker_mapping FROM recordings WHERE id = ? AND user_id = ?",
        (recording_id, user_id),
    )
    mapping_raw = dict(rows[0]).get("speaker_mapping")
    mapping = json.loads(mapping_raw) if mapping_raw else {}

    if speaker_label not in mapping:
        raise HTTPException(status_code=400, detail=f"Speaker label '{speaker_label}' not found in mapping")

    mapping[speaker_label]["identificationStatus"] = "dismissed"

    await db.execute(
        """UPDATE recordings
           SET speaker_mapping = ?, updated_at = datetime('now')
           WHERE id = ? AND user_id = ?""",
        (json.dumps(mapping), recording_id, user_id),
    )
    await db.commit()

    return await get_recording(user_id, recording_id)


async def upload_recording(
    user_id: str,
    file: "UploadFile",
    title: str | None = None,
) -> RecordingDetail:
    """Handle file upload: save to temp, upload to blob, create recording.

    If speech services are enabled, submits the recording for transcription
    so the poll_transcriptions scheduler picks it up automatically.

    Args:
        user_id: Owner's user ID.
        file: The uploaded file from FastAPI.
        title: Optional title for the recording.

    Returns:
        The created RecordingDetail.
    """
    import tempfile
    from pathlib import Path
    from fastapi import UploadFile

    from app.config import get_settings

    settings = get_settings()
    original_filename = file.filename or "upload"
    logger.info("upload_recording: starting for user=%s, file=%s", user_id[:12], original_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / original_filename
        # Stream to disk in chunks to avoid loading entire file into memory
        bytes_written = 0
        with local_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
                bytes_written += len(chunk)
        logger.info("upload_recording: saved %s to temp (%d bytes)", original_filename, bytes_written)

        # Transcode to MP3 for Azure Speech Services compatibility
        mp3_path = Path(tmpdir) / f"{Path(original_filename).stem}.mp3"
        if local_path.suffix.lower() != ".mp3":
            from app.services.sync_service import _transcode_to_mp3
            logger.info("upload_recording: transcoding %s → MP3", local_path.suffix)
            await _transcode_to_mp3(local_path, mp3_path)
            upload_path = mp3_path
            logger.info("upload_recording: transcode complete (%d bytes)", mp3_path.stat().st_size)
        else:
            upload_path = local_path

        # Build blob path (always .mp3 for transcription compatibility)
        recording_id = str(uuid.uuid4())
        blob_name = f"{user_id}/{recording_id}.mp3"

        # Upload transcoded file to blob storage
        logger.info("upload_recording: uploading to blob storage as %s", blob_name)
        await storage_service.upload_file(upload_path, blob_name)
        logger.info("upload_recording: blob upload complete")

        # If using local storage but speech is enabled, also upload to Azure Blob
        # so Azure Speech Services can access the audio via a SAS URL
        if settings.use_local_storage and settings.speech_enabled and settings.azure_storage_connection_string:
            from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient
            async with AsyncBlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            ) as azure_client:
                container = azure_client.get_container_client(settings.azure_storage_container)
                blob = container.get_blob_client(blob_name)
                with open(upload_path, "rb") as f:
                    await blob.upload_blob(f, overwrite=True)
                logger.info("upload_recording: also uploaded to Azure Blob for transcription: %s", blob_name)

    # Determine initial status based on whether speech services are configured
    should_transcribe = settings.speech_enabled and bool(settings.azure_storage_connection_string)
    initial_status = RecordingStatus.transcribing if should_transcribe else RecordingStatus.pending
    logger.info("upload_recording: should_transcribe=%s", should_transcribe)

    # Create recording in DB
    from datetime import datetime, timezone
    recording = await create_recording(
        user_id=user_id,
        original_filename=original_filename,
        source=RecordingSource.upload,
        title=title,
        file_path=blob_name,
        status=initial_status,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("upload_recording: DB record created id=%s, status=%s", recording.id[:12], initial_status)

    # Submit for transcription if speech services are configured
    if should_transcribe:
        try:
            from app.services.speech_client import SpeechClient

            logger.info("upload_recording: generating SAS URL for %s", blob_name)
            audio_url = storage_service._azure_sas_url(blob_name, 24, settings)
            speech = SpeechClient()
            logger.info("upload_recording: submitting to Azure Speech Services")
            transcription_id = await speech.create_transcription(
                audio_url=audio_url,
                display_name=original_filename,
            )

            db = await get_db()
            await db.execute(
                """UPDATE recordings
                   SET provider_job_id = ?, processing_started = datetime('now')
                   WHERE id = ?""",
                (transcription_id, recording.id),
            )
            await db.commit()
            logger.info("upload_recording: transcription submitted %s (job=%s)", original_filename, transcription_id[:8])
        except Exception as e:
            logger.exception("upload_recording: FAILED to submit transcription for %s: %s", original_filename, e)
            # Revert status to pending so it can be retried
            db = await get_db()
            await db.execute(
                "UPDATE recordings SET status = 'pending', status_message = ? WHERE id = ?",
                (f"Transcription submission failed: {e}", recording.id),
            )
            await db.commit()
    else:
        logger.info("upload_recording: skipping transcription (not configured)")

    result = await get_recording(user_id, recording.id)
    logger.info("upload_recording: done, returning recording %s", recording.id[:12])
    return result


async def search_recordings(user_id: str, query: str) -> list[RecordingSummary]:
    """Full-text search across recording titles, descriptions, and transcripts.

    Uses SQLite FTS5. Returns up to 50 results ranked by relevance.
    """
    db = await get_db()

    rows = await db.execute_fetchall(
        f"""SELECT {_SUMMARY_COLUMNS}
            FROM recordings
            WHERE user_id = ? AND rowid IN (
                SELECT rowid FROM recordings_fts WHERE recordings_fts MATCH ?
            )
            ORDER BY recorded_at DESC
            LIMIT 50""",
        (user_id, query),
    )

    recording_ids = [dict(r)["id"] for r in rows]
    tag_map = await _get_tag_ids_bulk(recording_ids)

    return [
        _row_to_summary(dict(r), tag_ids=tag_map.get(dict(r)["id"]))
        for r in rows
    ]


def _parse_duration_to_seconds(iso_dur: str) -> float | None:
    """Parse ISO 8601 duration like 'PT2.12S' or 'PT1M30.5S' to seconds."""
    if not iso_dur:
        return None
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", iso_dur)
    if m:
        h = float(m.group(1) or 0)
        mins = float(m.group(2) or 0)
        s = float(m.group(3) or 0)
        return h * 3600 + mins * 60 + s
    return None


async def get_recordings_for_review(user_id: str) -> list[dict]:
    """Get recordings that have speakers with suggest/unknown identification status.

    Returns lightweight recording info plus full speaker_mapping for the reviews UI.
    Speaker_mapping is parsed through Pydantic for normalization and enriched with
    participant display names.
    """
    db = await get_db()

    # Find recordings with suggest or unknown speakers
    rows = await db.execute_fetchall(
        """SELECT id, user_id, title, original_filename, recorded_at,
                  duration_seconds, speaker_mapping, source, status,
                  transcript_json, file_path
           FROM recordings
           WHERE user_id = ? AND speaker_mapping IS NOT NULL
             AND (speaker_mapping LIKE '%"identificationStatus":"suggest"%'
               OR speaker_mapping LIKE '%"identificationStatus": "suggest"%'
               OR speaker_mapping LIKE '%"identificationStatus":"unknown"%'
               OR speaker_mapping LIKE '%"identificationStatus": "unknown"%')
           ORDER BY recorded_at DESC""",
        (user_id,),
    )

    if not rows:
        return []

    results = []
    for row in rows:
        r = dict(row)
        # Parse speaker_mapping through Pydantic for normalization
        try:
            raw_mapping = json.loads(r["speaker_mapping"])
            mapping = {}
            for label, entry_data in raw_mapping.items():
                entry = SpeakerMappingEntry.model_validate(entry_data)
                # Strip embeddings
                entry.embedding = None
                mapping[label] = entry.model_dump()
        except (json.JSONDecodeError, Exception):
            continue

        # Extract per-speaker segments from transcript_json for audio playback
        speaker_segments: dict[str, dict] = {}
        tj = r.get("transcript_json")
        if tj:
            try:
                tj_data = json.loads(tj) if isinstance(tj, str) else tj
                phrases = tj_data.get("recognizedPhrases", [])
                for phrase in phrases:
                    spk = phrase.get("speaker")
                    if spk is None:
                        continue
                    label = f"Speaker {spk}"
                    offset = phrase.get("offset", "")
                    duration = phrase.get("duration", "")
                    # Parse ISO 8601 duration to seconds
                    offset_s = _parse_duration_to_seconds(offset)
                    duration_s = _parse_duration_to_seconds(duration)
                    if offset_s is not None and duration_s is not None:
                        if label not in speaker_segments or duration_s > speaker_segments[label].get("duration_s", 0):
                            speaker_segments[label] = {
                                "start_s": offset_s,
                                "duration_s": duration_s,
                                "end_s": offset_s + duration_s,
                            }
            except (json.JSONDecodeError, Exception):
                pass

        results.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "title": r.get("title") or r.get("original_filename"),
            "original_filename": r.get("original_filename"),
            "recorded_at": r.get("recorded_at"),
            "duration_seconds": r.get("duration_seconds"),
            "source": r.get("source"),
            "status": r.get("status"),
            "file_path": r.get("file_path"),
            "speaker_mapping": mapping,
            "speaker_segments": speaker_segments,
        })

    return results
