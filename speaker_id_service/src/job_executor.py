"""
Job executor for speaker identification service.
Orchestrates the complete identification workflow.
"""
import os
import uuid
from datetime import datetime, UTC
from typing import List, Optional, Dict

from shared_quickscribe_py.config import QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, UserHandler, TranscriptionHandler, LocksHandler,
    Recording, User, Transcription
)
from shared_quickscribe_py.azure_services import BlobStorageClient

from logging_handler import JobLogger
from speaker_processor import SpeakerProcessor
from profile_manager import ProfileManager
from embedding_engine import EmbeddingEngine
from service_version import SERVICE_VERSION


class JobExecutor:
    """
    Main executor for speaker identification jobs.
    Handles concurrency control, job tracking, and orchestration.
    """

    def __init__(self, settings: QuickScribeSettings):
        self.settings = settings

        cosmos_url = settings.cosmos.endpoint
        cosmos_key = settings.cosmos.key
        cosmos_db = settings.cosmos.database_name
        cosmos_container = settings.cosmos.container_name

        self.recording_handler = RecordingHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.user_handler = UserHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.transcription_handler = TranscriptionHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.locks_handler = LocksHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )

        storage_container = os.environ.get(
            "AZURE_STORAGE_CONTAINER_NAME",
            settings.blob_storage.audio_container_name
        )
        self.blob_client = BlobStorageClient(
            settings.blob_storage.connection_string,
            storage_container
        )

        self.profile_manager = ProfileManager(settings.blob_storage.connection_string)

        # Lock configuration
        self.lock_id = "speaker-id-lock"
        self.lock_ttl = 1800  # 30 minutes

    def execute_identification_job(self, max_recordings: Optional[int] = None) -> str:
        """
        Main entry point for speaker identification.

        Args:
            max_recordings: Optional limit on recordings to process (for testing)

        Returns:
            job_id: Unique identifier for this job execution
        """
        job_id = str(uuid.uuid4())
        logger = JobLogger(job_id)

        lock_acquired = False
        stats = {
            "recordings_processed": 0,
            "speakers_identified": 0,
            "auto_matches": 0,
            "suggest_matches": 0,
            "unknown_matches": 0,
            "errors": 0,
        }

        try:
            logger.info(f"=== Starting Speaker Identification Job (v{SERVICE_VERSION}) ===")
            logger.info(f"Job ID: {job_id}")

            # Acquire lock
            lock_acquired = self.locks_handler.acquire_lock(self.lock_id, job_id, self.lock_ttl)
            if not lock_acquired:
                logger.warning("Another speaker ID job is already running")
                return job_id

            # Initialize ML engine
            logger.info("Initializing ECAPA-TDNN embedding engine...")
            engine = EmbeddingEngine()
            processor = SpeakerProcessor(engine, self.blob_client)

            # Query recordings needing identification
            recordings = self._get_recordings_to_process(logger, max_recordings)
            if not recordings:
                logger.info("No recordings to process")
                return job_id

            logger.info(f"Found {len(recordings)} recordings to process")

            # Process each recording
            for recording in recordings:
                try:
                    self._process_recording(recording, processor, logger, stats)
                except Exception as e:
                    logger.error(f"Error processing recording {recording.id}: {e}", recording.id)
                    stats["errors"] += 1
                    # Mark as failed
                    self._update_recording_status(recording, "failed", logger)

            # Summary
            logger.info(f"\n=== Speaker Identification Complete ===")
            logger.info(f"Recordings processed: {stats['recordings_processed']}")
            logger.info(f"Speakers identified: {stats['speakers_identified']}")
            logger.info(f"  Auto: {stats['auto_matches']}")
            logger.info(f"  Suggest: {stats['suggest_matches']}")
            logger.info(f"  Unknown: {stats['unknown_matches']}")
            logger.info(f"Errors: {stats['errors']}")

        except Exception as e:
            logger.error(f"Critical error in speaker ID job: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
        finally:
            if lock_acquired:
                self.locks_handler.release_lock(self.lock_id, job_id)

        return job_id

    def _get_recordings_to_process(self, logger: JobLogger,
                                    max_recordings: Optional[int] = None) -> List[Recording]:
        """Query recordings with completed transcriptions needing speaker ID."""
        try:
            query = """
            SELECT * FROM c
            WHERE c.type = 'recording'
            AND c.transcription_status = 'completed'
            AND (
                NOT IS_DEFINED(c.speaker_identification_status)
                OR c.speaker_identification_status = null
                OR c.speaker_identification_status = 'not_started'
            )
            """

            items = list(self.recording_handler.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            recordings = [Recording(**item) for item in items]

            if max_recordings and len(recordings) > max_recordings:
                logger.info(f"Limiting to {max_recordings} recordings (of {len(recordings)} found)")
                recordings = recordings[:max_recordings]

            return recordings

        except Exception as e:
            logger.error(f"Error querying recordings: {e}")
            return []

    def _process_recording(self, recording: Recording, processor: SpeakerProcessor,
                           logger: JobLogger, stats: Dict[str, int]) -> None:
        """Process a single recording for speaker identification."""
        recording_id = recording.id
        user_id = recording.user_id

        # Mark as processing
        self._update_recording_status(recording, "processing", logger)

        # Get transcription
        if not recording.transcription_id:
            logger.warning(f"Recording {recording_id} has no transcription_id", recording_id)
            self._update_recording_status(recording, "failed", logger)
            return

        transcription = self.transcription_handler.get_transcription(recording.transcription_id)
        if not transcription:
            logger.warning(f"Transcription {recording.transcription_id} not found", recording_id)
            self._update_recording_status(recording, "failed", logger)
            return

        # Load user's profiles
        profile_db = self.profile_manager.load_profiles(user_id)
        logger.info(f"Loaded {len(profile_db.profiles)} speaker profiles for user {user_id}", recording_id)

        # Process speakers
        results = processor.process_recording(recording, transcription, profile_db, logger)

        if not results:
            logger.info(f"No speakers to identify in recording {recording_id}", recording_id)
            self._update_recording_status(recording, "completed", logger)
            stats["recordings_processed"] += 1
            return

        # Write results to speaker_mapping
        has_suggestions = False
        existing_mapping = transcription.speaker_mapping or {}

        # Convert existing mapping to dict format
        merged_mapping = {}
        for label, data in existing_mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}

        now = datetime.now(UTC).isoformat()

        for speaker_label, result in results.items():
            status = result["status"]

            # Handle embedding-only extraction (verified speaker needing training data)
            if status == "embedding_only":
                existing = merged_mapping.get(speaker_label, {})
                existing["embedding"] = result["embedding"]
                existing_history = existing.get("identificationHistory") or []
                existing_history.append({
                    "timestamp": now,
                    "action": "embedding_extracted",
                    "source": "worker",
                })
                existing["identificationHistory"] = existing_history
                merged_mapping[speaker_label] = existing
                logger.info(f"Stored embedding for verified speaker {speaker_label}", recording_id)
                continue

            stats["speakers_identified"] += 1

            # Build history entry for audit trail
            history_entry = {
                "timestamp": now,
                "action": f"auto_assigned" if status == "auto" else status,
                "source": "worker",
                "participantId": result["participant_id"],
                "similarity": result["similarity"],
                "candidatesPresented": result["top_candidates"],
            }
            existing_history = merged_mapping.get(speaker_label, {}).get("identificationHistory") or []
            updated_history = existing_history + [history_entry]

            if status == "auto":
                stats["auto_matches"] += 1
                merged_mapping[speaker_label] = {
                    **merged_mapping.get(speaker_label, {}),
                    "participantId": result["participant_id"],
                    "confidence": result["similarity"],
                    "manuallyVerified": False,
                    "identificationStatus": "auto",
                    "similarity": result["similarity"],
                    "topCandidates": result["top_candidates"],
                    "identifiedAt": now,
                    "embedding": result["embedding"],
                    "identificationHistory": updated_history,
                }
            elif status == "suggest":
                stats["suggest_matches"] += 1
                has_suggestions = True
                merged_mapping[speaker_label] = {
                    **merged_mapping.get(speaker_label, {}),
                    "identificationStatus": "suggest",
                    "similarity": result["similarity"],
                    "suggestedParticipantId": result["participant_id"],
                    "topCandidates": result["top_candidates"],
                    "identifiedAt": now,
                    "embedding": result["embedding"],
                    "identificationHistory": updated_history,
                }
            else:  # unknown
                stats["unknown_matches"] += 1
                has_suggestions = True
                merged_mapping[speaker_label] = {
                    **merged_mapping.get(speaker_label, {}),
                    "identificationStatus": "unknown",
                    "similarity": result["similarity"],
                    "topCandidates": result["top_candidates"],
                    "identifiedAt": now,
                    "embedding": result["embedding"],
                    "identificationHistory": updated_history,
                }

        # Save updated speaker_mapping to transcription
        self._save_speaker_mapping(transcription, merged_mapping, logger)

        # Set recording status
        final_status = "needs_review" if has_suggestions else "completed"
        self._update_recording_status(recording, final_status, logger)
        stats["recordings_processed"] += 1

    def _save_speaker_mapping(self, transcription: Transcription,
                               mapping: Dict, logger: JobLogger) -> None:
        """Save updated speaker_mapping to Cosmos DB."""
        try:
            transcription.speaker_mapping = mapping
            self.transcription_handler.update_transcription(transcription)
            logger.info(f"Saved speaker mapping for transcription {transcription.id}")
        except Exception as e:
            logger.error(f"Error saving speaker mapping for {transcription.id}: {e}")
            raise

    def _update_recording_status(self, recording: Recording, status: str,
                                  logger: JobLogger) -> None:
        """Update recording's speaker_identification_status."""
        try:
            recording.speaker_identification_status = status
            self.recording_handler.update_recording(recording)
            logger.info(f"Recording {recording.id} speaker_identification_status -> {status}", recording.id)
        except Exception as e:
            logger.error(f"Error updating recording status for {recording.id}: {e}", recording.id)
