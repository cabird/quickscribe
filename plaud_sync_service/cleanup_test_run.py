#!/usr/bin/env python3
"""
Cleanup script for Plaud Sync Service test runs.
Removes all documents and blobs created during a test run.
"""
import os
import sys
import argparse
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load .env file from current directory
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_quickscribe_py.config import QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, TranscriptionHandler,
    JobExecutionHandler, ManualReviewItemHandler
)
from shared_quickscribe_py.azure_services import BlobStorageClient


class TestRunCleaner:
    """Cleans up all resources created during a test run."""

    def __init__(self, settings: QuickScribeSettings, dry_run: bool = False):
        """
        Initialize cleanup handlers.

        :param settings: Validated QuickScribeSettings instance
        :param dry_run: If True, only show what would be deleted without deleting.
        """
        self.dry_run = dry_run
        self.settings = settings

        # Load configuration from settings
        cosmos_url = settings.cosmos.endpoint
        cosmos_key = settings.cosmos.key
        cosmos_db = settings.cosmos.database_name
        cosmos_container = os.environ.get("COSMOS_CONTAINER_NAME", "recordings")

        # Initialize handlers
        self.recording_handler = RecordingHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.transcription_handler = TranscriptionHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.job_execution_handler = JobExecutionHandler(
            cosmos_url, cosmos_key, cosmos_db, cosmos_container
        )
        self.manual_review_handler = ManualReviewItemHandler(
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

    def find_test_recordings(self, test_run_id: str) -> List[Any]:
        """Find all recordings with the given testRunId."""
        query = """
        SELECT * FROM c
        WHERE c.type = 'recording'
        AND c.testRunId = @test_run_id
        """
        parameters = [{"name": "@test_run_id", "value": test_run_id}]

        items = list(self.recording_handler.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return items

    def find_test_transcriptions(self, test_run_id: str) -> List[Any]:
        """Find all transcriptions with the given testRunId."""
        query = """
        SELECT * FROM c
        WHERE c.partitionKey = 'transcription'
        AND c.testRunId = @test_run_id
        """
        parameters = [{"name": "@test_run_id", "value": test_run_id}]

        items = list(self.transcription_handler.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return items

    def find_test_job_executions(self, test_run_id: str) -> List[Any]:
        """Find all job executions with the given testRunId."""
        query = """
        SELECT * FROM c
        WHERE c.partitionKey = 'job_execution'
        AND c.testRunId = @test_run_id
        """
        parameters = [{"name": "@test_run_id", "value": test_run_id}]

        items = list(self.job_execution_handler.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return items

    def find_all_test_run_ids(self) -> List[str]:
        """Find all unique test run IDs in the database."""
        query = """
        SELECT DISTINCT c.testRunId
        FROM c
        WHERE IS_DEFINED(c.testRunId)
        AND c.testRunId != null
        """

        items = list(self.job_execution_handler.container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        test_run_ids = [item['testRunId'] for item in items if 'testRunId' in item]
        return sorted(test_run_ids, reverse=True)  # Most recent first

    def find_latest_test_run_id(self) -> str:
        """Find the most recent test run ID."""
        test_run_ids = self.find_all_test_run_ids()
        if not test_run_ids:
            raise ValueError("No test runs found in database")
        return test_run_ids[0]

    def find_test_manual_review_items(self, test_run_id: str) -> List[Any]:
        """Find all manual review items with the given testRunId."""
        query = """
        SELECT * FROM c
        WHERE c.partitionKey = 'manual_review'
        AND c.testRunId = @test_run_id
        """
        parameters = [{"name": "@test_run_id", "value": test_run_id}]

        items = list(self.manual_review_handler.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        return items

    def delete_blob_files(self, recordings: List[Any]) -> int:
        """
        Delete blob storage files for recordings.

        :param recordings: List of recording documents.
        :return: Number of blobs deleted.
        """
        deleted_count = 0

        for recording in recordings:
            # Extract blob path from unique_filename or reconstruct it
            user_id = recording.get('user_id')
            unique_filename = recording.get('unique_filename')

            if user_id and unique_filename:
                blob_path = f"{user_id}/{unique_filename}"

                if self.dry_run:
                    print(f"  [DRY RUN] Would delete blob: {blob_path}")
                    deleted_count += 1
                else:
                    try:
                        # Delete blob if it exists
                        if self.blob_client.blob_exists(blob_path):
                            self.blob_client.delete_file(blob_path)
                            print(f"  ✓ Deleted blob: {blob_path}")
                            deleted_count += 1
                    except Exception as e:
                        print(f"  ✗ Error deleting blob {blob_path}: {str(e)}")

        return deleted_count

    def cleanup(self, test_run_id: str) -> Dict[str, int]:
        """
        Clean up all resources for a test run.

        :param test_run_id: Test run identifier.
        :return: Dictionary with counts of deleted items.
        """
        stats = {
            "transcriptions": 0,
            "recordings": 0,
            "job_executions": 0,
            "manual_review_items": 0,
            "blobs": 0
        }

        print(f"\n{'=' * 80}")
        print(f"Cleanup Test Run: {test_run_id}")
        if self.dry_run:
            print("[DRY RUN MODE - No actual deletions will occur]")
        print(f"{'=' * 80}\n")

        # Step 1: Find all test data
        print("Step 1: Finding test data...")
        transcriptions = self.find_test_transcriptions(test_run_id)
        recordings = self.find_test_recordings(test_run_id)
        job_executions = self.find_test_job_executions(test_run_id)
        manual_review_items = self.find_test_manual_review_items(test_run_id)

        print(f"  Found {len(transcriptions)} transcriptions")
        print(f"  Found {len(recordings)} recordings")
        print(f"  Found {len(job_executions)} job executions")
        print(f"  Found {len(manual_review_items)} manual review items")
        print()

        # Step 2: Delete transcriptions first (they depend on recordings)
        if transcriptions:
            print("Step 2: Deleting transcriptions...")
            for transcription in transcriptions:
                transcription_id = transcription['id']
                if self.dry_run:
                    print(f"  [DRY RUN] Would delete transcription: {transcription_id}")
                else:
                    try:
                        self.transcription_handler.delete_transcription(transcription_id)
                        print(f"  ✓ Deleted transcription: {transcription_id}")
                    except Exception as e:
                        print(f"  ✗ Error deleting transcription {transcription_id}: {str(e)}")
                        continue
                stats["transcriptions"] += 1
            print()

        # Step 3: Delete blob storage files
        if recordings:
            print("Step 3: Deleting blob storage files...")
            stats["blobs"] = self.delete_blob_files(recordings)
            print()

        # Step 4: Delete recordings
        if recordings:
            print("Step 4: Deleting recordings...")
            for recording in recordings:
                recording_id = recording['id']
                if self.dry_run:
                    print(f"  [DRY RUN] Would delete recording: {recording_id}")
                else:
                    try:
                        self.recording_handler.delete_recording(recording_id)
                        print(f"  ✓ Deleted recording: {recording_id}")
                    except Exception as e:
                        print(f"  ✗ Error deleting recording {recording_id}: {str(e)}")
                        continue
                stats["recordings"] += 1
            print()

        # Step 5: Delete job executions
        if job_executions:
            print("Step 5: Deleting job executions...")
            for job in job_executions:
                job_id = job['id']
                if self.dry_run:
                    print(f"  [DRY RUN] Would delete job execution: {job_id}")
                else:
                    try:
                        self.job_execution_handler.delete_job_execution(job_id)
                        print(f"  ✓ Deleted job execution: {job_id}")
                    except Exception as e:
                        print(f"  ✗ Error deleting job execution {job_id}: {str(e)}")
                        continue
                stats["job_executions"] += 1
            print()

        # Step 6: Delete manual review items
        if manual_review_items:
            print("Step 6: Deleting manual review items...")
            for item in manual_review_items:
                item_id = item['id']
                if self.dry_run:
                    print(f"  [DRY RUN] Would delete manual review item: {item_id}")
                else:
                    try:
                        self.manual_review_handler.delete_manual_review_item(item_id)
                        print(f"  ✓ Deleted manual review item: {item_id}")
                    except Exception as e:
                        print(f"  ✗ Error deleting manual review item {item_id}: {str(e)}")
                        continue
                stats["manual_review_items"] += 1
            print()

        # Summary
        print(f"{'=' * 80}")
        print("Cleanup Summary")
        print(f"{'=' * 80}")
        if self.dry_run:
            print("[DRY RUN - No actual deletions occurred]")
        print(f"  Transcriptions deleted: {stats['transcriptions']}")
        print(f"  Recordings deleted: {stats['recordings']}")
        print(f"  Job executions deleted: {stats['job_executions']}")
        print(f"  Manual review items deleted: {stats['manual_review_items']}")
        print(f"  Blob files deleted: {stats['blobs']}")
        print(f"{'=' * 80}\n")

        return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up all resources created during a Plaud Sync test run."
    )
    parser.add_argument(
        "test_run_id",
        nargs="?",
        help="Test run identifier to clean up (optional if using --all, --latest, or --list)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clean up all test runs"
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Clean up only the most recent test run"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all test run IDs and exit"
    )

    args = parser.parse_args()

    try:
        # Load and validate configuration
        from shared_quickscribe_py.config import get_settings
        print("Loading configuration...")
        settings = get_settings()
        print("✓ Configuration loaded\n")

        # Initialize cleaner with settings
        cleaner = TestRunCleaner(settings, dry_run=args.dry_run)

        # Handle --list flag
        if args.list:
            test_run_ids = cleaner.find_all_test_run_ids()
            if not test_run_ids:
                print("No test runs found in database.")
                return 0

            print(f"\n{'=' * 80}")
            print(f"Found {len(test_run_ids)} test run(s):")
            print(f"{'=' * 80}\n")
            for i, test_run_id in enumerate(test_run_ids, 1):
                print(f"  {i}. {test_run_id}")
            print()
            return 0

        # Determine which test run IDs to clean up
        test_run_ids_to_clean = []

        if args.all:
            test_run_ids_to_clean = cleaner.find_all_test_run_ids()
            if not test_run_ids_to_clean:
                print("No test runs found in database.")
                return 0
            print(f"\nCleaning up {len(test_run_ids_to_clean)} test run(s)...\n")

        elif args.latest:
            try:
                latest_id = cleaner.find_latest_test_run_id()
                test_run_ids_to_clean = [latest_id]
                print(f"\nCleaning up latest test run: {latest_id}\n")
            except ValueError as e:
                print(f"ERROR: {str(e)}")
                return 1

        elif args.test_run_id:
            test_run_ids_to_clean = [args.test_run_id]

        else:
            parser.error("Must specify test_run_id or use --all, --latest, or --list")

        # Clean up each test run
        total_stats = {
            "transcriptions": 0,
            "recordings": 0,
            "job_executions": 0,
            "manual_review_items": 0,
            "blobs": 0
        }

        for test_run_id in test_run_ids_to_clean:
            stats = cleaner.cleanup(test_run_id)
            for key in total_stats:
                total_stats[key] += stats[key]

        # Show combined summary if cleaning multiple runs
        if len(test_run_ids_to_clean) > 1:
            print(f"\n{'=' * 80}")
            print(f"Combined Summary ({len(test_run_ids_to_clean)} test runs)")
            print(f"{'=' * 80}")
            if args.dry_run:
                print("[DRY RUN - No actual deletions occurred]")
            print(f"  Total transcriptions: {total_stats['transcriptions']}")
            print(f"  Total recordings: {total_stats['recordings']}")
            print(f"  Total job executions: {total_stats['job_executions']}")
            print(f"  Total manual review items: {total_stats['manual_review_items']}")
            print(f"  Total blob files: {total_stats['blobs']}")
            print(f"{'=' * 80}\n")

        # Return non-zero if nothing was found/deleted
        if sum(total_stats.values()) == 0:
            print(f"WARNING: No test data found")
            return 1

        return 0

    except Exception as e:
        print(f"\nERROR: Cleanup failed: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
