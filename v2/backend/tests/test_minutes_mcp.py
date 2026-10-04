"""Tests for detailed minutes in MCP (get_minutes, get_transcript_window,
get_recording fields, synthesize preference) and in keyword search."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.auth import get_current_user_or_api_key
from app.config import Settings
from app.main import app
from app.routers import mcp_tools
from app.services import minutes_service, search_service


@pytest.fixture(autouse=True)
async def _override_api_key_auth(test_user):
    async def _override():
        return test_user

    app.dependency_overrides[get_current_user_or_api_key] = _override
    yield
    app.dependency_overrides.pop(get_current_user_or_api_key, None)


@pytest.fixture(autouse=True)
async def _patch_db_singleton(test_db):
    import app.database as db_mod

    original = db_mod._db
    db_mod._db = test_db
    yield
    db_mod._db = original


def _as_user(user):
    async def _override():
        return user

    app.dependency_overrides[get_current_user_or_api_key] = _override


MAPPING = json.dumps({
    "Speaker 1": {"displayName": "Alice", "participantId": "p-a"},
    "Speaker 2": {"displayName": "Bob", "participantId": "p-b"},
})


def _phrase(speaker: int, start_s: float, dur_s: float, text: str) -> dict:
    return {
        "speaker": speaker,
        "offsetMilliseconds": int(start_s * 1000),
        "durationMilliseconds": int(dur_s * 1000),
        "nBest": [{"display": text}],
    }


def _transcript(phrases: list[dict]) -> str:
    return json.dumps({"recognizedPhrases": phrases})


# Alternating speakers so each phrase is its own turn.
BASIC_PHRASES = [
    _phrase(1, 0, 5, "Welcome everyone."),
    _phrase(2, 10, 5, "Budget first."),
    _phrase(1, 70, 5, "Hiring update."),
    _phrase(2, 130, 5, "Roadmap next."),
    _phrase(1, 3725, 5, "Wrapping up after an hour."),
]

MINUTES_DOC = """# Weekly sync

**Date:** 2026-09-01 10:00 · **Duration:** 62 min · **Speakers:** Alice, Bob

**Gist:** Budget and hiring.

**Topics:** Budget [00:10]; Hiring [01:10]

### [99:99] Not a topic (overview area is ignored)

## Minutes

### [00:10] Budget
- Bob: budget first; zebracorn allocation 4M.

### [01:10] Hiring
- Alice: two hires.

### [02:10] (cont.) Budget
- Bob: revisit.

### [1:02:05] Wrap-up
- Alice: done.
"""


async def _insert(db, user_id, *, title="Weekly sync", transcript_json=None,
                  speaker_mapping=MAPPING, minutes=None, minutes_status=None,
                  minutes_error=None, minutes_meta=None, notes=None,
                  diarized="Speaker 1: raw transcript words", transcript_text=None,
                  status="ready"):
    rid = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO recordings
           (id, user_id, title, original_filename, source, status, diarized_text,
            transcript_text, transcript_json, speaker_mapping, meeting_notes, detailed_minutes,
            detailed_minutes_generated_at, detailed_minutes_status,
            detailed_minutes_error, detailed_minutes_meta, token_count)
           VALUES (?, ?, ?, 'f.mp3', 'upload', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1000)""",
        (rid, user_id, title, status, diarized, transcript_text, transcript_json, speaker_mapping,
         notes, minutes, "2026-09-01 11:00:00" if minutes else None,
         minutes_status, minutes_error, minutes_meta),
    )
    await db.commit()
    return rid


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    @pytest.mark.parametrize("text,ms", [
        ("00:00", 0), ("05:12", 312_000), ("5:12", 312_000), ("1:02:03", 3_723_000),
        ("75:00", 4_500_000), (" 01:10 ", 70_000),
    ])
    def test_parse_ts(self, text, ms):
        assert minutes_service.parse_ts(text) == ms

    @pytest.mark.parametrize("text", ["", "5", "05:60", "1:60:00", "aa:bb", "1:2:3:4", "-1:00"])
    def test_parse_ts_rejects(self, text):
        with pytest.raises(ValueError):
            minutes_service.parse_ts(text)

    def test_parse_ts_round_trips_ts(self):
        for ms in (0, 59_000, 600_000, 3_599_000, 3_600_000, 7_384_000):
            assert minutes_service.parse_ts(minutes_service.ts(ms)) == ms

    def test_parse_topics(self):
        topics = minutes_service.parse_topics(MINUTES_DOC)
        assert topics == [
            {"start_ms": 10_000, "timestamp": "00:10", "title": "Budget", "continued": False},
            {"start_ms": 70_000, "timestamp": "01:10", "title": "Hiring", "continued": False},
            {"start_ms": 130_000, "timestamp": "02:10", "title": "Budget", "continued": True},
            {"start_ms": 3_725_000, "timestamp": "1:02:05", "title": "Wrap-up", "continued": False},
        ]

    def test_parse_topics_without_minutes_heading_reads_whole_doc(self):
        assert [t["title"] for t in minutes_service.parse_topics("### [00:05] Only\n- x")] == ["Only"]

    def test_minutes_token_count_prefers_meta(self):
        assert minutes_service.minutes_token_count("abc", json.dumps({"minutes_tokens": 42})) == 42
        assert minutes_service.minutes_token_count("hello world", None) == minutes_service.ntok("hello world")
        assert minutes_service.minutes_token_count("hello", "not json") == minutes_service.ntok("hello")
        assert minutes_service.minutes_token_count(None, json.dumps({"minutes_tokens": 42})) is None


