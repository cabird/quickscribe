"""MCP token management — create, list, revoke, validate."""

from __future__ import annotations

import hashlib
import secrets
import uuid

from fastapi import HTTPException

from app.database import get_db
from app.models import McpTokenResponse

TOKEN_PREFIX = "qs_mcp_"


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_token(user_id: str, name: str) -> McpTokenResponse:
    """Generate a new MCP token for a user. Max 10 active tokens."""
    db = await get_db()

    # Check active (non-revoked) token count
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) as cnt FROM mcp_tokens WHERE user_id = ? AND revoked_at IS NULL",
        (user_id,),
    )
    if rows[0]["cnt"] >= 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum of 10 active MCP tokens reached. Revoke an existing token first.",
        )

    raw_token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    token_prefix = raw_token[len(TOKEN_PREFIX) : len(TOKEN_PREFIX) + 6]
    token_id = uuid.uuid4().hex[:8]

    await db.execute(
        """INSERT INTO mcp_tokens (id, user_id, token_name, token_prefix, token_hash, raw_token)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (token_id, user_id, name, token_prefix, token_hash, raw_token),
    )
    await db.commit()

    rows = await db.execute_fetchall(
        "SELECT * FROM mcp_tokens WHERE id = ?", (token_id,)
    )
    row = rows[0]
    return McpTokenResponse(
        id=row["id"],
        token_name=row["token_name"],
        token_prefix=row["token_prefix"],
        raw_token=row["raw_token"],
        last_used_at=row["last_used_at"],
        revoked_at=row["revoked_at"],
        created_at=row["created_at"],
    )


async def list_tokens(user_id: str) -> list[McpTokenResponse]:
    """List all tokens for a user, ordered by created_at DESC."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM mcp_tokens WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    return [
        McpTokenResponse(
            id=row["id"],
            token_name=row["token_name"],
            token_prefix=row["token_prefix"],
            raw_token=row["raw_token"],
            last_used_at=row["last_used_at"],
            revoked_at=row["revoked_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def revoke_token(user_id: str, token_id: str) -> None:
    """Revoke a token. 404 if not found or not owned by user."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id FROM mcp_tokens WHERE id = ? AND user_id = ?",
        (token_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Token not found")

    await db.execute(
        "UPDATE mcp_tokens SET revoked_at = datetime('now') WHERE id = ?",
        (token_id,),
    )
    await db.commit()


async def validate_token(raw_token: str) -> str | None:
    """Validate a raw token. Returns user_id if valid, None otherwise."""
    db = await get_db()
    token_hash_val = hash_token(raw_token)

    rows = await db.execute_fetchall(
        "SELECT user_id, revoked_at FROM mcp_tokens WHERE token_hash = ?",
        (token_hash_val,),
    )
    if not rows:
        return None

    row = rows[0]

    # Check revoked
    if row["revoked_at"] is not None:
        return None

    # Update last_used_at
    await db.execute(
        "UPDATE mcp_tokens SET last_used_at = datetime('now') WHERE token_hash = ?",
        (token_hash_val,),
    )
    await db.commit()

    return row["user_id"]
