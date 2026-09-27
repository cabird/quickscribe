"""MCP OAuth protocol adapter. Web identity and OAuth credentials stay separate."""

import hashlib
import json
import secrets
import time
from types import SimpleNamespace
from urllib.parse import urlencode

from fastapi import Request
from oauthlib.oauth2 import RequestValidator, WebApplicationServer
from starlette.responses import JSONResponse

from .config import get_settings
from .models import User
from .oauth_clients import Client, LOOPBACK, parse_url
from .oauth_store import connect, one

ACCESS_PREFIX = "qs_oauth_at_"
REFRESH_PREFIX = "qs_oauth_rt_"
ACCESS_SECONDS = 3600
REFRESH_DAYS = 30
GRANT_DAYS = 90
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}


def now_seconds():
    return int(time.time())


def issuer():
    value = get_settings().oauth_issuer.rstrip("/")
    url = parse_url(value)
    if (
        url.path
        or url.query
        or (url.scheme != "https" and not (url.scheme == "http" and url.hostname in LOOPBACK))
    ):
        raise ValueError("OAUTH_ISSUER must be an HTTPS origin (HTTP loopback is allowed locally)")
    return value


def resource():
    return issuer() + "/mcp"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class OAuthProblem(Exception):
    def __init__(self, error, description, status=400):
        self.error, self.description, self.status = error, description, status


def challenge():
    return f'Bearer resource_metadata="{issuer()}/.well-known/oauth-protected-resource/mcp", scope="mcp"'


async def oauth_error_handler(request: Request, exc: OAuthProblem):
    headers = dict(NO_STORE)
    if exc.status == 401:
        headers["WWW-Authenticate"] = challenge() + ', error="invalid_token"'
    body = (
        {"detail": exc.description}
        if request.url.path.startswith("/api/")
        else {
            "error": exc.error,
            "error_description": exc.description,
        }
    )
    return JSONResponse(body, status_code=exc.status, headers=headers)


async def validate_access_token(raw):
    if not raw.startswith(ACCESS_PREFIX) or len(raw) > 128:
        raise OAuthProblem("invalid_token", "A valid MCP access token is required", 401)
    now = now_seconds()
    async with connect() as db:
        user = await one(
            db,
            """SELECT users.* FROM oauth_credentials c
            JOIN oauth_grants g ON g.id=c.grant_id JOIN users ON users.id=g.user_id
            WHERE c.token_hash=? AND c.kind='access' AND c.expires_at>?
            AND g.revoked_at IS NULL AND g.expires_at>? AND g.resource=? AND g.scope='mcp'""",
            (digest(raw), now, now, resource()),
        )
    if not user:
        raise OAuthProblem("invalid_token", "The access token is expired, revoked or invalid", 401)
    return User(**vars(user))


