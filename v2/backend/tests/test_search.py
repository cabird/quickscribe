"""Tests for fast keyword search (search_service) and its FTS indexes."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import aiosqlite
import pytest

from app.database import _ensure_search_index
from app.services import search_service
from app.services.search_service import HL_END, HL_START, _name_matches, parse_query


# ---------------------------------------------------------------------------
# Query parsing
# ---------------------------------------------------------------------------


class TestParseQuery:
    def test_words_are_all_required_and_last_is_prefix(self):
        p = parse_query("dryden pat")
        assert p.words == ["dryden", "pat"] and p.prefix_last_word

    def test_trailing_space_disables_prefix(self):
        assert not parse_query("dryden ").prefix_last_word

    def test_single_char_last_word_is_not_prefix(self):
        assert not parse_query("dryden p").prefix_last_word

    def test_phrases_exclusions_and_people(self):
        p = parse_query('"claim construction" -billing -"status update" @car person:"chris b" x')
        assert p.phrases == ["claim construction"]
        assert p.exclude_words == ["billing"]
        assert p.exclude_phrases == ["status update"]
        assert p.people == ["car", "chris b"]
        assert p.words == ["x"]

    def test_unterminated_quote_runs_to_end(self):
        assert parse_query('dryden "claim constr').phrases == ["claim constr"]

    def test_phrase_last_is_not_prefix(self):
        assert not parse_query('"patent"').prefix_last_word

    @pytest.mark.parametrize("q", ["", "   ", "-", "@", '""', "- @ \"\""])
    def test_empty_ish(self, q):
        p = parse_query(q)
        assert not p.has_text and not p.people


class TestNameMatching:
    @pytest.mark.parametrize(
        "term,names,expected",
        [
            ("car", ["Carmen"], True),
            ("car", ["Carmichael"], True),
            ("car", ["Fred Carson"], True),
            ("car", ["Oscar Wilde"], False),  # prefix of a word, not substring
            ("chris b", ["Chris Bird"], True),
            ("chris b", ["Chris White"], False),
            ("bird", ["Me", "Christian Bird"], True),
        ],
    )
    def test_prefix_of_any_name_word(self, term, names, expected):
        assert _name_matches(term, names) is expected


# ---------------------------------------------------------------------------
# Search against a real (in-memory) database
# ---------------------------------------------------------------------------


@pytest.fixture
async def db(test_db: aiosqlite.Connection):
    with patch("app.database._db", test_db):
        yield test_db


async def _participant(db, user_id, display, first="", last="", aliases=()):
    pid = f"p-{uuid.uuid4()}"
    await db.execute(
        """INSERT INTO participants (id, user_id, display_name, first_name, last_name, aliases)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (pid, user_id, display, first, last, json.dumps(list(aliases))),
    )
    await db.commit()
    return pid


async def _recording(db, user_id, *, title="", transcript="", summary=None, notes=None,
                     speakers=None, recorded_at="2026-09-01T10:00:00", status="ready"):
    rid = f"r-{uuid.uuid4()}"
    mapping = (
        json.dumps({f"Speaker {i + 1}": {"participantId": pid, "displayName": name}
                    for i, (pid, name) in enumerate(speakers)})
        if speakers else None
    )
    await db.execute(
        """INSERT INTO recordings (id, user_id, title, original_filename, source, status,
                                   diarized_text, search_summary, meeting_notes,
                                   speaker_mapping, recorded_at)
           VALUES (?, ?, ?, 'f.mp3', 'upload', ?, ?, ?, ?, ?, ?)""",
        (rid, user_id, title, status, transcript, summary, notes, mapping, recorded_at),
    )
    await db.commit()
    return rid


async def _ids(user_id, q, **kw):
    return [r.id for r in (await search_service.search(user_id, q, **kw)).data]


