"""
Main job executor for QuickScribe processing service.
Orchestrates: check pending transcriptions, speaker identification, fetch Plaud recordings.
"""
import os
import uuid
from datetime import datetime, UTC, timedelta
from typing import List, Optional, Dict, Any

from shared_quickscribe_py.config import QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, UserHandler, TranscriptionHandler, LocksHandler,
    JobExecutionHandler, ManualReviewItemHandler, DeletedItemsHandler,
    Recording, User, JobExecution, JobExecutionStats, ManualReviewItem
)
from shared_quickscribe_py.cosmos.models import Status11 as JobStatus
from shared_quickscribe_py.azure_services import BlobStorageClient
from shared_quickscribe_py.plaud import PlaudClient

from logging_handler import JobLogger
from transcription_poller import TranscriptionPoller
from plaud_processor import PlaudProcessor
from profile_manager import ProfileManager
from service_version import SERVICE_VERSION

# Speaker ID imports — lazy-loaded to avoid torch import cost when not needed
# from embedding_engine import EmbeddingEngine
# from speaker_processor import SpeakerProcessor

# Default max recordings for speaker ID backlog per user per run
DEFAULT_MAX_SPEAKER_ID_PER_USER = int(os.environ.get("MAX_SPEAKER_ID_PER_USER", "10"))


