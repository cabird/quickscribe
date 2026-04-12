"""FastAPI application — entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import close_db, init_db
from app.scheduler.jobs import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend-dist"


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    # Startup validation
    if not settings.auth_disabled and not settings.azure_client_id:
        raise RuntimeError(
            "AUTH_DISABLED is False but AZURE_CLIENT_ID is not set. "
            "Either set AZURE_CLIENT_ID or set AUTH_DISABLED=true for development."
        )

    await init_db()
    logger.info("Database initialized")

    # Mark any stale "running" sync runs as aborted (server died/restarted mid-job)
    from app.database import get_db as _get_db
    from app.models import SyncRunStatus
    db = await _get_db()
    result = await db.execute(
        """UPDATE sync_runs
           SET status = ?, error_message = ?, finished_at = datetime('now')
           WHERE status = ?""",
        (
            SyncRunStatus.aborted.value,
            "Process restarted before job completed",
            SyncRunStatus.running.value,
        ),
    )
    await db.commit()
    if result.rowcount:
        logger.warning("Marked %d stale running sync run(s) as aborted", result.rowcount)

    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    await close_db()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title="QuickScribe",
    version=settings.api_version,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.routers import ai, collections, mcp_tokens, mcp_tools, participants, recordings, search, settings as settings_router, sync, tags  # noqa: E402

app.include_router(recordings.router)
app.include_router(participants.router)
app.include_router(tags.router)
app.include_router(ai.router)
app.include_router(settings_router.router)
app.include_router(sync.router)
app.include_router(search.router)
app.include_router(collections.router)
app.include_router(mcp_tokens.router)
app.include_router(mcp_tools.router)


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["system"])
async def health():
    """Health check."""
    return {"status": "ok", "version": settings.api_version}


@app.get("/api/version", tags=["system"])
async def version():
    """API version."""
    return {"version": settings.api_version}


# ---------------------------------------------------------------------------
# Local blob serving (dev mode only)
# ---------------------------------------------------------------------------

if settings.use_local_storage:
    from fastapi.responses import Response

    @app.get("/api/blobs/{blob_path:path}", tags=["storage"])
    async def serve_local_blob(blob_path: str):
        """Serve audio files from local blob directory (dev mode only)."""
        blob_dir = Path(settings.local_blob_path).resolve()
        file_path = (blob_dir / blob_path).resolve()
        # Prevent path traversal
        if not file_path.is_relative_to(blob_dir):
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        if not file_path.is_file():
            return JSONResponse(status_code=404, content={"detail": "File not found"})
        return FileResponse(file_path, media_type="audio/mpeg")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

from fastapi import Depends as _Depends
from fastapi.security import HTTPBearer as _HTTPBearer, HTTPAuthorizationCredentials as _HTTPAuthCreds
from fastapi_mcp import AuthConfig as _AuthConfig, FastApiMCP as _FastApiMCP
from app.services.mcp_token_service import TOKEN_PREFIX as _MCP_PREFIX

_mcp_bearer_scheme = _HTTPBearer(auto_error=False)


async def _mcp_auth(
    creds: _HTTPAuthCreds | None = _Depends(_mcp_bearer_scheme),
) -> None:
    """Require a valid MCP bearer token (qs_mcp_ prefix)."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not creds.credentials.startswith(_MCP_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid MCP token format")


mcp = _FastApiMCP(
    app,
    name="QuickScribe",
    description="Read-only audio recording library with transcripts, speaker identification, and AI summaries",
    include_tags=["mcp"],
    auth_config=_AuthConfig(
        dependencies=[_Depends(_mcp_auth)],
    ),
)
mcp.server.instructions = """QuickScribe is a read-only audio recording library for finding, inspecting, and \
extracting information from personal recordings and transcripts. Recordings may come from a Plaud wearable \
recorder or from manual uploads/pasted text. Each recording can include AI-generated titles, descriptions, \
retrieval-oriented summaries, full transcripts, identified speakers linked to known participants, and metadata \
such as recording date, duration, tags, and transcript token count.

Use this server as a staged retrieval workflow rather than jumping straight into transcript extraction. Start \
with search_recordings to find relevant recordings by topic, date range, participant, or transcript content. \
Then use get_recording to inspect the most promising items, especially the AI-generated search_summary, \
keywords, and normalized speaker information. Use token_count to judge transcript size before requesting full \
text. When you need exact wording or source evidence, call get_transcription; when you need a focused answer \
about a single recording, use ai_chat.

This server is optimized for fan-out investigation across multiple recordings. It is often effective to search \
broadly, inspect several candidate recordings in parallel, and then extract transcripts or ask targeted \
questions only for the most relevant ones. search_recordings supports a cascade mode that searches titles \
first, then AI summaries, then full transcript text; this is usually the best default because it surfaces \
likely matches quickly while still falling back to deeper transcript search when needed.

Participants are first-class entities. Use list_participants to browse the known speaker directory and \
search_participants for fuzzy, high-recall name matching across display names and aliases. Once you identify \
a participant, pass their participant_id into search_recordings to narrow results. All tools are read-only. \
ai_chat is stateless per call, scoped to a single recording, and depends on transcript availability and AI \
configuration."""
mcp.mount_http()  # Serves at /mcp


# ---------------------------------------------------------------------------
# Static files / SPA catch-all
# ---------------------------------------------------------------------------

if FRONTEND_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(request: Request, full_path: str):
        """Serve index.html for all non-API paths (SPA routing)."""
        # Don't intercept API or MCP routes
        if full_path.startswith("api/") or full_path == "mcp" or full_path.startswith("mcp/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        # Serve actual static files if they exist
        file_path = FRONTEND_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Fall back to index.html for SPA routing
        index = FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"detail": "Frontend not built"})
