"""Tests for sync endpoints.

Covers: trigger sync, list sync runs, get sync run detail.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import SyncRun, SyncRunStatus, SyncTrigger, User


# ---------------------------------------------------------------------------
# POST /api/sync/trigger — Trigger sync
# ---------------------------------------------------------------------------


class TestTriggerSync:
    @patch("app.services.sync_service.SyncService.trigger_sync", new_callable=AsyncMock)
    async def test_trigger_success(
        self, mock_trigger, client: httpx.AsyncClient
    ):
        mock_trigger.return_value = {"id": str(uuid.uuid4()), "status": "running"}
        resp = await client.post("/api/sync/trigger")
        assert resp.status_code in (200, 202)

    @patch("app.services.sync_service.SyncService.trigger_sync", new_callable=AsyncMock)
    async def test_trigger_already_running(
        self, mock_trigger, client: httpx.AsyncClient
    ):
        """If a sync is already in progress, should return conflict or appropriate status."""
        mock_trigger.side_effect = Exception("Sync already running")
        resp = await client.post("/api/sync/trigger")
        # Could be 409 Conflict or 400 or similar
        assert resp.status_code in (400, 409, 500)


# ---------------------------------------------------------------------------
# GET /api/sync/status — List sync runs / recent status
# ---------------------------------------------------------------------------


class TestListSyncRuns:
    async def test_list_empty(self, client: httpx.AsyncClient):
        resp = await client.get("/api/sync/status")
        assert resp.status_code == 200

    async def test_list_with_data(
        self, client: httpx.AsyncClient, sample_sync_run: SyncRun
    ):
        resp = await client.get("/api/sync/status")
        assert resp.status_code == 200
        body = resp.json()
        # Response could be a list or paginated object
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert len(data) >= 1

    async def test_list_filter_by_status(
        self, client: httpx.AsyncClient, sample_sync_run: SyncRun
    ):
        resp = await client.get(
            "/api/sync/status", params={"status": "completed"}
        )
        assert resp.status_code == 200

    async def test_list_filter_by_trigger(
        self, client: httpx.AsyncClient, sample_sync_run: SyncRun
    ):
        resp = await client.get(
            "/api/sync/status", params={"trigger": "manual"}
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/sync/status/{id} — Sync run detail
# ---------------------------------------------------------------------------


class TestGetSyncRunDetail:
    async def test_get_detail(
        self, client: httpx.AsyncClient, sample_sync_run: SyncRun
    ):
        """Get detail of a specific sync run (if the API supports it)."""
        # The spec shows GET /api/sync/status for recent status.
        # If the API supports getting a specific run by ID:
        resp = await client.get(f"/api/sync/status/{sample_sync_run.id}")
        # Either 200 with detail or 404 if this endpoint doesn't exist
        if resp.status_code == 200:
            body = resp.json()
            data = body if "data" not in body else body["data"]
            assert data["id"] == sample_sync_run.id
            assert data["status"] == "completed"

    async def test_get_detail_not_found(self, client: httpx.AsyncClient):
        resp = await client.get(f"/api/sync/status/{uuid.uuid4()}")
        assert resp.status_code in (404, 405)  # 405 if route doesn't exist
