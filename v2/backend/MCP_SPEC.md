# QuickScribe v2 MCP Server — Implementation Spec

## Overview

Add an MCP (Model Context Protocol) server to the QuickScribe v2 FastAPI backend, exposing read-only access to recordings, transcripts, participants, and AI chat. This lets LLM clients (Claude Code, Copilot, etc.) search, browse, and extract information from the QuickScribe recording library.

The MCP server is implemented using the `fastapi-mcp` library, which wraps existing FastAPI endpoints as MCP tools with minimal code. Authentication uses bearer tokens (API keys) passed in the `Authorization` header.

---

## Architecture

### Library

**`fastapi-mcp >= 0.4.0`** — mounts an MCP endpoint at `/mcp` on the existing FastAPI app. It automatically converts tagged FastAPI routes into MCP tools. Uses Streamable HTTP transport.

### Auth

MCP clients cannot do OAuth. Instead, users generate API tokens from the QuickScribe settings UI. Tokens are passed as `Authorization: Bearer <token>` headers. The existing `X-API-Key` auth path in QuickScribe already supports this pattern — MCP tokens extend it with dedicated management, scoping, and revocation.

### Read-Only

All MCP-exposed tools are read-only. No create, update, or delete operations are exposed. This is intentional — the MCP surface is for search and information extraction.

---

## Codebase Context

### Existing Project Structure

```
v2/backend/
├── src/app/
│   ├── main.py              # FastAPI app, middleware, router mounting
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── database.py          # SQLite schema, aiosqlite, FTS5, migrations
│   ├── auth.py              # Azure AD JWT + X-API-Key auth
│   ├── models.py            # Pydantic request/response models
│   ├── routers/             # 8 routers (recordings, participants, tags, ai, settings, sync, search, collections)
│   │   ├── recordings.py
│   │   ├── participants.py
│   │   ├── tags.py
│   │   ├── ai.py
│   │   ├── settings.py
│   │   ├── sync.py
│   │   ├── search.py
│   │   └── collections.py
│   ├── services/            # Business logic (recording_service, participant_service, ai_service, deep_search, etc.)
│   └── prompts/             # Jinja2 LLM prompt templates
├── data/app.db              # SQLite database
├── tests/
└── pyproject.toml
```

### Database

SQLite via `aiosqlite` (async). WAL mode. Path from `config.database_path` (default `./data/app.db`).

Key tables for MCP:

- **`recordings`** — `id` (TEXT PK), `user_id` (FK), `title`, `description`, `duration_seconds` (REAL), `recorded_at` (DATETIME), `source` (plaud/upload/paste), `status` (pending/transcoding/transcribing/processing/ready/failed), `transcript_text` (TEXT), `diarized_text` (TEXT), `transcript_json` (TEXT, JSON), `speaker_mapping` (TEXT, JSON), `search_summary` (TEXT), `search_keywords` (TEXT, JSON array), `created_at`
- **`recordings_fts`** — FTS5 virtual table indexing: title, description, diarized_text, transcript_text, search_summary. Auto-synced via triggers.
- **`participants`** — `id` (TEXT PK), `user_id` (FK), `display_name`, `aliases` (TEXT, JSON array), `email`, `role`, `organization`, `relationship`, `is_user` (BOOL), `created_at`
- **`speaker_profiles`** — `id` (PK), `user_id` (FK), `participant_id` (FK), `centroid` (BLOB), `embeddings_blob` (BLOB). Links participants to voice embeddings.
- **`users`** — `id` (TEXT PK), `email`, `name`, `api_key` (TEXT, 32-char), `azure_oid`, `role`

New table (see below): **`mcp_tokens`**

### Existing Auth (`auth.py`)

Two paths today:
1. **Azure AD JWT** — `Authorization: Bearer <jwt>` → validates against Azure AD JWKS
2. **API Key** — `X-API-Key: <key>` → looks up user by `api_key` column in `users` table

