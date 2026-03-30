"""RunLogger — writes structured log entries to the run_logs table in real time.

Each log call commits immediately so polling clients see new entries right away.
Includes a sync adapter for use inside asyncio.to_thread() contexts.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger(__name__)


class RunLogger:
    """Logger that writes each message to the run_logs table immediately."""

    def __init__(self, run_id: str):
        self.run_id = run_id

    async def info(self, message: str) -> None:
        logger.info("[run:%s] %s", self.run_id[:8], message)
        await self._log("info", message)

    async def warning(self, message: str) -> None:
        logger.warning("[run:%s] %s", self.run_id[:8], message)
        await self._log("warning", message)

    async def error(self, message: str) -> None:
        logger.error("[run:%s] %s", self.run_id[:8], message)
        await self._log("error", message)

    async def debug(self, message: str) -> None:
        logger.debug("[run:%s] %s", self.run_id[:8], message)
        await self._log("debug", message)

    async def _log(self, level: str, message: str) -> None:
        """Insert a log row and commit immediately."""
        try:
            db = await get_db()
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO run_logs (run_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
                (self.run_id, now, level, message),
            )
            await db.commit()
        except Exception as exc:
            logger.warning("Failed to write run log: %s", exc)

    def sync_adapter(self) -> SyncRunLogger:
        """Return a synchronous wrapper for use in threaded contexts.

        The sync adapter uses asyncio.run_coroutine_threadsafe() to post
        log entries back to the event loop that owns the database connection.
        """
        loop = asyncio.get_event_loop()
        return SyncRunLogger(self, loop)


class SyncRunLogger:
    """Synchronous facade for RunLogger, safe to call from worker threads."""

    def __init__(self, async_logger: RunLogger, loop: asyncio.AbstractEventLoop):
        self._async_logger = async_logger
        self._loop = loop

    def _post(self, coro):
        """Schedule a coroutine on the event loop and wait for it."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.result(timeout=5)

    def info(self, message: str) -> None:
        self._post(self._async_logger.info(message))

    def warning(self, message: str) -> None:
        self._post(self._async_logger.warning(message))

    def error(self, message: str) -> None:
        self._post(self._async_logger.error(message))

    def debug(self, message: str) -> None:
        self._post(self._async_logger.debug(message))
