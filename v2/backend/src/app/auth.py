"""Authentication — Azure AD JWT validation with dev bypass.

In production: validates Bearer token against Azure AD JWKS keys.
In dev: AUTH_DISABLED=true returns a hardcoded dev user.
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

_jwks_cache: dict = {}
_jwks_cache_time: float = 0
_jwks_lock = asyncio.Lock()
_JWKS_TTL = 86400  # 24 hours
_JWKS_STALE_TTL = 604800  # 7 days fallback


async def _fetch_jwks(tenant_id: str) -> dict:
    """Fetch JWKS keys from Azure AD."""
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()


async def _get_signing_key(kid: str, tenant_id: str) -> jwt.algorithms.RSAAlgorithm:
    """Get the RSA signing key for a given key ID."""
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    need_refresh = (now - _jwks_cache_time) > _JWKS_TTL

    if need_refresh or not _jwks_cache:
        async with _jwks_lock:
            # Re-check after acquiring lock (another coroutine may have refreshed)
            now = time.time()
            need_refresh = (now - _jwks_cache_time) > _JWKS_TTL
            if need_refresh or not _jwks_cache:
                try:
                    _jwks_cache = await _fetch_jwks(tenant_id)
                    _jwks_cache_time = now
                except Exception:
                    # Fall back to stale cache if within stale TTL
                    if _jwks_cache and (now - _jwks_cache_time) < _JWKS_STALE_TTL:
                        pass
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Unable to fetch authentication keys",
                        )

    for key_data in _jwks_cache.get("keys", []):
        if key_data.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token signing key not found",
    )


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


async def _validate_token(token: str, settings: Settings) -> dict:
    """Validate an Azure AD JWT token and return claims."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token missing key ID")

    signing_key = await _get_signing_key(kid, settings.azure_tenant_id)

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=[settings.azure_client_id, f"api://{settings.azure_client_id}"],
            issuer=f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0",
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# User resolution
# ---------------------------------------------------------------------------


async def _get_or_create_user(azure_oid: str, email: str | None, name: str | None) -> User:
    """Look up user by email (primary) or Azure OID, or auto-provision."""
    db = await get_db()

    # Primary lookup: email (case-insensitive)
    if email:
        row = await db.execute_fetchall(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,)
        )
        if row:
            user = User(**dict(row[0]))
            # Sync azure_oid and name on each login
            await db.execute(
                "UPDATE users SET azure_oid = ?, name = COALESCE(?, name) WHERE id = ?",
                (azure_oid, name, user.id),
            )
            await db.commit()
            user.azure_oid = azure_oid
            if name:
                user.name = name
            return user

    # Fallback: Azure OID
    row = await db.execute_fetchall(
        "SELECT * FROM users WHERE azure_oid = ?", (azure_oid,)
    )
    if row:
        user = User(**dict(row[0]))
        if email and not user.email:
            await db.execute("UPDATE users SET email = ? WHERE id = ?", (email, user.id))
            await db.commit()
            user.email = email
        return user

    # Auto-provision
    import uuid

    user_id = f"user-{uuid.uuid4()}"
    await db.execute(
        """INSERT INTO users (id, name, email, azure_oid, created_at, last_login)
           VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (user_id, name, email, azure_oid),
    )
    await db.commit()

    row = await db.execute_fetchall("SELECT * FROM users WHERE id = ?", (user_id,))
    return User(**dict(row[0]))


async def _get_dev_user() -> User:
    """Get or create the development bypass user.

    Tries to find the first real (non-test) user, falling back to creating a 'dev' user.
    """
    db = await get_db()

    # First try to find an existing real user (most likely the app owner)
    row = await db.execute_fetchall(
        "SELECT * FROM users WHERE name NOT LIKE 'Test%' AND name != 'dev' ORDER BY created_at ASC LIMIT 1"
    )
    if row:
        return User(**dict(row[0]))

    # Fall back to a 'dev' user
    row = await db.execute_fetchall(
        "SELECT * FROM users WHERE name = 'dev'"
    )
    if row:
        return User(**dict(row[0]))

    import uuid

    user_id = f"user-{uuid.uuid4()}"
    await db.execute(
        """INSERT INTO users (id, name, email, role, created_at, last_login)
           VALUES (?, 'dev', 'dev@localhost', 'user', datetime('now'), datetime('now'))""",
        (user_id,),
    )
    await db.commit()
    row = await db.execute_fetchall("SELECT * FROM users WHERE id = ?", (user_id,))
    return User(**dict(row[0]))


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """FastAPI dependency — returns the authenticated user."""
    if settings.auth_disabled:
        return await _get_dev_user()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = auth_header[7:]
    claims = await _validate_token(token, settings)

    azure_oid = claims.get("oid")
    if not azure_oid:
        raise HTTPException(status_code=401, detail="Token missing oid claim")

    user = await _get_or_create_user(
        azure_oid=azure_oid,
        email=claims.get("preferred_username") or claims.get("email"),
        name=claims.get("name"),
    )

    # Update last login
    db = await get_db()
    await db.execute(
        "UPDATE users SET last_login = datetime('now') WHERE id = ?", (user.id,)
    )
    await db.commit()

    return user
