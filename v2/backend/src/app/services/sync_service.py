"""Plaud sync orchestration — fetches new recordings, transcribes, enriches.

Orchestrates: plaud_client -> storage_service -> speech_client -> ai_service.
Logs each sync run to the sync_runs table. Idempotent by design.
"""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.config import get_settings
from app.database import get_db
from app.models import (
    PaginatedResponse,
    PlaudMetadata,
    RecordingSource,
    RecordingStatus,
    SyncRun,
    SyncRunDetail,
    SyncRunStatus,
    SyncRunSummary,
    SyncTrigger,
)
from app.services import ai_service, plaud_client, recording_service, storage_service
from app.services.run_logger import RunLogger
from app.services.speech_client import SpeechClient

logger = logging.getLogger(__name__)

# Concurrency guard — prevents overlapping sync runs
_sync_running = False


async def _create_sync_run(trigger: str, run_type: str = "plaud_sync") -> str:
    """Insert a new sync_run row and return its ID."""
    db = await get_db()
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO sync_runs (id, started_at, status, trigger, type, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, now, SyncRunStatus.running.value, trigger, run_type, now),
    )
    await db.commit()
    return run_id


async def _finish_sync_run(
    run_id: str,
    status: SyncRunStatus,
    stats: dict | None = None,
    error_message: str | None = None,
    logs: list[str] | None = None,
    users_processed: list[str] | None = None,
) -> None:
    """Update a sync_run with final status and stats."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """UPDATE sync_runs
           SET finished_at = ?, status = ?, stats_json = ?, error_message = ?,
               logs_json = ?, users_processed = ?
           WHERE id = ?""",
        (
            now,
            status.value,
            json.dumps(stats) if stats else None,
            error_message,
            json.dumps(logs) if logs else None,
            json.dumps(users_processed) if users_processed else None,
            run_id,
        ),
    )
    await db.commit()


async def run_sync(trigger: str = "scheduled", user_id: str | None = None) -> SyncRun:
    """Run a full Plaud sync cycle for all enabled users (or a specific user).

    Steps for each user:
    1. Fetch recording list from Plaud API
    2. Filter out already-imported and deleted recordings
    3. Download, upload to blob storage, and submit for transcription

    Args:
        trigger: "scheduled" or "manual".
        user_id: Optional user ID to sync only that user (for manual triggers).

    Returns:
        The SyncRun record for this execution.
    """
    global _sync_running

    if _sync_running:
        raise HTTPException(
            status_code=409,
            detail="A sync is already in progress",
        )

    _sync_running = True
    settings = get_settings()
    run_id = await _create_sync_run(trigger, run_type="plaud_sync")
    run_logger = RunLogger(run_id)
    run_logs: list[str] = []
    stats = {"users": 0, "new_recordings": 0, "skipped": 0, "errors": 0}
    users_processed: list[str] = []

    try:
        await run_logger.info("Starting Plaud sync (trigger=%s)" % trigger)
        db = await get_db()
        if user_id:
            user_rows = await db.execute_fetchall(
                "SELECT id, plaud_token FROM users WHERE id = ? AND plaud_enabled = 1 AND plaud_token IS NOT NULL",
                (user_id,),
            )
        else:
            user_rows = await db.execute_fetchall(
                "SELECT id, plaud_token FROM users WHERE plaud_enabled = 1 AND plaud_token IS NOT NULL"
            )

        await run_logger.info("Found %d enabled user(s)" % len(user_rows))

        for user_row in user_rows:
            user = dict(user_row)
            user_id = user["id"]
            token = user["plaud_token"]
            stats["users"] += 1
            users_processed.append(user_id)

            try:
                await _sync_user(user_id, token, stats, run_logs, settings, run_logger)
            except Exception as exc:
                stats["errors"] += 1
                msg = f"Error syncing user {user_id}: {exc}"
                logger.exception(msg)
                run_logs.append(msg)
                await run_logger.error(msg)

        status = SyncRunStatus.completed
        error_message = None
        await run_logger.info(
            "Sync completed: %d new, %d skipped, %d errors"
            % (stats["new_recordings"], stats["skipped"], stats["errors"])
        )

    except Exception as exc:
        status = SyncRunStatus.failed
        error_message = str(exc)
        logger.exception("Sync run %s failed: %s", run_id, exc)
        await run_logger.error("Sync failed: %s" % exc)
    finally:
        _sync_running = False

    await _finish_sync_run(
        run_id, status, stats, error_message, run_logs, users_processed
    )

    # Return the sync run
    rows = await (await get_db()).execute_fetchall(
        "SELECT * FROM sync_runs WHERE id = ?", (run_id,)
    )
    return SyncRun(**dict(rows[0]))


async def _sync_user(
    user_id: str,
    token: str,
    stats: dict,
    run_logs: list[str],
    settings,
    run_logger: RunLogger | None = None,
) -> None:
    """Sync recordings for a single user."""
    db = await get_db()

    # Fetch recordings from Plaud
    plaud_recordings = await plaud_client.fetch_recordings(token)
    run_logs.append(f"User {user_id}: fetched {len(plaud_recordings)} from Plaud")
    if run_logger:
        await run_logger.info(f"User {user_id[:8]}: fetched {len(plaud_recordings)} recordings from Plaud")

    # Get already-imported plaud_ids
    existing_rows = await db.execute_fetchall(
        "SELECT plaud_id FROM recordings WHERE user_id = ? AND plaud_id IS NOT NULL",
        (user_id,),
    )
    existing_ids = {dict(r)["plaud_id"] for r in existing_rows}

    # Get deleted plaud_ids
    deleted_rows = await db.execute_fetchall(
        "SELECT plaud_id FROM deleted_plaud_ids WHERE user_id = ?",
        (user_id,),
    )
    deleted_ids = {dict(r)["plaud_id"] for r in deleted_rows}

    blocked_ids = existing_ids | deleted_ids

    # Categorize recordings
    new_recordings = [r for r in plaud_recordings if r.id not in blocked_ids]
    already_imported = len(existing_ids & {r.id for r in plaud_recordings})
    previously_deleted = len(deleted_ids & {r.id for r in plaud_recordings})

    # Apply max_recordings_per_sync limit if set
    if settings.max_recordings_per_sync and len(new_recordings) > settings.max_recordings_per_sync:
        limited_to = settings.max_recordings_per_sync
        new_recordings = new_recordings[:limited_to]
    else:
        limited_to = None

    # Log clear breakdown
    summary = f"User {user_id[:8]}: {len(plaud_recordings)} from Plaud — {already_imported} already imported, {previously_deleted} previously deleted"
    if new_recordings:
        summary += f", {len(new_recordings)} to process"
        if limited_to:
            summary += f" (limited to {limited_to})"
    else:
        summary += ", nothing new"
    run_logs.append(summary)
    if run_logger:
        await run_logger.info(summary)
    stats["skipped"] += already_imported + previously_deleted

    for audio_file in new_recordings:
        try:
            was_processed = await _process_new_recording(user_id, token, audio_file, run_logger)
            if was_processed:
                stats["new_recordings"] += 1
                run_logs.append(f"Processed: {audio_file.filename}")
            else:
                stats["skipped"] += 1
                if run_logger:
                    await run_logger.info(f"Skipped (duplicate): {audio_file.filename}")
        except Exception as exc:
            if "UNIQUE constraint failed: recordings.plaud_id" in str(exc):
                stats["skipped"] += 1
                if run_logger:
                    await run_logger.info(f"Skipped (duplicate): {audio_file.filename}")
            else:
                stats["errors"] += 1
                msg = f"Error processing {audio_file.id}: {exc}"
                logger.exception(msg)
                run_logs.append(msg)
                if run_logger:
                    await run_logger.error(f"Error: {audio_file.filename}: {exc}")

    # Update last sync timestamp
    await db.execute(
        "UPDATE users SET plaud_last_sync = datetime('now') WHERE id = ?",
        (user_id,),
    )
    await db.commit()


async def _transcode_to_mp3(input_path: Path, output_path: Path) -> Path:
    """Transcode an audio file to MP3 128kbps using ffmpeg.

    Runs in a thread to avoid blocking the event loop.
    """
    import asyncio
    import subprocess

    def _run_ffmpeg():
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-codec:a", "libmp3lame", "-b:a", "128k",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:500]}")
        return output_path

    return await asyncio.to_thread(_run_ffmpeg)


async def _process_new_recording(
    user_id: str,
    token: str,
    audio_file: plaud_client.AudioFile,
    run_logger: RunLogger | None = None,
) -> bool:
    """Download a Plaud recording, transcode, upload to blob, and submit for transcription.

    Returns True if the recording was actually processed, False if skipped (already exists).
    """
    settings = get_settings()
    db = await get_db()

    # Double-check plaud_id doesn't already exist
    existing = await db.execute_fetchall(
        "SELECT id FROM recordings WHERE plaud_id = ?", (audio_file.id,)
    )
    if existing:
        return False

    if run_logger:
        await run_logger.info(f"Downloading: {audio_file.filename}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download from Plaud
        local_path = await plaud_client.download_file(token, audio_file, tmpdir)

        # Transcode to MP3
        mp3_path = Path(tmpdir) / f"{audio_file.id}.mp3"
        try:
            await _transcode_to_mp3(local_path, mp3_path)
            upload_path = mp3_path
            extension = ".mp3"
        except Exception as exc:
            logger.warning(
                "ffmpeg transcode failed for %s, uploading original: %s",
                audio_file.id, exc,
            )
            upload_path = local_path
            extension = local_path.suffix

        # Build blob path
        blob_name = f"{user_id}/{audio_file.id}{extension}"

        # Upload to local/Azure storage (for playback)
        await storage_service.upload_file(upload_path, blob_name)

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
                logger.info(f"Also uploaded to Azure Blob for transcription: {blob_name}")

    # Build Plaud metadata
    plaud_meta = PlaudMetadata(
        plaud_id=audio_file.id,
        original_timestamp=audio_file.start_time,
        filename=audio_file.filename,
        file_size=audio_file.filesize,
        duration_ms=audio_file.duration,
        file_type=audio_file.filetype,
        synced_at=datetime.now(timezone.utc).isoformat(),
    )

    # Determine initial status based on whether speech services are configured
    initial_status = RecordingStatus.transcribing if settings.speech_enabled else RecordingStatus.pending

    # Create recording in DB
    recording = await recording_service.create_recording(
        user_id=user_id,
        original_filename=audio_file.filename,
        source=RecordingSource.plaud,
        file_path=blob_name,
        duration_seconds=audio_file.duration_seconds,
        recorded_at=audio_file.recording_datetime.isoformat(),
        plaud_id=audio_file.id,
        plaud_metadata_json=plaud_meta.model_dump_json(),
        status=initial_status,
    )

    # Submit for transcription if speech services are configured
    # When using local storage, we also upload to Azure Blob above so SAS URL works
    if settings.speech_enabled and settings.azure_storage_connection_string:
        if run_logger:
            await run_logger.info(f"Submitting for transcription: {audio_file.filename}")
        # Always generate Azure SAS URL for speech (not local URL)
        audio_url = storage_service._azure_sas_url(blob_name, 24, settings)
        speech = SpeechClient()
        transcription_id = await speech.create_transcription(
            audio_url=audio_url,
            display_name=audio_file.filename,
        )

        db = await get_db()
        await db.execute(
            """UPDATE recordings
               SET provider_job_id = ?, processing_started = datetime('now')
               WHERE id = ?""",
            (transcription_id, recording.id),
        )
        await db.commit()
        if run_logger:
            await run_logger.info(f"Transcription submitted: {audio_file.filename} (job={transcription_id[:8]})")

    if run_logger:
        await run_logger.info(f"Processed: {audio_file.filename}")
    return True


async def poll_pending_transcriptions() -> list[str]:
    """Check status of all pending transcription jobs and process completed ones.

    Returns:
        List of recording IDs that completed processing.
    """
    settings = get_settings()
    if not settings.speech_enabled:
        return []

    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, user_id, provider_job_id, original_filename
           FROM recordings
           WHERE status = ? AND provider_job_id IS NOT NULL""",
        (RecordingStatus.transcribing.value,),
    )

    if not rows:
        return []

    # Create a run for transcription polling
    run_id = await _create_sync_run("scheduled", run_type="transcription_poll")
    run_logger = RunLogger(run_id)

    speech = SpeechClient()
    completed: list[str] = []

    await run_logger.info("Polling %d pending transcription(s)" % len(rows))

    for row in rows:
        r = dict(row)
        recording_id = r["id"]
        job_id = r["provider_job_id"]

        try:
            transcription = await speech.get_transcription(job_id)
            status = transcription.get("status", "")

            if status == "Succeeded":
                await run_logger.info(
                    "Transcription complete: %s" % (r["original_filename"] or recording_id[:8])
                )
                await _handle_transcription_complete(
                    recording_id, r["user_id"], job_id, speech, run_logger
                )
                completed.append(recording_id)

            elif status == "Failed":
                error = transcription.get("properties", {}).get(
                    "error", {}
                ).get("message", "Transcription failed")
                await db.execute(
                    """UPDATE recordings
                       SET status = ?, status_message = ?, updated_at = datetime('now')
                       WHERE id = ?""",
                    (RecordingStatus.failed.value, error, recording_id),
                )
                await db.commit()
                logger.warning("Transcription failed for %s: %s", recording_id, error)
                await run_logger.error(
                    "Transcription failed: %s — %s" % (r["original_filename"] or recording_id[:8], error)
                )

            else:
                await run_logger.debug(
                    "Still %s: %s" % (status, r["original_filename"] or recording_id[:8])
                )

        except Exception as exc:
            logger.exception("Error polling transcription for %s: %s", recording_id, exc)
            await run_logger.error("Error polling %s: %s" % (recording_id[:8], exc))

    poll_status = SyncRunStatus.completed
    await run_logger.info("Poll complete: %d transcription(s) finished" % len(completed))
    await _finish_sync_run(run_id, poll_status, {"completed": len(completed), "polled": len(rows)})

    return completed


