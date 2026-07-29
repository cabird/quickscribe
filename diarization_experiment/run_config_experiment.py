#!/usr/bin/env python3
"""
Config-based Speaker Identification Experiment

Run a controlled experiment with specific participants and recordings
defined in a YAML config file.

Usage:
    python run_config_experiment.py --config experiment.yaml --user-id USER_ID
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import random
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import yaml

# Add parent directory for shared_quickscribe_py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from data_loader import DataLoader, LabeledMeeting, SpeakerSegment, _parse_azure_transcript_json
from speaker_embedder import EcapaEmbedder, SpeakerProfileDB, SpeakerProfile, merge_adjacent_segments, l2_normalize
from shared_quickscribe_py.cosmos import Recording, Transcription
import numpy as np


@dataclass
class ExperimentConfig:
    """Parsed experiment configuration."""
    # User
    user_id: str

    # Learning config
    learn_participant_names: List[str]
    learn_participant_ids: List[str]
    max_recordings_per_participant: Optional[int]
    exclude_recording_ids: List[str]

    # Validation config
    validate_recording_ids: List[str]
    validate_recording_titles: List[str]
    validate_max_recordings: Optional[int]

    # Thresholds
    high_threshold: float
    low_threshold: float

    # Output
    profiles_file: str
    results_file: str
    audio_cache_dir: str


def load_config(config_path: str, user_id_override: Optional[str] = None) -> ExperimentConfig:
    """Load and parse YAML config file."""
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)

    # Get user_id from config or override
    user_id = user_id_override or cfg.get('user_id')
    if not user_id:
        raise ValueError("user_id must be specified in config file or via --user-id")

    learn = cfg.get('learn', {})
    validate = cfg.get('validate', {})
    thresholds = cfg.get('thresholds', {})
    output = cfg.get('output', {})

    # Parse participants
    participant_names = []
    participant_ids = []
    for p in learn.get('participants', []):
        if isinstance(p, str):
            participant_names.append(p)
        elif isinstance(p, dict):
            if 'name' in p:
                participant_names.append(p['name'])
            if 'id' in p:
                participant_ids.append(p['id'])

    # Parse validation recordings
    recording_ids = []
    recording_titles = []
    for r in validate.get('recordings', []):
        if isinstance(r, str):
            recording_titles.append(r)
        elif isinstance(r, dict):
            if 'id' in r:
                recording_ids.append(r['id'])
            if 'title' in r:
                recording_titles.append(r['title'])

    return ExperimentConfig(
        user_id=user_id,
        learn_participant_names=participant_names,
        learn_participant_ids=participant_ids,
        max_recordings_per_participant=learn.get('max_recordings_per_participant'),
        exclude_recording_ids=learn.get('exclude_recording_ids', []),
        validate_recording_ids=recording_ids,
        validate_recording_titles=recording_titles,
        validate_max_recordings=validate.get('max_recordings'),
        high_threshold=thresholds.get('high', 0.78),
        low_threshold=thresholds.get('low', 0.68),
        profiles_file=output.get('profiles_file', 'speaker_profiles.json'),
        results_file=output.get('results_file', 'experiment_results.json'),
        audio_cache_dir=output.get('audio_cache_dir', './audio_cache'),
    )


def find_participant_ids(data_loader: DataLoader, user_id: str,
                         names: List[str], ids: List[str]) -> Dict[str, str]:
    """
    Resolve participant names to IDs.

    Returns dict mapping participant_id -> display_name
    """
    all_participants = data_loader.get_all_participants(user_id)

    result = {}

    # Add explicitly specified IDs
    for pid in ids:
        for p in all_participants:
            if p.id == pid:
                result[pid] = p.displayName
                break

    # Find by name (case-insensitive partial match on displayName or firstName + lastName)
    for name in names:
        name_lower = name.lower()
        for p in all_participants:
            # Check displayName
            if name_lower in p.displayName.lower():
                result[p.id] = p.displayName
                break
            # Check firstName + lastName
            first = (getattr(p, 'firstName', '') or '').lower()
            last = (getattr(p, 'lastName', '') or '').lower()
            full_name = f"{first} {last}".strip()
            if name_lower in full_name or full_name in name_lower:
                result[p.id] = p.displayName
                break

    return result


def find_validation_recordings(data_loader: DataLoader, user_id: str,
                               config: ExperimentConfig) -> List[Dict]:
    """
    Find recordings to use for validation based on config.

    Returns list of recording data dicts.
    """
    recordings = []

    # Find by ID
    for rec_id in config.validate_recording_ids:
        results = list(data_loader.container.query_items(
            query="""
            SELECT c.id, c.user_id, c.title, c.original_filename, c.unique_filename,
                   c.duration, c.transcription_id, c.transcription_status
            FROM c WHERE c.id = @id
            """,
            parameters=[{'name': '@id', 'value': rec_id}],
            enable_cross_partition_query=True
        ))
        recordings.extend(results)

    # Find by title (partial match)
    for title in config.validate_recording_titles:
        results = list(data_loader.container.query_items(
            query="""
            SELECT c.id, c.user_id, c.title, c.original_filename, c.unique_filename,
                   c.duration, c.transcription_id, c.transcription_status
            FROM c
            WHERE c.transcription_status = 'completed'
            AND c.user_id = @user_id
            AND CONTAINS(LOWER(c.title), @title)
            """,
            parameters=[
                {'name': '@user_id', 'value': user_id},
                {'name': '@title', 'value': title.lower()}
            ],
            enable_cross_partition_query=True
        ))
        recordings.extend(results)

    # Deduplicate by ID
    seen = set()
    unique = []
    for r in recordings:
        if r['id'] not in seen:
            seen.add(r['id'])
            unique.append(r)

    # Apply max limit
    if config.validate_max_recordings:
        unique = unique[:config.validate_max_recordings]

    return unique


def build_profiles_for_participants(
    data_loader: DataLoader,
    embedder: EcapaEmbedder,
    user_id: str,
    participant_ids: Dict[str, str],
    config: ExperimentConfig
) -> SpeakerProfileDB:
    """
    Build voice profiles for specified participants.
    """
    print("\n" + "=" * 60)
    print("PHASE 1: Building Speaker Profiles")
    print("=" * 60)

    profile_db = SpeakerProfileDB()

    os.makedirs(config.audio_cache_dir, exist_ok=True)

    # Pre-fetch all recordings with their transcription speaker_mappings
    # This is more efficient than querying per-participant
    print("\n  Fetching all recordings with speaker mappings...")
    all_recordings = list(data_loader.container.query_items(
        query="""
        SELECT c.id, c.title, c.unique_filename, c.transcription_id
        FROM c
        WHERE c.transcription_status = 'completed'
        AND c.user_id = @user_id
        AND c.transcription_id != null
        """,
        parameters=[{'name': '@user_id', 'value': user_id}],
        enable_cross_partition_query=True
    ))

    # Batch fetch all transcriptions with speaker_mapping
    trans_ids = [r['transcription_id'] for r in all_recordings if r.get('transcription_id')]
    transcriptions_map = {}
    for i in range(0, len(trans_ids), 100):
        chunk = trans_ids[i:i+100]
        id_params = [{'name': f'@id{j}', 'value': tid} for j, tid in enumerate(chunk)]
        id_placeholders = ', '.join(f'@id{j}' for j in range(len(chunk)))
        trans_results = list(data_loader.container.query_items(
            query=f"SELECT c.id, c.speaker_mapping FROM c WHERE c.id IN ({id_placeholders})",
            parameters=id_params,
            enable_cross_partition_query=True
        ))
        for t in trans_results:
            transcriptions_map[t['id']] = t.get('speaker_mapping') or {}

    # Build recording->speaker_label mapping for each participant
    # Key: (recording_id, participant_id) -> speaker_label
    recording_speaker_map = {}
    for rec in all_recordings:
        trans_id = rec.get('transcription_id')
        if not trans_id or trans_id not in transcriptions_map:
            continue
        speaker_mapping = transcriptions_map[trans_id]
        for speaker_label, mapping in speaker_mapping.items():
            if isinstance(mapping, dict) and mapping.get('participantId'):
                key = (rec['id'], mapping['participantId'])
                recording_speaker_map[key] = speaker_label

    print(f"  Found {len(recording_speaker_map)} speaker mappings across {len(all_recordings)} recordings")

    for pid, display_name in participant_ids.items():
        print(f"\nBuilding profile for: {display_name}")

        # Find recordings where this participant appears (using transcription.speaker_mapping)
        participant_recordings = []
        for rec in all_recordings:
            key = (rec['id'], pid)
            if key in recording_speaker_map:
                rec['_speaker_label'] = recording_speaker_map[key]  # Store for later use
                participant_recordings.append(rec)

        # Exclude specified recordings
        if config.exclude_recording_ids:
            participant_recordings = [
                r for r in participant_recordings
                if r['id'] not in config.exclude_recording_ids
            ]

        # Apply limit (random sample for variety)
        available_recs = len(participant_recordings)
        if config.max_recordings_per_participant and available_recs > config.max_recordings_per_participant:
            participant_recordings = random.sample(participant_recordings, config.max_recordings_per_participant)
            print(f"  Found {available_recs} recordings, randomly sampling {len(participant_recordings)}")
        else:
            print(f"  Found {available_recs} recordings")

        total_recs = len(participant_recordings)
        embeddings_collected = 0

        for rec_idx, rec in enumerate(participant_recordings, 1):
            rec_title = rec.get('title', rec.get('id', 'unknown'))[:40]
            print(f"    [{rec_idx}/{total_recs}] {rec_title}...", end=" ", flush=True)
            # Get speaker label for this participant (stored earlier)
            speaker_label = rec.get('_speaker_label')

            if not speaker_label:
                print("no speaker label")
                continue

            # Get transcription for timing
            trans_id = rec.get('transcription_id')
            if not trans_id:
                print("no transcription")
                continue

            trans_results = list(data_loader.container.query_items(
                query="SELECT c.transcript_json FROM c WHERE c.id = @id",
                parameters=[{'name': '@id', 'value': trans_id}],
                enable_cross_partition_query=True
            ))

            if not trans_results or not trans_results[0].get('transcript_json'):
                print("no transcript JSON")
                continue

            segments = _parse_azure_transcript_json(trans_results[0]['transcript_json'])

            # Filter to this speaker's segments
            speaker_segments = [s for s in segments if s.speaker_label == speaker_label]
            if not speaker_segments:
                print("no segments for speaker")
                continue

            # Calculate speaking time for this speaker
            total_speaking_time = sum(s.end_s - s.start_s for s in speaker_segments)
            num_segments = len(speaker_segments)
            print(f"({num_segments} segs, {total_speaking_time:.1f}s) ", end="", flush=True)

            # Download audio
            unique_filename = rec.get('unique_filename')
            if not unique_filename:
                print("no filename")
                continue

            audio_path = os.path.join(config.audio_cache_dir, unique_filename)
            # Check if file exists AND has content (not an empty failed download)
            need_download = not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0
            if need_download:
                if os.path.exists(audio_path):
                    os.remove(audio_path)  # Remove empty file
                print("downloading...", end=" ", flush=True)
                if not data_loader.download_audio_with_fallback(
                    unique_filename, config.user_id, audio_path
                ):
                    print("FAILED")
                    continue

            # Extract embeddings - use heuristics for speed
            # 1. Merge adjacent segments into stretches
            # 2. Pick the longest stretches (limit per recording)
            # 3. Apply buffer to avoid speaker transitions
            MAX_EMBEDDINGS_PER_RECORDING = 5
            BUFFER_SECONDS = 3.0
            MIN_SEGMENT_AFTER_BUFFER = 3.0  # Need at least 3s after buffer applied

            segment_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in speaker_segments]
            merged = merge_adjacent_segments(segment_tuples, max_gap_s=0.5)  # More aggressive merging

            # Sort by duration (longest first) and take top N
            merged_with_duration = [(s, e, lbl, e - s) for s, e, lbl in merged]
            merged_with_duration.sort(key=lambda x: x[3], reverse=True)
            top_segments = merged_with_duration[:MAX_EMBEDDINGS_PER_RECORDING]

            # Apply buffer and filter segments that are still long enough
            time_ranges = []
            for start, end, _, duration in top_segments:
                buffered_start = start + BUFFER_SECONDS
                buffered_end = end - BUFFER_SECONDS
                if buffered_end - buffered_start >= MIN_SEGMENT_AFTER_BUFFER:
                    time_ranges.append((buffered_start, buffered_end))

            if not time_ranges:
                print(f"no usable segments after buffer")
                continue

            # Batch extract all embeddings at once (loads audio only once)
            print(f"extracting from {len(time_ranges)} segments...", end=" ", flush=True)
            all_embeddings = embedder.embeddings_for_segments(audio_path, time_ranges)

            # Show results for each segment
            valid_embeddings = []
            print()  # newline after "extracting..."
            for i, ((seg_start, seg_end), emb) in enumerate(zip(time_ranges, all_embeddings), 1):
                seg_duration = seg_end - seg_start
                # Format time as MM:SS
                start_min, start_sec = divmod(int(seg_start), 60)
                end_min, end_sec = divmod(int(seg_end), 60)
                if emb is not None:
                    valid_embeddings.append(emb)
                    status = "✓"
                else:
                    status = "✗"
                print(f"      seg {i}: {start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d} ({seg_duration:.1f}s) {status}")

            if valid_embeddings:
                profile = profile_db.get_or_create(pid, display_name)
                profile.update(valid_embeddings, recording_id=rec['id'])
                embeddings_collected += len(valid_embeddings)
                print(f"    -> {len(valid_embeddings)} embeddings collected")
            else:
                print(f"    -> no valid embeddings")

        print(f"  Total: {embeddings_collected} embeddings")

        profile = profile_db.get(pid)
        if profile and profile.n_samples > 0:
            print(f"  Profile: {profile.n_samples} samples, std={profile.embedding_std:.4f}" if profile.embedding_std else f"  Profile: {profile.n_samples} samples")

    return profile_db


def validate_recordings(
    data_loader: DataLoader,
    embedder: EcapaEmbedder,
    profile_db: SpeakerProfileDB,
    user_id: str,
    validation_recordings: List[Dict],
    config: ExperimentConfig
) -> List[Dict]:
    """
    Run identification on validation recordings.
    """
    print("\n" + "=" * 60)
    print("PHASE 2: Validating on Recordings")
    print("=" * 60)

    results = []

    for rec in validation_recordings:
        print(f"\nValidating: {rec.get('title', rec['id'])[:50]}")

        # Get transcription for timing and ground truth
        trans_id = rec.get('transcription_id')
        if not trans_id:
            print("  No transcription ID, skipping")
            continue

        trans_results = list(data_loader.container.query_items(
            query="SELECT c.transcript_json, c.speaker_mapping FROM c WHERE c.id = @id",
            parameters=[{'name': '@id', 'value': trans_id}],
            enable_cross_partition_query=True
        ))

        if not trans_results or not trans_results[0].get('transcript_json'):
            print("  No transcript_json, skipping")
            continue

        trans_data = trans_results[0]

        # Get ground truth from transcription's speaker_mapping (canonical source)
        ground_truth = {}  # speaker_label -> participant info
        speaker_mapping = trans_data.get('speaker_mapping', {})

        if speaker_mapping:
            # Also need participant display names
            all_participants = {p.id: p for p in data_loader.get_all_participants(config.user_id)}
            for label, mapping in speaker_mapping.items():
                if not isinstance(mapping, dict):
                    continue
                pid = mapping.get('participantId')
                if not pid:
                    continue
                participant = all_participants.get(pid)
                if not participant:
                    print(f"    WARNING: speaker_mapping references participant {pid} but profile not found")
                ground_truth[label] = {
                    'participantId': pid,
                    'displayName': participant.displayName if participant else 'Unknown',
                }

        segments = _parse_azure_transcript_json(trans_data['transcript_json'])

        if ground_truth:
            print(f"  Ground truth: {len(ground_truth)} labeled speakers")
        else:
            print("  No ground truth labels found")

        # Download audio
        unique_filename = rec.get('unique_filename')
        if not unique_filename:
            print("  No unique_filename, skipping")
            continue

        audio_path = os.path.join(config.audio_cache_dir, unique_filename)
        # Check if file exists AND has content (not an empty failed download)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            if os.path.exists(audio_path):
                os.remove(audio_path)  # Remove empty file
            if not data_loader.download_audio_with_fallback(
                unique_filename, config.user_id, audio_path
            ):
                continue

        # Group segments by speaker
        speaker_labels = list(set(s.speaker_label for s in segments))
        total_speakers = len(speaker_labels)
        print(f"  Found {total_speakers} speakers in recording")

        recording_result = {
            'recording_id': rec['id'],
            'title': rec.get('title', ''),
            'speakers': []
        }

        for spk_idx, speaker_label in enumerate(speaker_labels, 1):
            speaker_segments = [s for s in segments if s.speaker_label == speaker_label]
            total_speaking_time = sum(s.end_s - s.start_s for s in speaker_segments)

            # Merge and extract embeddings - use same heuristics as profile building
            MAX_SEGMENTS_FOR_VALIDATION = 15
            BUFFER_SECONDS = 3.0
            MIN_SEGMENT_AFTER_BUFFER = 3.0

            t_start = time.time()
            segment_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in speaker_segments]
            merged = merge_adjacent_segments(segment_tuples, max_gap_s=0.5)  # More aggressive merging

            # Sort by duration and take top N longest segments
            merged_with_duration = [(s, e, lbl, e - s) for s, e, lbl in merged]
            merged_with_duration.sort(key=lambda x: x[3], reverse=True)
            top_segments = merged_with_duration[:MAX_SEGMENTS_FOR_VALIDATION]

            # Apply buffer and filter
            time_ranges = []
            for start, end, _, duration in top_segments:
                buffered_start = start + BUFFER_SECONDS
                buffered_end = end - BUFFER_SECONDS
                if buffered_end - buffered_start >= MIN_SEGMENT_AFTER_BUFFER:
                    time_ranges.append((buffered_start, buffered_end))
            t_segment_prep = time.time() - t_start

            print(f"  [{spk_idx}/{total_speakers}] {speaker_label} ({len(speaker_segments)} segs, {total_speaking_time:.1f}s)")
            print(f"      segment prep: {t_segment_prep*1000:.1f}ms, extracting {len(time_ranges)} embeddings...", end=" ", flush=True)

            # Extract embeddings (single batch now that we've limited segments)
            t_start = time.time()
            all_embeddings = embedder.embeddings_for_segments(audio_path, time_ranges)
            valid_embeddings = [e for e in all_embeddings if e is not None]
            t_embedding = time.time() - t_start

            print(f"{len(valid_embeddings)} ok ({t_embedding:.2f}s)", end="")

            if not valid_embeddings:
                print(" - skipping (no valid embeddings)")
                continue

            # Compute speaker centroid
            t_start = time.time()
            emb_stack = np.stack([l2_normalize(e) for e in valid_embeddings], axis=0)
            speaker_centroid = l2_normalize(emb_stack.mean(axis=0))

            # Match against profiles
            match = profile_db.match_with_confidence(
                speaker_centroid,
                high_threshold=config.high_threshold,
                low_threshold=config.low_threshold
            )
            t_matching = time.time() - t_start

            print(f", matching: {t_matching*1000:.1f}ms")

            # Check ground truth
            gt = ground_truth.get(speaker_label, {})
            actual_pid = gt.get('participantId')
            actual_name = gt.get('displayName')
            predicted_pid = match['participant_id']
            predicted_name = match['display_name']

            is_correct = (predicted_pid == actual_pid) if actual_pid and predicted_pid else None

            speaker_result = {
                'speaker_label': speaker_label,
                'actual_participant': actual_name,
                'actual_participant_id': actual_pid,
                'predicted_participant': predicted_name,
                'predicted_participant_id': predicted_pid,
                'similarity': match['similarity'],
                'status': match['status'],
                'correct': is_correct,
            }

            recording_result['speakers'].append(speaker_result)

            # Print result
            status_icon = "✓" if is_correct else "✗" if is_correct is False else "?"
            sim_str = f"{match['similarity']:.3f}" if match['similarity'] else "N/A"
            if is_correct:
                print(f"      -> {status_icon} predicted={predicted_name} (sim={sim_str}, {match['status']})")
            elif is_correct is False:
                # Show IDs if names are the same but IDs differ (duplicate names)
                if predicted_name == actual_name:
                    pred_id_short = predicted_pid[:8] if predicted_pid else "None"
                    actual_id_short = actual_pid[:8] if actual_pid else "None"
                    print(f"      -> {status_icon} predicted={predicted_name} ({pred_id_short}...), actual={actual_name} ({actual_id_short}...) - DUPLICATE NAMES! (sim={sim_str})")
                else:
                    print(f"      -> {status_icon} predicted={predicted_name}, actual={actual_name} (sim={sim_str}, {match['status']})")
            else:
                # No ground truth
                print(f"      -> {status_icon} predicted={predicted_name} (sim={sim_str}, {match['status']}) [no ground truth]")

        results.append(recording_result)

    return results


def print_summary(results: List[Dict], profile_db: SpeakerProfileDB):
    """Print experiment summary."""
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)

    print(f"\nProfiles built: {len(profile_db.profiles)}")
    for pid, profile in profile_db.profiles.items():
        print(f"  {profile.display_name}: {profile.n_samples} samples from {len(profile.recording_ids)} recordings")

    print(f"\nRecordings validated: {len(results)}")

    total_speakers = 0
    correct = 0
    incorrect = 0
    unknown = 0

    for r in results:
        for s in r['speakers']:
            total_speakers += 1
            if s['correct'] is True:
                correct += 1
            elif s['correct'] is False:
                incorrect += 1
            else:
                unknown += 1

    print(f"\nTotal speakers evaluated: {total_speakers}")
    if total_speakers > 0:
        print(f"  Correct: {correct} ({100*correct/total_speakers:.1f}%)")
        print(f"  Incorrect: {incorrect} ({100*incorrect/total_speakers:.1f}%)")
        print(f"  Unknown/No ground truth: {unknown}")


def main():
    parser = argparse.ArgumentParser(
        description="Config-based Speaker Identification Experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("-c", "--config", required=True, help="Path to YAML config file")
    parser.add_argument("--user-id", help="User ID (overrides config file)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without running")
    parser.add_argument("--load-profiles", action="store_true",
                        help="Load existing profiles instead of building new ones")

    args = parser.parse_args()

    print("=" * 60)
    print("CONFIG-BASED SPEAKER IDENTIFICATION EXPERIMENT")
    print("=" * 60)
    print(f"Config: {args.config}")

    # Load config (with optional user_id override from command line)
    config = load_config(args.config, args.user_id)

    print(f"User ID: {config.user_id}")
    print(f"Started: {datetime.now().isoformat()}")

    print(f"\nLearn participants: {config.learn_participant_names + config.learn_participant_ids}")
    print(f"Validate recordings: {config.validate_recording_titles + config.validate_recording_ids}")
    print(f"Thresholds: high={config.high_threshold}, low={config.low_threshold}")

    # Initialize components
    print("\nInitializing...")
    data_loader = DataLoader()

    # Resolve participant names to IDs
    participant_ids = find_participant_ids(
        data_loader, config.user_id,
        config.learn_participant_names,
        config.learn_participant_ids
    )

    print(f"\nResolved participants:")
    for pid, name in participant_ids.items():
        print(f"  {name}: {pid}")

    # Find validation recordings
    validation_recordings = find_validation_recordings(data_loader, config.user_id, config)

    print(f"\nValidation recordings:")
    for r in validation_recordings:
        print(f"  {r.get('title', r['id'])[:60]}")

    if args.dry_run:
        print("\n[DRY RUN] Would proceed with experiment. Exiting.")
        return

    # Initialize embedder
    embedder = EcapaEmbedder()

    # Build or load profiles
    if args.load_profiles and os.path.exists(config.profiles_file):
        print(f"\nLoading existing profiles from {config.profiles_file}")
        profile_db = SpeakerProfileDB.load_from_file(config.profiles_file)
        print(f"Loaded {len(profile_db.profiles)} profiles")
        for pid, profile in profile_db.profiles.items():
            print(f"  {profile.display_name}: {profile.n_samples} samples")
    else:
        if args.load_profiles:
            print(f"\nWarning: {config.profiles_file} not found, building new profiles")
        profile_db = build_profiles_for_participants(
            data_loader, embedder, config.user_id,
            participant_ids, config
        )
        # Save profiles
        profile_db.save_to_file(config.profiles_file)
        print(f"\nProfiles saved to {config.profiles_file}")

    # Validate
    results = validate_recordings(
        data_loader, embedder, profile_db,
        config.user_id, validation_recordings, config
    )

    # Save results
    with open(config.results_file, 'w') as f:
        json.dump({
            'config': args.config,
            'user_id': config.user_id,
            'timestamp': datetime.now().isoformat(),
            'profiles': {pid: p.to_dict() for pid, p in profile_db.profiles.items()},
            'validation_results': results,
        }, f, indent=2, default=str)
    print(f"Results saved to {config.results_file}")

    # Print summary
    print_summary(results, profile_db)


if __name__ == "__main__":
    main()
