#!/usr/bin/env python3
"""
Test script to verify the transcoding callback endpoint functionality.
This script simulates the container app sending callbacks with different statuses.
"""

import requests
import json
import argparse
import uuid

def send_callback(url, action, recording_id=None, token=None, status=None, metadata=None, error=None):
    """Send a test callback to the API endpoint."""
    
    # Prepare the callback data based on the action and status
    if action == "test":
        data = {
            "action": "test",
            "content": "This is a test callback",
            "container_version": "test-version-1.0.0",
            "callback_token": token or str(uuid.uuid4()),
            "status": "completed",
            "timestamp": "2025-05-16T12:34:56Z"
        }
    elif action == "transcode":
        data = {
            "action": "transcode",
            "recording_id": recording_id or str(uuid.uuid4()),
            "status": status or "in_progress",
            "container_version": "test-version-1.0.0",
            "callback_token": token or str(uuid.uuid4()),
            "timestamp": "2025-05-16T12:34:56Z"
        }
        
        # Add metadata for completed status
        if status == "completed" and metadata:
            data["processing_time"] = 45.2
            data["input_metadata"] = {
                "duration": metadata.get("input_duration", 180.5),
                "format": "m4a",
                "size_bytes": 13107200,
                "codec": "aac"
            }
            data["output_metadata"] = {
                "duration": metadata.get("output_duration", 180.5),
                "format": "mp3", 
                "size_bytes": 8388608,
                "bitrate": "128k",
                "codec": "mp3"
            }
        
        # Add error message for failed status
        if status == "failed" and error:
            data["error_message"] = error
    
    print(f"Sending callback to {url} with data:")
    print(json.dumps(data, indent=2))
    
    # Send the request
    try:
        response = requests.post(url, json=data)
        print(f"Response status code: {response.status_code}")
        print(f"Response body: {response.text}")
        return response
    except Exception as e:
        print(f"Error sending callback: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Test the transcoding callback endpoint")
    parser.add_argument("--url", default="http://localhost:5000/api/transcoding_callback",
                      help="URL of the callback endpoint")
    parser.add_argument("--recording-id", help="ID of an existing recording")
    parser.add_argument("--token", help="Valid callback token for the recording")
    parser.add_argument("--action", default="transcode", choices=["test", "transcode"],
                      help="Action to simulate")
    parser.add_argument("--status", default="in_progress", 
                      choices=["in_progress", "completed", "failed"],
                      help="Status of the transcoding job")
    parser.add_argument("--duration", type=float, default=180.5,
                      help="Duration to set in the metadata (for completed status)")
    parser.add_argument("--error", default="Transcoding failed due to invalid file format",
                      help="Error message (for failed status)")
    
    args = parser.parse_args()
    
    # Send the callback
    if args.action == "transcode":
        metadata = {"input_duration": args.duration, "output_duration": args.duration}
        send_callback(args.url, args.action, args.recording_id, args.token, 
                     args.status, metadata, args.error)
    else:
        send_callback(args.url, args.action, args.recording_id, args.token)

if __name__ == "__main__":
    main()
