#!/usr/bin/env python3
"""
Comprehensive test script for User and PlaudSettings CosmosDB serialization.
Tests all database operations through the user_handler to ensure proper 
serialization/deserialization with CosmosDB.

Run this from the repo root with:
  scripts/.venv/bin/python scripts/test_cosmosdb_serialization.py
"""

import os
import sys
import uuid
from datetime import datetime, UTC, timedelta

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

class CosmosDBSerializationTest:
    def __init__(self):
        self.user_handler = create_user_handler()
        self.test_user_id = None
        self.test_user_email = f"cosmosdb-test-{uuid.uuid4().hex[:8]}@example.com"
        self.test_user_name = f"CosmosDB Test User {uuid.uuid4().hex[:6]}"
        
    def setup(self):
        """Create a test user for our tests"""
        print("\n=== Setting Up Test User ===")
        
        # Create user through handler
        created_user = self.user_handler.create_user(
            email=self.test_user_email,
            name=self.test_user_name,
            role="user"
        )
        
        self.test_user_id = created_user.id
        print(f"✓ Created test user: {created_user.name} (ID: {self.test_user_id})")
        print(f"  Email: {created_user.email}")
        print(f"  Created at: {created_user.created_at} (type: {type(created_user.created_at)})")
        
        return created_user
    
    def cleanup(self):
        """Delete the test user"""
        if self.test_user_id:
            print(f"\n=== Cleaning Up Test User ===")
            self.user_handler.delete_user(self.test_user_id)
            print(f"✓ Deleted test user: {self.test_user_id}")
            
    def test_basic_user_retrieval(self):
        """Test basic user retrieval and datetime deserialization"""
        print("\n=== Test 1: Basic User Retrieval ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        assert user is not None, "User should exist"
        assert user.id == self.test_user_id, "User ID should match"
        assert user.email == self.test_user_email, "Email should match"
        assert user.name == self.test_user_name, "Name should match"
        
        # Check datetime deserialization
        assert isinstance(user.created_at, datetime), f"created_at should be datetime, got {type(user.created_at)}"
        
        print(f"✓ User retrieved successfully")
        print(f"  created_at: {user.created_at} (type: {type(user.created_at)})")
        print(f"  last_login: {user.last_login}")
        print(f"  plaudSettings: {user.plaudSettings}")
        
        return user
        
    def test_add_plaud_settings(self):
        """Test adding PlaudSettings to user and saving to CosmosDB"""
        print("\n=== Test 2: Adding PlaudSettings ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        # Create PlaudSettings with various datetime scenarios
        now = datetime.now(UTC)
        past_sync = now - timedelta(hours=2)
        
        plaud_settings = PlaudSettings(
            bearerToken="test-cosmos-token-12345",
            enableSync=True,
            lastSyncTimestamp=past_sync
        )
        
        user.plaudSettings = plaud_settings
        
        # Save through handler
        saved_user = self.user_handler.save_user(user)
        
        assert saved_user is not None, "Save should succeed"
        assert saved_user.plaudSettings is not None, "PlaudSettings should exist"
        assert saved_user.plaudSettings.bearerToken == "test-cosmos-token-12345", "Bearer token should match"
        assert saved_user.plaudSettings.enableSync == True, "Enable sync should be True"
        assert isinstance(saved_user.plaudSettings.lastSyncTimestamp, datetime), "lastSyncTimestamp should be datetime"
        
        print(f"✓ PlaudSettings saved successfully")
        print(f"  bearerToken: {saved_user.plaudSettings.bearerToken}")
        print(f"  enableSync: {saved_user.plaudSettings.enableSync}")
        print(f"  lastSyncTimestamp: {saved_user.plaudSettings.lastSyncTimestamp} (type: {type(saved_user.plaudSettings.lastSyncTimestamp)})")
        
        return saved_user
        
    def test_retrieve_with_plaud_settings(self):
        """Test retrieving user with PlaudSettings from CosmosDB"""
        print("\n=== Test 3: Retrieving User with PlaudSettings ===")
        
        # Fresh retrieval from database
        user = self.user_handler.get_user(self.test_user_id)
        
        assert user is not None, "User should exist"
        assert user.plaudSettings is not None, "PlaudSettings should exist after retrieval"
        assert user.plaudSettings.bearerToken == "test-cosmos-token-12345", "Bearer token should persist"
        assert user.plaudSettings.enableSync == True, "Enable sync should persist"
        assert isinstance(user.plaudSettings.lastSyncTimestamp, datetime), "lastSyncTimestamp should deserialize to datetime"
        
        print(f"✓ PlaudSettings retrieved and deserialized correctly")
        print(f"  bearerToken: {user.plaudSettings.bearerToken}")
        print(f"  enableSync: {user.plaudSettings.enableSync}")
        print(f"  lastSyncTimestamp: {user.plaudSettings.lastSyncTimestamp} (type: {type(user.plaudSettings.lastSyncTimestamp)})")
        print(f"  activeSyncToken: {user.plaudSettings.activeSyncToken}")
        print(f"  activeSyncStarted: {user.plaudSettings.activeSyncStarted}")
        
        return user
        
    def test_modify_plaud_settings_fields(self):
        """Test modifying individual PlaudSettings fields"""
        print("\n=== Test 4: Modifying PlaudSettings Fields ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        # Modify fields directly
        user.plaudSettings.enableSync = False
        user.plaudSettings.bearerToken = "updated-cosmos-token-67890"
        user.plaudSettings.activeSyncToken = "active-sync-token-abc123"
        user.plaudSettings.activeSyncStarted = datetime.now(UTC)
        
        # Save changes
        saved_user = self.user_handler.save_user(user)
        
        # Verify changes
        assert saved_user.plaudSettings.enableSync == False, "enableSync should be updated"
        assert saved_user.plaudSettings.bearerToken == "updated-cosmos-token-67890", "bearerToken should be updated"
        assert saved_user.plaudSettings.activeSyncToken == "active-sync-token-abc123", "activeSyncToken should be set"
        assert isinstance(saved_user.plaudSettings.activeSyncStarted, datetime), "activeSyncStarted should be datetime"
        
        print(f"✓ PlaudSettings fields modified successfully")
        print(f"  enableSync: {saved_user.plaudSettings.enableSync}")
        print(f"  bearerToken: {saved_user.plaudSettings.bearerToken}")
        print(f"  activeSyncToken: {saved_user.plaudSettings.activeSyncToken}")
        print(f"  activeSyncStarted: {saved_user.plaudSettings.activeSyncStarted} (type: {type(saved_user.plaudSettings.activeSyncStarted)})")
        
        return saved_user
        
    def test_retrieve_modified_settings(self):
        """Test retrieving the modified PlaudSettings from CosmosDB"""
        print("\n=== Test 5: Retrieving Modified PlaudSettings ===")
        
        # Fresh retrieval
        user = self.user_handler.get_user(self.test_user_id)
        
        assert user.plaudSettings.enableSync == False, "Modified enableSync should persist"
        assert user.plaudSettings.bearerToken == "updated-cosmos-token-67890", "Modified bearerToken should persist"
        assert user.plaudSettings.activeSyncToken == "active-sync-token-abc123", "activeSyncToken should persist"
        assert isinstance(user.plaudSettings.activeSyncStarted, datetime), "activeSyncStarted should deserialize to datetime"
        assert isinstance(user.plaudSettings.lastSyncTimestamp, datetime), "lastSyncTimestamp should still be datetime"
        
        print(f"✓ Modified PlaudSettings persisted and deserialized correctly")
        print(f"  enableSync: {user.plaudSettings.enableSync}")
        print(f"  bearerToken: {user.plaudSettings.bearerToken}")
        print(f"  activeSyncToken: {user.plaudSettings.activeSyncToken}")
        print(f"  activeSyncStarted: {user.plaudSettings.activeSyncStarted}")
        print(f"  lastSyncTimestamp: {user.plaudSettings.lastSyncTimestamp}")
        
        return user
        
    def test_clear_datetime_fields(self):
        """Test clearing datetime fields and setting them to None"""
        print("\n=== Test 6: Clearing DateTime Fields ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        # Clear datetime fields
        user.plaudSettings.activeSyncToken = None
        user.plaudSettings.activeSyncStarted = None
        user.plaudSettings.lastSyncTimestamp = None
        
        # Save changes
        saved_user = self.user_handler.save_user(user)
        
        assert saved_user.plaudSettings.activeSyncToken is None, "activeSyncToken should be None"
        assert saved_user.plaudSettings.activeSyncStarted is None, "activeSyncStarted should be None"
        assert saved_user.plaudSettings.lastSyncTimestamp is None, "lastSyncTimestamp should be None"
        
        print(f"✓ DateTime fields cleared successfully")
        print(f"  activeSyncToken: {saved_user.plaudSettings.activeSyncToken}")
        print(f"  activeSyncStarted: {saved_user.plaudSettings.activeSyncStarted}")
        print(f"  lastSyncTimestamp: {saved_user.plaudSettings.lastSyncTimestamp}")
        
        return saved_user
        
    def test_retrieve_cleared_fields(self):
        """Test retrieving user with cleared datetime fields"""
        print("\n=== Test 7: Retrieving Cleared DateTime Fields ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        assert user.plaudSettings.activeSyncToken is None, "activeSyncToken should remain None"
        assert user.plaudSettings.activeSyncStarted is None, "activeSyncStarted should remain None"
        assert user.plaudSettings.lastSyncTimestamp is None, "lastSyncTimestamp should remain None"
        assert user.plaudSettings.enableSync == False, "enableSync should still be False"
        assert user.plaudSettings.bearerToken == "updated-cosmos-token-67890", "bearerToken should persist"
        
        print(f"✓ Cleared fields persisted correctly")
        print(f"  All datetime fields are None as expected")
        print(f"  Non-datetime fields preserved: enableSync={user.plaudSettings.enableSync}")
        
        return user
        
    def test_remove_plaud_settings(self):
        """Test completely removing PlaudSettings"""
        print("\n=== Test 8: Removing PlaudSettings ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        # Remove PlaudSettings entirely
        user.plaudSettings = None
        
        saved_user = self.user_handler.save_user(user)
        
        assert saved_user.plaudSettings is None, "PlaudSettings should be None"
        
        print(f"✓ PlaudSettings removed successfully")
        print(f"  plaudSettings: {saved_user.plaudSettings}")
        
        return saved_user
        
    def test_retrieve_without_plaud_settings(self):
        """Test retrieving user without PlaudSettings"""
        print("\n=== Test 9: Retrieving User Without PlaudSettings ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        assert user.plaudSettings is None, "PlaudSettings should remain None"
        assert user.email == self.test_user_email, "Other user fields should persist"
        assert user.name == self.test_user_name, "Other user fields should persist"
        
        print(f"✓ User without PlaudSettings retrieved correctly")
        print(f"  plaudSettings: {user.plaudSettings}")
        print(f"  Other fields intact: name={user.name}, email={user.email}")
        
        return user
        
    def test_legacy_update_method(self):
        """Test the legacy update_user method still works"""
        print("\n=== Test 10: Legacy update_user Method ===")
        
        # Use legacy method to add PlaudSettings back
        now = datetime.now(UTC)
        legacy_settings = {
            "bearerToken": "legacy-method-token",
            "enableSync": True,
            "lastSyncTimestamp": now.isoformat(),
            "activeSyncToken": "legacy-active-token",
            "activeSyncStarted": now.isoformat()
        }
        
        updated_user = self.user_handler.update_user(
            self.test_user_id,
            plaudSettingsDict=legacy_settings
        )
        
        assert updated_user is not None, "Legacy update should succeed"
        assert updated_user.plaudSettings is not None, "PlaudSettings should be created"
        assert updated_user.plaudSettings.bearerToken == "legacy-method-token", "Legacy bearer token should be set"
        assert isinstance(updated_user.plaudSettings.lastSyncTimestamp, datetime), "Legacy datetime should deserialize"
        assert isinstance(updated_user.plaudSettings.activeSyncStarted, datetime), "Legacy datetime should deserialize"
        
        print(f"✓ Legacy update_user method works correctly")
        print(f"  bearerToken: {updated_user.plaudSettings.bearerToken}")
        print(f"  lastSyncTimestamp: {updated_user.plaudSettings.lastSyncTimestamp} (type: {type(updated_user.plaudSettings.lastSyncTimestamp)})")
        print(f"  activeSyncStarted: {updated_user.plaudSettings.activeSyncStarted} (type: {type(updated_user.plaudSettings.activeSyncStarted)})")
        
        return updated_user
        
    def test_final_retrieval(self):
        """Final test to ensure everything persisted correctly"""
        print("\n=== Test 11: Final Retrieval Verification ===")
        
        user = self.user_handler.get_user(self.test_user_id)
        
        assert user.plaudSettings.bearerToken == "legacy-method-token", "Final bearer token should match"
        assert isinstance(user.plaudSettings.lastSyncTimestamp, datetime), "Final datetime should be datetime object"
        assert isinstance(user.plaudSettings.activeSyncStarted, datetime), "Final datetime should be datetime object"
        
        print(f"✓ Final verification passed")
        print(f"  All datetime fields properly serialized/deserialized through CosmosDB")
        print(f"  PlaudSettings persisted correctly: {user.plaudSettings.bearerToken}")
        
        return user
        
    def run_all_tests(self):
        """Run the complete test suite"""
        print("🧪 Starting comprehensive CosmosDB serialization tests...\n")
        
        tests_passed = 0
        total_tests = 11
        
        try:
            # Setup
            self.setup()
            
            # Run all tests
            self.test_basic_user_retrieval()
            tests_passed += 1
            
            self.test_add_plaud_settings()
            tests_passed += 1
            
            self.test_retrieve_with_plaud_settings()
            tests_passed += 1
            
            self.test_modify_plaud_settings_fields()
            tests_passed += 1
            
            self.test_retrieve_modified_settings()
            tests_passed += 1
            
            self.test_clear_datetime_fields()
            tests_passed += 1
            
            self.test_retrieve_cleared_fields()
            tests_passed += 1
            
            self.test_remove_plaud_settings()
            tests_passed += 1
            
            self.test_retrieve_without_plaud_settings()
            tests_passed += 1
            
            self.test_legacy_update_method()
            tests_passed += 1
            
            self.test_final_retrieval()
            tests_passed += 1
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Always cleanup
            self.cleanup()
            
        print(f"\n🎉 All {tests_passed}/{total_tests} CosmosDB serialization tests passed!")
        print("\n✅ Key Verification Points:")
        print("  • User creation and retrieval through CosmosDB")
        print("  • PlaudSettings serialization to storage format")
        print("  • PlaudSettings deserialization from storage")
        print("  • DateTime field handling (ISO strings ↔ datetime objects)")
        print("  • Field modifications persist through save/retrieve cycles")
        print("  • None values handled correctly")
        print("  • Complete PlaudSettings removal works")
        print("  • Legacy update_user method compatibility")
        print("  • All operations work through user_handler interface")
        
        return tests_passed == total_tests

def main():
    """Run the CosmosDB serialization test suite"""
    try:
        test_suite = CosmosDBSerializationTest()
        success = test_suite.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Test suite initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())