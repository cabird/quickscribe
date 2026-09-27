"""CIMD OAuth and consent via the existing Microsoft-authenticated React app."""

import hmac
import re
import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Request
from oauthlib.oauth2 import OAuth2Error
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.auth import _get_or_create_user, _validate_token
from app.config import get_settings
from app.oauth import (
    GRANT_DAYS,
    NO_STORE,
    OAuthProblem,
    Validator,
    digest,
    exchange_tokens,
    issuer,
    now_seconds,
    protocol,
    resource,
)
from app.oauth_clients import ClientMetadataError, resolve_client
from app.oauth_store import connect, one, prune

router = APIRouter()
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def browser_cookie():
    return ("__Host-" if issuer().startswith("https:") else "") + "qs_oauth_browser"


def parse_parameters(encoded):
    if len(encoded) > 16384:
        raise OAuthProblem("invalid_request", "Request too large")
    try:
        pairs = parse_qsl(encoded, keep_blank_values=True, max_num_fields=30, errors="strict")
    except (ValueError, UnicodeError):
        raise OAuthProblem("invalid_request", "Invalid request encoding")
    if len({key for key, _ in pairs}) != len(pairs):
        raise OAuthProblem("invalid_request", "Duplicate parameters are not supported")
    return dict(pairs)


async def form_parameters(request):
    if (
        request.headers.get("content-type", "").split(";")[0].strip()
        != "application/x-www-form-urlencoded"
    ):
        raise OAuthProblem("invalid_request", "Use application/x-www-form-urlencoded")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16384:
            raise OAuthProblem("invalid_request", "Request too large")
    try:
        return parse_parameters(body.decode("utf-8"))
    except UnicodeError:
        raise OAuthProblem("invalid_request", "Invalid request encoding")


def callback(uri, state, **values):
    parts = urlsplit(uri)
    params = list(parse_qsl(parts.query, keep_blank_values=True)) + list(values.items())
    if state is not None:
        params.append(("state", state))
    params.append(("iss", issuer()))
    return urlunsplit(parts._replace(query=urlencode(params)))


def same_origin(request):
    return (
        request.headers.get("origin") == issuer()
        and request.headers.get("sec-fetch-site") != "cross-site"
    )


async def browser_user(request: Request):
    """Microsoft access tokens only: no MCP token, API key or dev bypass."""
    headers = request.headers.getlist("authorization")
    if len(headers) != 1 or not headers[0].startswith("Bearer "):
        raise OAuthProblem("login_required", "Sign in to QuickScribe", 401)
    token = headers[0][7:]
    if token.startswith(("qs_", "bbx_")) or request.query_params.get("token"):
        raise OAuthProblem("access_denied", "Use your Microsoft website sign-in", 403)
    claims = await _validate_token(token, get_settings())
    if not claims.get("oid") or "user_impersonation" not in claims.get("scp", "").split():
        raise OAuthProblem(
            "access_denied", "A Microsoft access token for QuickScribe is required", 403
        )
    return await _get_or_create_user(
        claims["oid"], claims.get("preferred_username") or claims.get("email"), claims.get("name")
    )


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
@router.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
async def protected_resource_metadata():
    return JSONResponse(
        {
            "resource": resource(),
            "authorization_servers": [issuer()],
            "scopes_supported": ["mcp"],
            "bearer_methods_supported": ["header"],
        },
        headers=NO_STORE,
    )


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def authorization_metadata():
    base = issuer()
    return JSONResponse(
        {
            "issuer": base,
            "authorization_endpoint": base + "/oauth/authorize",
            "token_endpoint": base + "/oauth/token",
            "revocation_endpoint": base + "/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "scopes_supported": ["mcp"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint_auth_methods_supported": ["none"],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
        },
        headers=NO_STORE,
    )


