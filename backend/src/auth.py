"""
Authentication module for Azure AD JWT token validation.

This module provides token validation for frontend-driven (SPA) authentication.
In production, it validates JWT tokens from Azure AD.
In development mode, authentication can be bypassed.
"""
import os
import jwt
import requests
from typing import Optional, Dict
from functools import lru_cache
from datetime import datetime, timedelta
from threading import Lock
from config import config
import logging

logger = logging.getLogger(__name__)

# Cache for Azure AD public keys (valid for 24 hours)
_jwks_cache = None
_jwks_cache_time = None
_jwks_cache_lock = Lock()
JWKS_CACHE_DURATION = timedelta(hours=24)
JWKS_MAX_STALE_DURATION = timedelta(days=7)


@lru_cache(maxsize=1)
def get_azure_ad_config() -> Dict[str, str]:
    """Get Azure AD configuration from environment."""
    tenant_id = config.AZ_AUTH_TENANT_ID
    return {
        'tenant_id': tenant_id,
        'issuer': f'https://login.microsoftonline.com/{tenant_id}/v2.0',
        'jwks_uri': f'https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys',
        'client_id': config.AZ_AUTH_CLIENT_ID,
    }


def get_jwks() -> Dict:
    """
    Fetch Azure AD JSON Web Key Set (JWKS) for token signature validation.

    Keys are cached for 24 hours to reduce network calls.
    Thread-safe implementation with double-check locking pattern.
    """
    global _jwks_cache, _jwks_cache_time

    # Return cached keys if still valid (check outside lock for performance)
    if _jwks_cache and _jwks_cache_time:
        if datetime.now() - _jwks_cache_time < JWKS_CACHE_DURATION:
            return _jwks_cache

    # Acquire lock to refresh cache
    with _jwks_cache_lock:
        # Double-check inside the lock to prevent race conditions
        if _jwks_cache and _jwks_cache_time:
            if datetime.now() - _jwks_cache_time < JWKS_CACHE_DURATION:
                return _jwks_cache

        # Fetch fresh keys from Azure AD
        try:
            azure_config = get_azure_ad_config()
            response = requests.get(azure_config['jwks_uri'], timeout=10)
            response.raise_for_status()

            _jwks_cache = response.json()
            _jwks_cache_time = datetime.now()

            logger.info(f"Fetched Azure AD JWKS: {len(_jwks_cache.get('keys', []))} keys")
            return _jwks_cache

        except Exception as e:
            logger.error(f"Failed to fetch Azure AD JWKS: {e}")
            # Return cached keys only if not too stale
            if _jwks_cache and _jwks_cache_time:
                cache_age = datetime.now() - _jwks_cache_time
                if cache_age < JWKS_MAX_STALE_DURATION:
                    logger.warning(f"Using expired JWKS cache as fallback (age: {cache_age})")
                    return _jwks_cache
                else:
                    logger.critical(f"JWKS cache is too stale ({cache_age}). Failing request.")
            raise


def get_signing_key(token: str) -> Optional[str]:
    """
    Extract the public key for validating a JWT token signature.

    Args:
        token: JWT token string

    Returns:
        Public key in PEM format, or None if not found
    """
    try:
        # Decode header without validation to get key ID (kid)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')

        if not kid:
            logger.error("Token missing 'kid' in header")
            return None

        # Find matching key in JWKS
        jwks = get_jwks()
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                # Convert JWK to PEM format
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)

        logger.error(f"No matching key found for kid: {kid}")
        return None

    except Exception as e:
        logger.error(f"Failed to get signing key: {e}")
        return None


def validate_token(token: str) -> Optional[Dict]:
    """
    Validate a JWT token from Azure AD.

    Validates:
    - Signature using Azure AD public keys
    - Issuer (iss claim)
    - Audience (aud claim)
    - Expiration (exp claim)
    - Not before (nbf claim)

    Args:
        token: JWT token string from Authorization header

    Returns:
        Dictionary of token claims if valid, None otherwise
    """
    try:
        azure_config = get_azure_ad_config()

        # Get the signing key
        signing_key = get_signing_key(token)
        if not signing_key:
            return None

        # Validate and decode token
        # PyJWT automatically verifies signature, exp, nbf, iat, aud, and iss when provided
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=['RS256'],
            audience=[
                azure_config['client_id'],
                f"api://{azure_config['client_id']}"
            ],
            issuer=azure_config['issuer']
        )

        logger.info(f"Token validated successfully for user: {claims.get('oid', 'unknown')}")
        return claims

    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None

    except jwt.InvalidAudienceError:
        logger.warning("Token has invalid audience")
        return None

    except jwt.InvalidIssuerError:
        logger.warning("Token has invalid issuer")
        return None

    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error validating token: {e}")
        return None


def extract_token_from_header() -> Optional[str]:
    """
    Extract Bearer token from Authorization header.

    Returns:
        Token string if found, None otherwise
    """
    from flask import request

    auth_header = request.headers.get('Authorization', '')

    if not auth_header:
        return None

    # Expected format: "Bearer <token>"
    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != 'bearer':
        logger.warning(f"Invalid Authorization header format: {auth_header[:20]}...")
        return None

    return parts[1]
