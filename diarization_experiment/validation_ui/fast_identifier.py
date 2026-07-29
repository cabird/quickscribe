"""
Fast Speaker Identifier - Uses Pre-Computed Embeddings

Instead of re-extracting embeddings, this loads them from the embeddings directory
created by extract_embeddings.py or run_experiment.py.

This makes loading the validation UI 100x faster!
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from speaker_embedder import SpeakerProfileDB, cosine_similarity, l2_normalize
from speaker_identifier import MeetingIdentificationResult, SpeakerMatch


def load_embeddings(embeddings_dir: str = "../embeddings") -> Tuple[Dict, Dict[str, np.ndarray]]:
    """
    Load pre-computed embeddings and metadata.

    Returns:
        (metadata, embeddings_dict)

    embeddings_dict is keyed by "recording_id::speaker_label"
    """
    metadata_path = os.path.join(embeddings_dir, "metadata.json")
    embeddings_path = os.path.join(embeddings_dir, "embeddings.npz")

    if not os.path.exists(metadata_path):
        raise FileNotFoundError(
            f"Metadata not found at {metadata_path}. "
            f"Run extract_embeddings.py first to generate embeddings."
        )

    if not os.path.exists(embeddings_path):
        raise FileNotFoundError(
            f"Embeddings not found at {embeddings_path}. "
            f"Run extract_embeddings.py first to generate embeddings."
        )

    print(f"Loading metadata from {metadata_path}...")
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    print(f"Loading embeddings from {embeddings_path}...")
    embeddings_file = np.load(embeddings_path)
    embeddings = {key: embeddings_file[key] for key in embeddings_file.files}

    print(f"  Loaded {len(metadata['recordings'])} recordings")
    print(f"  Loaded {len(embeddings)} embedding sets")

    return metadata, embeddings


def compute_centroid(embeddings_array: np.ndarray, drop_count: int = 2) -> np.ndarray:
    """
    Compute robust L2-normalized centroid.

    Drops the lowest `drop_count` embeddings based on coherence.
    """
    n = len(embeddings_array)

    if n <= 3:
        # Not enough to drop any
        centroid = embeddings_array.mean(axis=0)
        return l2_normalize(centroid)

    # Adjust drop count
    drop_count = min(drop_count, n - 3)

    # Normalize all embeddings
    norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
    normalized = embeddings_array / (norms + 1e-8)

    # Compute similarity matrix
    similarity_matrix = np.dot(normalized, normalized.T)

    # Mean similarity for each embedding
    mean_similarities = (similarity_matrix.sum(axis=1) - 1.0) / (n - 1)

    # Keep highest coherence embeddings
    n_keep = n - drop_count
    keep_indices = np.argsort(mean_similarities)[-n_keep:]
    clean_embeddings = normalized[keep_indices]

    # Compute centroid
    centroid = clean_embeddings.mean(axis=0)
    return l2_normalize(centroid)


def fast_identify_from_embeddings(
    profile_db: SpeakerProfileDB,
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    high_threshold: float = 0.80,
    low_threshold: float = 0.60,
    max_meetings: Optional[int] = None
) -> List[MeetingIdentificationResult]:
    """
    Identify speakers using pre-computed embeddings.

    Args:
        profile_db: Speaker profile database
        metadata: Metadata from embeddings/metadata.json
        embeddings: Embeddings dict keyed by "recording_id::speaker_label"
        high_threshold: Auto-assign threshold
        low_threshold: Suggest threshold
        max_meetings: Limit number of meetings to process

    Returns:
        List of MeetingIdentificationResult
    """
    results = []
    recordings = metadata['recordings']

    # Limit if requested
    recording_ids = list(recordings.keys())
    if max_meetings:
        recording_ids = recording_ids[:max_meetings]
        print(f"Processing first {max_meetings} of {len(recordings)} recordings")

    print(f"Identifying speakers in {len(recording_ids)} recordings...")

    for idx, recording_id in enumerate(recording_ids, 1):
        recording_data = recordings[recording_id]

        if (idx - 1) % 20 == 0:
            print(f"  [{idx}/{len(recording_ids)}] {recording_data.get('title', recording_id)}")

        result = MeetingIdentificationResult(
            recording_id=recording_id,
            title=recording_data.get('title', recording_id)
        )

        # Process each speaker in this recording
        for speaker_label, speaker_info in recording_data.get('speakers', {}).items():
            key = f"{recording_id}::{speaker_label}"

            if key not in embeddings:
                # No embeddings for this speaker (probably too little audio)
                result.speaker_matches.append(SpeakerMatch(
                    speaker_label=speaker_label,
                    status="unknown",
                    segment_count=speaker_info.get('segment_count', 0),
                    total_duration_s=speaker_info.get('total_duration_s', 0.0)
                ))
                continue

            # Get embeddings for this speaker
            speaker_embeddings = embeddings[key]

            # Compute centroid
            speaker_centroid = compute_centroid(speaker_embeddings)

            # Match against profiles
            best_match = None
            best_similarity = -1.0

            for profile in profile_db.profiles.values():
                similarity = cosine_similarity(speaker_centroid, profile.centroid)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = profile

            # Determine status
            if best_similarity >= high_threshold:
                status = "auto"
            elif best_similarity >= low_threshold:
                status = "suggest"
            else:
                status = "unknown"

            result.speaker_matches.append(SpeakerMatch(
                speaker_label=speaker_label,
                status=status,
                matched_participant_id=best_match.participant_id if best_match else None,
                matched_display_name=best_match.display_name if best_match else None,
                similarity=best_similarity,
                embedding=speaker_centroid,
                segment_count=speaker_info.get('segment_count', 0),
                total_duration_s=speaker_info.get('total_duration_s', 0.0)
            ))

        results.append(result)

    print(f"Identification complete!")
    return results
