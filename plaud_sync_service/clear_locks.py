#!/usr/bin/env python3
"""
Clear distributed locks for local development.
WARNING: Only use this in development mode!
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from: {env_file}")
else:
    print(f"Warning: .env file not found at {env_file}")

from shared_quickscribe_py.config import get_settings
from shared_quickscribe_py.cosmos import LocksHandler

def main():
    print("=" * 80)
    print("CLEAR LOCKS - Development Tool")
    print("=" * 80)

    # Load settings
    settings = get_settings()

    # Check if we're in development mode
    if settings.environment != 'development':
        print(f"ERROR: This script can only be run in development mode!")
        print(f"Current environment: {settings.environment}")
        print("\nSet ENVIRONMENT=development in your .env file to use this script.")
        sys.exit(1)

    print(f"Environment: {settings.environment}")
    print()

    # Initialize locks handler
    cosmos_url = settings.cosmos.endpoint
    cosmos_key = settings.cosmos.key
    cosmos_db = settings.cosmos.database_name
    cosmos_container = settings.cosmos.container_name

    locks_handler = LocksHandler(cosmos_url, cosmos_key, cosmos_db, cosmos_container)

    # Lock ID used by the sync service
    lock_id = "plaud-sync-lock"

    # Check if lock exists
    if locks_handler.is_lock_held(lock_id):
        owner = locks_handler.get_lock_owner(lock_id)
        print(f"Lock found: '{lock_id}'")
        print(f"Owner: {owner}")
        print()

        # Force delete the lock
        try:
            locks_handler.container.delete_item(item=lock_id, partition_key="locks")
            print("✓ Lock cleared successfully!")
        except Exception as e:
            print(f"✗ Error clearing lock: {str(e)}")
            sys.exit(1)
    else:
        print(f"No lock found with ID: '{lock_id}'")
        print("Nothing to clear.")

    print("=" * 80)

if __name__ == "__main__":
    main()
