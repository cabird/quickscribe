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
    description="Search, browse, and extract information from audio recordings and transcripts",
    include_tags=["mcp"],
    auth_config=_AuthConfig(
        dependencies=[_Depends(_mcp_auth)],
    ),
)
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
