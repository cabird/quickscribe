#!/usr/bin/env python3
"""
Comprehensive test script for User and PlaudSettings Pydantic models.
Tests datetime handling, field validation, serialization, and database operations.

Run this from the repo root with:
  scripts/.venv/bin/python scripts/test_user_models.py
"""

import os
import sys
from datetime import datetime, UTC

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_dir)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(backend_dir, '.env.local'))
    print("✓ Loaded environment from .env.local")
except ImportError:
    print("Note: dotenv not available, using existing environment variables")
except FileNotFoundError:
    print("Note: .env.local not found, using existing environment variables")

from db_handlers.handler_factory import create_user_handler
from db_handlers.user_handler import User, PlaudSettings

def test_plaud_settings_creation():
    """Test PlaudSettings model creation and validation"""
    print("\n=== Testing PlaudSettings Creation ===")
    
    # Test basic creation
    settings = PlaudSettings(
        bearerToken="test-token-123",
        enableSync=True
    )
    print(f"✓ Basic PlaudSettings created: {settings.bearerToken}, enableSync={settings.enableSync}")
    
    # Test with datetime strings
    settings_with_dates = PlaudSettings(
        bearerToken="test-token-456",
        enableSync=False,
        lastSyncTimestamp="2025-06-03T20:00:00Z",
        activeSyncStarted="2025-06-03T21:30:00+00:00"
    )
    print(f"✓ PlaudSettings with date strings: lastSync={settings_with_dates.lastSyncTimestamp}, activeSync={settings_with_dates.activeSyncStarted}")
    print(f"  Types: lastSync={type(settings_with_dates.lastSyncTimestamp)}, activeSync={type(settings_with_dates.activeSyncStarted)}")
    
    # Test with datetime objects
    now = datetime.now(UTC)
    settings_with_datetime_objects = PlaudSettings(
        bearerToken="test-token-789",
        lastSyncTimestamp=now,
        activeSyncStarted=now
    )
    print(f"✓ PlaudSettings with datetime objects: lastSync={settings_with_datetime_objects.lastSyncTimestamp}")
    
    return settings, settings_with_dates, settings_with_datetime_objects

def test_plaud_settings_serialization():
    """Test PlaudSettings serialization for storage"""
    print("\n=== Testing PlaudSettings Serialization ===")
    
    now = datetime.now(UTC)
    settings = PlaudSettings(
        bearerToken="test-token-serialization",
        enableSync=True,
        lastSyncTimestamp=now,
        activeSyncStarted=now,
        activeSyncToken="sync-token-123"
    )
    
    # Test model_dump (for storage)
    storage_dict = settings.model_dump()
    print(f"✓ Serialized for storage: {storage_dict}")
    print(f"  lastSyncTimestamp type in dict: {type(storage_dict['lastSyncTimestamp'])}")
    print(f"  activeSyncStarted type in dict: {type(storage_dict['activeSyncStarted'])}")
    
    # Test round-trip: serialize -> deserialize
    restored_settings = PlaudSettings(**storage_dict)
    print(f"✓ Round-trip successful: {restored_settings.lastSyncTimestamp}")
    print(f"  Restored types: lastSync={type(restored_settings.lastSyncTimestamp)}, activeSync={type(restored_settings.activeSyncStarted)}")
    
    return settings, storage_dict

def test_user_model():
    """Test User model creation and validation"""
    print("\n=== Testing User Model ===")
    
    # Create basic user
    user = User(
        id="test-user-123",
        email="test@example.com",
        name="Test User",
        partitionKey="user",
        role="user"
    )
    print(f"✓ Basic User created: {user.name} ({user.email})")
    
    # Add datetime fields
    now = datetime.now(UTC)
    user.created_at = now
    user.last_login = now
    print(f"✓ User with datetime fields: created_at={user.created_at}, last_login={user.last_login}")
    
    # Add PlaudSettings
    plaud_settings = PlaudSettings(
        bearerToken="user-plaud-token",
        enableSync=True,
        lastSyncTimestamp=now
    )
    user.plaudSettings = plaud_settings
    print(f"✓ User with PlaudSettings: token={user.plaudSettings.bearerToken}, enableSync={user.plaudSettings.enableSync}")
    
    return user

