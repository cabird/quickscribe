"""APScheduler job definitions for background processing."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def plaud_sync_job() -> None:
    """Sync recordings from Plaud for all enabled users."""
    from app.services import sync_service

    logger.info("Starting scheduled Plaud sync")
    try:
        await sync_service.run_sync(trigger="scheduled")
    except Exception:
        logger.exception("Plaud sync job failed")


async def poll_transcriptions_job() -> None:
    """Poll Azure Speech Services for completed transcriptions."""
    from app.services import sync_service

    logger.info("Polling for pending transcriptions")
    try:
        await sync_service.poll_pending_transcriptions()
    except Exception:
        logger.exception("Transcription polling job failed")


async def refresh_meeting_notes_job() -> None:
    """Generate or regenerate meeting notes for recordings that need them."""
    from app.database import get_db
    from app.services import meeting_notes_service

    logger.info("Starting meeting notes refresh job")
    try:
        db = await get_db()
        rows = await db.execute_fetchall(
            """SELECT id, user_id FROM recordings
               WHERE status = 'ready'
                 AND (diarized_text IS NOT NULL OR transcript_text IS NOT NULL)
                 AND (
                   meeting_notes IS NULL
                   OR (speaker_mapping_updated_at IS NOT NULL
                       AND (meeting_notes_generated_at IS NULL
                            OR meeting_notes_generated_at < speaker_mapping_updated_at))
                 )
               ORDER BY COALESCE(recorded_at, created_at) DESC
               LIMIT 10"""
        )

        if not rows:
            logger.info("Meeting notes refresh: no recordings need notes")
            return

        generated = 0
        failed = 0
        for row in rows:
            r = dict(row)
            try:
                result = await meeting_notes_service.generate_meeting_notes(
                    r["id"], r["user_id"]
                )
                if result:
                    generated += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Meeting notes refresh failed for %s: %s", r["id"][:8], exc
                )

        logger.info(
            "Meeting notes refresh complete: %d generated, %d failed",
            generated, failed,
        )
    except Exception:
        logger.exception("Meeting notes refresh job failed")


def start_scheduler() -> None:
    """Register jobs and start the scheduler."""
    settings = get_settings()

    scheduler.add_job(
        plaud_sync_job,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="plaud_sync",
        replace_existing=True,
    )

    scheduler.add_job(
        poll_transcriptions_job,
        "interval",
        minutes=5,
        id="poll_transcriptions",
        replace_existing=True,
    )

    scheduler.add_job(
        refresh_meeting_notes_job,
        "interval",
        minutes=60,
        id="refresh_meeting_notes",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(
        "Scheduler started — sync every %d min, polling every 5 min, meeting notes every 60 min",
        settings.sync_interval_minutes,
    )


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
