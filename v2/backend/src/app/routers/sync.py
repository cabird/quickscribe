"""Sync endpoints — trigger sync, view sync runs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.database import get_db
from app.models import PaginatedResponse, SyncRunDetail, SyncRunSummary, User
from app.services import sync_service

router = APIRouter(prefix="/api/sync", tags=["sync"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/trigger", status_code=202)
async def trigger_sync(user: CurrentUser):
    """Manually trigger a Plaud sync for the current user."""
    run = await sync_service.run_sync(trigger="manual", user_id=user.id)
    return {"run_id": run.id, "message": "Sync started"}


@router.post("/poll", status_code=200)
async def poll_transcriptions(user: CurrentUser):
    """Manually trigger a poll for pending transcriptions."""
    completed = await sync_service.poll_pending_transcriptions()
    return {"completed": completed, "count": len(completed)}


@router.get("/runs", response_model=PaginatedResponse)
async def list_sync_runs(
    user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    type: str | None = None,
):
    """List sync runs (paginated, optionally filtered by status and/or type)."""
    result = await sync_service.get_sync_runs(
        page=page,
        per_page=per_page,
        status_filter=status,
        type_filter=type,
    )
    return result


@router.get("/runs/{run_id}", response_model=SyncRunDetail)
async def get_sync_run(run_id: str, user: CurrentUser):
    """Get sync run detail with logs."""
    run = await sync_service.get_sync_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sync run not found")
    return run


@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str, user: CurrentUser, after: int = 0):
    """Get log entries for a run, optionally after a given ID for polling."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, timestamp, level, message FROM run_logs WHERE run_id = ? AND id > ? ORDER BY id ASC",
        (run_id, after),
    )
    return {
        "logs": [dict(r) for r in rows],
        "run_id": run_id,
    }
