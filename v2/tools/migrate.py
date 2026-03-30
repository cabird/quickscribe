# /// script
# dependencies = [
#     "azure-cosmos>=4.7.0",
#     "azure-storage-blob>=12.23.0",
#     "rich>=13.0.0",
#     "pydantic>=2.9.0",
#     "python-dotenv>=1.0.0",
# ]
# requires-python = ">=3.11"
# ///
"""Migrate QuickScribe v1 (CosmosDB + Azure Blob) → v2 (SQLite + local/Azure Blob).

Usage:
    uv run tools/migrate.py                          # Full migration
    uv run tools/migrate.py --dry-run                # Report only, no writes
    uv run tools/migrate.py --skip-blobs             # DB only, skip blob download
    uv run tools/migrate.py --verify-only            # Check existing migration

Environment variables (set in .env or export):
    # Old system (read-only)
    OLD_COSMOS_ENDPOINT=https://xxx.documents.azure.com:443/
    OLD_COSMOS_KEY=xxx
    OLD_COSMOS_DATABASE=quickscribe
    OLD_COSMOS_CONTAINER=recordings

    OLD_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=xxx;...
    OLD_BLOB_CONTAINER=audio-files

    # New system (write)
    NEW_SQLITE_PATH=./data/app.db
    NEW_BLOB_PATH=./blobs              # Local blob directory (for dev)
    # OR for Azure:
    # NEW_BLOB_CONNECTION_STRING=...
    # NEW_BLOB_CONTAINER=audio-files
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from rich.console import Console
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich.table import Table

    console = Console()
except ImportError:
    console = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class MigrateConfig:
    # Old system
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "quickscribe"
    cosmos_container: str = "recordings"
    old_blob_connection_string: str = ""
    old_blob_container: str = "audio-files"

    # New system
    sqlite_path: str = "./data/app.db"
    new_blob_path: str = "./blobs"  # local blob dir
    new_blob_connection_string: str = ""  # Azure (optional)
    new_blob_container: str = "audio-files"

    # Flags
    dry_run: bool = False
    skip_blobs: bool = False
    verify_only: bool = False
    verbose: bool = False

    @classmethod
    def from_env(cls, args: argparse.Namespace) -> "MigrateConfig":
        return cls(
            cosmos_endpoint=os.getenv("OLD_COSMOS_ENDPOINT", ""),
            cosmos_key=os.getenv("OLD_COSMOS_KEY", ""),
            cosmos_database=os.getenv("OLD_COSMOS_DATABASE", "quickscribe"),
            cosmos_container=os.getenv("OLD_COSMOS_CONTAINER", "recordings"),
            old_blob_connection_string=os.getenv("OLD_BLOB_CONNECTION_STRING", ""),
            old_blob_container=os.getenv("OLD_BLOB_CONTAINER", "audio-files"),
            sqlite_path=os.getenv("NEW_SQLITE_PATH", "./data/app.db"),
            new_blob_path=os.getenv("NEW_BLOB_PATH", "./blobs"),
            new_blob_connection_string=os.getenv("NEW_BLOB_CONNECTION_STRING", ""),
            new_blob_container=os.getenv("NEW_BLOB_CONTAINER", "audio-files"),
            dry_run=args.dry_run,
            skip_blobs=args.skip_blobs,
            verify_only=args.verify_only,
            verbose=args.verbose,
        )


@dataclass
class MigrateStats:
    users: int = 0
    users_failed: int = 0
    recordings: int = 0
    recordings_failed: int = 0
    participants: int = 0
    participants_failed: int = 0
    tags: int = 0
    tags_failed: int = 0
    recording_tags: int = 0
    deleted_ids: int = 0
    job_executions: int = 0
    job_executions_failed: int = 0
    analysis_types: int = 0
    analysis_types_failed: int = 0
    blobs_copied: int = 0
    blobs_skipped: int = 0
    blobs_failed: int = 0
    blob_bytes: int = 0
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# CosmosDB reader
# ---------------------------------------------------------------------------


def read_cosmos_documents(config: MigrateConfig) -> dict[str, list[dict]]:
    """Read all documents from CosmosDB, grouped by partition key type."""
    from azure.cosmos import CosmosClient

    log("Connecting to CosmosDB...")
    client = CosmosClient(config.cosmos_endpoint, config.cosmos_key)
    database = client.get_database_client(config.cosmos_database)
    container = database.get_container_client(config.cosmos_container)

    log("Querying all documents...")
    docs = list(container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True,
    ))
    log(f"  Found {len(docs)} total documents")

    # Group by partition key / type
    grouped: dict[str, list[dict]] = {
        "user": [],
        "recording": [],
        "transcription": [],
        "participant": [],
        "deleted_items": [],
        "job_execution": [],
        "analysis_type": [],
        "manual_review": [],
        "locks": [],
        "other": [],
    }

    for doc in docs:
        pk = doc.get("partitionKey", "")
        doc_type = doc.get("type", "")
        # Some containers use userId as partition key; check both fields
        doc_id = doc.get("id", "")

        if doc_type == "user" or pk == "user":
            grouped["user"].append(doc)
        elif doc_type == "recording" or pk == "recording":
            grouped["recording"].append(doc)
        elif doc_type == "transcription" or pk == "transcription":
            grouped["transcription"].append(doc)
        elif doc_type == "participant" or pk == "participant":
            grouped["participant"].append(doc)
        elif doc_type == "deleted_items" or pk == "deleted_items":
            grouped["deleted_items"].append(doc)
        elif doc_type == "job_execution" or pk == "job_execution":
            grouped["job_execution"].append(doc)
        elif doc_type == "analysis_type" or pk == "analysis_type":
            grouped["analysis_type"].append(doc)
        elif doc_type == "manual_review" or pk == "manual_review":
            grouped["manual_review"].append(doc)
        elif doc_type == "lock" or pk == "lock":
            grouped["locks"].append(doc)
        else:
            grouped["other"].append(doc)

    for key, items in grouped.items():
        if items:
            log(f"  {key}: {len(items)} documents")

    return grouped


# ---------------------------------------------------------------------------
# SQLite writer
# ---------------------------------------------------------------------------


def init_sqlite(config: MigrateConfig) -> sqlite3.Connection:
    """Initialize SQLite database with v2 schema."""
    db_path = Path(config.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Read and execute the schema from database.py
    schema_path = Path(__file__).parent.parent / "v2" / "backend" / "src" / "app" / "database.py"
    if not schema_path.exists():
        # Try relative to this script
        schema_path = Path(__file__).parent.parent / "backend" / "src" / "app" / "database.py"

    if schema_path.exists():
        log(f"Reading schema from {schema_path}")
        content = schema_path.read_text()
        # Extract SCHEMA_SQL
        start = content.find('SCHEMA_SQL = """') + len('SCHEMA_SQL = """')
        end = content.find('"""', start)
        schema_sql = content[start:end]
        conn.executescript(schema_sql)

        # Extract FTS_SCHEMA_SQL
        fts_start = content.find('FTS_SCHEMA_SQL = """') + len('FTS_SCHEMA_SQL = """')
        fts_end = content.find('"""', fts_start)
        fts_sql = content[fts_start:fts_end]
        conn.executescript(fts_sql)
    else:
        log("WARNING: Could not find database.py for schema. Using inline schema.")
        _create_schema_inline(conn)

    conn.commit()
    return conn


