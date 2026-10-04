"""Tests for detailed minutes triggers: endpoint, post-transcription hook,
staleness refresh job and scheduler registration.

minutes_service.generate_minutes is always patched: no LLM calls.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services import minutes_service, sync_service


def _settings(ai: bool = True, speaker_id: bool = True) -> Settings:
    return Settings(
        database_path=":memory:",
        auth_disabled=True,
        azure_storage_connection_string="",
        azure_openai_endpoint="https://example.invalid/" if ai else "",
        azure_openai_api_key="key" if ai else "",
        speech_services_key="",
        speech_services_region="",
        speaker_id_enabled=speaker_id,
    )


@pytest.fixture(autouse=True)
async def _patch_db_singleton(test_db):
    """Services call get_db() directly; point the singleton at the test DB."""
    import app.database as db_mod

    original = db_mod._db
    db_mod._db = test_db
    yield
    db_mod._db = original


async def _drain_background():
    tasks = list(sync_service._background_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture(autouse=True)
async def _clean_background():
    yield
    await _drain_background()
    minutes_service._generating.clear()


TRANSCRIPT_JSON = json.dumps({
    "recognizedPhrases": [
        {"speaker": 1, "offsetMilliseconds": 0, "durationMilliseconds": 1000,
         "nBest": [{"display": "Hello."}]},
    ],
    "combinedRecognizedPhrases": [{"display": "Hello."}],
})


async def _insert(
    db,
    user_id,
    *,
    transcript_json: str | None = TRANSCRIPT_JSON,
    minutes: str | None = None,
    minutes_status: str | None = None,
    minutes_generated_at: str | None = None,
    speaker_mapping_updated_at: str | None = None,
    recorded_at: str | None = None,
    status: str = "ready",
    minutes_error: str | None = None,
) -> str:
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO recordings
           (id, user_id, title, original_filename, source, status,
            transcript_text, transcript_json, detailed_minutes,
            detailed_minutes_status, detailed_minutes_generated_at,
            speaker_mapping_updated_at, recorded_at, created_at, updated_at,
            detailed_minutes_error)
           VALUES (?, ?, 'Meeting', 'a.mp3', 'upload', ?, 'Hello.', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rec_id, user_id, status, transcript_json, minutes, minutes_status,
         minutes_generated_at, speaker_mapping_updated_at, recorded_at or now, now, now,
         minutes_error),
    )
    await db.commit()
    return rec_id


async def _status(db, rec_id):
    rows = await db.execute_fetchall(
        "SELECT detailed_minutes_status FROM recordings WHERE id = ?", (rec_id,)
    )
    return dict(rows[0])["detailed_minutes_status"]


# ---------------------------------------------------------------------------
# POST /api/recordings/{id}/generate-minutes
# ---------------------------------------------------------------------------


class TestGenerateMinutesEndpoint:
    # The endpoint imports get_settings inside the function body
    # (``from app.config import get_settings``), so patching
    # app.config.get_settings takes effect. If that import moves to module
    # level, patch app.routers.recordings.get_settings instead.

    async def test_202_spawns_task_and_detail_shows_generating(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id)
        gen = AsyncMock(return_value=True)
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
            assert resp.status_code == 202
            assert resp.json() == {"status": "generating"}

            detail = await client.get(f"/api/recordings/{rec_id}")
            assert detail.status_code == 200
            body = detail.json()
            assert body["detailed_minutes_status"] == "generating"
            assert "detailed_minutes" in body
            assert "detailed_minutes_meta" not in body

            await _drain_background()
        gen.assert_awaited_once_with(rec_id, test_user.id)

    async def test_detail_exposes_minutes_fields(self, client, test_db, test_user):
        rec_id = await _insert(
            test_db, test_user.id, minutes="# Minutes", minutes_status="ready",
            minutes_generated_at="2026-10-01 10:00:00",
        )
        body = (await client.get(f"/api/recordings/{rec_id}")).json()
        assert body["detailed_minutes"] == "# Minutes"
        assert body["detailed_minutes_status"] == "ready"
        assert body["detailed_minutes_generated_at"].startswith("2026-10-01T10:00:00")
        assert body["detailed_minutes_error"] is None

    async def test_404_for_other_users_recording(self, client_as_other, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id)
        gen = AsyncMock()
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client_as_other.post(f"/api/recordings/{rec_id}/generate-minutes")
        assert resp.status_code == 404
        assert await _status(test_db, rec_id) is None
        gen.assert_not_called()

    async def test_400_without_transcript_json(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id, transcript_json=None)
        gen = AsyncMock()
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
        assert resp.status_code == 400
        assert await _status(test_db, rec_id) is None
        gen.assert_not_called()

    async def test_503_when_ai_disabled(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id)
        gen = AsyncMock()
        with patch("app.config.get_settings", return_value=_settings(ai=False)), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
        assert resp.status_code == 503
        assert await _status(test_db, rec_id) is None
        gen.assert_not_called()

    async def test_409_when_in_process_guard_set(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id, minutes_status="ready")
        minutes_service._generating.add(rec_id)
        gen = AsyncMock()
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
        assert resp.status_code == 409
        assert await _status(test_db, rec_id) == "ready"
        gen.assert_not_called()

    async def test_409_when_status_generating(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id, minutes_status="generating",
                               minutes_error="earlier error")
        gen = AsyncMock()
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
        assert resp.status_code == 409
        gen.assert_not_called()
        rows = await test_db.execute_fetchall(
            """SELECT detailed_minutes_status, detailed_minutes_error
               FROM recordings WHERE id = ?""", (rec_id,)
        )
        row = dict(rows[0])
        assert row["detailed_minutes_status"] == "generating"
        assert row["detailed_minutes_error"] == "earlier error"

    async def test_404_for_nonexistent_recording(self, client):
        gen = AsyncMock()
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{uuid.uuid4()}/generate-minutes")
        assert resp.status_code == 404
        gen.assert_not_called()

    async def test_second_request_refused(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id)
        gen = AsyncMock(return_value=True)
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            first = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
            second = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
            await _drain_background()
        assert first.status_code == 202
        assert second.status_code == 409
        assert gen.await_count == 1

    async def test_failed_status_can_be_retried(self, client, test_db, test_user):
        rec_id = await _insert(test_db, test_user.id, minutes_status="failed",
                               minutes_error="RuntimeError: boom")
        gen = AsyncMock(return_value=True)
        with patch("app.config.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-minutes")
            assert resp.status_code == 202
            body = (await client.get(f"/api/recordings/{rec_id}")).json()
            assert body["detailed_minutes_status"] == "generating"
            assert body["detailed_minutes_error"] is None
            await _drain_background()
        gen.assert_awaited_once()

    async def test_shutdown_cancels_spawned_generation(self, test_db, test_user):
        started = asyncio.Event()

        async def slow(_rid, _uid):
            started.set()
            await asyncio.sleep(3600)

        with patch.object(minutes_service, "generate_minutes", slow):
            minutes_service.spawn_generation("rec", test_user.id)
            await started.wait()
            assert sync_service._background_tasks
            await sync_service.cancel_background_tasks()
        assert not sync_service._background_tasks


# ---------------------------------------------------------------------------
# _handle_transcription_complete hook
# ---------------------------------------------------------------------------


def _speech(content: dict | None = None) -> MagicMock:
    speech = MagicMock()
    speech.get_transcript_content = AsyncMock(
        return_value=content if content is not None else json.loads(TRANSCRIPT_JSON)
    )
    speech.delete_transcription = AsyncMock()
    return speech


class TestTranscriptionHook:
    async def _run(self, test_db, test_user, settings, spawn, content=None,
                   speaker_error: Exception | None = None):
        from app.services import (
            ai_service,
            meeting_notes_service,
            search_summary_service,
            speaker_processor,
        )

        rec_id = await _insert(test_db, test_user.id, transcript_json=None,
                               status="transcribing")
        order: list[str] = []

        async def process_recording(*_a, **_k):
            order.append("speaker_id")
            if speaker_error:
                raise speaker_error
            return False

        def spawn_side_effect(rid, uid):
            order.append("minutes")
            return spawn(rid, uid)

        with patch("app.services.sync_service.get_settings", return_value=settings), \
             patch.object(ai_service, "generate_title_description",
                          AsyncMock(return_value={"title": "T", "description": "D"})), \
             patch.object(search_summary_service, "generate_search_summary", AsyncMock()), \
             patch.object(meeting_notes_service, "generate_meeting_notes", AsyncMock()), \
             patch.object(speaker_processor, "process_recording", process_recording), \
             patch.object(minutes_service, "spawn_generation",
                          MagicMock(side_effect=spawn_side_effect)) as spawned:
            await sync_service._handle_transcription_complete(
                rec_id, test_user.id, "job-1", _speech(content)
            )
        return rec_id, order, spawned

    async def test_spawns_minutes_after_speaker_id(self, test_db, test_user):
        rec_id, order, spawned = await self._run(
            test_db, test_user, _settings(), MagicMock()
        )
        spawned.assert_called_once_with(rec_id, test_user.id)
        assert order == ["speaker_id", "minutes"]

    async def test_runs_generation_in_background(self, test_db, test_user):
        gen = AsyncMock(return_value=True)
        with patch.object(minutes_service, "generate_minutes", gen):
            rec_id, _order, _ = await self._run(
                test_db, test_user, _settings(),
                minutes_service.spawn_generation,
            )
            await _drain_background()
        gen.assert_awaited_once_with(rec_id, test_user.id)

    async def test_not_spawned_when_ai_disabled(self, test_db, test_user):
        _rec_id, order, spawned = await self._run(
            test_db, test_user, _settings(ai=False), MagicMock()
        )
        spawned.assert_not_called()
        assert "minutes" not in order

    async def test_spawned_when_speaker_id_disabled(self, test_db, test_user):
        rec_id, order, spawned = await self._run(
            test_db, test_user, _settings(speaker_id=False), MagicMock()
        )
        spawned.assert_called_once_with(rec_id, test_user.id)
        assert order == ["minutes"]

    async def test_not_spawned_for_silent_recording(self, test_db, test_user):
        _rec_id, order, spawned = await self._run(
            test_db, test_user, _settings(), MagicMock(),
            content={"recognizedPhrases": [], "combinedRecognizedPhrases": []},
        )
        spawned.assert_not_called()
        assert order == ["speaker_id"]

    async def test_spawned_even_if_speaker_id_raises(self, test_db, test_user):
        rec_id, order, spawned = await self._run(
            test_db, test_user, _settings(), MagicMock(),
            speaker_error=RuntimeError("speaker id down"),
        )
        spawned.assert_called_once_with(rec_id, test_user.id)
        assert order == ["speaker_id", "minutes"]

    async def test_spawn_failure_does_not_break_transcription(self, test_db, test_user):
        rec_id, _order, spawned = await self._run(
            test_db, test_user, _settings(),
            MagicMock(side_effect=RuntimeError("boom")),
        )
        spawned.assert_called_once()
        rows = await test_db.execute_fetchall(
            "SELECT status, transcript_json FROM recordings WHERE id = ?", (rec_id,)
        )
        row = dict(rows[0])
        assert row["status"] == "ready"
        assert row["transcript_json"]


# ---------------------------------------------------------------------------
# refresh_detailed_minutes_job
# ---------------------------------------------------------------------------


class TestRefreshJob:
    async def test_regenerates_only_stale_ready_minutes(self, test_db, test_user):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        old, new = "2026-10-01 10:00:00", "2026-10-02 10:00:00"
        stale = await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                              minutes_generated_at=old, speaker_mapping_updated_at=new)
        # No minutes at all (D5: never generated by the job)
        await _insert(test_db, test_user.id, speaker_mapping_updated_at=new)
        # Up to date
        await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                      minutes_generated_at=new, speaker_mapping_updated_at=old)
        # Failed but not stale
        await _insert(test_db, test_user.id, minutes="m", minutes_status="failed",
                      minutes_generated_at=new, speaker_mapping_updated_at=old)
        # Failed first generation (no minutes): never picked
        await _insert(test_db, test_user.id, minutes_status="failed",
                      minutes_generated_at=old, speaker_mapping_updated_at=new)
        # Currently generating
        await _insert(test_db, test_user.id, minutes="m", minutes_status="generating",
                      minutes_generated_at=old, speaker_mapping_updated_at=new)
        # Speaker mapping never updated
        await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                      minutes_generated_at=old)

        gen = AsyncMock(return_value=True)
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        gen.assert_awaited_once_with(stale, test_user.id)

    async def test_retries_stale_failed_refresh(self, test_db, test_user):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        rec_id = await _insert(
            test_db, test_user.id, minutes="old", minutes_status="failed",
            minutes_generated_at="2026-10-01 10:00:00",
            speaker_mapping_updated_at="2026-10-02 10:00:00",
        )
        gen = AsyncMock(return_value=True)
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        gen.assert_awaited_once_with(rec_id, test_user.id)

    async def test_never_picks_recording_without_minutes(self, test_db, test_user):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        await _insert(test_db, test_user.id, speaker_mapping_updated_at="2026-10-02 10:00:00")
        await _insert(test_db, test_user.id, minutes_status="ready",
                      minutes_generated_at="2026-10-01 10:00:00",
                      speaker_mapping_updated_at="2026-10-02 10:00:00")
        gen = AsyncMock(return_value=True)
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        gen.assert_not_called()

    async def test_skips_recording_already_generating(self, test_db, test_user, caplog):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        busy = await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                             minutes_generated_at="2026-09-01 00:00:00",
                             speaker_mapping_updated_at="2026-09-02 00:00:00")
        free = await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                             minutes_generated_at="2026-09-01 00:00:00",
                             speaker_mapping_updated_at="2026-09-02 00:00:00")
        minutes_service._generating.add(busy)
        gen = AsyncMock(return_value=True)
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen), \
             caplog.at_level("INFO", logger="app.scheduler.jobs"):
            await refresh_detailed_minutes_job()
        gen.assert_awaited_once_with(free, test_user.id)
        assert "1 regenerated, 0 failed, 1 skipped" in caplog.text

    async def test_rename_during_run_leaves_minutes_stale(self, test_db, test_user):
        """generated_at is the time names were read, so a rename mid-run is
        picked up by the next refresh."""
        from app.scheduler.jobs import refresh_detailed_minutes_job

        rec_id = await _insert(test_db, test_user.id)

        async def fake_pipeline(_client, _info, _turns):
            # Cross a one-second boundary so the rename is strictly later than
            # the read; with an end-of-run generated_at it would not be stale.
            await asyncio.sleep(1.1)
            await test_db.execute(
                """UPDATE recordings
                   SET speaker_mapping_updated_at = datetime('now')
                   WHERE id = ?""",
                (rec_id,),
            )
            await test_db.commit()
            return "# Minutes", {"chunks": 1, "transcript_tokens": 1,
                                 "minutes_tokens": 1, "seconds": 0}

        client = MagicMock()
        client.close = AsyncMock()
        with patch.object(minutes_service, "_get_client", return_value=client), \
             patch.object(minutes_service, "run_pipeline", fake_pipeline):
            assert await minutes_service.generate_minutes(rec_id, test_user.id)

        rows = await test_db.execute_fetchall(
            """SELECT detailed_minutes_generated_at AS g, speaker_mapping_updated_at AS s
               FROM recordings WHERE id = ?""", (rec_id,)
        )
        row = dict(rows[0])
        assert row["g"] < row["s"]

        gen = AsyncMock(return_value=True)
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        gen.assert_awaited_once_with(rec_id, test_user.id)

    async def test_limit_five_newest_first(self, test_db, test_user):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        ids = []
        for day in range(1, 8):
            ids.append(await _insert(
                test_db, test_user.id, minutes="m", minutes_status="ready",
                minutes_generated_at="2026-09-01 00:00:00",
                speaker_mapping_updated_at="2026-09-02 00:00:00",
                recorded_at=f"2026-09-{day:02}T10:00:00+00:00",
            ))
        gen = AsyncMock(return_value=True)
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        called = [c.args[0] for c in gen.await_args_list]
        assert called == list(reversed(ids))[:5]

    async def test_continues_after_failure(self, test_db, test_user):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        for _ in range(2):
            await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                          minutes_generated_at="2026-09-01 00:00:00",
                          speaker_mapping_updated_at="2026-09-02 00:00:00")
        gen = AsyncMock(side_effect=[RuntimeError("x"), True])
        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        assert gen.await_count == 2

    async def test_skipped_when_ai_disabled(self, test_db, test_user):
        from app.scheduler.jobs import refresh_detailed_minutes_job

        await _insert(test_db, test_user.id, minutes="m", minutes_status="ready",
                      minutes_generated_at="2026-09-01 00:00:00",
                      speaker_mapping_updated_at="2026-09-02 00:00:00")
        gen = AsyncMock()
        with patch("app.scheduler.jobs.get_settings", return_value=_settings(ai=False)), \
             patch.object(minutes_service, "generate_minutes", gen):
            await refresh_detailed_minutes_job()
        gen.assert_not_called()

    def test_job_registered(self):
        from app.scheduler import jobs

        with patch("app.scheduler.jobs.get_settings", return_value=_settings()), \
             patch.object(jobs.scheduler, "start"):
            try:
                jobs.start_scheduler()
                job = jobs.scheduler.get_job("refresh_detailed_minutes")
                assert job is not None
                assert job.func is jobs.refresh_detailed_minutes_job
                assert job.max_instances == 1
                assert job.trigger.interval.total_seconds() == 3600
            finally:
                jobs.scheduler.remove_all_jobs()
