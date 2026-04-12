"""Tests for MCP tool endpoints (Phase B).

Covers search_recordings, get_recording, get_transcription,
list_participants, search_participants, and ai_chat.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import PropertyMock, patch

import pytest

from app.auth import get_current_user_or_api_key
from app.main import app
from app.models import User


# ---------------------------------------------------------------------------
# Auth override for MCP endpoints (they use get_current_user_or_api_key)
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

    Several MCP endpoints and services call get_db() directly rather than
    using FastAPI's Depends(get_db), so we need to set the module global.
    """
    import app.database as db_mod

    original = db_mod._db
    db_mod._db = test_db
    yield
    db_mod._db = original


# ---------------------------------------------------------------------------
# Helper — insert a recording with FTS data
# ---------------------------------------------------------------------------


async def _insert_recording(
    db,
    user_id,
    rec_id,
    title,
    description="",
    diarized_text="",
    transcript_text="",
    search_summary="",
    speaker_mapping=None,
    token_count=None,
    recorded_at=None,
    status="ready",
):
    now = recorded_at or datetime.now(timezone.utc).isoformat()
    sm = speaker_mapping or "{}"
    await db.execute(
        """INSERT INTO recordings
           (id, user_id, title, description, original_filename, source, status,
            transcript_text, diarized_text, speaker_mapping, search_summary, token_count,
            recorded_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec_id, user_id, title, description, "test.mp3", "upload", status,
            transcript_text, diarized_text, sm, search_summary, token_count, now, now, now,
        ),
    )
    # Manually insert into FTS since triggers may not fire in tests
    cursor = await db.execute("SELECT rowid FROM recordings WHERE id = ?", (rec_id,))
    row = await cursor.fetchone()
    if row:
        await db.execute(
            """INSERT INTO recordings_fts(rowid, title, description, diarized_text,
               transcript_text, search_summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row[0], title, description, diarized_text, transcript_text, search_summary),
        )
    await db.commit()


