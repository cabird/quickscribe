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

    from fastapi import HTTPException

    logger.info("Starting scheduled Plaud sync")
    try:
        await sync_service.run_sync(trigger="scheduled")
    except HTTPException as exc:
        # e.g. a manual sync is already running
        logger.info("Scheduled Plaud sync skipped: %s", exc.detail)
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


async def prune_run_history_job() -> None:
    """Delete sync_runs (and cascaded run_logs) older than the retention window.

    Without this, sync_runs grows by ~96 rows/day forever, which also inflates
    every hourly Litestream snapshot of the database.

    Done as a single statement and a single commit rather than in batches. The
    app shares one aiosqlite connection across all callers, so awaiting between
    a DELETE and its commit would let an unrelated coroutine's in-flight write
    get committed by this job (and vice versa). One statement keeps that window
    as small as every other writer in the app. Measured against a copy of the
    production database, deleting a full 22k-row backlog plus its cascaded
    run_logs took ~1.6s -- well inside busy_timeout -- and steady-state runs
    only remove ~96 rows.
    """
    from app.database import get_db

    settings = get_settings()
    retention_days = settings.run_history_retention_days
    if retention_days <= 0:
        logger.info("Run history pruning disabled (retention_days=%d)", retention_days)
        return

    try:
        db = await get_db()
        cursor = await db.execute(
            """DELETE FROM sync_runs
               WHERE julianday(COALESCE(started_at, created_at))
                     < julianday('now', ?)""",
            (f"-{retention_days} days",),
        )
        deleted = cursor.rowcount or 0
        await db.commit()

        if deleted:
            rows = await db.execute_fetchall(
                "SELECT (SELECT COUNT(*) FROM sync_runs) AS runs,"
                " (SELECT COUNT(*) FROM run_logs) AS logs"
            )
            remaining = dict(rows[0])
            logger.info(
                "Run history pruned: %d sync_runs older than %d days deleted "
                "(%d runs, %d run_logs remaining)",
                deleted, retention_days,
                remaining["runs"], remaining["logs"],
            )
        else:
            logger.info(
                "Run history pruning: nothing older than %d days", retention_days
            )
    except Exception:
        logger.exception("Run history pruning job failed")


def start_scheduler() -> None:
    """Register jobs and start the scheduler."""
    settings = get_settings()

    if settings.plaud_enabled:
        scheduler.add_job(
            plaud_sync_job,
            "interval",
            minutes=settings.sync_interval_minutes,
            id="plaud_sync",
            replace_existing=True,
        )
    else:
        logger.warning("Plaud sync disabled on this server (PLAUD_ENABLED=false)")

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

    scheduler.add_job(
        prune_run_history_job,
        "interval",
        hours=24,
        id="prune_run_history",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(
        "Scheduler started — Plaud sync %s, polling every 5 min, "
        "meeting notes every 60 min, run-history pruning every 24h "
        "(retention %d days)",
        f"every {settings.sync_interval_minutes} min" if settings.plaud_enabled else "disabled",
        settings.run_history_retention_days,
    )


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
