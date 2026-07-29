#!/usr/bin/env python3
"""
List suspicious speaker labels for manual review.
Outputs recording title, date, and the problematic label.
"""

import argparse
import json
import os
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime


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


def load_data(embeddings_dir: str = "embeddings"):
    """Load metadata and embeddings."""
    embeddings_path = Path(embeddings_dir)

    with open(embeddings_path / "metadata.json") as f:
        metadata = json.load(f)

    embeddings = dict(np.load(embeddings_path / "embeddings.npz"))

    return metadata, embeddings


def compute_centroid(embeddings: np.ndarray, drop_count: int = 2) -> np.ndarray:
    """
    Compute robust L2-normalized centroid using coherence filtering.
    """
    n = len(embeddings)
    if n <= 3:
        centroid = embeddings.mean(axis=0)
        return centroid / (np.linalg.norm(centroid) + 1e-8)

    drop_count = min(drop_count, n - 3)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / (norms + 1e-8)
    similarity_matrix = np.dot(normalized, normalized.T)
    mean_similarities = (similarity_matrix.sum(axis=1) - 1.0) / (n - 1)
    n_keep = n - drop_count
    keep_indices = np.argsort(mean_similarities)[-n_keep:]
    clean_embeddings = normalized[keep_indices]
    centroid = clean_embeddings.mean(axis=0)
    norm = np.linalg.norm(centroid)
    return centroid / norm if norm > 1e-8 else centroid

def get_participant_embeddings(metadata: dict, embeddings: dict, exclude_recordings: set = None) -> dict:
    """Build dict: participant_name -> list of (recording_id, speaker_label, centroid)"""
    exclude_recordings = exclude_recordings or set()
    participants = defaultdict(list)

    for rec_id, rec in metadata["recordings"].items():
        if rec_id in exclude_recordings:
            continue
        for speaker_label, speaker in rec["speakers"].items():
            if speaker["participant_name"]:
                key = speaker["embedding_key"]
                if key in embeddings:
                    emb = embeddings[key]
                    centroid = compute_centroid(emb)
                    participants[speaker["participant_name"]].append({
                        "recording_id": rec_id,
                        "speaker_label": speaker_label,
                        "title": rec["title"],
                        "date": rec["recorded_at"][:10],
                        "centroid": centroid,
                        "duration_s": speaker["total_duration_s"]
                    })

    return participants

def cosine_sim(a, b):
    return float(np.dot(a, b))

