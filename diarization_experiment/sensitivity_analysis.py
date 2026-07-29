#!/usr/bin/env python3
"""
Sensitivity Analysis for Speaker Identification

Uses labeled recordings as ground truth to:
1. Analyze similarity distributions (same person vs different people)
2. Find optimal thresholds for speaker matching
3. Compare centroid vs raw embedding approaches
4. Test for transitive chain risks
5. Generate recommendations

Usage:
    python sensitivity_analysis.py --embeddings-dir embeddings/
    python sensitivity_analysis.py --embeddings-dir embeddings/ --output-report analysis_report.md
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class SimilarityStats:
    """Statistics for a set of similarity scores."""
    count: int
    min: float
    max: float
    mean: float
    std: float
    median: float
    p5: float   # 5th percentile
    p25: float  # 25th percentile
    p75: float  # 75th percentile
    p95: float  # 95th percentile


@dataclass
class ThresholdMetrics:
    """Precision/recall metrics at a given threshold."""
    threshold: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    accuracy: float


def load_data(embeddings_dir: str) -> Tuple[Dict, Dict[str, np.ndarray]]:
    """Load metadata and embeddings."""
    metadata_path = os.path.join(embeddings_dir, "metadata.json")
    embeddings_path = os.path.join(embeddings_dir, "embeddings.npz")

    print(f"Loading metadata from {metadata_path}...")
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    print(f"Loading embeddings from {embeddings_path}...")
    embeddings_file = np.load(embeddings_path)
    embeddings = {key: embeddings_file[key] for key in embeddings_file.files}

    print(f"  Loaded {len(metadata['recordings'])} recordings")
    print(f"  Loaded {len(embeddings)} embedding sets")

    return metadata, embeddings


def load_exclude_list(exclude_file: Optional[str]) -> set:
    """Load recording IDs to exclude from a file."""
    if not exclude_file or not os.path.exists(exclude_file):
        return set()

    exclude_ids = set()
    with open(exclude_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Handle inline comments
                recording_id = line.split()[0]
                exclude_ids.add(recording_id)
    return exclude_ids


def get_labeled_speakers(metadata: Dict, exclude_recordings: Optional[set] = None) -> Dict[str, List[Tuple[str, str]]]:
    """
    Get all labeled speakers grouped by participant.

    Returns:
        Dict mapping participant_id -> [(recording_id, speaker_label), ...]
    """
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

    # Filter to participants with at least 2 recordings
    multi_recording = {
        pid: locs for pid, locs in participants.items()
        if len(locs) >= 2
    }

    print(f"\nLabeled speakers:")
    print(f"  Total participants: {len(participants)}")
    print(f"  With 2+ recordings: {len(multi_recording)}")

    return multi_recording


def compute_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings."""
    # Embeddings should already be L2 normalized, but normalize anyway
    emb1_norm = emb1 / (np.linalg.norm(emb1) + 1e-8)
    emb2_norm = emb2 / (np.linalg.norm(emb2) + 1e-8)
    return float(np.dot(emb1_norm, emb2_norm))


def compute_centroid(embeddings: np.ndarray, drop_count: int = 2, use_medoid: bool = False) -> np.ndarray:
    """
    Compute robust L2-normalized centroid using coherence filtering.

    Drops the lowest `drop_count` embeddings based on their mean similarity
    to neighbors, which filters out embeddings from timing errors that
    captured a different speaker.

    If use_medoid=True, returns the actual embedding closest to the centroid
    instead of the centroid itself (stays on the true voice manifold).
    """
    n = len(embeddings)

    # If we have 3 or fewer embeddings, can't afford to drop any
    if n <= 3:
        centroid = embeddings.mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
        if use_medoid:
            distances = np.linalg.norm(embeddings - centroid, axis=1)
            return embeddings[np.argmin(distances)]
        return centroid

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

    # 5. If medoid, find the closest real embedding to the centroid
    if use_medoid:
        distances = np.linalg.norm(clean_embeddings - centroid, axis=1)
        return clean_embeddings[np.argmin(distances)]

    return centroid


