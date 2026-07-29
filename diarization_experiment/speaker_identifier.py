"""
Speaker Identifier

Uses pre-built speaker profiles to identify speakers in unlabeled meetings.

The identifier:
1. Loads unlabeled meetings from QuickScribe database
2. Downloads audio files
3. Extracts ECAPA embeddings for each diarized speaker
4. Matches embeddings against known speaker profiles
5. Reports identification results with confidence levels

Usage:
    identifier = SpeakerIdentifier(user_id="...", profiles_path="speaker_profiles.json")
    results = identifier.identify_all_meetings()
    identifier.print_results(results)
"""

from __future__ import annotations

import os
import json
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
import numpy as np

from speaker_embedder import (
    EcapaEmbedder, SpeakerProfileDB,
    merge_adjacent_segments, l2_normalize, cosine_similarity,
    build_meeting_speaker_centroids
)
from data_loader import DataLoader, UnlabeledMeeting, SpeakerSegment


@dataclass
class SpeakerMatch:
    """Result of matching a speaker against known profiles."""
    speaker_label: str  # Original diarization label (e.g., "Speaker 1")
    status: str  # "auto", "suggest", or "unknown"
    matched_participant_id: Optional[str] = None
    matched_display_name: Optional[str] = None
    similarity: Optional[float] = None
    embedding: Optional[np.ndarray] = None  # The speaker's centroid in this meeting
    segment_count: int = 0
    total_duration_s: float = 0.0

    def __str__(self) -> str:
        if self.status == "unknown":
            return f"{self.speaker_label}: Unknown ({self.segment_count} segments, {self.total_duration_s:.1f}s)"
        sim_pct = self.similarity * 100 if self.similarity else 0
        return (f"{self.speaker_label} -> {self.matched_display_name} "
                f"[{self.status}] (sim={sim_pct:.1f}%, {self.segment_count} segments, "
                f"{self.total_duration_s:.1f}s)")


@dataclass
class MeetingIdentificationResult:
    """Identification results for a single meeting."""
    recording_id: str
    title: str
    speaker_matches: List[SpeakerMatch] = field(default_factory=list)

    @property
    def auto_count(self) -> int:
        return sum(1 for m in self.speaker_matches if m.status == "auto")

    @property
    def suggest_count(self) -> int:
        return sum(1 for m in self.speaker_matches if m.status == "suggest")

    @property
    def unknown_count(self) -> int:
        return sum(1 for m in self.speaker_matches if m.status == "unknown")

    def get_match_for_speaker(self, speaker_label: str) -> Optional[SpeakerMatch]:
        for m in self.speaker_matches:
            if m.speaker_label == speaker_label:
                return m
        return None

    def __str__(self) -> str:
        lines = [f"Meeting: {self.title}"]
        lines.append(f"  Auto: {self.auto_count}, Suggest: {self.suggest_count}, "
                    f"Unknown: {self.unknown_count}")
        for match in self.speaker_matches:
            lines.append(f"    {match}")
        return "\n".join(lines)


@dataclass
class IdentificationStats:
    """Aggregate statistics across all meetings."""
    meetings_processed: int = 0
    total_speakers: int = 0
    auto_identified: int = 0
    suggested: int = 0
    unknown: int = 0

    @property
    def identification_rate(self) -> float:
        """Percentage of speakers auto-identified."""
        if self.total_speakers == 0:
            return 0.0
        return self.auto_identified / self.total_speakers * 100

    @property
    def suggestion_rate(self) -> float:
        """Percentage of speakers with suggestions (auto + suggest)."""
        if self.total_speakers == 0:
            return 0.0
        return (self.auto_identified + self.suggested) / self.total_speakers * 100

    def __str__(self) -> str:
        return (
            f"Meetings processed: {self.meetings_processed}\n"
            f"Total speakers: {self.total_speakers}\n"
            f"Auto-identified: {self.auto_identified} ({self.identification_rate:.1f}%)\n"
            f"Suggested: {self.suggested}\n"
            f"Unknown: {self.unknown}\n"
            f"Overall recognition rate: {self.suggestion_rate:.1f}%"
        )


