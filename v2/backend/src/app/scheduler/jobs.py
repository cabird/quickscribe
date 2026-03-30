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

    scheduler.start()
    logger.info(
        "Scheduler started — sync every %d min, polling every 5 min",
        settings.sync_interval_minutes,
    )


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
