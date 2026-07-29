#!/usr/bin/env python3
"""
Speaker Identification Experiment

This script runs the complete speaker identification experiment:
1. Builds speaker profiles from labeled meetings
2. Identifies speakers in unlabeled meetings
3. Reports results and accuracy metrics

The experiment uses ECAPA-TDNN embeddings for cross-meeting speaker recognition.

Usage:
    # Full experiment
    python run_experiment.py --user-id YOUR_USER_ID

    # Build profiles only
    python run_experiment.py --user-id YOUR_USER_ID --build-only

    # Identify only (using existing profiles)
    python run_experiment.py --user-id YOUR_USER_ID --identify-only --profiles speaker_profiles.json

    # Cross-validation experiment
    python run_experiment.py --user-id YOUR_USER_ID --cross-validate
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import random

# Add parent directory for shared_quickscribe_py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data_loader import DataLoader, LabeledMeeting
from profile_builder import ProfileBuilder
from speaker_identifier import SpeakerIdentifier, MeetingIdentificationResult
from speaker_embedder import SpeakerProfileDB


def run_full_experiment(user_id: str,
                       profiles_output: str = "speaker_profiles.json",
                       high_threshold: float = 0.78,
                       low_threshold: float = 0.68,
                       max_build_meetings: Optional[int] = None,
                       max_identify_meetings: Optional[int] = None,
                       audio_cache_dir: Optional[str] = None) -> Dict:
    """
    Run the complete speaker identification experiment.

    Returns:
        Dictionary with experiment results and statistics
    """
    print("=" * 60)
    print("SPEAKER IDENTIFICATION EXPERIMENT")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print(f"High threshold: {high_threshold}")
    print(f"Low threshold: {low_threshold}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "user_id": user_id,
        "started_at": datetime.now().isoformat(),
        "thresholds": {
            "high": high_threshold,
            "low": low_threshold
        }
    }

    # Phase 1: Build profiles from labeled meetings
    print("\n" + "=" * 40)
    print("PHASE 1: Building Speaker Profiles")
    print("=" * 40)

    builder = ProfileBuilder(
        user_id=user_id,
        audio_cache_dir=audio_cache_dir
    )

    profile_db = builder.build_profiles(max_meetings=max_build_meetings)
    builder.save_profiles(profiles_output)

    results["build_stats"] = {
        "meetings_processed": builder.stats.meetings_processed,
        "participants_found": builder.stats.participants_found,
        "total_segments": builder.stats.total_segments,
        "segments_with_embeddings": builder.stats.segments_with_embeddings,
        "total_audio_minutes": builder.stats.total_audio_duration_s / 60
    }

    results["profiles"] = {
        pid: {
            "display_name": p.display_name,
            "n_samples": p.n_samples,
            "meeting_count": len(p.recording_ids),
            "embedding_std": p.embedding_std
        }
        for pid, p in profile_db.profiles.items()
    }

    # Phase 2: Identify speakers in unlabeled meetings
    print("\n" + "=" * 40)
    print("PHASE 2: Identifying Speakers")
    print("=" * 40)

    identifier = SpeakerIdentifier(
        user_id=user_id,
        profile_db=profile_db,
        audio_cache_dir=audio_cache_dir,
        high_threshold=high_threshold,
        low_threshold=low_threshold
    )

    identification_results = identifier.identify_all_meetings(max_meetings=max_identify_meetings)

    results["identification_stats"] = {
        "meetings_processed": identifier.stats.meetings_processed,
        "total_speakers": identifier.stats.total_speakers,
        "auto_identified": identifier.stats.auto_identified,
        "suggested": identifier.stats.suggested,
        "unknown": identifier.stats.unknown,
        "identification_rate": identifier.stats.identification_rate,
        "suggestion_rate": identifier.stats.suggestion_rate
    }

    # Detailed meeting results
    results["meeting_results"] = []
    for mr in identification_results:
        meeting_result = {
            "recording_id": mr.recording_id,
            "title": mr.title,
            "speakers": []
        }
        for sm in mr.speaker_matches:
            meeting_result["speakers"].append({
                "speaker_label": sm.speaker_label,
                "status": sm.status,
                "matched_participant": sm.matched_display_name,
                "similarity": sm.similarity,
                "duration_s": sm.total_duration_s
            })
        results["meeting_results"].append(meeting_result)

    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"\nProfile Building:")
    print(f"  Meetings processed: {results['build_stats']['meetings_processed']}")
    print(f"  Unique speakers: {results['build_stats']['participants_found']}")
    print(f"  Total audio: {results['build_stats']['total_audio_minutes']:.1f} minutes")

    print(f"\nSpeaker Identification:")
    print(f"  Meetings processed: {results['identification_stats']['meetings_processed']}")
    print(f"  Total speakers: {results['identification_stats']['total_speakers']}")
    print(f"  Auto-identified: {results['identification_stats']['auto_identified']} "
          f"({results['identification_stats']['identification_rate']:.1f}%)")
    print(f"  Suggested: {results['identification_stats']['suggested']}")
    print(f"  Unknown: {results['identification_stats']['unknown']}")
    print(f"  Overall recognition: {results['identification_stats']['suggestion_rate']:.1f}%")

    results["completed_at"] = datetime.now().isoformat()

    return results


def run_cross_validation(user_id: str,
                        n_folds: int = 5,
                        high_threshold: float = 0.78,
                        low_threshold: float = 0.68,
                        audio_cache_dir: Optional[str] = None) -> Dict:
    """
    Run cross-validation experiment.

    Splits labeled meetings into folds, trains on n-1 folds, tests on 1 fold.
    This provides a more realistic estimate of accuracy.

    Returns:
        Dictionary with cross-validation results
    """
    print("=" * 60)
    print("CROSS-VALIDATION EXPERIMENT")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print(f"Folds: {n_folds}")
    print(f"Thresholds: high={high_threshold}, low={low_threshold}")
    print("=" * 60)

    # Load all labeled meetings
    data_loader = DataLoader()
    all_meetings = data_loader.get_labeled_meetings(user_id, min_participants=1)

    if len(all_meetings) < n_folds:
        print(f"Error: Only {len(all_meetings)} labeled meetings, need at least {n_folds}")
        return {"error": "Not enough labeled meetings"}

    print(f"\nTotal labeled meetings: {len(all_meetings)}")

    # Shuffle meetings
    random.shuffle(all_meetings)

    # Create folds
    fold_size = len(all_meetings) // n_folds
    folds: List[List[LabeledMeeting]] = []
    for i in range(n_folds):
        start = i * fold_size
        end = start + fold_size if i < n_folds - 1 else len(all_meetings)
        folds.append(all_meetings[start:end])

    fold_results = []

    for fold_idx in range(n_folds):
        print(f"\n{'='*40}")
        print(f"FOLD {fold_idx + 1}/{n_folds}")
        print(f"{'='*40}")

        # Split into train and test
        test_meetings = folds[fold_idx]
        train_meetings = []
        for i, fold in enumerate(folds):
            if i != fold_idx:
                train_meetings.extend(fold)

        print(f"Training on {len(train_meetings)} meetings, testing on {len(test_meetings)} meetings")

        # Build profiles from training set
        # We need to manually process since ProfileBuilder normally fetches from DB
        from speaker_embedder import EcapaEmbedder, SpeakerProfileDB, merge_adjacent_segments, l2_normalize

        embedder = EcapaEmbedder()
        profile_db = SpeakerProfileDB()

        for meeting in train_meetings:
            # Download audio
            try:
                audio_path = data_loader.download_audio(meeting.recording, output_dir=audio_cache_dir)
            except Exception as e:
                print(f"  Error downloading audio for {meeting.title}: {e}")
                continue

            # Group segments by participant
            for pid, participant in meeting.participant_map.items():
                segments = meeting.get_segments_for_participant(pid)
                if not segments:
                    continue

                # Get time ranges
                segment_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in segments]
                merged = merge_adjacent_segments(segment_tuples, max_gap_s=0.35)
                time_ranges = [(s, e) for s, e, _ in merged]

                # Extract embeddings
                embeddings = embedder.embeddings_for_segments(audio_path, time_ranges)
                valid_embeddings = [e for e in embeddings if e is not None]

                if valid_embeddings:
                    profile = profile_db.get_or_create(pid, participant.displayName)
                    profile.update(valid_embeddings, recording_id=meeting.recording_id)

        print(f"  Built profiles for {len(profile_db.profiles)} speakers")

        # Test on held-out meetings
        # For each test meeting, pretend we don't know the labels
        correct = 0
        incorrect = 0
        unknown = 0
        total = 0

        for meeting in test_meetings:
            try:
                audio_path = data_loader.download_audio(meeting.recording, output_dir=audio_cache_dir)
            except Exception:
                continue

            # Build ground truth
            ground_truth: Dict[str, str] = {}  # speaker_label -> participant_id
            for seg in meeting.speaker_segments:
                if seg.participant_id:
                    ground_truth[seg.speaker_label] = seg.participant_id

            # Group segments by speaker label
            speaker_labels = list(set(seg.speaker_label for seg in meeting.speaker_segments))

            for speaker_label in speaker_labels:
                segments = [s for s in meeting.speaker_segments if s.speaker_label == speaker_label]
                segment_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in segments]
                merged = merge_adjacent_segments(segment_tuples, max_gap_s=0.35)
                time_ranges = [(s, e) for s, e, _ in merged]

                embeddings = embedder.embeddings_for_segments(audio_path, time_ranges)
                valid_embeddings = [e for e in embeddings if e is not None]

                if not valid_embeddings:
                    continue

                # Compute centroid
                import numpy as np
                emb_stack = np.stack([l2_normalize(e) for e in valid_embeddings], axis=0)
                speaker_centroid = l2_normalize(emb_stack.mean(axis=0))

                # Match
                match = profile_db.match_with_confidence(
                    speaker_centroid,
                    high_threshold=high_threshold,
                    low_threshold=low_threshold
                )

                actual_pid = ground_truth.get(speaker_label)
                predicted_pid = match["participant_id"]

                total += 1

                if predicted_pid is None:
                    unknown += 1
                elif predicted_pid == actual_pid:
                    correct += 1
                else:
                    incorrect += 1

        accuracy = correct / total * 100 if total > 0 else 0
        print(f"  Results: {correct}/{total} correct ({accuracy:.1f}%), "
              f"{incorrect} incorrect, {unknown} unknown")

        fold_results.append({
            "fold": fold_idx + 1,
            "train_meetings": len(train_meetings),
            "test_meetings": len(test_meetings),
            "profiles_built": len(profile_db.profiles),
            "total_speakers": total,
            "correct": correct,
            "incorrect": incorrect,
            "unknown": unknown,
            "accuracy": accuracy
        })

    # Aggregate results
    avg_accuracy = sum(f["accuracy"] for f in fold_results) / len(fold_results)
    total_correct = sum(f["correct"] for f in fold_results)
    total_speakers = sum(f["total_speakers"] for f in fold_results)
    overall_accuracy = total_correct / total_speakers * 100 if total_speakers > 0 else 0

    print("\n" + "=" * 60)
    print("CROSS-VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Average fold accuracy: {avg_accuracy:.1f}%")
    print(f"Overall accuracy: {total_correct}/{total_speakers} ({overall_accuracy:.1f}%)")

    return {
        "n_folds": n_folds,
        "fold_results": fold_results,
        "average_accuracy": avg_accuracy,
        "overall_accuracy": overall_accuracy,
        "total_correct": total_correct,
        "total_speakers": total_speakers
    }


def main():
    parser = argparse.ArgumentParser(
        description="Speaker Identification Experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full experiment
  python run_experiment.py --user-id YOUR_USER_ID

  # Build profiles only
  python run_experiment.py --user-id YOUR_USER_ID --build-only

  # Identify using existing profiles
  python run_experiment.py --user-id YOUR_USER_ID --identify-only --profiles speaker_profiles.json

  # Cross-validation
  python run_experiment.py --user-id YOUR_USER_ID --cross-validate --folds 5
        """
    )

    parser.add_argument("--user-id", required=True, help="User ID to process")
    parser.add_argument("--build-only", action="store_true",
                        help="Only build profiles, don't identify")
    parser.add_argument("--identify-only", action="store_true",
                        help="Only identify, use existing profiles")
    parser.add_argument("--cross-validate", action="store_true",
                        help="Run cross-validation experiment")
    parser.add_argument("--profiles", default="speaker_profiles.json",
                        help="Path to speaker profiles JSON")
    parser.add_argument("--output", default="experiment_results.json",
                        help="Path to save experiment results")
    parser.add_argument("--high-threshold", type=float, default=0.78,
                        help="Similarity threshold for auto-identification")
    parser.add_argument("--low-threshold", type=float, default=0.68,
                        help="Similarity threshold for suggestions")
    parser.add_argument("--max-build", type=int,
                        help="Maximum meetings to use for building profiles")
    parser.add_argument("--max-identify", type=int,
                        help="Maximum meetings to identify")
    parser.add_argument("--folds", type=int, default=5,
                        help="Number of folds for cross-validation")
    parser.add_argument("--audio-cache", help="Directory to cache audio files")

    args = parser.parse_args()

    if args.cross_validate:
        results = run_cross_validation(
            user_id=args.user_id,
            n_folds=args.folds,
            high_threshold=args.high_threshold,
            low_threshold=args.low_threshold,
            audio_cache_dir=args.audio_cache
        )
    elif args.build_only:
        builder = ProfileBuilder(
            user_id=args.user_id,
            audio_cache_dir=args.audio_cache
        )
        builder.build_profiles(max_meetings=args.max_build)
        builder.save_profiles(args.profiles)
        results = {"mode": "build_only", "profiles_path": args.profiles}
    elif args.identify_only:
        identifier = SpeakerIdentifier(
            user_id=args.user_id,
            profiles_path=args.profiles,
            audio_cache_dir=args.audio_cache,
            high_threshold=args.high_threshold,
            low_threshold=args.low_threshold
        )
        id_results = identifier.identify_all_meetings(max_meetings=args.max_identify)
        identifier.print_detailed_results(id_results)
        results = {"mode": "identify_only", "stats": vars(identifier.stats)}
    else:
        results = run_full_experiment(
            user_id=args.user_id,
            profiles_output=args.profiles,
            high_threshold=args.high_threshold,
            low_threshold=args.low_threshold,
            max_build_meetings=args.max_build,
            max_identify_meetings=args.max_identify,
            audio_cache_dir=args.audio_cache
        )

    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