class SpeakerIdentifier:
    """
    Identifies speakers in unlabeled meetings using pre-built profiles.
    """

    def __init__(self, user_id: str,
                 profiles_path: Optional[str] = None,
                 profile_db: Optional[SpeakerProfileDB] = None,
                 audio_cache_dir: Optional[str] = None,
                 model_cache_dir: str = "pretrained_models",
                 high_threshold: float = 0.78,
                 low_threshold: float = 0.68,
                 min_segment_duration: float = 2.0,
                 max_segment_duration: float = 8.0):
        """
        Initialize the speaker identifier.

        Args:
            user_id: User ID to process
            profiles_path: Path to saved speaker profiles JSON
            profile_db: Pre-loaded SpeakerProfileDB (alternative to profiles_path)
            audio_cache_dir: Directory to cache downloaded audio files
            model_cache_dir: Directory to cache ECAPA model
            high_threshold: Similarity threshold for auto-identification
            low_threshold: Similarity threshold for suggestions
            min_segment_duration: Minimum segment duration for embeddings
            max_segment_duration: Maximum segment duration
        """
        self.user_id = user_id
        self.audio_cache_dir = audio_cache_dir or os.path.join(
            os.path.dirname(__file__), "audio_cache"
        )
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration

        print(f"Initializing SpeakerIdentifier for user {user_id}")
        print(f"  Thresholds: auto >= {high_threshold}, suggest >= {low_threshold}")

        # Initialize components
        self.data_loader = DataLoader()
        self.embedder = EcapaEmbedder(cache_dir=model_cache_dir)

        # Load profiles
        if profile_db:
            self.profile_db = profile_db
        elif profiles_path:
            self.profile_db = SpeakerProfileDB.load_from_file(profiles_path)
        else:
            raise ValueError("Must provide either profiles_path or profile_db")

        print(f"  Loaded {len(self.profile_db.profiles)} speaker profiles")

        # Track statistics
        self.stats = IdentificationStats()

    def identify_meeting(self, meeting: UnlabeledMeeting) -> MeetingIdentificationResult:
        """
        Identify speakers in a single meeting.

        Args:
            meeting: UnlabeledMeeting to process

        Returns:
            MeetingIdentificationResult with speaker matches
        """
        result = MeetingIdentificationResult(
            recording_id=meeting.recording_id,
            title=meeting.title
        )

        # Download audio if needed
        try:
            audio_path = self.data_loader.download_audio(
                meeting.recording,
                output_dir=self.audio_cache_dir
            )
            meeting.audio_path = audio_path
        except Exception as e:
            print(f"  Error downloading audio: {e}")
            return result

        # Group segments by speaker label
        speaker_segments: Dict[str, List[SpeakerSegment]] = {}
        for seg in meeting.speaker_segments:
            speaker_segments.setdefault(seg.speaker_label, []).append(seg)

        # Process each speaker
        for speaker_label, segments in speaker_segments.items():
            # Merge adjacent segments for better embeddings
            segment_tuples = [(s.start_s, s.end_s, s.speaker_label) for s in segments]
            merged = merge_adjacent_segments(segment_tuples, max_gap_s=0.35)
            time_ranges = [(s, e) for s, e, _ in merged]

            total_duration = sum(e - s for s, e in time_ranges)

            # Extract embeddings
            embeddings = self.embedder.embeddings_for_segments(
                audio_path,
                time_ranges,
                min_dur_s=self.min_segment_duration,
                max_dur_s=self.max_segment_duration
            )

            valid_embeddings = [e for e in embeddings if e is not None]

            if not valid_embeddings:
                # Not enough audio for this speaker
                result.speaker_matches.append(SpeakerMatch(
                    speaker_label=speaker_label,
                    status="unknown",
                    segment_count=len(segments),
                    total_duration_s=total_duration
                ))
                continue

            # Compute centroid for this speaker in this meeting
            emb_stack = np.stack([l2_normalize(e) for e in valid_embeddings], axis=0)
            speaker_centroid = l2_normalize(emb_stack.mean(axis=0))

            # Match against known profiles
            match_result = self.profile_db.match_with_confidence(
                speaker_centroid,
                high_threshold=self.high_threshold,
                low_threshold=self.low_threshold
            )

            result.speaker_matches.append(SpeakerMatch(
                speaker_label=speaker_label,
                status=match_result["status"],
                matched_participant_id=match_result["participant_id"],
                matched_display_name=match_result["display_name"],
                similarity=match_result["similarity"],
                embedding=speaker_centroid,
                segment_count=len(segments),
                total_duration_s=total_duration
            ))

        return result

    def identify_all_meetings(self, max_meetings: Optional[int] = None) -> List[MeetingIdentificationResult]:
        """
        Identify speakers in all unlabeled meetings.

        Args:
            max_meetings: Maximum meetings to process (for testing)

        Returns:
            List of MeetingIdentificationResult
        """
        print(f"\n=== Identifying Speakers in Unlabeled Meetings ===\n")

        meetings = self.data_loader.get_unlabeled_meetings(self.user_id)

        if max_meetings:
            meetings = meetings[:max_meetings]

        print(f"Processing {len(meetings)} unlabeled meetings...\n")

        results: List[MeetingIdentificationResult] = []

        for i, meeting in enumerate(meetings):
            print(f"[{i+1}/{len(meetings)}] {meeting.title}")

            result = self.identify_meeting(meeting)
            results.append(result)

            # Update stats
            self.stats.meetings_processed += 1
            for match in result.speaker_matches:
                self.stats.total_speakers += 1
                if match.status == "auto":
                    self.stats.auto_identified += 1
                elif match.status == "suggest":
                    self.stats.suggested += 1
                else:
                    self.stats.unknown += 1

            # Print quick summary
            print(f"  -> Auto: {result.auto_count}, Suggest: {result.suggest_count}, "
                  f"Unknown: {result.unknown_count}")

        print(f"\n=== Identification Complete ===\n")
        print(self.stats)

        return results

    def print_detailed_results(self, results: List[MeetingIdentificationResult]) -> None:
        """Print detailed results for all meetings."""
        print("\n=== Detailed Results ===\n")
        for result in results:
            print(result)
            print()

    def get_confusion_matrix(self, results: List[MeetingIdentificationResult],
                            ground_truth: Dict[str, Dict[str, str]]) -> Dict:
        """
        Compute confusion matrix if ground truth is available.

        Args:
            results: Identification results
            ground_truth: Dict mapping recording_id -> {speaker_label -> participant_id}

        Returns:
            Dict with confusion matrix and metrics
        """
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        true_negatives = 0

        for result in results:
            if result.recording_id not in ground_truth:
                continue

            gt = ground_truth[result.recording_id]

            for match in result.speaker_matches:
                if match.speaker_label not in gt:
                    continue

                actual_pid = gt[match.speaker_label]
                predicted_pid = match.matched_participant_id

                if actual_pid is None and predicted_pid is None:
                    true_negatives += 1
                elif actual_pid == predicted_pid:
                    true_positives += 1
                elif predicted_pid is None:
                    false_negatives += 1
                else:
                    false_positives += 1

        total = true_positives + false_positives + false_negatives + true_negatives
        accuracy = (true_positives + true_negatives) / total if total > 0 else 0
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "true_negatives": true_negatives,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1
        }


