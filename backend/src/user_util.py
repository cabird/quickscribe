"""
User utility functions for authentication and user management.

Supports three authentication modes:
1. Development (AUTH_MODE=disabled): Uses default 'cbird' user or test users
2. Local Testing (AUTH_MODE=enabled): Validates JWT tokens locally
3. Production (AUTH_MODE=enabled): Strict JWT validation in deployed environment
"""
import os
from config import config
from flask import request, session, jsonify
from shared_quickscribe_py.cosmos import get_user_handler, User
from typing import Optional
from functools import wraps
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


def get_current_user() -> Optional[User]:
    """
    Get the current authenticated user based on AUTH_MODE.

    In development mode (AUTH_MODE=disabled):
        - Uses 'local_user_id' from session if set (via /api/local/login)
        - Falls back to default 'cbird' user
        - No token validation

    In enabled mode (AUTH_MODE=enabled):
        - Extracts and validates JWT token from Authorization header
        - Auto-provisions user on first login
        - Strict validation

    Returns:
        User object if authenticated, None otherwise
    """
    auth_mode = os.getenv('AUTH_MODE', 'enabled')

    # Mode 1: Development bypass - use test users
    if auth_mode == 'disabled' and os.getenv('USE_DEV_USER_BYPASS') == 'true':
        return _get_local_test_user()

    # Mode 2 & 3: Real authentication
    return _get_authenticated_user()


def _get_local_test_user() -> Optional[User]:
    """
    Development mode: Use session-based test user or default 'cbird' user.

    Priority:
    1. Test user from session (set via /api/local/login)
    2. Default 'cbird' user (for rapid development)

    Returns:
        User object if found, None otherwise
    """
    user_handler = get_user_handler()

    # Check if test user selected via /api/local/login
    if 'local_user_id' in session:
        local_user_id = session['local_user_id']
        logger.info(f"Using test user from session: {local_user_id}")

        user = user_handler.get_user(local_user_id)
        if user and user.is_test_user:
            return user

        # If user not found or not a test user, clear the session
        logger.warning(f"Test user {local_user_id} not found or not marked as test user")
        session.pop('local_user_id', None)

    # Fallback: Use default user from environment for development
    default_dev_user = os.getenv('DEFAULT_DEV_USER', 'cbird')
    logger.info(f"Using default '{default_dev_user}' user for development")
    users = user_handler.get_user_by_name(default_dev_user)

    if users and len(users) > 0:
        return users[0]

    # If default user doesn't exist, log warning
    logger.warning(f"Default '{default_dev_user}' user not found in database")
    return None


def _get_authenticated_user() -> Optional[User]:
    """
    Production/testing mode: Validate JWT token and get/create user.

    Process:
    1. Extract Bearer token from Authorization header
    2. Validate token signature and claims
    3. Extract user info from token (oid, email, name)
    4. Fetch user from database or auto-provision on first login

    Returns:
        User object if token valid, None otherwise
    """
    from auth import extract_token_from_header, validate_token

    # Extract token from Authorization header
    token = extract_token_from_header()
    if not token:
        logger.debug("No authorization token in request")
        return None

    # Validate token and extract claims
    claims = validate_token(token)
    if not claims:
        logger.warning("Token validation failed")
        return None

    # Extract user information from token claims
    user_id = claims.get('oid')  # Azure AD Object ID (stable, unique)
    if not user_id:
        logger.error("Token missing 'oid' claim")
        return None

    email = claims.get('email') or claims.get('preferred_username') or claims.get('upn')
    name = claims.get('name')

    logger.info(f"Token validated for user: {email} (oid: {user_id})")

    # Get or create user
    user_handler = get_user_handler()

    # First, try to find user by Azure OID (for linked accounts)
    user = user_handler.get_user_by_azure_oid(user_id)

    if user:
        logger.info(f"Found existing user linked to Azure OID: {user.id}")
        return user

    # No linked user found - check if there's a user with matching email we can link
    if email:
        users_by_email = user_handler.get_user_by_email(email) if hasattr(user_handler, 'get_user_by_email') else []
        if not users_by_email:
            # Try by name as fallback (for legacy users)
            users_by_email = [u for u in user_handler.get_all_users() if u.email == email]

        if users_by_email:
            # Found existing user with same email - link Azure OID to them
            user = users_by_email[0]
            logger.info(f"Linking Azure OID {user_id} to existing user {user.id} ({user.email})")
            user.azure_oid = user_id
            try:
                user_handler.save_user(user)
                logger.info(f"Successfully linked Azure OID to user {user.id}")
            except Exception as e:
                logger.error(f"Failed to link Azure OID: {e}")
            return user

    # No existing user found - create a new one
    logger.info(f"Auto-provisioning new user: {email}")

    new_user_id = f"user-{user_id}"  # Prefix with 'user-' for consistency
    user = User(
        id=new_user_id,
        partitionKey="user",
        email=email,
        name=name or email,  # Use email as name if name not provided
        is_test_user=False,
        type="user",
        azure_oid=user_id,  # Store the Azure OID for future lookups
    )

    try:
        # Use create_item for new users since they don't exist yet
        user_data = user.model_dump(exclude_unset=True, exclude_none=True)
        user_handler.container.create_item(body=user_data)
        logger.info(f"User provisioned successfully: {new_user_id}")
    except Exception as e:
        logger.error(f"Failed to provision user: {e}")
        return None

    return user


def require_auth(f):
    """
    Decorator to require authentication for a route.

    In development mode (AUTH_MODE=disabled):
        - Allows requests with any available user (test user or cbird)
        - Returns 401 if no user available

    In enabled mode (AUTH_MODE=enabled):
        - Strictly validates JWT token
        - Returns 401 if token missing or invalid

    Usage:
        @api_bp.route('/protected')
        @require_auth
        def protected_route():
            user = get_current_user()
            return jsonify({'user_id': user.id})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_mode = os.getenv('AUTH_MODE', 'enabled')

        user = get_current_user()

        if not user:
            if auth_mode == 'disabled':
                return jsonify({
                    'error': 'No user available',
                    'message': 'Development mode active but no default user found. Create a test user or check database.'
                }), 401
            else:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'Valid Bearer token required in Authorization header'
                }), 401

        # User authenticated, proceed with route
        return f(*args, **kwargs)

    return decorated_function