# Global flag to toggle medoid mode for comparison
USE_MEDOID = False


def build_similarity_pairs(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]]
) -> Tuple[List[float], List[float]]:
    """
    Build same-person and different-person similarity pairs.

    Returns:
        (same_person_similarities, different_person_similarities)
    """
    same_person_sims = []
    diff_person_sims = []

    # Get all participant IDs with multiple recordings
    participant_ids = list(labeled_speakers.keys())

    print("\nBuilding similarity pairs...")

    # Same-person pairs (cross-recording)
    for pid in participant_ids:
        locations = labeled_speakers[pid]

        for i, (rec_id_a, spk_a) in enumerate(locations):
            for rec_id_b, spk_b in locations[i+1:]:
                # Skip same recording (can't be used for cross-recording analysis)
                if rec_id_a == rec_id_b:
                    continue

                key_a = f"{rec_id_a}::{spk_a}"
                key_b = f"{rec_id_b}::{spk_b}"

                if key_a not in embeddings or key_b not in embeddings:
                    continue

                emb_a = embeddings[key_a]
                emb_b = embeddings[key_b]

                # Compare centroids
                centroid_a = compute_centroid(emb_a, use_medoid=USE_MEDOID)
                centroid_b = compute_centroid(emb_b, use_medoid=USE_MEDOID)
                sim = compute_similarity(centroid_a, centroid_b)
                same_person_sims.append(sim)

    # Different-person pairs
    for i, pid_a in enumerate(participant_ids):
        for pid_b in participant_ids[i+1:]:
            # Sample one location from each participant
            loc_a = labeled_speakers[pid_a][0]
            loc_b = labeled_speakers[pid_b][0]

            key_a = f"{loc_a[0]}::{loc_a[1]}"
            key_b = f"{loc_b[0]}::{loc_b[1]}"

            if key_a not in embeddings or key_b not in embeddings:
                continue

            emb_a = embeddings[key_a]
            emb_b = embeddings[key_b]

            centroid_a = compute_centroid(emb_a, use_medoid=USE_MEDOID)
            centroid_b = compute_centroid(emb_b, use_medoid=USE_MEDOID)
            sim = compute_similarity(centroid_a, centroid_b)
            diff_person_sims.append(sim)

    print(f"  Same-person pairs: {len(same_person_sims)}")
    print(f"  Different-person pairs: {len(diff_person_sims)}")

    return same_person_sims, diff_person_sims


def compute_stats(similarities: List[float]) -> SimilarityStats:
    """Compute statistics for a list of similarity scores."""
    arr = np.array(similarities)
    return SimilarityStats(
        count=len(arr),
        min=float(np.min(arr)),
        max=float(np.max(arr)),
        mean=float(np.mean(arr)),
        std=float(np.std(arr)),
        median=float(np.median(arr)),
        p5=float(np.percentile(arr, 5)),
        p25=float(np.percentile(arr, 25)),
        p75=float(np.percentile(arr, 75)),
        p95=float(np.percentile(arr, 95)),
    )


def analyze_thresholds(
    same_person_sims: List[float],
    diff_person_sims: List[float],
    thresholds: Optional[List[float]] = None
) -> List[ThresholdMetrics]:
    """Compute precision/recall at various thresholds."""
    if thresholds is None:
        thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82, 0.85, 0.88, 0.90]

    results = []

    for thresh in thresholds:
        # True positives: same person pairs above threshold
        tp = sum(1 for s in same_person_sims if s >= thresh)
        # False negatives: same person pairs below threshold
        fn = sum(1 for s in same_person_sims if s < thresh)
        # False positives: different person pairs above threshold
        fp = sum(1 for s in diff_person_sims if s >= thresh)
        # True negatives: different person pairs below threshold
        tn = sum(1 for s in diff_person_sims if s < thresh)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0

        results.append(ThresholdMetrics(
            threshold=thresh,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1=f1,
            accuracy=accuracy,
        ))

    return results


