import os
import time
import traceback
import requests
import tempfile
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

# Constants
RATE_LIMITING_SLEEP_SECONDS = 60

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

class PlaudManager:
    """
    Manager class for interacting with Plaud.AI API.
    Handles authentication, fetching recordings, and downloading.
    """
    
    def __init__(self, bearer_token: str, logger):
        """
        Initialize the PlaudManager with authentication token and logger
        
        Args:
            bearer_token: The Plaud API authentication token
            logger: Logger instance to use for logging
        """
        self.bearer_token = bearer_token
        self.logger = logger
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
    
    def fetch_recordings(self, limit=99999, skip=0, is_trash=2, sort_by='start_time', is_desc='true') -> Optional[PlaudResponse]:
        """
        Fetch recordings from Plaud.AI API
        
        Args:
            limit: Maximum number of recordings to fetch
            skip: Number of recordings to skip
            is_trash: Filter by trash status (2: include all)
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

    def get_file_amazon_url(self, file_id: str) -> str:
        """
        Get the temporary Amazon S3 URL for a file
        
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
        # for some reason, plaud creates file with an opus extension but they actually are mp3 files
        if extension == 'opus':
            extension = 'mp3'
        filename = f"{date_str}_{sanitized_name}.{extension}"
        full_path = os.path.join(output_dir, filename)
        
        self.logger.info(f"Downloading to file: {filename} ")
        
        # Get download URL and fetch the file
        url = self.get_file_amazon_url(audio_file.id)
        response = requests.get(url)
        response.raise_for_status()
        
        with open(full_path, 'wb') as f:
            f.write(response.content)
            
        self.logger.info(f"Downloaded file: {filename} ({audio_file.duration_formatted})")
        return full_path


