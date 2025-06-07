#!/usr/bin/env python3
"""
Quick test script to verify the progress monitoring system is working.
Run this after the backend is started to test the progress endpoints.
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
TEST_USER_ID = "test-user-123"

def test_progress_system():
    """Test the complete progress monitoring system"""
    
    print("🧪 Testing QuickScribe Progress Monitoring System")
    print("=" * 50)
    
    # Step 1: Test local login (development mode)
    print("1. Testing local authentication...")
    login_response = requests.get(f"{BASE_URL}/local/login/{TEST_USER_ID}")
    if login_response.status_code == 200:
        print("✅ Local login successful")
        # Get session cookies
        session = requests.Session()
        session.get(f"{BASE_URL}/local/login/{TEST_USER_ID}")
    else:
        print("❌ Local login failed - make sure backend is running with LOCAL_AUTH_ENABLED=true")
        return False
    
    # Step 2: Test sync progress container creation
    print("\n2. Testing sync progress container...")
    try:
        # This should trigger container creation if it doesn't exist
        check_response = session.get(f"{BASE_URL}/plaud/sync/check_active")
        if check_response.status_code == 200:
            print("✅ Sync progress system accessible")
        else:
            print(f"❌ Sync progress check failed: {check_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing sync progress: {e}")
        return False
    
    # Step 3: Test progress endpoint without active sync
    print("\n3. Testing progress endpoints...")
    check_data = check_response.json()
    if not check_data.get('has_active_sync'):
        print("✅ No active sync detected (expected)")
    else:
        print(f"ℹ️  Active sync found: {check_data.get('sync_token')}")
    
    # Step 4: Test stale sync cleanup
    print("\n4. Testing stale sync cleanup...")
    cleanup_response = session.post(f"{BASE_URL}/plaud/admin/cleanup_stale_syncs")
    if cleanup_response.status_code == 200:
        cleanup_data = cleanup_response.json()
        print(f"✅ Cleanup successful: {cleanup_data.get('message')}")
    else:
        print(f"❌ Cleanup failed: {cleanup_response.status_code}")
    
    print("\n🎉 Progress monitoring system test completed!")
    print("\nNext steps:")
    print("1. Set up Plaud token in frontend settings")
    print("2. Click 'Sync from Plaud' to test full workflow")
    print("3. Monitor progress in real-time")
    
    return True

if __name__ == "__main__":
    try:
        test_progress_system()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        print("Make sure the backend is running on localhost:5000")