def compare_centroid_vs_raw(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]]
) -> Dict:
    """
    Compare centroid-based matching vs raw embedding matching.

    Returns dict with comparison metrics.
    """
    centroid_sims = []
    raw_mean_sims = []
    raw_max_sims = []

    participant_ids = list(labeled_speakers.keys())

    print("\nComparing centroid vs raw embeddings...")

    for pid in participant_ids:
        locations = labeled_speakers[pid]

        for i, (rec_id_a, spk_a) in enumerate(locations):
            for rec_id_b, spk_b in locations[i+1:]:
                if rec_id_a == rec_id_b:
                    continue

                key_a = f"{rec_id_a}::{spk_a}"
                key_b = f"{rec_id_b}::{spk_b}"

                if key_a not in embeddings or key_b not in embeddings:
                    continue

                emb_a = embeddings[key_a]
                emb_b = embeddings[key_b]

                # Centroid comparison
                centroid_a = compute_centroid(emb_a, use_medoid=USE_MEDOID)
                centroid_b = compute_centroid(emb_b, use_medoid=USE_MEDOID)
                centroid_sim = compute_similarity(centroid_a, centroid_b)
                centroid_sims.append(centroid_sim)

                # Raw embedding comparisons (all pairs)
                pair_sims = []
                for ea in emb_a:
                    for eb in emb_b:
                        pair_sims.append(compute_similarity(ea, eb))

                raw_mean_sims.append(np.mean(pair_sims))
                raw_max_sims.append(np.max(pair_sims))

    return {
        'centroid': {
            'mean': float(np.mean(centroid_sims)),
            'std': float(np.std(centroid_sims)),
            'min': float(np.min(centroid_sims)),
            'max': float(np.max(centroid_sims)),
        },
        'raw_mean': {
            'mean': float(np.mean(raw_mean_sims)),
            'std': float(np.std(raw_mean_sims)),
            'min': float(np.min(raw_mean_sims)),
            'max': float(np.max(raw_mean_sims)),
        },
        'raw_max': {
            'mean': float(np.mean(raw_max_sims)),
            'std': float(np.std(raw_max_sims)),
            'min': float(np.min(raw_max_sims)),
            'max': float(np.max(raw_max_sims)),
        },
        'n_pairs': len(centroid_sims),
    }


def analyze_chain_risk(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]],
    threshold: float = 0.75
) -> Dict:
    """
    Analyze risk of transitive chain errors.

    Find cases where A≈B and B≈C but A and C are different people.
    """
    print(f"\nAnalyzing chain risk at threshold {threshold}...")

    # Build centroid lookup
    centroids = {}
    speaker_to_participant = {}

    for pid, locations in labeled_speakers.items():
        for rec_id, spk_label in locations:
            key = f"{rec_id}::{spk_label}"
            if key in embeddings:
                centroids[key] = compute_centroid(embeddings[key], use_medoid=USE_MEDOID)
                speaker_to_participant[key] = pid

    # Find all pairs above threshold
    keys = list(centroids.keys())
    edges = []

    for i, key_a in enumerate(keys):
        for key_b in keys[i+1:]:
            sim = compute_similarity(centroids[key_a], centroids[key_b])
            if sim >= threshold:
                edges.append((key_a, key_b, sim))

    # Check for chain violations
    # A violation is: A-B edge, B-C edge, but A and C are different people
    violations = []
    chains_checked = 0

    # Build adjacency for faster lookup
    adj = defaultdict(list)
    for a, b, sim in edges:
        adj[a].append((b, sim))
        adj[b].append((a, sim))

    for key_b in keys:
        neighbors = adj[key_b]
        if len(neighbors) < 2:
            continue

        for i, (key_a, sim_ab) in enumerate(neighbors):
            for key_c, sim_bc in neighbors[i+1:]:
                chains_checked += 1

                # A and C are connected via B
                # Check if A and C are different people
                pid_a = speaker_to_participant.get(key_a)
                pid_c = speaker_to_participant.get(key_c)

                if pid_a and pid_c and pid_a != pid_c:
                    # Check direct similarity A-C
                    sim_ac = compute_similarity(centroids[key_a], centroids[key_c])

                    violations.append({
                        'speaker_a': key_a,
                        'speaker_b': key_b,
                        'speaker_c': key_c,
                        'participant_a': pid_a,
                        'participant_c': pid_c,
                        'sim_ab': sim_ab,
                        'sim_bc': sim_bc,
                        'sim_ac': sim_ac,
                    })

    return {
        'threshold': threshold,
        'edges_above_threshold': len(edges),
        'chains_checked': chains_checked,
        'violations': len(violations),
        'violation_rate': len(violations) / chains_checked if chains_checked > 0 else 0,
        'examples': violations[:5],  # First 5 examples
    }


