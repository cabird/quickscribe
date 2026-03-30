"""Handwritten Azure Speech Services v3.2 batch transcription client.

Replaces the 120-file auto-generated Swagger client with ~150 lines of httpx.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class SpeechClient:
    """Minimal Azure Speech Services v3.2 batch transcription client."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = (
            f"https://{settings.speech_services_region}"
            f".api.cognitive.microsoft.com/speechtotext/v3.2/"
        )
        self.headers = {
            "Ocp-Apim-Subscription-Key": settings.speech_services_key,
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    async def create_transcription(
        self,
        audio_url: str,
        display_name: str,
        locale: str = "en-US",
        min_speakers: int = 1,
        max_speakers: int = 5,
    ) -> str:
        """Submit a batch transcription job.

        Args:
            audio_url: Public or SAS-signed URL to the audio file.
            display_name: Human-readable name for the job.
            locale: Language locale.
            min_speakers: Minimum expected speakers for diarization.
            max_speakers: Maximum expected speakers for diarization.

        Returns:
            The transcription ID extracted from the self link.
        """
        payload = {
            "contentUrls": [audio_url],
            "displayName": display_name,
            "locale": locale,
            "properties": {
                "diarizationEnabled": True,
                "diarization": {
                    "speakers": {
                        "minCount": min_speakers,
                        "maxCount": max_speakers,
                    }
                },
                "wordLevelTimestampsEnabled": True,
                "punctuationMode": "DictatedAndAutomatic",
                "profanityFilterMode": "None",
            },
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                self._url("transcriptions"),
                json=payload,
                headers=self.headers,
            )
            resp.raise_for_status()

        data = resp.json()
        # The self link looks like .../transcriptions/{id}
        self_link = data.get("self", "")
        transcription_id = self_link.rstrip("/").rsplit("/", 1)[-1]

        logger.info(
            "Created transcription %s for %s", transcription_id, display_name
        )
        return transcription_id

    async def get_transcription(self, transcription_id: str) -> dict:
        """Get transcription status and metadata.

        Args:
            transcription_id: The transcription job ID.

        Returns:
            Full transcription object with status, createdDateTime, etc.
            Key field: status ("NotStarted", "Running", "Succeeded", "Failed").
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                self._url(f"transcriptions/{transcription_id}"),
                headers=self.headers,
            )
            resp.raise_for_status()

        return resp.json()

    async def get_transcript_content(self, transcription_id: str) -> dict:
        """Download the completed transcript JSON.

        Fetches the files list for the transcription, finds the transcript
        result file, and downloads its content.

        Args:
            transcription_id: The transcription job ID.

        Returns:
            The parsed transcript JSON containing combinedRecognizedPhrases,
            recognizedPhrases, etc.

        Raises:
            RuntimeError: If no transcript file is found.
        """
        # Step 1: list files for this transcription
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                self._url(f"transcriptions/{transcription_id}/files"),
                headers=self.headers,
            )
            resp.raise_for_status()

        files_data = resp.json()
        values = files_data.get("values", [])

        # Step 2: find the transcription result file
        content_url: str | None = None
        for file_entry in values:
            if file_entry.get("kind") == "Transcription":
                links = file_entry.get("links", {})
                content_url = links.get("contentUrl")
                break

        if not content_url:
            raise RuntimeError(
                f"No transcript file found for transcription {transcription_id}"
            )

        # Step 3: download the transcript content (no auth header needed, SAS in URL)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(content_url)
            resp.raise_for_status()

        logger.info("Downloaded transcript content for %s", transcription_id)
        return resp.json()

    async def delete_transcription(self, transcription_id: str) -> None:
        """Delete a transcription job and its results.

        Args:
            transcription_id: The transcription job ID.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(
                self._url(f"transcriptions/{transcription_id}"),
                headers=self.headers,
            )
            # 204 No Content is expected; 404 means already deleted
            if resp.status_code not in (204, 404):
                resp.raise_for_status()

        logger.info("Deleted transcription %s", transcription_id)