async def _handle_transcription_complete(
    recording_id: str,
    user_id: str,
    job_id: str,
    speech: SpeechClient,
    run_logger: RunLogger | None = None,
) -> None:
    """Process a completed transcription: download result, run AI enrichment."""
    db = await get_db()

    # Update status to processing (AI post-processing)
    await db.execute(
        "UPDATE recordings SET status = ? WHERE id = ?",
        (RecordingStatus.processing.value, recording_id),
    )
    await db.commit()

    # Download transcript content
    content = await speech.get_transcript_content(job_id)

    # Parse transcript
    transcript_text, diarized_text = _parse_transcript(content)
    token_count = len(transcript_text) // 4 if transcript_text else None

    # Extract speaker mapping skeleton from diarization
    speaker_mapping = _extract_speaker_mapping(content)

    # Run AI enrichment (title + description)
    title = None
    description = None
    settings = get_settings()
    if settings.ai_enabled and diarized_text:
        if run_logger:
            await run_logger.info("Running AI enrichment for %s" % recording_id[:8])
        try:
            result = await ai_service.generate_title_description(diarized_text)
            title = result.get("title")
            description = result.get("description")
            if run_logger and title:
                await run_logger.info("AI title: %s" % title)
        except Exception as exc:
            logger.warning("AI title/description failed for %s: %s", recording_id, exc)
            if run_logger:
                await run_logger.warning("AI enrichment failed for %s: %s" % (recording_id[:8], exc))

    # Update recording with all results
    await db.execute(
        """UPDATE recordings
           SET status = ?, transcript_text = ?, diarized_text = ?,
               transcript_json = ?, token_count = ?, speaker_mapping = ?,
               title = COALESCE(?, title), description = COALESCE(?, description),
               processing_completed = datetime('now'), updated_at = datetime('now')
           WHERE id = ?""",
        (
            RecordingStatus.ready.value,
            transcript_text,
            diarized_text,
            json.dumps(content),
            token_count,
            json.dumps(speaker_mapping) if speaker_mapping else None,
            title,
            description,
            recording_id,
        ),
    )
    await db.commit()

    # Generate search summary (non-fatal)
    if settings.ai_enabled and (diarized_text or transcript_text):
        try:
            from app.services import search_summary_service
            await search_summary_service.generate_search_summary(recording_id, user_id)
            if run_logger:
                await run_logger.info("Search summary generated for %s" % recording_id[:8])
        except Exception as exc:
            logger.warning("Search summary generation failed for %s: %s", recording_id, exc)
            if run_logger:
                await run_logger.warning("Search summary failed for %s: %s" % (recording_id[:8], exc))

    # Clean up the transcription job from Azure
    try:
        await speech.delete_transcription(job_id)
    except Exception:
        pass  # Non-critical cleanup

    # Speaker identification (if enabled and recording has audio)
    if settings.speaker_id_enabled:
        if run_logger:
            await run_logger.info("Starting speaker identification for %s" % recording_id[:8])
        try:
            from app.services import speaker_processor

            async with speaker_processor._speaker_id_lock:
                identified = await speaker_processor.process_recording(
                    user_id, recording_id, run_logger=run_logger
                )
                if identified:
                    logger.info("Speaker identification completed for %s", recording_id)
                    if run_logger:
                        await run_logger.info("Speaker identification completed for %s" % recording_id[:8])

                    # Re-rate other recordings against updated profiles
                    rerated = await speaker_processor.rerate_speakers(user_id)
                    if rerated:
                        logger.info("Re-rated speakers in %d recordings for user %s", rerated, user_id)
                        if run_logger:
                            await run_logger.info("Re-rated speakers in %d recording(s)" % rerated)
        except Exception as exc:
            logger.warning(
                "Speaker identification failed for %s (non-fatal): %s",
                recording_id, exc,
            )
            if run_logger:
                await run_logger.warning("Speaker ID failed for %s: %s" % (recording_id[:8], exc))

    logger.info("Completed processing for recording %s", recording_id)