def format_date(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d")
    except:
        return date_str[:10]

def main():
    parser = argparse.ArgumentParser(description="List suspicious speaker labels for manual review")
    parser.add_argument("--embeddings-dir", default="embeddings", help="Directory with embeddings")
    parser.add_argument("--exclude-file", type=str, default=None, help="File with recording IDs to exclude")
    args = parser.parse_args()

    print("Loading data...")
    exclude_recordings = load_exclude_list(args.exclude_file)
    if exclude_recordings:
        print(f"Excluding {len(exclude_recordings)} recordings")

    metadata, embeddings = load_data(args.embeddings_dir)
    participants = get_participant_embeddings(metadata, embeddings, exclude_recordings)

    print("\n" + "="*80)
    print("SUSPICIOUS LABELS TO REVIEW")
    print("="*80)

    # -------------------------------------------------------------------------
    # PART 1: Same-person low similarity (recordings that don't match the group)
    # -------------------------------------------------------------------------
    print("\n" + "-"*80)
    print("PART 1: LOW SAME-PERSON SIMILARITY")
    print("These recordings are labeled as a person but don't match their other recordings.")
    print("The speaker might be mislabeled (it's someone else).")
    print("-"*80 + "\n")

    suspicious_same = []

    for name, recs in participants.items():
        if len(recs) < 3:  # Need at least 3 recordings to identify outliers
            continue

        # Calculate each recording's average similarity to all others
        for i, rec in enumerate(recs):
            sims = []
            for j, other in enumerate(recs):
                if i != j:
                    sims.append(cosine_sim(rec["centroid"], other["centroid"]))

            avg_sim = np.mean(sims) if sims else 0
            min_sim = np.min(sims) if sims else 0

            # Flag if average similarity to group is very low
            if avg_sim < 0.4:  # Very suspicious
                suspicious_same.append({
                    "participant": name,
                    "recording_id": rec["recording_id"],
                    "speaker_label": rec["speaker_label"],
                    "title": rec["title"],
                    "date": format_date(rec["date"]),
                    "avg_sim": avg_sim,
                    "min_sim": min_sim,
                    "duration_s": rec["duration_s"],
                    "severity": "HIGH" if avg_sim < 0.2 else "MEDIUM"
                })

    # Sort by similarity (lowest first)
    suspicious_same.sort(key=lambda x: x["avg_sim"])

    for i, item in enumerate(suspicious_same, 1):
        print(f"{i}. [{item['severity']}] {item['participant']}")
        print(f"   Recording: {item['title'][:60]}...")
        print(f"   Date: {item['date']}")
        print(f"   Speaker: {item['speaker_label']} ({item['duration_s']:.0f}s audio)")
        print(f"   Avg similarity to other {item['participant']} recordings: {item['avg_sim']:.3f}")
        print(f"   Recording ID: {item['recording_id']}")
        print()

    # -------------------------------------------------------------------------
    # PART 2: Different-person high similarity (might be same person, wrong label)
    # -------------------------------------------------------------------------
    print("\n" + "-"*80)
    print("PART 2: HIGH CROSS-PERSON SIMILARITY")
    print("These pairs are labeled as DIFFERENT people but sound very similar.")
    print("One of them might be mislabeled.")
    print("-"*80 + "\n")

    suspicious_cross = []
    participant_names = list(participants.keys())

    for i, name1 in enumerate(participant_names):
        for name2 in participant_names[i+1:]:
            # Compare all recording pairs between these two people
            for rec1 in participants[name1]:
                for rec2 in participants[name2]:
                    sim = cosine_sim(rec1["centroid"], rec2["centroid"])

                    if sim > 0.65:  # Unusually high for different people
                        suspicious_cross.append({
                            "person1": name1,
                            "person2": name2,
                            "rec1_id": rec1["recording_id"],
                            "rec2_id": rec2["recording_id"],
                            "rec1_title": rec1["title"],
                            "rec2_title": rec2["title"],
                            "rec1_date": format_date(rec1["date"]),
                            "rec2_date": format_date(rec2["date"]),
                            "rec1_speaker": rec1["speaker_label"],
                            "rec2_speaker": rec2["speaker_label"],
                            "similarity": sim,
                            "severity": "HIGH" if sim > 0.8 else "MEDIUM"
                        })

    # Sort by similarity (highest first)
    suspicious_cross.sort(key=lambda x: -x["similarity"])

    # Deduplicate - show each recording only once
    seen_pairs = set()
    unique_cross = []
    for item in suspicious_cross:
        pair = tuple(sorted([item["rec1_id"], item["rec2_id"]]))
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            unique_cross.append(item)

    for i, item in enumerate(unique_cross[:20], 1):  # Top 20
        print(f"{i}. [{item['severity']}] {item['person1']} vs {item['person2']} (sim={item['similarity']:.3f})")
        print(f"   Recording A ({item['person1']}): {item['rec1_title'][:50]}...")
        print(f"      Date: {item['rec1_date']}, Speaker: {item['rec1_speaker']}")
        print(f"      ID: {item['rec1_id']}")
        print(f"   Recording B ({item['person2']}): {item['rec2_title'][:50]}...")
        print(f"      Date: {item['rec2_date']}, Speaker: {item['rec2_speaker']}")
        print(f"      ID: {item['rec2_id']}")
        print()

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nLow same-person similarity: {len(suspicious_same)} recordings")
    print(f"High cross-person similarity: {len(unique_cross)} pairs")

    print("\n" + "-"*40)
    print("PRIORITY RECORDINGS TO CHECK")
    print("-"*40)
    print("\nThese are the most suspicious - check these first:\n")

    # Top 5 from each category
    priority = []
    for item in suspicious_same[:5]:
        priority.append(f"- {item['date']} | {item['participant']} ({item['speaker_label']}) | {item['title'][:40]}...")
    for item in unique_cross[:5]:
        priority.append(f"- {item['rec1_date']} | {item['person1']} vs {item['person2']} | {item['rec1_title'][:40]}...")

    for p in priority:
        print(p)

if __name__ == "__main__":
    main()
