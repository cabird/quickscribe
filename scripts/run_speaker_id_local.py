# /// script
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "azure-storage-blob>=12.19.0",
#     "python-dotenv>=1.0.0",
#     "numpy>=1.24.0",
#     "torch>=2.0.0",
#     "torchaudio>=2.0.0",
#     "speechbrain>=1.0.0",
#     "pydantic>=2.0.0",
#     "pydantic-settings>=2.0.0",
# ]
# requires-python = ">=3.11"
# ///
"""
Local Speaker Identification Runner

Uploads experiment profiles to blob storage, then runs speaker identification
on a limited number of recordings using the existing diarization experiment
environment.

Usage:
    # From the diarization_experiment venv (has torch/speechbrain):
    cd /home/cbird/repos/quickscribe
    diarization_experiment/.venv/bin/python scripts/run_speaker_id_local.py --max-recordings 5
"""
import argparse
import json
import os
import sys
import warnings
import tempfile
from datetime import datetime, UTC
from pathlib import Path

# Suppress noisy torch/speechbrain FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Add shared lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared_quickscribe_py"))
sys.path.insert(0, str(Path(__file__).parent.parent / "diarization_experiment"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

import numpy as np
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient, ContainerClient

# Import from diarization experiment
from speaker_embedder import EcapaEmbedder, SpeakerProfileDB, l2_normalize, cosine_similarity, merge_adjacent_segments


def match_top_n(profile_db: SpeakerProfileDB, embedding: np.ndarray, n: int = 5):
    """Find the top N matching profiles for an embedding."""
    if not profile_db.profiles:
        return []
    embedding_norm = l2_normalize(embedding)
    results = []
    for pid, profile in profile_db.profiles.items():
        if profile.centroid is None:
            continue
        sim = cosine_similarity(embedding_norm, profile.centroid)
        results.append({
            "participantId": pid,
            "displayName": profile.display_name,
            "similarity": round(sim, 4),
        })
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:n]


# Monkey-patch onto SpeakerProfileDB for convenience
SpeakerProfileDB.match_top_n = lambda self, emb, n=5: match_top_n(self, emb, n)

PROFILES_CONTAINER = "speaker-profiles"
EXPERIMENT_PROFILES = Path(__file__).parent.parent / "diarization_experiment" / "speaker_profiles.json"

# Thresholds
AUTO_THRESHOLD = 0.78
SUGGEST_THRESHOLD = 0.68
MIN_CANDIDATE_THRESHOLD = 0.40


def get_blob_service():
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    return BlobServiceClient.from_connection_string(conn)


def get_cosmos_container():
    client = CosmosClient(
        url=os.environ["AZURE_COSMOS_ENDPOINT"],
        credential=os.environ["AZURE_COSMOS_KEY"],
    )
    db = client.get_database_client(os.environ.get("AZURE_COSMOS_DATABASE_NAME", "quickscribe"))
    return db.get_container_client(os.environ.get("AZURE_COSMOS_CONTAINER_NAME", "QuickScribeContainer"))


def ensure_blob_container(blob_service: BlobServiceClient, name: str) -> ContainerClient:
    """Create container if it doesn't exist."""
    try:
        container = blob_service.get_container_client(name)
        if not container.exists():
            print(f"Creating blob container: {name}")
            container.create_container()
        else:
            print(f"Blob container exists: {name}")
        return container
    except Exception as e:
        print(f"Error with container {name}: {e}")
        raise


def upload_profiles(blob_service: BlobServiceClient, user_id: str):
    """Upload experiment profiles to blob storage."""
    container = ensure_blob_container(blob_service, PROFILES_CONTAINER)
    blob_path = f"{user_id}/profiles.json"

    if not EXPERIMENT_PROFILES.exists():
        print(f"ERROR: Profile file not found: {EXPERIMENT_PROFILES}")
        return False

    with open(EXPERIMENT_PROFILES) as f:
        data = json.load(f)

    profiles = data.get("profiles", {})
    print(f"Uploading {len(profiles)} profiles to {PROFILES_CONTAINER}/{blob_path}")

    blob_client = container.get_blob_client(blob_path)
    blob_client.upload_blob(json.dumps(data, indent=2), overwrite=True)
    print("Profiles uploaded successfully")
    return True


def get_recordings_to_process(cosmos, max_recordings: int):
    """Get recordings needing speaker identification."""
    query = """
    SELECT * FROM c
    WHERE c.type = 'recording'
    AND c.transcription_status = 'completed'
    AND (
        NOT IS_DEFINED(c.speaker_identification_status)
        OR c.speaker_identification_status = null
        OR c.speaker_identification_status = 'not_started'
    )
    """
    items = list(cosmos.query_items(query=query, enable_cross_partition_query=True))
    print(f"Found {len(items)} recordings needing identification")

    if len(items) > max_recordings:
        print(f"Limiting to {max_recordings}")
        items = items[:max_recordings]

    return items


def extract_missing_training_embeddings(cosmos, embedder, profile_db, audio_blob_client, dry_run=False):
    """
    Scan ALL recordings for speakers with useForTraining=true but no embedding.
    Extract embeddings, write each one back to CosmosDB immediately,
    and update the in-memory profile_db.

    Returns count of embeddings extracted.
    """
    print("\n--- Scanning for missing training embeddings ---")

    query = """
    SELECT * FROM c
    WHERE c.type = 'recording'
    AND c.transcription_status = 'completed'
    AND IS_DEFINED(c.transcription_id)
    AND c.transcription_id != null
    """
    recordings = list(cosmos.query_items(query=query, enable_cross_partition_query=True))
    print(f"Scanning {len(recordings)} completed recordings...")

    total_extracted = 0

    for recording in recordings:
        rec_id = recording["id"]
        tid = recording.get("transcription_id")
        if not tid:
            continue

        try:
            transcription = cosmos.read_item(item=tid, partition_key="transcription")
        except Exception:
            continue

        mapping = transcription.get("speaker_mapping") or {}

        # Find speakers needing embeddings
        speakers_needing = []
        for label, data in mapping.items():
            if isinstance(data, dict) and data.get("manuallyVerified") and data.get("useForTraining") and not data.get("embedding"):
                speakers_needing.append(label)

        if not speakers_needing:
            continue

        title = recording.get("title", recording.get("original_filename", "?"))
        print(f"\n  {title} ({rec_id})")
        print(f"  Speakers needing embeddings: {speakers_needing}")

        # Parse diarization
        diarization = parse_diarization(transcription.get("transcript_json"))
        if not diarization:
            print(f"  Skipping: no diarization segments")
            continue

        diarization = merge_adjacent_segments(diarization)

        # Download audio
        unique_filename = recording["unique_filename"]
        user_id = recording["user_id"]
        suffix = os.path.splitext(unique_filename)[1] or ".mp3"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        blob_path = None
        for candidate_path in [f"{user_id}/{unique_filename}", unique_filename]:
            try:
                bc = audio_blob_client.get_blob_client(candidate_path)
                with open(tmp_path, "wb") as f:
                    stream = bc.download_blob()
                    stream.readinto(f)
                blob_path = candidate_path
                break
            except Exception:
                continue

        if not blob_path:
            print(f"  Skipping: audio blob not found")
            os.remove(tmp_path)
            continue

        try:
            # Load audio once
            wav, sr = embedder.load_audio_mono_16k(tmp_path)

            now = datetime.now(UTC).isoformat()

            for label in speakers_needing:
                # Get segments for this speaker
                speaker_segs = [(s, e) for s, e, spk in diarization if spk == label]
                speaker_segs = [(s, e) for s, e in speaker_segs if (e - s) >= 2.0]
                speaker_segs.sort(key=lambda x: x[1] - x[0], reverse=True)
                speaker_segs = speaker_segs[:15]

                if not speaker_segs:
                    print(f"    {label}: no valid segments")
                    continue

                # Extract embeddings
                embs = []
                for start_s, end_s in speaker_segs:
                    dur = end_s - start_s
                    if dur >= 10.0:
                        start_s += 3.0
                        end_s -= 3.0
                        dur = end_s - start_s
                    if dur > 10.0:
                        mid = (start_s + end_s) / 2.0
                        start_s = mid - 5.0
                        end_s = mid + 5.0
                    seg = embedder.slice_audio(wav, sr, start_s, end_s)
                    if seg.shape[1] < int(2.0 * sr):
                        continue
                    emb = embedder.embedding_from_waveform(seg)
                    embs.append(l2_normalize(emb))

                if not embs:
                    print(f"    {label}: no valid embeddings extracted")
                    continue

                centroid = l2_normalize(np.stack(embs, axis=0).mean(axis=0))

                # Update mapping in place
                speaker_data = mapping[label]
                speaker_data["embedding"] = centroid.tolist()
                history = speaker_data.get("identificationHistory") or []
                history.append({"timestamp": now, "action": "embedding_extracted", "source": "worker"})
                speaker_data["identificationHistory"] = history

                # Update profile in memory
                pid = speaker_data.get("participantId")
                if pid:
                    profile = profile_db.get_or_create(pid, speaker_data.get("displayName", ""))
                    profile.update([centroid], recording_id=rec_id)

                print(f"    {label}: extracted embedding ({len(embs)} segments) + updated profile")
                total_extracted += 1

            # Write updated mapping back to CosmosDB immediately
            if not dry_run:
                transcription["speaker_mapping"] = mapping
                cosmos.upsert_item(body=transcription)
                print(f"  Saved to CosmosDB")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    print(f"\n--- Embedding extraction complete: {total_extracted} embeddings extracted ---")
    return total_extracted


def parse_diarization(transcript_json_str: str):
    """Parse diarization segments from transcript_json."""
    if not transcript_json_str:
        return []

    try:
        data = json.loads(transcript_json_str)
    except (json.JSONDecodeError, TypeError):
        return []

    segments = []
    if isinstance(data, dict):
        phrases = data.get("recognizedPhrases", [])
        for phrase in phrases:
            speaker = phrase.get("speaker", 0)
            offset = phrase.get("offsetInTicks", 0) / 10_000_000
            duration = phrase.get("durationInTicks", 0) / 10_000_000
            segments.append((offset, offset + duration, f"Speaker {speaker}"))
    elif isinstance(data, list):
        for seg in data:
            if isinstance(seg, dict):
                start = seg.get("start", seg.get("offset", 0))
                end = seg.get("end", start + seg.get("duration", 0))
                speaker = seg.get("speaker", seg.get("speakerLabel", "Speaker 0"))
                if isinstance(speaker, int):
                    speaker = f"Speaker {speaker}"
                segments.append((float(start), float(end), speaker))

    return segments


def process_recording(recording, cosmos, embedder, profile_db, audio_blob_client):
    """Process a single recording for speaker identification."""
    rec_id = recording["id"]
    user_id = recording["user_id"]
    transcription_id = recording.get("transcription_id")

    if not transcription_id:
        print(f"  Skipping {rec_id}: no transcription_id")
        return None

    # Get transcription
    try:
        transcription = cosmos.read_item(item=transcription_id, partition_key="transcription")
    except Exception:
        print(f"  Skipping: transcription document missing (orphaned reference)")
        return "skip"  # Signal to caller: don't mark as completed

    # Parse diarization
    diarization = parse_diarization(transcription.get("transcript_json"))
    if not diarization:
        print(f"  Skipping {rec_id}: no diarization segments")
        return None

    diarization = merge_adjacent_segments(diarization)
    speakers = set(s for _, _, s in diarization)
    print(f"  {len(diarization)} segments, {len(speakers)} speakers")

    # Check existing mapping for manually verified or dismissed speakers
    existing_mapping = transcription.get("speaker_mapping") or {}
    skip_speakers = set()
    for label, data in existing_mapping.items():
        if isinstance(data, dict):
            if data.get("identificationStatus") == "dismissed":
                skip_speakers.add(label)
            elif data.get("manuallyVerified"):
                skip_speakers.add(label)

    if skip_speakers:
        print(f"  Skipping (verified/dismissed): {skip_speakers}")

    # If all speakers are already handled, skip entirely
    active_speakers = speakers - skip_speakers
    if not active_speakers:
        print(f"  All speakers verified/dismissed, nothing to do")
        return None

    # Download audio — try user-prefixed path first, then bare filename
    unique_filename = recording["unique_filename"]
    user_id = recording["user_id"]
    suffix = os.path.splitext(unique_filename)[1] or ".mp3"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name

    try:
        blob_path = None
        for candidate_path in [f"{user_id}/{unique_filename}", unique_filename]:
            try:
                bc = audio_blob_client.get_blob_client(candidate_path)
                with open(tmp_path, "wb") as f:
                    stream = bc.download_blob()
                    stream.readinto(f)
                blob_path = candidate_path
                break
            except Exception:
                continue

        if not blob_path:
            print(f"  Skipping: audio blob not found ({unique_filename})")
            os.remove(tmp_path)
            return "skip"
        print(f"  Downloaded audio: {blob_path}")

        # Build centroids using top N longest segments per speaker (not all segments)
        MAX_SEGMENTS_PER_SPEAKER = 15
        MIN_DURATION = 2.0

        # Group segments by speaker and pick the longest ones
        speaker_segments: dict[str, list[tuple[float, float]]] = {}
        for start_s, end_s, spk in diarization:
            if spk in skip_speakers:
                continue
            dur = end_s - start_s
            if dur >= MIN_DURATION:
                speaker_segments.setdefault(spk, []).append((start_s, end_s))

        # Sort by duration descending and take top N per speaker
        selected_segments = []
        selected_labels = []
        for spk, segs in speaker_segments.items():
            segs.sort(key=lambda x: x[1] - x[0], reverse=True)
            top = segs[:MAX_SEGMENTS_PER_SPEAKER]
            selected_segments.extend(top)
            selected_labels.extend([spk] * len(top))

        total_segs = len(selected_segments)
        total_all = sum(len(s) for s in speaker_segments.values())
        print(f"  Selected {total_segs} best segments (of {total_all} valid, from {len(diarization)} total)")

        # Extract embeddings
        wav, sr = embedder.load_audio_mono_16k(tmp_path)
        local_embs: dict[str, list] = {}
        for idx, ((start_s, end_s), spk) in enumerate(zip(selected_segments, selected_labels)):
            if (idx + 1) % 10 == 0 or idx == total_segs - 1:
                print(f"    [{idx+1}/{total_segs}]", flush=True)
            dur = end_s - start_s
            # Trim 3s from each edge on segments ≥10s to avoid crosstalk/boundary issues
            EDGE_TRIM = 3.0
            TRIM_THRESHOLD = 10.0
            if dur >= TRIM_THRESHOLD:
                start_s += EDGE_TRIM
                end_s -= EDGE_TRIM
                dur = end_s - start_s
            # Window long segments to center 10s
            if dur > 10.0:
                mid = (start_s + end_s) / 2.0
                start_s = mid - 5.0
                end_s = mid + 5.0
            seg = embedder.slice_audio(wav, sr, start_s, end_s)
            if seg.shape[1] < int(MIN_DURATION * sr):
                continue
            emb = embedder.embedding_from_waveform(seg)
            local_embs.setdefault(spk, []).append(l2_normalize(emb))

        centroids = {}
        for spk, embs in local_embs.items():
            mat = np.stack(embs, axis=0)
            centroids[spk] = l2_normalize(mat.mean(axis=0))

        print(f"  Built centroids for {len(centroids)} speakers")

        # Match against profiles
        results = {}
        auto_matches = {}
        now = datetime.now(UTC).isoformat()

        for speaker_label, centroid in centroids.items():
            if speaker_label in skip_speakers:
                continue

            # Get top N candidates
            top_candidates = profile_db.match_top_n(centroid, n=5)
            top_candidates = [c for c in top_candidates if c["similarity"] >= MIN_CANDIDATE_THRESHOLD]

            if not top_candidates:
                status = "unknown"
                best_id = None
                best_sim = None
            else:
                best = top_candidates[0]
                best_sim = best["similarity"]
                best_id = best["participantId"]

                if best_sim >= AUTO_THRESHOLD:
                    status = "auto"
                elif best_sim >= SUGGEST_THRESHOLD:
                    status = "suggest"
                else:
                    status = "unknown"
                    best_id = None

            # Duplicate auto-match detection
            if status == "auto" and best_id:
                if best_id in auto_matches:
                    prev_label = auto_matches[best_id]
                    prev_sim = results[prev_label]["similarity"]
                    if best_sim > prev_sim:
                        results[prev_label]["identificationStatus"] = "suggest"
                        auto_matches[best_id] = speaker_label
                    else:
                        status = "suggest"
                else:
                    auto_matches[best_id] = speaker_label

            # Build audit history entry
            history_entry = {
                "timestamp": now,
                "action": "auto_assigned" if status == "auto" else status,
                "source": "worker",
                "participantId": best_id,
                "similarity": round(best_sim, 4) if best_sim else None,
                "candidatesPresented": top_candidates,
            }

            result = {
                "identificationStatus": status,
                "similarity": round(best_sim, 4) if best_sim else None,
                "identifiedAt": now,
                "embedding": centroid.tolist(),
                "topCandidates": top_candidates,
                "identificationHistory": [history_entry],
            }

            if status == "auto":
                result["participantId"] = best_id
                result["confidence"] = round(best_sim, 4)
                result["manuallyVerified"] = False
            elif status == "suggest":
                result["suggestedParticipantId"] = best_id

            results[speaker_label] = result
            display = top_candidates[0]["displayName"] if top_candidates else "?"
            sim_str = f"{best_sim:.3f}" if best_sim else "N/A"
            print(f"    {speaker_label}: {status} (sim={sim_str}, candidate={display})")

        return results

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def write_results(cosmos, recording, transcription_id, results):
    """Write identification results back to CosmosDB."""
    # Update transcription speaker_mapping
    transcription = cosmos.read_item(item=transcription_id, partition_key="transcription")
    mapping = transcription.get("speaker_mapping") or {}

    has_suggestions = False
    for speaker_label, result in results.items():
        existing = mapping.get(speaker_label, {})
        if isinstance(existing, dict):
            merged = {**existing, **result}
        else:
            merged = result

        mapping[speaker_label] = merged

        if result["identificationStatus"] in ("suggest", "unknown"):
            has_suggestions = True

    transcription["speaker_mapping"] = mapping
    cosmos.upsert_item(body=transcription)
    print(f"  Updated transcription {transcription_id}")

    # Update recording status
    recording["speaker_identification_status"] = "needs_review" if has_suggestions else "completed"
    cosmos.upsert_item(body=recording)
    print(f"  Recording status -> {recording['speaker_identification_status']}")


def main():
    parser = argparse.ArgumentParser(description="Run speaker identification locally")
    parser.add_argument("--max-recordings", type=int, default=5, help="Max recordings to process")
    parser.add_argument("--skip-upload", action="store_true", help="Skip profile upload")
    parser.add_argument("--dry-run", action="store_true", help="Don't write results to CosmosDB")
    args = parser.parse_args()

    print("=" * 70)
    print("Local Speaker Identification Runner")
    print("=" * 70)

    # Setup clients
    blob_service = get_blob_service()
    cosmos = get_cosmos_container()

    # Get user ID
    recordings = list(cosmos.query_items(
        query="SELECT TOP 1 c.user_id FROM c WHERE c.type = 'recording'",
        enable_cross_partition_query=True,
    ))
    user_id = recordings[0]["user_id"]
    print(f"User ID: {user_id}")

    # Upload profiles
    if not args.skip_upload:
        upload_profiles(blob_service, user_id)

    # Load profiles from blob storage (includes any profiles added via UI)
    print("\nLoading speaker profiles from blob storage...")
    profiles_container = ensure_blob_container(blob_service, PROFILES_CONTAINER)
    blob_path = f"{user_id}/profiles.json"
    try:
        bc = profiles_container.get_blob_client(blob_path)
        import tempfile as _tmp
        with _tmp.NamedTemporaryFile(suffix=".json", delete=True) as tf:
            with open(tf.name, "wb") as f:
                stream = bc.download_blob()
                stream.readinto(f)
            profile_db = SpeakerProfileDB.load_from_file(tf.name)
        print(f"Loaded {len(profile_db.profiles)} profiles from blob storage")
    except Exception:
        # Fall back to local experiment file
        print("Blob profiles not found, falling back to local experiment profiles...")
        profile_db = SpeakerProfileDB.load_from_file(str(EXPERIMENT_PROFILES))
        print(f"Loaded {len(profile_db.profiles)} profiles from local file")

    # Get recordings to process
    print(f"\nQuerying recordings (max {args.max_recordings})...")
    recordings = get_recordings_to_process(cosmos, args.max_recordings)

    if not recordings:
        print("No recordings to process!")
        return

    # Initialize embedder
    print("\nInitializing ECAPA-TDNN embedder...")
    embedder = EcapaEmbedder(cache_dir=str(Path(__file__).parent.parent / "diarization_experiment" / "pretrained_models"))

    # Get audio blob client
    audio_container_name = os.environ.get("AZURE_STORAGE_AUDIO_CONTAINER_NAME",
                                          os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "recordings"))
    audio_blob_client = blob_service.get_container_client(audio_container_name)

    # Phase 1: Extract missing training embeddings (scans ALL recordings)
    extract_missing_training_embeddings(cosmos, embedder, profile_db, audio_blob_client, dry_run=args.dry_run)

    # Phase 2: Process new recordings for identification
    total_processed = 0
    total_speakers = 0
    status_counts = {"auto": 0, "suggest": 0, "unknown": 0}

    for i, recording in enumerate(recordings):
        rec_id = recording["id"]
        title = recording.get("title", recording.get("original_filename", "?"))
        print(f"\n[{i+1}/{len(recordings)}] {title} ({rec_id})")

        results = process_recording(recording, cosmos, embedder, profile_db, audio_blob_client)

        if results == "skip":
            # Orphaned recording — don't touch it
            pass
        elif results:
            total_processed += 1
            total_speakers += len(results)
            for r in results.values():
                status_counts[r["identificationStatus"]] += 1

            if not args.dry_run:
                write_results(cosmos, recording, recording["transcription_id"], results)
            else:
                print("  [DRY RUN] Skipping write")
        else:
            # No speakers to identify — mark as completed so it's not re-queried
            if not args.dry_run:
                recording["speaker_identification_status"] = "completed"
                cosmos.upsert_item(body=recording)
                print("  Marked as completed (nothing to identify)")

    # Save updated profiles back to blob storage (includes any new training embeddings)
    if not args.dry_run:
        print("\nSaving updated profiles to blob storage...")
        upload_data = json.dumps(profile_db.to_dict(), indent=2)
        bc = profiles_container.get_blob_client(blob_path)
        bc.upload_blob(upload_data, overwrite=True)
        print(f"Saved {len(profile_db.profiles)} profiles")

    print(f"\n{'=' * 70}")
    print(f"Done! Processed {total_processed} recordings, {total_speakers} speakers")
    print(f"  Auto:    {status_counts['auto']}")
    print(f"  Suggest: {status_counts['suggest']}")
    print(f"  Unknown: {status_counts['unknown']}")
    if args.dry_run:
        print("\n  *** DRY RUN — no changes written to CosmosDB ***")
    print("=" * 70)


if __name__ == "__main__":
    main()
