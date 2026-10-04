"""Real JWT, OAuthLib, SQLite and MCP integration; no cloud services or live data."""

import asyncio
import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth, config, database, oauth, oauth_clients, oauth_store
from app.routers import oauth as routes

ISSUER = "https://quickscribe.test"
RESOURCE = ISSUER + "/mcp"
CLIENT = "https://claude.ai/oauth/client.json"
REDIRECT = "http://127.0.0.1:49732/callback"
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


@pytest.fixture
async def world(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("OAUTH_ISSUER", ISSUER)
    monkeypatch.setenv("AUTH_DISABLED", "false")
    monkeypatch.setenv("AZURE_CLIENT_ID", "quickscribe-test")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    config.get_settings.cache_clear()
    from app.main import app

    app.dependency_overrides.clear()
    db = await database.init_db()
    for who in ("alice", "bob"):
        await db.execute(
            "INSERT INTO users (id,email,azure_oid,name,api_key) VALUES (?,?,?,?,?)",
            (who, who + "@example.com", who + "-oid", who.title(), who + "-key"),
        )
        await db.execute(
            """INSERT INTO recordings (id,user_id,title,original_filename,source,status,transcript_text)
            VALUES (?,?,?,?,?,'ready',?)""",
            (
                who + "-recording",
                who,
                who + " private recording",
                who + ".mp3",
                "upload",
                who + " private transcript",
            ),
        )
    await db.commit()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    async def signing_key(kid, tenant):
        return key.public_key()

    monkeypatch.setattr(auth, "_get_signing_key", signing_key)

    async def metadata(url):
        return {
            "client_id": url,
            "client_name": "Test Client",
            "redirect_uris": [REDIRECT],
            "token_endpoint_auth_method": "none",
        }

    monkeypatch.setattr(oauth_clients, "fetch_metadata", metadata)

    def login(who="alice", **extra):
        claims = {
            "oid": who + "-oid",
            "preferred_username": who + "@example.com",
            "name": who.title(),
            "aud": "quickscribe-test",
            "iss": "https://login.microsoftonline.com/test-tenant/v2.0",
            "exp": oauth.now_seconds() + 3600,
            "scp": "user_impersonation",
            **extra,
        }
        return {
            "Authorization": "Bearer "
            + jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
        }

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ISSUER) as client:
        yield client, db, login
    await database.close_db()
    app.dependency_overrides.clear()
    config.get_settings.cache_clear()


async def start(client, **changes):
    params = {
        "client_id": CLIENT,
        "redirect_uri": REDIRECT,
        "resource": RESOURCE,
        "response_type": "code",
        "scope": "mcp",
        "code_challenge_method": "S256",
        "code_challenge": CHALLENGE,
        "state": "opaque-client-state",
    }
    params.update(changes)
    return await client.get("/oauth/authorize", params=params)


async def consent_fields(world, who="alice"):
    client, db, login = world
    begun = await start(client)
    assert begun.status_code == 303, begun.text
    raw = parse_qs(urlsplit(begun.headers["location"]).query)["request"][0]
    info = await client.get("/api/oauth/consent", params={"request": raw}, headers=login(who))
    assert info.status_code == 200, info.text
    return {"request": raw, "csrf": info.json()["csrf"], "decision": "approve"}


async def issue_code(world, who="alice"):
    client, db, login = world
    fields = await consent_fields(world, who)
    approved = await client.post(
        "/api/oauth/consent", data=fields, headers={**login(who), "Origin": ISSUER}
    )
    assert approved.status_code == 200, approved.text
    values = parse_qs(urlsplit(approved.json()["redirect_uri"]).query)
    assert values["iss"] == [ISSUER] and values["state"] == ["opaque-client-state"]
    return values["code"][0]


def code_params(code, **changes):
    return {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT,
        "redirect_uri": REDIRECT,
        "code_verifier": VERIFIER,
        "resource": RESOURCE,
        **changes,
    }


async def issue_tokens(world, who="alice"):
    response = await world[0].post("/oauth/token", data=code_params(await issue_code(world, who)))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def bearer(token):
    return {"Authorization": "Bearer " + token}


async def refresh(client, token, **changes):
    return await client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT,
            "refresh_token": token,
            **changes,
        },
    )


