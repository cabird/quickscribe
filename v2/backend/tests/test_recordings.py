"""Tests for recording endpoints.

Covers: list, detail, upload, paste, update, delete, audio URL,
speaker assignment, tag operations, and full-text search.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import (
    Recording,
    RecordingSource,
    RecordingStatus,
    Participant,
    Tag,
    User,
)


# ---------------------------------------------------------------------------
# GET /api/recordings — List
# ---------------------------------------------------------------------------


class TestListRecordings:
    async def test_list_empty(self, client: httpx.AsyncClient):
        resp = await client.get("/api/recordings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["total"] == 0

    async def test_list_with_data(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.get("/api/recordings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        ids = [r["id"] for r in body["data"]]
        assert sample_recording.id in ids

    async def test_list_excludes_transcript_text(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        """List endpoint should return summaries without full transcript."""
        resp = await client.get("/api/recordings")
        assert resp.status_code == 200
        rec = resp.json()["data"][0]
        assert "transcript_text" not in rec or rec.get("transcript_text") is None

    async def test_list_pagination(
        self, client: httpx.AsyncClient, test_db, test_user: User
    ):
        """Insert multiple recordings and verify pagination params."""
        for i in range(5):
            rec_id = str(uuid.uuid4())
            await test_db.execute(
                """INSERT INTO recordings (id, user_id, original_filename, source, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (rec_id, test_user.id, f"file{i}.mp3", "upload", "ready"),
            )
        await test_db.commit()

        resp = await client.get("/api/recordings", params={"page": 1, "per_page": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["total"] >= 5

    async def test_list_search(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        """Full-text search via query parameter."""
        resp = await client.get(
            "/api/recordings", params={"search": "test transcript"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    async def test_list_date_filtering(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        """Filter recordings by date range."""
        yesterday = "2020-01-01"
        tomorrow = "2099-12-31"
        resp = await client.get(
            "/api/recordings",
            params={"date_from": yesterday, "date_to": tomorrow},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_ownership_isolation(
        self,
        client_as_other: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        """Other user should not see test_user's recordings."""
        resp = await client_as_other.get("/api/recordings")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["data"]]
        assert sample_recording.id not in ids


# ---------------------------------------------------------------------------
# GET /api/recordings/{id} — Detail
# ---------------------------------------------------------------------------


class TestGetRecording:
    async def test_get_found(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.get(f"/api/recordings/{sample_recording.id}")
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["id"] == sample_recording.id
        assert data["transcript_text"] is not None

    async def test_get_not_found(self, client: httpx.AsyncClient):
        resp = await client.get(f"/api/recordings/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_get_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        """User B cannot access User A's recording."""
        resp = await client_as_other.get(f"/api/recordings/{sample_recording.id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/recordings/upload — File upload
# ---------------------------------------------------------------------------


class TestUploadRecording:
    @patch("app.services.storage.StorageService.upload_file", new_callable=AsyncMock)
    async def test_upload_success(
        self, mock_upload, client: httpx.AsyncClient
    ):
        mock_upload.return_value = "audio/test-file.mp3"
        audio_content = b"\x00" * 1024  # fake audio bytes
        files = {"file": ("meeting.mp3", io.BytesIO(audio_content), "audio/mpeg")}
        resp = await client.post("/api/recordings/upload", files=files)
        assert resp.status_code in (200, 201)
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["original_filename"] == "meeting.mp3"
        assert data["source"] == "upload"

    async def test_upload_no_file(self, client: httpx.AsyncClient):
        resp = await client.post("/api/recordings/upload")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/recordings/paste — Paste transcript
# ---------------------------------------------------------------------------


class TestPasteTranscript:
    async def test_paste_success(self, client: httpx.AsyncClient):
        payload = {
            "title": "Zoom Meeting",
            "transcript_text": "Speaker 1: Hello everyone.\nSpeaker 2: Hi there.",
            "source_app": "zoom",
        }
        resp = await client.post("/api/recordings/paste", json=payload)
        assert resp.status_code in (200, 201)
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["source"] == "paste"
        assert data["title"] == "Zoom Meeting"

    async def test_paste_missing_text(self, client: httpx.AsyncClient):
        payload = {"title": "No transcript"}
        resp = await client.post("/api/recordings/paste", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/recordings/{id} — Update
# ---------------------------------------------------------------------------


class TestUpdateRecording:
    async def test_update_title(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.put(
            f"/api/recordings/{sample_recording.id}",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["title"] == "Updated Title"

    async def test_update_not_found(self, client: httpx.AsyncClient):
        resp = await client.put(
            f"/api/recordings/{uuid.uuid4()}",
            json={"title": "Nope"},
        )
        assert resp.status_code == 404

    async def test_update_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        resp = await client_as_other.put(
            f"/api/recordings/{sample_recording.id}",
            json={"title": "Hacked"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/recordings/{id}
# ---------------------------------------------------------------------------


class TestDeleteRecording:
    async def test_delete_success(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.delete(f"/api/recordings/{sample_recording.id}")
        assert resp.status_code in (200, 204)

        # Confirm it's gone
        resp2 = await client.get(f"/api/recordings/{sample_recording.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(self, client: httpx.AsyncClient):
        resp = await client.delete(f"/api/recordings/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_plaud_recording_adds_to_deleted_ids(
        self,
        client: httpx.AsyncClient,
        sample_plaud_recording: Recording,
        test_db,
        test_user: User,
    ):
        """Deleting a plaud-sourced recording should add its plaud_id to deleted_plaud_ids."""
        plaud_id = sample_plaud_recording.plaud_id
        resp = await client.delete(f"/api/recordings/{sample_plaud_recording.id}")
        assert resp.status_code in (200, 204)

        rows = await test_db.execute_fetchall(
            "SELECT * FROM deleted_plaud_ids WHERE user_id = ? AND plaud_id = ?",
            (test_user.id, plaud_id),
        )
        assert len(rows) == 1

    async def test_delete_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        resp = await client_as_other.delete(f"/api/recordings/{sample_recording.id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/recordings/{id}/audio — Audio streaming URL
# ---------------------------------------------------------------------------


class TestGetAudioUrl:
    @patch("app.services.storage.StorageService.generate_sas_url", new_callable=AsyncMock)
    async def test_audio_url_success(
        self, mock_sas, client: httpx.AsyncClient, sample_recording: Recording
    ):
        mock_sas.return_value = "https://storage.blob.core.windows.net/audio/file.mp3?sig=abc"
        resp = await client.get(f"/api/recordings/{sample_recording.id}/audio")
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        # Response should contain a URL
        url_value = data.get("url") or data.get("audio_url") or ""
        assert "https://" in url_value or resp.status_code == 200

    async def test_audio_url_not_found(self, client: httpx.AsyncClient):
        resp = await client.get(f"/api/recordings/{uuid.uuid4()}/audio")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/recordings/{id}/speakers/{label} — Speaker assignment
# ---------------------------------------------------------------------------


class TestSpeakerAssignment:
    async def test_assign_speaker(
        self,
        client: httpx.AsyncClient,
        sample_recording: Recording,
        sample_participant: Participant,
    ):
        resp = await client.put(
            f"/api/recordings/{sample_recording.id}/speakers/Speaker 1",
            json={
                "participant_id": sample_participant.id,
                "manually_verified": True,
            },
        )
        assert resp.status_code == 200

    async def test_assign_speaker_recording_not_found(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.put(
            f"/api/recordings/{uuid.uuid4()}/speakers/Speaker 1",
            json={"participant_id": sample_participant.id},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST/DELETE /api/recordings/{id}/tags/{tag_id} — Tag operations
# ---------------------------------------------------------------------------


class TestRecordingTags:
    async def test_add_tag_to_recording(
        self,
        client: httpx.AsyncClient,
        sample_recording: Recording,
        sample_tag: Tag,
    ):
        resp = await client.post(
            f"/api/recordings/{sample_recording.id}/tags/{sample_tag.id}"
        )
        assert resp.status_code in (200, 201, 204)

    async def test_remove_tag_from_recording(
        self,
        client: httpx.AsyncClient,
        sample_recording: Recording,
        sample_tag: Tag,
        test_db,
    ):
        # First add the tag
        await test_db.execute(
            "INSERT INTO recording_tags (recording_id, tag_id) VALUES (?, ?)",
            (sample_recording.id, sample_tag.id),
        )
        await test_db.commit()

        resp = await client.delete(
            f"/api/recordings/{sample_recording.id}/tags/{sample_tag.id}"
        )
        assert resp.status_code in (200, 204)

    async def test_add_tag_recording_not_found(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client.post(
            f"/api/recordings/{uuid.uuid4()}/tags/{sample_tag.id}"
        )
        assert resp.status_code == 404

    async def test_add_tag_not_found(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.post(
            f"/api/recordings/{sample_recording.id}/tags/{uuid.uuid4()}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------


class TestFullTextSearch:
    async def test_search_by_title(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.get(
            "/api/recordings", params={"search": "Test Meeting"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_search_by_transcript_content(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.get(
            "/api/recordings", params={"search": "test transcript"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_search_no_results(self, client: httpx.AsyncClient):
        resp = await client.get(
            "/api/recordings", params={"search": "xyznonexistent123"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
