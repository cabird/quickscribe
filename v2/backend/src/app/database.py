"""SQLite database connection and schema management.

Uses aiosqlite for async access. WAL mode enabled for concurrent reads.
"""

from __future__ import annotations

import aiosqlite
from pathlib import Path

from app.config import get_settings

_db: aiosqlite.Connection | None = None


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    email           TEXT,
    role            TEXT DEFAULT 'user',
    azure_oid       TEXT UNIQUE,
    plaud_enabled   INTEGER DEFAULT 0,
    plaud_token     TEXT,
    plaud_last_sync TEXT,
    settings_json   TEXT,
    api_key         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    last_login      TEXT
);

CREATE TABLE IF NOT EXISTS recordings (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(id),

    -- Audio metadata
    title               TEXT,
    description         TEXT,
    original_filename   TEXT NOT NULL,
    file_path           TEXT,
    duration_seconds    REAL,
    recorded_at         TEXT,
    source              TEXT NOT NULL,

    -- Plaud-specific
    plaud_id            TEXT UNIQUE,
    plaud_metadata_json TEXT,

    -- Processing status
    status              TEXT NOT NULL DEFAULT 'pending',
    status_message      TEXT,
    provider_job_id     TEXT,
    processing_started  TEXT,
    processing_completed TEXT,
    retry_count         INTEGER DEFAULT 0,

    -- Transcript data
    transcript_text     TEXT,
    diarized_text       TEXT,
    transcript_json     TEXT,
    token_count         INTEGER,
    speaker_mapping     TEXT,

    -- Search (AI-generated)
    search_summary      TEXT,
    search_keywords     TEXT,

    -- Meeting notes (AI-generated)
    meeting_notes           TEXT,
    meeting_notes_generated_at TEXT,
    meeting_notes_tags      TEXT,
    speaker_mapping_updated_at TEXT,

    -- Timestamps
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_recordings_user_id ON recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_recordings_status ON recordings(status);
CREATE INDEX IF NOT EXISTS idx_recordings_recorded_at ON recordings(user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_recordings_plaud_id ON recordings(plaud_id);

CREATE TABLE IF NOT EXISTS participants (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id),
    display_name    TEXT NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    aliases         TEXT,
    email           TEXT,
    role            TEXT,
    organization    TEXT,
    relationship    TEXT,
    notes           TEXT,
    is_user         INTEGER DEFAULT 0,
    first_seen      TEXT,
    last_seen       TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_participants_user_id ON participants(user_id);

CREATE TABLE IF NOT EXISTS tags (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    color       TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS recording_tags (
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    tag_id       TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (recording_id, tag_id)
);

CREATE TABLE IF NOT EXISTS analysis_templates (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deleted_plaud_ids (
    user_id     TEXT NOT NULL REFERENCES users(id),
    plaud_id    TEXT NOT NULL,
    deleted_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, plaud_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id              TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,
    trigger         TEXT NOT NULL,
    type            TEXT DEFAULT 'plaud_sync',
    stats_json      TEXT,
    error_message   TEXT,
    logs_json       TEXT,
    users_processed TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES sync_runs(id) ON DELETE CASCADE,
    timestamp   TEXT DEFAULT (datetime('now')),
    level       TEXT NOT NULL DEFAULT 'info',
    message     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_logs_run_id ON run_logs(run_id);

CREATE TABLE IF NOT EXISTS speaker_profiles (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id),
    participant_id  TEXT NOT NULL REFERENCES participants(id),
    display_name    TEXT NOT NULL,
    centroid        BLOB,
    n_samples       INTEGER DEFAULT 0,
    embeddings_blob BLOB,
    recording_ids   TEXT,
    embedding_std   REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, participant_id)
);

CREATE INDEX IF NOT EXISTS idx_speaker_profiles_user ON speaker_profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_recording_tags_recording ON recording_tags(recording_id);
CREATE INDEX IF NOT EXISTS idx_recording_tags_tag ON recording_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_analysis_templates_user ON analysis_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started_at ON sync_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status ON sync_runs(status);

CREATE TABLE IF NOT EXISTS search_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id TEXT NOT NULL,
    question TEXT NOT NULL,
    tier TEXT NOT NULL,
    step TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    reasoning_tokens INTEGER,
    duration_ms INTEGER,
    input_text TEXT,
    output_text TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_search_traces_search_id ON search_traces(search_id);
CREATE INDEX IF NOT EXISTS idx_search_traces_created ON search_traces(created_at DESC);

CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL DEFAULT 'Untitled collection',
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_collections_user_id ON collections(user_id);

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    added_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, recording_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_items_recording ON collection_items(recording_id);

CREATE TABLE IF NOT EXISTS mcp_tokens (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    token_name      TEXT NOT NULL,
    token_prefix    TEXT NOT NULL,
    token_hash      TEXT NOT NULL UNIQUE,
    raw_token       TEXT NOT NULL,
    scopes          TEXT,
    last_used_at    DATETIME,
    revoked_at      DATETIME,
    created_at      DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_mcp_tokens_user_id ON mcp_tokens (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_mcp_tokens_token_hash ON mcp_tokens (token_hash);

CREATE TABLE IF NOT EXISTS collection_searches (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT,
    item_count INTEGER,
    item_set_hash TEXT,
    search_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_collection_searches_collection ON collection_searches(collection_id);
"""

FTS_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
    title, description, diarized_text, transcript_text, search_summary,
    content='recordings',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
    INSERT INTO recordings_fts(rowid, title, description, diarized_text, transcript_text, search_summary)
    VALUES (new.rowid, new.title, new.description, new.diarized_text, new.transcript_text, new.search_summary);
END;

CREATE TRIGGER IF NOT EXISTS recordings_ad AFTER DELETE ON recordings BEGIN
    INSERT INTO recordings_fts(recordings_fts, rowid, title, description, diarized_text, transcript_text, search_summary)
    VALUES ('delete', old.rowid, old.title, old.description, old.diarized_text, old.transcript_text, old.search_summary);
END;

CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
    INSERT INTO recordings_fts(recordings_fts, rowid, title, description, diarized_text, transcript_text, search_summary)
    VALUES ('delete', old.rowid, old.title, old.description, old.diarized_text, old.transcript_text, old.search_summary);
    INSERT INTO recordings_fts(rowid, title, description, diarized_text, transcript_text, search_summary)
    VALUES (new.rowid, new.title, new.description, new.diarized_text, new.transcript_text, new.search_summary);
END;
"""


async def get_db() -> aiosqlite.Connection:
    """Get the database connection singleton."""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def _migrate_schema(db: aiosqlite.Connection) -> None:
    """Run lightweight migrations for schema additions."""
    # Add search_summary and search_keywords columns if missing
    cursor = await db.execute("PRAGMA table_info(recordings)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "search_summary" not in columns:
        await db.execute("ALTER TABLE recordings ADD COLUMN search_summary TEXT")
    if "search_keywords" not in columns:
        await db.execute("ALTER TABLE recordings ADD COLUMN search_keywords TEXT")

    # Rebuild FTS table if search_summary column was added
    # (FTS5 virtual tables can't be ALTERed, so drop and recreate)
    if "search_summary" not in columns:
        await db.execute("DROP TABLE IF EXISTS recordings_fts")
        await db.execute("DROP TRIGGER IF EXISTS recordings_ai")
        await db.execute("DROP TRIGGER IF EXISTS recordings_ad")
        await db.execute("DROP TRIGGER IF EXISTS recordings_au")
        await db.executescript(FTS_SCHEMA_SQL)
        # Repopulate FTS from existing data
        await db.execute(
            """INSERT INTO recordings_fts(rowid, title, description, diarized_text, transcript_text, search_summary)
               SELECT rowid, title, description, diarized_text, transcript_text, search_summary FROM recordings"""
        )

    # Add search_traces table if missing
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='search_traces'"
    )
    if not await cursor.fetchone():
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id TEXT NOT NULL,
                question TEXT NOT NULL,
                tier TEXT NOT NULL,
                step TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                reasoning_tokens INTEGER,
                duration_ms INTEGER,
                input_text TEXT,
                output_text TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_traces_search_id ON search_traces(search_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_traces_created ON search_traces(created_at DESC)"
        )

    # Add api_key column to users if missing
    cursor = await db.execute("PRAGMA table_info(users)")
    user_columns = {row[1] for row in await cursor.fetchall()}
    if "api_key" not in user_columns:
        try:
            await db.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
        except Exception:
            pass  # column already exists

    # Add mcp_tokens table if missing (for existing databases)
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='mcp_tokens'"
    )
    if not await cursor.fetchone():
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_tokens (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                token_name      TEXT NOT NULL,
                token_prefix    TEXT NOT NULL,
                token_hash      TEXT NOT NULL UNIQUE,
                raw_token       TEXT NOT NULL,
                scopes          TEXT,
                last_used_at    DATETIME,
                revoked_at      DATETIME,
                created_at      DATETIME DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS ix_mcp_tokens_user_id ON mcp_tokens (user_id)"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_mcp_tokens_token_hash ON mcp_tokens (token_hash)"
        )

    # Add meeting_notes columns if missing
    if "meeting_notes" not in columns:
        await db.execute("ALTER TABLE recordings ADD COLUMN meeting_notes TEXT")
    if "meeting_notes_generated_at" not in columns:
        await db.execute("ALTER TABLE recordings ADD COLUMN meeting_notes_generated_at TEXT")
    if "meeting_notes_tags" not in columns:
        await db.execute("ALTER TABLE recordings ADD COLUMN meeting_notes_tags TEXT")
    if "speaker_mapping_updated_at" not in columns:
        await db.execute("ALTER TABLE recordings ADD COLUMN speaker_mapping_updated_at TEXT")

    # Backfill null recorded_at with created_at for uploaded recordings
    await db.execute(
        "UPDATE recordings SET recorded_at = created_at WHERE recorded_at IS NULL"
    )

    await db.commit()


async def init_db() -> aiosqlite.Connection:
    """Initialize the database connection and create schema."""
    global _db
    settings = get_settings()

    # Ensure data directory exists
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(settings.db_path))
    _db.row_factory = aiosqlite.Row

    # Create schema
    await _db.executescript(SCHEMA_SQL)
    await _db.executescript(FTS_SCHEMA_SQL)
    await _db.commit()

    # Run migrations for existing databases
    await _migrate_schema(_db)

    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