# ---------------------------------------------------------------------------
# get_minutes
# ---------------------------------------------------------------------------


class TestGetMinutes:
    async def test_with_minutes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC, minutes_status="ready",
                            minutes_meta=json.dumps({"minutes_tokens": 321}))
        resp = await client.get(f"/api/mcp/recordings/{rid}/minutes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recording_id"] == rid
        assert data["title"] == "Weekly sync"
        assert data["available"] is True
        assert data["status"] == "ready"
        assert data["minutes"] == MINUTES_DOC
        assert data["generated_at"] == "2026-09-01 11:00:00"
        assert data["token_count"] == 321
        assert data["message"] is None
        assert [t["timestamp"] for t in data["topics"]] == ["00:10", "01:10", "02:10", "1:02:05"]
        assert data["topics"][2]["continued"] is True

    async def test_token_count_computed_without_meta(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC, minutes_status="ready")
        data = (await client.get(f"/api/mcp/recordings/{rid}/minutes")).json()
        assert data["token_count"] == minutes_service.ntok(MINUTES_DOC)

    async def test_without_minutes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id)
        resp = await client.get(f"/api/mcp/recordings/{rid}/minutes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["minutes"] is None
        assert data["topics"] == []
        assert data["token_count"] is None
        assert "not available" in data["message"]
        assert "get_transcription" in data["message"]

    async def test_failed_includes_error(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes_status="failed",
                            minutes_error="RateLimitError: quota")
        data = (await client.get(f"/api/mcp/recordings/{rid}/minutes")).json()
        assert data["available"] is False
        assert data["status"] == "failed"
        assert data["error"] == "RateLimitError: quota"
        assert "failed" in data["message"]

    async def test_generating(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes_status="generating")
        data = (await client.get(f"/api/mcp/recordings/{rid}/minutes")).json()
        assert data["available"] is False
        assert data["status"] == "generating"
        assert "being generated" in data["message"]

    async def test_regenerating_keeps_existing_minutes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC, minutes_status="generating")
        data = (await client.get(f"/api/mcp/recordings/{rid}/minutes")).json()
        assert data["available"] is True
        assert data["minutes"] == MINUTES_DOC
        assert data["status"] == "generating"
        assert data["message"] is None
        assert len(data["topics"]) == 4

    async def test_other_user_gets_404(self, client, test_db, test_user, other_user):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC, minutes_status="ready")
        _as_user(other_user)
        resp = await client.get(f"/api/mcp/recordings/{rid}/minutes")
        assert resp.status_code == 404

    async def test_missing_recording_404(self, client):
        resp = await client.get(f"/api/mcp/recordings/{uuid.uuid4()}/minutes")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# get_transcript_window
# ---------------------------------------------------------------------------