class TestSearch:
    async def test_all_terms_required(self, db, test_user):
        both = await _recording(db, test_user.id, transcript="dryden patent case")
        await _recording(db, test_user.id, transcript="dryden only")
        assert await _ids(test_user.id, "dryden patent ") == [both]

    async def test_stemming(self, db, test_user):
        rid = await _recording(db, test_user.id, transcript="we are litigating this")
        assert await _ids(test_user.id, "litigation ") == [rid]

    async def test_quotes_are_exact(self, db, test_user):
        exact = await _recording(db, test_user.id, transcript="the litigation started")
        await _recording(db, test_user.id, transcript="we are litigating this")
        assert await _ids(test_user.id, '"litigation"') == [exact]

    async def test_prefix_while_typing(self, db, test_user):
        rid = await _recording(db, test_user.id, transcript="claim construction hearing")
        assert await _ids(test_user.id, "construc") == [rid]
        assert await _ids(test_user.id, "construc ") == []

    async def test_exclusions(self, db, test_user):
        keep = await _recording(db, test_user.id, transcript="dryden patent")
        await _recording(db, test_user.id, transcript="dryden billing")
        await _recording(db, test_user.id, transcript="dryden status update")
        assert await _ids(test_user.id, 'dryden -billing -"status update"') == [keep]

    async def test_title_outranks_transcript(self, db, test_user):
        body = await _recording(db, test_user.id, title="Weekly sync", transcript="mediation " * 3)
        titled = await _recording(db, test_user.id, title="Mediation planning", transcript="hello")
        assert await _ids(test_user.id, "mediation ") == [titled, body]

    async def test_meeting_notes_and_summary_are_searched(self, db, test_user):
        notes = await _recording(db, test_user.id, notes="# Decisions\n- hire an associate")
        summ = await _recording(db, test_user.id, summary="Discussion of associate onboarding")
        assert set(await _ids(test_user.id, "associate ")) == {notes, summ}

    async def test_people_prefix_matches_any_name_word(self, db, test_user):
        carmen = await _participant(db, test_user.id, "Carmen", "Carmen", "Lee")
        carson = await _participant(db, test_user.id, "Fred Carson", "Fred", "Carson")
        oscar = await _participant(db, test_user.id, "Oscar")
        r1 = await _recording(db, test_user.id, transcript="budget", speakers=[(carmen, "Carmen")])
        r2 = await _recording(db, test_user.id, transcript="budget", speakers=[(carson, "Fred Carson")])
        await _recording(db, test_user.id, transcript="budget", speakers=[(oscar, "Oscar")])

        res = await search_service.search(test_user.id, "@car budget ")
        assert {r.id for r in res.data} == {r1, r2}
        assert sorted(res.people[0].names) == ["Carmen", "Fred Carson"]

    async def test_every_person_term_must_match(self, db, test_user):
        a = await _participant(db, test_user.id, "Carmen")
        b = await _participant(db, test_user.id, "Tom")
        both = await _recording(db, test_user.id, transcript="x", speakers=[(a, "Carmen"), (b, "Tom")])
        await _recording(db, test_user.id, transcript="x", speakers=[(a, "Carmen")])
        assert await _ids(test_user.id, "@carmen @tom") == [both]

    async def test_unknown_person_means_no_results(self, db, test_user):
        await _recording(db, test_user.id, transcript="budget")
        res = await search_service.search(test_user.id, "@nobody budget")
        assert res.data == [] and res.people[0].participant_ids == []

    async def test_aliases_match(self, db, test_user):
        me = await _participant(db, test_user.id, "Chris", "Christian", "Bird", ["cbird"])
        rid = await _recording(db, test_user.id, transcript="x", speakers=[(me, "Chris")])
        assert await _ids(test_user.id, "@cbi") == [rid]

    async def test_pinned_person_ids(self, db, test_user):
        a = await _participant(db, test_user.id, "Carmen")
        b = await _participant(db, test_user.id, "Carmichael")
        ra = await _recording(db, test_user.id, transcript="x", speakers=[(a, "Carmen")])
        await _recording(db, test_user.id, transcript="x", speakers=[(b, "Carmichael")])
        assert await _ids(test_user.id, "", person_ids=[a]) == [ra]

    async def test_snippets_highlight_and_name_speakers(self, db, test_user):
        p = await _participant(db, test_user.id, "Dan Delorey")
        await _recording(
            db, test_user.id, title="Patent meeting",
            transcript="Speaker 1: the patent inventor gets to serve as a witness",
            speakers=[(p, "Dan Delorey")],
        )
        hit = (await search_service.search(test_user.id, "patent ")).data[0]
        assert hit.title_highlight == f"{HL_START}Patent{HL_END} meeting"
        assert any("Dan Delorey" in s and f"{HL_START}patent{HL_END}" in s for s in hit.snippets)

    async def test_other_users_and_unready_are_excluded(self, db, test_user, other_user):
        await _recording(db, other_user.id, transcript="dryden")
        pending = await _recording(db, test_user.id, transcript="dryden", status="transcribing")
        assert await _ids(test_user.id, "dryden ") == []
        assert await _ids(test_user.id, "dryden ", ready_only=False) == [pending]

    @pytest.mark.parametrize(
        "q", ['NOT', 'AND OR', '"', '*', 'a" OR "b', 'x:y', "col:title", "(", "^start", "NEAR(a b)"]
    )
    async def test_hostile_input_never_errors(self, db, test_user, q):
        await _recording(db, test_user.id, transcript="not and or near title start")
        await search_service.search(test_user.id, q)  # must not raise

    async def test_filter_only_search_orders_newest_first(self, db, test_user):
        p = await _participant(db, test_user.id, "Carmen")
        old = await _recording(db, test_user.id, speakers=[(p, "Carmen")], recorded_at="2026-01-01")
        new = await _recording(db, test_user.id, speakers=[(p, "Carmen")], recorded_at="2026-09-01")
        assert await _ids(test_user.id, "@carmen") == [new, old]

    async def test_pagination_total(self, db, test_user):
        for _ in range(5):
            await _recording(db, test_user.id, transcript="dryden")
        res = await search_service.search(test_user.id, "dryden ", limit=2, offset=2)
        assert len(res.data) == 2 and res.total == 5


