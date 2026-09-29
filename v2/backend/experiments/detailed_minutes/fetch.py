# /// script
# requires-python = ">=3.11"
# dependencies = ["lz4"]
# ///
"""Cache recordings (timed transcript + baselines) from a QuickScribe DB snapshot.

The live DB is only reachable through Litestream's blob replica, so --download
pulls the newest hourly snapshot (an LZ4-compressed full copy of app.db, at most
an hour stale) into cache/app.db. That only reads the replica, so it can never
act as a second writer. Recordings are then written to cache/recordings/<id>.json.

Usage:
    uv run fetch.py --download                 # refresh cache/app.db from blob storage
    uv run fetch.py --list --since 2026-08-01  # show candidates
    uv run fetch.py --ids <id> <id> ...        # cache specific recordings
    uv run fetch.py --sample 9 --since 2026-07-28   # spread of lengths
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import lz4.frame

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
DB_PATH = CACHE / "app.db"
REC_DIR = CACHE / "recordings"

SUBSCRIPTION = "dfd21f2e-a846-4677-9341-78dd8723df4e"
STORAGE_ACCOUNT = "quickscribestore2"
CONTAINER = "quickscribe-v2-backup"


def az(*args: str) -> str:
    out = subprocess.run(
        ["az", *args, "--subscription", SUBSCRIPTION],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def download_snapshot() -> None:
    key = az("storage", "account", "keys", "list", "-n", STORAGE_ACCOUNT,
             "--query", "[0].value", "-o", "tsv")
    names = az("storage", "blob", "list", "--account-name", STORAGE_ACCOUNT,
               "--account-key", key, "-c", CONTAINER, "--prefix", "app.db/generations/",
               "--query", "[?contains(name,'/snapshots/')].[properties.lastModified,name]",
               "-o", "tsv")
    latest = sorted(line.split("\t") for line in names.splitlines())[-1]
    print(f"Newest snapshot: {latest[1]} ({latest[0]})")
    CACHE.mkdir(exist_ok=True)
    lz = CACHE / "snapshot.lz4"
    az("storage", "blob", "download", "--account-name", STORAGE_ACCOUNT,
       "--account-key", key, "-c", CONTAINER, "-n", latest[1], "-f", str(lz),
       "--no-progress", "-o", "none")
    tmp = DB_PATH.with_suffix(".tmp")
    with lz4.frame.open(lz, "rb") as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst)
    tmp.replace(DB_PATH)
    lz.unlink()
    print(f"Wrote {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.0f} MB)")


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit("No cache/app.db; run with --download first")
    # immutable=1: the snapshot is in WAL mode with no -shm, and we never write
    conn = sqlite3.connect(f"file:{DB_PATH}?immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


CANDIDATES_SQL = """
SELECT id, title, recorded_at, duration_seconds, token_count
FROM recordings
WHERE transcript_json IS NOT NULL AND recorded_at >= ? AND duration_seconds >= ?
ORDER BY duration_seconds DESC
"""


def candidates(conn, since: str, min_minutes: float) -> list[sqlite3.Row]:
    return conn.execute(CANDIDATES_SQL, (since, min_minutes * 60)).fetchall()


def pick_sample(rows: list[sqlite3.Row], n: int) -> list[sqlite3.Row]:
    """Evenly spaced picks across the duration-sorted list: longest to shortest."""
    if len(rows) <= n:
        return rows
    step = (len(rows) - 1) / (n - 1)
    return [rows[round(i * step)] for i in range(n)]


def speaker_names(mapping_json: str | None) -> dict[str, str]:
    """'Speaker 1' -> display name, falling back to the label itself."""
    try:
        mapping = json.loads(mapping_json or "{}")
    except json.JSONDecodeError:
        return {}
    return {label: (info or {}).get("displayName") or label for label, info in mapping.items()}


def phrases(transcript_json: str) -> list[dict]:
    data = json.loads(transcript_json)
    out = []
    for p in data.get("recognizedPhrases", []):
        best = (p.get("nBest") or [{}])[0]
        text = (best.get("display") or "").strip()
        if not text:
            continue
        out.append({
            "t_ms": int(p.get("offsetMilliseconds") or 0),
            "dur_ms": int(p.get("durationMilliseconds") or 0),
            "speaker": f"Speaker {p['speaker']}" if p.get("speaker") is not None else "Unknown",
            "text": text,
        })
    out.sort(key=lambda p: p["t_ms"])
    return out


def cache_recording(conn, rec_id: str) -> Path:
    r = conn.execute("SELECT * FROM recordings WHERE id = ?", (rec_id,)).fetchone()
    if r is None:
        raise SystemExit(f"No recording {rec_id}")
    doc = {
        "id": r["id"],
        "title": r["title"],
        "recorded_at": r["recorded_at"],
        "duration_seconds": r["duration_seconds"],
        "token_count": r["token_count"],
        "speakers": speaker_names(r["speaker_mapping"]),
        "phrases": phrases(r["transcript_json"]),
        "diarized_text": r["diarized_text"] or r["transcript_text"],
        "baselines": {
            "search_summary": r["search_summary"],
            "meeting_notes": r["meeting_notes"],
        },
    }
    REC_DIR.mkdir(parents=True, exist_ok=True)
    path = REC_DIR / f"{rec_id}.json"
    path.write_text(json.dumps(doc, indent=1))
    return path


def fmt_row(r) -> str:
    return (f"{r['id']}  {(r['recorded_at'] or '')[:10]}  {r['duration_seconds'] / 60:5.0f} min  "
            f"{r['token_count'] or 0:6} tok  {r['title']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", action="store_true", help="refresh cache/app.db from the Litestream snapshot")
    ap.add_argument("--since", default="2026-07-28", help="earliest recorded_at (YYYY-MM-DD)")
    ap.add_argument("--min-minutes", type=float, default=8)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sample", type=int, help="cache N recordings spread across lengths")
    ap.add_argument("--ids", nargs="*", default=[])
    args = ap.parse_args()

    if args.download:
        download_snapshot()
    if not (args.list or args.sample or args.ids):
        return
    conn = connect()
    rows = candidates(conn, args.since, args.min_minutes)
    if args.list:
        for r in rows:
            print(fmt_row(r))
    picked = list(args.ids)
    if args.sample:
        picked += [r["id"] for r in pick_sample(rows, args.sample)]
    for rec_id in picked:
        path = cache_recording(conn, rec_id)
        r = conn.execute(CANDIDATES_SQL.replace("ORDER BY", "AND id = ? ORDER BY"),
                         ("0000", 0, rec_id)).fetchone()
        print(f"cached {fmt_row(r)}  -> {path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
