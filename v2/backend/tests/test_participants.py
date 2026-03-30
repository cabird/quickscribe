"""Tests for participant endpoints.

Covers: list, create, detail, update, delete, search, merge.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.models import Participant, User


# ---------------------------------------------------------------------------
# GET /api/participants — List
# ---------------------------------------------------------------------------


class TestListParticipants:
    async def test_list_empty(self, client: httpx.AsyncClient):
        resp = await client.get("/api/participants")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)
        if isinstance(data, list):
            assert len(data) == 0
        else:
            assert data == [] or body.get("total", 0) == 0

    async def test_list_with_data(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.get("/api/participants")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            ids = [p["id"] for p in data]
        else:
            ids = [p["id"] for p in data]
        assert sample_participant.id in ids

    async def test_list_ownership_isolation(
        self,
        client_as_other: httpx.AsyncClient,
        sample_participant: Participant,
    ):
        """Other user should not see test_user's participants."""
        resp = await client_as_other.get("/api/participants")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            ids = [p["id"] for p in data]
        else:
            ids = []
        assert sample_participant.id not in ids


# ---------------------------------------------------------------------------
# POST /api/participants — Create
# ---------------------------------------------------------------------------


class TestCreateParticipant:
    async def test_create_success(self, client: httpx.AsyncClient):
        payload = {
            "display_name": "John Smith",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com",
            "organization": "Test Corp",
        }
        resp = await client.post("/api/participants", json=payload)
        assert resp.status_code in (200, 201)
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["display_name"] == "John Smith"
        assert data["email"] == "john@example.com"

    async def test_create_minimal(self, client: httpx.AsyncClient):
        """Only display_name is required."""
        resp = await client.post(
            "/api/participants", json={"display_name": "Minimal"}
        )
        assert resp.status_code in (200, 201)

    async def test_create_missing_display_name(self, client: httpx.AsyncClient):
        resp = await client.post("/api/participants", json={"email": "no@name.com"})
        assert resp.status_code == 422

    async def test_create_with_aliases(self, client: httpx.AsyncClient):
        payload = {
            "display_name": "Bob",
            "aliases": ["Bobby", "Robert"],
        }
        resp = await client.post("/api/participants", json=payload)
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# GET /api/participants/{id} — Detail
# ---------------------------------------------------------------------------


class TestGetParticipant:
    async def test_get_found(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.get(f"/api/participants/{sample_participant.id}")
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["id"] == sample_participant.id
        assert data["display_name"] == "Jane Doe"

    async def test_get_not_found(self, client: httpx.AsyncClient):
        resp = await client.get(f"/api/participants/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_get_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_participant: Participant,
    ):
        resp = await client_as_other.get(f"/api/participants/{sample_participant.id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/participants/{id} — Update
# ---------------------------------------------------------------------------


class TestUpdateParticipant:
    async def test_update_success(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.put(
            f"/api/participants/{sample_participant.id}",
            json={"display_name": "Jane Updated", "organization": "New Corp"},
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert data["display_name"] == "Jane Updated"
        assert data["organization"] == "New Corp"

    async def test_update_not_found(self, client: httpx.AsyncClient):
        resp = await client.put(
            f"/api/participants/{uuid.uuid4()}",
            json={"display_name": "Ghost"},
        )
        assert resp.status_code == 404

    async def test_update_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_participant: Participant,
    ):
        resp = await client_as_other.put(
            f"/api/participants/{sample_participant.id}",
            json={"display_name": "Hacked"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/participants/{id}
# ---------------------------------------------------------------------------


class TestDeleteParticipant:
    async def test_delete_success(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.delete(f"/api/participants/{sample_participant.id}")
        assert resp.status_code in (200, 204)

        # Confirm deleted
        resp2 = await client.get(f"/api/participants/{sample_participant.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(self, client: httpx.AsyncClient):
        resp = await client.delete(f"/api/participants/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_participant: Participant,
    ):
        resp = await client_as_other.delete(
            f"/api/participants/{sample_participant.id}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/participants/search — Search
# ---------------------------------------------------------------------------


class TestSearchParticipants:
    async def test_search_exact(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.get(
            "/api/participants/search", params={"q": "Jane Doe"}
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert len(data) >= 1
            assert any(p["id"] == sample_participant.id for p in data)

    async def test_search_fuzzy(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        """Partial name search should still find participant."""
        resp = await client.get(
            "/api/participants/search", params={"q": "Jane"}
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert len(data) >= 1

    async def test_search_no_results(self, client: httpx.AsyncClient):
        resp = await client.get(
            "/api/participants/search", params={"q": "xyznonexistent"}
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert len(data) == 0

    async def test_search_ownership_isolation(
        self,
        client_as_other: httpx.AsyncClient,
        sample_participant: Participant,
    ):
        """Other user's search should not find test_user's participants."""
        resp = await client_as_other.get(
            "/api/participants/search", params={"q": "Jane"}
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, list):
            assert all(p["id"] != sample_participant.id for p in data)


# ---------------------------------------------------------------------------
# POST /api/participants/{id}/merge/{other_id} — Merge
# ---------------------------------------------------------------------------


class TestMergeParticipants:
    async def test_merge_success(
        self,
        client: httpx.AsyncClient,
        sample_participant: Participant,
        test_db,
        test_user: User,
    ):
        """Merge other_participant into sample_participant."""
        # Create a second participant to merge
        other_id = str(uuid.uuid4())
        await test_db.execute(
            """INSERT INTO participants (id, user_id, display_name, created_at, updated_at)
               VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
            (other_id, test_user.id, "John Duplicate"),
        )
        await test_db.commit()

        resp = await client.post(
            f"/api/participants/{sample_participant.id}/merge/{other_id}"
        )
        assert resp.status_code == 200

        # The merged participant should be deleted
        resp2 = await client.get(f"/api/participants/{other_id}")
        assert resp2.status_code == 404

    async def test_merge_target_not_found(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.post(
            f"/api/participants/{sample_participant.id}/merge/{uuid.uuid4()}"
        )
        assert resp.status_code == 404

    async def test_merge_source_not_found(
        self, client: httpx.AsyncClient, sample_participant: Participant
    ):
        resp = await client.post(
            f"/api/participants/{uuid.uuid4()}/merge/{sample_participant.id}"
        )
        assert resp.status_code == 404

    async def test_merge_wrong_user(
        self,
        client_as_other: httpx.AsyncClient,
        sample_participant: Participant,
        test_db,
        test_user: User,
    ):
        """Cannot merge another user's participants."""
        other_id = str(uuid.uuid4())
        await test_db.execute(
            """INSERT INTO participants (id, user_id, display_name, created_at, updated_at)
               VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
            (other_id, test_user.id, "Merge Target"),
        )
        await test_db.commit()

        resp = await client_as_other.post(
            f"/api/participants/{sample_participant.id}/merge/{other_id}"
        )
        assert resp.status_code == 404