class JobExecutor:
    """
    Main executor for QuickScribe processing jobs.
    Handles concurrency control, job tracking, and orchestration of
    Plaud sync + speaker identification.
    """

    def __init__(self, settings: QuickScribeSettings):
        self.settings = settings

        cosmos_url = settings.cosmos.endpoint
        cosmos_key = settings.cosmos.key
        cosmos_db = settings.cosmos.database_name
        cosmos_container = settings.cosmos.container_name

        # Initialize handlers
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
        self.job_execution_handler = JobExecutionHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.manual_review_handler = ManualReviewItemHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.deleted_items_handler = DeletedItemsHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )

        # Initialize blob storage
        storage_container = os.environ.get(
            "AZURE_STORAGE_CONTAINER_NAME",
            settings.blob_storage.audio_container_name
        )
        self.blob_client = BlobStorageClient(
            settings.blob_storage.connection_string,
            storage_container
        )

        # Speaker ID: profile manager (lightweight, always available)
        self.profile_manager = ProfileManager(settings.blob_storage.connection_string)

        # Speaker ID: engine + processor — lazy-loaded (torch is expensive)
        self._speaker_engine = None
        self._speaker_processor = None

        # TTL for job executions (30 days)
        self.job_ttl = 30 * 24 * 60 * 60

        # Lock configuration — 90 min TTL to accommodate ML inference
        self.lock_id = "plaud-sync-lock"
        self.lock_ttl = 5400  # 90 minutes

    def _ensure_speaker_processor(self, logger: JobLogger):
        """Lazy-load ECAPA-TDNN model and speaker processor (only when needed)."""
        if self._speaker_processor is not None:
            return

        logger.info("Initializing ECAPA-TDNN embedding engine (first use this run)...")
        from embedding_engine import EmbeddingEngine
        from speaker_processor import SpeakerProcessor

        self._speaker_engine = EmbeddingEngine()
        self._speaker_processor = SpeakerProcessor(self._speaker_engine, self.blob_client)
        logger.info("Speaker ID engine ready")

    def execute_sync_job(self, trigger_source: str, user_id: Optional[str] = None,
                          test_run_id: Optional[str] = None, max_recordings: Optional[int] = None,
                          check_transcriptions_only: bool = False) -> str:
        job_id = str(uuid.uuid4())
        logger = JobLogger(job_id)

        self.test_run_id = test_run_id
        self.max_recordings = max_recordings
        self.check_transcriptions_only = check_transcriptions_only

        logger.info(f"=== Starting QuickScribe Processing Job (v{SERVICE_VERSION}) ===")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Trigger Source: {trigger_source}")
        logger.info(f"User ID: {user_id if user_id else 'ALL USERS'}")
        if test_run_id:
            logger.info(f"Test Run ID: {test_run_id}")
        if max_recordings:
            logger.info(f"Max Recordings per User: {max_recordings}")
        if check_transcriptions_only:
            logger.info(f"Mode: Check transcriptions only")

        stats = JobExecutionStats(
            transcriptions_checked=0,
            transcriptions_completed=0,
            recordings_found=0,
            recordings_downloaded=0,
            recordings_transcoded=0,
            recordings_uploaded=0,
            recordings_skipped=0,
            transcriptions_submitted=0,
            errors=0,
            chunks_created=0
        )

        # Speaker ID stats (tracked separately, logged at end)
        speaker_stats = {
            "speakers_identified": 0,
            "auto_matches": 0,
            "suggest_matches": 0,
            "unknown_matches": 0,
            "recordings_identified": 0,
            "embeddings_extracted": 0,
            "rerated_speakers": 0,
            "rerated_upgrades": 0,
            "errors": 0,
        }

        users_processed = []
        lock_acquired = False

        try:
            # Step 1: Acquire lock
            lock_acquired = self._try_acquire_lock(job_id, logger)
            if not lock_acquired:
                logger.warning("Another job is already running")
                return job_id

            # Step 2: Create job execution record
            self._create_job_execution(job_id, trigger_source, user_id, logger)

            # Step 3: Get users to process
            users_to_process = self._get_users_to_process(user_id, logger)

            if not users_to_process:
                logger.warning("No users found with Plaud sync enabled")
                self._complete_job_execution(job_id, stats, users_processed, logger)
                return job_id

            logger.info(f"Found {len(users_to_process)} users to process")

            # Step 4: Process each user
            for user in users_to_process:
                try:
                    logger.info(f"\n--- Processing user: {user.id} ({user.name or user.email or 'Unknown'}) ---")
                    users_processed.append(user.id)

                    # Phase A: Check pending transcriptions — capture completed IDs
                    user_stats, completed_recording_ids = self._check_pending_transcriptions(user, logger)
                    stats.transcriptions_checked += user_stats["checked"]
                    stats.transcriptions_completed += user_stats["completed"]
                    stats.errors += user_stats["errors"]

                    # Phase B: Speaker identification for newly completed + backlog
                    self._run_speaker_id_for_user(user, completed_recording_ids, speaker_stats, logger)

                    # Phase C: Re-rate existing suggest/unknown speakers against current profiles
                    self._rerate_speakers_for_user(user, speaker_stats, logger)

                    # Phase D: Fetch new Plaud recordings
                    if not self.check_transcriptions_only:
                        user_stats = self._process_plaud_recordings(user, logger)
                        stats.recordings_found += user_stats["found"]
                        stats.recordings_downloaded += user_stats["downloaded"]
                        stats.recordings_transcoded += user_stats["transcoded"]
                        stats.recordings_uploaded += user_stats["uploaded"]
                        stats.recordings_skipped += user_stats["skipped"]
                        stats.transcriptions_submitted += user_stats["submitted"]
                        stats.chunks_created += user_stats["chunks_created"]
                        stats.errors += user_stats["errors"]
                    else:
                        logger.info(f"Skipping Plaud recording download (check-transcriptions-only mode)")

                except Exception as e:
                    logger.error(f"Error processing user {user.id}: {str(e)}")
                    stats.errors += 1

            # Step 5: Summary
            logger.info(f"\n=== Job Execution Complete ===")
            logger.info(f"Users processed: {len(users_processed)}")
            logger.info(f"Transcriptions checked: {stats.transcriptions_checked}")
            logger.info(f"Transcriptions completed: {stats.transcriptions_completed}")
            logger.info(f"Recordings found: {stats.recordings_found}")
            logger.info(f"Recordings processed: {stats.recordings_downloaded}")
            logger.info(f"Chunks created: {stats.chunks_created}")
            logger.info(f"Transcriptions submitted: {stats.transcriptions_submitted}")
            logger.info(f"Speaker ID: {speaker_stats['recordings_identified']} recordings, "
                        f"{speaker_stats['speakers_identified']} speakers "
                        f"(auto={speaker_stats['auto_matches']}, suggest={speaker_stats['suggest_matches']}, "
                        f"unknown={speaker_stats['unknown_matches']})")
            if speaker_stats['rerated_speakers'] > 0:
                logger.info(f"Re-rated: {speaker_stats['rerated_speakers']} speakers checked, "
                            f"{speaker_stats['rerated_upgrades']} upgraded")
            logger.info(f"Errors: {stats.errors + speaker_stats['errors']}")

            self._complete_job_execution(job_id, stats, users_processed, logger)

        except Exception as e:
            logger.error(f"Critical error in job execution: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            stats.errors += 1
            self._fail_job_execution(job_id, str(e), stats, users_processed, logger)
        finally:
            if lock_acquired:
                self._release_lock(job_id, logger)

        return job_id

    # =========================================================================
    # Transcription polling (unchanged except returns completed recording IDs)
    # =========================================================================

    def _check_pending_transcriptions(self, user: User, logger: JobLogger) -> tuple:
        """
        Check status of pending transcriptions for a user.
        Returns (stats_dict, list_of_completed_recording_ids).
        """
        logger.info(f"Checking pending transcriptions for user {user.id}...")

        stats = {"checked": 0, "completed": 0, "errors": 0}
        completed_recording_ids = []

        poller = TranscriptionPoller(
            self.recording_handler,
            self.transcription_handler,
            self.manual_review_handler,
            logger,
            self.settings,
            test_run_id=self.test_run_id
        )

        try:
            query = """
            SELECT * FROM c
            WHERE c.type = 'recording'
            AND c.user_id = @user_id
            AND c.transcription_job_status IN ('submitted', 'processing')
            """
            parameters = [{"name": "@user_id", "value": user.id}]

            items = list(self.recording_handler.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            pending_recordings = [Recording(**item) for item in items]
            logger.info(f"Found {len(pending_recordings)} pending transcriptions for user {user.id}")

            if pending_recordings:
                logger.info("\n=== Pending Recordings (Cosmos DB Status) ===")
                for rec in pending_recordings:
                    logger.info(f"  Recording ID: {rec.id}")
                    logger.info(f"    Title: {rec.title}")
                    logger.info(f"    Cosmos Status: transcription_job_status={rec.transcription_job_status}")
                    logger.info(f"    Azure Job ID: {rec.transcription_job_id}")
                    if rec.last_check_time:
                        logger.info(f"    Last Checked: {rec.last_check_time}")
                    logger.info("")
        except Exception as e:
            logger.error(f"Error querying pending transcriptions: {str(e)}")
            pending_recordings = []

        for recording in pending_recordings:
            stats["checked"] += 1
            try:
                completed = poller.check_and_update_transcription(recording)
                if completed:
                    stats["completed"] += 1
                    completed_recording_ids.append(recording.id)
            except Exception as e:
                logger.error(f"Error checking transcription for recording {recording.id}: {str(e)}", recording.id)
                stats["errors"] += 1

        logger.info(f"\n=== Transcription Check Summary ===")
        logger.info(f"  Total Checked: {stats['checked']}")
        logger.info(f"  Completed: {stats['completed']}")
        logger.info(f"  Still Pending: {stats['checked'] - stats['completed'] - stats['errors']}")
        logger.info(f"  Errors: {stats['errors']}")
        return stats, completed_recording_ids

    # =========================================================================
    # Speaker Identification (new)
    # =========================================================================

    def _run_speaker_id_for_user(self, user: User, completed_recording_ids: List[str],
                                  speaker_stats: Dict[str, int], logger: JobLogger) -> None:
        """
        Run speaker identification for a user:
        1. Process newly completed recordings (from transcription polling)
        2. Process a small backlog of unidentified recordings (any source)
        """
        # Gather work: newly completed + backlog
        recording_ids_to_process = set(completed_recording_ids)

        # Query backlog: recordings with completed transcription but no speaker ID
        try:
            query = """
            SELECT c.id FROM c
            WHERE c.type = 'recording'
            AND c.user_id = @user_id
            AND c.transcription_status = 'completed'
            AND (
                NOT IS_DEFINED(c.speaker_identification_status)
                OR c.speaker_identification_status = null
                OR c.speaker_identification_status = 'not_started'
            )
            """
            parameters = [{"name": "@user_id", "value": user.id}]
            items = list(self.recording_handler.container.query_items(
                query=query, parameters=parameters,
                enable_cross_partition_query=True
            ))
            backlog_ids = [item["id"] for item in items]

            # Add backlog up to the limit (excluding already-queued)
            max_backlog = DEFAULT_MAX_SPEAKER_ID_PER_USER - len(recording_ids_to_process)
            if max_backlog > 0:
                for rid in backlog_ids:
                    if rid not in recording_ids_to_process:
                        recording_ids_to_process.add(rid)
                        if len(recording_ids_to_process) >= DEFAULT_MAX_SPEAKER_ID_PER_USER:
                            break

            if backlog_ids:
                logger.info(f"Speaker ID backlog: {len(backlog_ids)} unidentified recordings for user {user.id}")
        except Exception as e:
            logger.error(f"Error querying speaker ID backlog: {e}")

        if not recording_ids_to_process:
            logger.info(f"No recordings need speaker identification for user {user.id}")
            return

        logger.info(f"\n=== Speaker Identification: {len(recording_ids_to_process)} recordings ===")

        # Lazy-load ML engine
        self._ensure_speaker_processor(logger)

        # Load user profiles once
        profile_db = self.profile_manager.load_profiles(user.id)
        logger.info(f"Loaded {len(profile_db.profiles)} speaker profiles for user {user.id}")

        profiles_dirty = False
        now = datetime.now(UTC).isoformat()

        for recording_id in recording_ids_to_process:
            try:
                self._identify_recording(
                    recording_id, user, profile_db, speaker_stats, now, logger
                )
                profiles_dirty = True  # May have added embeddings
            except Exception as e:
                logger.error(f"Speaker ID error for recording {recording_id}: {e}", recording_id)
                speaker_stats["errors"] += 1
                # Mark failed but don't stop
                try:
                    recording = self.recording_handler.get_recording(recording_id)
                    if recording:
                        recording.speaker_identification_status = "failed"
                        self.recording_handler.update_recording(recording)
                except Exception:
                    pass

        # Save profiles once for this user (if anything changed)
        if profiles_dirty:
            try:
                self.profile_manager.save_profiles(user.id, profile_db)
                logger.info(f"Saved {len(profile_db.profiles)} profiles for user {user.id}")
            except Exception as e:
                logger.error(f"Failed to save profiles for user {user.id}: {e}")

    def _rerate_speakers_for_user(self, user: User, speaker_stats: Dict[str, int],
                                   logger: JobLogger) -> None:
        """
        Re-rate existing suggest/unknown speakers against current profiles.
        Uses stored embeddings — no audio download or ML inference needed.
        Pure cosine similarity math, very fast.
        """
        try:
            # Load current profiles
            profile_db = self.profile_manager.load_profiles(user.id)
            if not profile_db.profiles:
                return  # No profiles to match against

            # Query transcriptions with suggest/unknown speakers
            query = """
            SELECT * FROM c
            WHERE c.type = 'recording'
            AND c.user_id = @user_id
            AND c.transcription_status = 'completed'
            AND c.speaker_identification_status IN ('needs_review', 'completed')
            """
            parameters = [{"name": "@user_id", "value": user.id}]
            items = list(self.recording_handler.container.query_items(
                query=query, parameters=parameters,
                enable_cross_partition_query=True
            ))

            if not items:
                return

            import numpy as np
            from embedding_engine import l2_normalize

            now = datetime.now(UTC).isoformat()
            AUTO_THRESHOLD = 0.78
            SUGGEST_THRESHOLD = 0.68

            rerated = 0
            upgrades = 0

            for item in items:
                recording = Recording(**item)
                if not recording.transcription_id:
                    continue

                transcription = self.transcription_handler.get_transcription(recording.transcription_id)
                if not transcription or not transcription.speaker_mapping:
                    continue

                mapping = transcription.speaker_mapping
                mapping_changed = False

                for label, data in mapping.items():
                    if hasattr(data, 'model_dump'):
                        d = data.model_dump()
                    elif isinstance(data, dict):
                        d = data.copy()
                    else:
                        continue

                    status = d.get('identificationStatus')
                    if status not in ('suggest', 'unknown'):
                        continue

                    embedding_list = d.get('embedding')
                    if not embedding_list:
                        continue

                    rerated += 1
                    embedding = np.array(embedding_list, dtype=np.float32)

                    # Re-match against current profiles
                    match = profile_db.match_with_confidence(
                        embedding,
                        high_threshold=AUTO_THRESHOLD,
                        low_threshold=SUGGEST_THRESHOLD,
                    )

                    new_status = match["status"]

                    # Only upgrade, never downgrade
                    if status == 'unknown' and new_status in ('suggest', 'auto'):
                        pass  # upgrade
                    elif status == 'suggest' and new_status == 'auto':
                        pass  # upgrade
                    else:
                        continue  # no improvement

                    upgrades += 1
                    old_status = status

                    # Update the mapping entry
                    d['identificationStatus'] = new_status
                    d['similarity'] = match['similarity']
                    d['topCandidates'] = match.get('top_candidates', [])

                    if new_status == 'auto':
                        d['participantId'] = match['participant_id']
                        d['confidence'] = match['similarity']
                        d['manuallyVerified'] = False
                        d.pop('suggestedParticipantId', None)
                    elif new_status == 'suggest':
                        d['suggestedParticipantId'] = match['participant_id']

                    # Audit trail
                    history = d.get('identificationHistory') or []
                    history.append({
                        'timestamp': now,
                        'action': f'rerated_{old_status}_to_{new_status}',
                        'source': 'worker',
                        'participantId': match['participant_id'],
                        'similarity': match['similarity'],
                        'candidatesPresented': match.get('top_candidates', []),
                    })
                    d['identificationHistory'] = history

                    # Write back into mapping
                    if hasattr(data, 'model_dump'):
                        mapping[label] = d
                    else:
                        mapping[label] = d
                    mapping_changed = True

                    logger.info(
                        f"  Re-rated {label}: {old_status} → {new_status} "
                        f"(sim={'%.3f' % match['similarity']}, "
                        f"pid={match['participant_id']})",
                        recording.id
                    )

                if mapping_changed:
                    transcription.speaker_mapping = mapping
                    self.transcription_handler.update_transcription(transcription)

                    # Update recording status if all speakers are now resolved
                    has_pending = any(
                        (m.get('identificationStatus') if isinstance(m, dict) else getattr(m, 'identificationStatus', None))
                        in ('suggest', 'unknown')
                        for m in (mapping.values() if isinstance(mapping, dict) else [])
                    )
                    if not has_pending and recording.speaker_identification_status == 'needs_review':
                        recording.speaker_identification_status = 'completed'
                        self.recording_handler.update_recording(recording)

            speaker_stats['rerated_speakers'] += rerated
            speaker_stats['rerated_upgrades'] += upgrades

            if rerated > 0:
                logger.info(f"Re-rating complete: {rerated} speakers checked, {upgrades} upgraded")

        except Exception as e:
            logger.error(f"Error re-rating speakers for user {user.id}: {e}")
            speaker_stats['errors'] += 1

    def _identify_recording(self, recording_id: str, user: User,
                             profile_db, speaker_stats: Dict[str, int],
                             now: str, logger: JobLogger) -> None:
        """Process speaker identification for a single recording."""
        recording = self.recording_handler.get_recording(recording_id)
        if not recording:
            logger.warning(f"Recording {recording_id} not found", recording_id)
            return

        if not recording.transcription_id:
            logger.warning(f"Recording {recording_id} has no transcription_id", recording_id)
            return

        transcription = self.transcription_handler.get_transcription(recording.transcription_id)
        if not transcription:
            logger.warning(f"Transcription {recording.transcription_id} not found", recording_id)
            return

        title = recording.title or recording.original_filename
        logger.info(f"  Speaker ID: {title} ({recording_id})", recording_id)

        # Mark processing
        recording.speaker_identification_status = "processing"
        self.recording_handler.update_recording(recording)

        # Run processor
        results = self._speaker_processor.process_recording(
            recording, transcription, profile_db, logger
        )

        if not results:
            recording.speaker_identification_status = "completed"
            self.recording_handler.update_recording(recording)
            return

        # Merge results into speaker_mapping
        existing_mapping = transcription.speaker_mapping or {}
        merged_mapping = {}
        for label, data in existing_mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}

        has_suggestions = False

        for speaker_label, result in results.items():
            status = result["status"]

            # Handle embedding-only extraction (verified + training requested)
            if status == "embedding_only":
                existing = merged_mapping.get(speaker_label, {})
                existing["embedding"] = result["embedding"]
                existing_history = existing.get("identificationHistory") or []
                existing_history.append({
                    "timestamp": now, "action": "embedding_extracted", "source": "worker",
                })
                existing["identificationHistory"] = existing_history
                merged_mapping[speaker_label] = existing

                # Update profile with the new embedding
                pid = existing.get("participantId")
                if pid:
                    from embedding_engine import l2_normalize
                    import numpy as np
                    centroid = np.array(result["embedding"], dtype=np.float32)
                    profile = profile_db.get_or_create(pid, existing.get("displayName", ""))
                    profile.update([centroid], recording_id=recording_id)

                speaker_stats["embeddings_extracted"] += 1
                logger.info(f"    {speaker_label}: extracted embedding for training", recording_id)
                continue

            speaker_stats["speakers_identified"] += 1

            # Build audit history entry
            history_entry = {
                "timestamp": now,
                "action": "auto_assigned" if status == "auto" else status,
                "source": "worker",
                "participantId": result["participant_id"],
                "similarity": result["similarity"],
                "candidatesPresented": result["top_candidates"],
            }
            existing_history = merged_mapping.get(speaker_label, {}).get("identificationHistory") or []
            updated_history = existing_history + [history_entry]

            if status == "auto":
                speaker_stats["auto_matches"] += 1
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
                speaker_stats["suggest_matches"] += 1
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
                speaker_stats["unknown_matches"] += 1
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

        # Save to CosmosDB
        transcription.speaker_mapping = merged_mapping
        self.transcription_handler.update_transcription(transcription)

        final_status = "needs_review" if has_suggestions else "completed"
        recording.speaker_identification_status = final_status
        self.recording_handler.update_recording(recording)

        speaker_stats["recordings_identified"] += 1
        logger.info(f"    → {final_status}", recording_id)

    # =========================================================================
    # Plaud sync (unchanged)
    # =========================================================================

    def _process_plaud_recordings(self, user: User, logger: JobLogger) -> Dict[str, int]:
        """Fetch and process new Plaud recordings for a user."""
        logger.info(f"Processing Plaud recordings for user {user.id}...")

        stats = {
            "found": 0, "downloaded": 0, "transcoded": 0, "uploaded": 0,
            "submitted": 0, "chunks_created": 0, "skipped": 0, "errors": 0,
        }

        try:
            if not user.plaudSettings or not user.plaudSettings.bearerToken:
                logger.warning(f"User {user.id} has no Plaud bearer token")
                return stats

            plaud_client = PlaudClient(user.plaudSettings.bearerToken, logger.logger)

            processor = PlaudProcessor(
                self.recording_handler, self.blob_client, plaud_client,
                logger, self.settings, test_run_id=self.test_run_id
            )

            logger.info("Fetching existing Plaud IDs from database...")
            existing_plaud_ids = self.recording_handler.get_user_plaud_ids(user.id)

            deleted_plaud_ids = self.deleted_items_handler.get_deleted_plaud_ids(user.id)
            logger.info(f"Found {len(deleted_plaud_ids)} deleted Plaud IDs to block")

            all_blocked_ids = existing_plaud_ids + deleted_plaud_ids
            logger.info(f"Total blocked IDs: {len(all_blocked_ids)}")
            processor.set_existing_plaud_ids(all_blocked_ids)

            logger.info("Fetching recordings from Plaud...")
            response = plaud_client.fetch_recordings()

            if not response:
                logger.warning("No response from Plaud API")
                return stats

            all_recordings = response.data_file_list
            logger.info(f"Fetched {len(all_recordings)} recordings from Plaud")

            stats["found"] = len(all_recordings)

            new_recordings = [r for r in all_recordings if r.id not in all_blocked_ids]
            duplicate_count = len(all_recordings) - len(new_recordings)

            logger.info(
                f"Found {len(all_recordings)} recordings: "
                f"{len(new_recordings)} new, {duplicate_count} blocked"
            )

            plaud_recordings = new_recordings
            if self.max_recordings and len(new_recordings) > self.max_recordings:
                logger.info(f"Limiting to first {self.max_recordings} NEW recordings")
                plaud_recordings = new_recordings[:self.max_recordings]

            for plaud_recording in plaud_recordings:
                try:
                    result = processor.process_recording(user, plaud_recording)
                    stats["downloaded"] += result["downloaded"]
                    stats["transcoded"] += result["transcoded"]
                    stats["uploaded"] += result["uploaded"]
                    stats["submitted"] += result["submitted"]
                    stats["chunks_created"] += result["chunks_created"]
                    stats["skipped"] += result.get("skipped", 0)
                    stats["errors"] += result["errors"]
                except Exception as e:
                    logger.error(f"Error processing Plaud recording {plaud_recording.filename}: {str(e)}")
                    stats["errors"] += 1

            stats["skipped"] = duplicate_count
            logger.info(
                f"Processing complete: {stats['submitted']} submitted, "
                f"{stats['skipped']} skipped, {stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Error fetching Plaud recordings: {str(e)}")
            stats["errors"] += 1

        return stats

    # =========================================================================
    # Lock management & job tracking (unchanged)
    # =========================================================================

    def _try_acquire_lock(self, job_id: str, logger: JobLogger) -> bool:
        logger.debug("Attempting to acquire lock...")
        return self.locks_handler.acquire_lock(self.lock_id, job_id, self.lock_ttl)

    def _release_lock(self, job_id: str, logger: JobLogger):
        logger.debug("Releasing lock...")
        self.locks_handler.release_lock(self.lock_id, job_id)

    def _create_job_execution(self, job_id: str, trigger_source: str, user_id: Optional[str], logger: JobLogger):
        logger.debug("Creating job execution record...")
        job_execution = JobExecution(
            id=job_id,
            userId=user_id,
            status=JobStatus.running,
            triggerSource=trigger_source,
            startTime=datetime.now(UTC).isoformat(),
            logs=[],
            stats=JobExecutionStats(
                transcriptions_checked=0, transcriptions_completed=0,
                recordings_found=0, recordings_downloaded=0, recordings_transcoded=0,
                recordings_uploaded=0, recordings_skipped=0, transcriptions_submitted=0,
                errors=0, chunks_created=0,
            ),
            ttl=self.job_ttl,
            partitionKey="job_execution",
            testRunId=self.test_run_id,
        )
        self.job_execution_handler.create_job_execution(job_execution)
        logger.info("Job execution record created")

    def _get_users_to_process(self, user_id: Optional[str], logger: JobLogger) -> List[User]:
        if user_id:
            logger.debug(f"Fetching user: {user_id}")
            user = self.user_handler.get_user(user_id)
            if user and user.plaudSettings and user.plaudSettings.bearerToken:
                return [user]
            else:
                logger.warning(f"User {user_id} not found or has no Plaud settings")
                return []
        else:
            logger.debug("Fetching all users with Plaud sync enabled...")
            try:
                query = """
                SELECT * FROM c
                WHERE (c.type = 'user' OR NOT IS_DEFINED(c.type))
                AND IS_DEFINED(c.plaudSettings.bearerToken)
                AND c.plaudSettings.bearerToken != null
                AND c.plaudSettings.bearerToken != ''
                AND c.plaudSettings.enableSync = true
                """
                items = list(self.user_handler.container.query_items(
                    query=query, enable_cross_partition_query=True
                ))
                users = [User(**item) for item in items]
                logger.info(f"Found {len(users)} users with Plaud sync enabled")
                return users
            except Exception as e:
                logger.error(f"Error querying users: {str(e)}")
                return []

    def _complete_job_execution(self, job_id: str, stats: JobExecutionStats,
                                 users_processed: List[str], logger: JobLogger):
        logger.debug("Finalizing job execution...")
        job_execution = self.job_execution_handler.get_job_execution(job_id)
        if job_execution:
            job_execution.status = JobStatus.completed
            job_execution.endTime = datetime.now(UTC).isoformat()
            job_execution.logs = logger.get_logs()
            job_execution.stats = stats
            job_execution.usersProcessed = users_processed
            self.job_execution_handler.update_job_execution(job_execution)
            logger.info("Job execution finalized successfully")
        else:
            logger.error(f"Job execution {job_id} not found for completion update")

    def _fail_job_execution(self, job_id: str, error_message: str, stats: JobExecutionStats,
                           users_processed: List[str], logger: JobLogger):
        logger.error("Job execution failed")
        job_execution = self.job_execution_handler.get_job_execution(job_id)
        if job_execution:
            job_execution.status = JobStatus.failed
            job_execution.endTime = datetime.now(UTC).isoformat()
            job_execution.logs = logger.get_logs()
            job_execution.stats = stats
            job_execution.usersProcessed = users_processed
            job_execution.errorMessage = error_message
            self.job_execution_handler.update_job_execution(job_execution)
            logger.error("Job execution marked as failed")
        else:
            logger.error(f"Job execution {job_id} not found for failure update")