def handle_plaud_sync(message_content: dict, logger, transcode_func, send_callbacks_func, container_version):
    """
    Handle a Plaud sync request.
    
    Fetches recordings from Plaud, downloads them, transcodes to MP3,
    registers with backend, and uploads to Blob Storage.
    
    Args:
        message_content: The queue message content
        logger: Logger instance to use
        transcode_func: Function to transcode audio files
        send_callbacks_func: Function to send callbacks to backend
        container_version: Version string for the container
    """
    # Extract message content
    user_id = message_content.get('user_id')
    bearer_token = message_content.get('bearerToken')
    last_sync = message_content.get('lastSyncTimestamp')
    processed_ids = message_content.get('processedPlaudIds', [])
    callbacks = message_content.get('callbacks', [])
    callback_token = message_content.get('callback_token', '')
    dry_run = message_content.get('dry_run', False)
    
    # Basic response template
    response_template = {
        'action': 'plaud_sync',
        'user_id': user_id,
        'container_version': container_version,
        'callback_token': callback_token,
        'dry_run': dry_run
    }
    
    # Validation
    if not bearer_token:
        error_response = {
            **response_template,
            'status': 'failed',
            'error_message': 'Missing Plaud bearer token'
        }
        send_callbacks_func(callbacks, error_response)
        return
        
    if not callbacks:
        logger.error("No callbacks provided for Plaud sync")
        return

    # Main callback URL and token for registration
    callback_url = callbacks[0]['url'] if callbacks else None
    callback_registration_token = callbacks[0]['token'] if callbacks else None
    
    logger.info(f"Starting Plaud sync for user {user_id}")
    
    # Send initial in_progress callback
    in_progress_response = {
        **response_template,
        'status': 'in_progress',
        'message': 'Starting Plaud synchronization'
    }
    send_callbacks_func(callbacks, in_progress_response)
    
    try:
        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize Plaud manager and fetch recordings
            plaud_manager = PlaudManager(bearer_token, logger)
            start_time = time.time()
            
            # Fetch all recordings from Plaud
            plaud_data = plaud_manager.fetch_recordings()
            
            if not plaud_data or not plaud_data.data_file_list:
                logger.info("No recordings found or error occurred")
                error_response = {
                    **response_template,
                    'status': 'failed',
                    'error_message': "No recordings found or API error"
                }
                send_callbacks_func(callbacks, error_response)
                return
            
            # Filter recordings
            all_recordings = plaud_data.data_file_list
            new_recordings = [r for r in all_recordings if r.id not in processed_ids]
            logger.info(f"Found {len(new_recordings)} new recordings to process")
            
            # Filter by timestamp if provided
            if last_sync:
                try:
                    last_sync_dt = datetime.fromisoformat(last_sync)
                    # Ensure last_sync_dt is timezone-aware
                    if last_sync_dt.tzinfo is None:
                        # If no timezone, assume UTC
                        last_sync_dt = last_sync_dt.replace(tzinfo=timezone.utc)
                    
                    # Compare in UTC to avoid timezone issues
                    new_recordings = [r for r in new_recordings 
                                     if r.recording_datetime.astimezone(timezone.utc) > last_sync_dt.astimezone(timezone.utc)]
                    
                    logger.info(f"After timestamp filtering: {len(new_recordings)} new recordings")
                except Exception as e:
                    logger.error(f"Error parsing timestamp {last_sync}: {e}")
            
            # Calculate skipped recordings
            skipped_recordings = plaud_data.data_file_total - len(new_recordings)
            
            # To track successfully processed recordings and errors
            processed_recordings = []
            errors = []
            
            # Process each recording individually
            for idx, recording in enumerate(new_recordings):
                recording_start_time = time.time()
                logger.info(f"Processing recording {idx+1}/{len(new_recordings)}: {recording.filename}")
                
                # For tracking files to clean up
                downloaded_path = None
                mp3_output_path = None
                
                try:
                    # STEP 1: Download the file
                    logger.info(f"Downloading recording: {recording.id}")
                    downloaded_path = plaud_manager.download_file(recording, temp_dir)
                    if not downloaded_path:
                        raise Exception("Failed to download file")
                    
                    # STEP 2: Transcode to MP3
                    logger.info(f"Transcoding {downloaded_path} to MP3")
                    mp3_output_path = os.path.splitext(downloaded_path)[0] + "_transcoded.mp3"
                    transcode_func(downloaded_path, mp3_output_path)
                    logger.info(f"Transcoding complete: {mp3_output_path}")
                    
                    # STEP 3: Register with backend
                    logger.info(f"Registering recording with backend")
                    registration_data = {
                        "action": "register_plaud_recording",
                        "callback_token": callback_registration_token,
                        "user_id": user_id,
                        "plaud_id": recording.id,
                        "original_filename": recording.filename,
                        "original_timestamp": recording.recording_datetime.isoformat(),
                        "duration": recording.duration_seconds,
                        "filesize": recording.filesize,
                        "filetype": recording.file_extension,
                        "dry_run": dry_run
                    }
                    
                    registration_response = requests.post(callback_url, json=registration_data)
                    registration_response.raise_for_status()
                    registration_result = registration_response.json()
                    
                    if not registration_result.get('success'):
                        error_msg = registration_result.get('error', 'Unknown error from backend')
                        logger.error(f"Failed to register recording: {error_msg}")
                        raise Exception(f"Registration error: {error_msg}")
                    
                    sas_url = registration_result.get('sas_url')
                    recording_id = registration_result.get('recording_id')
                    
                    if not sas_url:
                        logger.error("No SAS URL received from backend")
                        raise Exception("No SAS URL received from backend")
                    
                    # STEP 4: Upload to Blob Storage
                    logger.info(f"Uploading to blob storage using SAS URL")
                    with open(mp3_output_path, 'rb') as data:
                        headers = {'x-ms-blob-type': 'BlockBlob'}
                        upload_response = requests.put(sas_url, data=data, headers=headers)
                        upload_response.raise_for_status()
                    
                    logger.info(f"Upload complete for recording {recording_id}")
                    
                    # STEP 5: Send individual success callback for this recording
                    success_response = {
                        **response_template,
                        'status': 'recording_processed',
                        'plaud_id': recording.id,
                        'recording_id': recording_id,
                        'original_filename': recording.filename,
                        'duration': recording.duration_seconds,
                        'original_timestamp': recording.recording_datetime.isoformat(),
                        'processing_time': time.time() - recording_start_time
                    }
                    send_callbacks_func(callbacks, success_response)
                    
                    # Add to successful recordings list
                    processed_recordings.append({
                        'recording_id': recording_id,
                        'plaud_id': recording.id,
                        'original_filename': recording.filename,
                        'duration': recording.duration_seconds,
                        'original_timestamp': recording.recording_datetime.isoformat()
                    })
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing recording {recording.id}: {error_msg}")
                    
                    # Send individual error callback for this recording
                    error_response = {
                        **response_template,
                        'status': 'recording_failed',
                        'plaud_id': recording.id,
                        'original_filename': recording.filename,
                        'error_message': error_msg,
                        'processing_time': time.time() - recording_start_time
                    }
                    send_callbacks_func(callbacks, error_response)
                    
                    # Add to errors list
                    errors.append(f"Error processing {recording.id}: {error_msg}")
                
                finally:
                    # Clean up files for this recording
                    try:
                        if downloaded_path and os.path.exists(downloaded_path):
                            os.remove(downloaded_path)
                        if mp3_output_path and os.path.exists(mp3_output_path):
                            os.remove(mp3_output_path)
                    except Exception as e:
                        logger.warning(f"Error cleaning up temporary files: {e}")
                
                # Rate limiting before next recording
                if idx < len(new_recordings) - 1:
                    logger.info(f"Waiting {RATE_LIMITING_SLEEP_SECONDS} seconds before next recording")
                    time.sleep(RATE_LIMITING_SLEEP_SECONDS)
            
            # Calculate total processing time
            total_processing_time = time.time() - start_time
            
            # Send final completion callback with summary
            completed_response = {
                **response_template,
                'status': 'completed',
                'total_recordings_found': plaud_data.data_file_total,
                'new_recordings_processed': len(processed_recordings),
                'skipped_recordings': skipped_recordings,
                'error_count': len(errors),
                'errors': errors[:10],  # Limit number of errors to avoid huge payload
                'processing_time': total_processing_time,
                'processed_recordings': processed_recordings
            }
            send_callbacks_func(callbacks, completed_response)
            
            logger.info(f"Plaud sync completed: {len(processed_recordings)} recordings processed, {len(errors)} errors")
        
    except Exception as e:
        logger.error(f"Error in Plaud sync: {e}")
        traceback_str = traceback.format_exc()
        logger.error(f"Traceback: {traceback_str}")
        
        # Send error callback for the overall process
        error_response = {
            **response_template,
            'status': 'failed',
            'error_message': str(e),
            'traceback': traceback_str
        }
        send_callbacks_func(callbacks, error_response)