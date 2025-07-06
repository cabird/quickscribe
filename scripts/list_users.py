#!/usr/bin/env python3
"""
List all users in the database to find user IDs.
"""

import sys
import os

# Add the backend directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
backend_dir = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_dir)

from db_handlers.user_handler import UserHandler
from config import config
from logging_config import get_logger

logger = get_logger('list_users')

def list_all_users():
    """List all users with their IDs and email addresses."""
    # Create handler directly instead of using factory (which requires Flask context)
    user_handler = UserHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
    
    try:
        users = user_handler.get_all_users()
        
        if not users:
            print("No users found in the database.")
            return
        
        print(f"Found {len(users)} users:\n")
        print(f"{'User ID':<40} {'Email':<40} {'Name':<30}")
        print("-" * 110)
        
        for user in users:
            user_id = user.id
            email = user.email or 'N/A'
            name = user.name or 'N/A'
            print(f"{user_id:<40} {email:<40} {name:<30}")
            
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    list_all_users()