import os
from config import config
from flask import request, session, jsonify
from db_handlers.user_handler import UserHandler
from db_handlers.models import User
from typing import Optional
from functools import wraps

def get_current_user() -> Optional[User]: 
    user_handler = UserHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
    
    # Check if local auth is enabled and we have a local user session
    if os.getenv('LOCAL_AUTH_ENABLED') and 'local_user_id' in session:
        local_user_id = session['local_user_id']
        user = user_handler.get_user(local_user_id)
        if user and user.is_test_user:
            return user
        # If local user not found or not a test user, clear the session
        session.pop('local_user_id', None)
    
    # Original authentication logic for production
    # Try to get the user_id from cookies
    user_id = request.cookies.get('user_id')

    if user_id:
        # Fetch user by ID if the user_id exists in the cookie
        user = user_handler.get_user(user_id)
    else:
        # If no user_id in cookie, fetch user by name 'cbird'
        users = user_handler.get_user_by_name('cbird')
        user = users[0] if users else None  # Assuming 'cbird' is unique, take the first result

    return user


def require_auth(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function