#!/usr/bin/env python3
"""
Investigate Outliers in Speaker Embeddings

Finds and reports:
1. Same-person pairs with unusually low similarity (potential labeling errors)
2. Different-person pairs with unusually high similarity (potential labeling errors)
3. Per-participant outlier analysis

Usage:
    python investigate_outliers.py --embeddings-dir embeddings/
"""

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class PairInfo:
    """Information about a speaker pair comparison."""
    recording_a: str
    recording_b: str
    speaker_a: str
    speaker_b: str
    title_a: str
    title_b: str
    similarity: float
    participant_a: str = None
    participant_b: str = None
    duration_a: float = 0
    duration_b: float = 0


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
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / (norms + 1e-8)
    similarity_matrix = np.dot(normalized, normalized.T)

    # 2. Compute mean similarity for each embedding to its neighbors
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


def compute_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings."""
    emb1_norm = emb1 / (np.linalg.norm(emb1) + 1e-8)
    emb2_norm = emb2 / (np.linalg.norm(emb2) + 1e-8)
    return float(np.dot(emb1_norm, emb2_norm))


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


def get_labeled_speakers(metadata: Dict, exclude_recordings: set = None) -> Dict[str, List[Tuple[str, str]]]:
    """Get all labeled speakers grouped by participant."""
    exclude_recordings = exclude_recordings or set()
    participants = defaultdict(list)

    for recording_id, recording in metadata['recordings'].items():
        if recording_id in exclude_recordings:
            continue
        for speaker_label, speaker_info in recording['speakers'].items():
            if speaker_info.get('participant_id'):
                participants[speaker_info['participant_id']].append(
                    (recording_id, speaker_label)
                )

    return {pid: locs for pid, locs in participants.items() if len(locs) >= 2}


def find_low_similarity_same_person(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]],
    threshold: float = 0.50
) -> List[PairInfo]:
    """Find same-person pairs with unusually low similarity."""

    low_pairs = []

    for pid, locations in labeled_speakers.items():
        first_rec = locations[0][0]
        first_spk = locations[0][1]
        participant_name = metadata['recordings'][first_rec]['speakers'][first_spk].get('participant_name', pid[:8])

        for i, (rec_id_a, spk_a) in enumerate(locations):
            for rec_id_b, spk_b in locations[i+1:]:
                if rec_id_a == rec_id_b:
                    continue

                key_a = f"{rec_id_a}::{spk_a}"
                key_b = f"{rec_id_b}::{spk_b}"

                if key_a not in embeddings or key_b not in embeddings:
                    continue

                centroid_a = compute_centroid(embeddings[key_a])
                centroid_b = compute_centroid(embeddings[key_b])
                sim = compute_similarity(centroid_a, centroid_b)

                if sim < threshold:
                    rec_a = metadata['recordings'][rec_id_a]
                    rec_b = metadata['recordings'][rec_id_b]
                    spk_info_a = rec_a['speakers'][spk_a]
                    spk_info_b = rec_b['speakers'][spk_b]

                    low_pairs.append(PairInfo(
                        recording_a=rec_id_a,
                        recording_b=rec_id_b,
                        speaker_a=spk_a,
                        speaker_b=spk_b,
                        title_a=rec_a.get('title', 'Unknown')[:50],
                        title_b=rec_b.get('title', 'Unknown')[:50],
                        similarity=sim,
                        participant_a=participant_name,
                        participant_b=participant_name,
                        duration_a=spk_info_a.get('total_duration_s', 0),
                        duration_b=spk_info_b.get('total_duration_s', 0),
                    ))

    return sorted(low_pairs, key=lambda x: x.similarity)


def find_high_similarity_different_person(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]],
    threshold: float = 0.50
) -> List[PairInfo]:
    """Find different-person pairs with unusually high similarity."""

    high_pairs = []
    participant_ids = list(labeled_speakers.keys())

    for i, pid_a in enumerate(participant_ids):
        for pid_b in participant_ids[i+1:]:
            for loc_a in labeled_speakers[pid_a]:
                for loc_b in labeled_speakers[pid_b]:
                    key_a = f"{loc_a[0]}::{loc_a[1]}"
                    key_b = f"{loc_b[0]}::{loc_b[1]}"

                    if key_a not in embeddings or key_b not in embeddings:
                        continue

                    centroid_a = compute_centroid(embeddings[key_a])
                    centroid_b = compute_centroid(embeddings[key_b])
                    sim = compute_similarity(centroid_a, centroid_b)

                    if sim >= threshold:
                        rec_a = metadata['recordings'][loc_a[0]]
                        rec_b = metadata['recordings'][loc_b[0]]
                        spk_info_a = rec_a['speakers'][loc_a[1]]
                        spk_info_b = rec_b['speakers'][loc_b[1]]

                        high_pairs.append(PairInfo(
                            recording_a=loc_a[0],
                            recording_b=loc_b[0],
                            speaker_a=loc_a[1],
                            speaker_b=loc_b[1],
                            title_a=rec_a.get('title', 'Unknown')[:50],
                            title_b=rec_b.get('title', 'Unknown')[:50],
                            similarity=sim,
                            participant_a=spk_info_a.get('participant_name', pid_a[:8]),
                            participant_b=spk_info_b.get('participant_name', pid_b[:8]),
                            duration_a=spk_info_a.get('total_duration_s', 0),
                            duration_b=spk_info_b.get('total_duration_s', 0),
                        ))

    return sorted(high_pairs, key=lambda x: -x.similarity)


def analyze_participant_outliers(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]],
    participant_id: str
) -> Dict:
    """Detailed analysis of a specific participant's recordings."""

    if participant_id not in labeled_speakers:
        return {'error': f'Participant {participant_id} not found'}

    locations = labeled_speakers[participant_id]

    first_rec = locations[0][0]
    first_spk = locations[0][1]
    participant_name = metadata['recordings'][first_rec]['speakers'][first_spk].get('participant_name', participant_id[:8])

    recordings = []
    for rec_id, spk_label in locations:
        key = f"{rec_id}::{spk_label}"
        if key not in embeddings:
            continue

        rec = metadata['recordings'][rec_id]
        spk_info = rec['speakers'][spk_label]

        recordings.append({
            'recording_id': rec_id,
            'speaker_label': spk_label,
            'title': rec.get('title', 'Unknown'),
            'duration': spk_info.get('total_duration_s', 0),
            'n_embeddings': spk_info.get('n_embeddings', 0),
            'centroid': compute_centroid(embeddings[key]),
        })

    n = len(recordings)
    similarity_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            if i == j:
                similarity_matrix[i, j] = 1.0
            else:
                similarity_matrix[i, j] = compute_similarity(
                    recordings[i]['centroid'],
                    recordings[j]['centroid']
                )

    avg_similarities = []
    for i in range(n):
        other_sims = [similarity_matrix[i, j] for j in range(n) if i != j]
        avg_sim = np.mean(other_sims) if other_sims else 0
        min_sim = np.min(other_sims) if other_sims else 0
        max_sim = np.max(other_sims) if other_sims else 0

        avg_similarities.append({
            'recording_id': recordings[i]['recording_id'],
            'title': recordings[i]['title'][:60],
            'speaker_label': recordings[i]['speaker_label'],
            'duration': recordings[i]['duration'],
            'n_embeddings': recordings[i]['n_embeddings'],
            'avg_similarity': avg_sim,
            'min_similarity': min_sim,
            'max_similarity': max_sim,
        })

    avg_similarities.sort(key=lambda x: x['avg_similarity'])

    worst_pairs = []
    for i in range(n):
        for j in range(i+1, n):
            sim = similarity_matrix[i, j]
            worst_pairs.append({
                'recording_a': recordings[i]['recording_id'],
                'recording_b': recordings[j]['recording_id'],
                'title_a': recordings[i]['title'][:40],
                'title_b': recordings[j]['title'][:40],
                'similarity': sim,
            })

    worst_pairs.sort(key=lambda x: x['similarity'])

    return {
        'participant_id': participant_id,
        'participant_name': participant_name,
        'total_recordings': len(recordings),
        'recordings_by_avg_similarity': avg_similarities,
        'worst_pairs': worst_pairs[:20],
        'overall_stats': {
            'mean': float(np.mean(similarity_matrix[np.triu_indices(n, k=1)])),
            'std': float(np.std(similarity_matrix[np.triu_indices(n, k=1)])),
            'min': float(np.min(similarity_matrix[np.triu_indices(n, k=1)])),
            'max': float(np.max(similarity_matrix[np.triu_indices(n, k=1)])),
        }
    }


