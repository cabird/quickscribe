"""
Transcription poller for checking Azure Speech Services status.
Polls pending transcriptions and updates recording/transcription records when complete.
"""
import os
import json
import uuid
import asyncio
import yaml
from datetime import datetime, UTC
from typing import Optional

from shared_quickscribe_py.config import QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, TranscriptionHandler, ManualReviewItemHandler,
    Recording, Transcription, TranscriptionStatus, ManualReviewItem, FailureRecord
)
from shared_quickscribe_py.cosmos.models import TranscriptionJobStatus
from shared_quickscribe_py.azure_services.azure_openai import get_openai_client
from logging_handler import JobLogger

# Azure Speech Services imports
import azure_speech_client
import requests

# Maximum number of processing failures before manual review is required
MAX_PROCESSING_FAILURES = 3

# Load prompts for AI post-processing
# Get the directory where this script is located
_script_dir = os.path.dirname(os.path.abspath(__file__))
_prompts_path = os.path.join(_script_dir, "prompts.yaml")

with open(_prompts_path, 'r') as stream:
    prompts = yaml.safe_load(stream)

generate_title_and_description_prompt = prompts['prompts']['generate_title_and_description']['prompt']


class TranscriptionPoller:
    """
    Polls Azure Speech Services for transcription status and updates records.
    """

    def __init__(self, recording_handler: RecordingHandler,
                 transcription_handler: TranscriptionHandler,
                 manual_review_handler: ManualReviewItemHandler,
                 logger: JobLogger,
                 settings: QuickScribeSettings,
                 test_run_id: Optional[str] = None):
        """
        Initialize transcription poller.

        Args:
            recording_handler: Handler for recording database operations
            transcription_handler: Handler for transcription database operations
            manual_review_handler: Handler for manual review items
            logger: Job logger instance
            settings: Validated QuickScribeSettings instance
            test_run_id: Optional test run identifier
        """
        self.recording_handler = recording_handler
        self.transcription_handler = transcription_handler
        self.manual_review_handler = manual_review_handler
        self.logger = logger
        self.settings = settings
        self.test_run_id = test_run_id

        # Azure Speech Services configuration (from validated settings)
        self.speech_key = settings.speech_services.subscription_key
        self.speech_region = settings.speech_services.region

        # Check if AI post-processing is enabled via feature flag
        self.ai_postprocessing_enabled = settings.ai_enabled
        if self.ai_postprocessing_enabled:
            self.logger.info("AI post-processing enabled (Azure OpenAI configured)")
        else:
            self.logger.warning(
                "AI post-processing DISABLED - AI_ENABLED=false. "
                "Recordings will not get AI-generated titles and descriptions."
            )

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

    def check_and_update_transcription(self, recording: Recording) -> bool:
        """
        Check transcription status for a recording and update if completed.

        Args:
            recording: Recording with pending transcription

        Returns:
            True if transcription completed, False otherwise
        """
        if not recording.transcription_job_id:
            self.logger.warning(f"Recording {recording.id} has no transcription_job_id", recording.id)
            return False

        self.logger.info(f"\n--- Checking Recording: {recording.title} ---", recording.id)
        self.logger.info(f"  Recording ID: {recording.id}", recording.id)
        self.logger.info(f"  Azure Job ID: {recording.transcription_job_id}", recording.id)

        try:
            # Get transcription status from Azure
            az_transcription = self.api.transcriptions_get(recording.transcription_job_id)
            status = az_transcription.status  # "NotStarted", "Running", "Succeeded", "Failed"

            # Display Azure API response details
            self.logger.info(f"  === Azure Speech Services Response ===", recording.id)
            self.logger.info(f"    Status: {status}", recording.id)
            if hasattr(az_transcription, 'created_date_time'):
                self.logger.info(f"    Created: {az_transcription.created_date_time}", recording.id)
            if hasattr(az_transcription, 'last_action_date_time'):
                self.logger.info(f"    Last Action: {az_transcription.last_action_date_time}", recording.id)
            if hasattr(az_transcription, 'properties') and az_transcription.properties:
                if hasattr(az_transcription.properties, 'duration'):
                    self.logger.info(f"    Duration: {az_transcription.properties.duration}", recording.id)
                if hasattr(az_transcription.properties, 'duration_in_ticks'):
                    self.logger.info(f"    Duration (ticks): {az_transcription.properties.duration_in_ticks}", recording.id)

            # Update last check time
            recording.last_check_time = datetime.now(UTC).isoformat()

            if status == "Succeeded":
                self.logger.info(f"  ✓ SUCCEEDED - Processing completed transcription", recording.id)
                self._handle_completed_transcription(recording, az_transcription)
                return True

            elif status == "Failed":
                error_msg = "Unknown error"
                if az_transcription.properties and az_transcription.properties.error:
                    error_code = az_transcription.properties.error.code
                    error_message = az_transcription.properties.error.message
                    error_msg = f"{error_code}: {error_message}"

                self.logger.error(f"  ✗ FAILED - {error_msg}", recording.id)
                self.logger.info(f"  Action: Updating Cosmos DB with failure status", recording.id)
                recording.transcription_job_status = TranscriptionJobStatus.failed
                recording.transcription_status = TranscriptionStatus.failed
                recording.transcription_error_message = error_msg
                self.recording_handler.update_recording(recording)

                # Track failure
                self._track_failure(recording, "transcription_failed", error_msg)
                return False

            elif status in ["Running", "NotStarted"]:
                new_status = TranscriptionJobStatus.processing if status == "Running" else TranscriptionJobStatus.submitted
                new_status_str = "processing" if status == "Running" else "submitted"
                self.logger.info(f"  ⧗ {status.upper()} - Still in progress", recording.id)
                self.logger.info(f"  Action: Updating Cosmos DB status to '{new_status_str}'", recording.id)
                recording.transcription_job_status = new_status
                self.recording_handler.update_recording(recording)
                return False

            else:
                self.logger.warning(f"  ? UNKNOWN STATUS: {status}", recording.id)
                return False

        except Exception as e:
            self.logger.error(f"Error checking transcription status: {str(e)}", recording.id)
            return False

    def _handle_completed_transcription(self, recording: Recording, az_transcription):
        """Process completed transcription and update database."""
        try:
            self.logger.info(f"  === Processing Completed Transcription ===", recording.id)

            # Get or create transcription record
            transcription = self.transcription_handler.get_transcription_by_recording(recording.id)
            if not transcription:
                self.logger.info(f"  Step 1: Creating new transcription record in Cosmos DB", recording.id)
                transcription = self.transcription_handler.create_transcription(
                    recording.user_id, recording.id, test_run_id=self.test_run_id
                )
            else:
                self.logger.info(f"  Step 1: Found existing transcription record: {transcription.id}", recording.id)

            # Store raw transcription data
            transcription.az_transcription_id = recording.transcription_job_id
            transcription.az_raw_transcription = str(az_transcription)

            # Download transcript JSON
            self.logger.info(f"  Step 2: Downloading transcript content from Azure", recording.id)
            transcript_json = self._download_transcript(recording.transcription_job_id)

            if transcript_json:
                transcription.transcript_json = transcript_json
                json_data = json.loads(transcript_json)

                # Count phrases for reporting
                phrase_count = len(json_data.get("recognizedPhrases", []))
                self.logger.info(f"  Step 3: Downloaded {phrase_count} recognized phrases", recording.id)

                # Generate diarized transcript
                self.logger.info(f"  Step 4: Generating diarized transcript", recording.id)
                transcription.diarized_transcript = self._generate_diarized_transcript(json_data)

                # Update transcription record
                self.logger.info(f"  Step 5: Saving transcription to Cosmos DB", recording.id)
                self.transcription_handler.update_transcription(transcription)

                # Update recording
                self.logger.info(f"  Step 6: Updating recording status to 'completed'", recording.id)
                recording.transcription_status = TranscriptionStatus.completed
                recording.transcription_id = transcription.id
                recording.transcription_job_status = TranscriptionJobStatus.completed
                recording.transcription_job_id = None  # Clear job ID, no longer needed
                recording.last_check_time = datetime.now(UTC).isoformat()
                self.recording_handler.update_recording(recording)

                # Reset failure count on success
                if recording.processing_failure_count > 0:
                    self.logger.info(f"  Step 7: Resetting failure count (was {recording.processing_failure_count})", recording.id)
                    recording.processing_failure_count = 0
                    recording.needs_manual_review = False
                    self.recording_handler.update_recording(recording)

                # Step 8: Generate title and description using AI (if enabled)
                if self.ai_postprocessing_enabled:
                    self.logger.info(f"  Step 8: Generating AI-powered title and description", recording.id)
                    try:
                        ai_content = asyncio.run(self._generate_title_and_description(transcription.diarized_transcript))
                        if ai_content:
                            # Update recording with generated content
                            if ai_content.get('title'):
                                recording.title = ai_content['title']
                                self.logger.info(f"    ✓ Title: '{recording.title}'", recording.id)
                            if ai_content.get('description'):
                                recording.description = ai_content['description']
                                self.logger.info(f"    ✓ Description: '{recording.description}'", recording.id)
                            self.recording_handler.update_recording(recording)
                        else:
                            self.logger.warning(f"    ⚠ Failed to generate title/description", recording.id)
                    except Exception as e:
                        self.logger.error(f"    ✗ Error in AI post-processing: {e}", recording.id)
                else:
                    self.logger.info(f"  Step 8: Skipping AI post-processing (not configured)", recording.id)

                self.logger.info(f"  ✓ SUCCESS: Transcription fully processed and saved", recording.id)

            else:
                self.logger.error("  ✗ ERROR: Failed to download transcript content from Azure", recording.id)
                self._track_failure(recording, "download_transcript", "Failed to download transcript")

        except Exception as e:
            self.logger.error(f"Error handling completed transcription: {str(e)}", recording.id)
            self._track_failure(recording, "handle_completion", str(e))

    def _download_transcript(self, transcription_id: str) -> Optional[str]:
        """Download transcript JSON from Azure Speech Services."""
        try:
            transcription = self.api.transcriptions_get(transcription_id)
            if transcription.status != "Succeeded":
                self.logger.warning(f"    Cannot download - transcription status is {transcription.status}")
                return None

            # Get files associated with transcription
            pag_files = self.api.transcriptions_list_files(transcription_id)

            # Find the transcription file
            file_count = 0
            for file_data in self._paginate(pag_files):
                file_count += 1
                self.logger.debug(f"    Found file {file_count}: kind={file_data.kind}, name={getattr(file_data, 'name', 'N/A')}")

                if file_data.kind != "Transcription":
                    continue

                # Download the file
                results_url = file_data.links.content_url
                self.logger.info(f"    Downloading transcription file from Azure")
                response = requests.get(results_url, timeout=30)
                response.raise_for_status()

                content = response.content.decode('utf-8')
                self.logger.info(f"    Downloaded {len(content)} characters")
                return content

            self.logger.warning(f"    No transcription file found among {file_count} files")
            return None

        except Exception as e:
            self.logger.error(f"    Error downloading transcript: {str(e)}")
            return None

    def _paginate(self, paginated_object):
        """
        Generator for paginating Azure API results.
        The autogenerated client doesn't support pagination natively.
        """
        yield from paginated_object.values

        typename = type(paginated_object).__name__
        auth_settings = ["api_key"]

        while paginated_object.next_link:
            link = paginated_object.next_link[len(self.api_client.configuration.host):]
            paginated_object, status, headers = self.api_client.call_api(
                link, "GET", response_type=typename, auth_settings=auth_settings
            )

            if status == 200:
                yield from paginated_object.values
            else:
                raise Exception(f"Could not receive paginated data: status {status}")

    def _generate_diarized_transcript(self, json_data: dict) -> str:
        """Generate human-readable diarized transcript from Azure JSON."""
        transcript = []
        last_speaker = None
        last_text = []

        for phrase in json_data.get("recognizedPhrases", []):
            current_speaker = phrase.get("speaker")
            current_text = phrase.get("nBest", [{}])[0].get("display", "")

            # Combine consecutive text if same speaker
            if current_speaker == last_speaker:
                last_text.append(current_text)
            else:
                if last_text:  # Add the previous speaker's combined text
                    transcript.append(f"Speaker {last_speaker}: " + " ".join(last_text) + "\n")

                # Reset for new speaker
                last_speaker = current_speaker
                last_text = [current_text]

        # Append the last speaker's text after the loop
        if last_text:
            transcript.append(f"Speaker {last_speaker}: " + " ".join(last_text) + "\n")

        return "\n".join(transcript)

    async def _generate_title_and_description(self, transcript_text: str) -> Optional[dict]:
        """
        Generate title and description for a transcript using LLM.

        Args:
            transcript_text: The transcript text to analyze

        Returns:
            Dict with 'title' and 'description' keys, or None on failure
        """
        try:
            # Get mini model client for cost efficiency
            client = get_openai_client("mini")

            # Prepare prompt
            prompt = generate_title_and_description_prompt.replace("__TRANSCRIPT__", transcript_text)

            self.logger.info("Sending LLM request for title and description generation")

            # Call LLM
            result = await client.send_prompt_async(prompt)

            # Parse JSON response
            # Extract JSON from any surrounding text
            first_brace = result.find('{')
            last_brace = result.rfind('}')

            if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
                self.logger.warning("No valid JSON found in LLM response")
                return None

            json_content = result[first_brace:last_brace + 1]
            parsed_result = json.loads(json_content)

            title = parsed_result.get('title', '').strip()
            description = parsed_result.get('description', '').strip()

            if not title or not description:
                self.logger.warning("LLM returned empty title or description")
                return None

            self.logger.info(f"Generated title: '{title}' (length: {len(title)})")
            self.logger.info(f"Generated description: '{description}' (length: {len(description)})")

            return {
                'title': title,
                'description': description
            }

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error generating title and description: {e}")
            return None

    def _track_failure(self, recording: Recording, step: str, error: str):
        """Track failure and potentially mark for manual review."""
        # Increment failure count
        if not recording.processing_failure_count:
            recording.processing_failure_count = 0
        recording.processing_failure_count += 1

        recording.last_failure_message = error

        # Check if needs manual review (MAX_PROCESSING_FAILURES+ failures)
        if recording.processing_failure_count >= MAX_PROCESSING_FAILURES:
            recording.needs_manual_review = True
            self.logger.warning(
                f"Recording {recording.id} marked for manual review after {recording.processing_failure_count} failures",
                recording.id
            )

            # Create ManualReviewItem in Cosmos DB
            try:
                # Create FailureRecord for this failure
                # Note: failureHistory tracks failures from when manual review threshold is hit
                # Earlier failures (attempts 1-2) are reflected in failureCount but not in detailed history
                failure_record = FailureRecord(
                    timestamp=datetime.now(UTC).isoformat(),
                    error=error,
                    step=step,
                    attemptNumber=recording.processing_failure_count
                )

                # Check if manual review item already exists
                existing_item = self.manual_review_handler.get_by_recording_id(recording.id)
                if not existing_item:
                    # Create new manual review item with initial failure history
                    manual_review_item = ManualReviewItem(
                        id=str(uuid.uuid4()),
                        recordingId=recording.id,
                        userId=recording.user_id,
                        recordingTitle=recording.title,
                        failureCount=recording.processing_failure_count,
                        lastError=recording.last_failure_message,
                        failureHistory=[failure_record],
                        status="pending",
                        createdAt=datetime.now(UTC).isoformat(),
                        updatedAt=datetime.now(UTC).isoformat(),
                        partitionKey="manual_review",
                        testRunId=self.test_run_id
                    )
                    self.manual_review_handler.create_manual_review_item(manual_review_item)
                    self.logger.info(f"Created manual review item for recording {recording.id}", recording.id)
                else:
                    # Update existing item - append new failure to history
                    existing_item.failureCount = recording.processing_failure_count
                    existing_item.lastError = recording.last_failure_message
                    existing_item.failureHistory.append(failure_record)
                    existing_item.updatedAt = datetime.now(UTC).isoformat()
                    self.manual_review_handler.update_manual_review_item(existing_item)
                    self.logger.info(f"Updated manual review item for recording {recording.id}", recording.id)
            except Exception as e:
                self.logger.error(f"Error creating manual review item: {str(e)}", recording.id)

        self.recording_handler.update_recording(recording)