def _create_schema_inline(conn: sqlite3.Connection):
    """Fallback inline schema creation."""
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA busy_timeout=5000;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT, email TEXT, role TEXT DEFAULT 'user',
            azure_oid TEXT UNIQUE, plaud_enabled INTEGER DEFAULT 0, plaud_token TEXT,
            plaud_last_sync TEXT, settings_json TEXT,
            created_at TEXT DEFAULT (datetime('now')), last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS recordings (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            title TEXT, description TEXT, original_filename TEXT NOT NULL,
            file_path TEXT, duration_seconds REAL, recorded_at TEXT, source TEXT NOT NULL,
            plaud_id TEXT UNIQUE, plaud_metadata_json TEXT,
            status TEXT NOT NULL DEFAULT 'ready', status_message TEXT,
            provider_job_id TEXT, processing_started TEXT, processing_completed TEXT,
            retry_count INTEGER DEFAULT 0,
            transcript_text TEXT, diarized_text TEXT, transcript_json TEXT,
            token_count INTEGER, speaker_mapping TEXT,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            display_name TEXT NOT NULL, first_name TEXT, last_name TEXT,
            aliases TEXT, email TEXT, role TEXT, organization TEXT,
            relationship TEXT, notes TEXT, is_user INTEGER DEFAULT 0,
            first_seen TEXT, last_seen TEXT,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL, color TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')), UNIQUE(user_id, name)
        );
        CREATE TABLE IF NOT EXISTS recording_tags (
            recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
            tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (recording_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS deleted_plaud_ids (
            user_id TEXT NOT NULL REFERENCES users(id),
            plaud_id TEXT NOT NULL, deleted_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, plaud_id)
        );
        CREATE TABLE IF NOT EXISTS sync_runs (
            id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
            status TEXT NOT NULL, trigger TEXT NOT NULL, stats_json TEXT,
            error_message TEXT, logs_json TEXT, users_processed TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS speaker_profiles (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            participant_id TEXT NOT NULL REFERENCES participants(id),
            display_name TEXT NOT NULL, centroid BLOB, n_samples INTEGER DEFAULT 0,
            embeddings_json TEXT, recording_ids TEXT, embedding_std REAL,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, participant_id)
        );
        CREATE TABLE IF NOT EXISTS analysis_templates (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL, prompt TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
            title, description, diarized_text, transcript_text,
            content='recordings',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
            INSERT INTO recordings_fts(rowid, title, description, diarized_text, transcript_text)
            VALUES (new.rowid, new.title, new.description, new.diarized_text, new.transcript_text);
        END;

        CREATE TRIGGER IF NOT EXISTS recordings_ad AFTER DELETE ON recordings BEGIN
            INSERT INTO recordings_fts(recordings_fts, rowid, title, description, diarized_text, transcript_text)
            VALUES ('delete', old.rowid, old.title, old.description, old.diarized_text, old.transcript_text);
        END;

        CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
            INSERT INTO recordings_fts(recordings_fts, rowid, title, description, diarized_text, transcript_text)
            VALUES ('delete', old.rowid, old.title, old.description, old.diarized_text, old.transcript_text);
            INSERT INTO recordings_fts(rowid, title, description, diarized_text, transcript_text)
            VALUES (new.rowid, new.title, new.description, new.diarized_text, new.transcript_text);
        END;
    """)


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------


def migrate_users(docs: list[dict], conn: sqlite3.Connection, stats: MigrateStats, dry_run: bool):
    """Migrate User documents."""
    log(f"\nMigrating {len(docs)} users...")

    for doc in docs:
        try:
            user_id = doc["id"]
            plaud_settings = doc.get("plaudSettings") or {}

            if dry_run:
                log(f"  [dry-run] Would migrate user: {user_id} ({doc.get('name')})")
                stats.users += 1
                continue

            conn.execute(
                """INSERT INTO users
                   (id, name, email, role, azure_oid, plaud_enabled, plaud_token,
                    plaud_last_sync, created_at, last_login)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, email=excluded.email, role=excluded.role,
                    azure_oid=excluded.azure_oid, plaud_enabled=excluded.plaud_enabled,
                    plaud_token=excluded.plaud_token, plaud_last_sync=excluded.plaud_last_sync,
                    last_login=excluded.last_login""",
                (
                    user_id,
                    doc.get("name"),
                    doc.get("email"),
                    doc.get("role", "user"),
                    doc.get("azure_oid"),
                    1 if plaud_settings.get("enableSync") else 0,
                    plaud_settings.get("bearerToken"),
                    plaud_settings.get("lastSyncTimestamp"),
                    doc.get("created_at"),
                    doc.get("last_login"),
                ),
            )

            # Migrate tags (embedded in User)
            for tag in doc.get("tags") or []:
                try:
                    conn.execute(
                        """INSERT INTO tags (id, user_id, name, color) VALUES (?, ?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET name=excluded.name, color=excluded.color""",
                        (tag["id"], user_id, tag["name"], tag["color"]),
                    )
                    stats.tags += 1
                except Exception as e:
                    stats.tags_failed += 1
                    stats.errors.append(f"Tag {tag.get('id')}: {e}")

            stats.users += 1

        except Exception as e:
            stats.users_failed += 1
            stats.errors.append(f"User {doc.get('id')}: {e}")
            log(f"  ERROR migrating user {doc.get('id')}: {e}")


def migrate_recordings(
    recordings: list[dict],
    transcriptions: list[dict],
    conn: sqlite3.Connection,
    stats: MigrateStats,
    dry_run: bool,
):
    """Migrate Recording + Transcription documents (merged into one table)."""
    # Build transcription lookup by recording_id
    tx_by_recording: dict[str, dict] = {}
    tx_by_id: dict[str, dict] = {}
    for tx in transcriptions:
        rid = tx.get("recording_id")
        if rid:
            tx_by_recording[rid] = tx
        tx_by_id[tx["id"]] = tx

    log(f"\nMigrating {len(recordings)} recordings (merging with {len(transcriptions)} transcriptions)...")

    for rec in recordings:
        try:
            rec_id = rec["id"]
            user_id = rec.get("user_id", "")

            # Find linked transcription
            tx = tx_by_recording.get(rec_id) or tx_by_id.get(rec.get("transcription_id", ""))

            # Determine file path (normalize from v1 patterns)
            file_path = _resolve_file_path(rec, user_id)

            # Plaud metadata
            plaud_meta = rec.get("plaudMetadata")
            plaud_id = plaud_meta.get("plaudId") if plaud_meta else None

            # Speaker mapping from transcription
            speaker_mapping = None
            if tx and tx.get("speaker_mapping"):
                sm = tx["speaker_mapping"]
                # Strip embeddings to reduce size (they're huge and stored elsewhere)
                # Actually spec says keep them — so keep
                speaker_mapping = json.dumps(sm) if isinstance(sm, dict) else sm

            # Serialize transcript_json if it's a dict/list (CosmosDB stores JSON natively)
            transcript_json_val = tx.get("transcript_json") if tx else None
            if isinstance(transcript_json_val, (dict, list)):
                transcript_json_val = json.dumps(transcript_json_val)

            # Map status, but override to "pending" if no transcript data exists
            status = _map_status(rec, has_transcript=bool(tx and (tx.get("text") or tx.get("diarized_transcript"))))

            if dry_run:
                log(f"  [dry-run] Would migrate recording: {rec_id} ({rec.get('title') or rec.get('original_filename')})")
                stats.recordings += 1
                continue

            conn.execute(
                """INSERT INTO recordings
                   (id, user_id, title, description, original_filename, file_path,
                    duration_seconds, recorded_at, source,
                    plaud_id, plaud_metadata_json,
                    status, status_message, provider_job_id,
                    processing_started, processing_completed, retry_count,
                    transcript_text, diarized_text, transcript_json,
                    token_count, speaker_mapping,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id, title=excluded.title,
                    description=excluded.description, original_filename=excluded.original_filename,
                    file_path=excluded.file_path, duration_seconds=excluded.duration_seconds,
                    recorded_at=excluded.recorded_at, source=excluded.source,
                    plaud_id=excluded.plaud_id, plaud_metadata_json=excluded.plaud_metadata_json,
                    status=excluded.status, status_message=excluded.status_message,
                    provider_job_id=excluded.provider_job_id,
                    processing_started=excluded.processing_started,
                    processing_completed=excluded.processing_completed,
                    retry_count=excluded.retry_count,
                    transcript_text=excluded.transcript_text, diarized_text=excluded.diarized_text,
                    transcript_json=excluded.transcript_json, token_count=excluded.token_count,
                    speaker_mapping=excluded.speaker_mapping, updated_at=excluded.updated_at""",
                (
                    rec_id,
                    user_id,
                    rec.get("title"),
                    rec.get("description"),
                    rec.get("original_filename", "unknown"),
                    file_path,
                    rec.get("duration"),
                    rec.get("recorded_timestamp"),
                    rec.get("source", "plaud"),
                    plaud_id,
                    json.dumps(plaud_meta) if plaud_meta else None,
                    status,
                    rec.get("transcription_error_message") or rec.get("last_failure_message"),
                    rec.get("transcription_job_id") or rec.get("az_transcription_id"),
                    None,  # processing_started
                    None,  # processing_completed
                    rec.get("processing_failure_count", 0),
                    tx.get("text") if tx else None,
                    tx.get("diarized_transcript") if tx else None,
                    transcript_json_val,
                    tx.get("token_count") or rec.get("token_count"),
                    speaker_mapping,
                    rec.get("upload_timestamp") or rec.get("created_at"),
                    rec.get("updated_at") or rec.get("upload_timestamp"),
                ),
            )

            # Migrate recording-tag associations
            for tag_id in rec.get("tagIds") or []:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO recording_tags (recording_id, tag_id) VALUES (?, ?)",
                        (rec_id, tag_id),
                    )
                    stats.recording_tags += 1
                except Exception:
                    pass

            stats.recordings += 1

        except Exception as e:
            stats.recordings_failed += 1
            stats.errors.append(f"Recording {rec.get('id')}: {e}")
            log(f"  ERROR migrating recording {rec.get('id')}: {e}")


def migrate_participants(docs: list[dict], conn: sqlite3.Connection, stats: MigrateStats, dry_run: bool):
    """Migrate Participant documents."""
    log(f"\nMigrating {len(docs)} participants...")

    for doc in docs:
        try:
            if dry_run:
                log(f"  [dry-run] Would migrate participant: {doc['id']} ({doc.get('displayName')})")
                stats.participants += 1
                continue

            aliases = doc.get("aliases", [])
            conn.execute(
                """INSERT INTO participants
                   (id, user_id, display_name, first_name, last_name, aliases,
                    email, role, organization, relationship, notes, is_user,
                    first_seen, last_seen, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    display_name=excluded.display_name, first_name=excluded.first_name,
                    last_name=excluded.last_name, aliases=excluded.aliases,
                    email=excluded.email, role=excluded.role, organization=excluded.organization,
                    relationship=excluded.relationship, notes=excluded.notes,
                    is_user=excluded.is_user, first_seen=excluded.first_seen,
                    last_seen=excluded.last_seen, updated_at=excluded.updated_at""",
                (
                    doc["id"],
                    doc.get("userId", ""),
                    doc.get("displayName", "Unknown"),
                    doc.get("firstName"),
                    doc.get("lastName"),
                    json.dumps(aliases) if aliases else None,
                    doc.get("email"),
                    doc.get("role"),
                    doc.get("organization"),
                    doc.get("relationshipToUser"),
                    doc.get("notes"),
                    1 if doc.get("isUser") else 0,
                    doc.get("firstSeen"),
                    doc.get("lastSeen"),
                    doc.get("createdAt"),
                    doc.get("updatedAt"),
                ),
            )
            stats.participants += 1

        except Exception as e:
            stats.participants_failed += 1
            stats.errors.append(f"Participant {doc.get('id')}: {e}")
            log(f"  ERROR migrating participant {doc.get('id')}: {e}")


def migrate_deleted_items(docs: list[dict], conn: sqlite3.Connection, stats: MigrateStats, dry_run: bool):
    """Migrate DeletedItems documents."""
    log(f"\nMigrating deleted item blocklists...")

    for doc in docs:
        user_id = doc.get("userId", "")
        items = doc.get("items", {})
        plaud_ids = items.get("plaud_recording", [])

        for pid in plaud_ids:
            try:
                if dry_run:
                    log(f"  [dry-run] Would add deleted plaud ID: {pid} for user {user_id}")
                else:
                    conn.execute(
                        "INSERT OR IGNORE INTO deleted_plaud_ids (user_id, plaud_id) VALUES (?, ?)",
                        (user_id, pid),
                    )
                stats.deleted_ids += 1
            except Exception as e:
                stats.errors.append(f"DeletedPlaudId {pid}: {e}")


def migrate_job_executions(docs: list[dict], conn: sqlite3.Connection, stats: MigrateStats, dry_run: bool):
    """Migrate JobExecution documents → sync_runs table."""
    log(f"\nMigrating {len(docs)} job executions → sync_runs...")

    for doc in docs:
        try:
            job_id = doc.get("id", str(uuid.uuid4()))

            if dry_run:
                log(f"  [dry-run] Would migrate job execution: {job_id}")
                stats.job_executions += 1
                continue

            # Map v1 job_execution fields to v2 sync_runs
            stats_data = doc.get("stats") or doc.get("results")
            logs_data = doc.get("logs") or doc.get("log_entries")

            conn.execute(
                """INSERT INTO sync_runs
                   (id, started_at, finished_at, status, trigger, stats_json,
                    error_message, logs_json, users_processed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    finished_at=excluded.finished_at, status=excluded.status,
                    stats_json=excluded.stats_json, error_message=excluded.error_message,
                    logs_json=excluded.logs_json, users_processed=excluded.users_processed""",
                (
                    job_id,
                    doc.get("started_at") or doc.get("startTime") or doc.get("created_at"),
                    doc.get("finished_at") or doc.get("endTime"),
                    doc.get("status", "completed"),
                    doc.get("trigger", "scheduled"),
                    json.dumps(stats_data) if isinstance(stats_data, (dict, list)) else stats_data,
                    doc.get("error_message") or doc.get("error"),
                    json.dumps(logs_data) if isinstance(logs_data, (dict, list)) else logs_data,
                    json.dumps(doc.get("users_processed")) if isinstance(doc.get("users_processed"), list) else doc.get("users_processed"),
                    doc.get("created_at") or doc.get("started_at") or doc.get("startTime"),
                ),
            )
            stats.job_executions += 1

        except Exception as e:
            stats.job_executions_failed += 1
            stats.errors.append(f"JobExecution {doc.get('id')}: {e}")
            log(f"  ERROR migrating job execution {doc.get('id')}: {e}")


def migrate_analysis_types(docs: list[dict], conn: sqlite3.Connection, stats: MigrateStats, dry_run: bool):
    """Migrate AnalysisType documents → analysis_templates table."""
    log(f"\nMigrating {len(docs)} analysis types → analysis_templates...")

    for doc in docs:
        try:
            doc_id = doc.get("id", str(uuid.uuid4()))
            user_id = doc.get("userId") or doc.get("user_id", "")

            # Skip built-in/global types that have no user_id
            if not user_id:
                log(f"  SKIP (no user_id, likely built-in): {doc.get('name', doc_id)}")
                continue

            if dry_run:
                log(f"  [dry-run] Would migrate analysis type: {doc_id} ({doc.get('name')})")
                stats.analysis_types += 1
                continue

            conn.execute(
                """INSERT INTO analysis_templates
                   (id, user_id, name, prompt, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, prompt=excluded.prompt, updated_at=excluded.updated_at""",
                (
                    doc_id,
                    user_id,
                    doc.get("name", "Untitled"),
                    doc.get("prompt") or doc.get("systemPrompt", ""),
                    doc.get("createdAt") or doc.get("created_at"),
                    doc.get("updatedAt") or doc.get("updated_at"),
                ),
            )
            stats.analysis_types += 1

        except Exception as e:
            stats.analysis_types_failed += 1
            stats.errors.append(f"AnalysisType {doc.get('id')}: {e}")
            log(f"  ERROR migrating analysis type {doc.get('id')}: {e}")


def migrate_blobs(
    recordings: list[dict],
    config: MigrateConfig,
    stats: MigrateStats,
):
    """Download audio blobs from old Azure Blob Storage to local directory."""
    from azure.storage.blob import BlobServiceClient

    blob_dir = Path(config.new_blob_path)
    blob_dir.mkdir(parents=True, exist_ok=True)

    log(f"\nDownloading blobs to {blob_dir}...")

    client = BlobServiceClient.from_connection_string(config.old_blob_connection_string)
    container = client.get_container_client(config.old_blob_container)

    for rec in recordings:
        user_id = rec.get("user_id", "")
        rec_id = rec["id"]
        file_path = _resolve_file_path(rec, user_id)

        if not file_path:
            stats.blobs_skipped += 1
            continue

        # Determine local destination
        local_dest = blob_dir / file_path
        if local_dest.exists():
            stats.blobs_skipped += 1
            if config.verbose:
                log(f"  SKIP (exists): {file_path}")
            continue

        # Try to find the blob in old storage
        old_blob_name = _find_old_blob_name(rec)
        if not old_blob_name:
            stats.blobs_skipped += 1
            if config.verbose:
                log(f"  SKIP (no blob name): {rec_id}")
            continue

        try:
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            blob = container.get_blob_client(old_blob_name)

            with open(local_dest, "wb") as f:
                stream = blob.download_blob()
                stream.readinto(f)

            size = local_dest.stat().st_size
            stats.blobs_copied += 1
            stats.blob_bytes += size
            if config.verbose:
                log(f"  OK: {old_blob_name} -> {file_path} ({size / 1024 / 1024:.1f} MB)")

        except Exception as e:
            stats.blobs_failed += 1
            stats.errors.append(f"Blob {old_blob_name}: {e}")
            if config.verbose:
                log(f"  FAIL: {old_blob_name}: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_file_path(rec: dict, user_id: str) -> str | None:
    """Normalize v1 blob paths to v2 format: {user_id}/{recording_id}.mp3"""
    rec_id = rec["id"]

    # Check if there's any blob reference
    blob_name = rec.get("blob_name") or rec.get("unique_filename")
    if not blob_name and not rec.get("file_path"):
        return None

    # Standardize to v2 format
    ext = ".mp3"
    if blob_name:
        p = Path(blob_name)
        if p.suffix:
            ext = p.suffix

    return f"{user_id}/{rec_id}{ext}"


def _find_old_blob_name(rec: dict) -> str | None:
    """Find the actual blob name in the old storage from v1 recording data."""
    # Try blob_name first (may include path)
    blob_name = rec.get("blob_name")
    if blob_name:
        return blob_name

    # Try unique_filename — may or may not include user_id prefix
    unique = rec.get("unique_filename")
    if unique:
        if "/" in unique:
            return unique
        # Construct full path: user_id/unique_filename
        user_id = rec.get("user_id") or rec.get("userId", "")
        if user_id:
            return f"{user_id}/{unique}"
        return unique

    # Try file_path as last resort
    file_path = rec.get("file_path")
    if file_path:
        return file_path

    return None


def _map_status(rec: dict, has_transcript: bool = False) -> str:
    """Map v1 multi-field status to v2 single status."""
    ts = rec.get("transcription_status", "")
    tcs = rec.get("transcoding_status", "")

    if ts == "completed":
        return "ready"
    elif ts == "failed" or tcs == "failed":
        return "failed"
    elif ts == "in_progress" or rec.get("transcription_job_status") in ("submitted", "processing"):
        return "transcribing"
    elif tcs == "in_progress" or tcs == "queued":
        return "transcoding"
    elif has_transcript:
        # No explicit status but transcript data exists — treat as ready
        return "ready"
    else:
        return "pending"  # Default to pending for unknown/unprocessed recordings


def _strip_cosmos_fields(doc: dict) -> dict:
    """Remove CosmosDB system fields."""
    cosmos_fields = {"_rid", "_self", "_etag", "_ts", "_attachments", "_lsn"}
    return {k: v for k, v in doc.items() if k not in cosmos_fields}


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_migration(config: MigrateConfig):
    """Verify migration completeness."""
    log("\nVerifying migration...")

    db_path = Path(config.sqlite_path)
    if not db_path.exists():
        log("ERROR: SQLite database not found at " + str(db_path))
        return

    conn = sqlite3.connect(str(db_path))

    counts = {}
    for table in ["users", "recordings", "participants", "tags", "recording_tags", "deleted_plaud_ids", "sync_runs", "analysis_templates"]:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = row[0]

    log("\nMigrated data counts:")
    for table, count in counts.items():
        log(f"  {table}: {count}")

    # Check for recordings with missing transcripts
    row = conn.execute(
        "SELECT COUNT(*) FROM recordings WHERE status = 'ready' AND diarized_text IS NULL AND transcript_text IS NULL"
    ).fetchone()
    if row[0] > 0:
        log(f"\n  WARNING: {row[0]} 'ready' recordings have no transcript text")

    # Check blob directory
    blob_dir = Path(config.new_blob_path)
    if blob_dir.exists():
        blob_count = sum(1 for _ in blob_dir.rglob("*.mp3"))
        log(f"\n  Local blobs: {blob_count} .mp3 files")

        # Check for recordings with file_path but no local blob
        rows = conn.execute("SELECT id, file_path FROM recordings WHERE file_path IS NOT NULL").fetchall()
        missing = 0
        for row in rows:
            local = blob_dir / row[1]
            if not local.exists():
                missing += 1
        if missing:
            log(f"  WARNING: {missing} recordings reference blobs that don't exist locally")
        else:
            log(f"  All {len(rows)} recording blobs present locally")

    conn.close()
    log("\nVerification complete.")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log(msg: str):
    if console:
        console.print(msg)
    else:
        print(msg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Migrate QuickScribe v1 → v2")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--skip-blobs", action="store_true", help="DB only, skip blob download")
    parser.add_argument("--verify-only", action="store_true", help="Check existing migration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-record progress")
    args = parser.parse_args()

    config = MigrateConfig.from_env(args)

    if config.verify_only:
        verify_migration(config)
        return

    # Validate config
    if not config.cosmos_endpoint or not config.cosmos_key:
        log("ERROR: OLD_COSMOS_ENDPOINT and OLD_COSMOS_KEY must be set")
        sys.exit(1)

    log("=" * 60)
    log("QuickScribe v1 → v2 Migration")
    log("=" * 60)
    if config.dry_run:
        log("MODE: DRY RUN (no writes)")
    log(f"Source: CosmosDB at {config.cosmos_endpoint}")
    log(f"Target: SQLite at {config.sqlite_path}")
    if config.skip_blobs:
        log("Blobs: SKIPPED")
    else:
        log(f"Blobs: {config.new_blob_path}")
    log("")

    stats = MigrateStats()

    # Step 1: Read from CosmosDB
    grouped = read_cosmos_documents(config)

    # Step 2: Initialize SQLite
    if not config.dry_run:
        conn = init_sqlite(config)
    else:
        conn = sqlite3.connect(":memory:")
        _create_schema_inline(conn)

    # Step 3: Migrate entities
    migrate_users(grouped["user"], conn, stats, config.dry_run)
    migrate_recordings(
        grouped["recording"],
        grouped["transcription"],
        conn,
        stats,
        config.dry_run,
    )
    migrate_participants(grouped["participant"], conn, stats, config.dry_run)
    migrate_deleted_items(grouped["deleted_items"], conn, stats, config.dry_run)
    migrate_job_executions(grouped["job_execution"], conn, stats, config.dry_run)
    migrate_analysis_types(grouped["analysis_type"], conn, stats, config.dry_run)

    if not config.dry_run:
        conn.commit()
        log("\nDatabase committed.")

    # Step 4: Download blobs
    if not config.skip_blobs and not config.dry_run and config.old_blob_connection_string:
        migrate_blobs(grouped["recording"], config, stats)
    elif not config.skip_blobs and not config.old_blob_connection_string:
        log("\nSkipping blobs: OLD_BLOB_CONNECTION_STRING not set")

    # Step 5: Rebuild FTS index
    if not config.dry_run:
        log("\nRebuilding FTS index...")
        conn.execute("INSERT INTO recordings_fts(recordings_fts) VALUES('rebuild')")
        conn.commit()
        log("FTS index rebuilt.")

    conn.close()

    # Report
    log("\n" + "=" * 60)
    log("Migration Complete")
    log("=" * 60)

    if console:
        table = Table(title="Results")
        table.add_column("Entity", style="bold")
        table.add_column("Migrated", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_row("Users", str(stats.users), str(stats.users_failed))
        table.add_row("Recordings", str(stats.recordings), str(stats.recordings_failed))
        table.add_row("Participants", str(stats.participants), str(stats.participants_failed))
        table.add_row("Tags", str(stats.tags), str(stats.tags_failed))
        table.add_row("Recording-Tags", str(stats.recording_tags), "")
        table.add_row("Deleted IDs", str(stats.deleted_ids), "")
        table.add_row("Sync Runs", str(stats.job_executions), str(stats.job_executions_failed))
        table.add_row("Analysis Templates", str(stats.analysis_types), str(stats.analysis_types_failed))
        if not config.skip_blobs:
            blob_size = f"{stats.blob_bytes / 1024 / 1024 / 1024:.1f} GB" if stats.blob_bytes > 0 else "0"
            table.add_row(
                "Blobs",
                f"{stats.blobs_copied} ({blob_size})",
                f"{stats.blobs_failed} failed, {stats.blobs_skipped} skipped",
            )
        console.print(table)
    else:
        log(f"  Users:        {stats.users} migrated, {stats.users_failed} failed")
        log(f"  Recordings:   {stats.recordings} migrated, {stats.recordings_failed} failed")
        log(f"  Participants: {stats.participants} migrated, {stats.participants_failed} failed")
        log(f"  Tags:         {stats.tags} migrated, {stats.tags_failed} failed")
        log(f"  Rec-Tags:     {stats.recording_tags}")
        log(f"  Deleted IDs:  {stats.deleted_ids}")
        log(f"  Sync Runs:    {stats.job_executions} migrated, {stats.job_executions_failed} failed")
        log(f"  Templates:    {stats.analysis_types} migrated, {stats.analysis_types_failed} failed")
        if not config.skip_blobs:
            log(f"  Blobs:        {stats.blobs_copied} copied, {stats.blobs_skipped} skipped, {stats.blobs_failed} failed")

    if stats.errors:
        log(f"\n{len(stats.errors)} errors encountered:")
        for err in stats.errors[:20]:
            log(f"  - {err}")
        if len(stats.errors) > 20:
            log(f"  ... and {len(stats.errors) - 20} more")

    # Run verification
    if not config.dry_run:
        verify_migration(config)


if __name__ == "__main__":
    main()
