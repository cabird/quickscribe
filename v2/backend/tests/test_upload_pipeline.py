"""Tests for the audio upload pipeline.

Covers: the upload request returning before any transcoding, the background
transcode + transcription submit, failure and reprocess, resuming after a
restart, duplicate detection, recording-time handling, and the content_hash
migration.

Storage, ffmpeg, ffprobe and Azure Speech are all faked — no network, no
binaries.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.config import Settings
from app.database import (
    CONTENT_HASH_INDEX_SQL,
    FTS_SCHEMA_SQL,
    SCHEMA_SQL,
    _migrate_schema,
)
from app.models import User
from app.services import storage_service, sync_service, upload_service

M4A = b"fake-m4a-bytes"


def _settings(speech: bool = True) -> Settings:
    """Production-shaped settings: Azure blob storage, speech on by default."""
    return Settings(
        database_path=":memory:",
        auth_disabled=True,
        local_blob_path="",
        azure_storage_connection_string="fake-connection-string",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        speech_services_key="key" if speech else "",
        speech_services_region="westus" if speech else "",
    )


class FakeBlobs:
    """In-memory stand-in for storage_service."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.uploads = 0

    async def upload_file(self, file_path, blob_name: str) -> str:
        self.uploads += 1
        self.blobs[blob_name] = Path(file_path).read_bytes()
        return blob_name

    async def download_file(self, blob_name: str, local_path) -> Path:
        if blob_name not in self.blobs:
            raise FileNotFoundError(blob_name)
        Path(local_path).write_bytes(self.blobs[blob_name])
        return Path(local_path)

    async def delete_blob(self, blob_name: str) -> None:
        self.blobs.pop(blob_name, None)


class FakeTranscoder:
    """Stand-in for ffmpeg: records calls, can block on a gate or fail."""

    def __init__(self) -> None:
        self.calls = 0
        self.running = 0
        self.max_running = 0
        self.gate: asyncio.Event | None = None
        self.started = asyncio.Event()
        self.error: Exception | None = None

    async def __call__(self, input_path: Path, output_path: Path, timeout: int = 300) -> Path:
        self.calls += 1
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        self.started.set()
        try:
            if self.gate is not None:
                await self.gate.wait()
            else:
                await asyncio.sleep(0)
            if self.error is not None:
                raise self.error
            Path(output_path).write_bytes(b"MP3:" + Path(input_path).read_bytes())
            return Path(output_path)
        finally:
            self.running -= 1


class Pipeline:
    def __init__(self, db, blobs, transcoder, speech, probe) -> None:
        self.db = db
        self.blobs = blobs
        self.transcoder = transcoder
        self.speech = speech
        self.probe = probe

    async def drain(self) -> None:
        """Wait for every spawned background task to finish."""
        while sync_service._background_tasks:
            await asyncio.gather(*sync_service._background_tasks, return_exceptions=True)

    async def row(self, recording_id: str) -> dict:
        rows = await self.db.execute_fetchall(
            "SELECT * FROM recordings WHERE id = ?", (recording_id,)
        )
        return dict(rows[0])

    async def count(self) -> int:
        rows = await self.db.execute_fetchall("SELECT COUNT(*) AS n FROM recordings")
        return dict(rows[0])["n"]

    async def add(
        self,
        user_id: str,
        status: str = "pending",
        file_path: str | None = "raw",
        provider_job_id: str | None = None,
        source: str = "upload",
    ) -> str:
        """Insert a recording directly, with its blob, as if left by an earlier run."""
        rec_id = str(uuid.uuid4())
        if file_path == "raw":
            file_path = f"{user_id}/{rec_id}.orig.m4a"
        elif file_path == "mp3":
            file_path = f"{user_id}/{rec_id}.mp3"
        if file_path:
            self.blobs.blobs[file_path] = M4A
        await self.db.execute(
            """INSERT INTO recordings
               (id, user_id, original_filename, source, status, file_path, provider_job_id)
               VALUES (?, ?, 'memo.m4a', ?, ?, ?, ?)""",
            (rec_id, user_id, source, status, file_path, provider_job_id),
        )
        await self.db.commit()
        return rec_id