class TestTranscriptWindow:
    async def _rec(self, db, user_id, phrases=BASIC_PHRASES):
        return await _insert(db, user_id, transcript_json=_transcript(phrases))

    async def test_range_with_timestamps(self, client, test_db, test_user):
        rid = await self._rec(test_db, test_user.id)
        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                params={"start": "00:10", "end": "01:10"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"].splitlines() == [
            "[00:10] Bob: Budget first.",
            "[01:10] Alice: Hiring update.",
        ]
        assert data["line_count"] == 2
        assert data["start"] == "00:10" and data["end"] == "01:10"
        assert data["covered_end"] == "01:15"
        assert data["truncated"] is False and data["next_start"] is None
        assert data["message"] is None
        assert data["tokens"] > 0

    async def test_range_with_seconds_and_hours(self, client, test_db, test_user):
        rid = await self._rec(test_db, test_user.id)
        data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                 params={"start": "3700", "end": "1:05:00"})).json()
        assert data["text"] == "[1:02:05] Alice: Wrapping up after an hour."
        assert data["start"] == "1:01:40"

    async def test_overlapping_turn_included(self, client, test_db, test_user):
        rid = await self._rec(test_db, test_user.id)
        # Bob's turn runs 10s-15s; a window starting at 12s still includes it.
        data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                 params={"start": "12", "end": "20"})).json()
        assert data["text"] == "[00:10] Bob: Budget first."

    async def test_timestamps_match_minutes_turns(self, client, test_db, test_user):
        rid = await self._rec(test_db, test_user.id)
        data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                 params={"start": 0, "end": "30:00"})).json()
        turns = minutes_service.transcript_turns(_transcript(BASIC_PHRASES), MAPPING)
        assert data["text"] == "\n".join(t.line() for t in turns[:4])
        assert data["truncated"] is False

    @pytest.mark.parametrize("start,end", [
        ("abc", "10"), ("10", "xyz"), ("05:60", "10:00"), ("-5", "10"), ("nan", "10"),
        ("10", "10"), ("20", "10"), ("01:00", "00:30"), ("inf", "10"),
        ("0", "1e306"), ("1e306", "1e307"), ("0", "10000001"), ("0", "9999999:00:00"),
    ])
    async def test_bad_input_400(self, client, test_db, test_user, start, end):
        rid = await self._rec(test_db, test_user.id)
        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                params={"start": start, "end": end})
        assert resp.status_code == 400

    async def test_duration_cap(self, client, test_db, test_user):
        phrases = [_phrase(1 + i % 2, i * 600, 5, f"Point {i}.") for i in range(10)]  # every 10 min
        rid = await self._rec(test_db, test_user.id, phrases)
        data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                 params={"start": "0", "end": "1:30:00"})).json()
        assert data["truncated"] is True
        assert "30 minutes" in data["truncated_reason"]
        assert data["end"] == "1:30:00"  # as requested
        assert data["covered_end"] == "30:05"
        assert data["line_count"] == 4  # 0, 10, 20, 30 min
        assert data["next_start"] == 2400.0

    async def test_duration_cap_without_more_content_is_not_truncated(self, client, test_db, test_user):
        rid = await self._rec(test_db, test_user.id)  # nothing between 02:15 and 1:02:05
        data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                 params={"start": "0", "end": "50:00"})).json()
        assert data["line_count"] == 4
        assert data["truncated"] is False and data["next_start"] is None

    async def test_token_cap(self, client, test_db, test_user):
        long_text = " ".join(["word"] * 400)
        phrases = [_phrase(1 + i % 2, i * 20, 5, long_text) for i in range(60)]
        rid = await self._rec(test_db, test_user.id, phrases)
        data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                 params={"start": "0", "end": "20:00"})).json()
        assert data["truncated"] is True
        assert "tokens" in data["truncated_reason"]
        assert data["tokens"] <= mcp_tools.TRANSCRIPT_WINDOW_MAX_TOKENS
        assert 0 < data["line_count"] < 60
        assert data["next_start"] == data["line_count"] * 20.0
        assert data["covered_end"] == minutes_service.ts((data["line_count"] - 1) * 20_000 + 5_000)

    async def test_past_end_of_recording(self, client, test_db, test_user):
        rid = await self._rec(test_db, test_user.id)
        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                params={"start": "2:00:00", "end": "2:10:00"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "" and data["line_count"] == 0
        assert data["covered_end"] is None
        assert data["recording_duration"] == "1:02:10"  # last turn end (no duration_seconds)
        assert "1:02:10" in data["message"]

    @pytest.mark.parametrize("end", ["1:00:00", "45:00"])
    async def test_paging_via_next_start_is_gap_and_duplicate_free(
        self, client, test_db, test_user, end,
    ):
        # Uneven, millisecond-precise offsets; a zero-length phrase; long
        # turns so the token cap triggers; back-to-back turns with no gap.
        long_text = " ".join(["word"] * 300)
        phrases, t = [], 0.0
        for i in range(120):
            dur = 0.0 if i == 7 else 3.3 + (i % 5) * 1.7
            phrases.append(_phrase(1 + i % 2, t, dur, f"P{i} " + (long_text if i % 3 == 0 else "short")))
            t = round(t + dur + (0 if i % 4 == 0 else 0.6 + (i % 7) * 0.317), 3)
        rid = await self._rec(test_db, test_user.id, phrases)
        expected = [x.line() for x in minutes_service.transcript_turns(_transcript(phrases), MAPPING)
                    if x.start_ms <= minutes_service.parse_ts(end)]

        got, start, pages = [], "0", 0
        while start is not None:
            data = (await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                     params={"start": start, "end": end})).json()
            got.extend(data["text"].splitlines())
            start = data["next_start"]
            pages += 1
            assert pages < 50
        assert pages > 1
        assert got == expected

    async def test_missing_recording_404(self, client):
        resp = await client.get(f"/api/mcp/recordings/{uuid.uuid4()}/transcript/window",
                                params={"start": "0", "end": "60"})
        assert resp.status_code == 404

    async def test_no_transcript_json(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, transcript_json=None)
        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                params={"start": "0", "end": "60"})
        assert resp.status_code == 400
        assert "get_transcription" in resp.json()["detail"]

    async def test_malformed_transcript_json(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, transcript_json=json.dumps({"x": 1}))
        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                params={"start": "0", "end": "60"})
        assert resp.status_code == 400

    async def test_other_user_gets_404(self, client, test_db, test_user, other_user):
        rid = await self._rec(test_db, test_user.id)
        _as_user(other_user)
        resp = await client.get(f"/api/mcp/recordings/{rid}/transcript/window",
                                params={"start": "0", "end": "60"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# get_recording fields
# ---------------------------------------------------------------------------


class TestGetRecordingMinutesFields:
    async def test_with_minutes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC, minutes_status="ready",
                            minutes_meta=json.dumps({"minutes_tokens": 77}))
        data = (await client.get(f"/api/mcp/recordings/{rid}")).json()
        assert data["has_minutes"] is True
        assert data["minutes_token_count"] == 77
        assert data["minutes_status"] == "ready"
        assert "detailed_minutes" not in data

    async def test_empty_minutes_is_not_has_minutes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes="")
        data = (await client.get(f"/api/mcp/recordings/{rid}")).json()
        assert data["has_minutes"] is False
        assert data["minutes_token_count"] is None
        resp = await client.post("/api/mcp/recordings/batch",
                                 json={"recording_ids": [rid], "view": "full"})
        assert resp.json()["results"][0]["has_minutes"] is False
        resp = await client.get("/api/mcp/recordings", params={"fields": ["has_minutes"]})
        assert resp.json()[0]["has_minutes"] is False

    @pytest.mark.parametrize("view", [None, "compact", "summary", "full"])
    async def test_has_minutes_in_view_presets(self, client, test_db, test_user, view):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC)
        params = {"view": view} if view else {}
        rows = (await client.get("/api/mcp/recordings", params=params)).json()
        assert rows[0]["has_minutes"] is True
        body = {"recording_ids": [rid], **({"view": view} if view else {})}
        rows = (await client.post("/api/mcp/recordings/batch", json=body)).json()["results"]
        assert rows[0]["has_minutes"] is True

    async def test_has_minutes_in_bulk_and_search_projection(self, client, test_db, test_user):
        with_m = await _insert(test_db, test_user.id, minutes=MINUTES_DOC)
        without = await _insert(test_db, test_user.id)
        resp = await client.post("/api/mcp/recordings/batch",
                                 json={"recording_ids": [with_m, without], "view": "compact"})
        assert resp.status_code == 200
        flags = {r["id"]: r["has_minutes"] for r in resp.json()["results"]}
        assert flags == {with_m: True, without: False}

        resp = await client.get("/api/mcp/recordings", params={"fields": ["title", "has_minutes"]})
        assert resp.status_code == 200
        flags = {r["id"]: r["has_minutes"] for r in resp.json()}
        assert flags == {with_m: True, without: False}

    async def test_without_minutes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes_status="failed")
        data = (await client.get(f"/api/mcp/recordings/{rid}")).json()
        assert data["has_minutes"] is False
        assert data["minutes_token_count"] is None
        assert data["minutes_status"] == "failed"


