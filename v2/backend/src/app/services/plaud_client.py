"""Plaud API client — isolated module for Plaud device sync.

Handles authentication, recording list fetching, and file downloads.
All Plaud-specific types stay in this module; the sync service maps
them to core Recording models at the boundary.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_PLAUD_API_BASE = "https://api.plaud.ai"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_DOWNLOAD_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# Browser-spoofing headers required by the Plaud API
_BROWSER_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "edit-from": "web",
    "origin": "https://app.plaud.ai",
    "referer": "https://app.plaud.ai/",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
}


@dataclass
class AudioFile:
    """A recording from the Plaud API."""

    id: str
    filename: str
    filesize: int
    filetype: str
    fullname: str
    duration: int  # milliseconds
    start_time: int  # unix ms
    end_time: int  # unix ms
    timezone: int  # offset hours
    zonemins: int
    serial_number: str = ""
    scene: int = 0
    is_trash: bool = False
    is_trans: bool = False
    is_summary: bool = False
    keywords: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.duration / 1000.0

    @property
    def recording_datetime(self) -> datetime:
        """Timezone-aware datetime from start_time."""
        ts_seconds = self.start_time / 1000.0
        tz = timezone(timedelta(hours=self.timezone))
        return datetime.fromtimestamp(ts_seconds, tz=tz)

    @property
    def file_extension(self) -> str:
        return os.path.splitext(self.fullname)[1].lstrip(".")


def _parse_audio_file(data: dict) -> AudioFile:
    """Parse an AudioFile from Plaud API JSON, ignoring unknown fields."""
    known_fields = {f.name for f in AudioFile.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return AudioFile(**filtered)


def _auth_headers(token: str) -> dict[str, str]:
    """Build request headers with auth token."""
    return {**_BROWSER_HEADERS, "authorization": f"bearer {token}"}


async def fetch_recordings(token: str) -> list[AudioFile]:
    """Fetch the full recording list from Plaud API.

    Args:
        token: Plaud bearer token.

    Returns:
        List of AudioFile objects, excluding trashed items.
    """
    url = f"{_PLAUD_API_BASE}/file/simple/web"
    params = {
        "skip": 0,
        "limit": 99999,
        "is_trash": 2,
        "sort_by": "start_time",
        "is_desc": "true",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_auth_headers(token))
        resp.raise_for_status()

    data = resp.json()
    file_list = data.get("data_file_list", [])
    recordings = [_parse_audio_file(f) for f in file_list]

    # Filter out trashed recordings
    recordings = [r for r in recordings if not r.is_trash]

    logger.info("Fetched %d recordings from Plaud API", len(recordings))
    return recordings


async def get_download_url(token: str, file_id: str) -> str:
    """Get a temporary S3 download URL for a Plaud file.

    Args:
        token: Plaud bearer token.
        file_id: Plaud file ID.

    Returns:
        Temporary presigned download URL.
    """
    url = f"{_PLAUD_API_BASE}/file/temp-url/{file_id}"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_auth_headers(token))
        resp.raise_for_status()

    return resp.json()["temp_url"]


async def download_file(
    token: str, audio_file: AudioFile, output_dir: str | Path
) -> Path:
    """Download a Plaud recording to a local file.

    Handles the .opus -> .mp3 quirk: Plaud labels some files as .opus
    but they are actually MP3-encoded.

    Args:
        token: Plaud bearer token.
        audio_file: The AudioFile to download.
        output_dir: Directory to save the file.

    Returns:
        Path to the downloaded file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build a descriptive filename
    date_str = audio_file.recording_datetime.strftime("%Y-%m-%d_%H-%M-%S")
    sanitized = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in audio_file.filename
    )

    extension = audio_file.file_extension
    # Plaud creates files with .opus extension but they are actually MP3
    if extension == "opus":
        extension = "mp3"

    filename = f"{date_str}_{sanitized}.{extension}"
    local_path = output_dir / filename

    # Get the temporary download URL and fetch the file
    download_url = await get_download_url(token, audio_file.id)

    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as client:
        resp = await client.get(download_url)
        resp.raise_for_status()

    local_path.write_bytes(resp.content)

    logger.info(
        "Downloaded %s (%d bytes, %.0fs)",
        filename,
        len(resp.content),
        audio_file.duration_seconds,
    )
    return local_path
