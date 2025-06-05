#!/usr/bin/env python3
"""
Reset Plaud sync timestamp to allow re-syncing existing recordings.

This script:
1. Finds a user by ID
2. Shows current sync timestamp 
3. Allows resetting to an earlier timestamp to force re-sync
"""

import os
import sys
from datetime import datetime, timezone, timedelta, UTC
from pathlib import Path
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

def load_config():
    """Load configuration from .env.test file"""
    env_file = Path(__file__).parent / '.env.test'
    if not env_file.exists():
        print(f"❌ Configuration file not found: {env_file}")
        sys.exit(1)
    
    load_dotenv(env_file)
    
    config = {
        'COSMOS_URL': os.getenv('COSMOS_URL') or os.getenv('AZURE_COSMOS_ENDPOINT'),
        'COSMOS_KEY': os.getenv('COSMOS_KEY') or os.getenv('AZURE_COSMOS_KEY'),
        'COSMOS_DB_NAME': os.getenv('COSMOS_DB_NAME', 'QuickScribeDatabase'),
        'COSMOS_CONTAINER_NAME': os.getenv('COSMOS_CONTAINER_NAME', 'QuickScribeContainer'),
        'TEST_USER_ID': os.getenv('TEST_USER_ID', '').strip()
    }
    
    missing = [k for k, v in config.items() if not v and k != 'TEST_USER_ID']
    if missing:
        print(f"❌ Missing configuration: {missing}")
        sys.exit(1)
    
    return config

def get_user(cosmos_container, user_id: str):
    """Get user from CosmosDB"""
    try:
        user = cosmos_container.read_item(item=user_id, partition_key="user")
        return user
    except Exception as e:
        print(f"❌ Error getting user {user_id}: {e}")
        return None

def update_user_sync_timestamp(cosmos_container, user_id: str, new_timestamp: str):
    """Update user's lastSyncTimestamp"""
    try:
        # Get current user
        user = get_user(cosmos_container, user_id)
        if not user:
            return False
        
        # Update plaud settings
        if 'plaudSettings' not in user:
            user['plaudSettings'] = {}
        
        user['plaudSettings']['lastSyncTimestamp'] = new_timestamp
        
        # Update in database
        cosmos_container.replace_item(item=user['id'], body=user)
        return True
        
    except Exception as e:
        print(f"❌ Error updating user sync timestamp: {e}")
        return False

def main():
    config = load_config()
    
    # Get user ID
    user_id = config.get('TEST_USER_ID')
    if not user_id:
        user_id = input("Enter user ID: ").strip()
        if not user_id:
            print("❌ User ID required")
            sys.exit(1)
    
    print(f"🔍 Working with user: {user_id}")
    
    # Initialize Cosmos client
    try:
        cosmos_client = CosmosClient(config['COSMOS_URL'], config['COSMOS_KEY'])
        cosmos_db = cosmos_client.get_database_client(config['COSMOS_DB_NAME'])
        cosmos_container = cosmos_db.get_container_client(config['COSMOS_CONTAINER_NAME'])
        print("✅ Connected to CosmosDB")
    except Exception as e:
        print(f"❌ Failed to connect to CosmosDB: {e}")
        sys.exit(1)
    
    # Get user
    user = get_user(cosmos_container, user_id)
    if not user:
        print(f"❌ User {user_id} not found")
        sys.exit(1)
    
    print("✅ Found user")
    
    # Show current settings
    plaud_settings = user.get('plaudSettings', {})
    current_timestamp = plaud_settings.get('lastSyncTimestamp')
    
    print(f"\n📅 Current lastSyncTimestamp: {current_timestamp}")
    
    if current_timestamp:
        try:
            current_dt = datetime.fromisoformat(current_timestamp)
            print(f"   Parsed as: {current_dt}")
            print(f"   Hours ago: {(datetime.now(UTC) - current_dt.astimezone(UTC)).total_seconds() / 3600:.1f}")
        except Exception as e:
            print(f"   ❌ Error parsing timestamp: {e}")
    
    print("\n🔄 Reset Options:")
    print("1. Reset to 1 week ago (will sync recent recordings)")
    print("2. Reset to 1 month ago (will sync more recordings)")
    print("3. Reset to null (will sync all recordings)")
    print("4. Set custom timestamp")
    print("5. Exit without changes")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    new_timestamp = None
    
    if choice == "1":
        new_timestamp = (datetime.now(UTC) - timedelta(weeks=1)).isoformat()
    elif choice == "2":
        new_timestamp = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    elif choice == "3":
        new_timestamp = None
    elif choice == "4":
        custom_timestamp = input("Enter timestamp (ISO format, e.g., 2025-05-01T00:00:00+00:00): ").strip()
        if custom_timestamp:
            try:
                # Validate timestamp
                datetime.fromisoformat(custom_timestamp)
                new_timestamp = custom_timestamp
            except Exception as e:
                print(f"❌ Invalid timestamp format: {e}")
                sys.exit(1)
    elif choice == "5":
        print("👋 Exiting without changes")
        sys.exit(0)
    else:
        print("❌ Invalid choice")
        sys.exit(1)
    
    # Confirm change
    print(f"\n🔄 Will change lastSyncTimestamp from:")
    print(f"   Old: {current_timestamp}")
    print(f"   New: {new_timestamp}")
    
    confirm = input("\nProceed? (y/N): ").strip().lower()
    if confirm != 'y':
        print("👋 Cancelled")
        sys.exit(0)
    
    # Update user
    if update_user_sync_timestamp(cosmos_container, user_id, new_timestamp):
        print("✅ Successfully updated lastSyncTimestamp")
        print(f"\n💡 Now run the Plaud sync test again:")
        print(f"   python test_plaud_sync.py --mode test")
    else:
        print("❌ Failed to update timestamp")
        sys.exit(1)

if __name__ == '__main__':
    main()