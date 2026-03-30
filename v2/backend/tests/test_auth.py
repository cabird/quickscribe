"""Tests for authentication and authorization.

Covers: dev bypass, missing header, invalid token, auto-provisioning.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_auth_disabled() -> Settings:
    return Settings(
        database_path=":memory:",
        auth_disabled=True,
    )


def _settings_auth_enabled() -> Settings:
    return Settings(
        database_path=":memory:",
        auth_disabled=False,
        azure_tenant_id="test-tenant",
        azure_client_id="test-client-id",
    )


# ---------------------------------------------------------------------------
# Dev bypass mode
# ---------------------------------------------------------------------------


class TestDevBypass:
    async def test_dev_bypass_returns_user(
        self, client: httpx.AsyncClient
    ):
        """With AUTH_DISABLED=true, requests should succeed without a token."""
        resp = await client.get("/api/recordings")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth enabled — error cases
# ---------------------------------------------------------------------------


class TestAuthRequired:
    """Tests with auth enabled (no dev bypass)."""

    async def test_missing_auth_header(self, test_db):
        """Request without Authorization header should return 401."""
        from app.main import app
        from app.auth import get_current_user  # noqa: F811

        # Remove any auth override so real auth runs
        app.dependency_overrides.pop(get_current_user, None)

        async def _override_get_db():
            return test_db

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_settings] = _settings_auth_enabled

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/recordings")
            assert resp.status_code == 401

        app.dependency_overrides.clear()

    async def test_invalid_token_format(self, test_db):
        """A garbage Bearer token should return 401."""
        from app.main import app
        from app.auth import get_current_user  # noqa: F811

        app.dependency_overrides.pop(get_current_user, None)

        async def _override_get_db():
            return test_db

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_settings] = _settings_auth_enabled

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/recordings",
                headers={"Authorization": "Bearer not.a.valid.jwt.token"},
            )
            assert resp.status_code == 401

        app.dependency_overrides.clear()

    async def test_no_bearer_prefix(self, test_db):
        """Authorization header without 'Bearer ' prefix should return 401."""
        from app.main import app
        from app.auth import get_current_user  # noqa: F811

        app.dependency_overrides.pop(get_current_user, None)

        async def _override_get_db():
            return test_db

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_settings] = _settings_auth_enabled

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/recordings",
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )
            assert resp.status_code == 401

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auto-provisioning
# ---------------------------------------------------------------------------


class TestAutoProvisioning:
    async def test_auto_provision_creates_user(self, test_db):
        """A valid token for an unknown user should auto-provision them."""
        from app.auth import _get_or_create_user

        # Temporarily set the global _db for the function
        import app.database as db_mod

        original_db = db_mod._db
        db_mod._db = test_db

        try:
            user = await _get_or_create_user(
                azure_oid="new-oid-9999",
                email="newuser@example.com",
                name="New User",
            )
            assert user.id.startswith("user-")
            assert user.email == "newuser@example.com"
            assert user.name == "New User"

            # Calling again should return the same user
            user2 = await _get_or_create_user(
                azure_oid="new-oid-9999",
                email="newuser@example.com",
                name="New User",
            )
            assert user2.id == user.id
        finally:
            db_mod._db = original_db

    async def test_auto_provision_matches_by_email(self, test_db):
        """If a user with matching email exists but no azure_oid, link them."""
        import app.database as db_mod
        import uuid

        original_db = db_mod._db
        db_mod._db = test_db

        try:
            # Pre-create a user without azure_oid
            user_id = f"user-{uuid.uuid4()}"
            await test_db.execute(
                """INSERT INTO users (id, name, email, created_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (user_id, "Existing", "existing@example.com"),
            )
            await test_db.commit()

            from app.auth import _get_or_create_user

            user = await _get_or_create_user(
                azure_oid="linking-oid",
                email="existing@example.com",
                name="Existing",
            )
            assert user.id == user_id
            assert user.azure_oid == "linking-oid"
        finally:
            db_mod._db = original_db
