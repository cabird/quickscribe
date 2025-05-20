#!/usr/bin/env python3
"""
Test Queue Sender - Sends a test message to trigger the container app
"""

import os
import json
import sys
from datetime import datetime
from azure.storage.queue import QueueClient
from dotenv import load_dotenv

def main(message_content=None):
    # Load environment variables from .env file
    print("?? Loading environment variables...")
    load_dotenv()
    
    # Get required environment variables
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    queue_name = os.getenv('TRANSCODING_QUEUE_NAME')
    
    if not connection_string or not queue_name:
        print("? Error: Missing required environment variables")
        print("   - AZURE_STORAGE_CONNECTION_STRING")
        print("   - TRANSCODING_QUEUE_NAME")
        return
    
    print(f"?? Connecting to queue: {queue_name}")
    
    # Create queue client
    queue_client = QueueClient.from_connection_string(
        connection_string, 
        queue_name
    )

    if message_content is None:
        message_content = f"Test message sent at {datetime.utcnow().isoformat()}Z"
    else:
        message_content = f"Test message sent at {datetime.utcnow().isoformat()}Z: {message_content}"
        
    # Create test message
    test_message = {
        "action": "test",
        "content": message_content,
        "callbacks": [
            {
                "url": "https://quickscribe-containerized-webapp.azurewebsites.net/api/transcoding_callback",  # Replace with your webhook URL
                "token": f"test-token-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            }
        ]
    }
    
    # Send message to queue
    print("?? Sending test message...")
    print(f"?? Message content:")
    print(json.dumps(test_message, indent=2))
    
    try:
        # Send the message
        message_json = json.dumps(test_message)
        queue_client.send_message(message_json)
        
        print("? Test message sent successfully!")
        print(f"?? Check your container app logs to see it processing the message")
        print(f"?? You can also check webhook.site if you set up a webhook URL")
        
    except Exception as e:
        print(f"? Error sending message: {e}")
        return

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
