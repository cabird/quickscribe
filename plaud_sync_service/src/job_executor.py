"""
Main job executor for Plaud sync service.
Orchestrates the complete sync workflow: check pending transcriptions, fetch Plaud recordings, process them.
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
from shared_quickscribe_py.cosmos.models import Status10 as JobStatus
from shared_quickscribe_py.azure_services import BlobStorageClient
from shared_quickscribe_py.plaud import PlaudClient

from logging_handler import JobLogger
from transcription_poller import TranscriptionPoller
from plaud_processor import PlaudProcessor


class JobExecutor:
    """
    Main executor for Plaud sync jobs.
    Handles concurrency control, job tracking, and orchestration.
    """

    def __init__(self, settings: QuickScribeSettings):
        """
        Initialize handlers and clients.

        Args:
            settings: Validated QuickScribeSettings instance
        """
        self.settings = settings

        # Load configuration from settings (validated at startup)
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

        # TTL for job executions (30 days)
        self.job_ttl = 30 * 24 * 60 * 60  # 2,592,000 seconds

        # Lock configuration
        self.lock_id = "plaud-sync-lock"
        self.lock_ttl = 1800  # 30 minutes

    def execute_sync_job(self, trigger_source: str, user_id: Optional[str] = None,
                          test_run_id: Optional[str] = None, max_recordings: Optional[int] = None,
                          check_transcriptions_only: bool = False) -> str:
        """
        Main entry point for job execution.

        Args:
            trigger_source: "scheduled" or "manual"
            user_id: Specific user ID for manual triggers, None for scheduled (processes all users)
            test_run_id: Optional test run identifier for cleanup purposes
            max_recordings: Optional limit on number of recordings to process per user (for testing)
            check_transcriptions_only: If True, only check transcription status, skip downloading new recordings

        Returns:
            job_id: Unique identifier for this job execution
        """
        job_id = str(uuid.uuid4())
        logger = JobLogger(job_id)

        # Store test_run_id for passing to sub-components
        self.test_run_id = test_run_id
        self.max_recordings = max_recordings
        self.check_transcriptions_only = check_transcriptions_only

        logger.info(f"=== Starting Plaud Sync Job ===")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Trigger Source: {trigger_source}")
        logger.info(f"User ID: {user_id if user_id else 'ALL USERS'}")
        if test_run_id:
            logger.info(f"Test Run ID: {test_run_id}")
        if max_recordings:
            logger.info(f"Max Recordings per User: {max_recordings}")
        if check_transcriptions_only:
            logger.info(f"Mode: Check transcriptions only (skip downloading new recordings)")

        # Initialize statistics
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

        users_processed = []
        lock_acquired = False

        try:
            # Step 1: Try to acquire lock
            lock_acquired = self._try_acquire_lock(job_id, logger)
            if not lock_acquired:
                logger.warning("Another sync job is already running")
                return job_id

            # Step 2: Create job execution record
            self._create_job_execution(job_id, trigger_source, user_id, logger)

            # Step 3: Get list of users to process
            users_to_process = self._get_users_to_process(user_id, logger)

            if not users_to_process:
                logger.warning("No users found with Plaud sync enabled")
                self._complete_job_execution(job_id, stats, users_processed, logger)
                return job_id

            logger.info(f"Found {len(users_to_process)} users to process")

            # Step 4: Process each user sequentially
            for user in users_to_process:
                try:
                    logger.info(f"\n--- Processing user: {user.id} ({user.name or user.email or 'Unknown'}) ---")
                    users_processed.append(user.id)

                    # Check pending transcriptions for this user
                    user_stats = self._check_pending_transcriptions(user, logger)
                    stats.transcriptions_checked += user_stats["checked"]
                    stats.transcriptions_completed += user_stats["completed"]
                    stats.errors += user_stats["errors"]

                    # Fetch and process new Plaud recordings for this user (unless check_transcriptions_only mode)
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

            # Step 5: Complete job execution
            logger.info(f"\n=== Job Execution Complete ===")
            logger.info(f"Users processed: {len(users_processed)}")
            logger.info(f"Transcriptions checked: {stats.transcriptions_checked}")
            logger.info(f"Transcriptions completed: {stats.transcriptions_completed}")
            logger.info(f"Recordings found: {stats.recordings_found}")
            logger.info(f"Recordings processed: {stats.recordings_downloaded}")
            logger.info(f"Chunks created: {stats.chunks_created}")
            logger.info(f"Transcriptions submitted: {stats.transcriptions_submitted}")
            logger.info(f"Errors: {stats.errors}")

            self._complete_job_execution(job_id, stats, users_processed, logger)

        except Exception as e:
            logger.error(f"Critical error in job execution: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            stats.errors += 1
            self._fail_job_execution(job_id, str(e), stats, users_processed, logger)
        finally:
            # Always release the lock if we acquired it
            if lock_acquired:
                self._release_lock(job_id, logger)

        return job_id

    def _try_acquire_lock(self, job_id: str, logger: JobLogger) -> bool:
        """
        Try to acquire lock for job execution using Cosmos DB.
        Returns True if lock acquired, False if another job is running.
        """
        logger.debug("Attempting to acquire lock...")
        return self.locks_handler.acquire_lock(self.lock_id, job_id, self.lock_ttl)

    def _release_lock(self, job_id: str, logger: JobLogger):
        """Release the distributed lock."""
        logger.debug("Releasing lock...")
        self.locks_handler.release_lock(self.lock_id, job_id)

    def _create_job_execution(self, job_id: str, trigger_source: str, user_id: Optional[str], logger: JobLogger):
        """Create initial job execution record in Cosmos DB."""
        logger.debug("Creating job execution record...")

        job_execution = JobExecution(
            id=job_id,
            userId=user_id,
            status=JobStatus.running,
            triggerSource=trigger_source,
            startTime=datetime.now(UTC).isoformat(),
            logs=[],
            stats=JobExecutionStats(
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
            ),
            ttl=self.job_ttl,
            partitionKey="job_execution",
            testRunId=self.test_run_id
        )

        self.job_execution_handler.create_job_execution(job_execution)
        logger.info("Job execution record created")

    def _get_users_to_process(self, user_id: Optional[str], logger: JobLogger) -> List[User]:
        """Get list of users to process based on trigger type."""
        if user_id:
            # Manual trigger - process specific user
            logger.debug(f"Fetching user: {user_id}")
            user = self.user_handler.get_user(user_id)
            if user and user.plaudSettings and user.plaudSettings.bearerToken:
                return [user]
            else:
                logger.warning(f"User {user_id} not found or has no Plaud settings")
                return []
        else:
            # Scheduled trigger - process all users with Plaud sync enabled
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
                    query=query,
                    enable_cross_partition_query=True
                ))

                users = [User(**item) for item in items]
                logger.info(f"Found {len(users)} users with Plaud sync enabled")
                return users
            except Exception as e:
                logger.error(f"Error querying users with Plaud sync: {str(e)}")
                return []

    def _check_pending_transcriptions(self, user: User, logger: JobLogger) -> Dict[str, int]:
        """
        Check status of pending transcriptions for a user.
        Returns stats dict with counts.
        """
        logger.info(f"Checking pending transcriptions for user {user.id}...")

        stats = {"checked": 0, "completed": 0, "errors": 0}

        # Initialize transcription poller
        poller = TranscriptionPoller(
            self.recording_handler,
            self.transcription_handler,
            self.manual_review_handler,
            logger,
            self.settings,
            test_run_id=self.test_run_id
        )

        # Get recordings with pending transcriptions
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

            # Display detailed status for each pending recording
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
            except Exception as e:
                logger.error(f"Error checking transcription for recording {recording.id}: {str(e)}", recording.id)
                stats["errors"] += 1

        # Summary
        logger.info(f"\n=== Transcription Check Summary ===")
        logger.info(f"  Total Checked: {stats['checked']}")
        logger.info(f"  Completed: {stats['completed']}")
        logger.info(f"  Still Pending: {stats['checked'] - stats['completed'] - stats['errors']}")
        logger.info(f"  Errors: {stats['errors']}")
        return stats

    def _process_plaud_recordings(self, user: User, logger: JobLogger) -> Dict[str, int]:
        """
        Fetch and process new Plaud recordings for a user.
        Returns stats dict with counts.
        """
        logger.info(f"Processing Plaud recordings for user {user.id}...")

        stats = {
            "found": 0,
            "downloaded": 0,
            "transcoded": 0,
            "uploaded": 0,
            "submitted": 0,
            "chunks_created": 0,
            "skipped": 0,
            "errors": 0
        }

        try:
            # Get Plaud client for this user
            if not user.plaudSettings or not user.plaudSettings.bearerToken:
                logger.warning(f"User {user.id} has no Plaud bearer token")
                return stats

            plaud_client = PlaudClient(user.plaudSettings.bearerToken, logger.logger)

            # Initialize Plaud processor with plaud_client
            processor = PlaudProcessor(
                self.recording_handler,
                self.blob_client,
                plaud_client,
                logger,
                self.settings,
                test_run_id=self.test_run_id
            )

            # Load existing Plaud IDs for deduplication
            logger.info("Fetching existing Plaud IDs from database...")
            existing_plaud_ids = self.recording_handler.get_user_plaud_ids(user.id)

            # Also fetch deleted Plaud IDs to prevent re-syncing deleted recordings
            deleted_plaud_ids = self.deleted_items_handler.get_deleted_plaud_ids(user.id)
            logger.info(f"Found {len(deleted_plaud_ids)} deleted Plaud IDs to block")

            # Combine both lists for deduplication
            all_blocked_ids = existing_plaud_ids + deleted_plaud_ids
            logger.info(f"Total blocked IDs: {len(all_blocked_ids)} ({len(existing_plaud_ids)} existing + {len(deleted_plaud_ids)} deleted)")
            processor.set_existing_plaud_ids(all_blocked_ids)

            # Fetch recordings from Plaud
            logger.info("Fetching recordings from Plaud...")
            response = plaud_client.fetch_recordings()

            if not response:
                logger.warning("No response from Plaud API")
                return stats

            all_recordings = response.data_file_list
            logger.info(f"Fetched {len(all_recordings)} recordings from Plaud")

            stats["found"] = len(all_recordings)

            # Filter out duplicates AND deleted items BEFORE applying max_recordings limit
            # This ensures --max-recordings gets you N NEW recordings, not N random ones
            new_recordings = [r for r in all_recordings if r.id not in all_blocked_ids]
            duplicate_count = len(all_recordings) - len(new_recordings)

            logger.info(
                f"Found {len(all_recordings)} recordings from Plaud: "
                f"{len(new_recordings)} new, {duplicate_count} blocked (existing or deleted)"
            )

            # Limit NEW recordings if max_recordings is set (for testing)
            plaud_recordings = new_recordings
            if self.max_recordings and len(new_recordings) > self.max_recordings:
                logger.info(f"Limiting to first {self.max_recordings} NEW recordings for testing")
                plaud_recordings = new_recordings[:self.max_recordings]
                logger.info(f"Will process {len(plaud_recordings)} new + skip {duplicate_count} duplicates")

            # Process each recording
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

            # Set skipped count to the number of blocked items we filtered out
            stats["skipped"] = duplicate_count

            logger.info(
                f"Processing complete: {stats['submitted']} submitted, "
                f"{stats['skipped']} skipped (existing or deleted), {stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Error fetching Plaud recordings: {str(e)}")
            stats["errors"] += 1

        logger.info(f"Plaud processing complete: {stats['downloaded']} downloaded, {stats['errors']} errors")
        return stats

    def _complete_job_execution(self, job_id: str, stats: JobExecutionStats,
                                 users_processed: List[str], logger: JobLogger):
        """Mark job execution as completed and save final stats."""
        logger.debug("Finalizing job execution...")

        # Fetch the job execution record
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
        """Mark job execution as failed and save error details."""
        logger.error("Job execution failed")

        # Fetch the job execution record
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