# ---------------------------------------------------------------------------
# synthesize_recordings preference
# ---------------------------------------------------------------------------


class TestSynthesizePreference:
    async def _texts(self, client, rid):
        with patch.object(Settings, "ai_enabled", new_callable=PropertyMock, return_value=True), \
             patch("app.services.ai_service.synthesize", new_callable=AsyncMock,
                   return_value=MagicMock(message="ok", usage={}, response_time_ms=1)) as synth:
            resp = await client.post("/api/mcp/synthesize",
                                     json={"recording_ids": [rid], "question": "q?"})
        assert resp.status_code == 200
        return synth.call_args.kwargs["recordings"][0]["text"]

    async def test_minutes_over_notes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes="MINUTES TEXT", notes="NOTES TEXT")
        assert await self._texts(client, rid) == "MINUTES TEXT"

    async def test_notes_over_transcript(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, notes="NOTES TEXT")
        assert await self._texts(client, rid) == "NOTES TEXT"

    async def test_minutes_over_diarized_without_notes(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes="MINUTES TEXT")
        assert await self._texts(client, rid) == "MINUTES TEXT"

    async def test_diarized_fallback(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, transcript_text="PLAIN TEXT")
        assert await self._texts(client, rid) == "Speaker 1: raw transcript words"

    async def test_plain_transcript_fallback(self, client, test_db, test_user):
        rid = await _insert(test_db, test_user.id, diarized=None, transcript_text="PLAIN TEXT")
        assert await self._texts(client, rid) == "PLAIN TEXT"


