#!/usr/bin/env python3
"""
Script to create test users for local development.

Usage:
    python create-test-user.py "Alice Test"
    python create-test-user.py "Bob Test"

Requirements:
    - Run from the project root directory
    - Backend .env.local file must exist with CosmosDB credentials
    - pip install python-dotenv
"""

import sys
import os
import re
import uuid
from datetime import datetime, UTC
from dotenv import load_dotenv

# Add backend directory to path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

def slugify(name):
    """Convert name to slug format for ID generation"""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower())
    return slug.strip('-')

def create_test_user(name):
    """Create a test user in CosmosDB"""
    
    # Load environment variables from backend/.env.local
    env_file = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env.local')
    if not os.path.exists(env_file):
        print(f"Error: {env_file} not found")
        sys.exit(1)
    
    load_dotenv(env_file)
    
    # Import after loading environment variables
    from db_handlers.handler_factory import create_user_handler
    
    # Generate user details
    slug = slugify(name)
    user_id = f"test-{slug}"
    email = f"{slug}@test.local"
    
    print(f"Creating test user: {name}")
    print(f"User ID: {user_id}")
    print(f"Email: {email}")
    
    # Create user handler
    user_handler = create_user_handler()
    
    # Check if user already exists
    existing_user = user_handler.get_user(user_id)
    if existing_user:
        print(f"User {user_id} already exists. Skipping creation.")
        return
    
    # Create user data
    user_data = {
        "id": user_id,
        "name": name,
        "email": email,
        "role": "user",
        "created_at": datetime.now(UTC).isoformat(),
        "last_login": None,
        "partitionKey": "user",
        "is_test_user": True,
        "plaudSettings": None
    }
    
    try:
        # Create user in database
        from azure.cosmos import CosmosClient
        cosmos_url = os.environ.get('COSMOS_URL')
        cosmos_key = os.environ.get('COSMOS_KEY')
        database_name = os.environ.get('COSMOS_DB_NAME')
        container_name = os.environ.get('COSMOS_CONTAINER_NAME')
        
        client = CosmosClient(cosmos_url, credential=cosmos_key)
        database = client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        
        container.create_item(body=user_data)
        
        print(f"✅ Successfully created test user: {name}")
        print(f"   ID: {user_id}")
        print(f"   Email: {email}")
        
    except Exception as e:
        print(f"❌ Failed to create user: {e}")
        sys.exit(1)

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python create-test-user.py \"User Name\"")
        print("Example: python create-test-user.py \"Alice Test\"")
        sys.exit(1)
    
    name = sys.argv[1].strip()
    if not name:
        print("Error: User name cannot be empty")
        sys.exit(1)
    
    create_test_user(name)

if __name__ == "__main__":
    main()