"""Tests for tag endpoints.

Covers: create, list, update, delete, validation.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.models import Tag, User


# ---------------------------------------------------------------------------
# POST /api/tags — Create
# ---------------------------------------------------------------------------


class TestCreateTag:
    async def test_create_success(self, client: httpx.AsyncClient):
        payload = {"name": "meeting", "color": "#00ff00"}
        resp = await client.post("/api/tags", json=payload)
        assert resp.status_code in (200, 201)
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["name"] == "meeting"
        assert data["color"] == "#00ff00"

    async def test_create_invalid_color(self, client: httpx.AsyncClient):
        """Color must be a valid hex color (#RRGGBB)."""
        payload = {"name": "bad-color", "color": "red"}
        resp = await client.post("/api/tags", json=payload)
        assert resp.status_code == 422

    async def test_create_invalid_color_short(self, client: httpx.AsyncClient):
        """Short hex (#RGB) should be rejected — only #RRGGBB."""
        payload = {"name": "short-hex", "color": "#f00"}
        resp = await client.post("/api/tags", json=payload)
        assert resp.status_code == 422

    async def test_create_duplicate_name(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        """Same user cannot have two tags with the same name."""
        payload = {"name": sample_tag.name, "color": "#0000ff"}
        resp = await client.post("/api/tags", json=payload)
        assert resp.status_code in (400, 409)

    async def test_create_missing_name(self, client: httpx.AsyncClient):
        resp = await client.post("/api/tags", json={"color": "#ff0000"})
        assert resp.status_code == 422

    async def test_create_missing_color(self, client: httpx.AsyncClient):
        resp = await client.post("/api/tags", json={"name": "no-color"})
        assert resp.status_code == 422

    async def test_create_name_too_long(self, client: httpx.AsyncClient):
        """Tag name is limited to 32 characters."""
        payload = {"name": "a" * 33, "color": "#ff0000"}
        resp = await client.post("/api/tags", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/tags — List
# ---------------------------------------------------------------------------


class TestListTags:
    async def test_list_empty(self, client: httpx.AsyncClient):
        resp = await client.get("/api/tags")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert len(data) == 0

    async def test_list_with_data(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client.get("/api/tags")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert len(data) >= 1
            assert any(t["id"] == sample_tag.id for t in data)

    async def test_list_ownership_isolation(
        self, client_as_other: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client_as_other.get("/api/tags")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert all(t["id"] != sample_tag.id for t in data)


# ---------------------------------------------------------------------------
# PUT /api/tags/{id} — Update
# ---------------------------------------------------------------------------


class TestUpdateTag:
    async def test_update_name(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client.put(
            f"/api/tags/{sample_tag.id}", json={"name": "updated"}
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["name"] == "updated"

    async def test_update_color(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client.put(
            f"/api/tags/{sample_tag.id}", json={"color": "#00ff00"}
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["color"] == "#00ff00"

    async def test_update_invalid_color(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client.put(
            f"/api/tags/{sample_tag.id}", json={"color": "not-a-color"}
        )
        assert resp.status_code == 422

    async def test_update_not_found(self, client: httpx.AsyncClient):
        resp = await client.put(
            f"/api/tags/{uuid.uuid4()}", json={"name": "ghost"}
        )
        assert resp.status_code == 404

    async def test_update_wrong_user(
        self, client_as_other: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client_as_other.put(
            f"/api/tags/{sample_tag.id}", json={"name": "hacked"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/tags/{id}
# ---------------------------------------------------------------------------


class TestDeleteTag:
    async def test_delete_success(
        self, client: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client.delete(f"/api/tags/{sample_tag.id}")
        assert resp.status_code in (200, 204)

        # Confirm deleted
        resp2 = await client.get("/api/tags")
        body = resp2.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert all(t["id"] != sample_tag.id for t in data)

    async def test_delete_not_found(self, client: httpx.AsyncClient):
        resp = await client.delete(f"/api/tags/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_wrong_user(
        self, client_as_other: httpx.AsyncClient, sample_tag: Tag
    ):
        resp = await client_as_other.delete(f"/api/tags/{sample_tag.id}")
        assert resp.status_code == 404

    async def test_delete_cascades_from_recordings(
        self,
        client: httpx.AsyncClient,
        sample_tag: Tag,
        sample_recording,
        test_db,
    ):
        """Deleting a tag should remove it from recording_tags join table."""
        await test_db.execute(
            "INSERT INTO recording_tags (recording_id, tag_id) VALUES (?, ?)",
            (sample_recording.id, sample_tag.id),
        )
        await test_db.commit()

        resp = await client.delete(f"/api/tags/{sample_tag.id}")
        assert resp.status_code in (200, 204)

        rows = await test_db.execute_fetchall(
            "SELECT * FROM recording_tags WHERE tag_id = ?", (sample_tag.id,)
        )
        assert len(rows) == 0