async def test_discovery_challenges_and_invalid_manual_tokens(world):
    client, _, _ = world
    info = (
        await client.get("/.well-known/oauth-authorization-server", headers={"Host": "evil.test"})
    ).json()
    assert info["issuer"] == ISSUER and info["client_id_metadata_document_supported"]
    assert "registration_endpoint" not in info
    for path in (
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    ):
        assert (await client.get(path)).json()["resource"] == RESOURCE
    for method in ("GET", "POST", "DELETE"):
        for headers in ({}, bearer("qs_mcp_fake"), bearer("qs_oauth_at_fake")):
            r = await client.request(method, "/mcp", headers=headers)
            assert r.status_code == 401, r.text
            assert 'resource_metadata="' + ISSUER in r.headers["www-authenticate"]


async def test_consent_requires_real_jwt_browser_and_current_identity(world):
    client, _, login = world
    fields = await consent_fields(world)
    path = "/api/oauth/consent?request=" + fields["request"]
    assert (await client.get(path)).status_code == 401
    for headers in (
        bearer("qs_mcp_fake"),
        bearer("qs_oauth_at_fake"),
        {"X-API-Key": "alice-key"},
        login(scp=""),
        login(aud="other-app"),
    ):
        assert (await client.get(path, headers=headers)).status_code in (401, 403)
    for origin in (None, "null", "https://evil.test"):
        headers = login()
        if origin:
            headers["Origin"] = origin
        assert (
            await client.post("/api/oauth/consent", data=fields, headers=headers)
        ).status_code == 403
    assert (
        await client.post(
            "/api/oauth/consent", data=fields, headers={**login("bob"), "Origin": ISSUER}
        )
    ).status_code == 403
    saved = client.cookies.get(routes.browser_cookie())
    client.cookies.clear()
    assert (await client.get(path, headers=login())).status_code == 400
    client.cookies.set(routes.browser_cookie(), saved)
    result = await client.post(
        "/api/oauth/consent", data=fields, headers={**login(), "Origin": ISSUER}
    )
    assert result.status_code == 200
    assert (
        await client.post("/api/oauth/consent", data=fields, headers={**login(), "Origin": ISSUER})
    ).status_code == 400


async def test_denial_creates_no_grant(world):
    client, db, login = world
    fields = await consent_fields(world)
    r = await client.post(
        "/api/oauth/consent",
        data={**fields, "decision": "deny"},
        headers={**login(), "Origin": ISSUER},
    )
    values = parse_qs(urlsplit(r.json()["redirect_uri"]).query)
    assert values["error"] == ["access_denied"] and values["iss"] == [ISSUER]
    assert (await db.execute_fetchall("SELECT * FROM oauth_grants")) == []


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"resource": "https://other.test/mcp"}, "invalid_target"),
        ({"scope": "mcp admin"}, "invalid_scope"),
        ({"response_type": "token"}, "unsupported_response_type"),
        ({"response_mode": "fragment"}, "invalid_request"),
        ({"code_challenge_method": "plain"}, "invalid_request"),
        ({"code_challenge": "short"}, "invalid_request"),
    ],
)
async def test_authorization_binding(world, changes, error):
    r = await start(world[0], **changes)
    assert r.status_code == 303, r.text
    values = parse_qs(urlsplit(r.headers["location"]).query)
    assert values["error"] == [error] and values["iss"] == [ISSUER]


async def test_no_redirect_for_invalid_client_or_callback(world):
    for change in (
        {"client_id": "https://evil.test/client.json"},
        {"redirect_uri": "https://evil.test/cb"},
    ):
        r = await start(world[0], **change)
        assert r.status_code == 400 and "location" not in r.headers


@pytest.mark.parametrize(
    "changes",
    [
        {"code_verifier": "w" * 64},
        {"code_verifier": "short"},
        {"redirect_uri": REDIRECT + "/other"},
        {"client_id": "https://claude.ai/other.json"},
        {"resource": ""},
        {"resource": "https://other.test/mcp"},
        {"client_secret": ""},
        {"scope": "mcp admin"},
    ],
)
async def test_code_bindings_and_single_use(world, changes):
    client = world[0]
    code = await issue_code(world)
    bad = await client.post("/oauth/token", data=code_params(code, **changes))
    assert bad.status_code == 400, bad.text
    good = await client.post("/oauth/token", data=code_params(code))
    assert good.status_code == 200, good.text
    assert (await client.post("/oauth/token", data=code_params(code))).status_code == 400


