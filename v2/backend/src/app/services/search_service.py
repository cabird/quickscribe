"""Fast keyword search: ranked FTS5 over titles, AI summaries, meeting notes,
descriptions, speaker names and transcripts. No LLM or embeddings involved.

Query syntax (every term must match):
    dryden patent        both words, any form ("patent" also finds "patents")
    "claim construction" exact phrase, no stemming
    -billing             exclude recordings containing the word
    -"status update"     exclude an exact phrase
    @car                 a participant whose name or alias has a word starting
                         with "car" spoke (Carmen, Carmichael, Fred Carson...)
    @"chris bird"        multi-word name prefix
    person:car           same as @car
The last plain word is also matched as a prefix, so results appear while typing.

Indexes and the search_docs view live in database.py (SEARCH_SCHEMA_SQL).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from app.database import SEARCH_INDEX_COLUMNS, get_db
from app.models import SearchPerson, SearchResponse, SearchResult

# BM25 column weights, in SEARCH_INDEX_COLUMNS order:
# title, summary, notes, description, speakers, transcript
BM25_WEIGHTS = (10.0, 4.0, 3.0, 2.0, 3.0, 1.0)
assert len(BM25_WEIGHTS) == len(SEARCH_INDEX_COLUMNS)
_TITLE_COL = SEARCH_INDEX_COLUMNS.index("title")
_TRANSCRIPT_COL = SEARCH_INDEX_COLUMNS.index("transcript")

# Highlight markers in snippets. Control characters can't occur in the indexed
# text, so the frontend can split on them safely.
HL_START = "\u0002"
HL_END = "\u0003"
_SNIPPET_TOKENS = 18

# -billing, -"a phrase", @car, @"chris bird", person:car, "phrase", word.
# An unterminated quote (mid-typing) runs to the end of the query.
_TOKEN_RE = re.compile(
    r'(?P<neg>-)?(?P<person>@|person:)?(?:"(?P<phrase>[^"]*)"?|(?P<word>[^\s"]+))',
    re.IGNORECASE,
)
_SPEAKER_LABEL_RE = re.compile(r"\bSpeaker \d+\b")


@dataclass
class ParsedQuery:
    words: list[str] = field(default_factory=list)
    phrases: list[str] = field(default_factory=list)
    exclude_words: list[str] = field(default_factory=list)
    exclude_phrases: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    prefix_last_word: bool = False

    @property
    def has_text(self) -> bool:
        return bool(self.words or self.phrases)


def parse_query(q: str) -> ParsedQuery:
    """Split a raw query into required words, phrases, exclusions and people."""
    parsed = ParsedQuery()
    last_kind = None
    for m in _TOKEN_RE.finditer(q or ""):
        phrase, word = m.group("phrase"), m.group("word")
        text = (phrase if phrase is not None else word or "").strip()
        if m.group("person"):
            if text:
                parsed.people.append(text.lower())
            last_kind = None
            continue
        if not text or text in ("-", "@") or text.lower() == "person:":
            continue  # a bare operator while typing
        if phrase is not None:
            (parsed.exclude_phrases if m.group("neg") else parsed.phrases).append(text)
            last_kind = None
        elif m.group("neg"):
            parsed.exclude_words.append(text)
            last_kind = None
        else:
            parsed.words.append(text)
            last_kind = "word"
    # Prefix-match the word being typed: only if the query doesn't end in a
    # space and the last token was a plain word of at least 2 characters.
    parsed.prefix_last_word = (
        last_kind == "word" and not (q or "").endswith((" ", "\t")) and len(parsed.words[-1]) >= 2
    )
    return parsed


def _fts_literal(term: str) -> str:
    """Quote a term as an FTS5 string literal (safe for any input)."""
    return '"' + term.replace('"', '""') + '"'


def _and_expr(terms: list[str], prefix_last: bool = False) -> str | None:
    parts = [_fts_literal(t) for t in terms]
    if not parts:
        return None
    if prefix_last:
        parts[-1] += "*"
    return " AND ".join(parts)


def _or_expr(terms: list[str]) -> str | None:
    return " OR ".join(_fts_literal(t) for t in terms) or None


def _name_matches(term: str, candidates: list[str]) -> bool:
    """True if `term` prefix-matches a run of words in any candidate name.

    "car" matches "Carmen", "Fred Carson"; "chris b" matches "Chris Bird".
    """
    want = term.split()
    if not want:
        return False
    for cand in candidates:
        words = cand.lower().split()
        for i in range(len(words) - len(want) + 1):
            window = words[i : i + len(want)]
            if all(w == t for w, t in zip(window[:-1], want[:-1])) and window[-1].startswith(want[-1]):
                return True
    return False


def _participant_names(row: dict) -> list[str]:
    names = [row.get("display_name") or ""]
    first, last = row.get("first_name") or "", row.get("last_name") or ""
    names += [first, last, f"{first} {last}"]
    try:
        aliases = json.loads(row.get("aliases") or "[]")
    except (TypeError, ValueError):
        aliases = []
    names += [a for a in aliases if isinstance(a, str)]
    return [n for n in names if n.strip()]


async def resolve_people(user_id: str, terms: list[str]) -> list[SearchPerson]:
    """Resolve each @term to the participants it matches."""
    if not terms:
        return []
    db = await get_db()
    rows = [
        dict(r)
        for r in await db.execute_fetchall(
            """SELECT id, display_name, first_name, last_name, aliases
               FROM participants WHERE user_id = ?""",
            (user_id,),
        )
    ]
    resolved = []
    for term in terms:
        matches = [r for r in rows if _name_matches(term, _participant_names(r))]
        resolved.append(
            SearchPerson(
                term=term,
                participant_ids=[r["id"] for r in matches],
                names=[r["display_name"] for r in matches],
            )
        )
    return resolved


def _spoke_clause(participant_ids: list[str]) -> tuple[str, list]:
    """Recording has a speaker mapped to any of these participants."""
    placeholders = ",".join("?" for _ in participant_ids)
    return (
        f"""EXISTS (
            SELECT 1 FROM json_each(CASE WHEN json_valid(r.speaker_mapping)
                                         THEN r.speaker_mapping END) AS je
            WHERE je.type = 'object'
              AND json_extract(je.value, '$.participantId') IN ({placeholders})
        )""",
        list(participant_ids),
    )


def _label_speakers(text: str, speaker_mapping: str | None) -> str:
    """Replace "Speaker 2" labels in a snippet with the identified name."""
    try:
        mapping = json.loads(speaker_mapping or "{}")
    except (TypeError, ValueError):
        return text
    if not isinstance(mapping, dict):
        return text

    def name(m: re.Match) -> str:
        entry = mapping.get(m.group(0))
        if isinstance(entry, dict) and entry.get("displayName"):
            return entry["displayName"]
        return m.group(0)

    return _SPEAKER_LABEL_RE.sub(name, text)


async def search(
    user_id: str,
    q: str = "",
    *,
    person_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    with_snippets: bool = True,
    ready_only: bool = True,
) -> SearchResponse:
    """Ranked keyword search. See the module docstring for query syntax."""
    from app.services.recording_service import (  # avoid import cycle
        _SUMMARY_COLUMNS,
        _get_tag_ids_bulk,
        _row_to_summary,
    )

    started = time.perf_counter()
    db = await get_db()
    parsed = parse_query(q)
    people = await resolve_people(user_id, parsed.people)

    def empty() -> SearchResponse:
        return SearchResponse(
            data=[], total=0, people=people, took_ms=int((time.perf_counter() - started) * 1000)
        )

    # Every @term must be satisfied; one that matches nobody means no results.
    if any(not p.participant_ids for p in people):
        return empty()

    stem_expr = _and_expr(parsed.words, parsed.prefix_last_word)
    exact_expr = _and_expr(parsed.phrases)
    weights = ", ".join(str(w) for w in BM25_WEIGHTS)

    ctes, joins, where, params = [], [], ["r.user_id = ?"], []
    if ready_only:
        where.append("r.status = 'ready'")
    rank_terms = []
    if stem_expr:
        ctes.append(
            f"sm AS (SELECT rowid AS rid, bm25(search_fts, {weights}) AS score "
            "FROM search_fts WHERE search_fts MATCH ?)"
        )
        params.append(stem_expr)
        joins.append("JOIN sm ON sm.rid = r.rowid")
        rank_terms.append("sm.score")
    if exact_expr:
        ctes.append(
            f"ex AS (SELECT rowid AS rid, bm25(search_exact_fts, {weights}) AS score "
            "FROM search_exact_fts WHERE search_exact_fts MATCH ?)"
        )
        params.append(exact_expr)
        joins.append("JOIN ex ON ex.rid = r.rowid")
        rank_terms.append("ex.score")

    params.append(user_id)
    if parsed.exclude_words:
        where.append("r.rowid NOT IN (SELECT rowid FROM search_fts WHERE search_fts MATCH ?)")
        params.append(_or_expr(parsed.exclude_words))
    if parsed.exclude_phrases:
        where.append(
            "r.rowid NOT IN (SELECT rowid FROM search_exact_fts WHERE search_exact_fts MATCH ?)"
        )
        params.append(_or_expr(parsed.exclude_phrases))
    for person in people:
        clause, clause_params = _spoke_clause(person.participant_ids)
        where.append(clause)
        params.extend(clause_params)
    if person_ids:
        for pid in person_ids:  # pinned people from the UI: each must have spoken
            clause, clause_params = _spoke_clause([pid])
            where.append(clause)
            params.extend(clause_params)
    if tag_ids:
        placeholders = ",".join("?" for _ in tag_ids)
        where.append(
            f"r.id IN (SELECT recording_id FROM recording_tags WHERE tag_id IN ({placeholders}))"
        )
        params.extend(tag_ids)
    if date_from:
        where.append("COALESCE(r.recorded_at, r.created_at) >= ?")
        params.append(date_from)
    if date_to:
        where.append("COALESCE(r.recorded_at, r.created_at) <= ?")
        params.append(date_to)

    rank = " + ".join(rank_terms) if rank_terms else "0"
    # bm25() is lower-is-better; ties (and filter-only searches) go newest first
    sql = (
        (f"WITH {', '.join(ctes)} " if ctes else "")
        + f"SELECT {_prefixed(_SUMMARY_COLUMNS)}, r.rowid AS doc_id, ({rank}) AS rank, "
        "COUNT(*) OVER () AS total "
        f"FROM recordings r {' '.join(joins)} WHERE {' AND '.join(where)} "
        "ORDER BY rank ASC, COALESCE(r.recorded_at, r.created_at) DESC "
        "LIMIT ? OFFSET ?"
    )
    params += [limit, offset]
    rows = [dict(r) for r in await db.execute_fetchall(sql, params)]
    if not rows:
        return empty()

    snippets: dict[int, dict] = {}
    if with_snippets and parsed.has_text:
        snippets = await _snippets(
            [r["doc_id"] for r in rows],
            "search_fts" if stem_expr else "search_exact_fts",
            stem_expr or exact_expr,
        )

    tag_map = await _get_tag_ids_bulk([r["id"] for r in rows])
    results = []
    for r in rows:
        summary = _row_to_summary(r, tag_ids=tag_map.get(r["id"]))
        snip = snippets.get(r["doc_id"], {})
        results.append(
            SearchResult(
                **summary.model_dump(),
                rank=r["rank"] if rank_terms else None,
                title_highlight=snip.get("title"),
                snippets=[
                    _label_speakers(s, r.get("speaker_mapping"))
                    for s in snip.get("snippets", [])
                ],
            )
        )
    return SearchResponse(
        data=results,
        total=rows[0]["total"],
        people=people,
        took_ms=int((time.perf_counter() - started) * 1000),
    )


def _prefixed(columns: str) -> str:
    return ", ".join(f"r.{c.strip()}" for c in columns.split(",") if c.strip())


async def _snippets(doc_ids: list[int], table: str, expr: str) -> dict[int, dict]:
    """Title highlight plus up to two snippets for just the returned page.

    Done as a second query so snippet() (which re-tokenizes whole transcripts)
    only runs for the rows being shown, not every match.
    """
    db = await get_db()
    placeholders = ",".join("?" for _ in doc_ids)
    marks = (HL_START, HL_END)
    rows = await db.execute_fetchall(
        f"""SELECT rowid,
                   highlight({table}, {_TITLE_COL}, ?, ?) AS title,
                   snippet({table}, -1, ?, ?, '…', {_SNIPPET_TOKENS}) AS best,
                   snippet({table}, {_TRANSCRIPT_COL}, ?, ?, '…', {_SNIPPET_TOKENS}) AS transcript
            FROM {table} WHERE {table} MATCH ? AND rowid IN ({placeholders})""",
        [*marks, *marks, *marks, expr, *doc_ids],
    )
    out = {}
    for row in rows:
        r = dict(row)
        found = [s for s in (r["best"], r["transcript"]) if s and HL_START in s]
        out[r["rowid"]] = {
            "title": r["title"] if r["title"] and HL_START in r["title"] else None,
            "snippets": list(dict.fromkeys(found)),  # dedupe, keep order
        }
    return out