def _parse_transcript(content: dict) -> tuple[str, str]:
    """Parse Azure Speech transcript JSON into plain text and diarized text.

    Returns:
        Tuple of (plain_text, diarized_text).
    """
    combined = content.get("combinedRecognizedPhrases", [])
    recognized = content.get("recognizedPhrases", [])

    # Plain text from combined phrases
    plain_parts = [p.get("display", "") for p in combined]
    plain_text = " ".join(plain_parts).strip()

    # Diarized text from recognized phrases
    diarized_parts: list[str] = []
    current_speaker: int | None = None

    for phrase in sorted(recognized, key=lambda p: p.get("offsetInTicks", 0)):
        speaker = phrase.get("speaker", 0)
        best = phrase.get("nBest", [{}])[0]
        display = best.get("display", "")

        if not display:
            continue

        if speaker != current_speaker:
            current_speaker = speaker
            diarized_parts.append(f"\nSpeaker {speaker}: {display}")
        else:
            diarized_parts.append(f" {display}")

    diarized_text = "".join(diarized_parts).strip()

    return plain_text, diarized_text


def _extract_speaker_mapping(content: dict) -> dict:
    """Extract a skeleton speaker mapping from diarization data.

    Creates an entry for each unique speaker label found in the transcript.
    """
    recognized = content.get("recognizedPhrases", [])
    speakers = set()

    for phrase in recognized:
        speaker = phrase.get("speaker")
        if speaker is not None:
            speakers.add(speaker)

    mapping = {}
    for speaker_num in sorted(speakers):
        label = f"Speaker {speaker_num}"
        mapping[label] = {
            "participantId": None,
            "displayName": None,
            "confidence": None,
            "manuallyVerified": False,
            "identificationStatus": None,
        }

    return mapping


async def get_sync_runs(
    page: int = 1,
    per_page: int = 20,
    status_filter: str | None = None,
    type_filter: str | None = None,
) -> PaginatedResponse:
    """List sync runs with pagination.

    Args:
        page: 1-based page number.
        per_page: Results per page.
        status_filter: Optional status to filter by.
        type_filter: Optional run type to filter by.

    Returns:
        PaginatedResponse containing SyncRunSummary items.
    """
    db = await get_db()
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    conditions: list[str] = []
    params: list = []
    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_rows = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM sync_runs {where}", params
    )
    total = dict(count_rows[0])["cnt"] if count_rows else 0

    rows = await db.execute_fetchall(
        f"""SELECT id, started_at, finished_at, status, trigger, type,
                   stats_json, error_message, users_processed, created_at
            FROM sync_runs {where}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    )

    data = [SyncRunSummary(**dict(r)) for r in rows]

    return PaginatedResponse(data=data, total=total, page=page, per_page=per_page)


async def get_sync_run(run_id: str) -> SyncRunDetail:
    """Get a single sync run with full logs.

    Raises:
        HTTPException 404 if not found.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM sync_runs WHERE id = ?", (run_id,)
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Sync run not found")

    return SyncRunDetail(**dict(rows[0]))