async def test_credentials_are_hashed_persistent_and_expire(world):
    client, db, _ = world
    tokens = await issue_tokens(world)
    assert tokens["scope"] == "mcp" and tokens["expires_in"] == 3600
    rows = await db.execute_fetchall("SELECT * FROM oauth_credentials")
    assert {r["token_hash"] for r in rows} == {
        oauth.digest(tokens["access_token"]),
        oauth.digest(tokens["refresh_token"]),
    }
    await database.close_db()
    db = await database.init_db()
    assert (
        await client.get("/api/mcp/tags", headers=bearer(tokens["access_token"]))
    ).status_code == 200
    await db.execute("UPDATE oauth_credentials SET expires_at=0 WHERE kind='access'")
    await db.commit()
    assert (await client.post("/mcp", headers=bearer(tokens["access_token"]))).status_code == 401
    rotated = await refresh(client, tokens["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]
    assert (await refresh(client, tokens["refresh_token"])).status_code == 400
    assert (
        await client.post("/mcp", headers=bearer(rotated.json()["access_token"]))
    ).status_code == 401
    assert (await refresh(client, rotated.json()["refresh_token"])).status_code == 400


async def test_ownership_and_no_credential_escalation(world):
    client, _, login = world
    alice = await issue_tokens(world)
    bob = await issue_tokens(world, "bob")
    for tokens, owner, other in ((alice, "alice", "bob"), (bob, "bob", "alice")):
        h = bearer(tokens["access_token"])
        result = await client.get("/api/mcp/recordings", headers=h)
        assert result.status_code == 200, result.text
        assert (
            owner + " private recording" in result.text
            and other + " private recording" not in result.text
        )
        assert (
            await client.get("/api/mcp/recordings/" + other + "-recording", headers=h)
        ).status_code == 404
        for path in (
            "/api/me",
            "/api/settings/mcp-tokens",
            "/api/settings/oauth-connections",
            "/api/recordings",
        ):
            assert (
                await client.get(path, headers={**h, "X-API-Key": "alice-key"})
            ).status_code in (401, 403)
    listing = (await client.get("/api/settings/oauth-connections", headers=login())).json()
    assert len(listing) == 1
    url = "/api/settings/oauth-connections/" + listing[0]["id"]
    assert (await client.delete(url, headers={**login("bob"), "Origin": ISSUER})).status_code == 404
    assert (await client.delete(url, headers=login())).status_code == 403
    assert (await client.delete(url, headers={**login(), "Origin": ISSUER})).status_code == 204
    assert (await client.post("/mcp", headers=bearer(alice["access_token"]))).status_code == 401
    assert (
        await client.get("/api/mcp/tags", headers=bearer(bob["access_token"]))
    ).status_code == 200


async def test_rfc_revocation_and_client_binding(world):
    client = world[0]
    tokens = await issue_tokens(world)

    async def revoke(client_id):
        return await client.post(
            "/oauth/revoke", data={"client_id": client_id, "token": tokens["refresh_token"]}
        )

    assert (await revoke("https://claude.ai/other.json")).status_code == 200
    assert (
        await client.get("/api/mcp/tags", headers=bearer(tokens["access_token"]))
    ).status_code == 200
    assert (await revoke(CLIENT)).status_code == 200
    assert (await client.post("/mcp", headers=bearer(tokens["access_token"]))).status_code == 401
    assert (await refresh(client, tokens["refresh_token"])).status_code == 400


async def test_concurrent_redemption_and_refresh(world):
    client = world[0]
    code = await issue_code(world)
    responses = await asyncio.gather(
        *(client.post("/oauth/token", data=code_params(code)) for _ in range(2))
    )
    assert sorted(r.status_code for r in responses) == [200, 400]
    tokens = next(r.json() for r in responses if r.status_code == 200)
    responses = await asyncio.gather(*(refresh(client, tokens["refresh_token"]) for _ in range(2)))
    assert sorted(r.status_code for r in responses) == [200, 400]
    replacement = next(r.json() for r in responses if r.status_code == 200)
    assert (
        await client.post("/mcp", headers=bearer(replacement["access_token"]))
    ).status_code == 401


async def rpc(client, token, method, params, number=1):
    return await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": number, "method": method, "params": params},
        headers={
            **bearer(token),
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        },
    )


async def test_real_mcp_transport_and_manual_token_compatibility(world):
    client, db, _ = world
    tokens = await issue_tokens(world)
    token = tokens["access_token"]
    init = await rpc(
        client,
        token,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    )
    assert init.status_code == 200, init.text
    assert "mcp-session-id" not in init.headers
    tools = await rpc(client, token, "tools/list", {})
    names = {t["name"] for t in tools.json()["result"]["tools"]}
    assert len(names) == 11
    assert {"get_minutes", "get_transcript_window"} <= names
    alice, bob = await issue_tokens(world), await issue_tokens(world, "bob")
    # The detailed-minutes tools are scoped per user under OAuth like the rest
    for number, (tool, extra) in enumerate(
        (("get_minutes", {}), ("get_transcript_window", {"start": "0", "end": "60"})), 20
    ):
        theirs = await rpc(
            client,
            alice["access_token"],
            "tools/call",
            {"name": tool, "arguments": {"recording_id": "bob-recording", **extra}},
            number,
        )
        assert theirs.json()["result"].get("isError"), theirs.text
        assert "bob private" not in theirs.text
    results = await asyncio.gather(
        *(
            rpc(
                client,
                t["access_token"],
                "tools/call",
                {"name": "search_recordings", "arguments": {}},
                i + 3,
            )
            for i, t in enumerate((alice, bob))
        )
    )
    for result, owner, other in zip(results, ("alice", "bob"), ("bob", "alice")):
        assert not result.json()["result"].get("isError"), result.text
        assert (
            owner + " private recording" in result.text
            and other + " private recording" not in result.text
        )
    for method in ("GET", "DELETE"):
        assert (await client.request(method, "/mcp", headers=bearer(token))).status_code == 405
    from app.services import mcp_token_service

    manual = await mcp_token_service.create_token("alice", "Regression test")
    assert (await rpc(client, manual.raw_token, "tools/list", {})).status_code == 200
    await mcp_token_service.revoke_token("alice", manual.id)
    assert (await rpc(client, manual.raw_token, "tools/list", {})).status_code == 401


async def test_no_dev_fallback_and_duplicate_headers(world):
    client, _, _ = world
    config.get_settings().auth_disabled = True
    assert (
        await client.get("/api/mcp/tags", headers=bearer("qs_oauth_at_invalid"))
    ).status_code == 401
    assert (
        await client.post(
            "/mcp",
            headers=[
                ("Authorization", "Bearer qs_oauth_at_bad"),
                ("Authorization", "Bearer qs_mcp_bad"),
            ],
        )
    ).status_code == 401
    assert (await client.get("/api/settings/oauth-connections")).status_code == 401


async def test_malformed_protocol_and_origin_requests(world):
    client = world[0]
    assert (await client.get("/oauth/authorize?client_id=a&client_id=b")).status_code == 400
    assert (
        await client.post(
            "/oauth/token",
            content="x" * 17000,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    ).status_code == 400
    assert (await client.post("/oauth/token", json={})).status_code == 400
    assert (
        await client.post(
            "/oauth/token",
            content=b"\xff",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    ).status_code == 400
    t = await issue_tokens(world)
    assert (
        await client.post(
            "/mcp", headers={**bearer(t["access_token"]), "Origin": "https://evil.test"}
        )
    ).status_code == 403


async def test_schema_idempotence_and_litestream_pragmas(world):
    _, db, _ = world
    await db.executescript(oauth_store.SCHEMA_SQL)
    await db.executescript(oauth_store.SCHEMA_SQL)
    assert len(await db.execute_fetchall("SELECT id FROM users")) == 2
    async with oauth_store.connect() as isolated:
        assert (await isolated.execute_fetchall("PRAGMA wal_autocheckpoint"))[0][0] == 0
        assert (await isolated.execute_fetchall("PRAGMA foreign_keys"))[0][0] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"client_id": "https://claude.ai/other.json"},
        {"resource": "https://other.test/mcp"},
        {"scope": "mcp admin"},
    ],
)
async def test_refresh_binding_rejection_preserves_token(world, changes):
    client = world[0]
    tokens = await issue_tokens(world)
    assert (await refresh(client, tokens["refresh_token"], **changes)).status_code == 400
    assert (await refresh(client, tokens["refresh_token"])).status_code == 200