@pytest.fixture
async def pipeline(test_db: aiosqlite.Connection):
    """Wire upload_service to the test DB with storage, ffmpeg and Speech faked."""
    await test_db.execute(CONTENT_HASH_INDEX_SQL)
    await test_db.commit()

    blobs = FakeBlobs()
    transcoder = FakeTranscoder()
    speech = AsyncMock()
    speech.create_transcription.return_value = "job-0123456789"
    probe = AsyncMock(return_value={})

    with (
        patch("app.database._db", test_db),
        patch.object(upload_service, "get_settings", return_value=_settings()),
        patch.object(upload_service, "_process_lock", asyncio.Lock()),
        patch.object(upload_service, "_transcode_to_mp3", transcoder),
        patch.object(upload_service, "_probe_media", probe),
        patch.object(upload_service, "SpeechClient", return_value=speech),
        patch.object(storage_service, "upload_file", blobs.upload_file),
        patch.object(storage_service, "download_file", blobs.download_file),
        patch.object(storage_service, "delete_blob", blobs.delete_blob),
        patch.object(
            storage_service, "_azure_sas_url", lambda name, hours, settings: f"https://sas/{name}"
        ),
    ):
        p = Pipeline(test_db, blobs, transcoder, speech, probe)
        yield p
        # Let spawned work finish while the DB and fakes are still in place
        if transcoder.gate is not None:
            transcoder.gate.set()
        await p.drain()


def _file(data: bytes = M4A, name: str = "memo.m4a", mime: str = "audio/mp4") -> dict:
    return {"file": (name, io.BytesIO(data), mime)}


def _upload_file(data: bytes = M4A, name: str = "memo.m4a") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name)


# ---------------------------------------------------------------------------
# POST /api/recordings/upload — the request path
# ---------------------------------------------------------------------------


