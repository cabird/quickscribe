"""Tests for the detailed minutes service (turns, chunking, prompts, generation)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from app.services import minutes_service as ms


@pytest.fixture(autouse=True)
async def _patch_db_singleton(test_db):
    import app.database as db_mod

    original = db_mod._db
    db_mod._db = test_db
    yield
    db_mod._db = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phrase(speaker, start_ms, dur_ms, text, ticks=False):
    p = {"speaker": speaker, "nBest": [{"display": text}]}
    if ticks:
        p["offsetInTicks"] = start_ms * 10_000
        p["durationInTicks"] = dur_ms * 10_000
    else:
        p["offsetMilliseconds"] = start_ms
        p["durationMilliseconds"] = dur_ms
    return p


def _transcript(phrases):
    return json.dumps({"recognizedPhrases": phrases})


MAPPING = json.dumps({
    "Speaker 1": {"displayName": "Alice"},
    "Speaker 2": {"displayName": "Bob"},
})


def _response(content, prompt=100, completion=50, reasoning=10):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content), finish_reason="stop")],
        usage=SimpleNamespace(
            prompt_tokens=prompt, completion_tokens=completion,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning)),
    )


def _rate_limit_error():
    req = httpx.Request("POST", "https://example.invalid")
    return openai.RateLimitError(
        "rate limited", response=httpx.Response(429, request=req), body=None)


async def _insert(db, user_id, transcript_json, speaker_mapping=MAPPING, **extra):
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    cols = {
        "id": rec_id, "user_id": user_id, "title": "Weekly Sync",
        "original_filename": "sync.mp3", "source": "upload", "status": "ready",
        "transcript_json": transcript_json, "speaker_mapping": speaker_mapping,
        "duration_seconds": 600, "recorded_at": "2026-09-01T10:30:00",
        "created_at": now, "updated_at": now, **extra,
    }
    await db.execute(
        f"INSERT INTO recordings ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        tuple(cols.values()),
    )
    await db.commit()
    return rec_id


async def _row(db, rec_id):
    rows = await db.execute_fetchall("SELECT * FROM recordings WHERE id = ?", (rec_id,))
    return dict(rows[0])


def _mock_client(side_effect=None, return_value=None):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=side_effect, return_value=return_value)
    return client


SIMPLE = _transcript([
    _phrase(1, 0, 2000, "Let's start."),
    _phrase(2, 3000, 2000, "Budget is 40k."),
])


# ---------------------------------------------------------------------------
# Timestamps and turns
# ---------------------------------------------------------------------------


def test_ts_formats():
    assert ms.ts(0) == "00:00"
    assert ms.ts(65_000) == "01:05"
    assert ms.ts(59 * 60_000 + 59_999) == "59:59"
    assert ms.ts(3_600_000) == "1:00:00"
    assert ms.ts(3_723_000) == "1:02:03"


def test_parse_phrases_both_offset_forms_and_sorting():
    data = _transcript([
        _phrase(2, 5000, 1000, "second", ticks=True),
        _phrase(1, 1000, 2000, "first"),
        _phrase(1, 9000, 500, "   "),  # empty after strip: skipped
        {"speaker": 1, "offsetMilliseconds": 10_000, "nBest": []},  # no text: skipped
    ])
    out = ms.parse_phrases(data)
    assert [p["text"] for p in out] == ["first", "second"]
    assert out[1] == {"t_ms": 5000, "dur_ms": 1000, "speaker": "Speaker 2", "text": "second"}
    assert out[0] == {"t_ms": 1000, "dur_ms": 2000, "speaker": "Speaker 1", "text": "first"}


def test_speaker_names_mapping_and_fallback():
    names = ms.speaker_names(json.dumps({
        "Speaker 1": {"displayName": "Alice"},
        "Speaker 2": {"displayName": None},
        "Speaker 3": {},
    }))
    assert names == {"Speaker 1": "Alice", "Speaker 2": "Speaker 2", "Speaker 3": "Speaker 3"}
    assert ms.speaker_names(None) == {}
    assert ms.speaker_names("not json") == {}


def test_build_turns_uses_names_and_falls_back_to_label():
    phrases = ms.parse_phrases(_transcript([
        _phrase(1, 0, 1000, "Hi."),
        _phrase(3, 2000, 1000, "Hello."),
    ]))
    turns = ms.build_turns(phrases, {"Speaker 1": "Alice"})
    assert [t.line() for t in turns] == ["[00:00] Alice: Hi.", "[00:02] Speaker 3: Hello."]


def test_build_turns_merging_rules():
    phrases = ms.parse_phrases(_transcript([
        _phrase(1, 0, 1000, "a"),
        _phrase(1, 5000, 1000, "b"),      # gap 4s exactly: merged
        _phrase(1, 10_001, 1000, "c"),    # gap 4.001s: new turn
        _phrase(2, 11_500, 1000, "d"),    # other speaker: new turn
        _phrase(2, 12_500, 55_000, "e"),  # turn becomes 56s: merged
        _phrase(2, 68_500, 4000, "f"),    # turn would be 61s: new turn
    ]))
    turns = ms.build_turns(phrases, {})
    assert [(t.speaker, t.text) for t in turns] == [
        ("Speaker 1", "a b"), ("Speaker 1", "c"), ("Speaker 2", "d e"), ("Speaker 2", "f"),
    ]
    assert (turns[0].start_ms, turns[0].end_ms) == (0, 6000)


def test_build_turns_exactly_60s_merges():
    phrases = ms.parse_phrases(_transcript([
        _phrase(1, 0, 30_000, "a"),
        _phrase(1, 31_000, 29_000, "b"),  # turn ends at exactly 60,000 ms: merged
        _phrase(1, 61_000, 1000, "c"),    # 62s: new turn
    ]))
    turns = ms.build_turns(phrases, {})
    assert [(t.text, t.start_ms, t.end_ms) for t in turns] == [("a b", 0, 60_000), ("c", 61_000, 62_000)]


def test_turn_line_past_one_hour():
    t = ms.Turn(3_725_000, 3_726_000, "Alice", "Late point.")
    assert t.line() == "[1:02:05] Alice: Late point."


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _turns_of_tokens(n, words=40):
    return [ms.Turn(i * 10_000, i * 10_000 + 5000, "A", " ".join(["word"] * words))
            for i in range(n)]


def test_chunking_respects_budget_on_turn_boundaries():
    turns = _turns_of_tokens(60)
    per = ms.ntok(turns[0].line())
    chunks = ms.chunk_turns(turns, chunk_tokens=500)
    assert [t for c in chunks for t in c] == turns
    for c in chunks[:-1]:
        assert sum(ms.ntok(t.line()) for t in c) <= 500
    assert len(chunks[0]) == 500 // per


def test_chunking_folds_small_remainder():
    turns = _turns_of_tokens(10)
    per = ms.ntok(turns[0].line())
    budget = per * 4  # chunks of 4 turns; remainder of 2 turns = 1/2 -> kept
    assert [len(c) for c in ms.chunk_turns(turns, budget)] == [4, 4, 2]
    turns = _turns_of_tokens(9)  # remainder of 1 turn = 1/4 -> folded
    assert [len(c) for c in ms.chunk_turns(turns, budget)] == [4, 5]


def test_chunking_remainder_of_exactly_one_third_is_kept():
    turns = _turns_of_tokens(4)
    per = ms.ntok(turns[0].line())
    assert [len(c) for c in ms.chunk_turns(turns, per * 3)] == [3, 1]  # 1/3 is not < 1/3


def test_chunking_single_small_transcript():
    turns = _turns_of_tokens(2)
    assert ms.chunk_turns(turns) == [turns]
    assert ms.chunk_turns([]) == []


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _info():
    return ms.MeetingInfo("Weekly Sync", "2026-09-01T10:30:00", 10, ["Alice", "Bob"])


def test_first_chunk_message():
    turns = _turns_of_tokens(4)
    chunks = [turns[:2], turns[2:]]
    msg = ms.chunk_user_message(_info(), chunks, 0, [])
    assert msg.startswith(
        "# MEETING\nTitle: Weekly Sync\nDate: 2026-09-01 10:30\nDuration: 10 min\n"
        "Speakers (from voice matching, may be wrong): Alice, Bob\n\n")
    assert "# MINUTES SO FAR (read-only)\n(none: this is the first segment)\n\n" in msg
    assert "# RECENT CONTEXT (read-only, already covered above)\n(none)\n\n" in msg
    assert "# NEW SEGMENT 1 of 2: [00:00] to [00:15]\n" in msg


def test_second_chunk_has_minutes_so_far_and_recent_context():
    turns = [
        ms.Turn(0, 5000, "Alice", "old"),           # ends > 2 min before chunk end: dropped
        ms.Turn(130_000, 140_000, "Bob", "recent"),  # within last 2 min of prior turns
        ms.Turn(150_000, 160_000, "Alice", "new one"),
    ]
    chunks = [turns[:2], turns[2:]]
    msg = ms.chunk_user_message(_info(), chunks, 1, ["### [00:00] Kickoff\n- stuff"])
    assert "# MINUTES SO FAR (read-only)\n### [00:00] Kickoff\n- stuff\n\n" in msg
    assert "# RECENT CONTEXT (read-only, already covered above)\n[02:10] Bob: recent\n\n" in msg
    assert "old" not in msg
    assert msg.endswith("# NEW SEGMENT 2 of 2: [02:30] to [02:40]\n[02:30] Alice: new one\n")


def test_header_unlabelled_and_document_shape():
    info = ms.MeetingInfo("T", "", 3, [])
    assert "Speakers (from voice matching, may be wrong): (unlabelled)" in ms.header(info)
    doc = ms.assemble_document(_info(), "**Gist:** x", "### [00:00] A\n- b")
    assert doc == (
        "# Weekly Sync\n\n**Date:** 2026-09-01 10:30 · **Duration:** 10 min · "
        "**Speakers:** Alice, Bob\n\n**Gist:** x\n\n## Minutes\n\n### [00:00] A\n- b\n")


def test_prompts_render_verbatim():
    from app.prompts import render
    assert render("minutes_chunk").startswith("You are a note-taker writing dense minutes")
    assert "**Gist:**" in render("minutes_rollup")


# ---------------------------------------------------------------------------
# generate_minutes
# ---------------------------------------------------------------------------


def _minutes_settings():
    from app.config import Settings
    return Settings(azure_openai_minutes_deployment="minutes-dep", minutes_reasoning_effort="medium")


async def test_generate_success_writes_columns_and_meta(test_db, test_user):
    from app.prompts import render

    rec_id = await _insert(test_db, test_user.id, SIMPLE, detailed_minutes_error="old error",
                           detailed_minutes_status="failed", updated_at="2000-01-01 00:00:00")
    client = _mock_client(side_effect=[
        _response("### [00:00] Budget\n- Bob: budget 40k"),
        _response("**Gist:** budget set."),
    ])
    with patch.object(ms, "_get_client", return_value=client), \
            patch.object(ms, "get_settings", _minutes_settings):
        assert await ms.generate_minutes(rec_id, test_user.id) is True

    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "ready"
    assert row["detailed_minutes_error"] is None
    assert row["detailed_minutes_generated_at"]
    assert row["updated_at"] != "2000-01-01 00:00:00"
    doc = row["detailed_minutes"]
    assert doc.startswith("# Weekly Sync\n\n**Date:** 2026-09-01 10:30 · **Duration:** 10 min · "
                          "**Speakers:** Alice, Bob\n\n**Gist:** budget set.\n\n## Minutes\n\n")
    assert "- Bob: budget 40k" in doc

    meta = json.loads(row["detailed_minutes_meta"])
    assert meta["model"] == "minutes-dep"
    assert meta["effort"] == "medium"
    assert meta["prompts"] == ["minutes_chunk", "minutes_rollup"]
    assert meta["chunk_tokens"] == 2000
    assert meta["chunks"] == 1
    assert meta["prompt_tokens"] == 200
    assert meta["completion_tokens"] == 100
    assert meta["reasoning_tokens"] == 20
    assert meta["transcript_tokens"] > 0 and meta["minutes_tokens"] > 0
    assert "seconds" in meta

    calls = client.chat.completions.create.await_args_list
    assert len(calls) == 2
    kw = calls[0].kwargs
    assert kw["model"] == "minutes-dep"
    assert kw["reasoning_effort"] == "medium"
    assert kw["max_completion_tokens"] == 32000
    assert kw["messages"][0] == {"role": "system", "content": render("minutes_chunk")}
    assert calls[1].kwargs["messages"][0] == {"role": "system", "content": render("minutes_rollup")}
    assert "[00:00] Alice: Let's start.\n[00:03] Bob: Budget is 40k." in kw["messages"][1]["content"]
    assert "# MINUTES\n### [00:00] Budget" in calls[1].kwargs["messages"][1]["content"]
    client.close.assert_awaited()
    assert not ms.is_generating(rec_id)


async def test_generate_failure_keeps_previous_text(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, SIMPLE,
                           detailed_minutes="old minutes", detailed_minutes_status="ready",
                           detailed_minutes_meta='{"chunks": 9}',
                           detailed_minutes_generated_at="2026-01-01 00:00:00")
    client = _mock_client(side_effect=RuntimeError("boom"))
    with patch.object(ms, "_get_client", return_value=client):
        assert await ms.generate_minutes(rec_id, test_user.id) is False
    assert client.chat.completions.create.await_count == 1  # no retry on non-429

    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert "boom" in row["detailed_minutes_error"]
    assert row["detailed_minutes"] == "old minutes"
    assert row["detailed_minutes_meta"] == '{"chunks": 9}'
    assert row["detailed_minutes_generated_at"] == "2026-01-01 00:00:00"
    assert not ms.is_generating(rec_id)


async def test_generate_empty_transcript_fails(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, _transcript([]))
    with patch.object(ms, "_get_client") as get_client:
        assert await ms.generate_minutes(rec_id, test_user.id) is False
        get_client.assert_not_called()
    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert row["detailed_minutes_error"]


async def test_generate_wrong_user_or_missing_transcript(test_db, test_user, other_user):
    rec_id = await _insert(test_db, test_user.id, SIMPLE)
    no_tx = await _insert(test_db, test_user.id, None)
    with patch.object(ms, "_get_client") as get_client:
        assert await ms.generate_minutes(rec_id, other_user.id) is False
        assert await ms.generate_minutes(no_tx, test_user.id) is False
        assert await ms.generate_minutes("missing", test_user.id) is False
        get_client.assert_not_called()
    assert (await _row(test_db, rec_id))["detailed_minutes_status"] is None
    assert (await _row(test_db, no_tx))["detailed_minutes_status"] is None


async def test_concurrency_guard(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, SIMPLE)
    release = asyncio.Event()
    started = asyncio.Event()

    async def slow_create(**kwargs):
        started.set()
        await release.wait()
        return _response("x")

    client = _mock_client(side_effect=slow_create)
    with patch.object(ms, "_get_client", return_value=client):
        first = asyncio.create_task(ms.generate_minutes(rec_id, test_user.id))
        try:
            await asyncio.wait_for(started.wait(), 1)
            assert ms.is_generating(rec_id)
            assert (await _row(test_db, rec_id))["detailed_minutes_status"] == "generating"
            assert await asyncio.wait_for(ms.generate_minutes(rec_id, test_user.id), 1) is False
        finally:
            release.set()
        assert await asyncio.wait_for(first, 1) is True
    assert not ms.is_generating(rec_id)
    assert client.chat.completions.create.await_count == 2  # one chunk + rollup, once


async def test_rate_limit_retry_with_backoff(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, SIMPLE)
    client = _mock_client(side_effect=[
        _rate_limit_error(), _rate_limit_error(), _response("chunk"), _response("overview"),
    ])
    sleep = AsyncMock()
    with patch.object(ms, "_get_client", return_value=client), \
            patch.object(ms.asyncio, "sleep", sleep):
        assert await ms.generate_minutes(rec_id, test_user.id) is True
    assert [c.args[0] for c in sleep.await_args_list] == [20, 30]
    assert (await _row(test_db, rec_id))["detailed_minutes_status"] == "ready"


async def test_rate_limit_gives_up(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, SIMPLE)
    client = _mock_client(side_effect=_rate_limit_error())
    sleep = AsyncMock()
    with patch.object(ms, "_get_client", return_value=client), \
            patch.object(ms.asyncio, "sleep", sleep):
        assert await ms.generate_minutes(rec_id, test_user.id) is False
    assert client.chat.completions.create.await_count == ms.RATE_LIMIT_ATTEMPTS
    assert max(c.args[0] for c in sleep.await_args_list) == 90
    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert "RateLimitError" in row["detailed_minutes_error"]


async def test_migration_adds_columns():
    import aiosqlite
    from app.database import SCHEMA_SQL, _migrate_schema

    MINUTES_COLS = ("detailed_minutes", "detailed_minutes_generated_at", "detailed_minutes_status",
                    "detailed_minutes_error", "detailed_minutes_meta")

    db = await aiosqlite.connect(":memory:")
    try:
        await db.executescript(SCHEMA_SQL)
        for col in MINUTES_COLS:  # simulate a database from before this feature
            await db.execute(f"ALTER TABLE recordings DROP COLUMN {col}")
        await db.commit()
        await _migrate_schema(db)
        cols = {r[1] for r in await db.execute_fetchall("PRAGMA table_info(recordings)")}
    finally:
        await db.close()
    assert set(MINUTES_COLS) <= cols


# ---------------------------------------------------------------------------
# Review fixes: interruption, empty/truncated output, meta, bad JSON, chunk warning
# ---------------------------------------------------------------------------


async def test_startup_resets_generating_rows(test_db, test_user):
    from app.database import reset_interrupted_minutes

    stuck = await _insert(test_db, test_user.id, SIMPLE, detailed_minutes="old",
                          detailed_minutes_status="generating")
    ready = await _insert(test_db, test_user.id, SIMPLE, detailed_minutes_status="ready")
    assert await reset_interrupted_minutes(test_db) == 1
    row = await _row(test_db, stuck)
    assert row["detailed_minutes_status"] == "failed"
    assert row["detailed_minutes_error"] == "interrupted (server restart)"
    assert row["detailed_minutes"] == "old"
    assert (await _row(test_db, ready))["detailed_minutes_status"] == "ready"


async def test_init_db_migrates_then_resets(monkeypatch, tmp_path):
    """init_db on a pre-feature DB (no minutes columns, one recording) must migrate
    before resetting; a second startup resets a row left 'generating'."""
    import aiosqlite
    import app.database as db_mod
    from app.config import Settings

    path = tmp_path / "a.db"
    old = await aiosqlite.connect(str(path))
    try:
        # A pre-feature production DB: full schema (incl. FTS) minus the minutes columns.
        await old.executescript(db_mod.SCHEMA_SQL)
        await old.executescript(db_mod.FTS_SCHEMA_SQL)
        await old.executescript(db_mod.SEARCH_SCHEMA_SQL)
        for col in ("detailed_minutes", "detailed_minutes_generated_at", "detailed_minutes_status",
                    "detailed_minutes_error", "detailed_minutes_meta"):
            await old.execute(f"ALTER TABLE recordings DROP COLUMN {col}")
        await old.execute("INSERT INTO users (id, name) VALUES ('u1', 'U')")
        await old.execute(
            "INSERT INTO recordings (id, user_id, title, original_filename, source, status) "
            "VALUES ('r1', 'u1', 'T', 'f.mp3', 'upload', 'ready')")
        await old.commit()
    finally:
        await old.close()

    monkeypatch.setattr(db_mod, "get_settings", lambda: Settings(database_path=str(path)))
    db = None
    try:
        db = await db_mod.init_db()
        await db.execute("UPDATE recordings SET detailed_minutes_status = 'generating' WHERE id = 'r1'")
        await db.commit()
    finally:
        if db is not None:
            await db.close()

    db = None
    try:
        db = await db_mod.init_db()
        rows = await db.execute_fetchall(
            "SELECT detailed_minutes_status, detailed_minutes_error FROM recordings WHERE id = 'r1'")
        assert tuple(rows[0]) == ("failed", "interrupted (server restart)")
    finally:
        if db is not None:
            await db.close()


async def test_cancel_marks_failed_and_reraises(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, SIMPLE, detailed_minutes="old")
    started = asyncio.Event()

    async def hang(**kwargs):
        started.set()
        await asyncio.Event().wait()

    client = _mock_client(side_effect=hang)
    with patch.object(ms, "_get_client", return_value=client):
        task = asyncio.create_task(ms.generate_minutes(rec_id, test_user.id))
        try:
            await asyncio.wait_for(started.wait(), 1)
        finally:
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert row["detailed_minutes_error"] == "cancelled"
    assert row["detailed_minutes"] == "old"
    assert not ms.is_generating(rec_id)


@pytest.mark.parametrize("empty_at", [0, 1])  # chunk call, rollup call
async def test_empty_response_fails_run(test_db, test_user, empty_at):
    rec_id = await _insert(test_db, test_user.id, SIMPLE, detailed_minutes="old")
    responses = [_response("chunk"), _response("overview")]
    responses[empty_at] = _response("   ")
    client = _mock_client(side_effect=responses)
    with patch.object(ms, "_get_client", return_value=client):
        assert await ms.generate_minutes(rec_id, test_user.id) is False
    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert "empty LLM response" in row["detailed_minutes_error"]
    assert row["detailed_minutes"] == "old"


async def test_length_finish_reason_warns_but_keeps_text(test_db, test_user, caplog):
    rec_id = await _insert(test_db, test_user.id, SIMPLE)
    truncated = _response("partial chunk")
    truncated.choices[0].finish_reason = "length"
    client = _mock_client(side_effect=[truncated, _response("overview")])
    with patch.object(ms, "_get_client", return_value=client), caplog.at_level("WARNING"):
        assert await ms.generate_minutes(rec_id, test_user.id) is True
    assert "completion token limit" in caplog.text
    row = await _row(test_db, rec_id)
    assert "partial chunk" in row["detailed_minutes"]
    calls = json.loads(row["detailed_minutes_meta"])["calls"]
    assert calls[0]["finish_reason"] == "length"


async def test_meta_has_prompt_hash_and_calls(test_db, test_user):
    import hashlib
    from app.prompts import render

    rec_id = await _insert(test_db, test_user.id, SIMPLE)
    client = _mock_client(side_effect=[_response("chunk"), _response("overview", prompt=7)])
    with patch.object(ms, "_get_client", return_value=client):
        assert await ms.generate_minutes(rec_id, test_user.id) is True
    meta = json.loads((await _row(test_db, rec_id))["detailed_minutes_meta"])
    expected = hashlib.sha256(
        (render("minutes_chunk") + render("minutes_rollup")).encode()).hexdigest()[:12]
    assert meta["prompt_hash"] == expected
    assert [c["label"] for c in meta["calls"]] == ["chunk1", "rollup"]
    assert set(meta["calls"][1]) == {
        "label", "seconds", "prompt_tokens", "completion_tokens", "reasoning_tokens", "finish_reason"}
    assert meta["calls"][1]["prompt_tokens"] == 7


async def test_non_json_transcript_fails(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, "not json at all")
    with patch.object(ms, "_get_client") as get_client:
        assert await ms.generate_minutes(rec_id, test_user.id) is False
        get_client.assert_not_called()
    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert row["detailed_minutes_error"].startswith("JSONDecodeError")


@pytest.mark.parametrize("bad", ["[]", '{"foo": 1}', '{"recognizedPhrases": "x"}'])
async def test_bad_transcript_json_fails_clearly(test_db, test_user, bad):
    rec_id = await _insert(test_db, test_user.id, bad)
    with patch.object(ms, "_get_client") as get_client:
        assert await ms.generate_minutes(rec_id, test_user.id) is False
        get_client.assert_not_called()
    row = await _row(test_db, rec_id)
    assert row["detailed_minutes_status"] == "failed"
    assert "recognizedPhrases" in row["detailed_minutes_error"]
    with pytest.raises(ValueError):
        ms.parse_phrases(bad)


async def test_many_chunks_logs_warning(caplog, monkeypatch):
    monkeypatch.setattr(ms, "CHUNK_WARN_THRESHOLD", 2)
    monkeypatch.setattr(ms, "chunk_turns", lambda turns: [[t] for t in turns])
    turns = _turns_of_tokens(3)
    client = _mock_client(return_value=_response("x"))
    with caplog.at_level("WARNING"):
        await ms.run_pipeline(client, _info(), turns)
    assert "need 3 chunks" in caplog.text


async def test_chunks_at_threshold_no_warning(caplog, monkeypatch):
    monkeypatch.setattr(ms, "CHUNK_WARN_THRESHOLD", 3)
    monkeypatch.setattr(ms, "chunk_turns", lambda turns: [[t] for t in turns])
    client = _mock_client(return_value=_response("x"))
    with caplog.at_level("WARNING"):
        await ms.run_pipeline(client, _info(), _turns_of_tokens(3))
    assert "chunks" not in caplog.text


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------


async def test_title_and_duration_fallbacks(test_db, test_user):
    rec_id = await _insert(test_db, test_user.id, _transcript([
        _phrase(1, 0, 2000, "Hi."),
        _phrase(2, 170_000, 10_000, "Bye."),  # last turn ends at 3:00
    ]), title=None, duration_seconds=None)
    client = _mock_client(side_effect=[_response("chunk"), _response("overview")])
    with patch.object(ms, "_get_client", return_value=client):
        assert await ms.generate_minutes(rec_id, test_user.id) is True
    doc = (await _row(test_db, rec_id))["detailed_minutes"]
    assert doc.startswith("# sync.mp3\n\n**Date:** 2026-09-01 10:30 · **Duration:** 3 min · ")
    user = client.chat.completions.create.await_args_list[0].kwargs["messages"][1]["content"]
    assert "Title: sync.mp3\n" in user and "Duration: 3 min\n" in user
