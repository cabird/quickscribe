# MCP OAuth

QuickScribe supports browser-approved MCP access through its existing Microsoft
website sign-in. It is live in version **2.8.18**. The server URL is
`https://quickscribe.cabird.com/mcp`.

In Claude's custom connector dialog select **Sign in now** and **Use Claude's
published identity**. Leave request headers, client ID and client secret empty.
Clients identify themselves with a Client ID Metadata Document (CIMD); dynamic
client registration and confidential clients are not supported. Existing manual
MCP tokens remain supported independently.

## Flow and boundaries

1. Public protected-resource and authorization-server metadata advertise the
   configured issuer, endpoints, `mcp` scope, S256 PKCE and CIMD support.
2. `/oauth/authorize` validates the client and callback, saves a ten-minute
   transaction and binds it to an HttpOnly SameSite browser cookie. The browser
   visits the React consent page at `/oauth/consent`.
3. Microsoft login resumes only an opaque transaction ID. Consent APIs validate
   the Microsoft access token, including the QuickScribe audience and delegated
   `user_impersonation` scope. They reject manual MCP tokens, OAuth credentials,
   API keys and the development bypass.
4. The page shows the account, client, callback and read access. Approval requires
   the initiating browser, same-origin POST and an account-bound consent proof.
   Approval or denial consumes the request exactly once. Redirects include `iss`.
5. The client exchanges its single-use code with its PKCE verifier and resource
   binding. The resulting token belongs to the existing QuickScribe user ID.
   Microsoft's credentials are never sent to the MCP client.

OAuth credentials authorize the read-only MCP tools (eleven since detailed
minutes added `get_minutes` and `get_transcript_window`) and their `/api/mcp`
backing routes. They cannot access general recording writes, account settings,
API-key creation, manual-token creation or connected-app management. Every MCP
HTTP request validates its bearer credential before protocol dispatch. Invalid
or expired credentials produce HTTP 401 with resource discovery metadata.

The transport uses stateless Streamable HTTP with JSON responses. No MCP session
identifier carries account authority. Authenticated GET/DELETE return 405; there
are no server-push subscriptions. Each response owns the SDK task group, including
cleanup after failed sends or cancellation.

## Storage and lifetimes

Four additive tables are created idempotently on startup: `oauth_transactions`,
`oauth_grants`, `oauth_codes`, and `oauth_credentials`. Existing account IDs,
recordings and manual tokens are unchanged. Credentials, codes and browser
transaction secrets are stored as SHA-256 hashes.

- Authorization request: 10 minutes; authorization code: 2 minutes.
- Access token: 1 hour; refresh token: 30 days, replaced on every refresh.
- Grant: 90 days absolute; reconnect after expiration.
- Reusing a consumed refresh token revokes the entire grant.
- Settings → Connected apps → Revoke access invalidates subsequent requests and
  refreshes. An already running tool operation can finish.

OAuth writes use short independent SQLite transactions with `BEGIN IMMEDIATE`.
They cannot commit a recording job's in-flight work on the application's shared
connection. Every OAuth connection sets `wal_autocheckpoint=0` and
`foreign_keys=ON`; Litestream remains responsible for checkpointing. No network
operation occurs while an OAuth write lock is held.

Starting authorization prunes expired requests, codes expired for over a day,
and grants expired/revoked for over seven days (cascading to credentials).
Consumed refresh hashes stay for the grant lifetime so reuse remains detectable.
Pending authorization requests have a global limit of 1,000.

## Configuration and deployment

Defaults already target the current production instance:

```dotenv
OAUTH_ISSUER=https://quickscribe.cabird.com
OAUTH_CIMD_HOSTS=["claude.ai","chatgpt.com"]
```

The issuer must be an HTTPS origin; HTTP loopback is permitted locally. It is not
inferred from Host headers. CIMD fetches allow only configured DNS hosts and
public resolved addresses, with HTTPS, no redirects/ambient credentials, a
five-second timeout and a 64 KiB limit. HTTPS callbacks match exactly; published
HTTP loopback callbacks may vary only their port.

Microsoft website authentication keeps its existing configuration. No new
Microsoft client secret or Azure registration changes are required. The existing
registration permits local testing at `http://localhost:5173`.

Follow `CLAUDE.md` and the current migration notes for deployment. Pin the
Pay-As-You-Go subscription `dfd21f2e-a846-4677-9341-78dd8723df4e`, take a fresh
backup, and stop → configure → start the single SQLite/Litestream instance.
The build script increments `v2/backend/VERSION`; do not bump it in advance.
Hosted Claude/ChatGPT end-to-end sign-in still requires checks in those clients.

## Production deployment (September 27, 2026)

Version **2.8.18** was deployed from `main` to the new subscription's `quickscribe`
App Service using stop → configure → start. A fresh database backup passed
SQLite integrity checks before the deployment. The production health endpoint
reports 2.8.18, with one running instance.

Production checks passed for the website bundle and Microsoft configuration,
OAuth discovery and error responses, secure browser-bound consent, CIMD resolution
using Codex's published identity, and Microsoft authentication enforcement.
The existing manual token successfully initialized MCP, discovered all nine tools,
and called `list_tags`. These checks issued no OAuth grant; the complete real
Codex sign-in, refresh, and revocation checks below used the local test instance.

## Validation record (September 27, 2026)

- 60 new backend tests cover real signed Microsoft JWTs, OAuthLib processing,
  migrations, rollback, concurrent redemption/refresh, ownership and scope,
  expiry/revocation, malformed inputs, CIMD HTTP/DNS restrictions and MCP lifecycle.
- Three frontend continuation tests pass, along with the TypeScript/Vite build.
- Real Codex CLI 0.153.4 sign-in completed through Microsoft and explicit consent
  against an isolated local database, with cloud jobs disabled.
- Codex discovered all nine tools and successfully called `list_tags` (empty
  result). Its native app-server APIs were used directly; no model turn was needed.
- Expiring only the local access token caused automatic refresh; SQLite confirmed
  exactly one replacement access/refresh pair and consumption of the old refresh.
- Clicking Revoke access in Settings made a fresh Codex connection fail with
  `Auth required`. Temporary local client credentials were then removed.
- No user-wide MCP configuration was changed.

The unchanged checkout had **83 failures and 189 passes**. Repairing the shared
HTTP fixture's auth dependency override and database binding recovered 61 tests.
The full suite now has **310 passes and 22 pre-existing failures**. Remaining
failures are stale AI/storage/sync mocks, old participant/sync routes, and outdated
upload/AI expectations; they also fail without this OAuth change. They are not
silently skipped or marked expected failures.

Commands:

```sh
cd v2/backend
PYTHONPATH=src uv run --frozen --extra dev pytest tests/ -q
# Focused OAuth checks:
PYTHONPATH=src uv run --frozen --extra dev pytest tests/test_mcp_oauth.py tests/test_oauth_metadata_fetch.py tests/test_mcp_transport_lifecycle.py -q
cd ../frontend
node --experimental-strip-types --test tests/oauthContinuation.test.ts
npm ci
npm run build
```

For a temporary native Codex connection without changing its configuration file:

```sh
codex mcp login quickscribe-oauth-local \
  -c 'mcp_servers.quickscribe-oauth-local.url="http://localhost:5173/mcp"' \
  --oauth-client-registration cimd
codex mcp logout quickscribe-oauth-local \
  -c 'mcp_servers.quickscribe-oauth-local.url="http://localhost:5173/mcp"'
```

Protocol references: [MCP authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
and [Claude connector authentication](https://claude.com/docs/connectors/building/authentication).
