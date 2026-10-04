"""Audio upload pipeline — fast receive, background transcode and submit.

The upload request only saves the raw file to blob storage and creates the
recording row. Everything slow (ffmpeg, Azure Speech submission) runs in a
background task afterwards.

The recording row is the job: status 'pending' or 'transcoding' with no
provider_job_id means work is still owed. resume_pending_uploads() finds such
rows at startup and on a schedule, so a restart mid-transcode loses nothing
and there is no separate jobs table to prune.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import sqlite3
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.config import get_settings
from app.database import get_db
from app.models import RecordingDetail, RecordingSource, RecordingStatus
from app.services import recording_service, storage_service
from app.services.speech_client import SpeechClient
from app.services.sync_service import _spawn, _transcode_to_mp3

if TYPE_CHECKING:
    from fastapi import UploadFile

logger = logging.getLogger(__name__)

# Statuses that mean "audio saved, transcription not yet submitted"
_OWED_STATUSES = (RecordingStatus.pending.value, RecordingStatus.transcoding.value)

# A multi-hour recording can take several minutes to encode on a small instance
_TRANSCODE_TIMEOUT_SECONDS = 3600

# One recording at a time — the app runs on a single small instance. Holding
# this while re-reading the row is also what stops the scheduled sweep and a
# just-spawned task from processing the same recording twice.
_process_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Request path
# ---------------------------------------------------------------------------


async def receive_upload(
    user_id: str,
    file: "UploadFile",
    title: str | None = None,
    recorded_at: datetime | None = None,
) -> dict:
    """Save an uploaded audio file and queue it for background processing.

    Returns as soon as the raw file is in blob storage and the recording row
    exists. Uploading bytes the user already uploaded returns the existing
    recording instead (and retries it if it had failed).

    Returns:
        {"recording_id", "status", "duplicate"}
    """
    original_filename = file.filename or "upload"
    suffix = _safe_suffix(original_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Fixed local name: the client-supplied filename never touches the disk path
        local_path = Path(tmpdir) / f"raw{suffix}"
        digest = hashlib.sha256()
        size = 0
        with local_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        content_hash = digest.hexdigest()

        existing = await _find_by_hash(user_id, content_hash)
        if existing:
            return await _duplicate_result(user_id, existing)

        probed = await _probe_media(local_path)

        recording_id = str(uuid.uuid4())
        # MP3 uploads are stored under their final name; anything else is kept
        # as-is until the background task has transcoded it.
        if suffix == ".mp3":
            blob_name = f"{user_id}/{recording_id}.mp3"
        else:
            blob_name = f"{user_id}/{recording_id}.orig{suffix}"
        await storage_service.upload_file(local_path, blob_name)

    try:
        await recording_service.create_recording(
            user_id=user_id,
            original_filename=original_filename,
            source=RecordingSource.upload,
            title=title or None,
            file_path=blob_name,
            duration_seconds=probed.get("duration_seconds"),
            recorded_at=_resolve_recorded_at(recorded_at, probed.get("recorded_at")),
            status=RecordingStatus.pending,
            recording_id=recording_id,
            content_hash=content_hash,
        )
    except sqlite3.IntegrityError:
        # The same file arrived twice at once and the other request won
        await _delete_quietly(blob_name)
        existing = await _find_by_hash(user_id, content_hash)
        if not existing:
            raise
        return await _duplicate_result(user_id, existing)

    logger.info(
        "Upload received: recording=%s user=%s file=%s (%d bytes)",
        recording_id[:12], user_id[:12], original_filename, size,
    )
    _spawn(process_upload(recording_id))
    return {
        "recording_id": recording_id,
        "status": RecordingStatus.pending.value,
        "duplicate": False,
    }


async def reprocess_recording(user_id: str, recording_id: str) -> RecordingDetail:
    """Retry a recording whose transcode or transcription failed.

    Raises:
        HTTPException 404 if not found or not owned by user, 400 if it has no
        audio, 409 if it is not waiting or failed.
    """
    existing = await recording_service.get_recording(user_id, recording_id)
    if not existing.file_path:
        raise HTTPException(status_code=400, detail="Recording has no audio to reprocess")
    if existing.status not in (RecordingStatus.failed, RecordingStatus.pending):
        raise HTTPException(
            status_code=409,
            detail=f"Recording is {existing.status.value}; only failed recordings can be reprocessed",
        )

    await _requeue(user_id, recording_id)
    return await recording_service.get_recording(user_id, recording_id)


async def _requeue(user_id: str, recording_id: str) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE recordings
           SET status = ?, status_message = NULL, provider_job_id = NULL,
               retry_count = retry_count + 1, updated_at = datetime('now')
           WHERE id = ? AND user_id = ?""",
        (RecordingStatus.pending.value, recording_id, user_id),
    )
    await db.commit()
    _spawn(process_upload(recording_id))


