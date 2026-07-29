"""
Speaker Identification Experiment

Uses ECAPA-TDNN embeddings to identify speakers across meetings
based on labeled recordings.

Modules:
- speaker_embedder: ECAPA-TDNN embedding extraction and profile management
- data_loader: QuickScribe database connectivity
- profile_builder: Build speaker profiles from labeled meetings
- speaker_identifier: Identify speakers in unlabeled meetings
- run_experiment: Complete experiment runner
"""

from .speaker_embedder import (
    EcapaEmbedder,
    SpeakerProfile,
    SpeakerProfileDB,
    cosine_similarity,
    l2_normalize,
    merge_adjacent_segments,
    build_meeting_speaker_centroids,
)

from .data_loader import (
    DataLoader,
    LabeledMeeting,
    UnlabeledMeeting,
    SpeakerSegment,
)

from .profile_builder import (
    ProfileBuilder,
    build_and_save_profiles,
)

from .speaker_identifier import (
    SpeakerIdentifier,
    SpeakerMatch,
    MeetingIdentificationResult,
)

__all__ = [
    # Embedder
    "EcapaEmbedder",
    "SpeakerProfile",
    "SpeakerProfileDB",
    "cosine_similarity",
    "l2_normalize",
    "merge_adjacent_segments",
    "build_meeting_speaker_centroids",
    # Data
    "DataLoader",
    "LabeledMeeting",
    "UnlabeledMeeting",
    "SpeakerSegment",
    # Builder
    "ProfileBuilder",
    "build_and_save_profiles",
    # Identifier
    "SpeakerIdentifier",
    "SpeakerMatch",
    "MeetingIdentificationResult",
]
