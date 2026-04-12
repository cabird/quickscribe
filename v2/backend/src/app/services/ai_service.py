"""Azure OpenAI integration for transcript analysis and chat."""

from __future__ import annotations

import json
import logging
import time

import tiktoken
from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.models import ChatResponse
from app.prompts import render

logger = logging.getLogger(__name__)

_enc: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def _count_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def _get_client() -> AsyncAzureOpenAI:
    """Create an async Azure OpenAI client."""
    settings = get_settings()
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


# Reserve tokens for system prompt overhead + completion
_MAX_CONTEXT_TOKENS = 200_000
_RESERVED_TOKENS = 10_000  # for system prompt framing + response
_MAX_TRANSCRIPT_TOKENS = _MAX_CONTEXT_TOKENS - _RESERVED_TOKENS


def _truncate_transcript(transcript: str, max_tokens: int = _MAX_TRANSCRIPT_TOKENS) -> str:
    """Truncate transcript to stay within token limits.

    Keeps the beginning and end, which tend to have the most identifying
    information (introductions and conclusions).
    """
    enc = _get_encoding()
    tokens = enc.encode(transcript)
    if len(tokens) <= max_tokens:
        return transcript

    half = max_tokens // 2
    return (
        enc.decode(tokens[:half])
        + "\n\n[... transcript truncated for length ...]\n\n"
        + enc.decode(tokens[-half:])
    )


async def generate_title_description(transcript: str) -> dict:
    """Generate a title and description for a transcript.

    Args:
        transcript: The full or diarized transcript text.

    Returns:
        Dict with "title" and "description" keys.
    """
    settings = get_settings()

    truncated = _truncate_transcript(transcript, max_tokens=8_000)
    prompt_text = render("generate_title_description", transcript=truncated)

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_mini_deployment,
            messages=[{"role": "user", "content": prompt_text}],
            max_completion_tokens=4000,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        result = json.loads(content)

        return {
            "title": result.get("title", "Untitled Recording"),
            "description": result.get("description", ""),
        }
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Failed to parse title/description response: %s", exc)
        return {"title": "Untitled Recording", "description": ""}
    finally:
        await client.close()


async def infer_speakers(transcript: str) -> dict:
    """Infer speaker identities from a diarized transcript.

    Args:
        transcript: Diarized transcript with "Speaker 1:", "Speaker 2:" labels.

    Returns:
        Dict mapping speaker labels to inferred info, e.g.:
        {"Speaker 1": {"name": "Alice", "reasoning": "..."}, ...}
    """
    settings = get_settings()

    truncated = _truncate_transcript(transcript, max_tokens=10_000)
    prompt_text = render("infer_speaker_names", transcript=truncated)

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[{"role": "user", "content": prompt_text}],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Failed to parse speaker inference response: %s", exc)
        return {}
    finally:
        await client.close()


async def chat(
    messages: list[dict],
    transcript_context: str,
) -> ChatResponse:
    """Chat with transcript context.

    Args:
        messages: Conversation history as list of {"role": ..., "content": ...}.
        transcript_context: The transcript text to include as system context.

    Returns:
        ChatResponse with the assistant's reply and usage info.
    """
    settings = get_settings()
    truncated = _truncate_transcript(transcript_context)

    system_message = {
        "role": "system",
        "content": (
            "You are a helpful assistant that answers questions about an audio transcript. "
            "Use the transcript below as your primary source of information. "
            "If something isn't covered in the transcript, say so.\n\n"
            f"TRANSCRIPT:\n{truncated}"
        ),
    }

    all_messages = [system_message] + messages

    client = _get_client()
    start_ms = int(time.time() * 1000)
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_chat_deployment or settings.azure_openai_mini_deployment or settings.azure_openai_deployment,
            messages=all_messages,
            reasoning_effort="low",
        )

        elapsed_ms = int(time.time() * 1000) - start_ms
        choice = response.choices[0]
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return ChatResponse(
            message=choice.message.content or "",
            usage=usage,
            response_time_ms=elapsed_ms,
        )
    finally:
        await client.close()


async def synthesize(
    recordings: list[dict],
    question: str,
) -> ChatResponse:
    """Synthesize information across multiple recordings.

    Args:
        recordings: List of dicts with keys: title, recorded_at, speaker_names, text.
        question: The user's question to answer across all recordings.

    Returns:
        ChatResponse with the synthesized answer and usage info.
    """
    settings = get_settings()

    # Build per-recording sections, tracking token usage
    sections: list[str] = []
    total_tokens = 0

    for i, rec in enumerate(recordings, 1):
        title = rec.get("title") or "Untitled"
        date = rec.get("recorded_at") or "unknown date"
        speakers = ", ".join(rec.get("speaker_names") or []) or "unknown"
        text = rec.get("text") or ""

        header = f'## Recording {i}: "{title}" ({date}, speakers: {speakers})\n'
        header_tokens = _count_tokens(header)
        remaining = _MAX_TRANSCRIPT_TOKENS - total_tokens - header_tokens
        if remaining <= 0:
            break
        text_tokens = _count_tokens(text)
        if text_tokens > remaining:
            text = _truncate_transcript(text, max_tokens=remaining)
            text_tokens = remaining
        sections.append(header + text)
        total_tokens += header_tokens + text_tokens

    recordings_block = "\n\n".join(sections)

    system_message = {
        "role": "system",
        "content": (
            "You are a helpful assistant that synthesizes information across multiple meeting recordings. "
            "Answer the user's question using the recording transcripts below as your primary source. "
            "Cite specific recordings by their title and date when making claims. "
            "If something isn't covered in the provided recordings, say so.\n\n"
            f"RECORDINGS:\n\n{recordings_block}"
        ),
    }

    all_messages = [system_message, {"role": "user", "content": question}]

    client = _get_client()
    start_ms = int(time.time() * 1000)
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_chat_deployment or settings.azure_openai_mini_deployment or settings.azure_openai_deployment,
            messages=all_messages,
            reasoning_effort="low",
        )

        elapsed_ms = int(time.time() * 1000) - start_ms
        choice = response.choices[0]
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return ChatResponse(
            message=choice.message.content or "",
            usage=usage,
            response_time_ms=elapsed_ms,
        )
    finally:
        await client.close()


async def run_analysis(transcript: str, prompt_template: str) -> str:
    """Run a custom analysis prompt against a transcript.

    Args:
        transcript: The transcript text.
        prompt_template: A prompt string containing a {transcript} placeholder.

    Returns:
        The raw LLM response text.
    """
    settings = get_settings()
    truncated = _truncate_transcript(transcript)
    prompt_text = prompt_template.format(transcript=truncated)

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[{"role": "user", "content": prompt_text}],
        )

        return response.choices[0].message.content or ""
    finally:
        await client.close()