async def oauth_user(request):
    """Guard before any dev/API-key fallback; only MCP tool REST routes qualify."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer qs_oauth_"):
        return None
    if len(request.headers.getlist("authorization")) != 1:
        raise OAuthProblem("invalid_token", "Ambiguous Authorization header", 401)
    route = request.scope.get("route")
    if "mcp" not in getattr(route, "tags", []):
        raise OAuthProblem("insufficient_scope", "This token only permits MCP tools", 403)
    return await validate_access_token(auth.split(" ", 1)[1])


class Validator(RequestValidator):
    """Per-request OAuthLib adapter. Async routes preload immutable bindings,
    then persist successful results atomically before returning any credential.
    """

    def __init__(self, client: Client, *, code=None, refresh=None, grant=None):
        self.client, self.code, self.refresh, self.grant = client, code, refresh, grant
        self.token = None

    def validate_client_id(self, client_id, request, *args, **kwargs):
        if client_id != self.client.client_id:
            return False
        request.client = SimpleNamespace(client_id=client_id)
        return True

    def client_authentication_required(self, request, *args, **kwargs):
        return False

    def authenticate_client_id(self, client_id, request, *args, **kwargs):
        return self.validate_client_id(client_id, request)

    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        return self.client.allows_redirect(redirect_uri)

    def get_default_redirect_uri(self, client_id, request, *args, **kwargs):
        return None  # always require an explicit callback

    def validate_response_type(self, client_id, response_type, client, request, *args, **kwargs):
        return response_type == "code"

    def get_default_scopes(self, client_id, request, *args, **kwargs):
        return ["mcp"]

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        return set(scopes) == {"mcp"}

    def is_pkce_required(self, client_id, request):
        return True

    def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
        return grant_type in {"authorization_code", "refresh_token"}

    def validate_code(self, client_id, code, client, request, *args, **kwargs):
        row = self.code
        if (
            row is None
            or row.code_hash != digest(code)
            or row.consumed_at is not None
            or row.expires_at <= now_seconds()
            or self.grant.client_id != client_id
        ):
            return False
        request.user, request.scopes = self.grant.user_id, ["mcp"]
        return True

    def get_code_challenge(self, code, request):
        return self.code.code_challenge

    def get_code_challenge_method(self, code, request):
        return "S256"

    def confirm_redirect_uri(self, client_id, code, redirect_uri, client, request, *args, **kwargs):
        return redirect_uri == self.code.redirect_uri

    def invalidate_authorization_code(self, client_id, code, request, *args, **kwargs):
        pass  # consumed with a conditional SQL UPDATE by exchange_tokens

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        row = self.refresh
        if (
            row is None
            or row.token_hash != digest(refresh_token)
            or row.kind != "refresh"
            or row.consumed_at is not None
            or row.expires_at <= now_seconds()
        ):
            return False
        request.user = self.grant.user_id
        return True

    def get_original_scopes(self, refresh_token, request, *args, **kwargs):
        return ["mcp"]

    def save_bearer_token(self, token, request, *args, **kwargs):
        self.token = dict(token)


def protocol(validator: Validator) -> WebApplicationServer:
    return WebApplicationServer(
        validator,
        token_expires_in=ACCESS_SECONDS,
        token_generator=lambda request: ACCESS_PREFIX + secrets.token_urlsafe(32),
        refresh_token_generator=lambda request: REFRESH_PREFIX + secrets.token_urlsafe(32),
    )


async def exchange_tokens(params):
    kind = params.get("grant_type")
    if kind not in {"authorization_code", "refresh_token"}:
        raise OAuthProblem("unsupported_grant_type", "Use authorization_code or refresh_token")
    if "scope" in params and set(params["scope"].split()) != {"mcp"}:
        raise OAuthProblem("invalid_scope", "Only the mcp scope is supported")
    is_code = kind == "authorization_code"
    raw = params.get("code" if is_code else "refresh_token", "")
    if not raw:
        raise OAuthProblem("invalid_request", "Missing grant credential")
    table, key = ("oauth_codes", "code_hash") if is_code else ("oauth_credentials", "token_hash")
    # The write lock covers read/validate/consume/issue, across processes too.
    # No HTTP/network operation is performed while this lock is held.
    async with connect(write=True) as db:
        row = await one(db, f"SELECT * FROM {table} WHERE {key}=?", (digest(raw),))
        grant = (
            await one(db, "SELECT * FROM oauth_grants WHERE id=?", (row.grant_id,)) if row else None
        )
        if not grant or not params.get("client_id") or params["client_id"] != grant.client_id:
            raise OAuthProblem("invalid_grant", "Invalid grant or client binding")
        target = params.get("resource")
        if (
            (is_code and not target)
            or (target and target != grant.resource)
            or grant.resource != resource()
        ):
            raise OAuthProblem("invalid_target", "The token must target this MCP resource")
        now = now_seconds()
        if (
            grant.revoked_at is not None
            or grant.expires_at <= now
            or not await one(db, "SELECT id FROM users WHERE id=?", (grant.user_id,))
        ):
            raise OAuthProblem("invalid_grant", "Authorization has expired or been revoked")
        if not is_code and row.kind != "refresh":
            raise OAuthProblem("invalid_grant", "A refresh token is required")
        if not is_code and row.consumed_at is not None:
            await db.execute("UPDATE oauth_grants SET revoked_at=? WHERE id=?", (now, grant.id))
            await db.commit()  # Replay revocation must survive the error response.
            raise OAuthProblem("invalid_grant", "Refresh token reuse detected; connect again")
        client = Client(grant.client_id, grant.client_name, (row.redirect_uri,) if is_code else ())
        validator = Validator(
            client, code=row if is_code else None, refresh=None if is_code else row, grant=grant
        )
        _, body, status = protocol(validator).create_token_response(
            issuer() + "/oauth/token",
            http_method="POST",
            body=urlencode(params),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        result = json.loads(body)
        if status != 200:
            raise OAuthProblem(
                result["error"], result.get("error_description", "Invalid token request"), status
            )
        changed = await db.execute(
            f"UPDATE {table} SET consumed_at=? WHERE {key}=? AND consumed_at IS NULL AND expires_at>?",
            (now, digest(raw), now),
        )
        if changed.rowcount != 1:
            raise OAuthProblem("invalid_grant", "Grant credential has already been used")
        for field, token_kind, lifetime in (
            ("access_token", "access", ACCESS_SECONDS),
            ("refresh_token", "refresh", REFRESH_DAYS * 86400),
        ):
            await db.execute(
                "INSERT INTO oauth_credentials (token_hash,grant_id,kind,expires_at) VALUES (?,?,?,?)",
                (
                    digest(result[field]),
                    grant.id,
                    token_kind,
                    min(now + lifetime, grant.expires_at),
                ),
            )
        await db.execute("UPDATE oauth_grants SET last_used_at=? WHERE id=?", (now, grant.id))
        result["expires_in"] = min(ACCESS_SECONDS, grant.expires_at - now)
        return result
