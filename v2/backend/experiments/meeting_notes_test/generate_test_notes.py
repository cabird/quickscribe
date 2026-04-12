# /// script
# dependencies = ["openai", "jinja2", "aiosqlite", "python-dotenv"]
# requires-python = ">=3.11"
# ///
"""Generate meeting notes for a set of test recordings.

Reads recordings from the QuickScribe SQLite database, renders the
Jinja2 prompt template, calls Azure OpenAI (gpt-5-mini with medium
thinking), and writes the resulting notes to markdown files.

Usage:
    cd /home/cbird/repos/quickscribe/v2/backend
    uv run experiments/meeting_notes_test/generate_test_notes.py
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import aiosqlite
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from openai import AsyncAzureOpenAI

# Load .env from the backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BACKEND_DIR / ".env")

# Paths
DB_PATH = BACKEND_DIR / "data" / "app.db"
TEMPLATE_DIR = BACKEND_DIR / "src" / "app" / "prompts"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Azure OpenAI config
ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01")
DEPLOYMENT = os.environ.get("AZURE_OPENAI_MINI_DEPLOYMENT", "gpt-5-mini")

# Test recordings — diverse set selected for coverage
TEST_RECORDING_IDS = [
    "a95992f3-52b3-4f68-8d01-370aff11cc18",  # 11m, 1 speaker, solo/monologue
    "4e3a59ab-d840-4ef2-a639-7bf002e7f86a",  # 17m, 2 speakers, short 1:1
    "e8a62b96-8720-4cd8-9ec1-3c6654d49f19",  # 49m, 5 speakers, standup
    "57c4e5c2-6946-402f-9f18-3920c96b9e64",  # 32m, 2 speakers, career/personal
    "d7a8c725-ef45-4489-9050-634a032f9d0e",  # 83m, 4 speakers, long with decisions
    "1402dabf-e2dd-4312-b233-2271625128cf",  # 115m, 3 speakers, very long research
    "7d83084f-14d4-45f5-8871-a894f8d2e68d",  # 19m, 5 speakers, short multi-person
    "95859150-f4c0-425e-b13d-94ba1047117e",  # 38m, 4 speakers, non-tech (medical)
]


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "unknown"
    minutes = int(seconds / 60)
    if minutes < 1:
        return f"{int(seconds)}s"
    return f"{minutes}m"


def extract_speaker_names(speaker_mapping_json: str | None) -> str:
    if not speaker_mapping_json:
        return "unknown"
    try:
        mapping = json.loads(speaker_mapping_json)
        names = []
        for label, entry in mapping.items():
            name = entry.get("displayName") or label
            if name:
                names.append(name)
        return ", ".join(names) if names else "unknown"
    except (json.JSONDecodeError, AttributeError):
        return "unknown"


async def generate_notes_for_recording(
    db: aiosqlite.Connection,
    client: AsyncAzureOpenAI,
    jinja_env: Environment,
    recording_id: str,
) -> tuple[str, str, float]:
    """Generate meeting notes for one recording. Returns (title, notes, elapsed_seconds)."""
    row = await db.execute_fetchall(
        """SELECT id, title, diarized_text, transcript_text, duration_seconds,
                  recorded_at, speaker_mapping, token_count
           FROM recordings WHERE id = ?""",
        (recording_id,),
    )
    if not row:
        raise ValueError(f"Recording {recording_id} not found")

    rec = dict(row[0])
    transcript = rec.get("diarized_text") or rec.get("transcript_text") or ""
    title = rec.get("title") or "Untitled"
    token_count = rec.get("token_count") or 0

    # Render prompt
    template = jinja_env.get_template("generate_meeting_notes.j2")
    prompt = template.render(
        title=title,
        date=rec.get("recorded_at") or "unknown",
        speakers=extract_speaker_names(rec.get("speaker_mapping")),
        duration=format_duration(rec.get("duration_seconds")),
        transcript=transcript,
    )

    print(f"  Calling GPT-5-mini (medium thinking) | {token_count} transcript tokens...")
    start = time.time()

    response = await client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[
            {"role": "system", "content": prompt},
        ],
        reasoning_effort="medium",
    )

    elapsed = time.time() - start
    notes = response.choices[0].message.content or ""
    usage = response.usage

    print(f"  Done in {elapsed:.1f}s | prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")

    return title, notes, elapsed


async def main():
    print(f"Database: {DB_PATH}")
    print(f"Template: {TEMPLATE_DIR / 'generate_meeting_notes.j2'}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Model: {DEPLOYMENT} (reasoning_effort=medium)")
    print(f"Recordings: {len(TEST_RECORDING_IDS)}")
    print()

    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row

    client = AsyncAzureOpenAI(
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    total_elapsed = 0
    results = []

    for i, rec_id in enumerate(TEST_RECORDING_IDS, 1):
        print(f"[{i}/{len(TEST_RECORDING_IDS)}] {rec_id}")
        try:
            title, notes, elapsed = await generate_notes_for_recording(
                db, client, jinja_env, rec_id
            )
            total_elapsed += elapsed

            # Write to file
            safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:60].strip()
            filename = f"{i:02d}_{safe_title}.md"
            output_path = OUTPUT_DIR / filename
            output_path.write_text(notes, encoding="utf-8")
            print(f"  Wrote: {filename} ({len(notes)} chars)")
            results.append((title, len(notes), elapsed))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((rec_id, 0, 0))
        print()

    await client.close()
    await db.close()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for title, chars, elapsed in results:
        print(f"  {title[:50]:50s} {chars:6d} chars  {elapsed:5.1f}s")
    print(f"\nTotal time: {total_elapsed:.1f}s")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
