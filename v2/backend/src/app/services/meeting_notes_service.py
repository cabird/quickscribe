"""Meeting notes generation for recordings.

Generates structured meeting notes with discussion threads, decisions,
action items, key quotes, and topic tags. Uses the mini model with
medium reasoning effort.
"""

from __future__ import annotations

import json
import logging
import re

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


def _parse_topic_tags(notes: str) -> list[str]:
    """Parse topic tags from the last section of the meeting notes markdown.

    Looks for a '## Topic Tags' heading and grabs the next non-empty line,
    splitting by comma.
    """
    lines = notes.split("\n")
    tag_section_found = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,3}\s*\d*\.?\s*Topic Tags", stripped, re.IGNORECASE):
            tag_section_found = True
            continue
        if tag_section_found and stripped:
            # Split by comma, strip whitespace
            tags = [t.strip() for t in stripped.split(",") if t.strip()]
            return tags
    return []


async def generate_meeting_notes(recording_id: str, user_id: str) -> str | None:
    """Generate structured meeting notes for a recording.

    Args:
        recording_id: The recording ID.
        user_id: The user ID (for authorization).

    Returns:
        The generated meeting notes markdown, or None on failure.
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
        logger.warning("Recording %s not found for meeting notes generation", recording_id)
        return None
    rec = dict(row[0])

    transcript = rec.get("diarized_text") or rec.get("transcript_text")
    if not transcript:
        logger.warning("Recording %s has no transcript for meeting notes", recording_id)
        return None

    # Truncate transcript if needed (token-aware, consistent with ai_service)
    from app.services.ai_service import _truncate_transcript
    transcript = _truncate_transcript(transcript)

    # Build prompt
    prompt_text = render(
        "generate_meeting_notes",
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
                {"role": "user", "content": prompt_text},
            ],
            max_completion_tokens=8000,
            reasoning_effort="medium",
        )

        content = response.choices[0].message.content or ""

        if not content.strip():
            logger.warning("Empty meeting notes response for %s", recording_id)
            return None

        # Parse topic tags from the notes
        tags = _parse_topic_tags(content)

        # Store in database
        await db.execute(
            """UPDATE recordings
               SET meeting_notes = ?, meeting_notes_generated_at = datetime('now'),
                   meeting_notes_tags = ?, updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (content, json.dumps(tags), recording_id, user_id),
        )
        await db.commit()

        logger.info(
            "Generated meeting notes for %s (%d chars, %d tags)",
            recording_id[:8],
            len(content),
            len(tags),
        )

        return content

    except Exception:
        logger.exception("Failed to generate meeting notes for %s", recording_id)
        return None
    finally:
        await client.close()
