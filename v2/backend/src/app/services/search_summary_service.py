"""Search summary generation for recordings.

Generates retrieval-optimized summaries used by the deep search pipeline.
Uses the mini model for cost efficiency.
"""

from __future__ import annotations

import json
import logging

from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.database import get_db
from app.prompts import render

logger = logging.getLogger(__name__)


def _get_client() -> AsyncAzureOpenAI:
    settings = get_settings()
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "unknown"
    minutes = int(seconds / 60)
    if minutes < 1:
        return f"{int(seconds)}s"
    return f"{minutes}m"


def _extract_speaker_names(speaker_mapping_json: str | None) -> str:
    """Extract display names from speaker mapping JSON."""
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


async def generate_search_summary(recording_id: str, user_id: str) -> dict:
    """Generate a retrieval-optimized search summary for a recording.

    Args:
        recording_id: The recording ID.
        user_id: The user ID (for authorization).

    Returns:
        Dict with "summary" and "keywords" keys.
    """
    db = await get_db()
    settings = get_settings()

    # Load recording
    row = await db.execute_fetchall(
        """SELECT id, title, description, diarized_text, transcript_text,
                  duration_seconds, recorded_at, speaker_mapping
           FROM recordings WHERE id = ? AND user_id = ?""",
        (recording_id, user_id),
    )
    if not row:
        raise ValueError(f"Recording {recording_id} not found")
    rec = dict(row[0])

    transcript = rec.get("diarized_text") or rec.get("transcript_text")
    if not transcript:
        raise ValueError(f"Recording {recording_id} has no transcript")

    # Truncate transcript for summary generation (keep it reasonable)
    max_chars = 60_000
    if len(transcript) > max_chars:
        half = max_chars // 2
        transcript = (
            transcript[:half]
            + "\n\n[... transcript truncated ...]\n\n"
            + transcript[-half:]
        )

    # Build prompt
    prompt_text = render(
        "generate_search_summary",
        title=rec.get("title") or "Untitled",
        date=rec.get("recorded_at") or "unknown",
        speakers=_extract_speaker_names(rec.get("speaker_mapping")),
        duration=_format_duration(rec.get("duration_seconds")),
        transcript=transcript,
    )

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_mini_deployment,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates retrieval-optimized summaries. Always respond with valid JSON only."},
                {"role": "user", "content": prompt_text},
            ],
            max_completion_tokens=4000,
        )

        choice = response.choices[0]
        print("\n=== RAW LLM RESPONSE ===")
        print(f"finish_reason: {choice.finish_reason}")
        print(f"refusal: {getattr(choice.message, 'refusal', None)}")
        print(f"content length: {len(choice.message.content or '')}")
        print(f"content: {(choice.message.content or '')[:1000]}")
        if hasattr(response, 'usage') and response.usage:
            print(f"usage: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
        print("=== END RAW RESPONSE ===\n")
        content = choice.message.content or "{}"
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        result = json.loads(text)

        summary = result.get("summary", "")
        keywords = result.get("keywords", [])

        # Store in database
        await db.execute(
            """UPDATE recordings
               SET search_summary = ?, search_keywords = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (summary, json.dumps(keywords), recording_id),
        )
        await db.commit()

        logger.info(
            "Generated search summary for %s (%d words, %d keywords)",
            recording_id[:8],
            len(summary.split()),
            len(keywords),
        )

        return {"summary": summary, "keywords": keywords}

    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Failed to parse search summary response: %s", exc)
        return {"summary": "", "keywords": []}
    finally:
        await client.close()
