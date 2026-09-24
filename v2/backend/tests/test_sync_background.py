"""Tests for manually triggered sync/poll runs.

Covers: runs start in the background and return their run ID immediately,
the one-at-a-time guards, manual polls always recording a run, and the
per-run poll counters shown on job cards.

These call the service functions directly (like test_scheduler_jobs.py)
rather than going through the HTTP client fixture.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services import sync_service


def _settings(speech: bool = True, plaud: bool = True) -> Settings:
    return Settings(
        database_path=":memory:",
        auth_disabled=True,
        azure_storage_connection_string="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        speech_services_key="key" if speech else "",
        speech_services_region="westus" if speech else "",
        plaud_enabled=plaud,
    )


@pytest.fixture
async def env(test_db: aiosqlite.Connection):
    """Point sync_service (and RunLogger) at the test DB with speech enabled."""
    with (
        patch("app.database._db", test_db),
        patch("app.services.sync_service.get_settings", return_value=_settings()),
    ):
        yield test_db
        # Let spawned runs finish while the DB is still open
        await asyncio.gather(*sync_service._background_tasks, return_exceptions=True)
    # Never leak a claimed slot into the next test
    sync_service._sync_running = False
    sync_service._poll_running = False


async def _run_row(db: aiosqlite.Connection, run_id: str) -> dict:
    rows = await db.execute_fetchall("SELECT * FROM sync_runs WHERE id = ?", (run_id,))
    return dict(rows[0])


async def _wait_finished(db: aiosqlite.Connection, run_id: str) -> dict:
    for _ in range(200):
        row = await _run_row(db, run_id)
        if row["status"] != "running":
            return row
        await asyncio.sleep(0.01)
    raise AssertionError(f"run {run_id} never finished")


async def _add_transcribing(db: aiosqlite.Connection, user_id: str, name: str) -> str:
    rec_id = f"rec-{uuid.uuid4()}"
    await db.execute(
        """INSERT INTO recordings (id, user_id, original_filename, source, status, provider_job_id)
           VALUES (?, ?, ?, 'upload', 'transcribing', ?)""",
        (rec_id, user_id, name, f"job-{name}"),
    )
    await db.commit()
    return rec_id


class TestManualSync:
    async def test_returns_run_id_before_work_finishes(self, env):
        gate = asyncio.Event()

        async def slow_execute(run_id, trigger, user_id):
            await gate.wait()
            sync_service._sync_running = False

        with patch.object(sync_service, "_execute_sync", slow_execute):
            # Must return while the work is still blocked on the gate
            run_id = await asyncio.wait_for(sync_service.start_sync(user_id="u1"), timeout=1)
            row = await _run_row(env, run_id)
            assert row["status"] == "running"
            assert row["trigger"] == "manual"
            assert row["type"] == "plaud_sync"

            with pytest.raises(HTTPException) as exc:
                await sync_service.start_sync(user_id="u1")
            assert exc.value.status_code == 409

            gate.set()
            await asyncio.gather(*sync_service._background_tasks)
        assert sync_service._sync_running is False

    async def test_background_sync_completes(self, env):
        # No Plaud-enabled users -> the run finishes immediately
        run_id = await sync_service.start_sync(user_id="nobody")
        row = await _wait_finished(env, run_id)
        assert row["status"] == "completed"
        assert json.loads(row["stats_json"])["new_recordings"] == 0
        assert sync_service._sync_running is False

    async def test_slot_released_if_run_row_cannot_be_created(self, env):
        with patch.object(
            sync_service, "_create_sync_run", AsyncMock(side_effect=RuntimeError("db"))
        ):
            with pytest.raises(RuntimeError):
                await sync_service.start_sync()
        assert sync_service._sync_running is False


class TestManualPoll:
    async def test_nothing_pending_still_records_a_run(self, env):
        run_id = await sync_service.start_poll()
        row = await _wait_finished(env, run_id)
        assert row["status"] == "completed"
        assert row["trigger"] == "manual"
        assert row["type"] == "transcription_poll"
        assert json.loads(row["stats_json"]) == {
            "polled": 0, "completed": 0, "failed": 0, "still_running": 0, "errors": 0,
        }
        logs = await env.execute_fetchall(
            "SELECT message FROM run_logs WHERE run_id = ?", (run_id,)
        )
        assert any("No pending transcriptions" in dict(r)["message"] for r in logs)
        assert sync_service._poll_running is False

    async def test_counts_completed_running_and_failed(self, env, test_user):
        done = await _add_transcribing(env, test_user.id, "done")
        await _add_transcribing(env, test_user.id, "busy")
        failed = await _add_transcribing(env, test_user.id, "bad")

        statuses = {
            "job-done": {"status": "Succeeded"},
            "job-busy": {"status": "Running"},
            "job-bad": {"status": "Failed", "properties": {"error": {"message": "nope"}}},
        }
        speech = AsyncMock()
        speech.get_transcription.side_effect = lambda job_id: statuses[job_id]

        with (
            patch.object(sync_service, "SpeechClient", return_value=speech),
            patch.object(sync_service, "_handle_transcription_complete", AsyncMock()) as handle,
        ):
            run_id = await sync_service.start_poll()
            row = await _wait_finished(env, run_id)

        assert json.loads(row["stats_json"]) == {
            "polled": 3, "completed": 1, "failed": 1, "still_running": 1, "errors": 0,
        }
        assert handle.await_args.args[0] == done
        rec = await env.execute_fetchall("SELECT status FROM recordings WHERE id = ?", (failed,))
        assert dict(rec[0])["status"] == "failed"

    async def test_second_poll_refused_while_running(self, env):
        gate = asyncio.Event()

        async def slow_execute(run_id, rows):
            await gate.wait()
            sync_service._poll_running = False
            return []

        with patch.object(sync_service, "_execute_poll", slow_execute):
            await asyncio.wait_for(sync_service.start_poll(), timeout=1)
            with pytest.raises(HTTPException) as exc:
                await sync_service.start_poll()
            assert exc.value.status_code == 409

            # The scheduled poll quietly skips instead of overlapping
            assert await sync_service.poll_pending_transcriptions() == []

            gate.set()
            await asyncio.gather(*sync_service._background_tasks)

    async def test_refused_when_speech_not_configured(self, env):
        with patch("app.services.sync_service.get_settings", return_value=_settings(speech=False)):
            with pytest.raises(HTTPException) as exc:
                await sync_service.start_poll()
        assert exc.value.status_code == 409
        assert sync_service._poll_running is False


    async def test_failure_marks_run_failed_and_releases_slot(self, env):
        with patch.object(
            sync_service, "_pending_transcriptions", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            run_id = await sync_service.start_poll()
            row = await _wait_finished(env, run_id)
        assert row["status"] == "failed"
        assert "boom" in row["error_message"]
        assert sync_service._poll_running is False


class TestScheduledPoll:
    async def test_idle_poll_records_no_run(self, env):
        assert await sync_service.poll_pending_transcriptions() == []
        rows = await env.execute_fetchall("SELECT COUNT(*) AS n FROM sync_runs")
        assert dict(rows[0])["n"] == 0

    async def test_manual_poll_refused_while_scheduled_poll_fetches(self, env, test_user):
        """The scheduled poll claims the slot before its first await."""
        await _add_transcribing(env, test_user.id, "busy")
        fetching = asyncio.Event()
        release = asyncio.Event()
        real_fetch = sync_service._pending_transcriptions

        async def slow_fetch():
            fetching.set()
            await release.wait()
            return await real_fetch()

        speech = AsyncMock()
        speech.get_transcription.return_value = {"status": "Running"}
        with (
            patch.object(sync_service, "_pending_transcriptions", slow_fetch),
            patch.object(sync_service, "SpeechClient", return_value=speech),
        ):
            scheduled = asyncio.create_task(sync_service.poll_pending_transcriptions())
            await fetching.wait()
            with pytest.raises(HTTPException) as exc:
                await sync_service.start_poll()
            assert exc.value.status_code == 409
            release.set()
            await scheduled

        assert sync_service._poll_running is False
        rows = await env.execute_fetchall("SELECT COUNT(*) AS n FROM sync_runs")
        assert dict(rows[0])["n"] == 1


class TestSyncDuplicateLogging:
    async def test_duplicates_logged_as_one_summary_line(self, env, test_user):
        from types import SimpleNamespace

        from app.services.run_logger import RunLogger

        files = [SimpleNamespace(id=f"p{i}", filename=f"2025-06-0{i}") for i in range(3)]
        run_id = await sync_service._create_sync_run("manual")
        stats = {"users": 0, "new_recordings": 0, "skipped": 0, "errors": 0}

        with (
            patch.object(sync_service.plaud_client, "fetch_recordings", AsyncMock(return_value=files)),
            patch.object(sync_service, "_process_new_recording", AsyncMock(return_value=False)),
        ):
            await sync_service._sync_user(
                test_user.id, "tok", stats, [], _settings(), RunLogger(run_id)
            )

        rows = await env.execute_fetchall("SELECT message FROM run_logs WHERE run_id = ?", (run_id,))
        messages = [dict(r)["message"] for r in rows]
        assert not any(m.startswith("Skipped (duplicate)") for m in messages)
        assert "Skipped 3 duplicate(s) already in the database" in messages
        assert stats["skipped"] == 3
