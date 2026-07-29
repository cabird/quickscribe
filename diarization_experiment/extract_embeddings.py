#!/usr/bin/env python3
"""
Speaker Embedding Extraction Script

Extracts ECAPA-TDNN speaker embeddings from all recordings in CosmosDB.
Stores embeddings in a format optimized for sensitivity analysis and
cross-recording speaker identification experiments.

Usage:
    # Full extraction
    python extract_embeddings.py --user-id USER_ID

    # Test on small sample
    python extract_embeddings.py --user-id USER_ID --max-recordings 10

    # Resume interrupted extraction
    python extract_embeddings.py --user-id USER_ID --resume

    # Dry run (show what would be extracted)
    python extract_embeddings.py --user-id USER_ID --dry-run

Output:
    embeddings/
    ├── metadata.json      # Recording info, speaker stats, labels
    ├── embeddings.npz     # All embedding vectors (compressed)
    └── extraction.log     # Detailed log with errors
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict

import numpy as np

# Add parent directory for shared_quickscribe_py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from data_loader import DataLoader, SpeakerSegment, _parse_azure_transcript_json
from speaker_embedder import EcapaEmbedder, merge_adjacent_segments


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ExtractionConfig:
    """Configuration for embedding extraction."""
    min_speaker_duration_s: float = 30.0      # Skip speakers with less total audio
    max_embeddings_per_speaker: int = 10      # Max embeddings to extract per speaker
    min_segment_duration_s: float = 4.0       # Min segment duration after buffer
    segment_buffer_s: float = 2.0             # Trim from segment edges
    segment_merge_gap_s: float = 0.5          # Merge segments with small gaps
    max_audio_offset_s: float = 5400.0        # Ignore segments past this offset (90 min default)

    output_dir: str = "embeddings"
    audio_cache_dir: str = "audio_cache"
    exclude_recordings: List[str] = field(default_factory=list)  # Recording IDs to skip

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SpeakerData:
    """Extracted data for a single speaker in a recording."""
    speaker_label: str
    participant_id: Optional[str]
    participant_name: Optional[str]
    manually_verified: bool
    total_duration_s: float
    n_segments: int
    n_embeddings: int
    embedding_key: str
    embedding_segments: List[Dict[str, float]]  # [{start_s, end_s, duration_s}, ...]


@dataclass
class RecordingData:
    """Extracted data for a recording."""
    recording_id: str
    title: str
    duration_s: Optional[float]
    recorded_at: Optional[str]
    speakers: Dict[str, SpeakerData]


@dataclass
class ExtractionResult:
    """Result of the full extraction process."""
    version: str = "1.0"
    extracted_at: str = ""
    user_id: str = ""
    config: Dict = field(default_factory=dict)
    summary: Dict = field(default_factory=dict)
    recordings: Dict[str, Dict] = field(default_factory=dict)
    participants: Dict[str, Dict] = field(default_factory=dict)
    errors: List[Dict] = field(default_factory=list)


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(output_dir: str) -> logging.Logger:
    """Setup logging to both file and console."""
    os.makedirs(output_dir, exist_ok=True)

    log_path = os.path.join(output_dir, "extraction.log")

    # Create logger
    logger = logging.getLogger("extraction")
    logger.setLevel(logging.DEBUG)

    # File handler (detailed)
    fh = logging.FileHandler(log_path, mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # Console handler (info only)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# =============================================================================
# Core Extraction Functions
# =============================================================================

def get_all_recordings(data_loader: DataLoader, user_id: str) -> List[Dict]:
    """
    Get all completed recordings for a user.

    Returns list of recording dicts with transcription info.
    """
    print("Querying all completed recordings...")

    recordings = list(data_loader.container.query_items(
        query="""
        SELECT c.id, c.user_id, c.title, c.original_filename, c.unique_filename,
               c.duration, c.transcription_id, c.transcription_status,
               c.upload_timestamp, c.recorded_timestamp
        FROM c
        WHERE c.transcription_status = 'completed'
        AND c.user_id = @user_id
        AND c.type = 'recording'
        """,
        parameters=[{'name': '@user_id', 'value': user_id}],
        enable_cross_partition_query=True
    ))

    print(f"  Found {len(recordings)} completed recordings")
    return recordings


def get_transcript_segments(data_loader: DataLoader, transcription_id: str) -> List[SpeakerSegment]:
    """Get parsed segments from a transcription."""
    results = list(data_loader.container.query_items(
        query="SELECT c.transcript_json FROM c WHERE c.id = @id",
        parameters=[{'name': '@id', 'value': transcription_id}],
        enable_cross_partition_query=True
    ))

    if not results or not results[0].get('transcript_json'):
        return []

    return _parse_azure_transcript_json(results[0]['transcript_json'])


def get_speaker_labels(data_loader: DataLoader, transcription_id: str, participant_cache: Dict[str, str]) -> Dict[str, Dict]:
    """
    Get speaker labels from transcription's speaker_mapping, looking up participant names by ID.

    Args:
        data_loader: DataLoader instance
        transcription_id: ID of the transcription
        participant_cache: Dict mapping participant_id -> display_name (updated in place)

    Returns dict: speaker_label -> {participant_id, participant_name, manually_verified}
    """
    # Get speaker_mapping from transcription
    results = list(data_loader.container.query_items(
        query="SELECT c.speaker_mapping FROM c WHERE c.id = @id",
        parameters=[{'name': '@id', 'value': transcription_id}],
        enable_cross_partition_query=True
    ))

    if not results or not results[0].get('speaker_mapping'):
        return {}

    speaker_mapping = results[0]['speaker_mapping']
    labels = {}

    # Collect participant IDs we need to look up
    ids_to_lookup = []
    for speaker_label, mapping in speaker_mapping.items():
        participant_id = mapping.get('participantId')
        if participant_id and participant_id not in participant_cache:
            ids_to_lookup.append(participant_id)

    # Batch lookup participant names
    if ids_to_lookup:
        # Query participants by ID
        id_list = ', '.join(f'"{pid}"' for pid in ids_to_lookup)
        query = f"SELECT c.id, c.displayName FROM c WHERE c.type = 'participant' AND c.id IN ({id_list})"
        participants = list(data_loader.container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        for p in participants:
            participant_cache[p['id']] = p.get('displayName', '')

    # Build labels dict
    for speaker_label, mapping in speaker_mapping.items():
        participant_id = mapping.get('participantId')
        labels[speaker_label] = {
            'participant_id': participant_id,
            'participant_name': participant_cache.get(participant_id) if participant_id else None,
            'manually_verified': mapping.get('manuallyVerified', False),
        }

    return labels


def prepare_segments_for_extraction(
    segments: List[SpeakerSegment],
    speaker_label: str,
    config: ExtractionConfig
) -> Tuple[float, int, List[Tuple[float, float]]]:
    """
    Prepare segments for a speaker: merge, filter, buffer, select best.

    Returns:
        (total_duration_s, n_segments, selected_time_ranges)
    """
    # Filter to this speaker
    speaker_segs = [s for s in segments if s.speaker_label == speaker_label]

    # Filter out segments past max_audio_offset (90 min default)
    # This avoids timing issues from chunked transcription of long recordings
    if config.max_audio_offset_s > 0:
        speaker_segs = [s for s in speaker_segs if s.start_s < config.max_audio_offset_s]

    n_segments = len(speaker_segs)

    if not speaker_segs:
        return 0.0, 0, []

    # Calculate total duration
    total_duration = sum(s.end_s - s.start_s for s in speaker_segs)

    # Skip if not enough audio
    if total_duration < config.min_speaker_duration_s:
        return total_duration, n_segments, []

    # Convert to tuples for merging
    seg_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in speaker_segs]

    # Merge adjacent segments
    merged = merge_adjacent_segments(seg_tuples, max_gap_s=config.segment_merge_gap_s)

    # Sort by duration (longest first)
    merged_with_dur = [(s, e, lbl, e - s) for s, e, lbl in merged]
    merged_with_dur.sort(key=lambda x: x[3], reverse=True)

    # Take top candidates (more than we need, some may fail)
    top_segments = merged_with_dur[:config.max_embeddings_per_speaker * 2]

    # Apply buffer and filter
    time_ranges = []
    for start, end, _, dur in top_segments:
        buffered_start = start + config.segment_buffer_s
        buffered_end = end - config.segment_buffer_s
        buffered_dur = buffered_end - buffered_start

        if buffered_dur >= config.min_segment_duration_s:
            time_ranges.append((buffered_start, buffered_end))

        if len(time_ranges) >= config.max_embeddings_per_speaker:
            break

    return total_duration, n_segments, time_ranges


def extract_recording(
    recording: Dict,
    data_loader: DataLoader,
    embedder: EcapaEmbedder,
    config: ExtractionConfig,
    logger: logging.Logger,
    participant_cache: Dict[str, str] = None,
    existing_speaker_keys: set = None,
    existing_recording_data: Dict = None
) -> Tuple[Optional[Dict], Dict[str, np.ndarray], Optional[Dict]]:
    """
    Extract embeddings from a single recording.

    Args:
        participant_cache: Shared cache mapping participant_id -> display_name (optional)
        existing_speaker_keys: Set of "rec_id::speaker_label" keys that already have embeddings
        existing_recording_data: Existing metadata for this recording (for incremental updates)

    Returns:
        (recording_metadata, embeddings_dict, error_info)
    """
    if participant_cache is None:
        participant_cache = {}
    if existing_speaker_keys is None:
        existing_speaker_keys = set()

    rec_id = recording['id']
    title = recording.get('title', recording.get('original_filename', rec_id))[:60]

    # Get transcription segments
    trans_id = recording.get('transcription_id')
    if not trans_id:
        return None, {}, {'recording_id': rec_id, 'error': 'No transcription_id'}

    segments = get_transcript_segments(data_loader, trans_id)
    if not segments:
        return None, {}, {'recording_id': rec_id, 'error': 'No transcript segments'}

    # Get speaker labels from transcription's speaker_mapping
    speaker_labels = get_speaker_labels(data_loader, trans_id, participant_cache)

    # Get unique speaker labels from segments
    unique_speakers = list(set(s.speaker_label for s in segments))

    # Download audio
    unique_filename = recording.get('unique_filename')
    if not unique_filename:
        return None, {}, {'recording_id': rec_id, 'error': 'No unique_filename'}

    audio_path = os.path.join(config.audio_cache_dir, unique_filename)

    # Check cache
    need_download = not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0
    if need_download:
        if os.path.exists(audio_path):
            os.remove(audio_path)

        logger.info(f"    Downloading audio...")
        if not data_loader.download_audio_with_fallback(
            unique_filename, recording.get('user_id', ''), audio_path
        ):
            return None, {}, {'recording_id': rec_id, 'error': 'Audio download failed'}

    # Process each speaker
    # Start with existing data if provided (for incremental updates)
    if existing_recording_data:
        recording_data = existing_recording_data.copy()
        recording_data['speakers'] = dict(existing_recording_data.get('speakers', {}))
    else:
        recording_data = {
            'recording_id': rec_id,
            'title': recording.get('title', ''),
            'duration_s': recording.get('duration'),
            'recorded_at': recording.get('recorded_timestamp'),
            'speakers': {}
        }

    embeddings_dict = {}
    speakers_extracted = 0
    speakers_skipped = 0
    total_embeddings = 0

    for speaker_label in unique_speakers:
        # Check if this speaker already has embeddings (incremental mode)
        embedding_key = f"{rec_id}::{speaker_label}"
        if embedding_key in existing_speaker_keys:
            # Even when skipping, refresh speaker labels from database
            # This ensures metadata stays current after validations are applied
            label_info = speaker_labels.get(speaker_label, {})
            if speaker_label in recording_data['speakers']:
                recording_data['speakers'][speaker_label]['participant_id'] = label_info.get('participant_id')
                recording_data['speakers'][speaker_label]['participant_name'] = label_info.get('participant_name')
                recording_data['speakers'][speaker_label]['manually_verified'] = label_info.get('manually_verified', False)
            logger.debug(f"    {speaker_label}: skipped (already has embeddings)")
            speakers_skipped += 1
            continue

        total_dur, n_segs, time_ranges = prepare_segments_for_extraction(
            segments, speaker_label, config
        )

        # Skip speakers with insufficient audio
        if not time_ranges:
            if total_dur > 0:
                logger.debug(f"    {speaker_label}: {total_dur:.1f}s total, skipped (< {config.min_speaker_duration_s}s)")
            continue

        # Extract embeddings
        try:
            all_embeddings = embedder.embeddings_for_segments(audio_path, time_ranges)
            valid_embeddings = [e for e in all_embeddings if e is not None]
        except Exception as e:
            logger.warning(f"    {speaker_label}: embedding extraction failed: {e}")
            continue

        if not valid_embeddings:
            logger.debug(f"    {speaker_label}: no valid embeddings extracted")
            continue

        # Build embedding key
        embedding_key = f"{rec_id}::{speaker_label}"

        # Get label info
        label_info = speaker_labels.get(speaker_label, {})

        # Build segment metadata
        embedding_segments = [
            {'start_s': s, 'end_s': e, 'duration_s': e - s}
            for (s, e), emb in zip(time_ranges, all_embeddings)
            if emb is not None
        ]

        # Store speaker data
        recording_data['speakers'][speaker_label] = {
            'participant_id': label_info.get('participant_id'),
            'participant_name': label_info.get('participant_name'),
            'manually_verified': label_info.get('manually_verified', False),
            'total_duration_s': total_dur,
            'n_segments': n_segs,
            'n_embeddings': len(valid_embeddings),
            'embedding_key': embedding_key,
            'embedding_segments': embedding_segments,
        }

        # Store embeddings
        embeddings_dict[embedding_key] = np.stack(valid_embeddings, axis=0)

        speakers_extracted += 1
        total_embeddings += len(valid_embeddings)

        # Log progress
        label_str = f" [{label_info.get('participant_name', '')}]" if label_info.get('participant_name') else ""
        logger.info(f"    {speaker_label}{label_str}: {len(valid_embeddings)} embeddings ({total_dur:.0f}s audio)")

    if speakers_extracted == 0 and speakers_skipped == 0:
        return None, {}, {'recording_id': rec_id, 'error': 'No speakers with sufficient audio'}

    # If we only skipped speakers (all already extracted), still return recording data
    # but with empty new embeddings
    if speakers_extracted == 0 and speakers_skipped > 0:
        logger.info(f"    All {speakers_skipped} speakers already have embeddings")
        return recording_data, {}, None

    return recording_data, embeddings_dict, None


def load_existing_progress(output_dir: str) -> Tuple[Dict, Dict[str, np.ndarray], set, set]:
    """
    Load existing extraction progress for resume capability.

    Returns:
        (existing_metadata, existing_embeddings, completed_recording_ids, completed_speaker_keys)

    The completed_speaker_keys is a set of "recording_id::speaker_label" strings
    that already have embeddings, enabling incremental extraction of new speakers
    in previously-processed recordings.
    """
    metadata_path = os.path.join(output_dir, 'metadata.json')
    embeddings_path = os.path.join(output_dir, 'embeddings.npz')

    existing_metadata = {}
    existing_embeddings = {}
    completed_ids = set()
    completed_speaker_keys = set()

    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                existing_metadata = json.load(f)
            completed_ids = set(existing_metadata.get('recordings', {}).keys())
            print(f"  Found existing progress: {len(completed_ids)} recordings already extracted")
        except Exception as e:
            print(f"  Warning: Could not load existing metadata: {e}")

    if os.path.exists(embeddings_path):
        try:
            data = np.load(embeddings_path)
            existing_embeddings = {k: data[k] for k in data.files}
            # Build set of speaker keys that already have embeddings
            completed_speaker_keys = set(existing_embeddings.keys())
            print(f"  Loaded {len(existing_embeddings)} existing embedding arrays")
            print(f"  Found {len(completed_speaker_keys)} existing speaker keys")
        except Exception as e:
            print(f"  Warning: Could not load existing embeddings: {e}")

    return existing_metadata, existing_embeddings, completed_ids, completed_speaker_keys


def save_results(
    result: ExtractionResult,
    embeddings: Dict[str, np.ndarray],
    output_dir: str,
    logger: logging.Logger
):
    """Save extraction results to disk."""
    os.makedirs(output_dir, exist_ok=True)

    # Save metadata
    metadata_path = os.path.join(output_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump({
            'version': result.version,
            'extracted_at': result.extracted_at,
            'user_id': result.user_id,
            'extraction_params': result.config,
            'summary': result.summary,
            'recordings': result.recordings,
            'participants': result.participants,
            'errors': result.errors,
        }, f, indent=2, default=str)

    logger.info(f"Saved metadata to {metadata_path}")

    # Save embeddings
    embeddings_path = os.path.join(output_dir, 'embeddings.npz')
    np.savez_compressed(embeddings_path, **embeddings)

    # Calculate file size
    size_mb = os.path.getsize(embeddings_path) / (1024 * 1024)
    logger.info(f"Saved embeddings to {embeddings_path} ({size_mb:.1f} MB)")


def build_participant_index(recordings: Dict[str, Dict]) -> Dict[str, Dict]:
    """Build index of participants and their appearances."""
    participants = {}

    for rec_id, rec_data in recordings.items():
        for speaker_label, speaker_data in rec_data.get('speakers', {}).items():
            pid = speaker_data.get('participant_id')
            if not pid:
                continue

            if pid not in participants:
                participants[pid] = {
                    'display_name': speaker_data.get('participant_name', 'Unknown'),
                    'appearances': [],
                    'total_recordings': 0,
                    'total_embeddings': 0,
                }

            participants[pid]['appearances'].append({
                'recording_id': rec_id,
                'speaker_label': speaker_label,
            })
            participants[pid]['total_recordings'] += 1
            participants[pid]['total_embeddings'] += speaker_data.get('n_embeddings', 0)

    return participants


# =============================================================================
# Main Extraction Function
# =============================================================================

def run_extraction(
    user_id: str,
    config: ExtractionConfig,
    max_recordings: Optional[int] = None,
    resume: bool = False,
    dry_run: bool = False,
):
    """Run the full extraction process."""

    # Setup logging
    logger = setup_logging(config.output_dir)
    logger.info("=" * 70)
    logger.info("SPEAKER EMBEDDING EXTRACTION")
    logger.info("=" * 70)
    logger.info(f"User ID: {user_id}")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info(f"Output directory: {config.output_dir}")
    logger.info(f"Config: {config.to_dict()}")

    # Initialize data loader
    logger.info("\nInitializing data loader...")
    data_loader = DataLoader()

    # Get all recordings
    all_recordings = get_all_recordings(data_loader, user_id)

    if max_recordings:
        all_recordings = all_recordings[:max_recordings]
        logger.info(f"Limited to {max_recordings} recordings for testing")

    # Check for existing progress
    existing_metadata = {}
    existing_embeddings = {}
    completed_ids = set()
    completed_speaker_keys = set()

    if resume:
        logger.info("\nChecking for existing progress...")
        existing_metadata, existing_embeddings, completed_ids, completed_speaker_keys = load_existing_progress(config.output_dir)

    # In incremental mode, process ALL recordings but skip individual speakers
    # that already have embeddings. This allows extracting new speakers in
    # previously-processed recordings.
    if resume and completed_speaker_keys:
        # Process all recordings, incremental extraction will skip existing speakers
        recordings_to_process = all_recordings
        logger.info(f"\nIncremental mode: will process all {len(recordings_to_process)} recordings")
        logger.info(f"  (Skipping {len(completed_speaker_keys)} speakers that already have embeddings)")
    else:
        # Non-incremental: skip entire recordings that have been processed
        recordings_to_process = [r for r in all_recordings if r['id'] not in completed_ids]
        logger.info(f"\nRecordings to process: {len(recordings_to_process)}")
        if completed_ids:
            logger.info(f"  (Skipping {len(completed_ids)} already completed)")

    if dry_run:
        logger.info("\n[DRY RUN] Would process the following recordings:")
        for i, rec in enumerate(recordings_to_process[:20], 1):
            title = rec.get('title', rec.get('original_filename', rec['id']))[:50]
            logger.info(f"  {i}. {title}")
        if len(recordings_to_process) > 20:
            logger.info(f"  ... and {len(recordings_to_process) - 20} more")
        return

    # Initialize embedder
    logger.info("\nInitializing ECAPA-TDNN embedder...")
    embedder = EcapaEmbedder()

    # Ensure cache directory exists
    os.makedirs(config.audio_cache_dir, exist_ok=True)

    # Initialize result containers
    all_recordings_data = dict(existing_metadata.get('recordings', {}))
    all_embeddings = dict(existing_embeddings)
    all_errors = list(existing_metadata.get('errors', []))

    # Process recordings
    logger.info("\n" + "=" * 70)
    logger.info("EXTRACTING EMBEDDINGS")
    logger.info("=" * 70)

    total_to_process = len(recordings_to_process)

    # Shared cache for participant lookups across all recordings
    participant_cache: Dict[str, str] = {}

    for idx, recording in enumerate(recordings_to_process, 1):
        rec_id = recording['id']
        title = recording.get('title', recording.get('original_filename', rec_id))[:50]

        # Skip excluded recordings
        if rec_id in config.exclude_recordings:
            logger.info(f"\n[{idx}/{total_to_process}] {title}")
            logger.info(f"  ID: {rec_id}")
            logger.info(f"  SKIPPED: In exclude list")
            all_errors.append({'recording_id': rec_id, 'error': 'Excluded by config'})
            continue

        logger.info(f"\n[{idx}/{total_to_process}] {title}")
        logger.info(f"  ID: {rec_id}")

        try:
            # Get existing data for this recording (for incremental updates)
            existing_rec_data = all_recordings_data.get(rec_id)

            rec_data, embeddings, error = extract_recording(
                recording, data_loader, embedder, config, logger, participant_cache,
                existing_speaker_keys=completed_speaker_keys,
                existing_recording_data=existing_rec_data
            )

            if error:
                logger.warning(f"  SKIPPED: {error.get('error', 'Unknown error')}")
                all_errors.append(error)
                continue

            if rec_data:
                all_recordings_data[rec_id] = rec_data
                all_embeddings.update(embeddings)

                n_speakers = len(rec_data.get('speakers', {}))
                n_new_emb = sum(len(e) if hasattr(e, '__len__') else 1 for e in embeddings.values())
                if n_new_emb > 0:
                    logger.info(f"  Extracted: {n_speakers} speakers total, {n_new_emb} new embeddings")
                else:
                    logger.info(f"  No new speakers to extract")

            # Save progress periodically (every 10 recordings)
            if idx % 10 == 0:
                logger.info(f"\n  [Saving intermediate progress...]")
                intermediate_result = ExtractionResult(
                    extracted_at=datetime.now().isoformat(),
                    user_id=user_id,
                    config=config.to_dict(),
                    recordings=all_recordings_data,
                    participants=build_participant_index(all_recordings_data),
                    errors=all_errors,
                )
                save_results(intermediate_result, all_embeddings, config.output_dir, logger)

        except Exception as e:
            logger.error(f"  ERROR: {e}")
            all_errors.append({
                'recording_id': rec_id,
                'error': str(e),
            })
            continue

    # Build final result
    logger.info("\n" + "=" * 70)
    logger.info("FINALIZING")
    logger.info("=" * 70)

    # Build participant index
    participants = build_participant_index(all_recordings_data)

    # Calculate summary statistics
    total_speakers = sum(len(r.get('speakers', {})) for r in all_recordings_data.values())
    labeled_speakers = sum(
        1 for r in all_recordings_data.values()
        for s in r.get('speakers', {}).values()
        if s.get('participant_id')
    )
    total_embeddings = sum(
        s.get('n_embeddings', 0)
        for r in all_recordings_data.values()
        for s in r.get('speakers', {}).values()
    )

    summary = {
        'total_recordings': len(all_recordings),
        'recordings_processed': len(all_recordings_data),
        'recordings_skipped': len(all_errors),
        'total_speakers_extracted': total_speakers,
        'labeled_speakers': labeled_speakers,
        'unlabeled_speakers': total_speakers - labeled_speakers,
        'unique_participants': len(participants),
        'total_embeddings': total_embeddings,
    }

    result = ExtractionResult(
        extracted_at=datetime.now().isoformat(),
        user_id=user_id,
        config=config.to_dict(),
        summary=summary,
        recordings=all_recordings_data,
        participants=participants,
        errors=all_errors,
    )

    # Save final results
    save_results(result, all_embeddings, config.output_dir, logger)

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("EXTRACTION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"\nSummary:")
    logger.info(f"  Total recordings: {summary['total_recordings']}")
    logger.info(f"  Recordings processed: {summary['recordings_processed']}")
    logger.info(f"  Recordings skipped: {summary['recordings_skipped']}")
    logger.info(f"  Total speakers: {summary['total_speakers_extracted']}")
    logger.info(f"    Labeled: {summary['labeled_speakers']}")
    logger.info(f"    Unlabeled: {summary['unlabeled_speakers']}")
    logger.info(f"  Unique participants: {summary['unique_participants']}")
    logger.info(f"  Total embeddings: {summary['total_embeddings']}")

    if participants:
        logger.info(f"\nTop participants by recordings:")
        sorted_parts = sorted(participants.items(), key=lambda x: x[1]['total_recordings'], reverse=True)
        for pid, pdata in sorted_parts[:10]:
            logger.info(f"  {pdata['display_name']}: {pdata['total_recordings']} recordings, {pdata['total_embeddings']} embeddings")

    if all_errors:
        logger.info(f"\nErrors ({len(all_errors)}):")
        for err in all_errors[:10]:
            logger.info(f"  {err.get('recording_id', 'unknown')[:8]}...: {err.get('error', 'Unknown')}")
        if len(all_errors) > 10:
            logger.info(f"  ... and {len(all_errors) - 10} more (see extraction.log)")

    logger.info(f"\nOutput files:")
    logger.info(f"  {os.path.join(config.output_dir, 'metadata.json')}")
    logger.info(f"  {os.path.join(config.output_dir, 'embeddings.npz')}")
    logger.info(f"  {os.path.join(config.output_dir, 'extraction.log')}")

    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract speaker embeddings from all recordings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--user-id",
        required=True,
        help="User ID to extract embeddings for"
    )

    parser.add_argument(
        "--output-dir",
        default="embeddings",
        help="Output directory for results (default: embeddings)"
    )

    parser.add_argument(
        "--audio-cache-dir",
        default="audio_cache",
        help="Directory for caching downloaded audio (default: audio_cache)"
    )

    parser.add_argument(
        "--max-recordings",
        type=int,
        default=None,
        help="Maximum number of recordings to process (for testing)"
    )

    parser.add_argument(
        "--min-speaker-duration",
        type=float,
        default=30.0,
        help="Minimum speaker duration in seconds (default: 30)"
    )

    parser.add_argument(
        "--max-embeddings",
        type=int,
        default=10,
        help="Maximum embeddings per speaker (default: 10)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous extraction (skip already-processed recordings)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without actually processing"
    )

    parser.add_argument(
        "--max-audio-offset",
        type=float,
        default=5400.0,
        help="Max audio offset in seconds (default: 5400 = 90 min). Segments past this are ignored."
    )

    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="Recording IDs to exclude (space-separated)"
    )

    parser.add_argument(
        "--exclude-file",
        type=str,
        default=None,
        help="File containing recording IDs to exclude (one per line)"
    )

    args = parser.parse_args()

    # Load exclude list from file if specified
    exclude_recordings = set(args.exclude)
    if args.exclude_file and os.path.exists(args.exclude_file):
        with open(args.exclude_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    exclude_recordings.add(line)

    # Build config
    config = ExtractionConfig(
        min_speaker_duration_s=args.min_speaker_duration,
        max_embeddings_per_speaker=args.max_embeddings,
        max_audio_offset_s=args.max_audio_offset,
        output_dir=args.output_dir,
        audio_cache_dir=args.audio_cache_dir,
        exclude_recordings=list(exclude_recordings),
    )

    # Run extraction
    run_extraction(
        user_id=args.user_id,
        config=config,
        max_recordings=args.max_recordings,
        resume=args.resume,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