The `get_current_user()` dependency tries JWT first, falls back to API key. Dev mode (`AUTH_DISABLED=true`) bypasses both.

### Existing Search

- **FTS5** — `recordings_fts` indexes title, description, diarized_text, transcript_text, search_summary
- **`recording_service.search_recordings()`** — runs `MATCH` query against FTS5, returns up to 50 results
- **`recording_service.list_recordings()`** — if `search` param provided, does FTS5 OR speaker_mapping LIKE
- **`participant_service.search_participants()`** — fuzzy LIKE search on display_name and aliases

---

## New Files

| File | Purpose |
|------|---------|
| `src/app/routers/mcp_tools.py` | New FastAPI router with MCP-specific endpoints, tagged `mcp` |
| `src/app/routers/mcp_tokens.py` | Token management endpoints (create, list, revoke) for the settings UI |
| `src/app/services/mcp_token_service.py` | Token CRUD, hashing, validation logic |
| `src/app/services/mcp_search_service.py` | Tiered/cascading search logic for MCP |
| `tests/test_mcp.py` | Tests for MCP tools and token management |

### Modified Files

| File | Change |
|------|--------|
| `src/app/main.py` | Mount MCP server, include new routers |
| `src/app/database.py` | Add `mcp_tokens` table to schema |
| `src/app/auth.py` | Add MCP bearer token validation to auth chain |
| `src/app/config.py` | No changes needed (token prefix configurable via constant) |
| `src/app/models.py` | Add MCP token models, update RecordingSummary/RecordingDetail |
| `pyproject.toml` | Add `fastapi-mcp >= 0.4.0` dependency |
| Frontend: settings page | Add MCP token management UI section |

---

## Database Changes

### New Table: `mcp_tokens`

```sql
CREATE TABLE IF NOT EXISTS mcp_tokens (
    id              TEXT PRIMARY KEY,           -- 8-char random ID
    user_id         TEXT NOT NULL,              -- FK to users.id
    token_name      TEXT NOT NULL,              -- User-given label
    token_prefix    TEXT NOT NULL,              -- First 6 chars after prefix, for display
    token_hash      TEXT NOT NULL UNIQUE,       -- SHA-256 of raw token
    raw_token       TEXT NOT NULL,              -- Full token, always retrievable
    scopes          TEXT,                       -- JSON array, NULL = all scopes (reserved for future use)
    last_used_at    DATETIME,
    revoked_at      DATETIME,
    created_at      DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_mcp_tokens_user_id ON mcp_tokens (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_mcp_tokens_token_hash ON mcp_tokens (token_hash);
```

Token format: `qs_mcp_` followed by 32 URL-safe random characters.

Tokens are stored in plaintext (`raw_token` column) so they can be viewed anytime from the settings UI. The `token_hash` column (SHA-256) is used for fast lookup during authentication — when a bearer token arrives, hash it and look up by hash.

### Existing Column: `recordings.token_count`

The `token_count INTEGER` column already exists on the `recordings` table. No schema change needed — this is included in search results and recording detail so MCP clients know transcript size before requesting it.

---

## MCP Tools (6 tools)

All tools are read-only. All require a valid MCP bearer token. All filter by the authenticated user's `user_id` (tenant isolation).

### 1. `search_recordings`

The workhorse. Lists, filters, and/or keyword-searches recordings.

**Endpoint:** `GET /api/mcp/recordings`

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | str, optional | None | Search text. If omitted, lists all (with filters). |
| `mode` | enum | `cascade` | Search mode: `title`, `summary`, `full`, `cascade`. Ignored when no query. |
| `participant_id` | str, optional | None | Filter to recordings featuring this participant |
| `date_from` | date, optional | None | Start of date range (inclusive) |
| `date_to` | date, optional | None | End of date range (inclusive) |
| `limit` | int | 20 | Max results (1-100) |
| `offset` | int | 0 | Pagination offset |

