# /// script
# dependencies = [
#     "aiosqlite>=0.20.0",
#     "openai>=1.51.0",
#     "pyyaml>=6.0",
#     "pydantic>=2.9.0",
#     "pydantic-settings>=2.0.0",
#     "python-dotenv>=1.0.0",
#     "tiktoken>=0.5.0",
# ]
# requires-python = ">=3.11"
# ///
"""Backfill search summaries for all recordings that have transcripts but no summary.

Usage:
    cd v2/backend/src && uv run ../../../tools/backfill_summaries.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add backend src to path so we can import app modules
_backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_backend_dir / "src"))

# Load .env from the backend directory and fix relative DATABASE_PATH
import os  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
load_dotenv(_backend_dir / ".env")

# Ensure DATABASE_PATH is absolute (relative paths in .env are relative to backend dir)
db_path = os.environ.get("DATABASE_PATH", "./data/app.db")
if not os.path.isabs(db_path):
    os.environ["DATABASE_PATH"] = str(_backend_dir / db_path)

from app.config import get_settings  # noqa: E402
from app.database import init_db, close_db, get_db  # noqa: E402
from app.services import search_summary_service  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
logger = logging.getLogger(__name__)


async def main(limit: int | None = None, dry_run: bool = False, show: bool = False):
    settings = get_settings()
    if not settings.ai_enabled:
        logger.error("AI is not enabled (missing AZURE_OPENAI_ENDPOINT or API_KEY)")
        return

    await init_db()
    db = await get_db()

    try:
        # Find recordings with transcripts but no search_summary
        rows = await db.execute_fetchall(
            """SELECT id, user_id, title, original_filename
               FROM recordings
               WHERE status = 'ready'
                 AND (diarized_text IS NOT NULL OR transcript_text IS NOT NULL)
                 AND search_summary IS NULL
               ORDER BY recorded_at DESC"""
        )

        total = len(rows)
        if limit:
            rows = rows[:limit]

        logger.info(
            "Found %d recordings needing summaries%s",
            total,
            f" (processing {limit})" if limit and limit < total else "",
        )

        if dry_run:
            for row in rows:
                row = dict(row)
                logger.info(
                    "  Would process: %s - %s",
                    row["id"][:8],
                    row.get("title") or row["original_filename"],
                )
            return

        processed = 0
        errors = 0
        start = time.time()
        concurrency = 8
        sem = asyncio.Semaphore(concurrency)
        counter_lock = asyncio.Lock()

        async def process_one(i: int, row_dict: dict):
            nonlocal processed, errors
            rec_id = row_dict["id"]
            user_id = row_dict["user_id"]
            title = row_dict.get("title") or row_dict["original_filename"]

            async with sem:
                try:
                    result = await search_summary_service.generate_search_summary(rec_id, user_id)
                    summary_words = len(result.get("summary", "").split())
                    keywords_count = len(result.get("keywords", []))
                    async with counter_lock:
                        processed += 1
                        done = processed + errors
                    logger.info(
                        "[%d/%d] %s - %s (%d words, %d keywords)",
                        done, len(rows), rec_id[:8], title[:40],
                        summary_words, keywords_count,
                    )
                    if show:
                        print(f"\n{'─' * 60}")
                        print(f"  {title}")
                        print(f"{'─' * 60}")
                        print(f"  {result.get('summary', '').strip()}")
                        kw = result.get('keywords', [])
                        if kw:
                            print(f"  Keywords: {', '.join(kw)}")
                        print()
                except Exception as exc:
                    async with counter_lock:
                        errors += 1
                        done = processed + errors
                    logger.error("[%d/%d] %s - FAILED: %s", done, len(rows), rec_id[:8], exc)

        # Launch all tasks, semaphore limits concurrency to 8
        tasks = [
            process_one(i, dict(row))
            for i, row in enumerate(rows)
        ]
        await asyncio.gather(*tasks)

        elapsed = time.time() - start
        logger.info(
            "Done! Processed %d, errors %d, elapsed %.1fs (%.1fs/recording avg, %d concurrent)",
            processed, errors, elapsed,
            elapsed / max(processed, 1),
            concurrency,
        )

    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill search summaries")
    parser.add_argument("--limit", type=int, help="Max recordings to process")
    parser.add_argument("--dry-run", action="store_true", help="Just list what would be processed")
    parser.add_argument("--show", action="store_true", help="Print each summary after generation")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, dry_run=args.dry_run, show=args.show))