def analyze_per_participant(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    labeled_speakers: Dict[str, List[Tuple[str, str]]]
) -> Dict:
    """
    Analyze intra-participant similarity across recordings.

    For each participant, compute cross-recording similarity.
    """
    print("\nAnalyzing per-participant consistency...")

    results = {}

    for pid, locations in labeled_speakers.items():
        if len(locations) < 2:
            continue

        # Get participant name
        first_rec = locations[0][0]
        first_spk = locations[0][1]
        name = metadata['recordings'][first_rec]['speakers'][first_spk].get('participant_name', pid)

        # Compute all cross-recording similarities
        sims = []
        for i, (rec_id_a, spk_a) in enumerate(locations):
            for rec_id_b, spk_b in locations[i+1:]:
                if rec_id_a == rec_id_b:
                    continue

                key_a = f"{rec_id_a}::{spk_a}"
                key_b = f"{rec_id_b}::{spk_b}"

                if key_a not in embeddings or key_b not in embeddings:
                    continue

                centroid_a = compute_centroid(embeddings[key_a], use_medoid=USE_MEDOID)
                centroid_b = compute_centroid(embeddings[key_b], use_medoid=USE_MEDOID)
                sims.append(compute_similarity(centroid_a, centroid_b))

        if sims:
            results[pid] = {
                'name': name,
                'n_recordings': len(locations),
                'n_pairs': len(sims),
                'mean_similarity': float(np.mean(sims)),
                'min_similarity': float(np.min(sims)),
                'max_similarity': float(np.max(sims)),
                'std': float(np.std(sims)),
            }

    return results


def detect_same_recording_anomalies(
    metadata: Dict,
    embeddings: Dict[str, np.ndarray],
    threshold: float = 0.75
) -> List[Dict]:
    """
    Find speakers within the same recording with suspiciously high similarity.

    These may be diarization errors (one person split into two labels).
    """
    print(f"\nDetecting same-recording anomalies (sim >= {threshold})...")

    anomalies = []

    for recording_id, recording in metadata['recordings'].items():
        speakers = list(recording['speakers'].keys())

        for i, spk_a in enumerate(speakers):
            for spk_b in speakers[i+1:]:
                key_a = f"{recording_id}::{spk_a}"
                key_b = f"{recording_id}::{spk_b}"

                if key_a not in embeddings or key_b not in embeddings:
                    continue

                centroid_a = compute_centroid(embeddings[key_a], use_medoid=USE_MEDOID)
                centroid_b = compute_centroid(embeddings[key_b], use_medoid=USE_MEDOID)
                sim = compute_similarity(centroid_a, centroid_b)

                if sim >= threshold:
                    info_a = recording['speakers'][spk_a]
                    info_b = recording['speakers'][spk_b]

                    anomalies.append({
                        'recording_id': recording_id,
                        'recording_title': recording.get('title', 'Unknown'),
                        'speaker_a': spk_a,
                        'speaker_b': spk_b,
                        'similarity': sim,
                        'duration_a': info_a.get('total_duration_s', 0),
                        'duration_b': info_b.get('total_duration_s', 0),
                        'participant_a': info_a.get('participant_name'),
                        'participant_b': info_b.get('participant_name'),
                    })

    print(f"  Found {len(anomalies)} anomalies")
    return anomalies


