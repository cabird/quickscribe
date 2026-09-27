"""Persistent OAuth state; isolated transactions on the existing SQLite file.

Never share a transaction with application services. Every connection disables
automatic WAL checkpoints: Litestream exclusively owns checkpointing in production.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import aiosqlite

from .config import get_settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS oauth_transactions (
    id_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
    client_id TEXT NOT NULL, client_name TEXT NOT NULL,
    redirect_uri TEXT NOT NULL, resource TEXT NOT NULL,
    code_challenge TEXT NOT NULL, state TEXT,
    expires_at INTEGER NOT NULL, consumed_at INTEGER
);
CREATE TABLE IF NOT EXISTS oauth_grants (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL, client_name TEXT NOT NULL,
    resource TEXT NOT NULL, scope TEXT NOT NULL,
    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
    revoked_at INTEGER, last_used_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_oauth_grants_user ON oauth_grants(user_id);
CREATE TABLE IF NOT EXISTS oauth_codes (
    code_hash TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL REFERENCES oauth_grants(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL, code_challenge TEXT NOT NULL,
    expires_at INTEGER NOT NULL, consumed_at INTEGER
);
CREATE TABLE IF NOT EXISTS oauth_credentials (
    token_hash TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL REFERENCES oauth_grants(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('access','refresh')),
    expires_at INTEGER NOT NULL, consumed_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_oauth_credentials_grant ON oauth_credentials(grant_id);
CREATE INDEX IF NOT EXISTS ix_oauth_codes_grant ON oauth_codes(grant_id);
"""


@asynccontextmanager
async def connect(*, write=False):
    async with aiosqlite.connect(get_settings().database_path, timeout=10) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA wal_autocheckpoint=0")
        await db.execute("PRAGMA foreign_keys=ON")
        if write:
            await db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            await db.commit()
        except BaseException:
            await db.rollback()
            raise


async def one(db, sql, args=()):
    async with db.execute(sql, args) as cursor:
        row = await cursor.fetchone()
    return SimpleNamespace(**dict(row)) if row else None


async def prune(db, now):
    await db.execute("DELETE FROM oauth_transactions WHERE expires_at < ?", (now,))
    await db.execute("DELETE FROM oauth_codes WHERE expires_at < ?", (now - 86400,))
    # Keep consumed refresh hashes for the grant lifetime to detect replay.
    # Cascades remove credentials when a dead grant passes its 7-day retention.
    await db.execute(
        "DELETE FROM oauth_grants WHERE expires_at < ? OR revoked_at < ?",
        (now - 7 * 86400, now - 7 * 86400),
    )
