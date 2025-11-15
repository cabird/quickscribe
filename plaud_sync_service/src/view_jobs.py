#!/usr/bin/env python3
"""
Simple command-line viewer for Plaud sync job executions.
Queries CosmosDB and displays job execution logs interactively.
"""
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from azure.cosmos import CosmosClient
import pytz

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Seattle timezone
SEATTLE_TZ = pytz.timezone('America/Los_Angeles')

# ANSI color codes for log levels
COLOR_RESET = '\033[0m'
COLOR_DEBUG = '\033[90m'      # Gray/dim
COLOR_INFO = '\033[0m'        # Default/white
COLOR_WARNING = '\033[33m'    # Yellow
COLOR_ERROR = '\033[91m'      # Bright red
COLOR_CRITICAL = '\033[1;91m' # Bold bright red


def get_cosmos_client():
    """Create and return CosmosDB client from environment variables."""
    endpoint = os.getenv('AZURE_COSMOS_ENDPOINT')
    key = os.getenv('AZURE_COSMOS_KEY')
    database_name = os.getenv('AZURE_COSMOS_DATABASE_NAME') or os.getenv('COSMOS_DB_NAME')
    container_name = os.getenv('COSMOS_CONTAINER_NAME')

    if not all([endpoint, key, database_name, container_name]):
        print("ERROR: Missing required environment variables")
        print(f"  AZURE_COSMOS_ENDPOINT: {'✓' if endpoint else '✗'}")
        print(f"  AZURE_COSMOS_KEY: {'✓' if key else '✗'}")
        print(f"  Database name: {'✓' if database_name else '✗'}")
        print(f"  Container name: {'✓' if container_name else '✗'}")
        sys.exit(1)

    client = CosmosClient(endpoint, credential=key)
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    return container


def format_datetime(iso_string):
    """Convert ISO datetime string to Seattle timezone human-readable format."""
    if not iso_string:
        return "N/A"

    # Parse ISO string (handles both with and without timezone)
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))

    # Convert to Seattle timezone
    seattle_dt = dt.astimezone(SEATTLE_TZ)

    # Format as human-readable
    return seattle_dt.strftime('%Y-%m-%d %I:%M:%S %p %Z')


def get_job_executions(container, show_all=False):
    """Query all job executions, then filter for activity or duration > 30s, sorted by start time (oldest first).

    Args:
        container: CosmosDB container client
        show_all: If True, return all jobs without filtering
    """
    query = """
        SELECT * FROM c
        WHERE c.type = 'job_execution'
        ORDER BY c.startTime ASC
    """

    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    # If show_all is True, return all items without filtering
    if show_all:
        return items

    # Filter: include jobs with activity OR duration > 30 seconds
    filtered_items = []
    for item in items:
        stats = item.get('stats', {})
        recordings = stats.get('recordings_uploaded', 0)
        transcriptions = stats.get('transcriptions_completed', 0)
        errors = stats.get('errors', 0)

        # Check if job has activity
        has_activity = (recordings >= 1 or transcriptions >= 1 or errors >= 1)

        # Check duration
        start_time = item.get('startTime')
        end_time = item.get('endTime')
        duration_over_30s = False

        if start_time and end_time:
            try:
                start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration_seconds = (end - start).total_seconds()
                duration_over_30s = duration_seconds > 30
            except:
                pass

        # Include if ANY condition is met
        if has_activity or duration_over_30s:
            filtered_items.append(item)

    return filtered_items


def calculate_duration(start_time, end_time):
    """Calculate duration between start and end times."""
    if not start_time or not end_time:
        return "N/A"

    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        duration = end - start

        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        if minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except:
        return "N/A"