def generate_report(
    metadata: Dict,
    same_stats: SimilarityStats,
    diff_stats: SimilarityStats,
    threshold_metrics: List[ThresholdMetrics],
    centroid_comparison: Dict,
    chain_analysis: Dict,
    per_participant: Dict,
    anomalies: List[Dict],
) -> str:
    """Generate markdown report."""

    lines = [
        "# Speaker Identification Sensitivity Analysis",
        "",
        f"**Generated from:** {metadata['summary']['total_recordings']} recordings",
        f"**Labeled speakers:** {metadata['summary']['labeled_speakers']}",
        f"**Unique participants:** {metadata['summary']['unique_participants']}",
        "",
        "---",
        "",
        "## 1. Similarity Distributions",
        "",
        "### Same Person (Cross-Recording)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Count | {same_stats.count} pairs |",
        f"| Mean | {same_stats.mean:.3f} |",
        f"| Std Dev | {same_stats.std:.3f} |",
        f"| Min | {same_stats.min:.3f} |",
        f"| Max | {same_stats.max:.3f} |",
        f"| 5th percentile | {same_stats.p5:.3f} |",
        f"| 25th percentile | {same_stats.p25:.3f} |",
        f"| Median | {same_stats.median:.3f} |",
        f"| 75th percentile | {same_stats.p75:.3f} |",
        f"| 95th percentile | {same_stats.p95:.3f} |",
        "",
        "### Different People",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Count | {diff_stats.count} pairs |",
        f"| Mean | {diff_stats.mean:.3f} |",
        f"| Std Dev | {diff_stats.std:.3f} |",
        f"| Min | {diff_stats.min:.3f} |",
        f"| Max | {diff_stats.max:.3f} |",
        f"| 5th percentile | {diff_stats.p5:.3f} |",
        f"| 25th percentile | {diff_stats.p25:.3f} |",
        f"| Median | {diff_stats.median:.3f} |",
        f"| 75th percentile | {diff_stats.p75:.3f} |",
        f"| 95th percentile | {diff_stats.p95:.3f} |",
        "",
        f"**Separation:** {same_stats.mean - diff_stats.mean:.3f} (same - different means)",
        "",
        "---",
        "",
        "## 2. Threshold Analysis",
        "",
        "| Threshold | Precision | Recall | F1 | Accuracy | TP | FP | TN | FN |",
        "|-----------|-----------|--------|-------|----------|-----|-----|-----|-----|",
    ]

    best_f1 = max(threshold_metrics, key=lambda x: x.f1)
    best_precision_90 = None

    for m in threshold_metrics:
        marker = " **" if m.threshold == best_f1.threshold else ""
        lines.append(
            f"| {m.threshold:.2f}{marker} | {m.precision:.3f} | {m.recall:.3f} | "
            f"{m.f1:.3f} | {m.accuracy:.3f} | {m.true_positives} | {m.false_positives} | "
            f"{m.true_negatives} | {m.false_negatives} |"
        )
        if m.precision >= 0.95 and (best_precision_90 is None or m.recall > best_precision_90.recall):
            best_precision_90 = m

    lines.extend([
        "",
        f"**Best F1 Score:** {best_f1.threshold:.2f} (F1 = {best_f1.f1:.3f})",
    ])

    if best_precision_90:
        lines.append(f"**Best for High Precision (≥95%):** {best_precision_90.threshold:.2f} (P={best_precision_90.precision:.3f}, R={best_precision_90.recall:.3f})")

    lines.extend([
        "",
        "### Recommendations",
        "",
    ])

    # Find overlap zone
    overlap_min = diff_stats.p95
    overlap_max = same_stats.p5

    if overlap_max > overlap_min:
        lines.append(f"⚠️ **Overlap zone:** {overlap_min:.3f} - {overlap_max:.3f}")
        lines.append(f"   Similarities in this range are ambiguous.")
    else:
        lines.append(f"✅ **Clean separation:** Different-person max ({diff_stats.max:.3f}) < Same-person min ({same_stats.min:.3f})")

    lines.extend([
        "",
        f"- **Auto-assign threshold:** {best_precision_90.threshold if best_precision_90 else 0.80:.2f} (high confidence)",
        f"- **Suggest threshold:** {best_f1.threshold:.2f} (balanced)",
        f"- **Reject threshold:** {diff_stats.p95:.2f} (below this, definitely different)",
        "",
        "---",
        "",
        "## 3. Centroid vs Raw Embedding Comparison",
        "",
        f"Comparing {centroid_comparison['n_pairs']} same-person pairs across recordings:",
        "",
        "| Method | Mean Similarity | Std Dev | Min | Max |",
        "|--------|-----------------|---------|-----|-----|",
        f"| Centroid | {centroid_comparison['centroid']['mean']:.3f} | {centroid_comparison['centroid']['std']:.3f} | {centroid_comparison['centroid']['min']:.3f} | {centroid_comparison['centroid']['max']:.3f} |",
        f"| Raw (mean of pairs) | {centroid_comparison['raw_mean']['mean']:.3f} | {centroid_comparison['raw_mean']['std']:.3f} | {centroid_comparison['raw_mean']['min']:.3f} | {centroid_comparison['raw_mean']['max']:.3f} |",
        f"| Raw (max of pairs) | {centroid_comparison['raw_max']['mean']:.3f} | {centroid_comparison['raw_max']['std']:.3f} | {centroid_comparison['raw_max']['min']:.3f} | {centroid_comparison['raw_max']['max']:.3f} |",
        "",
    ])

    centroid_better = centroid_comparison['centroid']['mean'] > centroid_comparison['raw_mean']['mean']
    if centroid_better:
        improvement = centroid_comparison['centroid']['mean'] - centroid_comparison['raw_mean']['mean']
        lines.append(f"**Centroid is better** by {improvement:.3f} on average")
    else:
        lines.append("**Raw embedding mean is better** (unusual)")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Transitive Chain Risk Analysis",
        "",
        f"Testing at threshold {chain_analysis['threshold']}:",
        "",
        f"- Edges above threshold: {chain_analysis['edges_above_threshold']}",
        f"- A→B→C chains checked: {chain_analysis['chains_checked']}",
        f"- **Violations found: {chain_analysis['violations']}**",
        f"- Violation rate: {chain_analysis['violation_rate']*100:.2f}%",
        "",
    ])

    if chain_analysis['violations'] > 0:
        lines.append("⚠️ **Chain risk detected.** Some A→B→C chains link different people.")
        lines.append("")
        if chain_analysis['examples']:
            lines.append("Examples:")
            for ex in chain_analysis['examples'][:3]:
                lines.append(f"- {ex['speaker_a'].split('::')[1]} ↔ {ex['speaker_b'].split('::')[1]} ↔ {ex['speaker_c'].split('::')[1]}")
                lines.append(f"  sim(A,B)={ex['sim_ab']:.3f}, sim(B,C)={ex['sim_bc']:.3f}, sim(A,C)={ex['sim_ac']:.3f}")
    else:
        lines.append("✅ **No chain violations found** at this threshold.")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Per-Participant Consistency",
        "",
        "How consistent are embeddings for each known participant?",
        "",
        "| Participant | Recordings | Mean Sim | Min Sim | Max Sim | Std |",
        "|-------------|------------|----------|---------|---------|-----|",
    ])

    sorted_participants = sorted(
        per_participant.values(),
        key=lambda x: x['n_recordings'],
        reverse=True
    )

    for p in sorted_participants[:15]:  # Top 15
        lines.append(
            f"| {p['name']} | {p['n_recordings']} | {p['mean_similarity']:.3f} | "
            f"{p['min_similarity']:.3f} | {p['max_similarity']:.3f} | {p['std']:.3f} |"
        )

    # Identify problematic participants
    low_consistency = [p for p in sorted_participants if p['min_similarity'] < 0.70]
    if low_consistency:
        lines.extend([
            "",
            "⚠️ **Participants with low minimum similarity (<0.70):**",
        ])
        for p in low_consistency:
            lines.append(f"- {p['name']}: min={p['min_similarity']:.3f}")

    lines.extend([
        "",
        "---",
        "",
        "## 6. Same-Recording Anomalies (Potential Diarization Errors)",
        "",
        f"Speakers within the same recording with similarity ≥ 0.75:",
        "",
    ])

    if anomalies:
        lines.append("| Recording | Speaker A | Speaker B | Similarity | Duration A | Duration B |")
        lines.append("|-----------|-----------|-----------|------------|------------|------------|")

        for a in sorted(anomalies, key=lambda x: -x['similarity'])[:20]:
            title = a['recording_title'][:40] + "..." if len(a['recording_title']) > 40 else a['recording_title']
            lines.append(
                f"| {title} | {a['speaker_a']} | {a['speaker_b']} | "
                f"{a['similarity']:.3f} | {a['duration_a']:.0f}s | {a['duration_b']:.0f}s |"
            )

        # Likely fragments (asymmetric duration)
        fragments = [a for a in anomalies if min(a['duration_a'], a['duration_b']) / max(a['duration_a'], a['duration_b']) < 0.3]
        if fragments:
            lines.extend([
                "",
                f"**Likely fragments (one speaker has <30% of other's duration):** {len(fragments)}",
            ])
    else:
        lines.append("No same-recording anomalies found.")

    lines.extend([
        "",
        "---",
        "",
        "## Summary & Recommendations",
        "",
        "### Threshold Recommendations",
        "",
        f"1. **High Confidence (auto-assign):** ≥ {best_precision_90.threshold if best_precision_90 else 0.80:.2f}",
        f"2. **Medium Confidence (suggest):** {best_f1.threshold:.2f} - {best_precision_90.threshold if best_precision_90 else 0.80:.2f}",
        f"3. **Reject (different person):** < {diff_stats.p95:.2f}",
        "",
        "### Approach Recommendations",
        "",
    ])

    if centroid_better:
        lines.append("✅ Use **centroid-based matching** (better separation)")
    else:
        lines.append("⚠️ Consider **raw embedding matching** (centroid didn't help)")

    if chain_analysis['violation_rate'] > 0.05:
        lines.append("⚠️ Avoid **transitive chains** (>5% violation rate)")
    else:
        lines.append("✅ Transitive chains are relatively safe (<5% violations)")

    if fragments := [a for a in anomalies if min(a['duration_a'], a['duration_b']) / max(a['duration_a'], a['duration_b']) < 0.3]:
        lines.append(f"⚠️ Consider **merging {len(fragments)} likely fragments** before cross-recording matching")

    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Sensitivity analysis for speaker identification")
    parser.add_argument("--embeddings-dir", default="embeddings", help="Directory with embeddings")
    parser.add_argument("--output-report", default="sensitivity_report.md", help="Output report path")
    parser.add_argument("--chain-threshold", type=float, default=0.75, help="Threshold for chain analysis")
    parser.add_argument("--anomaly-threshold", type=float, default=0.75, help="Threshold for anomaly detection")
    parser.add_argument("--exclude-file", type=str, default=None, help="File with recording IDs to exclude")
    parser.add_argument("--use-medoid", action="store_true", help="Use medoid instead of centroid")
    args = parser.parse_args()

    # Set global flag for medoid mode
    global USE_MEDOID
    USE_MEDOID = args.use_medoid

    print("=" * 70)
    print("SPEAKER IDENTIFICATION SENSITIVITY ANALYSIS")
    print("=" * 70)

    # Load exclusion list
    exclude_recordings = load_exclude_list(args.exclude_file)
    if exclude_recordings:
        print(f"\nExcluding {len(exclude_recordings)} recordings")

    # Load data
    metadata, embeddings = load_data(args.embeddings_dir)

    # Get labeled speakers
    labeled_speakers = get_labeled_speakers(metadata, exclude_recordings)

    if len(labeled_speakers) < 2:
        print("\nError: Need at least 2 participants with multiple recordings for analysis.")
        sys.exit(1)

    # Build similarity pairs
    same_sims, diff_sims = build_similarity_pairs(metadata, embeddings, labeled_speakers)

    if len(same_sims) < 10:
        print(f"\nWarning: Only {len(same_sims)} same-person pairs. Results may be unreliable.")

    # Compute statistics
    print("\nComputing statistics...")
    same_stats = compute_stats(same_sims)
    diff_stats = compute_stats(diff_sims)

    print(f"\nSame-person similarities:")
    print(f"  Mean: {same_stats.mean:.3f} ± {same_stats.std:.3f}")
    print(f"  Range: [{same_stats.min:.3f}, {same_stats.max:.3f}]")

    print(f"\nDifferent-person similarities:")
    print(f"  Mean: {diff_stats.mean:.3f} ± {diff_stats.std:.3f}")
    print(f"  Range: [{diff_stats.min:.3f}, {diff_stats.max:.3f}]")

    # Threshold analysis
    print("\nAnalyzing thresholds...")
    threshold_metrics = analyze_thresholds(same_sims, diff_sims)

    best_f1 = max(threshold_metrics, key=lambda x: x.f1)
    print(f"  Best F1: {best_f1.f1:.3f} at threshold {best_f1.threshold:.2f}")

    # Centroid vs raw comparison
    centroid_comparison = compare_centroid_vs_raw(metadata, embeddings, labeled_speakers)

    print(f"  Centroid mean similarity: {centroid_comparison['centroid']['mean']:.3f}")
    print(f"  Raw mean similarity: {centroid_comparison['raw_mean']['mean']:.3f}")

    # Chain risk analysis
    chain_analysis = analyze_chain_risk(metadata, embeddings, labeled_speakers, args.chain_threshold)

    print(f"  Chain violations: {chain_analysis['violations']} / {chain_analysis['chains_checked']}")

    # Per-participant analysis
    per_participant = analyze_per_participant(metadata, embeddings, labeled_speakers)

    # Same-recording anomalies
    anomalies = detect_same_recording_anomalies(metadata, embeddings, args.anomaly_threshold)

    # Generate report
    print("\nGenerating report...")
    report = generate_report(
        metadata,
        same_stats,
        diff_stats,
        threshold_metrics,
        centroid_comparison,
        chain_analysis,
        per_participant,
        anomalies,
    )

    # Save report
    output_path = args.output_report
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"\n{'=' * 70}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 70}")
    print(f"\nReport saved to: {output_path}")

    # Quick summary
    print("\nQuick Summary:")
    print(f"  Same-person mean: {same_stats.mean:.3f}")
    print(f"  Different-person mean: {diff_stats.mean:.3f}")
    print(f"  Separation: {same_stats.mean - diff_stats.mean:.3f}")
    print(f"  Recommended threshold: {best_f1.threshold:.2f}")
    print(f"  Same-recording anomalies: {len(anomalies)}")


if __name__ == "__main__":
    main()
