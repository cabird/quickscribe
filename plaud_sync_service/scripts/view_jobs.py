#!/usr/bin/env python3
"""
Interactive job execution viewer.
Query and view job executions from Cosmos DB with their logs.
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Get the plaud_sync_service root directory (parent of scripts/)
from dotenv import load_dotenv
SCRIPT_DIR = Path(__file__).parent
SERVICE_ROOT = SCRIPT_DIR.parent

# Load environment variables from .env file in service root
env_file = SERVICE_ROOT / '.env'
if env_file.exists():
    load_dotenv(env_file)

# Add src/ directory to path
sys.path.insert(0, str(SERVICE_ROOT / 'src'))

from shared_quickscribe_py.config import get_settings
from shared_quickscribe_py.cosmos import JobExecutionHandler


def format_datetime(iso_string: str) -> str:
    """Format ISO datetime string for display."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_string


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds is None:
        return "N/A"

    minutes = seconds // 60
    secs = seconds % 60

    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def has_activity(job: Dict[str, Any]) -> bool:
    """Check if job has any activity (recordings/transcriptions/errors)."""
    stats = job.get('stats', {})
    recordings = stats.get('recordings_uploaded', 0)
    transcriptions = stats.get('transcriptions_completed', 0)
    errors = stats.get('errors', 0)
    return recordings > 0 or transcriptions > 0 or errors > 0


def display_jobs_table(jobs: List[Dict[str, Any]]):
    """Display jobs in a formatted table."""
    if not jobs:
        print("\nNo jobs found.\n")
        return

    # Table headers
    print("\n" + "=" * 130)
    print(f"{'#':<4} {'Job ID':<38} {'Started':<20} {'Duration':<10} {'Status':<12} {'Rec':<5} {'Txn':<5} {'Err':<5}")
    print("=" * 130)

    # Table rows
    for idx, job in enumerate(jobs, 1):
        job_id = job.get('id', 'N/A')
        start_time = format_datetime(job.get('startTime', 'N/A'))
        duration = format_duration(job.get('duration'))
        status = job.get('status', 'N/A')

        stats = job.get('stats', {})
        recordings = stats.get('recordings_uploaded', 0)
        transcriptions = stats.get('transcriptions_completed', 0)
        errors = stats.get('errors', 0)

        # Color code status
        status_display = status
        if status == 'completed':
            status_display = f"\033[32m{status}\033[0m"  # Green
        elif status == 'failed':
            status_display = f"\033[31m{status}\033[0m"  # Red
        elif status == 'running':
            status_display = f"\033[33m{status}\033[0m"  # Yellow

        print(f"{idx:<4} {job_id:<38} {start_time:<20} {duration:<10} {status_display:<20} {recordings:<5} {transcriptions:<5} {errors:<5}")

    print("=" * 130)
    print(f"Total: {len(jobs)} jobs\n")


