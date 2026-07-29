#!/usr/bin/env python3
"""
Find clusters of unlabeled speakers who are likely the same person.

Uses centroid-based similarity and transitive chaining to group speakers.
Outputs an ordered list of clusters to help prioritize labeling.

Usage:
    python find_unlabeled_clusters.py --embeddings-dir embeddings/
    python find_unlabeled_clusters.py --embeddings-dir embeddings/ --threshold 0.55
"""

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

import numpy as np


@dataclass
class Speaker:
    """A speaker in a recording."""
    recording_id: str
    speaker_label: str
    title: str
    date: str
    duration_s: float
    participant_id: Optional[str]
    participant_name: Optional[str]
    centroid: np.ndarray = field(repr=False)

    @property
    def key(self) -> str:
        return f"{self.recording_id}::{self.speaker_label}"

    @property
    def is_labeled(self) -> bool:
        return self.participant_id is not None


@dataclass
class Cluster:
    """A cluster of speakers believed to be the same person."""
    speakers: List[Speaker]

    @property
    def total_duration(self) -> float:
        return sum(s.duration_s for s in self.speakers)

    @property
    def num_recordings(self) -> int:
        return len(set(s.recording_id for s in self.speakers))

    @property
    def num_speakers(self) -> int:
        return len(self.speakers)

    @property
    def dates(self) -> List[str]:
        return sorted(set(s.date for s in self.speakers))

    @property
    def has_labeled(self) -> bool:
        return any(s.is_labeled for s in self.speakers)

    @property
    def labeled_name(self) -> Optional[str]:
        for s in self.speakers:
            if s.participant_name:
                return s.participant_name
        return None


def load_exclude_list(exclude_file: str) -> set:
    """Load recording IDs to exclude from a file."""
    if not exclude_file or not os.path.exists(exclude_file):
        return set()

    exclude_ids = set()
    with open(exclude_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                recording_id = line.split()[0]
                exclude_ids.add(recording_id)
    return exclude_ids


def load_data(embeddings_dir: str) -> Tuple[Dict, Dict[str, np.ndarray]]:
    """Load metadata and embeddings."""
    metadata_path = os.path.join(embeddings_dir, "metadata.json")
    embeddings_path = os.path.join(embeddings_dir, "embeddings.npz")

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    embeddings_file = np.load(embeddings_path)
    embeddings = {key: embeddings_file[key] for key in embeddings_file.files}

    return metadata, embeddings


def compute_centroid(embeddings: np.ndarray, drop_count: int = 2) -> np.ndarray:
    """
    Compute robust L2-normalized centroid using coherence filtering.

    Drops the lowest `drop_count` embeddings based on their mean similarity
    to neighbors, which filters out embeddings from timing errors that
    captured a different speaker.
    """
    n = len(embeddings)

    # If we have 3 or fewer embeddings, can't afford to drop any
    if n <= 3:
        centroid = embeddings.mean(axis=0)
        return centroid / (np.linalg.norm(centroid) + 1e-8)

    # Adjust drop count if we don't have enough embeddings
    drop_count = min(drop_count, n - 3)

    # 1. Compute pairwise similarity matrix (embeddings should be normalized)
    # Normalize just in case
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / (norms + 1e-8)
    similarity_matrix = np.dot(normalized, normalized.T)

    # 2. Compute mean similarity for each embedding to its neighbors
    # Subtract 1.0 to exclude self-similarity
    mean_similarities = (similarity_matrix.sum(axis=1) - 1.0) / (n - 1)

    # 3. Keep embeddings with highest coherence (drop lowest)
    n_keep = n - drop_count
    keep_indices = np.argsort(mean_similarities)[-n_keep:]
    clean_embeddings = normalized[keep_indices]

    # 4. Compute centroid of clean set and re-normalize
    centroid = clean_embeddings.mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 1e-8:
        centroid = centroid / norm

    return centroid


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b))


