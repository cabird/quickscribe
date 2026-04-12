"""Speaker identification logic.

Core pipeline: processes a recording's speakers, matches against profiles,
and writes results to speaker_mapping. All PyTorch work runs synchronously
and should be called via asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone

import numpy as np

from app.config import get_settings
from app.database import get_db
from app.services import profile_store, storage_service
from app.services.embedding_engine import (
    EmbeddingEngine,
    get_engine,
    l2_normalize,
    merge_adjacent_segments,
)

logger = logging.getLogger(__name__)

# Module-level lock prevents concurrent speaker ID operations
# (manual trigger + sync overlap, or concurrent model access)
_speaker_id_lock = asyncio.Lock()

# Thresholds — loaded from config at runtime
def _thresholds():
    from app.config import get_settings
    s = get_settings()
    return s.speaker_id_auto_threshold, s.speaker_id_suggest_threshold

AUTO_THRESHOLD = 0.78  # fallback defaults; use _thresholds() in hot paths
SUGGEST_THRESHOLD = 0.68
MIN_CANDIDATE_THRESHOLD = 0.40

# Segment selection constants
MAX_SEGMENTS_PER_SPEAKER = 15
MIN_DURATION = 2.0
EDGE_TRIM = 3.0
TRIM_THRESHOLD = 10.0
CENTER_WINDOW = 10.0


def _parse_diarization(transcript_json_str: str) -> list[tuple[float, float, str]]:
    """Parse diarization segments from Azure Speech transcript JSON.

    Handles both dict (recognizedPhrases) and list-of-segments formats.

    Returns:
        List of (start_s, end_s, speaker_label) tuples.
    """
    try:
        transcript_data = json.loads(transcript_json_str)
    except (json.JSONDecodeError, TypeError):
        return []

    segments = []

    if isinstance(transcript_data, dict):
        phrases = transcript_data.get("recognizedPhrases", [])
        for phrase in phrases:
            speaker = phrase.get("speaker", 0)
            offset = phrase.get("offsetInTicks", 0) / 10_000_000
            duration = phrase.get("durationInTicks", 0) / 10_000_000
            segments.append((offset, offset + duration, f"Speaker {speaker}"))
    elif isinstance(transcript_data, list):
        for seg in transcript_data:
            if isinstance(seg, dict):
                start = seg.get("start", seg.get("offset", 0))
                end = seg.get("end", start + seg.get("duration", 0))
                speaker = seg.get("speaker", seg.get("speakerLabel", "Speaker 0"))
                if isinstance(speaker, int):
                    speaker = f"Speaker {speaker}"
                segments.append((float(start), float(end), speaker))

    return segments


def _process_recording_sync(
    engine: EmbeddingEngine,
    audio_path: str,
    diarization: list[tuple[float, float, str]],
    existing_mapping: dict,
    profiles: list[dict],
) -> dict[str, dict]:
    """Synchronous speaker identification — runs in a thread.

    Args:
        engine: Loaded EmbeddingEngine.
        audio_path: Path to local audio file.
        diarization: Parsed diarization segments.
        existing_mapping: Current speaker_mapping dict.
        profiles: User's speaker profiles (from profile_store.get_profiles).

    Returns:
        Dict mapping speaker_label to identification result dict.
    """
    # Determine which speakers to skip
    skip_speakers = set()
    needs_embedding_only = set()  # Verified but missing embedding

    for label, data in existing_mapping.items():
        if isinstance(data, dict):
            ex = data
        elif hasattr(data, "model_dump"):
            ex = data.model_dump()
        else:
            ex = {}

        id_status = ex.get("identificationStatus")
        if id_status == "dismissed":
            skip_speakers.add(label)
        elif ex.get("manuallyVerified", False):
            # Training is automatic for verified speakers
            if not ex.get("embedding"):
                needs_embedding_only.add(label)
                logger.info("Need embedding for verified %s (no embedding stored)", label)
            else:
                skip_speakers.add(label)

    # Check what's left
    all_speakers = set(s for _, _, s in diarization)
    active_speakers = all_speakers - skip_speakers
    if not active_speakers:
        logger.info("All speakers verified/dismissed, nothing to do")
        return {}

    if skip_speakers:
        logger.info("Skipping (verified/dismissed): %s", skip_speakers)

    # Select top N longest segments per speaker
    speaker_segments: dict[str, list[tuple[float, float]]] = {}
    for start_s, end_s, spk in diarization:
        if spk in skip_speakers:
            continue
        dur = end_s - start_s
        if dur >= MIN_DURATION:
            speaker_segments.setdefault(spk, []).append((start_s, end_s))

    selected_segments: list[tuple[float, float]] = []
    selected_labels: list[str] = []
    for spk, segs in speaker_segments.items():
        segs.sort(key=lambda x: x[1] - x[0], reverse=True)
        top = segs[:MAX_SEGMENTS_PER_SPEAKER]
        selected_segments.extend(top)
        selected_labels.extend([spk] * len(top))

    logger.info(
        "Selected %d segments across %d speakers",
        len(selected_segments),
        len(speaker_segments),
    )

    # Load audio and extract embeddings
    wav, sr = engine.load_audio_mono_16k(audio_path)
    local_embs: dict[str, list[np.ndarray]] = {}

    for (start_s, end_s), spk in zip(selected_segments, selected_labels):
        dur = end_s - start_s
        # Edge trim on long segments
        if dur >= TRIM_THRESHOLD:
            start_s += EDGE_TRIM
            end_s -= EDGE_TRIM
            dur = end_s - start_s
        # Center-window to max
        if dur > CENTER_WINDOW:
            mid = (start_s + end_s) / 2.0
            start_s = mid - CENTER_WINDOW / 2.0
            end_s = mid + CENTER_WINDOW / 2.0

        seg = engine.slice_audio(wav, sr, start_s, end_s)
        if seg.shape[1] < int(MIN_DURATION * sr):
            continue

        emb = engine.embedding_from_waveform(seg)
        local_embs.setdefault(spk, []).append(l2_normalize(emb))

    # Build per-speaker centroids
    centroids: dict[str, np.ndarray] = {}
    for spk, embs in local_embs.items():
        mat = np.stack(embs, axis=0)
        centroids[spk] = l2_normalize(mat.mean(axis=0))

    logger.info("Built centroids for %d speakers", len(centroids))

    # Build in-memory profile lookup for matching
    profile_centroids = []
    for p in profiles:
        if p["centroid"] is not None:
            profile_centroids.append(p)

    # Match each speaker against profiles
    results: dict[str, dict] = {}
    auto_matches: dict[str, str] = {}  # participant_id -> speaker_label

    for speaker_label, centroid in centroids.items():
        # For verified speakers that just need embedding extraction
        if speaker_label in needs_embedding_only:
            results[speaker_label] = {
                "status": "embedding_only",
                "participantId": None,
                "similarity": None,
                "topCandidates": [],
                "embedding": centroid.tolist(),
            }
            logger.info("  %s: extracted embedding for training (verified)", speaker_label)
            continue

        # Match against all profiles
        embedding_norm = l2_normalize(centroid)
        candidates = []
        for p in profile_centroids:
            a_norm = embedding_norm
            b_norm = l2_normalize(p["centroid"])
            sim = float(np.dot(a_norm, b_norm))
            candidates.append({
                "participantId": p["participant_id"],
                "displayName": p["display_name"],
                "similarity": round(sim, 4),
            })

        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        top_candidates = [c for c in candidates[:5] if c["similarity"] >= MIN_CANDIDATE_THRESHOLD]

        if not top_candidates:
            result = {
                "status": "unknown",
                "participantId": None,
                "similarity": None,
                "topCandidates": [],
                "embedding": centroid.tolist(),
            }
        else:
            best = top_candidates[0]
            best_sim = best["similarity"]

            auto_t, suggest_t = _thresholds()
            if best_sim >= auto_t:
                status = "auto"
                best_id = best["participantId"]
            elif best_sim >= suggest_t:
                status = "suggest"
                best_id = best["participantId"]
            else:
                status = "unknown"
                best_id = None

            result = {
                "status": status,
                "participantId": best_id,
                "similarity": best_sim,
                "topCandidates": top_candidates,
                "embedding": centroid.tolist(),
            }

        # Duplicate auto-match detection
        if result["status"] == "auto" and result["participantId"]:
            pid = result["participantId"]
            if pid in auto_matches:
                prev_label = auto_matches[pid]
                prev_sim = results[prev_label]["similarity"]
                curr_sim = result["similarity"]

                if curr_sim > prev_sim:
                    results[prev_label]["status"] = "suggest"
                    logger.info(
                        "Duplicate auto-match for %s: keeping %s (%.3f), demoting %s (%.3f)",
                        pid, speaker_label, curr_sim, prev_label, prev_sim,
                    )
                    auto_matches[pid] = speaker_label
                else:
                    result["status"] = "suggest"
                    logger.info(
                        "Duplicate auto-match for %s: keeping %s (%.3f), demoting %s (%.3f)",
                        pid, prev_label, prev_sim, speaker_label, curr_sim,
                    )
            else:
                auto_matches[pid] = speaker_label

        results[speaker_label] = result
        logger.info(
            "  %s: %s (sim=%s, pid=%s)",
            speaker_label,
            result["status"],
            f"{result['similarity']:.3f}" if result["similarity"] else "N/A",
            result["participantId"] or "none",
        )

    return results


async def process_recording(
    user_id: str,
    recording_id: str,
    run_logger=None,
) -> bool:
    """Main entry point: identify speakers for a recording.

    Acquires the speaker ID lock, downloads audio, runs embedding extraction
    in a thread, matches against profiles, and updates the database.

    Args:
        user_id: Owner of the recording.
        recording_id: Recording to process.
        run_logger: Optional RunLogger for real-time log entries.

    Returns:
        True if identification was performed, False if skipped.
    """
    settings = get_settings()
    db = await get_db()

    # Load recording
    rows = await db.execute_fetchall(
        """SELECT id, user_id, file_path, source, transcript_json, speaker_mapping
           FROM recordings WHERE id = ? AND user_id = ?""",
        (recording_id, user_id),
    )
    if not rows:
        logger.warning("Recording %s not found for user %s", recording_id, user_id)
        return False

    rec = dict(rows[0])

    # Skip paste recordings (no audio)
    if rec["source"] == "paste":
        logger.info("Skipping speaker ID for paste recording %s", recording_id)
        return False

    # Skip if no audio file
    if not rec["file_path"]:
        logger.warning("No audio file for recording %s, skipping speaker ID", recording_id)
        return False

    # Skip if no transcript
    if not rec["transcript_json"]:
        logger.warning("No transcript JSON for recording %s, skipping speaker ID", recording_id)
        return False

    # Parse diarization
    diarization = _parse_diarization(rec["transcript_json"])
    if not diarization:
        logger.warning("No diarization segments for recording %s", recording_id)
        return False

    # Merge adjacent segments
    diarization = merge_adjacent_segments(diarization)

    if run_logger:
        all_spk = set(s for _, _, s in diarization)
        await run_logger.info(
            "Processing recording %s: %d segments, %d speakers"
            % (recording_id[:8], len(diarization), len(all_spk))
        )

    # Load existing speaker mapping
    existing_mapping = {}
    if rec["speaker_mapping"]:
        try:
            existing_mapping = json.loads(rec["speaker_mapping"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Load profiles
    profiles = await profile_store.get_profiles(user_id)

    # Download audio to temp file
    suffix = os.path.splitext(rec["file_path"])[1] or ".mp3"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()

    try:
        await storage_service.download_file(rec["file_path"], tmp.name)
    except Exception as exc:
        logger.warning("Failed to download audio for %s: %s", recording_id, exc)
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        return False

    try:
        # Run CPU-bound work in thread
        engine = get_engine(settings.speaker_id_model_path)
        results = await asyncio.to_thread(
            _process_recording_sync,
            engine,
            tmp.name,
            diarization,
            existing_mapping,
            profiles,
        )
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    if not results:
        if run_logger:
            await run_logger.info("No speakers to identify for %s" % recording_id[:8])
        return False

    # Log per-speaker results
    if run_logger:
        for speaker_label, result in results.items():
            status = result["status"]
            sim = result.get("similarity")
            pid = result.get("participantId")
            sim_str = "%.3f" % sim if sim else "N/A"
            await run_logger.info(
                "Speaker ID: %s -> %s (sim=%s, pid=%s)"
                % (speaker_label, status, sim_str, pid or "none")
            )

    # Merge results into speaker_mapping
    now = datetime.now(timezone.utc).isoformat()

    for speaker_label, result in results.items():
        status = result["status"]

        if status == "embedding_only":
            # Just add embedding to existing entry
            if speaker_label in existing_mapping:
                existing_mapping[speaker_label]["embedding"] = result["embedding"]

                # Auto-train: update profile for verified speakers
                pid = existing_mapping[speaker_label].get("participantId")
                if pid:
                    embedding = np.array(result["embedding"], dtype=np.float32)
                    await profile_store.update_profile_with_embedding(
                        user_id, pid, embedding, recording_id
                    )
            continue

        if status == "auto":
            entry = existing_mapping.get(speaker_label, {})
            entry["participantId"] = result["participantId"]
            # Set displayName from the best matching candidate
            best_candidate = result["topCandidates"][0] if result["topCandidates"] else {}
            entry["displayName"] = best_candidate.get("displayName")
            entry["confidence"] = result["similarity"]
            entry["manuallyVerified"] = False
            entry["identificationStatus"] = "auto"
            entry["similarity"] = result["similarity"]
            entry["topCandidates"] = result["topCandidates"]
            entry["identifiedAt"] = now
            entry["embedding"] = result["embedding"]
            existing_mapping[speaker_label] = entry

        elif status == "suggest":
            entry = existing_mapping.get(speaker_label, {})
            entry["identificationStatus"] = "suggest"
            entry["similarity"] = result["similarity"]
            entry["suggestedParticipantId"] = result["participantId"]
            # Set suggestedDisplayName from the best matching candidate
            best_candidate = result["topCandidates"][0] if result["topCandidates"] else {}
            entry["suggestedDisplayName"] = best_candidate.get("displayName")
            entry["topCandidates"] = result["topCandidates"]
            entry["identifiedAt"] = now
            entry["embedding"] = result["embedding"]
            existing_mapping[speaker_label] = entry

        else:  # unknown
            entry = existing_mapping.get(speaker_label, {})
            entry["identificationStatus"] = "unknown"
            entry["similarity"] = result["similarity"]
            entry["topCandidates"] = result["topCandidates"]
            entry["identifiedAt"] = now
            entry["embedding"] = result["embedding"]
            existing_mapping[speaker_label] = entry

    # Save updated speaker_mapping
    await db.execute(
        """UPDATE recordings
           SET speaker_mapping = ?, speaker_mapping_updated_at = datetime('now'),
               updated_at = datetime('now')
           WHERE id = ?""",
        (json.dumps(existing_mapping), recording_id),
    )
    await db.commit()

    logger.info(
        "Speaker identification complete for recording %s: %d speakers processed",
        recording_id,
        len(results),
    )
    return True


async def rerate_speakers(user_id: str) -> int:
    """Re-rate speakers against current profiles.

    Queries recordings with suggest/unknown speakers, re-matches stored
    embeddings against current profiles. Only upgrades (unknown->suggest,
    suggest->auto), never downgrades.

    Returns:
        Number of recordings updated.
    """
    settings = get_settings()
    db = await get_db()

    # Find recordings with speaker IDs that might benefit from re-rating
    rows = await db.execute_fetchall(
        """SELECT id, speaker_mapping FROM recordings
           WHERE user_id = ? AND speaker_mapping IS NOT NULL""",
        (user_id,),
    )

    profiles = await profile_store.get_profiles(user_id)
    if not profiles:
        return 0

    # Build profile centroid lookup
    profile_centroids = [p for p in profiles if p["centroid"] is not None]
    if not profile_centroids:
        return 0

    updated_count = 0

    for row in rows:
        r = dict(row)
        recording_id = r["id"]
        try:
            mapping = json.loads(r["speaker_mapping"])
        except (json.JSONDecodeError, TypeError):
            continue

        changed = False
        for label, entry in mapping.items():
            if not isinstance(entry, dict):
                continue

            # Only re-rate suggest and unknown entries
            id_status = entry.get("identificationStatus")
            if id_status not in ("suggest", "unknown"):
                continue

            # Need a stored embedding
            emb_data = entry.get("embedding")
            if not emb_data or not isinstance(emb_data, list):
                continue

            embedding = l2_normalize(np.array(emb_data, dtype=np.float32))

            # Match against current profiles
            candidates = []
            for p in profile_centroids:
                b_norm = l2_normalize(p["centroid"])
                sim = float(np.dot(embedding, b_norm))
                candidates.append({
                    "participantId": p["participant_id"],
                    "displayName": p["display_name"],
                    "similarity": round(sim, 4),
                })

            candidates.sort(key=lambda x: x["similarity"], reverse=True)
            top_candidates = [c for c in candidates[:5] if c["similarity"] >= MIN_CANDIDATE_THRESHOLD]

            if not top_candidates:
                continue

            best = top_candidates[0]
            best_sim = best["similarity"]

            # Determine new status
            auto_t, suggest_t = _thresholds()
            if best_sim >= auto_t:
                new_status = "auto"
            elif best_sim >= suggest_t:
                new_status = "suggest"
            else:
                continue  # Still unknown, no upgrade

            # Only upgrade, never downgrade
            status_rank = {"unknown": 0, "suggest": 1, "auto": 2}
            old_rank = status_rank.get(id_status, 0)
            new_rank = status_rank.get(new_status, 0)

            if new_rank <= old_rank:
                continue

            # Apply upgrade
            now = datetime.now(timezone.utc).isoformat()
            if new_status == "auto":
                entry["participantId"] = best["participantId"]
                entry["displayName"] = best.get("displayName")
                entry["confidence"] = best_sim
                entry["identificationStatus"] = "auto"
            elif new_status == "suggest":
                entry["suggestedParticipantId"] = best["participantId"]
                entry["suggestedDisplayName"] = best.get("displayName")
                entry["identificationStatus"] = "suggest"

            entry["similarity"] = best_sim
            entry["topCandidates"] = top_candidates
            entry["identifiedAt"] = now

            changed = True
            logger.info(
                "Re-rated %s in %s: %s -> %s (sim=%.3f)",
                label, recording_id, id_status, new_status, best_sim,
            )

        if changed:
            await db.execute(
                """UPDATE recordings
                   SET speaker_mapping = ?, speaker_mapping_updated_at = datetime('now'),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(mapping), recording_id),
            )
            updated_count += 1

    if updated_count:
        await db.commit()
        logger.info("Re-rated speakers in %d recordings for user %s", updated_count, user_id)

    return updated_count