async def _insert_participant(db, user_id, part_id, display_name, aliases=None, **kwargs):
    now = datetime.now(timezone.utc).isoformat()
    aliases_json = json.dumps(aliases) if aliases else None
    await db.execute(
        """INSERT INTO participants
           (id, user_id, display_name, first_name, last_name, aliases, email,
            role, organization, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            part_id, user_id, display_name,
            kwargs.get("first_name"), kwargs.get("last_name"),
            aliases_json, kwargs.get("email"),
            kwargs.get("role"), kwargs.get("organization"),
            now, now,
        ),
    )
    await db.commit()


# ===========================================================================
# search_recordings endpoint tests
# ===========================================================================


class TestSearchRecordings:
    """GET /api/mcp/recordings"""

    async def test_list_recordings_no_query(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid, "Daily Standup")

        resp = await client.get("/api/mcp/recordings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        titles = [r["title"] for r in data]
        assert "Daily Standup" in titles

    async def test_search_title_mode(self, client, test_db, test_user):
        rid1 = str(uuid.uuid4())
        rid2 = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid1, "Budget Review",
            transcript_text="we talked about the weather",
        )
        await _insert_recording(
            test_db, test_user.id, rid2, "Weather Report",
            transcript_text="budget numbers are looking good",
        )

        resp = await client.get("/api/mcp/recordings", params={"query": "Budget", "mode": "title"})
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["id"] for r in data]
        assert rid1 in ids
        # rid2 has "budget" only in transcript, not title
        assert rid2 not in ids

    async def test_search_cascade_mode(self, client, test_db, test_user):
        rid_title = str(uuid.uuid4())
        rid_summary = str(uuid.uuid4())
        rid_transcript = str(uuid.uuid4())

        await _insert_recording(
            test_db, test_user.id, rid_title, "Widgets Discussion",
        )
        await _insert_recording(
            test_db, test_user.id, rid_summary, "Monday Sync",
            search_summary="Discussed widgets production numbers",
        )
        await _insert_recording(
            test_db, test_user.id, rid_transcript, "Tuesday Check-in",
            transcript_text="We need more widgets for the factory line",
        )

        resp = await client.get(
            "/api/mcp/recordings", params={"query": "widgets", "mode": "cascade"}
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["id"] for r in data]
        assert rid_title in ids
        assert rid_summary in ids
        assert rid_transcript in ids

        # Verify match_tier is set correctly
        tier_map = {r["id"]: r.get("match_tier") for r in data}
        assert tier_map[rid_title] == "title"
        assert tier_map[rid_summary] == "summary"
        assert tier_map[rid_transcript] == "transcript"

    async def test_search_with_date_filter(self, client, test_db, test_user):
        old_date = "2024-01-15T10:00:00+00:00"
        new_date = "2024-06-20T10:00:00+00:00"

        rid_old = str(uuid.uuid4())
        rid_new = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid_old, "January Meeting", recorded_at=old_date,
        )
        await _insert_recording(
            test_db, test_user.id, rid_new, "June Meeting", recorded_at=new_date,
        )

        resp = await client.get(
            "/api/mcp/recordings",
            params={"date_from": "2024-06-01", "date_to": "2024-07-01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["id"] for r in data]
        assert rid_new in ids
        assert rid_old not in ids

    async def test_search_with_participant_filter(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(test_db, test_user.id, part_id, "Alice Smith")

        rid = str(uuid.uuid4())
        mapping = json.dumps({
            "Speaker 1": {"participantId": part_id, "displayName": "Alice Smith"},
        })
        await _insert_recording(
            test_db, test_user.id, rid, "Team Sync",
            speaker_mapping=mapping,
        )

        resp = await client.get(
            "/api/mcp/recordings", params={"participant_id": part_id}
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["id"] for r in data]
        assert rid in ids

    async def test_search_pagination(self, client, test_db, test_user):
        for i in range(5):
            rid = str(uuid.uuid4())
            await _insert_recording(test_db, test_user.id, rid, f"Recording {i}")

        resp = await client.get("/api/mcp/recordings", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        page1 = resp.json()
        assert len(page1) == 2

        resp2 = await client.get("/api/mcp/recordings", params={"limit": 2, "offset": 2})
        assert resp2.status_code == 200
        page2 = resp2.json()
        assert len(page2) == 2

        # Pages should not overlap
        ids1 = {r["id"] for r in page1}
        ids2 = {r["id"] for r in page2}
        assert ids1.isdisjoint(ids2)

    async def test_search_empty_query(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid, "All Access")

        resp = await client.get("/api/mcp/recordings", params={"query": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_search_special_chars(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid, "Normal Meeting")

        resp = await client.get(
            "/api/mcp/recordings",
            params={"query": 'hello "world" & (test) OR NOT'},
        )
        assert resp.status_code == 200
        # Should not crash — may or may not return results


# ===========================================================================
# get_recording endpoint tests
# ===========================================================================


class TestGetRecording:
    """GET /api/mcp/recordings/{id}"""

    async def test_get_recording(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        mapping = json.dumps({
            "Speaker 1": {"displayName": "Bob", "participantId": None},
        })
        await _insert_recording(
            test_db, test_user.id, rid, "Detailed Meeting",
            search_summary="A summary of the meeting",
            speaker_mapping=mapping,
            token_count=500,
        )

        resp = await client.get(f"/api/mcp/recordings/{rid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rid
        assert data["title"] == "Detailed Meeting"
        assert data["search_summary"] == "A summary of the meeting"
        assert data["token_count"] == 500
        assert isinstance(data["speakers"], list)
        assert len(data["speakers"]) == 1
        assert data["speakers"][0]["label"] == "Speaker 1"
        assert data["speakers"][0]["display_name"] == "Bob"

    async def test_get_recording_not_found(self, client):
        resp = await client.get(f"/api/mcp/recordings/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_get_recording_wrong_user(self, client, test_db, other_user):
        rid = str(uuid.uuid4())
        await _insert_recording(test_db, other_user.id, rid, "Secret Meeting")

        resp = await client.get(f"/api/mcp/recordings/{rid}")
        assert resp.status_code == 404


# ===========================================================================
# get_transcription endpoint tests
# ===========================================================================


class TestGetTranscription:
    """GET /api/mcp/recordings/{id}/transcript"""

    async def test_get_transcript(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        text = "Speaker 1: Hello.\nSpeaker 2: Hi there.\nSpeaker 1: How are you?"
        await _insert_recording(
            test_db, test_user.id, rid, "Chat Recording",
            diarized_text=text, token_count=20,
        )

        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recording_id"] == rid
        assert data["total_tokens"] == 20
        assert "Hello" in data["text"]
        assert data["returned_tokens"] > 0

    async def test_get_transcript_pagination(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        # Create a longer text with many tokens
        lines = [f"Speaker {i % 2 + 1}: This is line number {i} of the conversation."
                 for i in range(50)]
        text = "\n".join(lines)
        token_count = len(text) // 4
        await _insert_recording(
            test_db, test_user.id, rid, "Long Chat",
            diarized_text=text, token_count=token_count,
        )

        # First page
        resp1 = await client.get(
            f"/api/mcp/recordings/{rid}/transcript",
            params={"token_offset": 0, "token_limit": 10},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["has_more"] is True
        assert data1["token_offset"] == 0
        assert data1["returned_tokens"] > 0

        # Second page with offset
        resp2 = await client.get(
            f"/api/mcp/recordings/{rid}/transcript",
            params={"token_offset": data1["returned_tokens"], "token_limit": 10},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["token_offset"] == data1["returned_tokens"]

    async def test_get_transcript_no_transcript(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid, "Empty Recording",
            diarized_text="", transcript_text="",
        )

        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tokens"] == 0
        assert data["text"] == ""


# ===========================================================================
# list_participants endpoint tests
# ===========================================================================


class TestListParticipants:
    """GET /api/mcp/participants"""

    async def test_list_participants(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(
            test_db, test_user.id, part_id, "Charlie Brown",
            email="charlie@example.com", organization="Peanuts Inc",
        )

        resp = await client.get("/api/mcp/participants")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        found = [p for p in data if p["id"] == part_id]
        assert len(found) == 1
        assert found[0]["display_name"] == "Charlie Brown"
        assert "recording_count" in found[0]


# ===========================================================================
# search_participants endpoint tests
# ===========================================================================


class TestSearchParticipants:
    """GET /api/mcp/participants/search"""

    async def test_search_participants(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(test_db, test_user.id, part_id, "Diana Prince")

        resp = await client.get(
            "/api/mcp/participants/search", params={"query": "Diana"}
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [p["id"] for p in data]
        assert part_id in ids

    async def test_search_participants_alias(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(
            test_db, test_user.id, part_id, "Bruce Wayne",
            aliases=["Batman", "The Dark Knight"],
        )

        resp = await client.get(
            "/api/mcp/participants/search", params={"query": "Batman"}
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [p["id"] for p in data]
        assert part_id in ids

    async def test_search_participants_multi_word(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(test_db, test_user.id, part_id, "Jane Doe")

        resp = await client.get(
            "/api/mcp/participants/search", params={"query": "Jane Doe"}
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [p["id"] for p in data]
        assert part_id in ids


# ===========================================================================
# ai_chat endpoint tests
# ===========================================================================


class TestAiChat:
    """POST /api/mcp/recordings/{id}/chat"""

    async def test_ai_chat_no_ai(self, client, test_db, test_user):
        """When AI is not configured, the endpoint should return 503."""
        rid = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid, "AI Test Meeting",
            diarized_text="Speaker 1: Let us discuss the plan.",
        )

        from app.config import Settings

        with patch.object(Settings, "ai_enabled", new_callable=PropertyMock, return_value=False):
            resp = await client.post(
                f"/api/mcp/recordings/{rid}/chat",
                json={"message": "What was discussed?"},
            )
        assert resp.status_code == 503
        assert "AI" in resp.json()["detail"] or "not configured" in resp.json()["detail"]