**Search Modes (when `query` is provided):**

- **`title`** — FTS5 MATCH on title column only
- **`summary`** — FTS5 MATCH on title + description + search_summary
- **`full`** — FTS5 MATCH on all indexed columns (title, description, diarized_text, transcript_text, search_summary)
- **`cascade`** (default) — Runs title first; if under `limit`, adds summary matches (deduped); if still under `limit`, adds full-text matches (deduped). Each result is tagged with `match_tier` ("title", "summary", "transcript") indicating which tier matched it.

**FTS5 Column Filtering:** SQLite FTS5 supports column filters in MATCH expressions: `title:budget` searches only the title column. For `summary` mode, use `{title description search_summary}:budget`. For `cascade` mode, run three separate queries with increasing column scope.

**FTS5 Query Escaping:** User-provided query strings must be sanitized before use in FTS5 MATCH expressions. Raw punctuation, quotes, and boolean operators (`AND`, `OR`, `NOT`) can cause syntax errors. Normalize by:
1. Stripping special characters except alphanumeric, spaces, and hyphens
2. Wrapping each term in double quotes for literal matching (e.g., `"budget" "review"`)
3. If the sanitized query is empty, fall back to listing without search
If FTS5 still throws a syntax error, catch the exception and return an empty result set with a 200 (not a 500).

**Response:** Array of:
```json
{
  "id": "abc123",
  "title": "Q1 Budget Review",
  "description": "Monthly budget discussion with finance team",
  "duration_seconds": 1842.5,
  "recorded_at": "2026-03-15T14:30:00",
  "source": "plaud",
  "status": "ready",
  "speaker_names": ["Alice", "Bob", "Carol"],
  "tag_ids": ["tag1", "tag2"],
  "token_count": 12450,
  "match_tier": "title"
}
```

`match_tier` is only present when a `query` was provided. `token_count` is always present (null if no transcript yet).

**Implementation Notes:**
- Participant filter: join through `speaker_mapping` JSON — check if any entry has `participantId` matching the given ID. Use `json_each()` with `json_extract()` (not LIKE, which can produce false positives on substring matches).
- Date filter: `WHERE COALESCE(recorded_at, created_at) >= ? AND COALESCE(recorded_at, created_at) <= ?`
- Cascade mode: run up to 3 queries, collect IDs seen so far, exclude them from subsequent tiers. Stop when `limit` reached.
- Order: by `COALESCE(recorded_at, created_at) DESC` (newest first) within each tier.

### 2. `get_recording`

Full metadata for a single recording, including AI summary and simplified speaker info.

**Endpoint:** `GET /api/mcp/recordings/{recording_id}`

**Response:**
```json
{
  "id": "abc123",
  "title": "Q1 Budget Review",
  "description": "Monthly budget discussion with finance team",
  "duration_seconds": 1842.5,
  "recorded_at": "2026-03-15T14:30:00",
  "source": "plaud",
  "status": "ready",
  "search_summary": "Discussion of Q1 budget allocations...",
  "search_keywords": ["budget", "Q1", "finance", "headcount"],
  "speakers": [
    {"label": "Speaker 1", "display_name": "Alice", "participant_id": "p1"},
    {"label": "Speaker 2", "display_name": "Bob", "participant_id": null}
  ],
  "tag_ids": ["tag1", "tag2"],
  "token_count": 12450
}
```

`speakers` is a simplified view of `speaker_mapping` — just label, display_name, and participant_id (if linked). No embeddings, confidence scores, or ML metadata.

### 3. `get_transcription`

Diarized transcript text with token-based pagination.

**Endpoint:** `GET /api/mcp/recordings/{recording_id}/transcript`

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `token_offset` | int | 0 | Start reading from this token position |
| `token_limit` | int | 10000 | Max tokens to return |

