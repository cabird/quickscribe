"""
Plaud processor for downloading, transcoding, and submitting recordings.
Handles large file chunking (>300MB or >2 hours).
"""
import os
import uuid
import tempfile
import time
import shutil
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path

import ffmpeg

from shared_quickscribe_py.config import QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, Recording, TranscodingStatus, TranscriptionStatus
)
from shared_quickscribe_py.cosmos.models import PlaudMetadata, TranscriptionJobStatus
from shared_quickscribe_py.azure_services import BlobStorageClient
from shared_quickscribe_py.plaud import PlaudClient
from logging_handler import JobLogger

# Azure Speech Services imports
import azure_speech_client


# Chunking thresholds
MAX_FILE_SIZE_MB = 300
MAX_DURATION_SECONDS = 2 * 60 * 60  # 2 hours
CHUNK_SIZE_MB = 200
CHUNK_DURATION_SECONDS = 1.5 * 60 * 60  # 1.5 hours


class PlaudProcessor:
    """
    Processes Plaud recordings: download, transcode, upload, submit for transcription.
    Handles large file chunking automatically.
    """

    def __init__(self, recording_handler: RecordingHandler,
                 blob_client: BlobStorageClient, plaud_client, logger: JobLogger,
                 settings: QuickScribeSettings,
                 test_run_id: Optional[str] = None):
        """
        Initialize Plaud processor.

        Args:
            recording_handler: Handler for recording database operations
            blob_client: Azure Blob Storage client
            plaud_client: Plaud API client
            logger: Job logger instance
            settings: Validated QuickScribeSettings instance
            test_run_id: Optional test run identifier
        """
        self.recording_handler = recording_handler
        self.blob_client = blob_client
        self.plaud_client = plaud_client
        self.logger = logger
        self.settings = settings
        self.test_run_id = test_run_id

        # Azure Speech Services configuration (from validated settings)
        self.speech_key = settings.speech_services.subscription_key
        self.speech_region = settings.speech_services.region

        # Initialize API client
        try:
            self.api_client = self._get_speech_api_client()
            self.api = azure_speech_client.CustomSpeechTranscriptionsApi(api_client=self.api_client)
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure Speech Services API client: {str(e)}")
            raise

    def _get_speech_api_client(self):
        """Create Azure Speech Services API client."""
        configuration = azure_speech_client.Configuration()
        configuration.api_key["Ocp-Apim-Subscription-Key"] = self.speech_key
        configuration.host = f"https://{self.speech_region}.api.cognitive.microsoft.com/speechtotext/v3.2"
        return azure_speech_client.ApiClient(configuration)

    def set_existing_plaud_ids(self, plaud_ids: List[str]):
        """
        Set the list of existing Plaud IDs for deduplication.

        Args:
            plaud_ids: List of Plaud IDs that already exist in the database
        """
        self._existing_plaud_ids = set(plaud_ids)
        self.logger.info(f"Loaded {len(plaud_ids)} existing Plaud IDs for deduplication")

    def process_recording(self, user, plaud_recording) -> Dict[str, int]:
        """
        Process a single Plaud recording.

        Returns:
            Stats dict with counts for downloaded, transcoded, uploaded, submitted, chunks_created, errors
        """
        stats = {
            "downloaded": 0,
            "transcoded": 0,
            "uploaded": 0,
            "submitted": 0,
            "chunks_created": 0,
            "errors": 0,
            "skipped": 0
        }

        self.logger.info(f"Processing recording: {plaud_recording.filename}")

        local_file = None
        try:
            # Safety check: This should have been filtered in job_executor, but check anyway
            if hasattr(self, '_existing_plaud_ids') and plaud_recording.id in self._existing_plaud_ids:
                self.logger.warning(
                    f"Unexpected duplicate (Plaud ID: {plaud_recording.id}) - "
                    f"should have been filtered in job_executor"
                )
                stats["skipped"] = 1
                return stats

            # Step 1: Download from Plaud
            local_file = self._download_recording(plaud_recording)
            if not local_file:
                self.logger.error(f"Failed to download recording: {plaud_recording.filename}")
                stats["errors"] = 1
                return stats
            stats["downloaded"] = 1

            # Step 2: Check if chunking is needed
            needs_chunking, file_size_mb, duration_seconds = self._check_if_needs_chunking(local_file)

            if needs_chunking:
                self.logger.info(f"Recording needs chunking (size: {file_size_mb:.1f}MB, duration: {duration_seconds:.0f}s)")
                chunk_stats = self._process_chunked_recording(
                    user, plaud_recording, local_file, duration_seconds
                )
                stats["chunks_created"] = chunk_stats["chunks_created"]
                stats["transcoded"] = chunk_stats["transcoded"]
                stats["uploaded"] = chunk_stats["uploaded"]
                stats["submitted"] = chunk_stats["submitted"]
                stats["errors"] = chunk_stats["errors"]
            else:
                # Process as single recording
                single_stats = self._process_single_recording(
                    user, plaud_recording, local_file
                )
                stats["transcoded"] = single_stats["transcoded"]
                stats["uploaded"] = single_stats["uploaded"]
                stats["submitted"] = single_stats["submitted"]
                stats["errors"] = single_stats["errors"]

        except Exception as e:
            self.logger.error(f"Error processing recording {plaud_recording.filename}: {str(e)}")
            stats["errors"] = 1
        finally:
            # Always clean up the downloaded file
            if local_file and os.path.exists(local_file):
                os.remove(local_file)
                self.logger.debug(f"Cleaned up temporary file: {local_file}")

        return stats

    def _download_recording(self, plaud_recording) -> Optional[str]:
        """Download recording from Plaud. Returns local file path."""
        try:
            self.logger.debug(f"Downloading: {plaud_recording.filename}")

            # Create temporary file
            suffix = self._get_file_extension(plaud_recording.filetype, plaud_recording.fullname)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                local_path = tmp_file.name

            # Get download URL from Plaud API
            download_url = self.plaud_client.get_file_download_url(plaud_recording.id)

            # Check available disk space (without HEAD request since S3 presigned URLs don't support it)
            _, _, free_space = shutil.disk_usage(tempfile.gettempdir())
            free_space_mb = free_space / (1024 * 1024)

            # Warn if very low disk space (< 500MB), but continue anyway
            if free_space_mb < 500:
                self.logger.warning(
                    f"Low disk space: {free_space_mb:.1f}MB available. "
                    f"Download may fail if file is too large."
                )
            else:
                self.logger.debug(f"Disk space available: {free_space_mb:.1f}MB")

            # Download the file
            # Note: S3 presigned URLs are method-specific, so HEAD requests fail with 403
            import requests
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.logger.info(f"Downloaded to: {local_path}")

            # Throttle to avoid rate limiting (5 seconds between downloads)
            time.sleep(5)

            return local_path

        except Exception as e:
            self.logger.error(f"Download failed: {str(e)}")
            return None

    def _get_file_extension(self, file_type: str, fullname: str = "") -> str:
        """Get file extension from file type, handling Plaud's opus-as-mp3 quirk.

        Falls back to extracting extension from fullname if file_type is empty.
        """
        extension = file_type.lower() if file_type else ""

        # If filetype is empty, extract from fullname (e.g., "abc123.opus" -> "opus")
        if not extension and fullname and "." in fullname:
            extension = fullname.rsplit(".", 1)[-1].lower()

        if extension == "opus":
            # Plaud .opus files are actually MP3
            extension = "mp3"

        # Default to mp3 if still no extension
        if not extension:
            extension = "mp3"

        return f".{extension}"

    def _check_if_needs_chunking(self, file_path: str) -> Tuple[bool, float, float]:
        """
        Check if file needs chunking.

        Returns:
            (needs_chunking, file_size_mb, duration_seconds)
        """
        # Get file size
        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Get duration using ffprobe
        try:
            probe = ffmpeg.probe(file_path)
            duration_seconds = float(probe['format']['duration'])
        except Exception as e:
            self.logger.warning(f"Could not probe duration: {str(e)}")
            duration_seconds = 0

        needs_chunking = (file_size_mb > MAX_FILE_SIZE_MB or
                          duration_seconds > MAX_DURATION_SECONDS)

        return needs_chunking, file_size_mb, duration_seconds

    def _process_single_recording(self, user, plaud_recording, local_file: str) -> Dict[str, int]:
        """Process recording without chunking with atomic cleanup on failure."""
        stats = {"transcoded": 0, "uploaded": 0, "submitted": 0, "errors": 0}

        # Track state for cleanup
        recording = None
        blob_uploaded = False
        transcoded_file = None

        try:
            # Step 1: Transcode to MP3 (no cleanup needed if this fails)
            transcoded_file = self._transcode_to_mp3(local_file)
            if not transcoded_file:
                stats["errors"] = 1
                return stats
            stats["transcoded"] = 1

            # Step 2: Create basic recording in Cosmos DB (POINT OF NO RETURN)
            recorded_timestamp = plaud_recording.recording_datetime.isoformat()
            title = plaud_recording.filename

            recording = self.recording_handler.create_recording(
                user_id=user.id,
                original_filename=plaud_recording.filename,
                unique_filename=f"placeholder.mp3",  # Will update with actual filename
                title=title,
                recorded_timestamp=recorded_timestamp,
                transcription_status=TranscriptionStatus.not_started,
                transcoding_status=TranscodingStatus.completed,
                source="plaud"
            )
            self.logger.info(f"Created recording in Cosmos: {recording.id}")

            # Step 3: Upload to blob storage using the recording ID
            blob_path = f"{user.id}/{recording.id}.mp3"
            blob_url = self._upload_to_blob(transcoded_file, blob_path)
            if not blob_url:
                raise Exception("Blob upload failed")
            blob_uploaded = True
            stats["uploaded"] = 1
            self.logger.info(f"Uploaded blob: {blob_path}")

            # Step 4: Add custom fields to recording
            recording.type = "recording"  # Required for queries to find this document
            recording.unique_filename = f"{user.id}/{recording.id}.mp3"
            recording.upload_timestamp = datetime.now(UTC).isoformat()
            recording.plaudMetadata = PlaudMetadata(**plaud_recording.to_metadata())
            recording.testRunId = self.test_run_id
            recording.duration = plaud_recording.duration_seconds
            recording.processing_failure_count = 0
            recording.needs_manual_review = False

            # Step 5: Update recording with all fields
            recording = self.recording_handler.update_recording(recording)
            self.logger.info(f"Updated recording with full metadata: {recording.id}")

            # Step 6: Submit for transcription (failure here is non-fatal)
            transcription_job_id = self._submit_transcription(recording, blob_url)
            if transcription_job_id:
                recording.transcription_job_id = transcription_job_id
                recording.transcription_job_status = TranscriptionJobStatus.submitted
                self.recording_handler.update_recording(recording)
                stats["submitted"] = 1
                self.logger.info(f"Submitted for transcription: {transcription_job_id}")
            else:
                # Transcription submission failed, but keep the recording
                # User can retry transcription manually
                self.logger.warning(f"Transcription submission failed for {recording.id}, but recording is saved")

        except Exception as e:
            self.logger.error(f"Error processing single recording: {str(e)}")
            stats["errors"] = 1

            # ATOMIC CLEANUP: Delete everything created if any step failed
            if recording:
                self.logger.warning(f"Cleaning up failed recording: {recording.id}")
                self._cleanup_failed_recording(recording.id, user.id, blob_uploaded)

        finally:
            # Always clean up temporary transcoded file
            if transcoded_file and os.path.exists(transcoded_file):
                os.remove(transcoded_file)

        return stats

    def _process_chunked_recording(self, user, plaud_recording,
                                    local_file: str, total_duration: float) -> Dict[str, int]:
        """Process recording with chunking and atomic cleanup on failure."""
        stats = {"chunks_created": 0, "transcoded": 0, "uploaded": 0, "submitted": 0, "errors": 0}

        # Generate chunk group ID to link all chunks together
        import uuid
        chunk_group_id = str(uuid.uuid4())
        self.logger.info(f"Processing chunked recording with group ID: {chunk_group_id}")

        try:
            # Calculate number of chunks needed
            num_chunks = int((total_duration / CHUNK_DURATION_SECONDS) + 0.5)
            if num_chunks < 2:
                num_chunks = 2

            self.logger.info(f"Splitting into {num_chunks} chunks")

            # Split the file
            chunk_files = self._split_audio(local_file, num_chunks, total_duration)
            stats["chunks_created"] = len(chunk_files)

            # Process each chunk
            for i, chunk_file in enumerate(chunk_files):
                chunk_number = i + 1
                self.logger.info(f"Processing chunk {chunk_number} of {num_chunks}")

                transcoded_chunk = None

                try:
                    # Step 1: Transcode chunk (no cleanup needed if this fails)
                    transcoded_chunk = self._transcode_to_mp3(chunk_file)
                    if not transcoded_chunk:
                        raise Exception(f"Chunk {chunk_number} transcode failed")
                    stats["transcoded"] += 1

                    # Step 2: Create recording in Cosmos DB (POINT OF NO RETURN)
                    chunk_timestamp = plaud_recording.recording_datetime + timedelta(seconds=(i * CHUNK_DURATION_SECONDS))
                    chunk_title = f"{plaud_recording.filename} - Part {chunk_number} of {num_chunks}"

                    chunk_recording = self.recording_handler.create_recording(
                        user_id=user.id,
                        original_filename=plaud_recording.filename,
                        unique_filename=f"placeholder.mp3",  # Will update with actual filename
                        title=chunk_title,
                        recorded_timestamp=chunk_timestamp.isoformat(),
                        transcription_status=TranscriptionStatus.not_started,
                        transcoding_status=TranscodingStatus.completed,
                        source="plaud"
                    )
                    self.logger.info(f"Created chunk recording: {chunk_recording.id}")

                    # Step 3: Upload chunk to blob storage
                    blob_path = f"{user.id}/{chunk_recording.id}.mp3"
                    blob_url = self._upload_to_blob(transcoded_chunk, blob_path)
                    if not blob_url:
                        raise Exception(f"Chunk {chunk_number} blob upload failed")
                    stats["uploaded"] += 1
                    self.logger.info(f"Uploaded chunk blob: {blob_path}")

                    # Step 4: Add custom fields including chunkGroupId
                    chunk_recording.type = "recording"  # Required for queries to find this document
                    chunk_recording.unique_filename = f"{user.id}/{chunk_recording.id}.mp3"
                    chunk_recording.upload_timestamp = datetime.now(UTC).isoformat()
                    chunk_recording.plaudMetadata = PlaudMetadata(**plaud_recording.to_metadata())
                    chunk_recording.testRunId = self.test_run_id
                    chunk_recording.chunkGroupId = chunk_group_id  # Link to group
                    chunk_recording.duration = CHUNK_DURATION_SECONDS
                    chunk_recording.processing_failure_count = 0
                    chunk_recording.needs_manual_review = False

                    # Step 5: Update recording with all fields
                    chunk_recording = self.recording_handler.update_recording(chunk_recording)
                    self.logger.info(f"Updated chunk with metadata: {chunk_recording.id}")

                    # Step 6: Submit for transcription (failure here is non-fatal)
                    transcription_job_id = self._submit_transcription(chunk_recording, blob_url)
                    if transcription_job_id:
                        chunk_recording.transcription_job_id = transcription_job_id
                        chunk_recording.transcription_job_status = TranscriptionJobStatus.submitted
                        self.recording_handler.update_recording(chunk_recording)
                        stats["submitted"] += 1
                        self.logger.info(f"Submitted chunk for transcription: {transcription_job_id}")
                    else:
                        self.logger.warning(f"Transcription submission failed for chunk {chunk_number}, but chunk is saved")

                except Exception as e:
                    self.logger.error(f"Error processing chunk {chunk_number}: {str(e)}")
                    stats["errors"] += 1

                    # ATOMIC CLEANUP: If ANY chunk fails, cleanup ALL chunks in the group
                    self.logger.warning(f"Chunk {chunk_number} failed, cleaning up entire chunk group: {chunk_group_id}")
                    self._cleanup_chunk_group(chunk_group_id)

                    # Re-raise to stop processing remaining chunks
                    raise Exception(f"Chunk group {chunk_group_id} failed at chunk {chunk_number}")

                finally:
                    # Always clean up temporary files
                    if transcoded_chunk and os.path.exists(transcoded_chunk):
                        os.remove(transcoded_chunk)
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)

            # Success: All chunks processed successfully
            self.logger.info(f"Successfully processed all {num_chunks} chunks for group {chunk_group_id}")

        except Exception as e:
            self.logger.error(f"Error processing chunked recording: {str(e)}")
            stats["errors"] += 1

        return stats

    def _split_audio(self, input_file: str, num_chunks: int, total_duration: float) -> List[str]:
        """Split audio file into chunks."""
        chunk_files = []
        chunk_duration = total_duration / num_chunks

        for i in range(num_chunks):
            start_time = i * chunk_duration

            # Construct chunk filename using stem (works for all cases)
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_chunk{i+1}.mp3")

            try:
                # Use ffmpeg to extract chunk
                (
                    ffmpeg
                    .input(input_file, ss=start_time, t=chunk_duration)
                    .output(output_file, codec='copy')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                chunk_files.append(output_file)

            except ffmpeg.Error as e:
                self.logger.error(f"Error splitting chunk {i+1}: {str(e)}")
                if e.stderr:
                    stderr_output = e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else str(e.stderr)
                    self.logger.error(f"FFmpeg stderr: {stderr_output}")
            except Exception as e:
                self.logger.error(f"Error splitting chunk {i+1} (unexpected): {str(e)}")

        return chunk_files

    def _transcode_to_mp3(self, input_file: str) -> Optional[str]:
        """Transcode audio file to standard MP3 format."""
        try:
            # Construct output filename using stem (works for all cases)
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_transcoded.mp3")

            self.logger.debug(f"Transcoding to: {output_file}")

            # Transcode with ffmpeg
            (
                ffmpeg
                .input(input_file)
                .output(output_file, acodec='libmp3lame', audio_bitrate='128k')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            self.logger.info(f"Transcoding complete: {output_file}")

            # Verify the file exists
            if not os.path.exists(output_file):
                self.logger.error(f"Transcoded file does not exist after ffmpeg: {output_file}")
                return None

            return output_file

        except ffmpeg.Error as e:
            self.logger.error(f"Transcoding failed: {str(e)}")
            if e.stderr:
                stderr_output = e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else str(e.stderr)
                self.logger.error(f"FFmpeg stderr: {stderr_output}")
            return None
        except Exception as e:
            self.logger.error(f"Transcoding failed with unexpected error: {str(e)}")
            return None

    def _upload_to_blob(self, file_path: str, blob_path: str) -> Optional[str]:
        """Upload file to Azure Blob Storage."""
        try:
            self.logger.debug(f"Uploading local file '{file_path}' to blob: {blob_path}")

            # Check if local file exists
            if not os.path.exists(file_path):
                self.logger.error(f"Local file does not exist: {file_path}")
                return None

            # Upload file (method expects: local_file_path, blob_name)
            self.blob_client.upload_file(file_path, blob_path)

            # Generate SAS URL for Azure Speech Services
            blob_url = self.blob_client.generate_sas_url(blob_path, hours=48)

            self.logger.info("Upload complete")
            return blob_url

        except Exception as e:
            self.logger.error(f"Upload failed for local file '{file_path}' to blob '{blob_path}': {str(e)}")
            return None

    def _submit_transcription(self, recording: Recording, blob_sas_url: str) -> Optional[str]:
        """Submit recording for batch transcription to Azure Speech Services."""
        try:
            self.logger.debug(f"Submitting transcription for: {recording.title}")

            # Create transcription properties
            properties = azure_speech_client.TranscriptionProperties()
            properties.punctuation_mode = "DictatedAndAutomatic"
            properties.diarization_enabled = True
            properties.diarization = azure_speech_client.DiarizationProperties(
                azure_speech_client.DiarizationSpeakersProperties(min_count=1, max_count=5)
            )

            # Create transcription definition
            name = f"Transcription of {recording.title}"
            description = f"Transcription started at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"

            transcription_definition = azure_speech_client.Transcription(
                display_name=name,
                description=description,
                locale="en-US",
                content_urls=[blob_sas_url],
                properties=properties
            )

            # Submit transcription
            created_transcription, status, headers = self.api.transcriptions_create_with_http_info(
                transcription=transcription_definition
            )

            # Extract transcription ID from location header
            transcription_id = headers["location"].split("/")[-1]

            self.logger.info(f"Transcription submitted: {transcription_id}")
            return transcription_id

        except Exception as e:
            self.logger.error(f"Transcription submission failed: {str(e)}")
            return None

    def _cleanup_failed_recording(self, recording_id: str, user_id: str, blob_uploaded: bool = False):
        """
        Clean up a failed recording to maintain atomicity.
        Deletes both the Cosmos DB record and the blob storage file.

        :param recording_id: Recording ID to delete
        :param user_id: User ID for blob path construction
        :param blob_uploaded: Whether the blob was successfully uploaded (if True, delete it)
        """
        try:
            self.logger.info(f"Cleaning up failed recording: {recording_id}")

            # Delete blob if it was uploaded
            if blob_uploaded:
                blob_path = f"{user_id}/{recording_id}.mp3"
                try:
                    if self.blob_client.blob_exists(blob_path):
                        self.blob_client.delete_file(blob_path)
                        self.logger.info(f"Deleted blob: {blob_path}")
                except Exception as e:
                    self.logger.error(f"Failed to delete blob {blob_path}: {str(e)}")

            # Delete from Cosmos
            try:
                self.recording_handler.delete_recording(recording_id)
                self.logger.info(f"Deleted recording from Cosmos: {recording_id}")
            except Exception as e:
                self.logger.error(f"Failed to delete recording {recording_id}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Failed to cleanup recording {recording_id}: {str(e)}")

    def _cleanup_chunk_group(self, chunk_group_id: str):
        """
        Clean up all recordings in a chunk group after a failure.
        Deletes all chunk recordings and their associated blobs.

        :param chunk_group_id: UUID of the chunk group to clean up
        """
        try:
            self.logger.info(f"Cleaning up chunk group: {chunk_group_id}")

            # Query for all recordings with this chunkGroupId
            query = """
                SELECT * FROM c
                WHERE c.type = 'recording'
                AND c.chunkGroupId = @chunk_group_id
            """
            parameters = [{"name": "@chunk_group_id", "value": chunk_group_id}]

            chunks = list(self.recording_handler.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            self.logger.info(f"Found {len(chunks)} chunks to clean up")

            # Delete each chunk (recording + blob)
            for chunk in chunks:
                chunk_id = chunk['id']
                user_id = chunk['user_id']
                blob_path = f"{user_id}/{chunk_id}.mp3"

                try:
                    # Delete blob
                    if self.blob_client.blob_exists(blob_path):
                        self.blob_client.delete_file(blob_path)
                        self.logger.info(f"Deleted blob: {blob_path}")

                    # Delete recording
                    self.recording_handler.delete_recording(chunk_id)
                    self.logger.info(f"Deleted chunk recording: {chunk_id}")

                except Exception as e:
                    self.logger.error(f"Failed to delete chunk {chunk_id}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Failed to cleanup chunk group {chunk_group_id}: {str(e)}")