# ---------------------------------------------------------------------------
# Keyword search over minutes
# ---------------------------------------------------------------------------


async def _search_ids(user_id, q):
    return [r.id for r in (await search_service.search(user_id, q)).data]


class TestMinutesSearch:
    async def test_phrase_only_in_minutes_is_found(self, test_db, test_user):
        rid = await _insert(test_db, test_user.id, minutes=MINUTES_DOC)
        await _insert(test_db, test_user.id)  # no minutes
        assert await _search_ids(test_user.id, "zebracorn ") == [rid]
        assert await _search_ids(test_user.id, '"zebracorn allocation"') == [rid]

    async def test_index_follows_minutes_updates(self, test_db, test_user):
        rid = await _insert(test_db, test_user.id)
        assert await _search_ids(test_user.id, "quokkaplan ") == []

        await test_db.execute("UPDATE recordings SET detailed_minutes = ? WHERE id = ?",
                              ("## Minutes\n- quokkaplan agreed", rid))
        await test_db.commit()
        assert await _search_ids(test_user.id, "quokkaplan ") == [rid]

        await test_db.execute("UPDATE recordings SET detailed_minutes = ? WHERE id = ?",
                              ("## Minutes\n- something else", rid))
        await test_db.commit()
        assert await _search_ids(test_user.id, "quokkaplan ") == []
        assert await _search_ids(test_user.id, "something ") == [rid]

        await test_db.execute("UPDATE recordings SET detailed_minutes = NULL WHERE id = ?", (rid,))
        await test_db.commit()
        assert await _search_ids(test_user.id, "quokkaplan ") == []
        assert await _search_ids(test_user.id, "something ") == []

    async def test_minutes_only_phrase_is_user_scoped(self, test_db, test_user, other_user):
        mine = await _insert(test_db, test_user.id, minutes=MINUTES_DOC)
        await _insert(test_db, other_user.id, minutes=MINUTES_DOC)
        assert await _search_ids(test_user.id, "zebracorn ") == [mine]
        await test_db.execute("DELETE FROM recordings WHERE id = ?", (mine,))
        await test_db.commit()
        assert await _search_ids(test_user.id, "zebracorn ") == []

    def test_weights_match_columns(self):
        from app.database import SEARCH_INDEX_COLUMNS

        assert len(search_service.BM25_WEIGHTS) == len(SEARCH_INDEX_COLUMNS)
        i = SEARCH_INDEX_COLUMNS.index("minutes")
        assert SEARCH_INDEX_COLUMNS[i + 1:] == ("transcript",)
        assert search_service.BM25_WEIGHTS[i] == 1.0
