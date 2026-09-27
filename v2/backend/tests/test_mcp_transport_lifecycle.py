"""Exercise the real SDK transport's cleanup on disconnect and cancellation."""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from app.mcp_transport import MCPResponse


def request(method="initialize"):
    params = (
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "lifecycle-test", "version": "1"},
        }
        if method == "initialize"
        else {}
    )
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/mcp",
        "raw_path": b"/mcp",
        "query_string": b"",
        "server": ("brainbox.example", 443),
        "client": ("127.0.0.1", 40000),
        "headers": [
            (b"host", b"brainbox.example"),
            (b"content-type", b"application/json"),
            (b"accept", b"application/json, text/event-stream"),
        ],
    }
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Future()

    return scope, receive


def tracked_server():
    state = {"active": 0, "closed": 0}

    @asynccontextmanager
    async def lifespan(server):
        state["active"] += 1
        try:
            yield {}
        finally:
            state["active"] -= 1
            state["closed"] += 1

    return Server("lifecycle-test", lifespan=lifespan), state


def response(server):
    return MCPResponse(StreamableHTTPSessionManager(server, stateless=True, json_response=True))


def has_connection_error(exc):
    if isinstance(exc, ConnectionError):
        return True
    return any(has_connection_error(child) for child in getattr(exc, "exceptions", ()))


@pytest.mark.parametrize("failed_message", ["http.response.start", "http.response.body"])
async def test_disconnected_client_closes_server_and_next_request_succeeds(failed_message):
    server, state = tracked_server()

    async def disconnected_send(message):
        if message["type"] == failed_message:
            raise ConnectionError("Client disconnected")

    scope, receive = request()
    with pytest.raises(Exception) as error:
        await asyncio.wait_for(response(server)(scope, receive, disconnected_send), timeout=2)
    assert has_connection_error(error.value)
    assert state == {"active": 0, "closed": 1}

    messages = []

    async def send(message):
        messages.append(message)

    scope, receive = request()
    await asyncio.wait_for(response(server)(scope, receive, send), timeout=2)
    assert messages[0]["status"] == 200
    assert b"mcp-session-id" not in dict(messages[0]["headers"])
    assert state == {"active": 0, "closed": 2}


async def test_cancelled_request_cancels_running_tool_and_closes_server():
    server, state = tracked_server()
    entered, tool_closed = asyncio.Event(), asyncio.Event()

    @server.list_tools()
    async def list_tools():
        entered.set()
        try:
            await asyncio.Future()
        finally:
            tool_closed.set()

    async def send(message):
        pass

    scope, receive = request("tools/list")
    pending = asyncio.create_task(response(server)(scope, receive, send))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(pending, timeout=2)
        assert tool_closed.is_set()
        assert state == {"active": 0, "closed": 1}
    finally:
        if not pending.done():
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
