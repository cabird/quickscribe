"""Tests for scheduled maintenance jobs.

Covers: run history pruning (sync_runs + cascaded run_logs retention).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import aiosqlite
import pytest

from app.config import Settings
from app.scheduler.jobs import prune_run_history_job


def _iso(days_ago: float) -> str:
    """ISO-8601 UTC timestamp N days in the past, matching production format."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


async def _add_run(db: aiosqlite.Connection, started_at: str, n_logs: int = 2) -> str:
    run_id = f"run-{uuid.uuid4()}"
    await db.execute(
        """INSERT INTO sync_runs (id, started_at, status, trigger, created_at)
           VALUES (?, ?, 'success', 'scheduled', ?)""",
        (run_id, started_at, started_at),
    )
    for i in range(n_logs):
        await db.execute(
            "INSERT INTO run_logs (run_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
            (run_id, started_at, "info", f"log {i}"),
        )
    await db.commit()
    return run_id


async def _counts(db: aiosqlite.Connection) -> tuple[int, int]:
    rows = await db.execute_fetchall(
        "SELECT (SELECT COUNT(*) FROM sync_runs) AS runs,"
        " (SELECT COUNT(*) FROM run_logs) AS logs"
    )
    r = dict(rows[0])
    return r["runs"], r["logs"]


def _settings(retention_days: int) -> Settings:
    return Settings(
        database_path=":memory:",
        auth_disabled=True,
        azure_storage_connection_string="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        speech_services_key="",
        speech_services_region="",
        run_history_retention_days=retention_days,
    )


class TestPruneRunHistory:
    async def test_deletes_only_rows_older_than_retention(
        self, test_db: aiosqlite.Connection
    ):
        old_id = await _add_run(test_db, _iso(45))
        edge_id = await _add_run(test_db, _iso(31))
        recent_id = await _add_run(test_db, _iso(2))

        with patch("app.scheduler.jobs.get_settings", return_value=_settings(30)), \
             patch("app.database._db", test_db):
            await prune_run_history_job()

        rows = await test_db.execute_fetchall("SELECT id FROM sync_runs")
        remaining = {dict(r)["id"] for r in rows}
        assert remaining == {recent_id}
        assert old_id not in remaining
        assert edge_id not in remaining

    async def test_cascade_removes_run_logs(self, test_db: aiosqlite.Connection):
        await _add_run(test_db, _iso(60), n_logs=5)
        await _add_run(test_db, _iso(1), n_logs=3)
        assert await _counts(test_db) == (2, 8)

        with patch("app.scheduler.jobs.get_settings", return_value=_settings(30)), \
             patch("app.database._db", test_db):
            await prune_run_history_job()

        assert await _counts(test_db) == (1, 3)

        orphans = await test_db.execute_fetchall(
            "SELECT COUNT(*) AS n FROM run_logs"
            " WHERE run_id NOT IN (SELECT id FROM sync_runs)"
        )
        assert dict(orphans[0])["n"] == 0

    async def test_is_idempotent(self, test_db: aiosqlite.Connection):
        await _add_run(test_db, _iso(90))
        await _add_run(test_db, _iso(3))

        with patch("app.scheduler.jobs.get_settings", return_value=_settings(30)), \
             patch("app.database._db", test_db):
            await prune_run_history_job()
            after_first = await _counts(test_db)
            await prune_run_history_job()
            after_second = await _counts(test_db)

        assert after_first == after_second == (1, 2)

    @pytest.mark.parametrize("retention", [0, -1])
    async def test_disabled_when_retention_not_positive(
        self, test_db: aiosqlite.Connection, retention: int
    ):
        await _add_run(test_db, _iso(365))
        before = await _counts(test_db)

        with patch("app.scheduler.jobs.get_settings", return_value=_settings(retention)), \
             patch("app.database._db", test_db):
            await prune_run_history_job()

        assert await _counts(test_db) == before

    async def test_handles_null_started_at_via_created_at(
        self, test_db: aiosqlite.Connection
    ):
        """started_at is NOT NULL in schema, but COALESCE must not drop rows."""
        await _add_run(test_db, _iso(45))

        with patch("app.scheduler.jobs.get_settings", return_value=_settings(30)), \
             patch("app.database._db", test_db):
            await prune_run_history_job()

        assert await _counts(test_db) == (0, 0)
