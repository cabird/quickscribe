"""Tests for meeting notes feature — schema, service, background job, and endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from app.auth import get_current_user, get_current_user_or_api_key
from app.database import SCHEMA_SQL
from app.main import app
from app.models import User


# ---------------------------------------------------------------------------
# Auth overrides — MCP and recordings routers use different auth deps
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _override_api_key_auth(test_user):
    """Ensure MCP endpoints authenticate with the test user."""

    async def _override():
        return test_user

    app.dependency_overrides[get_current_user_or_api_key] = _override
    yield
    app.dependency_overrides.pop(get_current_user_or_api_key, None)


@pytest.fixture(autouse=True)
async def _patch_db_singleton(test_db):
    """Patch the module-level _db singleton so get_db() returns the test DB.

    Several services call get_db() directly rather than using FastAPI Depends.
    """
    import app.database as db_mod

    original = db_mod._db
    db_mod._db = test_db
    yield
    db_mod._db = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_recording(
    db,
    user_id,
    rec_id=None,
    title="Test Meeting",
    diarized_text="Speaker 1: Hello.\nSpeaker 2: Hi there.",
    transcript_text="Hello. Hi there.",
    meeting_notes=None,
    meeting_notes_generated_at=None,
    meeting_notes_tags=None,
    speaker_mapping_updated_at=None,
    speaker_mapping=None,
    status="ready",
    recorded_at=None,
):
    rec_id = rec_id or str(uuid.uuid4())
    now = recorded_at or datetime.now(timezone.utc).isoformat()
    sm = speaker_mapping or json.dumps({
        "Speaker 1": {
            "displayName": "Speaker 1",
            "participantId": None,
            "confidence": None,
            "manuallyVerified": False,
            "identificationStatus": "unknown",
        }
    })
    await db.execute(
        """INSERT INTO recordings
           (id, user_id, title, description, original_filename, source, status,
            transcript_text, diarized_text, speaker_mapping, token_count,
            meeting_notes, meeting_notes_generated_at, meeting_notes_tags,
            speaker_mapping_updated_at,
            recorded_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec_id, user_id, title, "desc", "meeting.mp3", "upload", status,
            transcript_text, diarized_text, sm, 20,
            meeting_notes, meeting_notes_generated_at,
            json.dumps(meeting_notes_tags) if meeting_notes_tags else None,
            speaker_mapping_updated_at,
            now, now, now,
        ),
    )
    # Manually insert FTS row
    cursor = await db.execute("SELECT rowid FROM recordings WHERE id = ?", (rec_id,))
    row = await cursor.fetchone()
    if row:
        await db.execute(
            """INSERT INTO recordings_fts(rowid, title, description, diarized_text,
               transcript_text, search_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row[0], title, "desc", diarized_text or "", transcript_text or "", ""),
        )
    await db.commit()
    return rec_id


SAMPLE_MEETING_NOTES = """# Test Meeting Notes

## Discussion Threads
- Discussed project timeline

## Decisions
- Agreed to ship by Friday

## Action Items
- @Alice: Finalize the design

## Key Quotes
> "We need to move fast" — Speaker 1

## Topic Tags
Azure, hiring, paper
"""


# ===========================================================================
# Schema tests
# ===========================================================================


class TestSchema:
    async def test_meeting_notes_columns_exist(self, test_db):
        """Verify the 4 new meeting-notes columns exist in the recordings table."""
        cursor = await test_db.execute("PRAGMA table_info(recordings)")
        columns = {row[1] for row in await cursor.fetchall()}

        assert "meeting_notes" in columns
        assert "meeting_notes_generated_at" in columns
        assert "meeting_notes_tags" in columns
        assert "speaker_mapping_updated_at" in columns


# ===========================================================================
# Meeting notes service tests
# ===========================================================================


def _make_mock_openai_response(content: str):
    """Create a mock that mimics the OpenAI chat completion response."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


class TestMeetingNotesService:
    async def test_generate_meeting_notes(self, test_db, test_user):
        """Mock Azure OpenAI and verify notes are stored in DB."""
        rec_id = await _insert_recording(test_db, test_user.id)

        mock_response = _make_mock_openai_response(SAMPLE_MEETING_NOTES)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.meeting_notes_service._get_client",
            return_value=mock_client,
        ):
            from app.services.meeting_notes_service import generate_meeting_notes

            result = await generate_meeting_notes(rec_id, test_user.id)

        assert result is not None
        assert "Discussion Threads" in result

        # Verify stored in DB
        rows = await test_db.execute_fetchall(
            "SELECT meeting_notes, meeting_notes_generated_at, meeting_notes_tags FROM recordings WHERE id = ?",
            (rec_id,),
        )
        row = dict(rows[0])
        assert row["meeting_notes"] == SAMPLE_MEETING_NOTES
        assert row["meeting_notes_generated_at"] is not None

    async def test_generate_meeting_notes_parses_topic_tags(self, test_db, test_user):
        """Verify topic tags are parsed and stored as JSON array."""
        rec_id = await _insert_recording(test_db, test_user.id)

        mock_response = _make_mock_openai_response(SAMPLE_MEETING_NOTES)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.meeting_notes_service._get_client",
            return_value=mock_client,
        ):
            from app.services.meeting_notes_service import generate_meeting_notes

            await generate_meeting_notes(rec_id, test_user.id)

        rows = await test_db.execute_fetchall(
            "SELECT meeting_notes_tags FROM recordings WHERE id = ?", (rec_id,)
        )
        tags = json.loads(dict(rows[0])["meeting_notes_tags"])
        assert tags == ["Azure", "hiring", "paper"]

    async def test_generate_meeting_notes_no_transcript(self, test_db, test_user):
        """Recording without any transcript should return None."""
        rec_id = await _insert_recording(
            test_db, test_user.id,
            diarized_text=None,
            transcript_text=None,
        )

        mock_client = AsyncMock()

        with patch(
            "app.services.meeting_notes_service._get_client",
            return_value=mock_client,
        ):
            from app.services.meeting_notes_service import generate_meeting_notes

            result = await generate_meeting_notes(rec_id, test_user.id)

        assert result is None
        # LLM should never have been called
        mock_client.chat.completions.create.assert_not_called()

    async def test_generate_meeting_notes_updates_generated_at(self, test_db, test_user):
        """Verify meeting_notes_generated_at is set after generation."""
        rec_id = await _insert_recording(test_db, test_user.id)

        # Confirm it's NULL before generation
        rows = await test_db.execute_fetchall(
            "SELECT meeting_notes_generated_at FROM recordings WHERE id = ?", (rec_id,)
        )
        assert dict(rows[0])["meeting_notes_generated_at"] is None

        mock_response = _make_mock_openai_response(SAMPLE_MEETING_NOTES)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.meeting_notes_service._get_client",
            return_value=mock_client,
        ):
            from app.services.meeting_notes_service import generate_meeting_notes

            await generate_meeting_notes(rec_id, test_user.id)

        rows = await test_db.execute_fetchall(
            "SELECT meeting_notes_generated_at FROM recordings WHERE id = ?", (rec_id,)
        )
        assert dict(rows[0])["meeting_notes_generated_at"] is not None