def display_job_details(job: Dict[str, Any]):
    """Display detailed information about a job execution."""
    print("\n" + "=" * 80)
    print("JOB EXECUTION DETAILS")
    print("=" * 80)

    print(f"\nJob ID:        {job.get('id', 'N/A')}")
    print(f"Status:        {job.get('status', 'N/A')}")
    print(f"Trigger:       {job.get('triggerSource', 'N/A')}")
    print(f"Started:       {format_datetime(job.get('startTime', 'N/A'))}")
    print(f"Ended:         {format_datetime(job.get('endTime', 'N/A'))}")
    print(f"Duration:      {format_duration(job.get('duration'))}")

    if job.get('userId'):
        print(f"User ID:       {job['userId']}")

    if job.get('testRunId'):
        print(f"Test Run ID:   {job['testRunId']}")

    # Display stats
    stats = job.get('stats', {})
    print("\nStatistics:")
    print(f"  Recordings Found:      {stats.get('recordings_found', 0)}")
    print(f"  Recordings Downloaded: {stats.get('recordings_downloaded', 0)}")
    print(f"  Recordings Transcoded: {stats.get('recordings_transcoded', 0)}")
    print(f"  Recordings Uploaded:   {stats.get('recordings_uploaded', 0)}")
    print(f"  Recordings Skipped:    {stats.get('recordings_skipped', 0)}")
    print(f"  Chunks Created:        {stats.get('chunks_created', 0)}")
    print(f"  Transcriptions Checked:   {stats.get('transcriptions_checked', 0)}")
    print(f"  Transcriptions Submitted: {stats.get('transcriptions_submitted', 0)}")
    print(f"  Transcriptions Completed: {stats.get('transcriptions_completed', 0)}")
    print(f"  Errors:                {stats.get('errors', 0)}")

    # Display error message if present
    if job.get('errorMessage'):
        print(f"\nError Message:\n{job['errorMessage']}")

    # Display logs
    logs = job.get('logs', [])
    if logs:
        print(f"\nLogs ({len(logs)} entries):")
        print("-" * 80)

        for log in logs:
            timestamp = format_datetime(log.get('timestamp', 'N/A'))
            level = log.get('level', 'info').upper()
            message = log.get('message', '')
            recording_id = log.get('recordingId')

            # Color code log levels
            level_display = level
            if level == 'ERROR':
                level_display = f"\033[31m{level}\033[0m"  # Red
            elif level == 'WARNING':
                level_display = f"\033[33m{level}\033[0m"  # Yellow
            elif level == 'DEBUG':
                level_display = f"\033[90m{level}\033[0m"  # Gray

            log_line = f"[{timestamp}] {level_display:<17} {message}"
            if recording_id:
                log_line += f" (recording: {recording_id})"

            print(log_line)
    else:
        print("\nNo logs available for this job.")

    print("\n" + "=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='View job executions from Cosmos DB',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='Show all jobs, including those with no activity'
    )

    parser.add_argument(
        '-n', '--limit',
        type=int,
        default=100,
        help='Number of jobs to retrieve (default: 100)'
    )

    args = parser.parse_args()

    try:
        # Load settings
        settings = get_settings()

        # Initialize job execution handler
        cosmos_url = settings.cosmos.endpoint
        cosmos_key = settings.cosmos.key
        cosmos_db = settings.cosmos.database_name
        cosmos_container = settings.cosmos.container_name

        handler = JobExecutionHandler(cosmos_url, cosmos_key, cosmos_db, cosmos_container)

        # Query jobs
        print(f"\nQuerying last {args.limit} job executions...")

        if args.all:
            # Get all jobs
            jobs, total = handler.query_jobs(limit=args.limit, has_activity=None)
        else:
            # Only get jobs with activity
            jobs, total = handler.query_jobs(limit=args.limit, has_activity=True)

        if not jobs:
            print("\nNo jobs found.")
            return

        # Display jobs table
        display_jobs_table(jobs)

        # Interactive selection loop
        while True:
            try:
                selection = input("Enter job number to view details (or 'q' to quit): ").strip()

                if selection.lower() in ('q', 'quit', 'exit'):
                    print("\nGoodbye!")
                    break

                # Try to parse as number
                try:
                    job_num = int(selection)
                    if 1 <= job_num <= len(jobs):
                        display_job_details(jobs[job_num - 1])

                        # Ask if they want to see another
                        cont = input("Press Enter to return to list, or 'q' to quit: ").strip()
                        if cont.lower() in ('q', 'quit', 'exit'):
                            print("\nGoodbye!")
                            break

                        # Re-display the table
                        display_jobs_table(jobs)
                    else:
                        print(f"Invalid number. Please enter 1-{len(jobs)}")
                except ValueError:
                    print("Invalid input. Please enter a number or 'q' to quit.")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                print("\n\nGoodbye!")
                break

    except Exception as e:
        print(f"\nError: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