def test_user_serialization():
    """Test User model serialization"""
    print("\n=== Testing User Serialization ===")
    
    now = datetime.now(UTC)
    user = User(
        id="test-user-serialization",
        email="serialize@example.com",
        name="Serialize User",
        partitionKey="user",
        created_at=now,
        last_login=now,
        plaudSettings=PlaudSettings(
            bearerToken="serialize-token",
            enableSync=True,
            lastSyncTimestamp=now,
            activeSyncStarted=now
        )
    )
    
    # Test serialization
    user_dict = user.model_dump()
    print(f"✓ User serialized: {user_dict['name']}")
    print(f"  created_at type: {type(user_dict['created_at'])}")
    print(f"  plaudSettings.lastSyncTimestamp type: {type(user_dict['plaudSettings']['lastSyncTimestamp'])}")
    
    # Test round-trip
    restored_user = User(**user_dict)
    print(f"✓ User round-trip successful: {restored_user.name}")
    print(f"  Restored created_at type: {type(restored_user.created_at)}")
    print(f"  Restored plaudSettings.lastSyncTimestamp type: {type(restored_user.plaudSettings.lastSyncTimestamp)}")
    
    return user, user_dict

def test_field_modifications():
    """Test modifying user fields directly"""
    print("\n=== Testing Field Modifications ===")
    
    user = User(
        id="test-user-modifications",
        email="modify@example.com",
        name="Modify User",
        partitionKey="user",
        plaudSettings=PlaudSettings(
            bearerToken="initial-token",
            enableSync=False
        )
    )
    
    print(f"Initial state: enableSync={user.plaudSettings.enableSync}, token={user.plaudSettings.bearerToken}")
    
    # Modify PlaudSettings fields directly
    user.plaudSettings.enableSync = True
    user.plaudSettings.bearerToken = "modified-token"
    user.plaudSettings.activeSyncToken = "new-sync-token"
    user.plaudSettings.activeSyncStarted = datetime.now(UTC)
    user.plaudSettings.lastSyncTimestamp = datetime.now(UTC)
    
    print(f"✓ Modified fields: enableSync={user.plaudSettings.enableSync}, token={user.plaudSettings.bearerToken}")
    print(f"  activeSyncToken={user.plaudSettings.activeSyncToken}")
    print(f"  activeSyncStarted={user.plaudSettings.activeSyncStarted}")
    print(f"  lastSyncTimestamp={user.plaudSettings.lastSyncTimestamp}")
    
    # Test clearing fields
    user.plaudSettings.activeSyncToken = None
    user.plaudSettings.activeSyncStarted = None
    print(f"✓ Cleared fields: activeSyncToken={user.plaudSettings.activeSyncToken}, activeSyncStarted={user.plaudSettings.activeSyncStarted}")
    
    return user