def identify_and_report(user_id: str, profiles_path: str, max_meetings: Optional[int] = None) -> None:
    """Convenience function to run identification and print results."""
    identifier = SpeakerIdentifier(user_id=user_id, profiles_path=profiles_path)
    results = identifier.identify_all_meetings(max_meetings=max_meetings)
    identifier.print_detailed_results(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Identify speakers in unlabeled meetings")
    parser.add_argument("--user-id", required=True, help="User ID to process")
    parser.add_argument("--profiles", required=True, help="Path to speaker profiles JSON")
    parser.add_argument("--max-meetings", type=int, help="Maximum meetings to process")
    parser.add_argument("--high-threshold", type=float, default=0.78,
                        help="Similarity threshold for auto-identification")
    parser.add_argument("--low-threshold", type=float, default=0.68,
                        help="Similarity threshold for suggestions")
    parser.add_argument("--audio-cache", help="Directory to cache audio files")

    args = parser.parse_args()

    identifier = SpeakerIdentifier(
        user_id=args.user_id,
        profiles_path=args.profiles,
        audio_cache_dir=args.audio_cache,
        high_threshold=args.high_threshold,
        low_threshold=args.low_threshold
    )

    results = identifier.identify_all_meetings(max_meetings=args.max_meetings)
    identifier.print_detailed_results(results)
