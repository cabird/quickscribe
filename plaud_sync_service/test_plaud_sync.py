#!/usr/bin/env python3
"""
Test script for Plaud Sync Service.
Runs the actual Azure Functions code with a test run ID for tracking and cleanup.
"""
import os
import sys
import uuid
import argparse
from datetime import datetime, UTC
from dotenv import load_dotenv

# Load .env file from current directory
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# Add parent directory to path to import job_executor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_quickscribe_py.config import get_settings
from job_executor import JobExecutor


def main():
    """
    Execute a test sync job with tracking ID.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Test Plaud Sync Service with optional recording limit"
    )
    parser.add_argument(
        "--max-recordings",
        type=int,
        default=None,
        help="Maximum number of recordings to process per user (default: no limit)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Specific user ID to test (default: all users)"
    )
    parser.add_argument(
        "--check-transcriptions-only",
        action="store_true",
        help="Only check transcription status, skip downloading new recordings"
    )
    args = parser.parse_args()

    # Generate unique test run ID
    test_run_id = f"test_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

    print("=" * 80)
    print("Plaud Sync Service - Test Run")
    print("=" * 80)
    print(f"Test Run ID: {test_run_id}")
    print(f"Started at: {datetime.now(UTC).isoformat()}")
    if args.user_id:
        print(f"User ID: {args.user_id}")
    if args.check_transcriptions_only:
        print(f"Mode: Check transcriptions only (skip downloading recordings)")
    if args.max_recordings:
        print(f"Max Recordings: {args.max_recordings} per user")
    print()
    print("This test will:")
    if args.check_transcriptions_only:
        print("  1. Check pending transcriptions only")
        print("  2. Skip downloading/processing new Plaud recordings")
    else:
        print("  1. Execute the full Plaud sync workflow")
        print("  2. Check pending transcriptions")
        print("  3. Fetch and process Plaud recordings")
        if args.max_recordings:
            print(f"  4. Limit processing to {args.max_recordings} recordings per user")
            print(f"  5. Tag all created documents with testRunId")
        else:
            print("  4. Tag all created documents with testRunId")
    print()
    print("After the test, use cleanup_test_run.py to remove all test data:")
    print(f"  python cleanup_test_run.py {test_run_id}")
    print()
    print("-" * 80)
    print()

    try:
        # Load and validate configuration
        print("Loading configuration...")
        settings = get_settings()
        print(f"✓ Configuration loaded (AI: {settings.ai_enabled}, Cosmos: {settings.cosmos_enabled})")
        print()

        # Initialize the job executor
        executor = JobExecutor(settings)

        # Execute sync job with test_run_id and optional limits
        job_id = executor.execute_sync_job(
            trigger_source="manual",
            user_id=args.user_id,
            test_run_id=test_run_id,
            max_recordings=args.max_recordings,
            check_transcriptions_only=args.check_transcriptions_only
        )

        print()
        print("-" * 80)
        print(f"Test completed successfully!")
        print(f"Job ID: {job_id}")
        print(f"Test Run ID: {test_run_id}")
        if args.max_recordings:
            print(f"Processed up to {args.max_recordings} recordings per user")
        print()
        print("To view job details, check the JobExecution document in Cosmos DB:")
        print(f"  Container: job_execution")
        print(f"  Document ID: {job_id}")
        print()
        print("To clean up all test data, run:")
        print(f"  python cleanup_test_run.py {test_run_id}")
        print()
        print("Usage examples:")
        print(f"  python test_plaud_sync.py --max-recordings 2")
        print(f"  python test_plaud_sync.py --max-recordings 5 --user-id <user_id>")
        print(f"  python test_plaud_sync.py --check-transcriptions-only")
        print(f"  python test_plaud_sync.py --check-transcriptions-only --user-id <user_id>")
        print("=" * 80)

        return 0

    except Exception as e:
        print()
        print("-" * 80)
        print(f"ERROR: Test failed with exception: {str(e)}")
        print()
        import traceback
        print(traceback.format_exc())
        print()
        print(f"Test Run ID: {test_run_id}")
        print("You may still need to clean up partial test data:")
        print(f"  python cleanup_test_run.py {test_run_id}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