**Response:**
```json
{
  "recording_id": "abc123",
  "total_tokens": 12450,
  "returned_tokens": 10000,
  "token_offset": 0,
  "has_more": true,
  "text": "Speaker 1: Good morning everyone...\nSpeaker 2: Thanks for joining..."
}
```

**Implementation Notes:**
- Uses `diarized_text` (preferred) or falls back to `transcript_text`
- Token counting uses the existing `token_count` column for total size. For pagination slicing, approximate by character-to-token ratio (roughly 4 chars per token) and split on turn boundaries.
- Pagination splits on speaker turn boundaries (newlines in diarized_text). When `token_limit` would cut mid-turn, include the full turn. Report actual `returned_tokens`.
- **Oversized single turn:** If the first eligible turn exceeds `token_limit`, return that single turn anyway. `returned_tokens` may exceed `token_limit` in this case — this preserves turn integrity and avoids empty pages or infinite pagination loops.
- If `token_offset` exceeds `total_tokens`, return empty text with `has_more: false`.
- Note: because pagination uses character-to-token approximation, `token_offset` values are approximate. Clients should use the `returned_tokens` from each response to compute the next offset rather than assuming exact token positions.

### 4. `list_participants`

Browse all known speakers for the authenticated user.

**Endpoint:** `GET /api/mcp/participants`

**Response:** Array of:
```json
{
  "id": "p1",
  "display_name": "Alice Chen",
  "aliases": ["Alice", "A. Chen"],
  "email": "alice@example.com",
  "role": "Engineering Manager",
  "organization": "Acme Corp",
  "recording_count": 15
}
```

**Implementation Notes:**
- `recording_count`: count of recordings where this participant appears in `speaker_mapping` (any entry with `participantId` matching). Use `json_each()` with `json_extract()` for accurate matching — not LIKE.
- Ordered by `display_name` ASC.

### 5. `search_participants`

Fuzzy name search across participants. Errs on the side of recall over precision — returns more matches rather than fewer.

**Endpoint:** `GET /api/mcp/participants/search`

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | str | required | Name to search for |
| `limit` | int | 20 | Max results |

**Response:** Same shape as `list_participants`.

**Implementation Notes:**
- Search `display_name` and `aliases` (JSON array) using case-insensitive LIKE with wildcards: `%query%`
- Also search with each word individually for multi-word queries (e.g., "Alice Chen" matches "Alice" or "Chen")
- Consider trigram-style fuzzy: split query into 3-char substrings, match any. This catches typos like "Alce" matching "Alice".
- Rank results: exact display_name match first, then prefix match, then substring match, then alias matches.
- The goal is high recall — if in doubt, include the result. Let the LLM client filter.

### 6. `ai_chat`

Ask a question about a specific recording's transcript, powered by the existing AI chat service.

**Endpoint:** `POST /api/mcp/recordings/{recording_id}/chat`

**Request:**
```json
{
  "message": "What were the main action items discussed?"
}
```

**Response:**
```json
{
  "response": "The main action items were: 1) Alice to finalize the Q1 budget spreadsheet by Friday...",
  "usage": {"prompt_tokens": 8500, "completion_tokens": 250},
  "response_time_ms": 3200
}
```

**Implementation Notes:**
- Calls the existing `ai_service.chat()` function which sends the transcript as context to Azure OpenAI. The existing service already returns `usage` and `response_time_ms` — pass them through.
- Stateless — each call is independent (no conversation history). The MCP client manages its own conversation state.
- For long transcripts, the existing `ai_service.chat()` handles truncation to fit model context limits.
- Returns 400 if the recording has no transcript yet.
- Returns 503 if AI is not configured (`ai_enabled == False`).

---

## MCP Server Setup (`main.py`)

Add to `main.py`, after all routers are mounted but **before** the SPA catch-all:

