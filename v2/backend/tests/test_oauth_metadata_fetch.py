"""Exercise the real CIMD HTTP reader against a local server, without DNS/network fixtures.

URL admission and public-address resolution are covered in test_mcp_oauth.
These tests call the lower-level reader directly over loopback so its actual
HTTP redirect handling, streaming, parsing, and timeout behavior are exercised.
"""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from aiohttp import web

from app import oauth_clients


@asynccontextmanager
async def metadata_server(handler):
    app = web.Application()
    app.router.add_get("/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        host, port = runner.addresses[0]
        yield f"http://{host}:{port}"
    finally:
        await runner.cleanup()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_metadata_does_not_follow_redirects(status):
    paths = []

    async def handler(request):
        paths.append(request.path)
        if request.path == "/client.json":
            return web.Response(status=status, headers={"Location": "/redirected.json"})
        return web.json_response({"client_name": "Unexpected redirect target"})

    async with metadata_server(handler) as base:
        with pytest.raises(oauth_clients.ClientMetadataError):
            await oauth_clients.fetch_metadata(base + "/client.json")
    assert paths == ["/client.json"]


@pytest.mark.parametrize("size", [65536, 65537])
async def test_metadata_streaming_size_boundary(size):
    metadata = {"padding": "a" * (size - len(b'{"padding":""}'))}
    body = json.dumps(metadata, separators=(",", ":")).encode()
    assert len(body) == size

    async def handler(request):
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        # No Content-Length: the reader must enforce its bound while consuming
        # chunks, rather than relying on a declared response length.
        for offset in range(0, len(body), 4096):
            await response.write(body[offset : offset + 4096])
        await response.write_eof()
        return response

    async with metadata_server(handler) as base:
        if size == 65536:
            assert await oauth_clients.fetch_metadata(base + "/client.json") == metadata
        else:
            with pytest.raises(oauth_clients.ClientMetadataError):
                await oauth_clients.fetch_metadata(base + "/client.json")


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b'{"client_id":"first","client_id":"second"}', "application/json"),
        (b'{"nested":{"redirect_uris":[],"redirect_uris":[]}}', "application/json"),
        (b'{"client_name":"valid JSON with the wrong MIME"}', "text/html"),
        (b'{"client_name":', "application/json"),
    ],
)
async def test_metadata_rejects_ambiguous_or_invalid_responses(body, content_type):
    async def handler(request):
        return web.Response(body=body, content_type=content_type)

    async with metadata_server(handler) as base:
        with pytest.raises(oauth_clients.ClientMetadataError):
            await oauth_clients.fetch_metadata(base + "/client.json")


async def test_metadata_timeout_is_reported_as_client_error(monkeypatch):
    real_timeout = oauth_clients.aiohttp.ClientTimeout
    monkeypatch.setattr(
        oauth_clients.aiohttp, "ClientTimeout", lambda **kwargs: real_timeout(total=0.05)
    )
    started, release = asyncio.Event(), asyncio.Event()

    async def handler(request):
        started.set()
        await release.wait()
        return web.json_response({"client_name": "Too late"})

    async with metadata_server(handler) as base:
        try:
            with pytest.raises(oauth_clients.ClientMetadataError):
                await oauth_clients.fetch_metadata(base + "/client.json")
            assert started.is_set()
        finally:
            release.set()


async def test_metadata_requests_do_not_send_ambient_credentials(monkeypatch, tmp_path):
    # A metadata fetch must not inherit credentials from machine-level HTTP
    # configuration or retain a cookie set by an earlier metadata response.
    netrc = tmp_path / "netrc"
    netrc.write_text("machine 127.0.0.1 login ambient-user password ambient-password\n")
    netrc.chmod(0o600)
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("HTTP_PROXY", "http://proxy-user:proxy-password@127.0.0.1:1")
    monkeypatch.setenv("http_proxy", "http://proxy-user:proxy-password@127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    requests = []

    async def handler(request):
        requests.append(dict(request.headers))
        response = web.json_response({"client_name": "Local test client"})
        response.set_cookie("metadata_secret", "must-not-be-forwarded")
        return response

    async with metadata_server(handler) as base:
        for _ in range(2):
            assert await oauth_clients.fetch_metadata(base + "/client.json") == {
                "client_name": "Local test client"
            }
    assert len(requests) == 2
    for headers in requests:
        assert {"authorization", "proxy-authorization", "cookie"}.isdisjoint(
            key.lower() for key in headers
        )