async def test_expired_pending_code_refresh_grant_and_deleted_user(world):
    client, db, login = world
    fields = await consent_fields(world)
    await db.execute("UPDATE oauth_transactions SET expires_at=0")
    await db.commit()
    assert (
        await client.post("/api/oauth/consent", data=fields, headers={**login(), "Origin": ISSUER})
    ).status_code == 400
    code = await issue_code(world)
    await db.execute("UPDATE oauth_codes SET expires_at=0")
    await db.commit()
    assert (await client.post("/oauth/token", data=code_params(code))).status_code == 400
    tokens = await issue_tokens(world)
    await db.execute("UPDATE oauth_credentials SET expires_at=0 WHERE kind='refresh'")
    await db.commit()
    assert (await refresh(client, tokens["refresh_token"])).status_code == 400
    tokens = await issue_tokens(world)
    await db.execute("UPDATE oauth_grants SET expires_at=0")
    await db.commit()
    assert (await client.post("/mcp", headers=bearer(tokens["access_token"]))).status_code == 401
    tokens = await issue_tokens(world)
    # Recordings have no delete cascade; remove this test user's content first.
    await db.execute("DELETE FROM recordings WHERE user_id='alice'")
    await db.execute("DELETE FROM users WHERE id='alice'")
    await db.commit()
    assert (await client.post("/mcp", headers=bearer(tokens["access_token"]))).status_code == 401
    assert (await refresh(client, tokens["refresh_token"])).status_code == 400