class TestIndexSync:
    async def test_update_and_delete_keep_index_in_sync(self, db, test_user):
        rid = await _recording(db, test_user.id, title="Patent talk")
        await db.execute("UPDATE recordings SET title = 'Budget review' WHERE id = ?", (rid,))
        await db.commit()
        assert await _ids(test_user.id, "patent ") == []
        assert await _ids(test_user.id, "budget ") == [rid]

        # Unrelated column updates don't touch the index
        await db.execute("UPDATE recordings SET status = 'ready' WHERE id = ?", (rid,))
        await db.commit()
        assert await _ids(test_user.id, "budget ") == [rid]

        await db.execute("DELETE FROM recordings WHERE id = ?", (rid,))
        await db.commit()
        assert await _ids(test_user.id, "budget ") == []
        for table in ("search_fts", "search_exact_fts"):
            await db.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")

    async def test_speaker_mapping_change_reindexes_speaker_names(self, db, test_user):
        rid = await _recording(db, test_user.id, transcript="x")
        mapping = json.dumps({"Speaker 1": {"participantId": "p", "displayName": "Carmen Lee"}})
        await db.execute("UPDATE recordings SET speaker_mapping = ? WHERE id = ?", (mapping, rid))
        await db.commit()
        assert await _ids(test_user.id, "carmen ") == [rid]

    async def test_malformed_speaker_mapping_is_tolerated(self, db, test_user):
        rid = await _recording(db, test_user.id, transcript="dryden")
        await db.execute(
            "UPDATE recordings SET speaker_mapping = ? WHERE id = ?",
            ('{"Speaker 1": "Carmen"}', rid),
        )
        await db.execute("UPDATE recordings SET speaker_mapping = 'not json' WHERE id = ?", (rid,))
        await db.commit()
        assert await _ids(test_user.id, "dryden ") == [rid]