async def _find_by_hash(user_id: str, content_hash: str) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, status FROM recordings WHERE user_id = ? AND content_hash = ?",
        (user_id, content_hash),
    )
    return dict(rows[0]) if rows else None


async def _duplicate_result(user_id: str, existing: dict) -> dict:
    status = existing["status"]
    if status == RecordingStatus.failed.value:
        # Sending the file again is the natural way to retry from a phone
        await _requeue(user_id, existing["id"])
        status = RecordingStatus.pending.value
    logger.info("Upload is a duplicate of recording %s (status=%s)", existing["id"][:12], status)
    return {"recording_id": existing["id"], "status": status, "duplicate": True}


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else ""


def _resolve_recorded_at(explicit: datetime | None, probed: datetime | None) -> str:
    """Pick the recording time: caller-supplied, else the file's own, else now.

    Stored as UTC so the text column sorts chronologically.
    """
    chosen = explicit or probed or datetime.now(timezone.utc)
    if chosen.tzinfo is None:
        chosen = chosen.replace(tzinfo=timezone.utc)
    return chosen.astimezone(timezone.utc).isoformat()


async def _probe_media(path: Path) -> dict:
    """Read duration and embedded creation time with ffprobe.

    Best-effort: returns {} if ffprobe is missing, fails or finds nothing.
    """

    def _run_ffprobe() -> dict:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        return _parse_probe(json.loads(result.stdout))

    try:
        return await asyncio.to_thread(_run_ffprobe)
    except Exception as exc:
        logger.warning("ffprobe failed for %s: %s", path.name, exc)
        return {}


def _parse_probe(data: dict) -> dict:
    """Extract {"duration_seconds", "recorded_at"} from ffprobe -show_format JSON."""
    fmt = data.get("format") or {}
    result: dict = {}

    try:
        duration = float(fmt.get("duration"))
        if duration > 0:
            result["duration_seconds"] = duration
    except (TypeError, ValueError):
        pass

    tags = {str(k).lower(): v for k, v in (fmt.get("tags") or {}).items()}
    # Apple's tag carries the local offset; creation_time is the generic MP4 one
    for key in ("com.apple.quicktime.creationdate", "creation_time"):
        parsed = _parse_media_datetime(tags.get(key))
        if parsed:
            result["recorded_at"] = parsed
            break

    return result


def _parse_media_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # Encoders that don't know the time write 1904/1970; ignore those and
    # anything from the future.
    if parsed.year < 2000 or parsed > datetime.now(timezone.utc) + timedelta(days=1):
        return None
    return parsed


# ---------------------------------------------------------------------------
# Background path
# ---------------------------------------------------------------------------


async def process_upload(recording_id: str) -> None:
    """Transcode a stored recording to MP3 if needed and submit it for transcription.

    Safe to call more than once: it does nothing unless the recording is
    still owed work. Failures mark the recording 'failed' with the reason;
    the raw audio stays in storage so it can be reprocessed.
    """
    try:
        async with _process_lock:
            await _process(recording_id)
    except asyncio.CancelledError:
        # Shutdown: leave the row as it is so the next startup resumes it
        raise
    except Exception as exc:
        logger.exception("Upload processing failed for %s: %s", recording_id, exc)
        await _mark_failed(recording_id, str(exc))


async def resume_pending_uploads() -> int:
    """Process every recording that is still owed a transcode or submission.

    Run at startup and on a schedule; picks up work interrupted by a restart.

    Returns:
        The number of recordings attempted.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id FROM recordings
           WHERE status IN (?, ?) AND provider_job_id IS NULL AND file_path IS NOT NULL
           ORDER BY created_at""",
        _OWED_STATUSES,
    )
    for row in rows:
        await process_upload(dict(row)["id"])
    return len(rows)