async def test_redeem_transaction_rolls_back_on_issue_failure(world, monkeypatch):
    code = await issue_code(world)
    real_protocol = oauth.protocol

    def broken(validator):
        server = real_protocol(validator)
        real_response = server.create_token_response

        def response(*args, **kwargs):
            headers, body, status = real_response(*args, **kwargs)
            result = json.loads(body)
            result["refresh_token"] = None  # Fail after code consumption, before commit.
            return headers, json.dumps(result), status

        server.create_token_response = response
        return server

    monkeypatch.setattr(oauth, "protocol", broken)
    with pytest.raises(AttributeError):
        await oauth.exchange_tokens(code_params(code))
    monkeypatch.setattr(oauth, "protocol", real_protocol)
    assert (await world[0].post("/oauth/token", data=code_params(code))).status_code == 200


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1/client.json",
        "https://claude.ai/",
        "https://claude.ai/client.json?q=1",
        "https://claude.ai:444/client.json",
        "http://claude.ai/client.json",
        "https://user@claude.ai/client.json",
        "https://claude.ai/client.json#fragment",
    ],
)
async def test_cimd_url_admission(value):
    with pytest.raises(oauth_clients.ClientMetadataError):
        await oauth_clients.resolve_client(value)


def test_redirect_matching_is_exact_except_loopback_port():
    assert oauth_clients.redirect_matches("http://127.0.0.1:5000/cb", "http://127.0.0.1:8000/cb")
    assert not oauth_clients.redirect_matches(
        "http://localhost:5000/cb", "http://127.0.0.1:8000/cb"
    )
    assert not oauth_clients.redirect_matches(
        "https://client.test/cb/extra", "https://client.test/cb"
    )
    assert not oauth_clients.redirect_matches(
        "https://client.test:443/cb", "https://client.test/cb"
    )


async def test_metadata_plural_auth_methods_and_dns_rebinding(world, monkeypatch):
    async def metadata(url):
        return {
            "client_id": url,
            "client_name": "Codex",
            "redirect_uris": [REDIRECT],
            "token_endpoint_auth_method": "private_key_jwt",
            "token_endpoint_auth_methods_supported": ["none"],
        }

    monkeypatch.setattr(oauth_clients, "fetch_metadata", metadata)
    assert (await oauth_clients.resolve_client(CLIENT)).client_name == "Codex"

    async def resolve(*args, **kwargs):
        return [{"host": "10.1.2.3"}]

    monkeypatch.setattr(oauth_clients.DefaultResolver, "resolve", resolve)
    resolver = oauth_clients.PublicResolver()
    try:
        with pytest.raises(OSError):
            await resolver.resolve("claude.ai", 443)
    finally:
        await resolver.close()


async def test_retention_keeps_refresh_replay_detection_until_grant_dies(world):
    client, db, _ = world
    tokens = await issue_tokens(world)
    assert (await refresh(client, tokens["refresh_token"])).status_code == 200
    async with oauth_store.connect(write=True) as isolated:
        await oauth_store.prune(isolated, oauth.now_seconds())
    assert len(await db.execute_fetchall("SELECT * FROM oauth_credentials")) == 4
    await db.execute("UPDATE oauth_grants SET expires_at=0")
    await db.commit()
    async with oauth_store.connect(write=True) as isolated:
        await oauth_store.prune(isolated, oauth.now_seconds())
    assert await db.execute_fetchall("SELECT * FROM oauth_credentials") == []


@pytest.mark.parametrize("path", ["/oauth/consent", "/oauth/consent/", "/OAUTH/CONSENT"])
async def test_consent_security_headers_cover_spa_route_variants(world, path):
    response = await world[0].get(path)
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "same-origin"