async def test_existing_database_gets_index_built():
    """A database from before the search index existed is indexed on startup."""
    from app.database import FTS_SCHEMA_SQL, SCHEMA_SQL

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA_SQL)
    await db.executescript(FTS_SCHEMA_SQL)
    await db.execute("INSERT INTO users (id) VALUES ('u')")
    await db.execute(
        """INSERT INTO recordings (id, user_id, original_filename, source, status, diarized_text)
           VALUES ('r', 'u', 'f', 'upload', 'ready', 'pre-existing litigation')"""
    )
    await db.commit()

    try:
        await _ensure_search_index(db)
        await _ensure_search_index(db)  # idempotent: no second copy of each row
        with patch("app.database._db", db):
            assert await _ids("u", "litigate ") == ["r"]
        for table in ("search_fts", "search_exact_fts"):
            await db.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")
    finally:
        await db.close()


class TestIndexBuild:
    async def _fresh_db(self):
        from app.database import FTS_SCHEMA_SQL, SCHEMA_SQL

        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await db.executescript(SCHEMA_SQL)
        await db.executescript(FTS_SCHEMA_SQL)
        await db.execute("INSERT INTO users (id) VALUES ('u')")
        await db.execute(
            """INSERT INTO recordings (id, user_id, original_filename, source, status, diarized_text)
               VALUES ('r', 'u', 'f', 'upload', 'ready', 'pre-existing litigation')"""
        )
        await db.commit()
        return db

    async def test_failed_build_rolls_back_and_retries(self):
        import app.database as database

        db = await self._fresh_db()
        try:
            # Break the populate step: the build must leave nothing half-done
            with patch.object(database, "_SEARCH_COLS", "title, bogus_column"):
                with pytest.raises(Exception):
                    await _ensure_search_index(db)
            assert not db.in_transaction
            await _ensure_search_index(db)
            with patch("app.database._db", db):
                assert await _ids("u", "litigate ") == ["r"]
        finally:
            await db.close()

    async def test_schema_change_triggers_rebuild(self):
        db = await self._fresh_db()
        try:
            await _ensure_search_index(db)
            await db.execute("UPDATE search_meta SET value = 'old' WHERE key = 'schema_version'")
            await db.commit()
            await _ensure_search_index(db)
            row = await (await db.execute("SELECT value FROM search_meta")).fetchone()
            from app.database import SEARCH_SCHEMA_VERSION

            assert row[0] == SEARCH_SCHEMA_VERSION
            with patch("app.database._db", db):
                assert await _ids("u", "litigate ") == ["r"]
        finally:
            await db.close()

    async def test_missing_documents_self_heal(self):
        db = await self._fresh_db()
        try:
            await _ensure_search_index(db)
            # Simulate an index that lost a row (e.g. a REPLACE into recordings)
            await db.execute(
                "INSERT INTO search_fts(search_fts, rowid, title, summary, notes, description, speakers, transcript) "
                "SELECT 'delete', doc_id, title, summary, notes, description, speakers, transcript FROM search_docs"
            )
            await db.commit()
            await _ensure_search_index(db)
            with patch("app.database._db", db):
                assert await _ids("u", "litigate ") == ["r"]
        finally:
            await db.close()

    async def test_upsert_keeps_index_in_sync(self, db, test_user):
        rid = await _recording(db, test_user.id, title="Patent talk")
        await db.execute(
            """INSERT INTO recordings (id, user_id, original_filename, source, title)
               VALUES (?, ?, 'f', 'upload', 'Budget review')
               ON CONFLICT(id) DO UPDATE SET title = excluded.title""",
            (rid, test_user.id),
        )
        await db.commit()
        assert await _ids(test_user.id, "budget ") == [rid]
        assert await _ids(test_user.id, "patent ") == []
