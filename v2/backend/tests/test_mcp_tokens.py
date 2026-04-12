"""Tests for MCP token infrastructure (Phase A).

Covers: token service (create, list, revoke, validate), management
endpoints, and auth flow integration.
"""

from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite
import httpx
import pytest

import app.database as db_mod
from app.auth import get_current_user, get_current_user_or_api_key, _try_mcp_token
from app.config import Settings, get_settings
from app.database import get_db
from app.models import McpTokenResponse, User
from app.services import mcp_token_service
from app.services.mcp_token_service import TOKEN_PREFIX, hash_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_db(test_db: aiosqlite.Connection):
    """Context manager style: set the module-level _db so service functions work."""
    original = db_mod._db
    db_mod._db = test_db

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            db_mod._db = original

    return _Ctx()


# ---------------------------------------------------------------------------
# Token service tests (unit-level, using test_db directly)
# ---------------------------------------------------------------------------


class TestTokenService:
    """Service-layer tests for mcp_token_service functions."""

    async def test_create_token(self, test_db: aiosqlite.Connection, test_user: User):
        """Creates token, verifies qs_mcp_ prefix, hash stored correctly."""
        with _patch_db(test_db):
            result = await mcp_token_service.create_token(test_user.id, "My Token")

        assert isinstance(result, McpTokenResponse)
        assert result.raw_token.startswith(TOKEN_PREFIX)
        assert result.token_name == "My Token"
        # token_prefix is the first 6 chars after the prefix
        assert result.token_prefix == result.raw_token[len(TOKEN_PREFIX) : len(TOKEN_PREFIX) + 6]

        # Verify hash stored in DB matches
        rows = await test_db.execute_fetchall(
            "SELECT token_hash FROM mcp_tokens WHERE id = ?", (result.id,)
        )
        assert rows
        assert rows[0]["token_hash"] == hash_token(result.raw_token)

    async def test_create_token_max_limit(
        self, test_db: aiosqlite.Connection, test_user: User
    ):
        """Creating 11th token should raise HTTPException (max 10 active)."""
        with _patch_db(test_db):
            for i in range(10):
                await mcp_token_service.create_token(test_user.id, f"Token {i}")

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await mcp_token_service.create_token(test_user.id, "Token 10")

            assert exc_info.value.status_code == 400
            assert "Maximum" in exc_info.value.detail

    async def test_list_tokens(self, test_db: aiosqlite.Connection, test_user: User):
        """Creates multiple tokens, verifies list returns all with raw_token."""
        with _patch_db(test_db):
            t1 = await mcp_token_service.create_token(test_user.id, "First")
            t2 = await mcp_token_service.create_token(test_user.id, "Second")

            tokens = await mcp_token_service.list_tokens(test_user.id)

        assert len(tokens) == 2
        names = {t.token_name for t in tokens}
        assert names == {"First", "Second"}
        # raw_token should be visible
        for t in tokens:
            assert t.raw_token.startswith(TOKEN_PREFIX)

    async def test_revoke_token(self, test_db: aiosqlite.Connection, test_user: User):
        """Revoke then verify revoked_at is set."""
        with _patch_db(test_db):
            token = await mcp_token_service.create_token(test_user.id, "To Revoke")
            assert token.revoked_at is None

            await mcp_token_service.revoke_token(test_user.id, token.id)

        rows = await test_db.execute_fetchall(
            "SELECT revoked_at FROM mcp_tokens WHERE id = ?", (token.id,)
        )
        assert rows[0]["revoked_at"] is not None

    async def test_revoke_token_wrong_user(
        self, test_db: aiosqlite.Connection, test_user: User, other_user: User
    ):
        """Revoking another user's token should raise 404."""
        with _patch_db(test_db):
            token = await mcp_token_service.create_token(test_user.id, "Mine")

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await mcp_token_service.revoke_token(other_user.id, token.id)

            assert exc_info.value.status_code == 404

    async def test_validate_token(self, test_db: aiosqlite.Connection, test_user: User):
        """Create token, validate it, verify returns user_id."""
        with _patch_db(test_db):
            token = await mcp_token_service.create_token(test_user.id, "Valid")
            user_id = await mcp_token_service.validate_token(token.raw_token)

        assert user_id == test_user.id

    async def test_validate_revoked_token(
        self, test_db: aiosqlite.Connection, test_user: User
    ):
        """Revoke then validate should return None."""
        with _patch_db(test_db):
            token = await mcp_token_service.create_token(test_user.id, "Revokable")
            await mcp_token_service.revoke_token(test_user.id, token.id)

            result = await mcp_token_service.validate_token(token.raw_token)

        assert result is None



