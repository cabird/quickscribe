#!/usr/bin/env python3
"""
Test script for tag functionality.
Tests the complete tag workflow including API endpoints.
Run with the Flask app running locally via docker-compose.
"""

import requests
import json
import sys
import time
import uuid
from typing import List, Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api"

class TagTester:
    def __init__(self):
        self.session = requests.Session()
        self.current_user = None
        
    def test_create_test_user(self) -> bool:
        """Create a new test user for testing."""
        print("=== Creating New Test User ===")
        
        # Generate unique test user details
        user_suffix = str(uuid.uuid4())[:8]
        test_name = f"Tag Test User {user_suffix}"
        test_email = f"tag-test-{user_suffix}@example.com"
        
        print(f"1. Creating test user: {test_name}")
        response = self.session.post(f"{API_BASE}/local/create_test_user", 
                                   json={
                                       "name": test_name,
                                       "email": test_email
                                   })
        
        if response.status_code != 201:
            print(f"  ✗ Failed to create test user: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
        
        user_data = response.json()
        self.current_user = user_data['user']
        print(f"  ✓ Created test user: {self.current_user['name']} ({self.current_user['id']})")
        
        # Login as the new test user
        print("2. Logging in as new test user...")
        response = self.session.post(f"{API_BASE}/local/login", 
                                   json={"user_id": self.current_user['id']})
        if response.status_code != 200:
            print(f"  ✗ Failed to login: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
        print("  ✓ Logged in successfully")
        
        return True
    
    def test_default_tags(self) -> bool:
        """Test getting default tags."""
        print("\n=== Testing Default Tags ===")
        
        response = self.session.get(f"{API_BASE}/tags/get")
        if response.status_code != 200:
            print(f"  ✗ Failed to get tags: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
        
        tags = response.json()
        expected_defaults = ["Meeting", "Personal", "Self Memos"]
        
        if len(tags) != 3:
            print(f"  ✗ Expected 3 default tags, got {len(tags)}")
            return False
        
        tag_names = [tag['name'] for tag in tags]
        for expected in expected_defaults:
            if expected not in tag_names:
                print(f"  ✗ Missing default tag: {expected}")
                return False
        
        print("  ✓ All default tags present:")
        for tag in tags:
            print(f"    - {tag['name']} ({tag['id']}) {tag['color']}")
        
        return True
    
    def test_create_tags(self) -> List[Dict]:
        """Test creating custom tags."""
        print("\n=== Testing Tag Creation ===")
        
        created_tags = []
        
        # Test cases: [name, color, should_succeed]
        test_cases = [
            ("Work Tasks", "#FF5733", True),
            ("Family", "#28A745", True),
            ("Ideas", "#6F42C1", True),
            ("", "#FF0000", False),  # Empty name
            ("A" * 33, "#FF0000", False),  # Too long name
            ("Valid Name", "invalid-color", False),  # Invalid color
            ("Valid Name", "#ZZZ", False),  # Invalid hex
            ("work tasks", "#FF0000", False),  # Duplicate (case insensitive)
        ]
        
        for name, color, should_succeed in test_cases:
            print(f"  Creating tag: '{name}' {color}")
            response = self.session.post(f"{API_BASE}/tags/create", 
                                       json={"name": name, "color": color})
            
            if should_succeed:
                if response.status_code == 201:
                    tag = response.json()
                    created_tags.append(tag)
                    print(f"    ✓ Created: {tag['name']} ({tag['id']})")
                else:
                    print(f"    ✗ Expected success but got: {response.status_code}")
                    print(f"      Response: {response.text}")
                    return []
            else:
                if response.status_code in [400, 409]:
                    error_msg = response.json().get('error', 'Unknown error')
                    print(f"    ✓ Correctly rejected: {error_msg}")
                else:
                    print(f"    ✗ Expected failure but got: {response.status_code}")
                    print(f"      Response: {response.text}")
                    return []
        
        return created_tags
    
    def test_update_tags(self, tags: List[Dict]) -> bool:
        """Test updating tags."""
        print("\n=== Testing Tag Updates ===")
        
        if not tags:
            print("  ✗ No tags to update")
            return False
        
        # Update first tag
        tag = tags[0]
        new_name = "Updated Work Tasks"
        new_color = "#DC3545"
        
        print(f"  Updating tag {tag['id']}: '{tag['name']}' → '{new_name}'")
        response = self.session.post(f"{API_BASE}/tags/update", 
                                   json={
                                       "tagId": tag['id'],
                                       "name": new_name,
                                       "color": new_color
                                   })
        
        if response.status_code != 200:
            print(f"    ✗ Failed to update tag: {response.status_code}")
            print(f"      Response: {response.text}")
            return False
        
        updated_tag = response.json()
        if updated_tag['name'] != new_name or updated_tag['color'] != new_color:
            print(f"    ✗ Tag not updated correctly")
            print(f"      Expected: {new_name} {new_color}")
            print(f"      Got: {updated_tag['name']} {updated_tag['color']}")
            return False
        
        print(f"    ✓ Updated: {updated_tag['name']} {updated_tag['color']}")
        
        # Update the tag in our local list for future tests
        tags[0] = updated_tag
        
        # Test invalid updates
        print("  Testing invalid updates...")
        response = self.session.post(f"{API_BASE}/tags/update", 
                                   json={"tagId": tag['id'], "name": ""})
        if response.status_code == 400:
            print("    ✓ Correctly rejected empty name")
        else:
            print(f"    ✗ Should have rejected empty name: {response.status_code}")
            return False
        
        return True
    
    def test_dummy_recording_creation(self) -> Optional[str]:
        """Test creating a dummy recording."""
        print("\n=== Testing Dummy Recording Creation ===")
        
        print("  Creating dummy recording...")
        response = self.session.post(f"{API_BASE}/local/create_dummy_recording", 
                                   json={
                                       "title": "Test Recording for Tags",
                                       "original_filename": "test-recording.mp3"
                                   })
        
        if response.status_code != 201:
            print(f"    ✗ Failed to create dummy recording: {response.status_code}")
            print(f"      Response: {response.text}")
            return None
        
        recording_data = response.json()
        recording = recording_data['recording']
        recording_id = recording['id']
        
        print(f"    ✓ Created dummy recording: {recording['title']} ({recording_id})")
        print(f"      is_dummy_recording: {recording.get('is_dummy_recording', False)}")
        
        # Verify it's marked as dummy
        if not recording.get('is_dummy_recording', False):
            print("    ✗ Recording not marked as dummy")
            return None
        
        return recording_id
    
    def test_recording_tags(self, tags: List[Dict], recording_id: str) -> bool:
        """Test adding/removing tags from recordings."""
        print("\n=== Testing Recording Tag Operations ===")
        
        if not tags:
            print("  ✗ No tags available for testing")
            return False
        
        if not recording_id:
            print("  ✗ No recording available for testing")
            return False
        
        # Add tags to recording
        tag1, tag2 = tags[0], tags[1] if len(tags) > 1 else tags[0]
        
        print(f"  Adding tag '{tag1['name']}' ({tag1['id']}) to recording...")
        response = self.session.get(f"{API_BASE}/recordings/{recording_id}/add_tag/{tag1['id']}")
        if response.status_code != 200:
            print(f"    ✗ Failed to add tag: {response.status_code}")
            print(f"      Response: {response.text}")
            return False
        
        updated_recording = response.json()
        if tag1['id'] not in updated_recording.get('tagIds', []):
            print("    ✗ Tag not added to recording")
            return False
        print(f"    ✓ Added tag {tag1['name']}")
        
        # Add second tag (if different)
        if len(tags) > 1 and tag2['id'] != tag1['id']:
            print(f"  Adding tag '{tag2['name']}' ({tag2['id']}) to recording...")
            response = self.session.get(f"{API_BASE}/recordings/{recording_id}/add_tag/{tag2['id']}")
            if response.status_code == 200:
                updated_recording = response.json()
                if tag2['id'] in updated_recording.get('tagIds', []):
                    print(f"    ✓ Added tag {tag2['name']}")
                else:
                    print("    ✗ Second tag not added to recording")
                    return False
            else:
                print(f"    ✗ Failed to add second tag: {response.status_code}")
                return False
        
        # Verify both tags are on recording
        current_tags = updated_recording.get('tagIds', [])
        print(f"  Current tags on recording: {current_tags}")
        
        # Remove a tag
        print(f"  Removing tag '{tag1['name']}' from recording...")
        response = self.session.get(f"{API_BASE}/recordings/{recording_id}/remove_tag/{tag1['id']}")
        if response.status_code != 200:
            print(f"    ✗ Failed to remove tag: {response.status_code}")
            print(f"      Response: {response.text}")
            return False
        
        updated_recording = response.json()
        if tag1['id'] in updated_recording.get('tagIds', []):
            print("    ✗ Tag not removed from recording")
            return False
        print(f"    ✓ Removed tag {tag1['name']}")
        
        return True
    
    def test_delete_tags(self, tags: List[Dict], recording_id: Optional[str]) -> bool:
        """Test deleting tags."""
        print("\n=== Testing Tag Deletion ===")
        
        if not tags:
            print("  ✗ No tags to delete")
            return False
        
        # Add a tag to recording first if we have one
        if recording_id and len(tags) > 1:
            tag_to_delete = tags[1]
            print(f"  Adding tag '{tag_to_delete['name']}' to recording before deletion...")
            self.session.get(f"{API_BASE}/recordings/{recording_id}/add_tag/{tag_to_delete['id']}")
        else:
            tag_to_delete = tags[0]
        
        print(f"  Deleting tag: {tag_to_delete['name']} ({tag_to_delete['id']})")
        response = self.session.get(f"{API_BASE}/tags/delete/{tag_to_delete['id']}")
        
        if response.status_code != 200:
            print(f"    ✗ Failed to delete tag: {response.status_code}")
            print(f"      Response: {response.text}")
            return False
        
        print("    ✓ Tag deleted successfully")
        
        # Verify tag is gone from user's tags
        response = self.session.get(f"{API_BASE}/tags/get")
        if response.status_code == 200:
            remaining_tags = response.json()
            tag_ids = [tag['id'] for tag in remaining_tags]
            if tag_to_delete['id'] not in tag_ids:
                print("    ✓ Tag removed from user's tag list")
            else:
                print("    ✗ Tag still in user's tag list")
                return False
        
        # If we had a recording, verify tag was removed from it
        if recording_id:
            response = self.session.get(f"{API_BASE}/recording/{recording_id}")
            if response.status_code == 200:
                recording = response.json()
                if tag_to_delete['id'] not in recording.get('tagIds', []):
                    print("    ✓ Tag removed from recording")
                else:
                    print("    ✗ Tag not removed from recording")
                    return False
        
        return True
    
    def test_error_cases(self) -> bool:
        """Test various error cases."""
        print("\n=== Testing Error Cases ===")
        
        # Test adding non-existent tag to recording
        print("  Testing non-existent tag...")
        fake_recording_id = "dummy-fake-recording"
        fake_tag_id = "non-existent-tag"
        
        # First create a real recording for testing
        response = self.session.post(f"{API_BASE}/local/create_dummy_recording", 
                                   json={
                                       "title": "Error Test Recording",
                                       "original_filename": "error-test.mp3"
                                   })
        if response.status_code == 201:
            real_recording_id = response.json()['recording']['id']
            
            # Try to add non-existent tag
            response = self.session.get(f"{API_BASE}/recordings/{real_recording_id}/add_tag/{fake_tag_id}")
            if response.status_code == 404:
                print("    ✓ Correctly rejected non-existent tag")
            else:
                print(f"    ✗ Should have rejected non-existent tag: {response.status_code}")
                return False
        
        # Test adding tag to non-existent recording
        # Get a real tag first
        response = self.session.get(f"{API_BASE}/tags/get")
        if response.status_code == 200:
            tags = response.json()
            if tags:
                real_tag_id = tags[0]['id']
                response = self.session.get(f"{API_BASE}/recordings/{fake_recording_id}/add_tag/{real_tag_id}")
                if response.status_code == 404:
                    print("    ✓ Correctly rejected non-existent recording")
                else:
                    print(f"    ✗ Should have rejected non-existent recording: {response.status_code}")
                    return False
        
        return True
    
    def cleanup_test_user(self) -> bool:
        """Clean up the test user and all associated data."""
        print("\n=== Cleaning Up Test User ===")
        
        if not self.current_user:
            print("  No test user to clean up")
            return True
        
        user_id = self.current_user['id']
        print(f"  Deleting test user: {self.current_user['name']} ({user_id})")
        
        response = self.session.post(f"{API_BASE}/local/delete_test_user/{user_id}")
        if response.status_code == 200:
            cleanup_data = response.json()
            print(f"  ✓ Test user deleted successfully")
            print(f"    - Deleted {cleanup_data.get('deleted_recordings', 0)} recordings")
            print(f"    - Deleted {cleanup_data.get('deleted_transcriptions', 0)} transcriptions") 
            print(f"    - Deleted {cleanup_data.get('deleted_blobs', 0)} blob files")
            return True
        else:
            print(f"  ✗ Failed to delete test user: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tag tests."""
        print("🏷️  QuickScribe Tag API Tests")
        print("=" * 50)
        
        try:
            # Test 1: Create and setup test user
            if not self.test_create_test_user():
                return False
            
            # Test 2: Default tags
            if not self.test_default_tags():
                return False
            
            # Test 3: Create tags
            created_tags = self.test_create_tags()
            if not created_tags:
                return False
            
            # Test 4: Update tags
            if not self.test_update_tags(created_tags):
                return False
            
            # Test 5: Create dummy recording
            recording_id = self.test_dummy_recording_creation()
            if not recording_id:
                return False
            
            # Test 6: Recording tag operations
            if not self.test_recording_tags(created_tags, recording_id):
                return False
            
            # Test 7: Error cases
            if not self.test_error_cases():
                return False
            
            # Test 8: Delete tags
            if not self.test_delete_tags(created_tags, recording_id):
                return False
            
            print("\n" + "=" * 50)
            print("✅ All tag tests passed!")
            return True
        
        finally:
            # Always try to clean up
            self.cleanup_test_user()

def main():
    """Main test runner."""
    print("Starting tag API tests...")
    print("Make sure the Flask app is running at http://localhost:5000")
    print("You can start it with: docker-compose up backend")
    print()
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/get_api_version", timeout=5)
        if response.status_code == 200:
            version = response.json().get('version', 'unknown')
            print(f"Connected to QuickScribe API version: {version}")
        else:
            print("❌ Server responded but API endpoint failed")
            return 1
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"Error: {e}")
        print("Make sure the backend is running: docker-compose up backend")
        return 1
    
    # Run tests
    tester = TagTester()
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())