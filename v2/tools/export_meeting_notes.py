# /// script
# dependencies = []
# requires-python = ">=3.11"
# ///
"""Export meeting notes from a downloaded SQLite snapshot to Markdown files.

Usage:
    uv run v2/tools/export_meeting_notes.py [DB_PATH] [OUT_DIR]

Defaults: /tmp/qs.db -> v2/exports/meeting_notes/
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y · %-I:%M %p")
    except Exception:
        return iso


def fmt_date_filename(iso: str | None) -> str:
    if not iso:
        return "0000-00-00"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return "0000-00-00"


def fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def slugify(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:max_len].strip("-") or "untitled"


def speakers_from_mapping(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        m = json.loads(raw)
    except Exception:
        return []
    seen, names = set(), []
    for entry in m.values():
        name = (entry or {}).get("displayName")
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def topics_from_meeting_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return [str(t) for t in v] if isinstance(v, list) else []
    except Exception:
        return []


def render(rec: sqlite3.Row, user_tags: list[str]) -> str:
    title = rec["title"] or rec["original_filename"] or "Untitled"
    date = fmt_date(rec["recorded_at"] or rec["created_at"])
    duration = fmt_duration(rec["duration_seconds"])
    speakers = speakers_from_mapping(rec["speaker_mapping"])
    topics = topics_from_meeting_tags(rec["meeting_notes_tags"])

    lines = [f"# {title}", ""]
    if date:
        lines.append(f"- **Date:** {date}")
    if duration:
        lines.append(f"- **Duration:** {duration}")
    if speakers:
        lines.append(f"- **Speakers:** {', '.join(speakers)}")
    if rec["source"]:
        lines.append(f"- **Source:** {rec['source']}")
    if topics:
        lines.append(f"- **Topics:** {', '.join(topics)}")
    if user_tags:
        lines.append(f"- **Tags:** {', '.join(user_tags)}")
    lines.append(f"- **ID:** `{rec['id']}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append((rec["meeting_notes"] or "").strip())
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/qs.db")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        Path(__file__).resolve().parent.parent / "exports" / "meeting_notes"
    )

    if not db_path.exists():
        print(f"ERROR: {db_path} not found", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, title, original_filename, recorded_at, created_at,
               duration_seconds, source, speaker_mapping,
               meeting_notes, meeting_notes_tags
        FROM recordings
        WHERE meeting_notes IS NOT NULL AND TRIM(meeting_notes) != ''
        ORDER BY COALESCE(recorded_at, created_at) DESC
        """
    ).fetchall()

    written = 0
    for rec in rows:
        user_tags = [
            r[0]
            for r in conn.execute(
                """SELECT t.name FROM tags t
                   JOIN recording_tags rt ON rt.tag_id = t.id
                   WHERE rt.recording_id = ?
                   ORDER BY t.name""",
                (rec["id"],),
            )
        ]

        date_part = fmt_date_filename(rec["recorded_at"] or rec["created_at"])
        slug = slugify(rec["title"] or rec["original_filename"] or "untitled")
        id8 = rec["id"][:8]
        path = out_dir / f"{date_part}_{slug}__{id8}.md"
        path.write_text(render(rec, user_tags), encoding="utf-8")
        written += 1

    print(f"Wrote {written} files to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