# ---------------------------------------------------------------------------
# Token management endpoint tests (using client fixture)
# ---------------------------------------------------------------------------


class TestTokenEndpoints:
    """HTTP endpoint tests for /api/settings/mcp-tokens."""

    @pytest.fixture
    async def mcp_client(
        self,
        test_db: aiosqlite.Connection,
        test_user: User,
    ):
        """Client with both get_current_user and get_current_user_or_api_key overridden."""
        from app.main import app

        async def _override_get_db():
            return test_db

        async def _override_get_current_user():
            return test_user

        async def _override_get_settings():
            return Settings(
                database_path=":memory:",
                auth_disabled=True,
                azure_storage_connection_string="",
                azure_openai_endpoint="",
                azure_openai_api_key="",
                speech_services_key="",
                speech_services_region="",
            )

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_settings] = _override_get_settings
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_current_user_or_api_key] = _override_get_current_user

        # Patch the module-level _db for service calls
        original_db = db_mod._db
        db_mod._db = test_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        db_mod._db = original_db
        app.dependency_overrides.clear()

    async def test_create_token_endpoint(self, mcp_client: httpx.AsyncClient):
        """POST /api/settings/mcp-tokens returns 200 and correct response shape."""
        resp = await mcp_client.post(
            "/api/settings/mcp-tokens", json={"name": "Test Token"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_name"] == "Test Token"
        assert body["raw_token"].startswith(TOKEN_PREFIX)
        assert "id" in body
        assert "token_prefix" in body
        assert "created_at" in body

    async def test_list_tokens_endpoint(self, mcp_client: httpx.AsyncClient):
        """GET after creating returns list including raw_token."""
        await mcp_client.post("/api/settings/mcp-tokens", json={"name": "Token A"})
        await mcp_client.post("/api/settings/mcp-tokens", json={"name": "Token B"})

        resp = await mcp_client.get("/api/settings/mcp-tokens")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        names = {t["token_name"] for t in body}
        assert names == {"Token A", "Token B"}
        for t in body:
            assert t["raw_token"].startswith(TOKEN_PREFIX)

    async def test_revoke_token_endpoint(self, mcp_client: httpx.AsyncClient):
        """DELETE returns 204."""
        create_resp = await mcp_client.post(
            "/api/settings/mcp-tokens", json={"name": "To Delete"}
        )
        token_id = create_resp.json()["id"]

        resp = await mcp_client.delete(f"/api/settings/mcp-tokens/{token_id}")
        assert resp.status_code == 204

    async def test_revoke_nonexistent_token(self, mcp_client: httpx.AsyncClient):
        """DELETE unknown ID returns 404."""
        resp = await mcp_client.delete("/api/settings/mcp-tokens/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth flow tests
# ---------------------------------------------------------------------------


class TestMcpTokenAuth:
    """Tests for MCP token authentication via _try_mcp_token."""

    async def test_mcp_token_auth_valid(
        self, test_db: aiosqlite.Connection, test_user: User
    ):
        """_try_mcp_token returns a User for a valid MCP token."""
        with _patch_db(test_db):
            token = await mcp_token_service.create_token(test_user.id, "Auth Test")
            user = await _try_mcp_token(token.raw_token)

        assert user is not None
        assert user.id == test_user.id

    async def test_mcp_token_auth_invalid(self, test_db: aiosqlite.Connection):
        """_try_mcp_token returns None for an invalid MCP token."""
        with _patch_db(test_db):
            result = await _try_mcp_token("qs_mcp_bogus_token_value")

        assert result is None

    async def test_mcp_token_auth_non_mcp_token(self, test_db: aiosqlite.Connection):
        """_try_mcp_token returns None for a non-MCP token (no qs_mcp_ prefix)."""
        with _patch_db(test_db):
            result = await _try_mcp_token("eyJhbGciOiJSUzI1NiJ9.some.jwt")

        assert result is None
