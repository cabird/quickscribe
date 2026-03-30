"""Collections endpoints — CRUD, items, search-to-add, and collection deep search."""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.models import (
    AddItemsRequest,
    Collection,
    CollectionDetail,
    CollectionSearchRecord,
    CreateCollection,
    CreateFromCandidatesRequest,
    DeepSearchRequest,
    SearchToAddRequest,
    UpdateCollection,
    User,
)
from app.services import collection_service, deep_search

router = APIRouter(prefix="/api/collections", tags=["collections"])

CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Collections CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_collections(user: CurrentUser) -> list[Collection]:
    """List all collections for the current user."""
    rows = await collection_service.list_collections(user.id)
    return [Collection(**r) for r in rows]


@router.post("", status_code=201)
async def create_collection(body: CreateCollection, user: CurrentUser) -> Collection:
    """Create a new collection."""
    result = await collection_service.create_collection(
        user.id, body.name, body.description
    )
    return Collection(**result)


@router.post("/from-candidates", status_code=201)
async def create_from_candidates(
    body: CreateFromCandidatesRequest, user: CurrentUser
) -> CollectionDetail:
    """Create a new collection pre-populated with recordings from search candidates."""
    result = await collection_service.create_from_candidates(
        user.id, body.name, body.recording_ids
    )
    return CollectionDetail(**result)


@router.get("/{collection_id}")
async def get_collection(collection_id: str, user: CurrentUser) -> CollectionDetail:
    """Get a collection with its items."""
    result = await collection_service.get_collection(user.id, collection_id)
    if not result:
        raise HTTPException(status_code=404, detail="Collection not found")
    return CollectionDetail(**result)


@router.put("/{collection_id}")
async def update_collection(
    collection_id: str, body: UpdateCollection, user: CurrentUser
) -> Collection:
    """Update a collection's name and/or description."""
    result = await collection_service.update_collection(
        user.id, collection_id, body.name, body.description
    )
    if not result:
        raise HTTPException(status_code=404, detail="Collection not found")
    return Collection(**result)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, user: CurrentUser):
    """Delete a collection."""
    deleted = await collection_service.delete_collection(user.id, collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")


# ---------------------------------------------------------------------------
# Collection download (zip of transcripts)
# ---------------------------------------------------------------------------


def _sanitize_filename(name: str) -> str:
    """Replace special characters with underscores for clean filenames."""
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized or "Untitled"


def _format_duration(seconds: float | None) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds is None:
        return "Unknown"
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


@router.get("/{collection_id}/download")
async def download_collection(collection_id: str, user: CurrentUser):
    """Download all transcripts in a collection as a zip file."""
    # Get collection name for the zip filename
    col = await collection_service.get_collection(user.id, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    transcripts = await collection_service.get_collection_transcripts(
        user.id, collection_id
    )
    if not transcripts:
        raise HTTPException(
            status_code=404, detail="No transcripts found in collection"
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        seen_names: dict[str, int] = {}
        for t in transcripts:
            title = _sanitize_filename(t["title"])
            date_str = t["date"][:10] if t["date"] else "no_date"
            base_name = f"{title}_{date_str}"

            # Deduplicate filenames
            if base_name in seen_names:
                seen_names[base_name] += 1
                file_name = f"{base_name} ({seen_names[base_name]}).txt"
            else:
                seen_names[base_name] = 0
                file_name = f"{base_name}.txt"

            speakers = ", ".join(t["speakers"]) if t["speakers"] else "Unknown"
            duration = _format_duration(t["duration_seconds"])

            content = (
                f"Title: {t['title']}\n"
                f"Date: {date_str}\n"
                f"Speakers: {speakers}\n"
                f"Duration: {duration}\n"
                f"\n---\n\n"
                f"{t['transcript_text']}"
            )
            zf.writestr(file_name, content)

    buf.seek(0)
    safe_collection_name = _sanitize_filename(col["name"])
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_collection_name}.zip"'
        },
    )


# ---------------------------------------------------------------------------
# Collection items
# ---------------------------------------------------------------------------


@router.post("/{collection_id}/items")
async def add_items(
    collection_id: str, body: AddItemsRequest, user: CurrentUser
):
    """Add recordings to a collection. Skips duplicates."""
    result = await collection_service.add_items(
        user.id, collection_id, body.recording_ids
    )
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Collection not found")
    return result


@router.delete("/{collection_id}/items/{recording_id}", status_code=204)
async def remove_item(
    collection_id: str, recording_id: str, user: CurrentUser
):
    """Remove a recording from a collection."""
    removed = await collection_service.remove_item(
        user.id, collection_id, recording_id
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found in collection")


@router.post("/{collection_id}/items/search")
async def search_to_add(
    collection_id: str, body: SearchToAddRequest, user: CurrentUser
):
    """Search recordings to add to a collection. Returns results with in_collection flag."""
    results = await collection_service.search_to_add(
        user.id,
        collection_id,
        query=body.query,
        date_from=body.date_from,
        date_to=body.date_to,
        speaker=body.speaker,
    )
    return results


# ---------------------------------------------------------------------------
# Collection deep search (SSE)
# ---------------------------------------------------------------------------


@router.post("/{collection_id}/search")
async def collection_search(
    collection_id: str, body: DeepSearchRequest, user: CurrentUser
):
    """Run deep search on a collection's recordings (Tier 2 + 3 only).

    Returns an SSE stream with progress events and the final result.
    """

    async def event_stream():
        async for event in deep_search.search_collection(
            body.question, collection_id, user.id
        ):
            event_type = event.get("event", "status")
            data = event.get("data", "")
            if isinstance(data, (dict, list)):
                data = json.dumps(data)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Collection search history
# ---------------------------------------------------------------------------


@router.get("/{collection_id}/searches")
async def get_search_history(
    collection_id: str, user: CurrentUser
) -> list[CollectionSearchRecord]:
    """Return past searches for a collection."""
    rows = await collection_service.get_search_history(user.id, collection_id)
    return [CollectionSearchRecord(**r) for r in rows]