async def _process(recording_id: str) -> None:
    settings = get_settings()
    db = await get_db()

    rows = await db.execute_fetchall(
        """SELECT id, user_id, original_filename, file_path, status, provider_job_id
           FROM recordings WHERE id = ?""",
        (recording_id,),
    )
    if not rows:
        return
    rec = dict(rows[0])
    if rec["status"] not in _OWED_STATUSES or rec["provider_job_id"] or not rec["file_path"]:
        return

    file_path: str = rec["file_path"]
    should_transcribe = settings.speech_enabled and bool(settings.azure_storage_connection_string)
    needs_transcode = not file_path.lower().endswith(".mp3")
    # Local-storage dev with real Speech: Azure needs its own copy to read
    needs_mirror = settings.use_local_storage and should_transcribe

    if needs_transcode or needs_mirror:
        with tempfile.TemporaryDirectory() as tmpdir:
            if needs_transcode:
                await _set_status(recording_id, RecordingStatus.transcoding)
                raw_path = Path(tmpdir) / f"raw{Path(file_path).suffix}"
                local_path = Path(tmpdir) / "audio.mp3"
                await storage_service.download_file(file_path, raw_path)
                logger.info("Transcoding %s for recording %s", raw_path.suffix, recording_id[:12])
                await _transcode_to_mp3(raw_path, local_path, timeout=_TRANSCODE_TIMEOUT_SECONDS)

                mp3_blob = f"{rec['user_id']}/{recording_id}.mp3"
                await storage_service.upload_file(local_path, mp3_blob)
                cursor = await db.execute(
                    "UPDATE recordings SET file_path = ?, updated_at = datetime('now') WHERE id = ?",
                    (mp3_blob, recording_id),
                )
                await db.commit()
                if not cursor.rowcount:
                    # Deleted while we were transcoding; don't leave the MP3 behind
                    await _delete_quietly(mp3_blob)
                    return
                await _delete_quietly(file_path)
                file_path = mp3_blob
            else:
                local_path = Path(tmpdir) / "audio.mp3"
                await storage_service.download_file(file_path, local_path)

            if needs_mirror:
                await _mirror_to_azure(local_path, file_path, settings)

    if not should_transcribe:
        # Nothing to submit to; park it as pending, as before. Only write when
        # the status actually changed — the sweep revisits parked rows.
        if needs_transcode:
            await _set_status(recording_id, RecordingStatus.pending)
            logger.info("Recording %s stored; transcription not configured", recording_id[:12])
        return

    audio_url = storage_service._azure_sas_url(file_path, 24, settings)
    transcription_id = await SpeechClient().create_transcription(
        audio_url=audio_url,
        display_name=rec["original_filename"],
    )
    await db.execute(
        """UPDATE recordings
           SET status = ?, provider_job_id = ?, status_message = NULL,
               processing_started = datetime('now'), updated_at = datetime('now')
           WHERE id = ?""",
        (RecordingStatus.transcribing.value, transcription_id, recording_id),
    )
    await db.commit()
    logger.info(
        "Transcription submitted for recording %s (job=%s)",
        recording_id[:12], transcription_id[:8],
    )


async def _set_status(recording_id: str, status: RecordingStatus) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE recordings SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status.value, recording_id),
    )
    await db.commit()


async def _mark_failed(recording_id: str, message: str) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE recordings
           SET status = ?, status_message = ?, updated_at = datetime('now')
           WHERE id = ? AND status IN (?, ?)""",
        (RecordingStatus.failed.value, message[:500], recording_id, *_OWED_STATUSES),
    )
    await db.commit()


async def _delete_quietly(blob_name: str) -> None:
    try:
        await storage_service.delete_blob(blob_name)
    except Exception as exc:
        logger.warning("Failed to delete blob %s: %s", blob_name, exc)


async def _mirror_to_azure(local_path: Path, blob_name: str, settings) -> None:
    from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient

    async with AsyncBlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as azure_client:
        container = azure_client.get_container_client(settings.azure_storage_container)
        blob = container.get_blob_client(blob_name)
        with open(local_path, "rb") as f:
            await blob.upload_blob(f, overwrite=True)
    logger.info("Also uploaded to Azure Blob for transcription: %s", blob_name)