def print_section(title: str):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Investigate speaker embedding outliers")
    parser.add_argument("--embeddings-dir", default="embeddings", help="Directory with embeddings")
    parser.add_argument("--low-threshold", type=float, default=0.50, help="Threshold for low same-person similarity")
    parser.add_argument("--high-threshold", type=float, default=0.50, help="Threshold for high different-person similarity")
    parser.add_argument("--participant", help="Specific participant ID to analyze")
    parser.add_argument("--exclude-file", type=str, default=None, help="File with recording IDs to exclude")
    args = parser.parse_args()

    print("Loading data...")
    exclude_recordings = load_exclude_list(args.exclude_file)
    if exclude_recordings:
        print(f"Excluding {len(exclude_recordings)} recordings")

    metadata, embeddings = load_data(args.embeddings_dir)
    labeled_speakers = get_labeled_speakers(metadata, exclude_recordings)

    print(f"Loaded {len(metadata['recordings'])} recordings")
    print(f"Found {len(labeled_speakers)} participants with 2+ recordings")

    # 1. LOW SIMILARITY SAME-PERSON PAIRS
    print_section("1. SAME-PERSON PAIRS WITH LOW SIMILARITY")
    print(f"   (These should be HIGH - potential labeling errors)")
    print(f"   Threshold: < {args.low_threshold}")

    low_pairs = find_low_similarity_same_person(
        metadata, embeddings, labeled_speakers, args.low_threshold
    )

    if low_pairs:
        print(f"\nFound {len(low_pairs)} suspicious pairs:\n")

        by_participant = defaultdict(list)
        for pair in low_pairs:
            by_participant[pair.participant_a].append(pair)

        for participant, pairs in sorted(by_participant.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n--- {participant} ({len(pairs)} low-similarity pairs) ---")
            for pair in pairs[:5]:
                print(f"\n  Similarity: {pair.similarity:.3f}")
                print(f"  Recording A: {pair.title_a}")
                print(f"    ID: {pair.recording_a}")
                print(f"    {pair.speaker_a}, {pair.duration_a:.0f}s audio")
                print(f"  Recording B: {pair.title_b}")
                print(f"    ID: {pair.recording_b}")
                print(f"    {pair.speaker_b}, {pair.duration_b:.0f}s audio")

            if len(pairs) > 5:
                print(f"\n  ... and {len(pairs) - 5} more pairs")
    else:
        print("\nNo low-similarity same-person pairs found.")

    # 2. HIGH SIMILARITY DIFFERENT-PERSON PAIRS
    print_section("2. DIFFERENT-PERSON PAIRS WITH HIGH SIMILARITY")
    print(f"   (These should be LOW - potential labeling errors)")
    print(f"   Threshold: >= {args.high_threshold}")

    high_pairs = find_high_similarity_different_person(
        metadata, embeddings, labeled_speakers, args.high_threshold
    )

    if high_pairs:
        print(f"\nFound {len(high_pairs)} suspicious pairs:\n")

        for pair in high_pairs[:20]:
            print(f"\n  Similarity: {pair.similarity:.3f}")
            print(f"  Person A: {pair.participant_a}")
            print(f"    Recording: {pair.title_a}")
            print(f"    ID: {pair.recording_a}, {pair.speaker_a}")
            print(f"  Person B: {pair.participant_b}")
            print(f"    Recording: {pair.title_b}")
            print(f"    ID: {pair.recording_b}, {pair.speaker_b}")

        if len(high_pairs) > 20:
            print(f"\n... and {len(high_pairs) - 20} more pairs")
    else:
        print("\nNo high-similarity different-person pairs found.")

    # 3. PARTICIPANTS WITH ISSUES
    participant_issues = []
    for pid, locations in labeled_speakers.items():
        if len(locations) < 2:
            continue

        first_rec = locations[0][0]
        first_spk = locations[0][1]
        name = metadata['recordings'][first_rec]['speakers'][first_spk].get('participant_name', pid[:8])

        low_count = sum(1 for p in low_pairs if p.participant_a == name)

        if low_count > 0:
            participant_issues.append((pid, name, len(locations), low_count))

    participant_issues.sort(key=lambda x: -x[3])

    if participant_issues:
        print_section("3. PARTICIPANTS WITH POTENTIAL ISSUES")
        print(f"\n{'Participant':<20} {'Recordings':<12} {'Low-Sim Pairs':<15}")
        print("-" * 47)
        for pid, name, n_rec, n_issues in participant_issues[:10]:
            print(f"{name:<20} {n_rec:<12} {n_issues:<15}")

    # 4. DETAILED ANALYSIS FOR CHRIS BIRD (or specified participant)
    target_participant = args.participant

    if not target_participant:
        for pid, locations in labeled_speakers.items():
            first_rec = locations[0][0]
            first_spk = locations[0][1]
            name = metadata['recordings'][first_rec]['speakers'][first_spk].get('participant_name', '')
            if 'chris' in name.lower():
                target_participant = pid
                break

    if target_participant:
        print_section("4. DETAILED PARTICIPANT ANALYSIS")

        analysis = analyze_participant_outliers(metadata, embeddings, labeled_speakers, target_participant)

        if 'error' not in analysis:
            print(f"\nParticipant: {analysis['participant_name']}")
            print(f"Total recordings: {analysis['total_recordings']}")
            print(f"\nOverall stats:")
            stats = analysis['overall_stats']
            print(f"  Mean similarity: {stats['mean']:.3f}")
            print(f"  Std dev: {stats['std']:.3f}")
            print(f"  Min: {stats['min']:.3f}")
            print(f"  Max: {stats['max']:.3f}")

            print(f"\n--- Recordings ranked by avg similarity (lowest = most suspicious) ---\n")
            print(f"{'Avg Sim':<10} {'Min Sim':<10} {'Duration':<10} {'Title'}")
            print("-" * 90)

            for rec in analysis['recordings_by_avg_similarity'][:15]:
                print(f"{rec['avg_similarity']:.3f}     {rec['min_similarity']:.3f}     {rec['duration']:.0f}s       {rec['title'][:55]}")

            print(f"\n--- Worst pairs (lowest similarity) ---\n")
            for pair in analysis['worst_pairs'][:10]:
                print(f"Similarity: {pair['similarity']:.3f}")
                print(f"  A: {pair['title_a']}")
                print(f"  B: {pair['title_b']}")
                print()

    # SUMMARY
    print_section("SUMMARY")
    print(f"""
Findings:
  - Same-person pairs with sim < {args.low_threshold}: {len(low_pairs)}
  - Different-person pairs with sim >= {args.high_threshold}: {len(high_pairs)}
  - Participants with issues: {len(participant_issues)}

To investigate a specific participant:
  uv run python investigate_outliers.py --participant <PARTICIPANT_ID>
""")


if __name__ == "__main__":
    main()
