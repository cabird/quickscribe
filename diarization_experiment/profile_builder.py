"""
Speaker Profile Builder

Builds speaker voice profiles from labeled meetings by:
1. Fetching labeled meetings from QuickScribe database
2. Downloading audio files
3. Extracting ECAPA-TDNN embeddings for each speaker's segments
4. Building and storing speaker profiles

The resulting profiles can be used to automatically identify speakers
in unlabeled meetings.

Usage:
    builder = ProfileBuilder(user_id="...")
    builder.build_profiles()
    builder.save_profiles("speaker_profiles.json")
"""

from __future__ import annotations

import os
import json
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from speaker_embedder import (
    EcapaEmbedder, SpeakerProfileDB, SpeakerProfile,
    merge_adjacent_segments, l2_normalize
)
from data_loader import DataLoader, LabeledMeeting, SpeakerSegment


@dataclass
class BuildStats:
    """Statistics from profile building."""
    meetings_processed: int = 0
    participants_found: int = 0
    total_segments: int = 0
    segments_with_embeddings: int = 0
    total_audio_duration_s: float = 0.0

    def __str__(self) -> str:
        return (
            f"Meetings processed: {self.meetings_processed}\n"
            f"Unique participants: {self.participants_found}\n"
            f"Total segments: {self.total_segments}\n"
            f"Segments with valid embeddings: {self.segments_with_embeddings}\n"
            f"Total audio duration: {self.total_audio_duration_s / 60:.1f} minutes"
        )