def build_speakers(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    exclude_recordings: Set[str]
) -> List[Speaker]:
    """Build list of all speakers with their centroids."""
    speakers = []

    for rec_id, rec in metadata['recordings'].items():
        if rec_id in exclude_recordings:
            continue

        for speaker_label, speaker_info in rec['speakers'].items():
            key = speaker_info.get('embedding_key', f"{rec_id}::{speaker_label}")

            if key not in embeddings:
                continue

            emb = embeddings[key]
            centroid = compute_centroid(emb)

            speakers.append(Speaker(
                recording_id=rec_id,
                speaker_label=speaker_label,
                title=rec.get('title', rec.get('original_filename', rec_id))[:60],
                date=rec.get('recorded_at', '')[:10],
                duration_s=speaker_info.get('total_duration_s', 0),
                participant_id=speaker_info.get('participant_id'),
                participant_name=speaker_info.get('participant_name'),
                centroid=centroid,
            ))

    return speakers


def find_clusters_union_find(
    speakers: List[Speaker],
    threshold: float
) -> List[Cluster]:
    """
    Find clusters of similar speakers using union-find with transitive chaining.
    """
    n = len(speakers)

    # Union-find data structure
    parent = list(range(n))
    rank = [0] * n

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int):
        px, py = find(x), find(y)
        if px == py:
            return
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1

    # Build similarity edges and union similar speakers
    print(f"Computing pairwise similarities for {n} speakers...")
    edges_found = 0

    for i in range(n):
        for j in range(i + 1, n):
            # Skip if same recording (different speakers in same meeting)
            if speakers[i].recording_id == speakers[j].recording_id:
                continue

            sim = cosine_similarity(speakers[i].centroid, speakers[j].centroid)
            if sim >= threshold:
                union(i, j)
                edges_found += 1

    print(f"Found {edges_found} edges above threshold {threshold}")

    # Group speakers by their root
    groups = defaultdict(list)
    for i, speaker in enumerate(speakers):
        root = find(i)
        groups[root].append(speaker)

    # Convert to clusters
    clusters = [Cluster(speakers=group) for group in groups.values()]

    return clusters


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def main():
    parser = argparse.ArgumentParser(description="Find clusters of unlabeled speakers")
    parser.add_argument("--embeddings-dir", default="embeddings", help="Directory with embeddings")
    parser.add_argument("--exclude-file", type=str, default=None, help="File with recording IDs to exclude")
    parser.add_argument("--threshold", type=float, default=0.55, help="Similarity threshold for clustering")
    parser.add_argument("--min-recordings", type=int, default=2, help="Minimum recordings per cluster to show")
    parser.add_argument("--show-labeled", action="store_true", help="Also show clusters with labeled speakers")
    args = parser.parse_args()

    # Load data
    print("Loading data...")
    exclude_recordings = load_exclude_list(args.exclude_file)
    if exclude_recordings:
        print(f"Excluding {len(exclude_recordings)} recordings")

    metadata, embeddings = load_data(args.embeddings_dir)
    print(f"Loaded {len(metadata['recordings'])} recordings")

    # Build speakers
    speakers = build_speakers(metadata, embeddings, exclude_recordings)
    print(f"Found {len(speakers)} speakers with embeddings")

    labeled = sum(1 for s in speakers if s.is_labeled)
    unlabeled = len(speakers) - labeled
    print(f"  Labeled: {labeled}")
    print(f"  Unlabeled: {unlabeled}")

    # Find clusters
    print(f"\nClustering with threshold {args.threshold}...")
    clusters = find_clusters_union_find(speakers, args.threshold)

    # Filter and sort clusters
    if not args.show_labeled:
        # Only show clusters that have at least one unlabeled speaker
        clusters = [c for c in clusters if not all(s.is_labeled for s in c.speakers)]

    # Filter by min recordings
    clusters = [c for c in clusters if c.num_recordings >= args.min_recordings]

    # Sort by total duration (most audio first - easier to verify)
    clusters.sort(key=lambda c: c.total_duration, reverse=True)

    # Separate into two categories
    auto_labelable = [c for c in clusters if c.has_labeled]
    needs_identification = [c for c in clusters if not c.has_labeled]

    # Output Section 1: Auto-labelable
    print("\n" + "=" * 80)
    print("SECTION 1: READY TO AUTO-LABEL")
    print("These clusters have a known participant. Unlabeled speakers can be assigned.")
    print("=" * 80)

    if not auto_labelable:
        print("\nNo auto-labelable clusters found.")
    else:
        # Summary table
        print(f"\n{'Participant':<20} {'Unlabeled':<10} {'Audio':<10} {'Recordings':<10}")
        print("-" * 50)

        for cluster in auto_labelable:
            unlabeled_count = sum(1 for s in cluster.speakers if not s.is_labeled)
            unlabeled_duration = sum(s.duration_s for s in cluster.speakers if not s.is_labeled)
            unlabeled_recs = len(set(s.recording_id for s in cluster.speakers if not s.is_labeled))
            print(f"{cluster.labeled_name:<20} {unlabeled_count:<10} {format_duration(unlabeled_duration):<10} {unlabeled_recs:<10}")

        # Detailed view
        print("\n" + "-" * 80)
        print("DETAILS: Unlabeled speakers to assign")
        print("-" * 80)

        for cluster in auto_labelable:
            unlabeled = [s for s in cluster.speakers if not s.is_labeled]
            if not unlabeled:
                continue

            print(f"\n>>> Assign to: {cluster.labeled_name}")
            sorted_speakers = sorted(unlabeled, key=lambda s: s.date)
            for speaker in sorted_speakers:
                print(f"    {speaker.date} | {speaker.recording_id[:8]}... | {speaker.speaker_label} ({format_duration(speaker.duration_s)}) | {speaker.title[:45]}")

    # Output Section 2: Needs identification
    print("\n" + "=" * 80)
    print("SECTION 2: NEEDS MANUAL IDENTIFICATION")
    print("These clusters have NO labeled speakers. Listen to one and provide a name.")
    print("=" * 80)

    if not needs_identification:
        print("\nNo unidentified clusters found.")
    else:
        print(f"\nFound {len(needs_identification)} unidentified clusters:\n")

        for i, cluster in enumerate(needs_identification, 1):
            print(f"{'─' * 80}")
            print(f"UNKNOWN PERSON {i}")
            print(f"  Recordings: {cluster.num_recordings} | "
                  f"Speaker instances: {cluster.num_speakers} | "
                  f"Total audio: {format_duration(cluster.total_duration)}")
            print(f"  Date range: {cluster.dates[0]} to {cluster.dates[-1]}")
            print()

            # Sort speakers by date, show sample
            sorted_speakers = sorted(cluster.speakers, key=lambda s: (-s.duration_s))  # longest first for easier ID

            print("  Best recordings to identify (longest audio):")
            for speaker in sorted_speakers[:5]:
                print(f"    ○ {speaker.date} | {speaker.recording_id[:8]}... | {speaker.speaker_label} ({format_duration(speaker.duration_s)}) | {speaker.title[:45]}")

            if len(sorted_speakers) > 5:
                print(f"    ... and {len(sorted_speakers) - 5} more")
            print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    auto_label_count = sum(
        sum(1 for s in c.speakers if not s.is_labeled)
        for c in auto_labelable
    )
    auto_label_duration = sum(
        sum(s.duration_s for s in c.speakers if not s.is_labeled)
        for c in auto_labelable
    )

    needs_id_count = sum(len(c.speakers) for c in needs_identification)
    needs_id_duration = sum(c.total_duration for c in needs_identification)

    print(f"""
AUTO-LABELABLE (just assign the known participant):
  Clusters: {len(auto_labelable)}
  Speakers to label: {auto_label_count}
  Audio: {format_duration(auto_label_duration)}

NEEDS IDENTIFICATION (listen and name one):
  Clusters: {len(needs_identification)}
  Speakers: {needs_id_count}
  Audio: {format_duration(needs_id_duration)}
""")


if __name__ == "__main__":
    main()