```python
# ── MCP Server ────────────────────────────────────────────────────────
from fastapi import Depends as _Depends, Request as _Request
from fastapi.security import HTTPBearer as _HTTPBearer, HTTPAuthorizationCredentials as _HTTPAuthCreds
from fastapi_mcp import AuthConfig as _AuthConfig, FastApiMCP as _FastApiMCP

_mcp_bearer_scheme = _HTTPBearer(auto_error=False)

async def _mcp_auth(
    request: _Request,
    creds: _HTTPAuthCreds | None = _Depends(_mcp_bearer_scheme),
) -> None:
    """Require a valid MCP bearer token (qs_mcp_ prefix)."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not creds.credentials.startswith("qs_mcp_"):
        raise HTTPException(status_code=401, detail="Invalid MCP token format")

mcp = _FastApiMCP(
    app,
    name="QuickScribe",
    description="Search, browse, and extract information from audio recordings and transcripts",
    include_tags=["mcp"],
    auth_config=_AuthConfig(
        dependencies=[_Depends(_mcp_auth)],
    ),
)
mcp.mount_http()  # Serves at /mcp
```

Only endpoints tagged `"mcp"` are exposed. The `mcp_tools.py` router uses this tag.

### SPA catch-all fix

The existing SPA catch-all at `/{full_path:path}` only skips `api/`-prefixed paths. It will intercept `/mcp` requests and serve `index.html` instead of the MCP endpoint. Update the catch-all to also exclude MCP paths:

```python
if full_path.startswith("api/") or full_path == "mcp" or full_path.startswith("mcp/"):
    return JSONResponse(status_code=404, content={"detail": "Not found"})
```

### Routing clarification

There are two layers:
- **FastAPI routes** live at `/api/mcp/...` — these are the implementation endpoints in `mcp_tools.py`
- **MCP transport** is served at `/mcp` by `fastapi-mcp` — this is what MCP clients connect to

`fastapi-mcp` discovers the tagged FastAPI routes and exposes them as MCP tools over the `/mcp` transport. MCP clients only ever connect to `/mcp`. The `/api/mcp/...` REST endpoints are not called directly by MCP clients but could be used for testing or non-MCP integrations.

---

## MCP Token Auth Flow

When an MCP request arrives at `/mcp`:

1. `fastapi-mcp` runs the `_mcp_auth` dependency — checks that a Bearer token is present
2. The underlying FastAPI route's own auth dependency (`get_current_user`) fires
3. `get_current_user` is updated to check MCP tokens:
   - Extract token from `Authorization: Bearer qs_mcp_...`
   - If it starts with `qs_mcp_`, hash it (SHA-256), look up in `mcp_tokens` by `token_hash`
   - Verify not revoked, not expired
   - Update `last_used_at`
   - Return the token's `user_id` as the authenticated user
4. If not an MCP token, fall through to existing JWT / API key checks

### Changes to `auth.py`

Add a new function `_try_mcp_token(token: str) -> User | None` that:
1. Checks if token starts with `qs_mcp_` — if not, returns `None` immediately
2. Hashes with SHA-256
3. Queries `mcp_tokens` table by hash
4. Validates not revoked and not expired
5. Updates `last_used_at`
6. Looks up user by `user_id` from the token row
7. Returns `User` or `None`

**Critical insertion point:** This check must run **before** `_validate_token()` is called. In both `get_current_user()` and `get_current_user_or_api_key()`, after extracting the bearer token string, check for the `qs_mcp_` prefix first. If present, route to `_try_mcp_token()`. Only fall through to JWT validation if the token does NOT have the MCP prefix. Without this, MCP tokens will fail JWT decode and return 401.

```python
# In get_current_user_or_api_key() — after extracting bearer token:
token = auth_header[7:]
if token.startswith("qs_mcp_"):
    user = await _try_mcp_token(token)
    if user:
        return user
    raise HTTPException(status_code=401, detail="Invalid or revoked MCP token")
# ... existing JWT validation follows
```

### Auth dependency for MCP tools