class ProfileBuilder:
    """
    Builds speaker profiles from labeled meetings.

    The builder:
    1. Loads labeled meetings from CosmosDB
    2. Downloads audio files
    3. Extracts ECAPA embeddings for labeled speaker segments
    4. Aggregates embeddings into per-participant profiles
    """

    def __init__(self, user_id: str,
                 audio_cache_dir: Optional[str] = None,
                 model_cache_dir: str = "pretrained_models",
                 min_segment_duration: float = 2.0,
                 max_segment_duration: float = 8.0,
                 merge_segments: bool = True,
                 merge_gap_threshold: float = 0.35):
        """
        Initialize the profile builder.

        Args:
            user_id: User ID to build profiles for
            audio_cache_dir: Directory to cache downloaded audio files
            model_cache_dir: Directory to cache ECAPA model
            min_segment_duration: Minimum segment duration for embeddings (seconds)
            max_segment_duration: Maximum segment duration (longer segments windowed)
            merge_segments: Whether to merge adjacent same-speaker segments
            merge_gap_threshold: Max gap between segments to merge (seconds)
        """
        self.user_id = user_id
        self.audio_cache_dir = audio_cache_dir or os.path.join(
            os.path.dirname(__file__), "audio_cache"
        )
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.merge_segments = merge_segments
        self.merge_gap_threshold = merge_gap_threshold

        print(f"Initializing ProfileBuilder for user {user_id}")

        # Initialize components
        self.data_loader = DataLoader()
        self.embedder = EcapaEmbedder(cache_dir=model_cache_dir)
        self.profile_db = SpeakerProfileDB()

        # Track build statistics
        self.stats = BuildStats()

    def build_profiles(self,
                      min_participants: int = 1,
                      require_verified: bool = False,
                      max_meetings: Optional[int] = None,
                      incremental: bool = False,
                      existing_profiles_path: Optional[str] = None) -> SpeakerProfileDB:
        """
        Build speaker profiles from all labeled meetings.

        Args:
            min_participants: Minimum labeled participants per meeting
            require_verified: Only use manually verified speaker mappings
            max_meetings: Maximum number of meetings to process (for testing)
            incremental: If True, skip (participant, recording) pairs that already have embeddings
            existing_profiles_path: Path to existing profiles to load for incremental mode

        Returns:
            SpeakerProfileDB with all built profiles
        """
        print(f"\n=== Building Speaker Profiles ===\n")

        # Load existing profiles for incremental mode
        if incremental and existing_profiles_path and os.path.exists(existing_profiles_path):
            print(f"Incremental mode: loading existing profiles from {existing_profiles_path}")
            self.profile_db = SpeakerProfileDB.load_from_file(existing_profiles_path)
            print(f"  Loaded {len(self.profile_db.profiles)} existing profiles")

            # Build set of (participant_id, recording_id) pairs we already have
            self._existing_pairs = set()
            for pid, profile in self.profile_db.profiles.items():
                for rid in profile.recording_ids:
                    self._existing_pairs.add((pid, rid))
            print(f"  Found {len(self._existing_pairs)} existing (participant, recording) pairs\n")
        else:
            self._existing_pairs = set()
            if incremental:
                print("Incremental mode requested but no existing profiles found - building from scratch\n")

        # Get labeled meetings
        meetings = self.data_loader.get_labeled_meetings(
            self.user_id,
            min_participants=min_participants,
            require_verified=require_verified
        )

        if max_meetings:
            meetings = meetings[:max_meetings]

        print(f"Processing {len(meetings)} labeled meetings...\n")

        skipped_meetings = 0
        for i, meeting in enumerate(meetings):
            print(f"[{i+1}/{len(meetings)}] {meeting.title}")
            processed = self._process_meeting(meeting, incremental=incremental)
            if processed:
                self.stats.meetings_processed += 1
            else:
                skipped_meetings += 1

        # Compute final statistics
        self.stats.participants_found = len(self.profile_db.profiles)

        print(f"\n=== Build Complete ===\n")
        print(self.stats)
        if incremental and skipped_meetings > 0:
            print(f"Skipped meetings (all participants already processed): {skipped_meetings}")
        print()

        # Print per-participant summary
        print("Per-participant summary:")
        for pid, profile in self.profile_db.profiles.items():
            print(f"  {profile.display_name}: {profile.n_samples} embeddings "
                  f"from {len(profile.recording_ids)} meetings")

        return self.profile_db

    def _process_meeting(self, meeting: LabeledMeeting, incremental: bool = False) -> bool:
        """
        Process a single labeled meeting to extract speaker embeddings.

        Args:
            meeting: The labeled meeting to process
            incremental: If True, skip participants already processed for this recording

        Returns:
            True if any participants were processed, False if all skipped
        """
        # Group segments by participant
        participant_segments: Dict[str, List[SpeakerSegment]] = {}
        for seg in meeting.speaker_segments:
            if seg.participant_id:
                participant_segments.setdefault(seg.participant_id, []).append(seg)

        # In incremental mode, check which participants need processing
        if incremental:
            participants_to_process = {}
            for pid, segments in participant_segments.items():
                if (pid, meeting.recording_id) not in self._existing_pairs:
                    participants_to_process[pid] = segments
                else:
                    participant = meeting.participant_map.get(pid)
                    display_name = participant.displayName if participant else pid
                    print(f"    {display_name}: skipped (already has embeddings from this recording)")

            if not participants_to_process:
                return False  # Nothing new to process

            participant_segments = participants_to_process

        # Download audio (only if we have participants to process)
        try:
            audio_path = self.data_loader.download_audio(
                meeting.recording,
                output_dir=self.audio_cache_dir
            )
            meeting.audio_path = audio_path
        except Exception as e:
            print(f"  Error downloading audio: {e}")
            return False

        # Process each participant
        any_processed = False
        for pid, segments in participant_segments.items():
            participant = meeting.participant_map.get(pid)
            display_name = participant.displayName if participant else pid

            # Optionally merge adjacent segments
            if self.merge_segments:
                segment_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in segments]
                merged = merge_adjacent_segments(
                    segment_tuples,
                    max_gap_s=self.merge_gap_threshold
                )
                # Convert back to time ranges
                time_ranges = [(s, e) for s, e, _ in merged]
            else:
                time_ranges = [(s.start_s, s.end_s) for s in segments]

            self.stats.total_segments += len(time_ranges)
            total_duration = sum(e - s for s, e in time_ranges)
            self.stats.total_audio_duration_s += total_duration

            # Extract embeddings for all segments
            embeddings = self.embedder.embeddings_for_segments(
                audio_path,
                time_ranges,
                min_dur_s=self.min_segment_duration,
                max_dur_s=self.max_segment_duration
            )

            # Filter out None embeddings
            valid_embeddings = [e for e in embeddings if e is not None]
            self.stats.segments_with_embeddings += len(valid_embeddings)

            if not valid_embeddings:
                print(f"    {display_name}: no valid embeddings (segments too short)")
                continue

            # Update profile
            profile = self.profile_db.get_or_create(pid, display_name)
            profile.update(valid_embeddings, recording_id=meeting.recording_id)
            any_processed = True

            print(f"    {display_name}: {len(valid_embeddings)}/{len(time_ranges)} embeddings "
                  f"({total_duration:.1f}s audio)")

        return any_processed

    def save_profiles(self, path: str) -> None:
        """Save profiles to JSON file."""
        self.profile_db.save_to_file(path)
        print(f"Profiles saved to {path}")

    def load_profiles(self, path: str) -> SpeakerProfileDB:
        """Load profiles from JSON file."""
        self.profile_db = SpeakerProfileDB.load_from_file(path)
        print(f"Loaded {len(self.profile_db.profiles)} profiles from {path}")
        return self.profile_db