@router.get("/oauth/authorize", include_in_schema=False)
async def authorize(request: Request):
    params = parse_parameters(request.url.query)
    try:
        client = await resolve_client(params.get("client_id", ""))
    except ClientMetadataError as exc:
        raise OAuthProblem("invalid_client", str(exc))
    redirect = params.get("redirect_uri", "")
    if not client.allows_redirect(redirect):
        raise OAuthProblem("invalid_request", "Callback is not declared by this client")
    try:
        if params.get("resource") != resource():
            raise OAuthProblem("invalid_target", "Request this MCP resource")
        if params.get("response_mode", "query") != "query":
            raise OAuthProblem("invalid_request", "Only query responses are supported")
        if params.get("code_challenge_method") != "S256" or not ID_PATTERN.fullmatch(
            params.get("code_challenge", "")
        ):
            raise OAuthProblem("invalid_request", "S256 PKCE is required")
        protocol(Validator(client)).validate_authorization_request(
            issuer() + "/oauth/authorize?" + urlencode(params)
        )
    except (OAuthProblem, OAuth2Error) as exc:
        description = exc.description
        return RedirectResponse(
            callback(redirect, params.get("state"), error=exc.error, error_description=description),
            status_code=303,
            headers=NO_STORE,
        )
    now = now_seconds()
    raw = secrets.token_urlsafe(32)
    browser = request.cookies.get(browser_cookie(), "")
    if not ID_PATTERN.fullmatch(browser):
        browser = secrets.token_urlsafe(32)
    async with connect(write=True) as db:
        await prune(db, now)
        count = await one(db, "SELECT count(*) AS n FROM oauth_transactions")
        if count.n >= 1000:
            raise OAuthProblem(
                "temporarily_unavailable", "Too many pending sign-ins; try again shortly", 429
            )
        await db.execute(
            """INSERT INTO oauth_transactions
            (id_hash,browser_hash,client_id,client_name,redirect_uri,resource,code_challenge,state,expires_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                digest(raw),
                digest(browser),
                client.client_id,
                client.client_name,
                redirect,
                resource(),
                params["code_challenge"],
                params.get("state"),
                now + 600,
            ),
        )
    response = RedirectResponse(
        "/oauth/consent?" + urlencode({"request": raw}), status_code=303, headers=NO_STORE
    )
    response.set_cookie(
        browser_cookie(),
        browser,
        max_age=1200,
        httponly=True,
        secure=issuer().startswith("https:"),
        samesite="lax",
        path="/",
    )
    return response


async def transaction(db, request, raw):
    browser = request.cookies.get(browser_cookie(), "")
    if not ID_PATTERN.fullmatch(raw) or not ID_PATTERN.fullmatch(browser):
        raise OAuthProblem(
            "invalid_request", "Connection request is missing or expired; start again"
        )
    row = await one(db, "SELECT * FROM oauth_transactions WHERE id_hash=?", (digest(raw),))
    if (
        not row
        or row.consumed_at is not None
        or row.expires_at <= now_seconds()
        or row.resource != resource()
        or not hmac.compare_digest(row.browser_hash, digest(browser))
    ):
        raise OAuthProblem(
            "invalid_request", "Connection request is missing or expired; start again"
        )
    return row


def consent_csrf(request, raw, user_id):
    return hmac.new(
        request.cookies.get(browser_cookie(), "").encode(), (raw + ":" + user_id).encode(), "sha256"
    ).hexdigest()


@router.get("/api/oauth/consent", include_in_schema=False)
async def consent_info(request: Request, user=Depends(browser_user)):
    raw = parse_parameters(request.url.query).get("request", "")
    async with connect() as db:
        row = await transaction(db, request, raw)
    return JSONResponse(
        {
            "client_name": row.client_name,
            "client_id": row.client_id,
            "redirect_uri": row.redirect_uri,
            "email": user.email,
            "name": user.name,
            "csrf": consent_csrf(request, raw, user.id),
        },
        headers=NO_STORE,
    )


@router.post("/api/oauth/consent", include_in_schema=False)
async def consent_decision(request: Request, user=Depends(browser_user)):
    if not same_origin(request):
        raise OAuthProblem("access_denied", "Cross-origin request rejected", 403)
    params = await form_parameters(request)
    raw = params.get("request", "")
    if not hmac.compare_digest(params.get("csrf", ""), consent_csrf(request, raw, user.id)):
        raise OAuthProblem("access_denied", "Invalid consent; reload and try again", 403)
    if params.get("decision") not in {"approve", "deny"}:
        raise OAuthProblem("invalid_request", "Choose whether to allow access")
    now = now_seconds()
    async with connect(write=True) as db:
        row = await transaction(db, request, raw)
        await db.execute(
            "UPDATE oauth_transactions SET consumed_at=? WHERE id_hash=?", (now, row.id_hash)
        )
        if params["decision"] == "deny":
            target = callback(
                row.redirect_uri,
                row.state,
                error="access_denied",
                error_description="The user declined access",
            )
        else:
            grant_id, code = secrets.token_hex(16), secrets.token_urlsafe(32)
            await db.execute(
                """INSERT INTO oauth_grants
                (id,user_id,client_id,client_name,resource,scope,created_at,expires_at)
                VALUES (?,?,?,?,?,'mcp',?,?)""",
                (
                    grant_id,
                    user.id,
                    row.client_id,
                    row.client_name,
                    resource(),
                    now,
                    now + GRANT_DAYS * 86400,
                ),
            )
            await db.execute(
                """INSERT INTO oauth_codes (code_hash,grant_id,redirect_uri,code_challenge,expires_at)
                VALUES (?,?,?,?,?)""",
                (digest(code), grant_id, row.redirect_uri, row.code_challenge, now + 120),
            )
            target = callback(row.redirect_uri, row.state, code=code)
    return JSONResponse({"redirect_uri": target}, headers=NO_STORE)


@router.post("/oauth/token", include_in_schema=False)
async def token_endpoint(request: Request):
    params = await form_parameters(request)
    if (
        request.url.query
        or request.headers.get("authorization")
        or any(k in params for k in ("client_secret", "client_assertion", "client_assertion_type"))
    ):
        raise OAuthProblem("invalid_client", "Use public-client PKCE without a client secret")
    if params.get("grant_type") == "authorization_code" and not re.fullmatch(
        r"[A-Za-z0-9._~-]{43,128}", params.get("code_verifier", "")
    ):
        raise OAuthProblem("invalid_grant", "A valid PKCE verifier is required")
    return JSONResponse(await exchange_tokens(params), headers=NO_STORE)


@router.post("/oauth/revoke", include_in_schema=False)
async def revoke_endpoint(request: Request):
    params = await form_parameters(request)
    if (
        request.url.query
        or request.headers.get("authorization")
        or any(k in params for k in ("client_secret", "client_assertion", "client_assertion_type"))
        or not params.get("client_id")
    ):
        raise OAuthProblem("invalid_client", "Identify the public client in the request body")
    if not params.get("token"):
        raise OAuthProblem("invalid_request", "A token is required")
    async with connect(write=True) as db:
        await db.execute(
            """UPDATE oauth_grants SET revoked_at=? WHERE client_id=? AND id IN
            (SELECT grant_id FROM oauth_credentials WHERE token_hash=?)""",
            (now_seconds(), params["client_id"], digest(params["token"])),
        )
    return Response(status_code=200, headers=NO_STORE)


@router.get("/api/settings/oauth-connections", tags=["settings"])
async def connections(user=Depends(browser_user)):
    async with connect() as db:
        rows = await db.execute_fetchall(
            """SELECT id,client_name,client_id,created_at,expires_at,last_used_at,revoked_at
            FROM oauth_grants WHERE user_id=? ORDER BY created_at DESC""",
            (user.id,),
        )
    return JSONResponse([dict(row) for row in rows], headers=NO_STORE)


@router.delete("/api/settings/oauth-connections/{connection_id}", tags=["settings"])
async def disconnect(connection_id: str, request: Request, user=Depends(browser_user)):
    if not same_origin(request):
        raise OAuthProblem("access_denied", "Cross-origin request rejected", 403)
    async with connect(write=True) as db:
        changed = await db.execute(
            "UPDATE oauth_grants SET revoked_at=? WHERE id=? AND user_id=?",
            (now_seconds(), connection_id, user.id),
        )
        if not changed.rowcount:
            raise OAuthProblem("invalid_request", "Connection not found", 404)
    return Response(status_code=204, headers=NO_STORE)
