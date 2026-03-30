"""Shared test fixtures for QuickScribe v2 backend tests.

Provides an in-memory SQLite database, authenticated test client,
and sample data fixtures.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite
import httpx
import pytest

from app.config import Settings, get_settings
from app.database import SCHEMA_SQL, FTS_SCHEMA_SQL, get_db
from app.models import (
    User,
    Recording,
    RecordingSource,
    RecordingStatus,
    Participant,
    Tag,
    SyncRun,
    SyncRunStatus,
    SyncTrigger,
)


# ---------------------------------------------------------------------------
# Settings override — disable auth, use in-memory DB
# ---------------------------------------------------------------------------


def _test_settings() -> Settings:
    return Settings(
        database_path=":memory:",
        auth_disabled=True,
        azure_storage_connection_string="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        speech_services_key="",
        speech_services_region="",
    )


# ---------------------------------------------------------------------------
# Database fixture — fresh in-memory SQLite per test
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_db():
    """Create a fresh in-memory SQLite database with schema applied."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA_SQL)
    await db.executescript(FTS_SCHEMA_SQL)
    await db.commit()
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# Test user fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_user(test_db: aiosqlite.Connection) -> User:
    """Insert and return a test user."""
    user_id = f"user-{uuid.uuid4()}"
    now = datetime.now(timezone.utc).isoformat()
    await test_db.execute(
        """INSERT INTO users (id, name, email, role, azure_oid, created_at, last_login)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, "Test User", "test@example.com", "user", "oid-test-1234", now, now),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall("SELECT * FROM users WHERE id = ?", (user_id,))
    return User(**dict(row[0]))


@pytest.fixture
async def other_user(test_db: aiosqlite.Connection) -> User:
    """Insert and return a second user for ownership tests."""
    user_id = f"user-{uuid.uuid4()}"
    now = datetime.now(timezone.utc).isoformat()
    await test_db.execute(
        """INSERT INTO users (id, name, email, role, azure_oid, created_at, last_login)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, "Other User", "other@example.com", "user", "oid-other-5678", now, now),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall("SELECT * FROM users WHERE id = ?", (user_id,))
    return User(**dict(row[0]))


# ---------------------------------------------------------------------------
# FastAPI test client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(
    test_db: aiosqlite.Connection,
    test_user: User,
):
    """Async HTTP test client with dependency overrides for DB and auth."""
    from app.main import app

    async def _override_get_db():
        return test_db

    async def _override_get_current_user():
        return test_user

    async def _override_get_settings():
        return _test_settings()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = _override_get_settings

    # Override auth — import here to avoid circular imports
    from app.auth import get_current_user

    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def client_as_other(
    test_db: aiosqlite.Connection,
    other_user: User,
):
    """Test client authenticated as the 'other' user for ownership tests."""
    from app.main import app
    from app.auth import get_current_user

    async def _override_get_db():
        return test_db

    async def _override_get_current_user():
        return other_user

    async def _override_get_settings():
        return _test_settings()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = _override_get_settings
    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sample_recording(
    test_db: aiosqlite.Connection, test_user: User
) -> Recording:
    """Insert and return a sample recording with transcript."""
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    speaker_mapping = json.dumps(
        {
            "Speaker 1": {
                "participant_id": None,
                "display_name": "Speaker 1",
                "confidence": None,
                "manually_verified": False,
                "identification_status": "unknown",
            }
        }
    )
    await test_db.execute(
        """INSERT INTO recordings
           (id, user_id, title, description, original_filename, source, status,
            transcript_text, diarized_text, speaker_mapping, token_count,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec_id,
            test_user.id,
            "Test Meeting",
            "A test meeting recording",
            "meeting.mp3",
            RecordingSource.upload.value,
            RecordingStatus.ready.value,
            "Hello, this is a test transcript.",
            "Speaker 1: Hello, this is a test transcript.",
            speaker_mapping,
            12,
            now,
            now,
        ),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall(
        "SELECT * FROM recordings WHERE id = ?", (rec_id,)
    )
    return Recording(**dict(row[0]))


@pytest.fixture
async def sample_plaud_recording(
    test_db: aiosqlite.Connection, test_user: User
) -> Recording:
    """Insert and return a sample recording with plaud source."""
    rec_id = str(uuid.uuid4())
    plaud_id = f"plaud-{uuid.uuid4()}"
    now = datetime.now(timezone.utc).isoformat()
    await test_db.execute(
        """INSERT INTO recordings
           (id, user_id, title, original_filename, source, status, plaud_id,
            transcript_text, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rec_id,
            test_user.id,
            "Plaud Recording",
            "plaud_rec.opus",
            RecordingSource.plaud.value,
            RecordingStatus.ready.value,
            plaud_id,
            "Plaud transcript content.",
            now,
            now,
        ),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall(
        "SELECT * FROM recordings WHERE id = ?", (rec_id,)
    )
    return Recording(**dict(row[0]))


@pytest.fixture
async def sample_participant(
    test_db: aiosqlite.Connection, test_user: User
) -> Participant:
    """Insert and return a sample participant."""
    part_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await test_db.execute(
        """INSERT INTO participants
           (id, user_id, display_name, first_name, last_name, email, organization,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            part_id,
            test_user.id,
            "Jane Doe",
            "Jane",
            "Doe",
            "jane@example.com",
            "Acme Corp",
            now,
            now,
        ),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall(
        "SELECT * FROM participants WHERE id = ?", (part_id,)
    )
    return Participant(**dict(row[0]))


@pytest.fixture
async def sample_tag(test_db: aiosqlite.Connection, test_user: User) -> Tag:
    """Insert and return a sample tag."""
    tag_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await test_db.execute(
        """INSERT INTO tags (id, user_id, name, color, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (tag_id, test_user.id, "important", "#ff0000", now),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall("SELECT * FROM tags WHERE id = ?", (tag_id,))
    return Tag(**dict(row[0]))


@pytest.fixture
async def sample_sync_run(test_db: aiosqlite.Connection) -> SyncRun:
    """Insert and return a sample sync run."""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    stats = json.dumps({"recordings_synced": 3, "errors": 0})
    await test_db.execute(
        """INSERT INTO sync_runs
           (id, started_at, finished_at, status, trigger, stats_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            now,
            now,
            SyncRunStatus.completed.value,
            SyncTrigger.manual.value,
            stats,
            now,
        ),
    )
    await test_db.commit()
    row = await test_db.execute_fetchall(
        "SELECT * FROM sync_runs WHERE id = ?", (run_id,)
    )
    return SyncRun(**dict(row[0]))
