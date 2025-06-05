#!/usr/bin/env python3
"""
Debug script to investigate Plaud timestamp filtering issues.

This script:
1. Fetches recordings from Plaud API
2. Shows their timestamps in various timezones
3. Helps debug why recordings are being filtered out
"""

import os
import sys
from datetime import datetime, timezone, timedelta, UTC
from pathlib import Path
import requests
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment
env_file = Path(__file__).parent / '.env.test'
if env_file.exists():
    load_dotenv(env_file)
else:
    print(f"❌ Please create {env_file} with your Plaud bearer token")
    sys.exit(1)

def get_default_headers(bearer_token: str):
    """Get HTTP headers for Plaud API requests"""
    return {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': f'bearer {bearer_token}',
        'edit-from': 'web',
        'origin': 'https://app.plaud.ai',
        'priority': 'u=1, i',
        'referer': 'https://app.plaud.ai/',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
    }

def fetch_recordings(bearer_token: str, limit: int = 10):
    """Fetch recordings from Plaud API"""
    url = 'https://api.plaud.ai/file/simple/web'
    params = {
        'skip': 0,
        'limit': limit,
        'is_trash': 2,  # include all
        'sort_by': 'start_time',
        'is_desc': 'true'
    }
    
    session = requests.Session()
    session.headers.update(get_default_headers(bearer_token))
    
    response = session.get(url, params=params)
    response.raise_for_status()
    return response.json()

def convert_plaud_timestamp(start_time_ms: int, tz_hours: int, tz_mins: int = 0):
    """Convert Plaud timestamp to datetime"""
    # Convert milliseconds to seconds
    start_time_seconds = start_time_ms / 1000
    # Create timezone object
    tz_offset = timedelta(hours=tz_hours, minutes=tz_mins)
    tz = timezone(tz_offset)
    # Create and return datetime object
    return datetime.fromtimestamp(start_time_seconds, tz=tz)

def main():
    bearer_token = os.getenv('PLAUD_BEARER_TOKEN')
    if not bearer_token:
        print("❌ PLAUD_BEARER_TOKEN not found in environment")
        sys.exit(1)
    
    # Test timestamp from the logs
    test_timestamp_str = "2025-06-04T06:51:08.691520+00:00"
    test_timestamp = datetime.fromisoformat(test_timestamp_str)
    
    print("🔍 Debugging Plaud Timestamp Filtering")
    print("=" * 60)
    print(f"\n📅 Last sync timestamp: {test_timestamp_str}")
    print(f"   As UTC: {test_timestamp}")
    print(f"   Unix timestamp: {test_timestamp.timestamp()}")
    
    # Fetch recordings
    print(f"\n📥 Fetching recordings from Plaud...")
    try:
        data = fetch_recordings(bearer_token, limit=10)
        recordings = data.get('data_file_list', [])
        total = data.get('data_file_total', 0)
        
        print(f"✅ Found {len(recordings)} recordings (total: {total})")
        
        print(f"\n📊 Analyzing recordings:")
        print("-" * 100)
        
        newer_count = 0
        for idx, rec in enumerate(recordings):
            # Get recording details
            filename = rec.get('filename', 'Unknown')
            start_time_ms = rec.get('start_time', 0)
            tz_hours = rec.get('timezone', 0)
            tz_mins = rec.get('zonemins', 0)
            
            # Convert to datetime
            rec_datetime = convert_plaud_timestamp(start_time_ms, tz_hours, tz_mins)
            
            # Convert to UTC for comparison
            rec_datetime_utc = rec_datetime.astimezone(UTC)
            
            # Check if newer than test timestamp
            is_newer = rec_datetime > test_timestamp
            is_newer_utc = rec_datetime_utc > test_timestamp
            
            if is_newer_utc:
                newer_count += 1
            
            print(f"\n{idx + 1}. {filename}")
            print(f"   Plaud timestamp (ms): {start_time_ms}")
            print(f"   Timezone offset: UTC{tz_hours:+d}:{tz_mins:02d}")
            print(f"   Local time: {rec_datetime}")
            print(f"   UTC time: {rec_datetime_utc}")
            print(f"   Time diff from last sync: {rec_datetime_utc - test_timestamp}")
            print(f"   Is newer (local compare): {'✅ YES' if is_newer else '❌ NO'}")
            print(f"   Is newer (UTC compare): {'✅ YES' if is_newer_utc else '❌ NO'}")
            
        print("\n" + "=" * 100)
        print(f"\n📈 Summary:")
        print(f"   Total recordings fetched: {len(recordings)}")
        print(f"   Recordings newer than {test_timestamp_str}: {newer_count}")
        
        # Additional timezone debugging
        print(f"\n🌍 Timezone Analysis:")
        print(f"   Current UTC time: {datetime.now(UTC)}")
        print(f"   Hours since last sync: {(datetime.now(UTC) - test_timestamp).total_seconds() / 3600:.1f}")
        
        # Check if the comparison in the code is correct
        print(f"\n🐛 Code Comparison Test:")
        print(f"   The code does: recording.recording_datetime > last_sync_dt")
        print(f"   last_sync_dt is: {test_timestamp} (timezone-aware UTC)")
        
        if recordings:
            first_rec = recordings[0]
            rec_dt = convert_plaud_timestamp(
                first_rec['start_time'], 
                first_rec.get('timezone', 0),
                first_rec.get('zonemins', 0)
            )
            print(f"   First recording datetime: {rec_dt} (timezone-aware local)")
            print(f"   Direct comparison result: {rec_dt > test_timestamp}")
            print(f"   ⚠️  This compares different timezones!")
            
    except Exception as e:
        print(f"❌ Error fetching recordings: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()