The MCP tools router (`mcp_tools.py`) should use `get_current_user_or_api_key` as its auth dependency. This dependency will be updated to handle MCP tokens as described above, so MCP bearer tokens, JWT tokens, and API keys all work through the same function.

---

## Token Management Endpoints

These are for the settings UI, NOT exposed via MCP. Tagged `"settings"`.

### `POST /api/settings/mcp-tokens`

Create a new MCP token.

**Request:**
```json
{
  "name": "My Claude Code token"
}
```

**Response:**
```json
{
  "id": "a1b2c3d4",
  "token_name": "My Claude Code token",
  "token_prefix": "qs_mcp_aB3",
  "raw_token": "qs_mcp_aB3xK9...",
  "last_used_at": null,
  "revoked_at": null,
  "created_at": "2026-04-12T10:30:00"
}
```

**Logic:**
- Generate: `qs_mcp_` + 32 `secrets.token_urlsafe` chars
- Hash: SHA-256 of full token → store in `token_hash`
- Prefix: first 6 chars after `qs_mcp_` → store in `token_prefix` (for display)
- Store raw token in `raw_token` column (always retrievable)
- Max 10 active (non-revoked) tokens per user

### `GET /api/settings/mcp-tokens`

List all tokens for the authenticated user. Returns full `raw_token` on every call (not one-time).

**Response:** Array of token objects (same shape as create response), ordered by `created_at DESC`.

### `DELETE /api/settings/mcp-tokens/{token_id}`

Revoke a token. Sets `revoked_at` to current time. Idempotent.

---

## Token Management UI

Add an "MCP Tokens" section to the existing Settings page (`SettingsPage` in the frontend).

### Display

- Section header: "MCP Access Tokens"
- Brief explanation: "Create tokens to connect LLM tools (Claude Code, Copilot, etc.) to your QuickScribe data."
- Create form: text input for token name + "Create Token" button
- Token list: cards showing each token with:
  - Token name
  - Full raw token in a readonly input field (click to select, copy button)
  - Created date, last used date
  - "Revoke" button (with confirmation)
  - Expandable "MCP Config" section showing a pasteable config snippet

### MCP Config Snippet

Each token card shows a copyable config block:

```json
{
  "mcpServers": {
    "quickscribe": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "{origin}/mcp",
        "--header",
        "Authorization: Bearer {raw_token}"
      ]
    }
  }
}
```

Where `{origin}` is `window.location.origin` and `{raw_token}` is the full token. This can be pasted directly into Claude Code's MCP config or similar tools.

---

## Dependencies

Add to `pyproject.toml`:

```toml
"fastapi-mcp>=0.4.0",
```

---

## Implementation Order

1. **Database changes** — add `mcp_tokens` table to `database.py`.
2. **Token service** — `mcp_token_service.py` with create, list, revoke, validate functions.
3. **Auth integration** — update `auth.py` to check MCP tokens in the auth chain.
4. **Token management router** — `mcp_tokens.py` with create/list/revoke endpoints.
5. **MCP search service** — `mcp_search_service.py` with tiered/cascading search.
6. **MCP tools router** — `mcp_tools.py` with all 6 tool endpoints, tagged `"mcp"`.
7. **MCP server mount** — update `main.py` to create `FastApiMCP` instance and mount.
8. **Frontend** — add MCP token management to settings page.
9. **Tests** — token CRUD, auth flow, each MCP tool, cascading search.

---

## Notes

- **Scopes:** The `scopes` column exists in `mcp_tokens` but is not enforced in v1. Reserved for future use (e.g., limiting a token to read-only participants but not recordings).
- **Rate limiting:** Not implemented in v1. Can be added later via middleware if needed.
- **Token security:** Raw tokens are stored in plaintext in SQLite. This is a deliberate tradeoff for user convenience (always viewable). The threat model assumes the database is not publicly accessible.
- **Token counting:** Uses the existing `token_count` column already computed on recordings. Pagination approximates token positions using character-to-token ratios.