class TestUploadRequest:
    async def test_returns_before_transcoding_finishes(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        pipeline.transcoder.gate = asyncio.Event()  # ffmpeg never finishes on its own

        resp = await asyncio.wait_for(
            client.post("/api/recordings/upload", files=_file()), timeout=5
        )

        assert resp.status_code == 201
        body = resp.json()
        # The iOS Shortcut looks for this exact "success" text
        assert body == {
            "success": "File uploaded successfully!",
            "filename": "memo.m4a",
            "recording_id": body["recording_id"],
            "status": "pending",
            "duplicate": False,
        }
        assert list(body)[:4] == ["success", "filename", "recording_id", "status"]
        pipeline.speech.create_transcription.assert_not_called()

        # The background task picks it up and is now stuck in the "transcode"
        await asyncio.wait_for(pipeline.transcoder.started.wait(), timeout=5)
        assert (await pipeline.row(body["recording_id"]))["status"] == "transcoding"

        pipeline.transcoder.gate.set()
        await pipeline.drain()
        assert (await pipeline.row(body["recording_id"]))["status"] == "transcribing"

    async def test_raw_file_is_stored_untouched(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        pipeline.transcoder.gate = asyncio.Event()

        resp = await asyncio.wait_for(
            client.post("/api/recordings/upload", files=_file()), timeout=5
        )
        rec_id = resp.json()["recording_id"]

        row = await pipeline.row(rec_id)
        assert row["file_path"] == f"{test_user.id}/{rec_id}.orig.m4a"
        assert pipeline.blobs.blobs[row["file_path"]] == M4A
        assert row["source"] == "upload"
        assert row["original_filename"] == "memo.m4a"
        assert row["user_id"] == test_user.id
        assert row["content_hash"]

    async def test_title_and_recorded_at_form_fields(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        # The file's own timestamp must lose to the explicit one
        pipeline.probe.return_value = {
            "recorded_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        resp = await client.post(
            "/api/recordings/upload",
            files=_file(),
            data={"title": "Standup", "recorded_at": "2026-09-30T09:15:00-07:00"},
        )
        row = await pipeline.row(resp.json()["recording_id"])
        assert row["title"] == "Standup"
        assert row["recorded_at"] == "2026-09-30T16:15:00+00:00"

    async def test_title_query_param_still_accepted(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        resp = await client.post(
            "/api/recordings/upload", files=_file(), params={"title": "From query"}
        )
        assert (await pipeline.row(resp.json()["recording_id"]))["title"] == "From query"

    async def test_no_title_leaves_title_empty_for_ai(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        resp = await client.post("/api/recordings/upload", files=_file())
        assert (await pipeline.row(resp.json()["recording_id"]))["title"] is None

    async def test_recording_time_and_duration_from_file_metadata(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        pipeline.probe.return_value = {
            "recorded_at": datetime(2026, 9, 28, 14, 30, tzinfo=timezone.utc),
            "duration_seconds": 754.2,
        }
        resp = await client.post("/api/recordings/upload", files=_file())
        row = await pipeline.row(resp.json()["recording_id"])
        assert row["recorded_at"] == "2026-09-28T14:30:00+00:00"
        assert row["duration_seconds"] == 754.2

    async def test_recording_time_defaults_to_now(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        before = datetime.now(timezone.utc)
        resp = await client.post("/api/recordings/upload", files=_file())
        row = await pipeline.row(resp.json()["recording_id"])
        recorded = datetime.fromisoformat(row["recorded_at"])
        assert before - timedelta(seconds=1) <= recorded <= datetime.now(timezone.utc)

    async def test_invalid_recorded_at_rejected(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        resp = await client.post(
            "/api/recordings/upload", files=_file(), data={"recorded_at": "yesterday"}
        )
        assert resp.status_code == 422
        assert await pipeline.count() == 0

    async def test_empty_file_rejected(self, client: httpx.AsyncClient, pipeline: Pipeline):
        resp = await client.post("/api/recordings/upload", files=_file(data=b""))
        assert resp.status_code == 400
        assert await pipeline.count() == 0
        assert pipeline.blobs.blobs == {}

    async def test_no_file_rejected(self, client: httpx.AsyncClient, pipeline: Pipeline):
        resp = await client.post("/api/recordings/upload")
        assert resp.status_code == 400

    async def test_audio_file_field_name_accepted(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        resp = await client.post(
            "/api/recordings/upload",
            files={"audio_file": ("memo.m4a", io.BytesIO(M4A), "audio/mp4")},
        )
        assert resp.status_code == 201

    async def test_hostile_filename_cannot_escape(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        resp = await client.post(
            "/api/recordings/upload", files=_file(name="../../../etc/cron.d/evil.m4a")
        )
        assert resp.status_code == 201
        await pipeline.drain()
        rec_id = resp.json()["recording_id"]
        assert set(pipeline.blobs.blobs) == {f"{test_user.id}/{rec_id}.mp3"}

    async def test_storage_failure_creates_no_recording(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        with patch.object(
            storage_service, "upload_file", AsyncMock(side_effect=RuntimeError("blob down"))
        ):
            resp = await client.post("/api/recordings/upload", files=_file())
        assert resp.status_code == 500
        assert await pipeline.count() == 0


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


class TestDuplicates:
    async def test_same_file_twice_returns_existing(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        first = await client.post("/api/recordings/upload", files=_file())
        await pipeline.drain()
        uploads_before = pipeline.blobs.uploads
        second = await client.post("/api/recordings/upload", files=_file(name="renamed.m4a"))
        await pipeline.drain()

        assert second.status_code == 200
        body = second.json()
        assert body["duplicate"] is True
        assert body["recording_id"] == first.json()["recording_id"]
        assert body["status"] == "transcribing"
        assert await pipeline.count() == 1
        assert pipeline.transcoder.calls == 1
        assert pipeline.speech.create_transcription.await_count == 1
        # Recognised before anything was stored or probed again
        assert pipeline.blobs.uploads == uploads_before
        assert pipeline.probe.await_count == 1

    async def test_different_content_is_not_a_duplicate(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        await client.post("/api/recordings/upload", files=_file())
        resp = await client.post("/api/recordings/upload", files=_file(data=b"other-bytes"))
        assert resp.status_code == 201
        assert await pipeline.count() == 2

    async def test_duplicates_are_scoped_per_user(
        self, pipeline: Pipeline, test_user: User, other_user: User
    ):
        mine = await upload_service.receive_upload(test_user.id, _upload_file())
        theirs = await upload_service.receive_upload(other_user.id, _upload_file())

        assert theirs["duplicate"] is False
        assert theirs["recording_id"] != mine["recording_id"]
        assert (await pipeline.row(theirs["recording_id"]))["user_id"] == other_user.id

    async def test_reuploading_a_failed_recording_retries_it(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        pipeline.transcoder.error = RuntimeError("ffmpeg failed: bad header")
        first = await client.post("/api/recordings/upload", files=_file())
        await pipeline.drain()
        rec_id = first.json()["recording_id"]
        assert (await pipeline.row(rec_id))["status"] == "failed"

        pipeline.transcoder.error = None
        second = await client.post("/api/recordings/upload", files=_file())
        await pipeline.drain()

        assert second.status_code == 200
        assert second.json() == {
            "success": "File uploaded successfully!",
            "filename": "memo.m4a",
            "recording_id": rec_id,
            "status": "pending",
            "duplicate": True,
        }
        assert (await pipeline.row(rec_id))["status"] == "transcribing"
        assert await pipeline.count() == 1

    async def test_simultaneous_identical_uploads_keep_one(
        self, pipeline: Pipeline, test_user: User
    ):
        """Both requests pass the lookup before either inserts; the index decides."""
        winner = await upload_service.receive_upload(test_user.id, _upload_file())
        await pipeline.drain()
        real_find = upload_service._find_by_hash
        calls = 0

        async def find_missing_first(user_id, content_hash):
            nonlocal calls
            calls += 1
            return None if calls == 1 else await real_find(user_id, content_hash)

        with patch.object(upload_service, "_find_by_hash", find_missing_first):
            loser = await upload_service.receive_upload(test_user.id, _upload_file())
        await pipeline.drain()

        assert loser == {
            "recording_id": winner["recording_id"],
            "status": "transcribing",
            "duplicate": True,
        }
        assert await pipeline.count() == 1
        # The loser's raw upload was cleaned up
        assert set(pipeline.blobs.blobs) == {f"{test_user.id}/{winner['recording_id']}.mp3"}


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------


class TestProcessUpload:
    async def test_transcodes_swaps_blob_and_submits(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        resp = await client.post("/api/recordings/upload", files=_file())
        await pipeline.drain()

        rec_id = resp.json()["recording_id"]
        mp3 = f"{test_user.id}/{rec_id}.mp3"
        row = await pipeline.row(rec_id)
        assert row["status"] == "transcribing"
        assert row["file_path"] == mp3
        assert row["provider_job_id"] == "job-0123456789"
        assert row["processing_started"] is not None
        # The raw original is gone; only the transcoded MP3 remains
        assert pipeline.blobs.blobs == {mp3: b"MP3:" + M4A}
        pipeline.speech.create_transcription.assert_awaited_once_with(
            audio_url=f"https://sas/{mp3}", display_name="memo.m4a"
        )

    async def test_mp3_upload_is_not_transcoded(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        resp = await client.post(
            "/api/recordings/upload", files=_file(data=b"mp3-bytes", name="Talk.MP3")
        )
        await pipeline.drain()

        rec_id = resp.json()["recording_id"]
        row = await pipeline.row(rec_id)
        assert pipeline.transcoder.calls == 0
        assert row["status"] == "transcribing"
        assert pipeline.blobs.blobs == {f"{test_user.id}/{rec_id}.mp3": b"mp3-bytes"}

    async def test_transcode_failure_marks_failed_and_keeps_raw(
        self, client: httpx.AsyncClient, pipeline: Pipeline
    ):
        pipeline.transcoder.error = RuntimeError("ffmpeg failed: moov atom not found")
        resp = await client.post("/api/recordings/upload", files=_file())
        await pipeline.drain()

        row = await pipeline.row(resp.json()["recording_id"])
        assert row["status"] == "failed"
        assert "moov atom not found" in row["status_message"]
        assert row["provider_job_id"] is None
        assert pipeline.blobs.blobs == {row["file_path"]: M4A}
        pipeline.speech.create_transcription.assert_not_called()

    async def test_speech_failure_marks_failed_after_transcode(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        pipeline.speech.create_transcription.side_effect = RuntimeError("speech 503")
        resp = await client.post("/api/recordings/upload", files=_file())
        await pipeline.drain()

        rec_id = resp.json()["recording_id"]
        row = await pipeline.row(rec_id)
        assert row["status"] == "failed"
        assert "speech 503" in row["status_message"]
        assert row["file_path"] == f"{test_user.id}/{rec_id}.mp3"

    async def test_without_speech_transcodes_and_parks_as_pending(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        with patch.object(upload_service, "get_settings", return_value=_settings(speech=False)):
            resp = await client.post("/api/recordings/upload", files=_file())
            await pipeline.drain()
            rec_id = resp.json()["recording_id"]
            row = await pipeline.row(rec_id)
            assert row["status"] == "pending"
            assert row["file_path"] == f"{test_user.id}/{rec_id}.mp3"

            # The sweep revisits it but has nothing to do and writes nothing
            await pipeline.db.execute(
                "UPDATE recordings SET updated_at = '2020-01-01 00:00:00' WHERE id = ?", (rec_id,)
            )
            await pipeline.db.commit()
            await upload_service.resume_pending_uploads()
            assert (await pipeline.row(rec_id))["updated_at"] == "2020-01-01 00:00:00"
        assert pipeline.transcoder.calls == 1
        pipeline.speech.create_transcription.assert_not_called()

    async def test_only_one_transcode_at_a_time(self, pipeline: Pipeline, test_user: User):
        ids = [await pipeline.add(test_user.id) for _ in range(3)]

        await asyncio.gather(*(upload_service.process_upload(i) for i in ids))

        assert pipeline.transcoder.calls == 3
        assert pipeline.transcoder.max_running == 1
        for rec_id in ids:
            assert (await pipeline.row(rec_id))["status"] == "transcribing"

    async def test_same_recording_is_not_processed_twice(
        self, pipeline: Pipeline, test_user: User
    ):
        rec_id = await pipeline.add(test_user.id)

        await asyncio.gather(
            upload_service.process_upload(rec_id),
            upload_service.process_upload(rec_id),
            upload_service.resume_pending_uploads(),
        )
        await upload_service.process_upload(rec_id)  # and once more after it is done

        assert pipeline.transcoder.calls == 1
        assert pipeline.speech.create_transcription.await_count == 1

    async def test_cancelled_mid_transcode_resumes_later(
        self, pipeline: Pipeline, test_user: User
    ):
        """A shutdown must leave the recording resumable, not failed."""
        rec_id = await pipeline.add(test_user.id)
        pipeline.transcoder.gate = asyncio.Event()

        task = asyncio.create_task(upload_service.process_upload(rec_id))
        await pipeline.transcoder.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        row = await pipeline.row(rec_id)
        assert row["status"] == "transcoding"
        assert row["status_message"] is None

        pipeline.transcoder.gate = None
        assert await upload_service.resume_pending_uploads() == 1
        assert (await pipeline.row(rec_id))["status"] == "transcribing"

    async def test_deleted_while_transcoding_leaves_no_blob(
        self, pipeline: Pipeline, test_user: User
    ):
        rec_id = await pipeline.add(test_user.id)
        pipeline.transcoder.gate = asyncio.Event()

        task = asyncio.create_task(upload_service.process_upload(rec_id))
        await pipeline.transcoder.started.wait()
        pipeline.blobs.blobs.clear()  # what delete_recording does to the raw blob
        await pipeline.db.execute("DELETE FROM recordings WHERE id = ?", (rec_id,))
        await pipeline.db.commit()
        pipeline.transcoder.gate.set()
        await task

        assert pipeline.blobs.blobs == {}
        pipeline.speech.create_transcription.assert_not_called()

    @pytest.mark.parametrize(
        ("status", "job_id"),
        [("transcribing", "job-1"), ("processing", "job-1"), ("ready", None), ("failed", None)],
    )
    async def test_ignores_recordings_not_owed_work(
        self, pipeline: Pipeline, test_user: User, status: str, job_id: str | None
    ):
        rec_id = await pipeline.add(test_user.id, status=status, provider_job_id=job_id)
        before = await pipeline.row(rec_id)

        await upload_service.process_upload(rec_id)

        assert await pipeline.row(rec_id) == before
        assert pipeline.transcoder.calls == 0
        pipeline.speech.create_transcription.assert_not_called()

    async def test_unknown_recording_is_a_noop(self, pipeline: Pipeline):
        await upload_service.process_upload(str(uuid.uuid4()))
        assert pipeline.transcoder.calls == 0


# ---------------------------------------------------------------------------
# Resuming after a restart
# ---------------------------------------------------------------------------


class TestResumePendingUploads:
    async def test_picks_up_interrupted_work_only(self, pipeline: Pipeline, test_user: User):
        waiting = await pipeline.add(test_user.id, status="pending")
        interrupted = await pipeline.add(test_user.id, status="transcoding")
        submitted = await pipeline.add(
            test_user.id, status="transcribing", file_path="mp3", provider_job_id="job-9"
        )
        done = await pipeline.add(test_user.id, status="ready", file_path="mp3")
        failed = await pipeline.add(test_user.id, status="failed")
        pasted = await pipeline.add(
            test_user.id, status="pending", file_path=None, source="paste"
        )

        assert await upload_service.resume_pending_uploads() == 2

        assert (await pipeline.row(waiting))["status"] == "transcribing"
        assert (await pipeline.row(interrupted))["status"] == "transcribing"
        assert (await pipeline.row(submitted))["provider_job_id"] == "job-9"
        assert (await pipeline.row(done))["status"] == "ready"
        assert (await pipeline.row(failed))["status"] == "failed"
        assert (await pipeline.row(pasted))["status"] == "pending"
        assert pipeline.transcoder.calls == 2

    async def test_one_failure_does_not_stop_the_rest(
        self, pipeline: Pipeline, test_user: User
    ):
        broken = await pipeline.add(test_user.id)
        del pipeline.blobs.blobs[(await pipeline.row(broken))["file_path"]]  # raw blob lost
        fine = await pipeline.add(test_user.id)

        await upload_service.resume_pending_uploads()

        assert (await pipeline.row(broken))["status"] == "failed"
        assert (await pipeline.row(fine))["status"] == "transcribing"

    async def test_scheduler_registers_the_job(self):
        from app.scheduler import jobs

        with (
            patch("app.scheduler.jobs.get_settings", return_value=_settings()),
            patch.object(jobs.scheduler, "start"),
        ):
            try:
                jobs.start_scheduler()
                job = jobs.scheduler.get_job("process_uploads")
            finally:
                jobs.scheduler.remove_all_jobs()

        assert job is not None
        assert job.func is jobs.process_uploads_job

    async def test_job_swallows_errors(self, pipeline: Pipeline):
        from app.scheduler import jobs

        with patch.object(
            upload_service, "resume_pending_uploads", AsyncMock(side_effect=RuntimeError("db"))
        ):
            await jobs.process_uploads_job()  # must not raise into the scheduler


# ---------------------------------------------------------------------------
# POST /api/recordings/{id}/reprocess
# ---------------------------------------------------------------------------


class TestReprocess:
    async def test_retries_failed_transcode(self, client: httpx.AsyncClient, pipeline: Pipeline):
        pipeline.transcoder.error = RuntimeError("ffmpeg failed")
        rec_id = (await client.post("/api/recordings/upload", files=_file())).json()[
            "recording_id"
        ]
        await pipeline.drain()
        pipeline.transcoder.error = None

        resp = await client.post(f"/api/recordings/{rec_id}/reprocess")
        await pipeline.drain()

        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        row = await pipeline.row(rec_id)
        assert row["status"] == "transcribing"
        assert row["status_message"] is None
        assert row["retry_count"] == 1

    async def test_retries_failed_transcription_without_transcoding_again(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        """Azure Speech failed the job: the MP3 is resubmitted under a new job."""
        rec_id = await pipeline.add(
            test_user.id, status="failed", file_path="mp3", provider_job_id="job-old"
        )

        resp = await client.post(f"/api/recordings/{rec_id}/reprocess")
        await pipeline.drain()

        assert resp.status_code == 200
        row = await pipeline.row(rec_id)
        assert row["status"] == "transcribing"
        assert row["provider_job_id"] == "job-0123456789"
        assert pipeline.transcoder.calls == 0

    @pytest.mark.parametrize("status", ["ready", "transcribing", "transcoding", "processing"])
    async def test_refused_unless_failed_or_waiting(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User, status: str
    ):
        rec_id = await pipeline.add(
            test_user.id, status=status, file_path="mp3", provider_job_id="job-1"
        )
        resp = await client.post(f"/api/recordings/{rec_id}/reprocess")
        await pipeline.drain()

        assert resp.status_code == 409
        row = await pipeline.row(rec_id)
        assert row["status"] == status
        assert row["provider_job_id"] == "job-1"

    async def test_refused_without_audio(
        self, client: httpx.AsyncClient, pipeline: Pipeline, test_user: User
    ):
        rec_id = await pipeline.add(test_user.id, status="failed", file_path=None, source="paste")
        resp = await client.post(f"/api/recordings/{rec_id}/reprocess")
        assert resp.status_code == 400

    async def test_other_users_recording_is_not_found(
        self, pipeline: Pipeline, test_user: User, other_user: User
    ):
        rec_id = await pipeline.add(test_user.id, status="failed")

        with pytest.raises(HTTPException) as exc:
            await upload_service.reprocess_recording(other_user.id, rec_id)

        assert exc.value.status_code == 404
        assert (await pipeline.row(rec_id))["status"] == "failed"

    async def test_unknown_recording(self, client: httpx.AsyncClient, pipeline: Pipeline):
        resp = await client.post(f"/api/recordings/{uuid.uuid4()}/reprocess")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reading the recording time out of the file
# ---------------------------------------------------------------------------


class TestProbeParsing:
    def test_apple_creation_date_preferred_and_keeps_offset(self):
        result = upload_service._parse_probe(
            {
                "format": {
                    "duration": "125.440000",
                    "tags": {
                        "creation_time": "2026-10-01T18:00:00.000000Z",
                        "com.apple.quicktime.creationdate": "2026-10-01T10:03:22-0700",
                    },
                }
            }
        )
        assert result["duration_seconds"] == 125.44
        assert result["recorded_at"].astimezone(timezone.utc) == datetime(
            2026, 10, 1, 17, 3, 22, tzinfo=timezone.utc
        )

    def test_generic_creation_time(self):
        result = upload_service._parse_probe(
            {"format": {"tags": {"Creation_Time": "2026-09-28T14:30:00.000000Z"}}}
        )
        assert result == {"recorded_at": datetime(2026, 9, 28, 14, 30, tzinfo=timezone.utc)}

    @pytest.mark.parametrize(
        "value",
        ["1904-01-01T00:00:00.000000Z", "1970-01-01T00:00:00Z", "2999-01-01T00:00:00Z",
         "not a date", "", None, 12345],
    )
    def test_implausible_dates_ignored(self, value):
        assert upload_service._parse_probe({"format": {"tags": {"creation_time": value}}}) == {}

    @pytest.mark.parametrize("data", [{}, {"format": None}, {"format": {"duration": "N/A"}},
                                      {"format": {"duration": "0"}}])
    def test_missing_or_bad_fields(self, data):
        assert upload_service._parse_probe(data) == {}

    async def test_probe_failure_is_not_fatal(self, tmp_path):
        """No ffprobe on the box (or it crashes): the upload still goes through."""
        with patch.object(
            upload_service.subprocess, "run", side_effect=FileNotFoundError("ffprobe")
        ):
            assert await upload_service._probe_media(tmp_path / "memo.m4a") == {}

    def test_naive_explicit_time_treated_as_utc(self):
        assert (
            upload_service._resolve_recorded_at(datetime(2026, 9, 30, 9, 15), None)
            == "2026-09-30T09:15:00+00:00"
        )


class TestSafeSuffix:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [("memo.m4a", ".m4a"), ("Talk.MP3", ".mp3"), ("noext", ""),
         ("weird.m4a;rm -rf", ""), ("a.toolongextension", ""), ("../x/y.wav", ".wav")],
    )
    def test_suffix(self, name: str, expected: str):
        assert upload_service._safe_suffix(name) == expected


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------


class TestContentHashMigration:
    async def test_adds_column_and_index_to_existing_database(self):
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        try:
            await db.executescript(SCHEMA_SQL)
            await db.executescript(FTS_SCHEMA_SQL)
            # Recreate the pre-migration shape, with a row already in it
            await db.execute("ALTER TABLE recordings DROP COLUMN content_hash")
            await db.execute("INSERT INTO users (id) VALUES ('u1')")
            await db.execute(
                """INSERT INTO recordings (id, user_id, original_filename, source)
                   VALUES ('old-1', 'u1', 'a.mp3', 'upload'),
                          ('old-2', 'u1', 'b.mp3', 'upload')"""
            )
            await db.commit()

            await _migrate_schema(db)
            await _migrate_schema(db)  # idempotent

            cursor = await db.execute("PRAGMA table_info(recordings)")
            assert "content_hash" in {row[1] for row in await cursor.fetchall()}
            # Old rows (no hash) coexist; a repeated hash for one user is refused
            await db.execute("UPDATE recordings SET content_hash = 'abc' WHERE id = 'old-1'")
            with pytest.raises(aiosqlite.IntegrityError):
                await db.execute("UPDATE recordings SET content_hash = 'abc' WHERE id = 'old-2'")
        finally:
            await db.close()
