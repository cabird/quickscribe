"""SQLite-backed speaker profile storage.

Replaces v1's Azure Blob-based profile store. Stores centroids and individual
embeddings as BLOBs (raw float32 bytes) for compact, fast storage.

Each user's speaker profiles live in the `speaker_profiles` table.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import numpy as np

from app.database import get_db

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 192
MAX_EMBEDDINGS_PER_PROFILE = 100


def _serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize a single embedding to raw float32 bytes."""
    return embedding.astype(np.float32).tobytes()


def _deserialize_embedding(blob: bytes) -> np.ndarray:
    """Deserialize a single embedding from raw float32 bytes."""
    return np.frombuffer(blob, dtype=np.float32).copy()


def _serialize_embeddings(embeddings: list[np.ndarray]) -> bytes:
    """Serialize a list of embeddings to a single BLOB."""
    if not embeddings:
        return b""
    return np.stack(embeddings).astype(np.float32).tobytes()


def _deserialize_embeddings(blob: bytes | None, dim: int = EMBEDDING_DIM) -> list[np.ndarray]:
    """Deserialize a BLOB into a list of embedding arrays."""
    if not blob:
        return []
    mat = np.frombuffer(blob, dtype=np.float32).reshape(-1, dim)
    return [mat[i].copy() for i in range(len(mat))]


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2 normalize a vector."""
    return v / (np.linalg.norm(v) + 1e-12)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings."""
    a_norm = _l2_normalize(a)
    b_norm = _l2_normalize(b)
    return float(np.dot(a_norm, b_norm))


def _compute_centroid(embeddings: list[np.ndarray]) -> np.ndarray:
    """Compute L2-normalized centroid from a list of embeddings."""
    mat = np.stack(embeddings, axis=0)
    return _l2_normalize(mat.mean(axis=0))


def _compute_embedding_std(embeddings: list[np.ndarray], centroid: np.ndarray) -> float | None:
    """Compute std of cosine similarities between embeddings and centroid."""
    if len(embeddings) < 2:
        return None
    distances = [1.0 - _cosine_similarity(e, centroid) for e in embeddings]
    return float(np.std(distances))


async def get_profiles(user_id: str) -> list[dict]:
    """Load all speaker profiles for a user.

    Returns:
        List of dicts with keys: participant_id, display_name, centroid,
        embeddings, recording_ids, n_samples, embedding_std.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, participant_id, display_name, centroid, n_samples,
                  embeddings_blob, recording_ids, embedding_std
           FROM speaker_profiles WHERE user_id = ?""",
        (user_id,),
    )

    profiles = []
    for row in rows:
        r = dict(row)
        centroid = _deserialize_embedding(r["centroid"]) if r["centroid"] else None
        embeddings = _deserialize_embeddings(r["embeddings_blob"])
        recording_ids = json.loads(r["recording_ids"]) if r["recording_ids"] else []
        profiles.append({
            "id": r["id"],
            "participant_id": r["participant_id"],
            "display_name": r["display_name"],
            "centroid": centroid,
            "embeddings": embeddings,
            "recording_ids": recording_ids,
            "n_samples": r["n_samples"] or 0,
            "embedding_std": r["embedding_std"],
        })

    return profiles


async def save_profile(
    user_id: str,
    participant_id: str,
    display_name: str,
    centroid: np.ndarray | None,
    embeddings: list[np.ndarray],
    recording_ids: list[str],
    n_samples: int,
    embedding_std: float | None = None,
) -> None:
    """Upsert a speaker profile.

    Uses INSERT OR REPLACE on the (user_id, participant_id) unique constraint.
    """
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Check if profile exists
    existing = await db.execute_fetchall(
        "SELECT id FROM speaker_profiles WHERE user_id = ? AND participant_id = ?",
        (user_id, participant_id),
    )

    centroid_blob = _serialize_embedding(centroid) if centroid is not None else None
    embeddings_blob = _serialize_embeddings(embeddings) if embeddings else None

    if existing:
        profile_id = dict(existing[0])["id"]
        await db.execute(
            """UPDATE speaker_profiles
               SET display_name = ?, centroid = ?, n_samples = ?,
                   embeddings_blob = ?, recording_ids = ?, embedding_std = ?,
                   updated_at = ?
               WHERE id = ?""",
            (
                display_name,
                centroid_blob,
                n_samples,
                embeddings_blob,
                json.dumps(recording_ids),
                embedding_std,
                now,
                profile_id,
            ),
        )
    else:
        profile_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO speaker_profiles
               (id, user_id, participant_id, display_name, centroid, n_samples,
                embeddings_blob, recording_ids, embedding_std, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id,
                user_id,
                participant_id,
                display_name,
                centroid_blob,
                n_samples,
                embeddings_blob,
                json.dumps(recording_ids),
                embedding_std,
                now,
                now,
            ),
        )

    await db.commit()