# ===========================================================================
# Background job tests
# ===========================================================================


class TestRefreshMeetingNotesJob:
    """Test the query logic in refresh_meeting_notes_job."""

    # The job's SQL query for reference:
    # WHERE status = 'ready'
    #   AND (diarized_text IS NOT NULL OR transcript_text IS NOT NULL)
    #   AND (
    #     meeting_notes IS NULL
    #     OR (speaker_mapping_updated_at IS NOT NULL
    #         AND meeting_notes_generated_at < speaker_mapping_updated_at)
    #   )

    JOB_QUERY = """
        SELECT id, user_id FROM recordings
        WHERE status = 'ready'
          AND (diarized_text IS NOT NULL OR transcript_text IS NOT NULL)
          AND (
            meeting_notes IS NULL
            OR (speaker_mapping_updated_at IS NOT NULL
                AND meeting_notes_generated_at < speaker_mapping_updated_at)
          )
        ORDER BY COALESCE(recorded_at, created_at) DESC
        LIMIT 10
    """

    async def test_refresh_job_picks_null_notes(self, test_db, test_user):
        """Recording with no meeting_notes should be found by the job query."""
        rec_id = await _insert_recording(
            test_db, test_user.id, meeting_notes=None,
        )

        rows = await test_db.execute_fetchall(self.JOB_QUERY)
        ids = [dict(r)["id"] for r in rows]
        assert rec_id in ids

    async def test_refresh_job_picks_stale_notes(self, test_db, test_user):
        """Notes generated before speaker_mapping_updated_at should be found."""
        old_time = "2024-06-01T10:00:00"
        new_time = "2024-06-15T10:00:00"
        rec_id = await _insert_recording(
            test_db, test_user.id,
            meeting_notes="some old notes",
            meeting_notes_generated_at=old_time,
            speaker_mapping_updated_at=new_time,
        )

        rows = await test_db.execute_fetchall(self.JOB_QUERY)
        ids = [dict(r)["id"] for r in rows]
        assert rec_id in ids

    async def test_refresh_job_skips_fresh_notes(self, test_db, test_user):
        """Notes generated after speaker_mapping_updated_at should NOT be found."""
        old_time = "2024-06-01T10:00:00"
        new_time = "2024-06-15T10:00:00"
        rec_id = await _insert_recording(
            test_db, test_user.id,
            meeting_notes="fresh notes",
            meeting_notes_generated_at=new_time,
            speaker_mapping_updated_at=old_time,
        )

        rows = await test_db.execute_fetchall(self.JOB_QUERY)
        ids = [dict(r)["id"] for r in rows]
        assert rec_id not in ids