def display_job_list(jobs):
    """Display numbered list of job executions."""
    print("\n" + "="*80)
    print("PLAUD SYNC JOB EXECUTIONS")
    print("="*80 + "\n")

    if not jobs:
        print("No job executions found.")
        return

    for idx, job in enumerate(jobs, start=1):
        job_id = job.get('id', 'Unknown')
        start_time = job.get('startTime')
        end_time = job.get('endTime')
        status = job.get('status', 'unknown')
        trigger = job.get('triggerSource', 'unknown')
        stats = job.get('stats', {})

        # Color code status
        status_display = status.upper()
        if status == 'completed':
            status_display = f"✓ {status_display}"
        elif status == 'failed':
            status_display = f"✗ {status_display}"

        # Get stats
        recordings = stats.get('recordings_uploaded', 0)
        transcriptions = stats.get('transcriptions_completed', 0)
        errors = stats.get('errors', 0)
        duration = calculate_duration(start_time, end_time)

        print(f"{idx:3d}. [{status_display:12s}] {format_datetime(start_time)}")
        print(f"      Job ID: {job_id}")
        print(f"      Trigger: {trigger} | Duration: {duration} | Recordings: {recordings} | Transcriptions: {transcriptions} | Errors: {errors}")
        print()


def display_job_logs(job):
    """Display detailed logs for a specific job execution."""
    print("\n" + "="*80)
    print(f"JOB EXECUTION: {job.get('id')}")
    print("="*80)
    print(f"Status:       {job.get('status', 'unknown').upper()}")
    print(f"Trigger:      {job.get('triggerSource', 'unknown')}")
    print(f"Started:      {format_datetime(job.get('startTime'))}")
    print(f"Ended:        {format_datetime(job.get('endTime'))}")

    if job.get('userId'):
        print(f"User ID:      {job['userId']}")

    if job.get('errorMessage'):
        print(f"Error:        {job['errorMessage']}")

    # Display stats
    stats = job.get('stats', {})
    if stats:
        print("\nStatistics:")
        print(f"  Recordings Found:      {stats.get('recordings_found', 0)}")
        print(f"  Recordings Downloaded: {stats.get('recordings_downloaded', 0)}")
        print(f"  Recordings Transcoded: {stats.get('recordings_transcoded', 0)}")
        print(f"  Recordings Uploaded:   {stats.get('recordings_uploaded', 0)}")
        print(f"  Transcriptions Submit: {stats.get('transcriptions_submitted', 0)}")
        print(f"  Chunks Created:        {stats.get('chunks_created', 0)}")
        print(f"  Errors:                {stats.get('errors', 0)}")

    # Display logs
    logs = job.get('logs', [])
    if logs:
        print("\n" + "-"*80)
        print("LOGS")
        print("-"*80 + "\n")

        for log in logs:
            level = log.get('level', 'info').upper()
            message = log.get('message', '')
            timestamp = log.get('timestamp', '')

            # Format: LEVEL: message
            print(f"{level:8s}: {message}")
    else:
        print("\nNo logs available.")

    print("\n" + "="*80 + "\n")


def main():
    """Main interactive loop."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='View Plaud sync job executions from CosmosDB'
    )
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='Show all jobs without filtering (default: only show jobs with activity or duration > 30s)'
    )
    args = parser.parse_args()

    try:
        # Connect to CosmosDB
        print("Connecting to CosmosDB...")
        container = get_cosmos_client()

        # Fetch job executions
        filter_msg = "all jobs" if args.all else "filtered jobs (activity or duration > 30s)"
        print(f"Fetching job executions ({filter_msg})...")
        jobs = get_job_executions(container, show_all=args.all)

        while True:
            # Display list
            display_job_list(jobs)

            # Prompt user
            choice = input("Enter job number to view details (or 'q' to quit): ").strip().lower()

            if choice == 'q':
                print("Goodbye!")
                break

            # Validate input
            try:
                job_num = int(choice)
                if 1 <= job_num <= len(jobs):
                    display_job_logs(jobs[job_num - 1])
                    input("\nPress Enter to continue...")
                else:
                    print(f"Invalid number. Please enter 1-{len(jobs)} or 'q'.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q'.")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