async def match_speaker(
    user_id: str,
    embedding: np.ndarray,
    threshold: float = 0.40,
    top_n: int = 5,
) -> dict:
    """Find the best matching profile for an embedding.

    Args:
        user_id: Owner of the profiles.
        embedding: 192-dim query embedding.
        threshold: Minimum cosine similarity to consider.
        top_n: Number of top candidates to return.

    Returns:
        Dict with keys: participant_id, display_name, similarity, top_candidates.
        participant_id is None if best match is below threshold.
    """
    profiles = await get_profiles(user_id)

    if not profiles:
        return {
            "participant_id": None,
            "display_name": None,
            "similarity": None,
            "top_candidates": [],
        }

    embedding_norm = _l2_normalize(embedding)
    results = []

    for profile in profiles:
        if profile["centroid"] is None:
            continue
        sim = _cosine_similarity(embedding_norm, profile["centroid"])
        results.append({
            "participant_id": profile["participant_id"],
            "display_name": profile["display_name"],
            "similarity": round(sim, 4),
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    top_candidates = [c for c in results[:top_n] if c["similarity"] >= threshold]

    if not top_candidates:
        return {
            "participant_id": None,
            "display_name": None,
            "similarity": None,
            "top_candidates": [],
        }

    best = top_candidates[0]
    return {
        "participant_id": best["participant_id"],
        "display_name": best["display_name"],
        "similarity": best["similarity"],
        "top_candidates": top_candidates,
    }


async def update_profile_with_embedding(
    user_id: str,
    participant_id: str,
    new_embedding: np.ndarray,
    recording_id: str,
) -> None:
    """Add an embedding to an existing profile, recomputing the centroid.

    If the profile does not exist, creates one. Caps embeddings at
    MAX_EMBEDDINGS_PER_PROFILE, dropping the oldest when exceeded.
    """
    db = await get_db()

    # Load existing profile
    rows = await db.execute_fetchall(
        """SELECT id, display_name, centroid, embeddings_blob, recording_ids, n_samples
           FROM speaker_profiles WHERE user_id = ? AND participant_id = ?""",
        (user_id, participant_id),
    )

    new_emb_norm = _l2_normalize(new_embedding)

    if rows:
        r = dict(rows[0])
        embeddings = _deserialize_embeddings(r["embeddings_blob"])
        recording_ids = json.loads(r["recording_ids"]) if r["recording_ids"] else []
        display_name = r["display_name"]
    else:
        embeddings = []
        recording_ids = []
        # Look up display name from participants table
        p_rows = await db.execute_fetchall(
            "SELECT display_name FROM participants WHERE id = ? AND user_id = ?",
            (participant_id, user_id),
        )
        display_name = dict(p_rows[0])["display_name"] if p_rows else participant_id

    # Add new embedding
    embeddings.append(new_emb_norm)
    if recording_id and recording_id not in recording_ids:
        recording_ids.append(recording_id)

    # Cap at max
    if len(embeddings) > MAX_EMBEDDINGS_PER_PROFILE:
        excess = len(embeddings) - MAX_EMBEDDINGS_PER_PROFILE
        embeddings = embeddings[excess:]
        # Also trim recording_ids if they exceed (keep in sync approximately)
        if len(recording_ids) > MAX_EMBEDDINGS_PER_PROFILE:
            recording_ids = recording_ids[-MAX_EMBEDDINGS_PER_PROFILE:]

    # Recompute centroid
    centroid = _compute_centroid(embeddings)
    embedding_std = _compute_embedding_std(embeddings, centroid)

    await save_profile(
        user_id=user_id,
        participant_id=participant_id,
        display_name=display_name,
        centroid=centroid,
        embeddings=embeddings,
        recording_ids=recording_ids,
        n_samples=len(embeddings),
        embedding_std=embedding_std,
    )


async def rebuild_all_profiles(user_id: str) -> int:
    """Rebuild all speaker profiles from verified speaker_mapping embeddings.

    Scans all recordings for the user, collects embeddings from manually verified
    entries, and rebuilds profiles from scratch. Creates a sync_run with
    type='profile_rebuild' and logs progress in real time.

    Returns:
        Number of profiles rebuilt.
    """
    from app.services.run_logger import RunLogger
    from app.services.sync_service import _create_sync_run, _finish_sync_run
    from app.models import SyncRunStatus

    # Create a tracked run for this rebuild
    run_id = await _create_sync_run("manual", run_type="profile_rebuild")
    run_logger = RunLogger(run_id)

    db = await get_db()

    await run_logger.info("Starting profile rebuild for user %s" % user_id[:8])

    # Delete existing profiles for this user
    await db.execute("DELETE FROM speaker_profiles WHERE user_id = ?", (user_id,))
    await db.commit()
    await run_logger.info("Cleared existing profiles")

    # Gather all recordings with speaker mappings
    rows = await db.execute_fetchall(
        "SELECT id, speaker_mapping FROM recordings WHERE user_id = ? AND speaker_mapping IS NOT NULL",
        (user_id,),
    )

    await run_logger.info("Scanning %d recording(s) for verified embeddings" % len(rows))

    # Collect: participant_id -> [(embedding, recording_id)]
    participant_data: dict[str, list[tuple[np.ndarray, str]]] = {}

    for row in rows:
        r = dict(row)
        recording_id = r["id"]
        try:
            mapping = json.loads(r["speaker_mapping"])
        except (json.JSONDecodeError, TypeError):
            continue

        for label, entry in mapping.items():
            if not isinstance(entry, dict):
                continue

            # Only use manually verified entries
            verified = entry.get("manuallyVerified", False)
            if not verified:
                continue

            pid = entry.get("participantId")
            if not pid:
                continue

            emb_data = entry.get("embedding")
            if not emb_data or not isinstance(emb_data, list):
                continue

            embedding = np.array(emb_data, dtype=np.float32)
            if embedding.shape != (EMBEDDING_DIM,):
                continue

            participant_data.setdefault(pid, []).append((_l2_normalize(embedding), recording_id))

    await run_logger.info(
        "Found %d participant(s) with verified embeddings" % len(participant_data)
    )

    # Build profiles
    count = 0
    for participant_id, entries in participant_data.items():
        # Look up display name
        p_rows = await db.execute_fetchall(
            "SELECT display_name FROM participants WHERE id = ? AND user_id = ?",
            (participant_id, user_id),
        )
        display_name = dict(p_rows[0])["display_name"] if p_rows else participant_id

        # Cap embeddings
        if len(entries) > MAX_EMBEDDINGS_PER_PROFILE:
            entries = entries[-MAX_EMBEDDINGS_PER_PROFILE:]

        embeddings = [e for e, _ in entries]
        recording_ids = list(dict.fromkeys(rid for _, rid in entries))  # unique, order preserved

        centroid = _compute_centroid(embeddings)
        embedding_std = _compute_embedding_std(embeddings, centroid)

        await save_profile(
            user_id=user_id,
            participant_id=participant_id,
            display_name=display_name,
            centroid=centroid,
            embeddings=embeddings,
            recording_ids=recording_ids,
            n_samples=len(embeddings),
            embedding_std=embedding_std,
        )
        count += 1
        await run_logger.info(
            "Built profile: %s (%d embedding(s) from %d recording(s))"
            % (display_name, len(embeddings), len(recording_ids))
        )

    logger.info("Rebuilt %d speaker profiles for user %s", count, user_id)
    await run_logger.info("Rebuild complete: %d profile(s)" % count)
    await _finish_sync_run(
        run_id, SyncRunStatus.completed,
        stats={"profiles_rebuilt": count, "recordings_scanned": len(rows)},
    )
    return count
