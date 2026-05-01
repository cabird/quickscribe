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
    search_keywords=None,
    meeting_notes=None,
    duration_seconds=None,
):
    now = recorded_at or datetime.now(timezone.utc).isoformat()
    sm = speaker_mapping or "{}"
    sk = json.dumps(search_keywords) if search_keywords is not None else None
    await db.execute(
        """INSERT INTO recordings
           (id, user_id, title, description, original_filename, source, status,
            transcript_text, diarized_text, speaker_mapping, search_summary,
            search_keywords, meeting_notes, duration_seconds, token_count,
            recorded_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec_id, user_id, title, description, "test.mp3", "upload", status,
            transcript_text, diarized_text, sm, search_summary,
            sk, meeting_notes, duration_seconds, token_count,
            now, now, now,
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
            role, organization, relationship, notes, is_user,
            first_seen, last_seen, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            part_id, user_id, display_name,
            kwargs.get("first_name"), kwargs.get("last_name"),
            aliases_json, kwargs.get("email"),
            kwargs.get("role"), kwargs.get("organization"),
            kwargs.get("relationship"), kwargs.get("notes"),
            1 if kwargs.get("is_user") else 0,
            kwargs.get("first_seen"), kwargs.get("last_seen"),
            now, now,
        ),
    )
    await db.commit()


async def _insert_tag(db, user_id, tag_id, name, color="#abcdef"):
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO tags (id, user_id, name, color, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (tag_id, user_id, name, color, now),
    )
    await db.commit()


async def _attach_tag(db, recording_id, tag_id):
    await db.execute(
        "INSERT INTO recording_tags (recording_id, tag_id) VALUES (?, ?)",
        (recording_id, tag_id),
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


# ===========================================================================
# search_recordings — view + fields projection
# ===========================================================================


class TestSearchView:
    """View presets and explicit fields whitelist on search_recordings."""

    async def _seed_one(self, test_db, test_user):
        rid = str(uuid.uuid4())
        mapping = json.dumps({
            "Speaker 1": {"displayName": "Alice", "participantId": "p-alice"},
            "Speaker 2": {"displayName": "Bob"},  # no participantId -> unresolved
        })
        await _insert_recording(
            test_db, test_user.id, rid, "Strategy Meeting",
            description="One-line summary",
            search_summary="Three to five sentence retrieval summary",
            search_keywords=["strategy", "ops"],
            speaker_mapping=mapping,
            duration_seconds=600.0,
            token_count=4500,
            meeting_notes="# Heavy markdown\n\nLong content...",
        )
        return rid

    async def test_default_view_is_full_and_backwards_compatible(
        self, client, test_db, test_user
    ):
        """No `view` param → full shape, with all old fields preserved."""
        rid = await self._seed_one(test_db, test_user)
        resp = await client.get("/api/mcp/recordings")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        r = rows[0]
        # Old fields preserved (regression guard)
        for f in (
            "id", "title", "description", "duration_seconds", "recorded_at",
            "source", "status", "speaker_names", "tag_ids", "token_count",
        ):
            assert f in r, f"missing legacy field {f}"
        # New additive fields present too
        for f in (
            "search_summary", "search_keywords",
            "speakers", "speaker_count", "unresolved_speaker_count",
        ):
            assert f in r, f"missing new field {f}"
        # meeting_notes is NOT in search results (only in get_recordings full)
        assert "meeting_notes" not in r

    async def test_view_compact(self, client, test_db, test_user):
        await self._seed_one(test_db, test_user)
        resp = await client.get("/api/mcp/recordings", params={"view": "compact"})
        assert resp.status_code == 200
        r = resp.json()[0]
        # Compact: id + minimal triage fields, NO description / speaker_names
        assert "id" in r and "title" in r and "duration_seconds" in r
        assert "speakers" in r and "speaker_count" in r
        assert "description" not in r
        assert "speaker_names" not in r
        assert "search_summary" not in r
        assert "search_keywords" not in r
        assert "tag_ids" not in r

    async def test_view_summary(self, client, test_db, test_user):
        await self._seed_one(test_db, test_user)
        resp = await client.get("/api/mcp/recordings", params={"view": "summary"})
        assert resp.status_code == 200
        r = resp.json()[0]
        for f in ("id", "title", "description", "search_summary", "tag_ids", "speakers"):
            assert f in r
        # Summary excludes search_keywords + speaker_names
        assert "search_keywords" not in r
        assert "speaker_names" not in r

    async def test_view_full_includes_keywords(self, client, test_db, test_user):
        await self._seed_one(test_db, test_user)
        resp = await client.get("/api/mcp/recordings", params={"view": "full"})
        r = resp.json()[0]
        assert "search_keywords" in r
        assert r["search_keywords"] == ["strategy", "ops"]
        assert "speaker_names" in r

    async def test_explicit_fields_overrides_view(self, client, test_db, test_user):
        await self._seed_one(test_db, test_user)
        resp = await client.get(
            "/api/mcp/recordings",
            params=[("view", "full"), ("fields", "title"), ("fields", "speakers")],
        )
        assert resp.status_code == 200
        r = resp.json()[0]
        # `id` always included; title + speakers explicit; everything else excluded
        assert set(r.keys()) == {"id", "title", "speakers"}

    async def test_unknown_field_returns_400(self, client, test_db, test_user):
        await self._seed_one(test_db, test_user)
        resp = await client.get(
            "/api/mcp/recordings", params={"fields": "summery"},
        )
        assert resp.status_code == 400
        assert "summery" in resp.json()["detail"]
        assert "Valid:" in resp.json()["detail"] or "valid" in resp.json()["detail"].lower()

    async def test_invalid_view_returns_400(self, client, test_db, test_user):
        await self._seed_one(test_db, test_user)
        resp = await client.get("/api/mcp/recordings", params={"view": "tiny"})
        assert resp.status_code == 400


# ===========================================================================
# search_recordings — structured speakers + counts
# ===========================================================================


class TestSearchSpeakers:
    async def test_structured_speakers_and_counts(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        mapping = json.dumps({
            "Speaker 1": {"displayName": "Alice", "participantId": "p-alice"},
            "Speaker 2": {"displayName": "Bob", "participantId": None},
            "Speaker 3": {"displayName": "Carol", "participantId": "p-carol"},
        })
        await _insert_recording(
            test_db, test_user.id, rid, "Three Speakers",
            speaker_mapping=mapping,
        )
        resp = await client.get("/api/mcp/recordings")
        r = resp.json()[0]
        assert r["speaker_count"] == 3
        assert r["unresolved_speaker_count"] == 1
        labels = {s["label"] for s in r["speakers"]}
        assert labels == {"Speaker 1", "Speaker 2", "Speaker 3"}
        names = {s["display_name"] for s in r["speakers"]}
        assert names == {"Alice", "Bob", "Carol"}
        # Backwards-compat: speaker_names still has all three names
        assert set(r["speaker_names"]) == {"Alice", "Bob", "Carol"}

    async def test_malformed_speaker_mapping_safe(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid, "Broken",
            speaker_mapping="not-json-at-all",
        )
        resp = await client.get("/api/mcp/recordings")
        assert resp.status_code == 200
        r = resp.json()[0]
        # Defined behavior: zero speakers, empty list, no crash
        assert r["speakers"] == []
        assert r["speaker_count"] == 0
        assert r["unresolved_speaker_count"] == 0
        assert r["speaker_names"] == []

    async def test_non_dict_speaker_mapping_safe(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid, "List Mapping",
            speaker_mapping=json.dumps(["foo", "bar"]),
        )
        resp = await client.get("/api/mcp/recordings")
        assert resp.status_code == 200
        r = resp.json()[0]
        assert r["speakers"] == []
        assert r["speaker_count"] == 0


# ===========================================================================
# search_recordings — pagination envelope
# ===========================================================================


class TestSearchPagination:
    async def _seed_n(self, db, user_id, n, base_date="2024-01-01T00:00:00+00:00"):
        # Distinct timestamps so ordering is deterministic
        from datetime import datetime as _dt, timedelta as _td
        base = _dt.fromisoformat(base_date)
        for i in range(n):
            rid = str(uuid.uuid4())
            await _insert_recording(
                db, user_id, rid, f"Rec {i}",
                recorded_at=(base + _td(minutes=i)).isoformat(),
            )

    async def test_paginated_envelope_shape(self, client, test_db, test_user):
        await self._seed_n(test_db, test_user.id, 5)
        resp = await client.get(
            "/api/mcp/recordings",
            params={"paginated": "true", "limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        env = resp.json()
        assert isinstance(env, dict)
        assert set(["results", "limit", "offset", "has_more", "next_offset", "total"]).issubset(env.keys())
        assert env["limit"] == 2
        assert env["offset"] == 0
        assert env["has_more"] is True
        assert env["next_offset"] == 2
        assert env["total"] == 5  # non-cascade → total computed
        assert len(env["results"]) == 2

    async def test_paginated_last_page_has_more_false(self, client, test_db, test_user):
        await self._seed_n(test_db, test_user.id, 3)
        resp = await client.get(
            "/api/mcp/recordings",
            params={"paginated": "true", "limit": 2, "offset": 2},
        )
        env = resp.json()
        assert env["has_more"] is False
        assert env["next_offset"] is None
        assert len(env["results"]) == 1

    async def test_paginated_exact_fit(self, client, test_db, test_user):
        await self._seed_n(test_db, test_user.id, 4)
        resp = await client.get(
            "/api/mcp/recordings",
            params={"paginated": "true", "limit": 2, "offset": 2},
        )
        env = resp.json()
        # Page is exactly the last 2 → has_more should be False
        assert env["has_more"] is False
        assert len(env["results"]) == 2

    async def test_paginated_default_false_returns_bare_list(
        self, client, test_db, test_user
    ):
        await self._seed_n(test_db, test_user.id, 2)
        resp = await client.get("/api/mcp/recordings")
        body = resp.json()
        # Regression guard: default response is a list, not an envelope
        assert isinstance(body, list)

    async def test_paginated_cascade_total_is_null(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid, "Widgets")
        resp = await client.get(
            "/api/mcp/recordings",
            params={"paginated": "true", "query": "widgets", "mode": "cascade"},
        )
        env = resp.json()
        assert env["total"] is None  # cascade total deferred


# ===========================================================================
# search_recordings — tag filter
# ===========================================================================


class TestSearchTagFilter:
    async def test_filter_by_single_tag(self, client, test_db, test_user):
        tag_a, tag_b = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_tag(test_db, test_user.id, tag_a, "alpha")
        await _insert_tag(test_db, test_user.id, tag_b, "beta")

        rid_a, rid_b = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid_a, "Has Alpha")
        await _insert_recording(test_db, test_user.id, rid_b, "Has Beta")
        await _attach_tag(test_db, rid_a, tag_a)
        await _attach_tag(test_db, rid_b, tag_b)

        resp = await client.get(
            "/api/mcp/recordings", params=[("tag_id", tag_a)],
        )
        ids = [r["id"] for r in resp.json()]
        assert rid_a in ids and rid_b not in ids

    async def test_filter_tag_match_any(self, client, test_db, test_user):
        tag_a, tag_b = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_tag(test_db, test_user.id, tag_a, "alpha")
        await _insert_tag(test_db, test_user.id, tag_b, "beta")
        rid_a, rid_b, rid_c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid_a, "A only")
        await _insert_recording(test_db, test_user.id, rid_b, "B only")
        await _insert_recording(test_db, test_user.id, rid_c, "Neither")
        await _attach_tag(test_db, rid_a, tag_a)
        await _attach_tag(test_db, rid_b, tag_b)

        resp = await client.get(
            "/api/mcp/recordings",
            params=[("tag_id", tag_a), ("tag_id", tag_b), ("tag_match", "any")],
        )
        ids = set(r["id"] for r in resp.json())
        assert rid_a in ids and rid_b in ids and rid_c not in ids

    async def test_filter_tag_match_all(self, client, test_db, test_user):
        tag_a, tag_b = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_tag(test_db, test_user.id, tag_a, "alpha")
        await _insert_tag(test_db, test_user.id, tag_b, "beta")
        rid_a, rid_ab = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid_a, "A only")
        await _insert_recording(test_db, test_user.id, rid_ab, "Both")
        await _attach_tag(test_db, rid_a, tag_a)
        await _attach_tag(test_db, rid_ab, tag_a)
        await _attach_tag(test_db, rid_ab, tag_b)

        resp = await client.get(
            "/api/mcp/recordings",
            params=[("tag_id", tag_a), ("tag_id", tag_b), ("tag_match", "all")],
        )
        ids = set(r["id"] for r in resp.json())
        assert rid_ab in ids and rid_a not in ids

    async def test_other_users_tag_no_leak(
        self, client, test_db, test_user, other_user
    ):
        # Other user's tag attached to other user's recording
        other_tag = str(uuid.uuid4())
        await _insert_tag(test_db, other_user.id, other_tag, "secret")
        other_rid = str(uuid.uuid4())
        await _insert_recording(test_db, other_user.id, other_rid, "Theirs")
        await _attach_tag(test_db, other_rid, other_tag)

        # Authenticated as test_user, filter by their tag → no results
        resp = await client.get(
            "/api/mcp/recordings", params=[("tag_id", other_tag)],
        )
        assert resp.json() == []


# ===========================================================================
# search_recordings — sort
# ===========================================================================


class TestSearchSort:
    async def test_sort_duration_desc_non_cascade(
        self, client, test_db, test_user
    ):
        rid_short, rid_long = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid_short, "Short", duration_seconds=60.0,
        )
        await _insert_recording(
            test_db, test_user.id, rid_long, "Long", duration_seconds=3600.0,
        )
        resp = await client.get(
            "/api/mcp/recordings", params={"sort": "duration_desc"},
        )
        ids = [r["id"] for r in resp.json()]
        assert ids == [rid_long, rid_short]

    async def test_cascade_default_sort_preserves_tier_order(
        self, client, test_db, test_user
    ):
        # Three recordings: title-match, summary-match, transcript-match
        # Title match has the OLDEST recorded_at — but should come first
        # because cascade with default sort preserves tier order.
        rid_t = str(uuid.uuid4())
        rid_s = str(uuid.uuid4())
        rid_x = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid_t, "Widgets Discussion",
            recorded_at="2020-01-01T00:00:00+00:00",
        )
        await _insert_recording(
            test_db, test_user.id, rid_s, "Monday Sync",
            search_summary="widgets production",
            recorded_at="2024-06-01T00:00:00+00:00",
        )
        await _insert_recording(
            test_db, test_user.id, rid_x, "Random Chat",
            transcript_text="we shipped widgets to the factory",
            recorded_at="2025-01-01T00:00:00+00:00",
        )
        resp = await client.get(
            "/api/mcp/recordings", params={"query": "widgets", "mode": "cascade"},
        )
        ids = [r["id"] for r in resp.json()]
        assert ids[0] == rid_t  # title tier first
        assert ids[1] == rid_s  # summary tier second
        assert ids[2] == rid_x  # transcript tier third

    async def test_cascade_explicit_sort_flattens(
        self, client, test_db, test_user
    ):
        # With explicit sort=duration_desc, tier order should be ignored;
        # results should be sorted globally by duration. match_tier still
        # annotated on each row.
        rid_t = str(uuid.uuid4())  # title tier, short
        rid_x = str(uuid.uuid4())  # transcript tier, long
        await _insert_recording(
            test_db, test_user.id, rid_t, "Widgets Brief",
            duration_seconds=30.0,
        )
        await _insert_recording(
            test_db, test_user.id, rid_x, "Random Chat",
            transcript_text="we shipped widgets to the factory",
            duration_seconds=9000.0,
        )
        resp = await client.get(
            "/api/mcp/recordings",
            params={"query": "widgets", "mode": "cascade", "sort": "duration_desc"},
        )
        rows = resp.json()
        ids = [r["id"] for r in rows]
        assert ids == [rid_x, rid_t]  # global duration sort
        tier_map = {r["id"]: r.get("match_tier") for r in rows}
        assert tier_map[rid_t] == "title"
        assert tier_map[rid_x] == "transcript"

    async def test_cascade_flat_sort_puts_nulls_last_desc(
        self, client, test_db, test_user
    ):
        # Regression: when sorted column is NULL on some matched rows in
        # cascade-flat mode, NULLs must trail in BOTH directions.
        # Previously, reverse=True flipped the (None-trailing, val) tuple
        # trick and put nulls at the FRONT.
        rid_null = str(uuid.uuid4())
        rid_short = str(uuid.uuid4())
        rid_long = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid_null, "Widgets Null",
            duration_seconds=None,
        )
        await _insert_recording(
            test_db, test_user.id, rid_short, "Widgets Short",
            duration_seconds=60.0,
        )
        await _insert_recording(
            test_db, test_user.id, rid_long, "Widgets Long",
            duration_seconds=9000.0,
        )
        resp = await client.get(
            "/api/mcp/recordings",
            params={"query": "widgets", "mode": "cascade", "sort": "duration_desc"},
        )
        ids = [r["id"] for r in resp.json()]
        assert ids == [rid_long, rid_short, rid_null]

    async def test_cascade_flat_sort_puts_nulls_last_asc(
        self, client, test_db, test_user
    ):
        # Same regression as above, but for ascending — nulls should still
        # trail (a None-having row is "no signal", not "very small").
        rid_null = str(uuid.uuid4())
        rid_short = str(uuid.uuid4())
        rid_long = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid_null, "Widgets Null",
            duration_seconds=None,
        )
        await _insert_recording(
            test_db, test_user.id, rid_short, "Widgets Short",
            duration_seconds=60.0,
        )
        await _insert_recording(
            test_db, test_user.id, rid_long, "Widgets Long",
            duration_seconds=9000.0,
        )
        resp = await client.get(
            "/api/mcp/recordings",
            params={"query": "widgets", "mode": "cascade", "sort": "duration_asc"},
        )
        ids = [r["id"] for r in resp.json()]
        assert ids == [rid_short, rid_long, rid_null]


# ===========================================================================
# get_recordings (batch)
# ===========================================================================


class TestGetRecordingsBatch:
    async def test_happy_path_summary_view(self, client, test_db, test_user):
        rid1, rid2 = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid1, "First",
            description="d1", search_summary="ss1",
        )
        await _insert_recording(
            test_db, test_user.id, rid2, "Second",
            description="d2", search_summary="ss2",
        )
        resp = await client.post(
            "/api/mcp/recordings/batch",
            json={"recording_ids": [rid1, rid2]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["missing_ids"] == []
        # Default view=summary on this endpoint
        ids = [r["id"] for r in body["results"]]
        assert ids == [rid1, rid2]  # first-seen order preserved
        for r in body["results"]:
            assert "description" in r
            assert "search_summary" in r
            # summary view excludes meeting_notes and search_keywords
            assert "meeting_notes" not in r
            assert "search_keywords" not in r

    async def test_view_full_includes_meeting_notes(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid, "With Notes",
            meeting_notes="# Heavy markdown",
        )
        resp = await client.post(
            "/api/mcp/recordings/batch",
            json={"recording_ids": [rid], "view": "full"},
        )
        r = resp.json()["results"][0]
        assert r["meeting_notes"] == "# Heavy markdown"
        assert "meeting_notes_generated_at" in r

    async def test_explicit_fields_wins_over_view(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid, "X",
            description="d", search_summary="s",
            meeting_notes="should not appear",
        )
        resp = await client.post(
            "/api/mcp/recordings/batch",
            json={
                "recording_ids": [rid],
                "view": "full",  # would include meeting_notes
                "fields": ["title", "speakers"],  # but explicit fields wins
            },
        )
        r = resp.json()["results"][0]
        assert set(r.keys()) == {"id", "title", "speakers"}

    async def test_missing_ids_combined(self, client, test_db, test_user, other_user):
        rid_mine = str(uuid.uuid4())
        rid_theirs = str(uuid.uuid4())
        rid_nope = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid_mine, "Mine")
        await _insert_recording(test_db, other_user.id, rid_theirs, "Theirs")

        resp = await client.post(
            "/api/mcp/recordings/batch",
            json={"recording_ids": [rid_mine, rid_theirs, rid_nope]},
        )
        body = resp.json()
        assert [r["id"] for r in body["results"]] == [rid_mine]
        # Both other-user and nonexistent IDs combined into missing_ids
        assert set(body["missing_ids"]) == {rid_theirs, rid_nope}

    async def test_dedupe_preserves_first_seen_order(
        self, client, test_db, test_user
    ):
        rid1, rid2 = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid1, "First")
        await _insert_recording(test_db, test_user.id, rid2, "Second")
        resp = await client.post(
            "/api/mcp/recordings/batch",
            json={"recording_ids": [rid2, rid1, rid2, rid1]},
        )
        ids = [r["id"] for r in resp.json()["results"]]
        assert ids == [rid2, rid1]

    async def test_empty_list_returns_400(self, client):
        resp = await client.post(
            "/api/mcp/recordings/batch", json={"recording_ids": []},
        )
        # Pydantic min_length=1 → 422 (validation), our endpoint also has a
        # 400 fallback for the post-validation case. Either is acceptable —
        # we just need the bad request to be rejected.
        assert resp.status_code in (400, 422)

    async def test_more_than_50_returns_422(self, client):
        ids = [str(uuid.uuid4()) for _ in range(51)]
        resp = await client.post(
            "/api/mcp/recordings/batch", json={"recording_ids": ids},
        )
        assert resp.status_code == 422

    async def test_unknown_field_returns_400(self, client, test_db, test_user):
        rid = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid, "X")
        resp = await client.post(
            "/api/mcp/recordings/batch",
            json={"recording_ids": [rid], "fields": ["title", "summery"]},
        )
        assert resp.status_code == 400
        assert "summery" in resp.json()["detail"]


# ===========================================================================
# list_tags
# ===========================================================================


class TestListTags:
    async def test_basic(self, client, test_db, test_user):
        tag_a, tag_b = str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_tag(test_db, test_user.id, tag_a, "work", color="#0000ff")
        await _insert_tag(test_db, test_user.id, tag_b, "personal")

        resp = await client.get("/api/mcp/tags")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        names = [r["name"] for r in rows]
        assert names == sorted(names)  # ordered by name
        for r in rows:
            assert "id" in r and "name" in r and "color" in r
            assert r["recording_count"] == 0

    async def test_recording_count(self, client, test_db, test_user):
        tag_id = str(uuid.uuid4())
        await _insert_tag(test_db, test_user.id, tag_id, "important")
        rid1, rid2, rid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid1, "A")
        await _insert_recording(test_db, test_user.id, rid2, "B")
        await _insert_recording(test_db, test_user.id, rid3, "C")
        await _attach_tag(test_db, rid1, tag_id)
        await _attach_tag(test_db, rid2, tag_id)

        rows = (await client.get("/api/mcp/tags")).json()
        assert rows[0]["recording_count"] == 2

    async def test_other_users_tags_invisible(
        self, client, test_db, test_user, other_user
    ):
        await _insert_tag(test_db, other_user.id, str(uuid.uuid4()), "secret")
        await _insert_tag(test_db, test_user.id, str(uuid.uuid4()), "mine")
        rows = (await client.get("/api/mcp/tags")).json()
        names = [r["name"] for r in rows]
        assert "mine" in names and "secret" not in names

    async def test_recording_count_excludes_other_user_recordings(
        self, client, test_db, test_user, other_user
    ):
        # Tag belongs to test_user; an other_user recording manually attached
        # to that tag (only possible via direct DB write) must NOT inflate the
        # count for test_user. This is the defense-in-depth check on the
        # double-join through recordings.user_id = t.user_id.
        tag_id = str(uuid.uuid4())
        await _insert_tag(test_db, test_user.id, tag_id, "shared")

        rid_mine = str(uuid.uuid4())
        rid_theirs = str(uuid.uuid4())
        await _insert_recording(test_db, test_user.id, rid_mine, "Mine")
        await _insert_recording(test_db, other_user.id, rid_theirs, "Theirs")
        await _attach_tag(test_db, rid_mine, tag_id)
        await _attach_tag(test_db, rid_theirs, tag_id)

        rows = (await client.get("/api/mcp/tags")).json()
        assert rows[0]["recording_count"] == 1


# ===========================================================================
# Extended participant fields
# ===========================================================================


class TestParticipantsExtended:
    async def test_list_includes_new_fields(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(
            test_db, test_user.id, part_id, "Charlie",
            relationship="colleague", notes="Works on widgets",
            is_user=False,
            first_seen="2024-01-01T00:00:00+00:00",
            last_seen="2025-04-15T00:00:00+00:00",
        )
        resp = await client.get("/api/mcp/participants")
        rows = resp.json()
        c = next(p for p in rows if p["id"] == part_id)
        assert c["relationship"] == "colleague"
        assert c["notes"] == "Works on widgets"
        assert c["is_user"] is False
        assert c["first_seen"] == "2024-01-01T00:00:00+00:00"
        assert c["last_seen"] == "2025-04-15T00:00:00+00:00"

    async def test_search_includes_new_fields(self, client, test_db, test_user):
        part_id = str(uuid.uuid4())
        await _insert_participant(
            test_db, test_user.id, part_id, "Diana Search",
            relationship="manager", is_user=True,
        )
        resp = await client.get(
            "/api/mcp/participants/search", params={"query": "Diana"},
        )
        d = next(p for p in resp.json() if p["id"] == part_id)
        assert d["relationship"] == "manager"
        assert d["is_user"] is True

    async def test_list_recording_count_correct(self, client, test_db, test_user):
        # Single GROUP BY query must produce same count as old correlated
        # subquery. Two recordings both feature this participant.
        part_id = str(uuid.uuid4())
        await _insert_participant(test_db, test_user.id, part_id, "Eve")
        for _ in range(2):
            rid = str(uuid.uuid4())
            mapping = json.dumps({
                "Speaker 1": {"participantId": part_id, "displayName": "Eve"},
            })
            await _insert_recording(
                test_db, test_user.id, rid, "Sync", speaker_mapping=mapping,
            )
        # And one recording where this participant does NOT appear
        rid_other = str(uuid.uuid4())
        await _insert_recording(
            test_db, test_user.id, rid_other, "Solo",
            speaker_mapping=json.dumps({
                "Speaker 1": {"participantId": "other", "displayName": "X"},
            }),
        )
        rows = (await client.get("/api/mcp/participants")).json()
        eve = next(p for p in rows if p["id"] == part_id)
        assert eve["recording_count"] == 2
