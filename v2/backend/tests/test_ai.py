"""Tests for AI endpoints.

Covers: chat with transcript, analysis execution.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from app.models import Recording, User


# ---------------------------------------------------------------------------
# POST /api/ai/chat — Chat with transcript
# ---------------------------------------------------------------------------


class TestAiChat:
    @patch("app.services.ai_service.AiService.chat", new_callable=AsyncMock)
    async def test_chat_success(
        self,
        mock_chat,
        client: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        mock_chat.return_value = {
            "message": "The meeting discussed project timelines.",
            "usage": {"prompt_tokens": 100, "completion_tokens": 25},
            "response_time_ms": 1200,
        }
        payload = {
            "recording_id": sample_recording.id,
            "messages": [
                {"role": "user", "content": "What was discussed in this meeting?"}
            ],
        }
        resp = await client.post("/api/ai/chat", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        data = body if "data" not in body else body["data"]
        assert "message" in data
        assert len(data["message"]) > 0

    @patch("app.services.ai_service.AiService.chat", new_callable=AsyncMock)
    async def test_chat_recording_not_found(
        self, mock_chat, client: httpx.AsyncClient
    ):
        """Chat for a nonexistent recording should return 404."""
        payload = {
            "recording_id": str(uuid.uuid4()),
            "messages": [
                {"role": "user", "content": "Hello?"}
            ],
        }
        resp = await client.post("/api/ai/chat", json=payload)
        assert resp.status_code == 404

    async def test_chat_missing_messages(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        """Request without messages should fail validation."""
        payload = {"recording_id": sample_recording.id}
        resp = await client.post("/api/ai/chat", json=payload)
        assert resp.status_code == 422

    async def test_chat_missing_recording_id(self, client: httpx.AsyncClient):
        """Request without recording_id should fail validation."""
        payload = {
            "messages": [{"role": "user", "content": "Hello"}]
        }
        resp = await client.post("/api/ai/chat", json=payload)
        assert resp.status_code == 422

    @patch("app.services.ai_service.AiService.chat", new_callable=AsyncMock)
    async def test_chat_wrong_user(
        self,
        mock_chat,
        client_as_other: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        """User B cannot chat about User A's recording."""
        payload = {
            "recording_id": sample_recording.id,
            "messages": [
                {"role": "user", "content": "What happened?"}
            ],
        }
        resp = await client_as_other.post("/api/ai/chat", json=payload)
        assert resp.status_code == 404

    @patch("app.services.ai_service.AiService.chat", new_callable=AsyncMock)
    async def test_chat_multi_turn(
        self,
        mock_chat,
        client: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        """Multi-turn conversation should include previous messages."""
        mock_chat.return_value = {
            "message": "There were two action items.",
            "usage": {"prompt_tokens": 200, "completion_tokens": 30},
            "response_time_ms": 1500,
        }
        payload = {
            "recording_id": sample_recording.id,
            "messages": [
                {"role": "user", "content": "Summarize the meeting."},
                {"role": "assistant", "content": "The meeting covered project updates."},
                {"role": "user", "content": "What were the action items?"},
            ],
        }
        resp = await client.post("/api/ai/chat", json=payload)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/recordings/{id}/analyze — Run analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    @patch("app.services.ai_service.AiService.analyze", new_callable=AsyncMock)
    async def test_analyze_success(
        self,
        mock_analyze,
        client: httpx.AsyncClient,
        sample_recording: Recording,
        test_db,
        test_user: User,
    ):
        # Create an analysis template first
        template_id = str(uuid.uuid4())
        await test_db.execute(
            """INSERT INTO analysis_templates (id, user_id, name, prompt, created_at, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (
                template_id,
                test_user.id,
                "Summary",
                "Summarize the following transcript:\n\n{transcript}",
            ),
        )
        await test_db.commit()

        mock_analyze.return_value = {
            "result": "This meeting covered three main topics...",
            "usage": {"prompt_tokens": 500, "completion_tokens": 100},
        }

        resp = await client.post(
            f"/api/recordings/{sample_recording.id}/analyze",
            json={"template_id": template_id},
        )
        assert resp.status_code == 200

    @patch("app.services.ai_service.AiService.analyze", new_callable=AsyncMock)
    async def test_analyze_recording_not_found(
        self, mock_analyze, client: httpx.AsyncClient
    ):
        resp = await client.post(
            f"/api/recordings/{uuid.uuid4()}/analyze",
            json={"template_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    async def test_analyze_missing_template_id(
        self, client: httpx.AsyncClient, sample_recording: Recording
    ):
        resp = await client.post(
            f"/api/recordings/{sample_recording.id}/analyze",
            json={},
        )
        assert resp.status_code == 422

    @patch("app.services.ai_service.AiService.analyze", new_callable=AsyncMock)
    async def test_analyze_wrong_user(
        self,
        mock_analyze,
        client_as_other: httpx.AsyncClient,
        sample_recording: Recording,
    ):
        resp = await client_as_other.post(
            f"/api/recordings/{sample_recording.id}/analyze",
            json={"template_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    @patch("app.services.ai_service.AiService.analyze", new_callable=AsyncMock)
    async def test_analyze_service_error(
        self,
        mock_analyze,
        client: httpx.AsyncClient,
        sample_recording: Recording,
        test_db,
        test_user: User,
    ):
        """AI service failure should return 500 or appropriate error."""
        template_id = str(uuid.uuid4())
        await test_db.execute(
            """INSERT INTO analysis_templates (id, user_id, name, prompt, created_at, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (template_id, test_user.id, "Failing", "Do something with {transcript}"),
        )
        await test_db.commit()

        mock_analyze.side_effect = Exception("OpenAI API error")
        resp = await client.post(
            f"/api/recordings/{sample_recording.id}/analyze",
            json={"template_id": template_id},
        )
        assert resp.status_code in (500, 502, 503)