# ===========================================================================
# MCP integration tests
# ===========================================================================


class TestMcpMeetingNotes:
    async def test_get_recording_includes_meeting_notes(self, client, test_db, test_user):
        """GET /api/mcp/recordings/{id} returns meeting_notes field."""
        rec_id = await _insert_recording(
            test_db, test_user.id,
            meeting_notes="# Notes\nSome meeting notes.",
            meeting_notes_generated_at="2024-06-15T10:00:00",
            meeting_notes_tags=["tag1", "tag2"],
        )

        resp = await client.get(f"/api/mcp/recordings/{rec_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting_notes"] == "# Notes\nSome meeting notes."
        assert data["meeting_notes_generated_at"] is not None

    async def test_synthesize_prefers_meeting_notes(self, client, test_db, test_user):
        """Synthesize endpoint should pass meeting_notes (not diarized_text) to AI."""
        rec_id = await _insert_recording(
            test_db, test_user.id,
            diarized_text="Speaker 1: raw transcript here",
            meeting_notes="# Structured Meeting Notes\nKey points discussed.",
        )

        mock_response = MagicMock()
        mock_response.answer = "Synthesized answer"
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        with patch(
            "app.services.ai_service.synthesize",
            new_callable=AsyncMock,
            return_value=MagicMock(answer="Synthesized answer", citations=[], usage=MagicMock(prompt_tokens=100, completion_tokens=50)),
        ) as mock_synth:
            resp = await client.post(
                "/api/mcp/synthesize",
                json={
                    "recording_ids": [rec_id],
                    "question": "What was discussed?",
                },
            )
            assert resp.status_code == 200

            # Verify AI received meeting_notes, not raw transcript
            call_args = mock_synth.call_args
            recordings_arg = call_args.kwargs.get("recordings") or call_args[1].get("recordings") or call_args[0][0]
            # The text field should be meeting notes, not the raw diarized text
            assert "Structured Meeting Notes" in recordings_arg[0]["text"]
            assert "raw transcript here" not in recordings_arg[0]["text"]


# ===========================================================================
# Manual trigger endpoint test
# ===========================================================================


class TestGenerateMeetingNotesEndpoint:
    async def test_generate_meeting_notes_endpoint(self, client, test_db, test_user):
        """POST /api/recordings/{id}/generate-meeting-notes returns 200."""
        rec_id = await _insert_recording(test_db, test_user.id)

        mock_response = _make_mock_openai_response(SAMPLE_MEETING_NOTES)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.meeting_notes_service._get_client",
            return_value=mock_client,
        ):
            resp = await client.post(f"/api/recordings/{rec_id}/generate-meeting-notes")

        assert resp.status_code == 200
        data = resp.json()
        assert "meeting_notes" in data
        assert "Discussion Threads" in data["meeting_notes"]
        assert data["meeting_notes_tags"] == ["Azure", "hiring", "paper"]
