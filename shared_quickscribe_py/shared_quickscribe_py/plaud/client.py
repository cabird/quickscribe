"""
Plaud API Client for QuickScribe
Handles authentication, fetching recordings, and downloading from Plaud.AI
"""
import os
import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class AudioFile:
    """Represents a Plaud audio recording file."""
    id: str
    filename: str
    filesize: int
    filetype: str
    fullname: str
    file_md5: str
    ori_ready: bool
    version: int
    version_ms: int
    edit_time: int
    edit_from: str
    is_trash: bool
    start_time: int
    end_time: int
    duration: int
    timezone: int
    zonemins: int
    scene: int
    serial_number: str
    is_trans: bool
    is_summary: bool
    keywords: List[str] = field(default_factory=list)
    filetag_id_list: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self):
        """Return duration in seconds rather than milliseconds"""
        return self.duration / 1000

    @property
    def duration_formatted(self):
        """Return a human-readable duration format (MM:SS)"""
        seconds = int(self.duration / 1000)
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def recording_datetime(self):
        """Return a timezone-aware datetime object from start_time"""
        # Convert milliseconds to seconds
        start_time_seconds = self.start_time / 1000
        # Create timezone object
        tz = timezone(timedelta(hours=self.timezone))
        # Create and return datetime object
        return datetime.fromtimestamp(start_time_seconds, tz=tz)

    @property
    def file_extension(self):
        """Extract file extension from fullname"""
        return os.path.splitext(self.fullname)[1].lstrip('.')

    def to_metadata(self) -> Dict[str, Any]:
        """
        Convert AudioFile to PlaudMetadata format for storage in Recording.

        Returns:
            Dictionary matching the PlaudMetadata interface from Models.ts
        """
        return {
            "plaudId": self.id,
            "originalTimestamp": self.recording_datetime.isoformat(),
            "plaudFilename": self.filename,
            "plaudFileSize": self.filesize,
            "plaudDuration": self.duration,
            "plaudFileType": self.filetype,
            "syncedAt": datetime.now(timezone.utc).isoformat()
        }


@dataclass
class PlaudResponse:
    """Response from Plaud API containing audio files."""
    status: int
    msg: str
    data_file_total: int
    data_file_list: List[AudioFile]

    @classmethod
    def from_json(cls, data: Dict[str, Any]):
        """Create a PlaudResponse object from JSON data"""
        audio_files = [AudioFile(**file_data) for file_data in data["data_file_list"]]
        return cls(
            status=data["status"],
            msg=data["msg"],
            data_file_total=data["data_file_total"],
            data_file_list=audio_files
        )


class PlaudClient:
    """
    Client class for interacting with Plaud.AI API.
    Handles authentication, fetching recordings, and downloading.
    """

    def __init__(self, bearer_token: str, logger_instance: Optional[logging.Logger] = None):
        """
        Initialize the PlaudClient with authentication token

        Args:
            bearer_token: The Plaud API authentication token
            logger_instance: Optional logger instance to use for logging
        """
        self.bearer_token = bearer_token
        self.logger = logger_instance or logger
        self.session = requests.Session()
        self.session.headers.update(self._get_default_headers())

    def _get_default_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Plaud API requests"""
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'authorization': f'bearer {self.bearer_token}',
            'edit-from': 'web',
            'origin': 'https://app.plaud.ai',
            'priority': 'u=1, i',
            'referer': 'https://app.plaud.ai/',
            'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        }

    def get(self, url: str, params=None) -> requests.Response:
        """Make a GET request to the Plaud API"""
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response

    def fetch_recordings(
        self,
        limit: int = 99999,
        skip: int = 0,
        is_trash: int = 2,
        sort_by: str = 'start_time',
        is_desc: str = 'true'
    ) -> Optional[PlaudResponse]:
        """
        Fetch recordings from Plaud.AI API

        Args:
            limit: Maximum number of recordings to fetch
            skip: Number of recordings to skip
            is_trash: Filter by trash status (2: include all, 0: not trash, 1: trash only)
            sort_by: Field to sort by
            is_desc: Sort in descending order if 'true'

        Returns:
            PlaudResponse object or None if an error occurs
        """
        url = 'https://api.plaud.ai/file/simple/web'
        params = {
            'skip': skip,
            'limit': limit,
            'is_trash': is_trash,
            'sort_by': sort_by,
            'is_desc': is_desc
        }

        self.logger.info(f"Fetching recordings from Plaud.AI API")

        response = self.get(url, params=params)
        if response.content:
            result = PlaudResponse.from_json(response.json())
            self.logger.info(f"Successfully fetched {result.data_file_total} recordings from Plaud")
            return result
        return None

    def get_file_download_url(self, file_id: str) -> str:
        """
        Get the temporary Amazon S3 download URL for a file

        Args:
            file_id: Plaud file ID

        Returns:
            Temporary download URL
        """
        url = f'https://api.plaud.ai/file/temp-url/{file_id}'
        self.logger.info(f"Getting download URL for file {file_id}")

        response = self.get(url)
        return response.json()['temp_url']

    def download_file(self, audio_file: AudioFile, output_dir: str) -> Optional[str]:
        """
        Download an audio file using its ID

        Args:
            audio_file: AudioFile object to download
            output_dir: Directory to save the file

        Returns:
            Path to the downloaded file or None if download failed
        """
        os.makedirs(output_dir, exist_ok=True)

        # Create a more descriptive filename
        date_str = audio_file.recording_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        sanitized_name = ''.join(c if c.isalnum() or c in ['-', '_'] else '_' for c in audio_file.filename)

        extension = audio_file.file_extension
        # Plaud creates files with an opus extension but they are actually MP3 files
        if extension == 'opus':
            extension = 'mp3'
        filename = f"{date_str}_{sanitized_name}.{extension}"
        full_path = os.path.join(output_dir, filename)

        self.logger.info(f"Downloading file: {filename}")

        # Get download URL and fetch the file
        download_url = self.get_file_download_url(audio_file.id)
        response = requests.get(download_url)
        response.raise_for_status()

        with open(full_path, 'wb') as f:
            f.write(response.content)

        self.logger.info(f"Downloaded file: {filename} ({audio_file.duration_formatted})")
        return full_path

    def filter_recordings_by_ids(
        self,
        recordings: List[AudioFile],
        processed_ids: List[str]
    ) -> List[AudioFile]:
        """
        Filter out recordings that have already been processed

        Args:
            recordings: List of AudioFile objects
            processed_ids: List of Plaud IDs that have already been processed

        Returns:
            List of unprocessed AudioFile objects
        """
        return [r for r in recordings if r.id not in processed_ids]

    def filter_recordings_by_timestamp(
        self,
        recordings: List[AudioFile],
        after_timestamp: datetime
    ) -> List[AudioFile]:
        """
        Filter recordings to only include those after a certain timestamp

        Args:
            recordings: List of AudioFile objects
            after_timestamp: Only include recordings after this time

        Returns:
            List of AudioFile objects recorded after the given timestamp
        """
        # Ensure after_timestamp is timezone-aware
        if after_timestamp.tzinfo is None:
            after_timestamp = after_timestamp.replace(tzinfo=timezone.utc)

        # Compare in UTC to avoid timezone issues
        return [
            r for r in recordings
            if r.recording_datetime.astimezone(timezone.utc) > after_timestamp.astimezone(timezone.utc)
        ]