def test_database_operations():
    """Test actual database operations with the new models"""
    print("\n=== Testing Database Operations ===")
    
    try:
        user_handler = create_user_handler()
        print("✓ UserHandler created successfully")
        
        # Create a test user
        test_user_id = "test-pydantic-models-001"
        now = datetime.now(UTC)
        
        # Check if user exists and delete if so
        existing_user = user_handler.get_user(test_user_id)
        if existing_user:
            user_handler.delete_user(test_user_id)
            print(f"✓ Cleaned up existing test user: {test_user_id}")
        
        # Create new user using the handler's create method
        created_user = user_handler.create_user(
            email="pydantic-test@example.com",
            name="Pydantic Test User",
            role="user"
        )
        print(f"✓ Created user via handler: {created_user.name} ({created_user.id})")
        
        # Update the user ID for our test
        test_user_id = created_user.id
        
        # Test 1: Add PlaudSettings using clean API
        print("\n--- Test 1: Adding PlaudSettings ---")
        user = user_handler.get_user(test_user_id)
        user.plaudSettings = PlaudSettings(
            bearerToken="database-test-token",
            enableSync=True,
            lastSyncTimestamp=now
        )
        
        saved_user = user_handler.save_user(user)
        print(f"✓ Saved user with PlaudSettings: enableSync={saved_user.plaudSettings.enableSync}")
        print(f"  lastSyncTimestamp type: {type(saved_user.plaudSettings.lastSyncTimestamp)}")
        
        # Test 2: Modify PlaudSettings fields
        print("\n--- Test 2: Modifying PlaudSettings ---")
        user = user_handler.get_user(test_user_id)
        user.plaudSettings.activeSyncToken = "new-sync-token-database"
        user.plaudSettings.activeSyncStarted = datetime.now(UTC)
        user.plaudSettings.enableSync = False
        
        updated_user = user_handler.save_user(user)
        print(f"✓ Updated PlaudSettings: enableSync={updated_user.plaudSettings.enableSync}")
        print(f"  activeSyncToken={updated_user.plaudSettings.activeSyncToken}")
        print(f"  activeSyncStarted type: {type(updated_user.plaudSettings.activeSyncStarted)}")
        
        # Test 3: Clear specific fields
        print("\n--- Test 3: Clearing Fields ---")
        user = user_handler.get_user(test_user_id)
        user.plaudSettings.activeSyncToken = None
        user.plaudSettings.activeSyncStarted = None
        
        cleared_user = user_handler.save_user(user)
        print(f"✓ Cleared fields: activeSyncToken={cleared_user.plaudSettings.activeSyncToken}")
        print(f"  activeSyncStarted={cleared_user.plaudSettings.activeSyncStarted}")
        print(f"  enableSync still: {cleared_user.plaudSettings.enableSync}")
        
        # Test 4: Remove entire PlaudSettings
        print("\n--- Test 4: Removing PlaudSettings ---")
        user = user_handler.get_user(test_user_id)
        user.plaudSettings = None
        
        reset_user = user_handler.save_user(user)
        print(f"✓ Removed PlaudSettings: plaudSettings={reset_user.plaudSettings}")
        
        # Test 5: Test legacy update_user method still works
        print("\n--- Test 5: Legacy update_user method ---")
        legacy_updated = user_handler.update_user(
            test_user_id,
            plaudSettingsDict={
                "bearerToken": "legacy-token",
                "enableSync": True,
                "lastSyncTimestamp": now.isoformat()
            }
        )
        print(f"✓ Legacy update_user works: token={legacy_updated.plaudSettings.bearerToken}")
        print(f"  lastSyncTimestamp type: {type(legacy_updated.plaudSettings.lastSyncTimestamp)}")
        
        # Cleanup
        user_handler.delete_user(test_user_id)
        print(f"✓ Cleaned up test user: {test_user_id}")
        
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n=== Testing Edge Cases ===")
    
    try:
        # Test invalid datetime strings
        print("--- Testing invalid datetime handling ---")
        try:
            settings = PlaudSettings(
                bearerToken="test",
                lastSyncTimestamp="invalid-date"
            )
            print("✗ Should have failed with invalid date")
        except ValueError as e:
            print(f"✓ Correctly rejected invalid date: {e}")
        
        # Test None values
        print("--- Testing None values ---")
        settings = PlaudSettings(
            bearerToken="test",
            lastSyncTimestamp=None,
            activeSyncStarted=None
        )
        print(f"✓ None values handled: lastSync={settings.lastSyncTimestamp}, activeSync={settings.activeSyncStarted}")
        
        # Test serialization with None values
        settings_dict = settings.model_dump()
        print(f"✓ Serialization with None: {settings_dict}")
        
        return True
        
    except Exception as e:
        print(f"✗ Edge case test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Starting comprehensive Pydantic model tests...\n")
    
    all_tests_passed = True
    
    try:
        # Test model creation and validation
        test_plaud_settings_creation()
        test_plaud_settings_serialization()
        test_user_model()
        test_user_serialization()
        test_field_modifications()
        test_edge_cases()
        
        # Test database operations (requires database connection)
        db_test_passed = test_database_operations()
        all_tests_passed = all_tests_passed and db_test_passed
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        all_tests_passed = False
    
    print(f"\n{'🎉 All tests passed!' if all_tests_passed else '❌ Some tests failed!'}")
    return 0 if all_tests_passed else 1

if __name__ == "__main__":
    exit(main())