def build_profiles_from_embeddings(
    embeddings_dir: str = "embeddings",
    output_path: str = "speaker_profiles.json",
    require_verified: bool = False
) -> SpeakerProfileDB:
    """
    Build speaker profiles directly from existing embeddings.npz + metadata.json.

    This is MUCH faster than re-extracting embeddings from audio since it reuses
    the embeddings already extracted by extract_embeddings.py.

    Args:
        embeddings_dir: Directory containing embeddings.npz and metadata.json
        output_path: Path to save profiles JSON
        require_verified: Only use manually verified speaker mappings

    Returns:
        Built SpeakerProfileDB
    """
    import numpy as np

    embeddings_path = os.path.join(embeddings_dir, 'embeddings.npz')
    metadata_path = os.path.join(embeddings_dir, 'metadata.json')

    if not os.path.exists(embeddings_path) or not os.path.exists(metadata_path):
        raise FileNotFoundError(f"embeddings.npz and metadata.json must exist in {embeddings_dir}")

    print(f"Building profiles from existing embeddings in {embeddings_dir}")

    # Load embeddings and metadata
    print("  Loading embeddings...")
    embeddings_data = np.load(embeddings_path)
    embeddings = {k: embeddings_data[k] for k in embeddings_data.files}

    print("  Loading metadata...")
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    print(f"  Found {len(embeddings)} speaker embeddings")

    # Build profiles from labeled speakers
    profile_db = SpeakerProfileDB()

    recordings = metadata.get('recordings', {})
    labeled_count = 0
    skipped_unverified = 0

    for rec_id, rec_data in recordings.items():
        speakers = rec_data.get('speakers', {})

        for speaker_label, speaker_info in speakers.items():
            participant_id = speaker_info.get('participant_id')
            participant_name = speaker_info.get('participant_name', '')
            manually_verified = speaker_info.get('manually_verified', False)
            embedding_key = speaker_info.get('embedding_key')

            # Skip unlabeled speakers
            if not participant_id:
                continue

            # Skip unverified if required
            if require_verified and not manually_verified:
                skipped_unverified += 1
                continue

            # Get embeddings for this speaker
            if embedding_key and embedding_key in embeddings:
                speaker_embeddings = embeddings[embedding_key]

                # speaker_embeddings shape is (n_embeddings, 192)
                emb_list = [speaker_embeddings[i] for i in range(speaker_embeddings.shape[0])]

                # Update profile
                profile = profile_db.get_or_create(participant_id, participant_name)
                profile.update(emb_list, recording_id=rec_id)
                labeled_count += 1

    print(f"\nProfile building complete:")
    print(f"  Labeled speakers processed: {labeled_count}")
    if require_verified and skipped_unverified > 0:
        print(f"  Skipped (not verified): {skipped_unverified}")
    print(f"  Unique participants: {len(profile_db.profiles)}")

    # Print per-participant summary
    print("\nPer-participant summary:")
    for pid, profile in profile_db.profiles.items():
        print(f"  {profile.display_name}: {profile.n_samples} embeddings "
              f"from {len(profile.recording_ids)} recordings")

    # Save profiles
    profile_db.save_to_file(output_path)
    print(f"\nProfiles saved to {output_path}")

    return profile_db


def build_and_save_profiles(user_id: str, output_path: str = "speaker_profiles.json",
                           **kwargs) -> SpeakerProfileDB:
    """
    Convenience function to build and save profiles in one call.

    Args:
        user_id: User ID to build profiles for
        output_path: Path to save profiles JSON
        **kwargs: Additional arguments for ProfileBuilder

    Returns:
        Built SpeakerProfileDB
    """
    builder = ProfileBuilder(user_id, **kwargs)
    db = builder.build_profiles()
    builder.save_profiles(output_path)
    return db


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build speaker profiles from labeled meetings")
    parser.add_argument("--user-id", help="User ID to build profiles for (required unless --from-embeddings)")
    parser.add_argument("--output", default="speaker_profiles.json", help="Output path for profiles")
    parser.add_argument("--max-meetings", type=int, help="Maximum meetings to process")
    parser.add_argument("--require-verified", action="store_true",
                        help="Only use manually verified speaker mappings")
    parser.add_argument("--audio-cache", help="Directory to cache audio files")
    parser.add_argument("--incremental", action="store_true",
                        help="Only process new (participant, recording) pairs not in existing profiles")
    parser.add_argument("--from-embeddings", metavar="DIR", nargs="?", const="embeddings",
                        help="Build profiles from existing embeddings.npz + metadata.json (fast mode). "
                             "Optionally specify embeddings directory (default: embeddings/)")

    args = parser.parse_args()

    if args.from_embeddings is not None:
        # Fast mode: build from existing embeddings
        embeddings_dir = args.from_embeddings
        print(f"\n=== Building Profiles from Existing Embeddings ===")
        print(f"Directory: {embeddings_dir}")
        print(f"Require verified: {args.require_verified}\n")

        build_profiles_from_embeddings(
            embeddings_dir=embeddings_dir,
            output_path=args.output,
            require_verified=args.require_verified
        )
    else:
        # Traditional mode: extract from audio
        if not args.user_id:
            parser.error("--user-id is required unless using --from-embeddings")

        builder = ProfileBuilder(
            user_id=args.user_id,
            audio_cache_dir=args.audio_cache
        )

        # For incremental mode, use output path as existing profiles path
        existing_profiles = args.output if args.incremental else None

        builder.build_profiles(
            require_verified=args.require_verified,
            max_meetings=args.max_meetings,
            incremental=args.incremental,
            existing_profiles_path=existing_profiles
        )

        builder.save_profiles(args.output)
