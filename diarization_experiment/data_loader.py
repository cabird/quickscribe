"""
Data Loader for Speaker Identification Experiment

Connects to QuickScribe's CosmosDB and Azure Blob Storage to:
1. Find recordings with labeled speakers (transcriptions with speaker_mapping + participantId)
2. Parse Azure transcription JSON to extract speaker segments with timing
3. Download audio files for embedding extraction

Usage:
    loader = DataLoader()
    labeled_meetings = loader.get_labeled_meetings(user_id)
    for meeting in labeled_meetings:
        audio_path = loader.download_audio(meeting.recording)
        segments = meeting.speaker_segments
"""

from __future__ import annotations

import os
import json
import tempfile
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

# Add parent directory to path for shared_quickscribe_py
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load .env before importing shared library (which validates config on import)
from dotenv import load_dotenv
load_dotenv()

from azure.cosmos import CosmosClient

from shared_quickscribe_py.config import get_settings, QuickScribeSettings
from shared_quickscribe_py.cosmos import (
    RecordingHandler, TranscriptionHandler, ParticipantHandler,
    Recording, Transcription, Participant
)
from shared_quickscribe_py.azure_services import BlobStorageClient


# Azure time format: 100-nanosecond ticks or ISO duration strings
TICKS_PER_SECOND = 10_000_000


@dataclass
class SpeakerSegment:
    """A single speaker segment with timing and speaker info."""
    start_s: float
    end_s: float
    speaker_label: str  # e.g., "Speaker 1"
    text: str
    participant_id: Optional[str] = None  # If mapped to a participant
    participant_name: Optional[str] = None


@dataclass
class LabeledMeeting:
    """A meeting that has labeled speakers (speaker_mapping with participantIds)."""
    recording: Recording
    transcription: Transcription
    speaker_segments: List[SpeakerSegment]
    participant_map: Dict[str, Participant]  # participant_id -> Participant
    audio_path: Optional[str] = None  # Set after downloading

    @property
    def recording_id(self) -> str:
        return self.recording.id

    @property
    def title(self) -> str:
        return self.recording.title or self.recording.original_filename

    def get_segments_for_participant(self, participant_id: str) -> List[SpeakerSegment]:
        """Get all segments for a specific participant."""
        return [s for s in self.speaker_segments if s.participant_id == participant_id]

    def get_labeled_participants(self) -> List[str]:
        """Get list of participant IDs that appear in this meeting."""
        return list(set(s.participant_id for s in self.speaker_segments if s.participant_id))


@dataclass
class UnlabeledMeeting:
    """A meeting that has diarization but no labeled speakers."""
    recording: Recording
    transcription: Transcription
    speaker_segments: List[SpeakerSegment]
    audio_path: Optional[str] = None

    @property
    def recording_id(self) -> str:
        return self.recording.id

    @property
    def title(self) -> str:
        return self.recording.title or self.recording.original_filename

    def get_segments_for_speaker(self, speaker_label: str) -> List[SpeakerSegment]:
        """Get all segments for a specific speaker label."""
        return [s for s in self.speaker_segments if s.speaker_label == speaker_label]

    def get_speaker_labels(self) -> List[str]:
        """Get unique speaker labels in this meeting."""
        return list(set(s.speaker_label for s in self.speaker_segments))


def _parse_azure_time(x: Any) -> Optional[float]:
    """
    Parse Azure time formats to seconds.

    Handles:
    - int/float ticks (100ns units)
    - ISO 8601 durations like "PT12.34S", "PT2M11.84S", "PT1H30M45.5S"
    - Plain seconds as string
    """
    if x is None:
        return None

    if isinstance(x, (int, float)):
        # Large numbers are ticks, small are seconds
        if x > 1e6:
            return float(x) / TICKS_PER_SECOND
        return float(x)

    if isinstance(x, str):
        s = x.strip()

        # ISO 8601 duration: PT[nH][nM][nS] (e.g., PT1H30M45.5S, PT2M11.84S, PT12.34S)
        if s.startswith("PT"):
            total_seconds = 0.0
            remainder = s[2:]  # Strip "PT"

            # Extract hours
            h_match = re.match(r"(\d+)H", remainder)
            if h_match:
                total_seconds += int(h_match.group(1)) * 3600
                remainder = remainder[h_match.end():]

            # Extract minutes
            m_match = re.match(r"(\d+)M", remainder)
            if m_match:
                total_seconds += int(m_match.group(1)) * 60
                remainder = remainder[m_match.end():]

            # Extract seconds
            s_match = re.match(r"(\d+(?:\.\d+)?)S", remainder)
            if s_match:
                total_seconds += float(s_match.group(1))

            if total_seconds > 0:
                return total_seconds

        # Plain seconds
        try:
            return float(s)
        except ValueError:
            return None

    return None


def _parse_azure_transcript_json(transcript_json: str) -> List[SpeakerSegment]:
    """
    Parse Azure Speech Services transcript JSON to extract speaker segments.

    The JSON contains recognizedPhrases with:
    - speaker: int (speaker ID)
    - offset: int (start time in 100ns ticks)
    - duration: int (duration in 100ns ticks)
    - nBest[0].display: string (transcribed text)
    """
    segments: List[SpeakerSegment] = []

    try:
        data = json.loads(transcript_json)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse transcript JSON: {e}")
        return segments

    for phrase in data.get("recognizedPhrases", []):
        speaker_id = phrase.get("speaker")
        if speaker_id is None:
            continue

        speaker_label = f"Speaker {speaker_id}"

        offset = _parse_azure_time(phrase.get("offset"))
        duration = _parse_azure_time(phrase.get("duration"))

        if offset is None:
            continue

        end_s = offset + duration if duration else offset + 1.0

        # Get display text
        text = ""
        nbest = phrase.get("nBest", [])
        if nbest and isinstance(nbest, list):
            text = nbest[0].get("display", "")

        segments.append(SpeakerSegment(
            start_s=offset,
            end_s=end_s,
            speaker_label=speaker_label,
            text=text,
        ))

    # Sort by start time
    segments.sort(key=lambda s: s.start_s)
    return segments


class DataLoader:
    """
    Loads data from QuickScribe's CosmosDB for speaker identification experiments.
    """

    def __init__(self, settings: Optional[QuickScribeSettings] = None):
        """
        Initialize data loader with database connections.

        Args:
            settings: QuickScribeSettings instance. If None, loads from environment.
        """
        self.settings = settings or get_settings()

        # Initialize handlers
        cosmos_endpoint = self.settings.cosmos.endpoint
        cosmos_key = self.settings.cosmos.key
        database_name = self.settings.cosmos.database_name

        self.recording_handler = RecordingHandler(cosmos_endpoint, cosmos_key, database_name, 'QuickScribeContainer')
        self.transcription_handler = TranscriptionHandler(cosmos_endpoint, cosmos_key, database_name, 'QuickScribeContainer')
        self.participant_handler = ParticipantHandler(cosmos_endpoint, cosmos_key, database_name, 'QuickScribeContainer')

        # Shared CosmosDB container client for custom queries
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        db = cosmos_client.get_database_client(database_name)
        self.container = db.get_container_client('QuickScribeContainer')

        # Blob storage for audio downloads
        self.blob_client = BlobStorageClient(self.settings.blob_storage.connection_string, 'recordings')

        # Cache for participants
        self._participant_cache: Dict[str, Participant] = {}

        print(f"DataLoader initialized (database: {database_name})")

    def _get_participant(self, user_id: str, participant_id: str) -> Optional[Participant]:
        """Get participant with caching."""
        cache_key = f"{user_id}:{participant_id}"
        if cache_key not in self._participant_cache:
            try:
                p = self.participant_handler.get_participant(user_id, participant_id)
                if p:
                    self._participant_cache[cache_key] = p
            except Exception:
                pass
        return self._participant_cache.get(cache_key)

    def _load_user_participants(self, user_id: str) -> Dict[str, Participant]:
        """Load all participants for a user into cache."""
        try:
            participants = self.participant_handler.get_participants_for_user(user_id)
            for p in participants:
                cache_key = f"{user_id}:{p.id}"
                self._participant_cache[cache_key] = p
            return {p.id: p for p in participants}
        except Exception as e:
            print(f"Warning: Failed to load participants: {e}")
            return {}

    def get_labeled_meetings(self, user_id: str,
                            min_participants: int = 1,
                            require_verified: bool = False) -> List[LabeledMeeting]:
        """
        Get meetings that have labeled speakers (speaker_mapping in transcription).

        Speaker mappings are read from Transcription.speaker_mapping, which is the
        canonical source of truth for speaker identification.

        Args:
            user_id: User ID to query
            min_participants: Minimum number of labeled participants required
            require_verified: If True, only include manually verified mappings

        Returns:
            List of LabeledMeeting objects
        """
        print(f"Fetching labeled meetings for user {user_id}...")

        # Load all participants for this user
        all_participants = self._load_user_participants(user_id)
        print(f"  Loaded {len(all_participants)} participant profiles")

        # Get completed recordings with transcriptions
        recordings_data = list(self.container.query_items(
            query="""
            SELECT c.id, c.user_id, c.title, c.original_filename, c.unique_filename,
                   c.duration, c.transcription_id, c.transcription_status,
                   c.upload_timestamp, c.recorded_timestamp
            FROM c
            WHERE c.transcription_status = 'completed'
            AND c.transcription_id != null
            AND c.user_id = @user_id
            """,
            parameters=[
                {'name': '@user_id', 'value': user_id}
            ],
            enable_cross_partition_query=True
        ))

        print(f"  Found {len(recordings_data)} recordings with transcriptions")

        labeled_meetings: List[LabeledMeeting] = []
        skipped_no_timing = 0
        skipped_no_speaker_mapping = 0

        for rec_data in recordings_data:
            trans_id = rec_data.get('transcription_id')
            if not trans_id:
                continue

            # Get transcription with speaker_mapping
            trans_results = list(self.container.query_items(
                query="SELECT * FROM c WHERE c.id = @id",
                parameters=[{'name': '@id', 'value': trans_id}],
                enable_cross_partition_query=True
            ))

            if not trans_results:
                continue

            trans_data = trans_results[0]
            transcript_json = trans_data.get('transcript_json')

            if not transcript_json:
                skipped_no_timing += 1
                continue

            # Read speaker mapping from transcription (canonical source of truth)
            speaker_mapping = trans_data.get('speaker_mapping') or {}

            # Build participant map and label mapping from transcription.speaker_mapping
            participant_map: Dict[str, Participant] = {}
            label_to_participant: Dict[str, str] = {}

            for speaker_label, mapping_entry in speaker_mapping.items():
                if not isinstance(mapping_entry, dict):
                    continue

                pid = mapping_entry.get('participantId')
                if not pid:
                    continue

                if require_verified and not mapping_entry.get('manuallyVerified', False):
                    continue

                participant = all_participants.get(pid)
                if participant:
                    participant_map[pid] = participant
                    label_to_participant[speaker_label] = pid
                else:
                    print(f"  WARNING: speaker_mapping references participant {pid} but profile not found")

            # Check minimum participants requirement
            if len(participant_map) < min_participants:
                skipped_no_speaker_mapping += 1
                continue

            # Build a minimal Recording object
            recording = Recording(
                id=rec_data['id'],
                user_id=rec_data.get('user_id', user_id),
                partitionKey='recording',
                title=rec_data.get('title', ''),
                original_filename=rec_data.get('original_filename', ''),
                unique_filename=rec_data.get('unique_filename', ''),
                duration=rec_data.get('duration'),
                transcription_id=trans_id,
                transcription_status=rec_data.get('transcription_status'),
                upload_timestamp=rec_data.get('upload_timestamp'),
                recorded_timestamp=rec_data.get('recorded_timestamp'),
            )

            # Parse segments and add participant info
            segments = _parse_azure_transcript_json(transcript_json)

            for seg in segments:
                if seg.speaker_label in label_to_participant:
                    pid = label_to_participant[seg.speaker_label]
                    seg.participant_id = pid
                    seg.participant_name = participant_map[pid].displayName

            # Create minimal Transcription object
            transcription = Transcription(
                id=trans_id,
                recording_id=rec_data['id'],
                user_id=user_id,
                partitionKey=user_id,
                transcript_json=transcript_json,
                diarized_transcript=trans_data.get('diarized_transcript', ''),
            )

            labeled_meetings.append(LabeledMeeting(
                recording=recording,
                transcription=transcription,
                speaker_segments=segments,
                participant_map=participant_map,
            ))

        print(f"  Found {len(labeled_meetings)} meetings with labeled speakers and timing data")
        if skipped_no_timing > 0:
            print(f"  (Skipped {skipped_no_timing} without timing data)")
        if skipped_no_speaker_mapping > 0:
            print(f"  (Skipped {skipped_no_speaker_mapping} without enough labeled speakers in speaker_mapping)")

        return labeled_meetings

    def get_unlabeled_meetings(self, user_id: str) -> List[UnlabeledMeeting]:
        """
        Get meetings with diarization but no labeled speakers.

        Uses transcription.speaker_mapping as the source of truth for labels.
        A meeting is "unlabeled" if speaker_mapping is empty or has no participantId values.

        Args:
            user_id: User ID to query

        Returns:
            List of UnlabeledMeeting objects
        """
        print(f"Fetching unlabeled meetings for user {user_id}...")

        # Get all completed recordings with transcriptions
        recordings_data = list(self.container.query_items(
            query="""
            SELECT c.id, c.user_id, c.title, c.original_filename, c.unique_filename,
                   c.duration, c.transcription_id, c.transcription_status,
                   c.upload_timestamp, c.recorded_timestamp
            FROM c
            WHERE c.transcription_status = 'completed'
            AND c.user_id = @user_id
            AND c.transcription_id != null
            """,
            parameters=[{'name': '@user_id', 'value': user_id}],
            enable_cross_partition_query=True
        ))

        print(f"  Found {len(recordings_data)} completed recordings")

        # Batch fetch all transcriptions with speaker_mapping
        trans_ids = [r.get('transcription_id') for r in recordings_data if r.get('transcription_id')]
        print(f"  Fetching {len(trans_ids)} transcriptions...")

        # Fetch all transcriptions at once (including speaker_mapping)
        transcriptions_map = {}
        if trans_ids:
            # CosmosDB has a limit on IN clause, so batch in chunks of 100
            for i in range(0, len(trans_ids), 100):
                chunk = trans_ids[i:i+100]
                # Build IN clause dynamically
                id_params = [{'name': f'@id{j}', 'value': tid} for j, tid in enumerate(chunk)]
                id_placeholders = ', '.join(f'@id{j}' for j in range(len(chunk)))

                trans_results = list(self.container.query_items(
                    query=f"SELECT c.id, c.transcript_json, c.diarized_transcript, c.speaker_mapping FROM c WHERE c.id IN ({id_placeholders})",
                    parameters=id_params,
                    enable_cross_partition_query=True
                ))

                for t in trans_results:
                    transcriptions_map[t['id']] = t

                if i + 100 < len(trans_ids):
                    print(f"    Fetched {min(i+100, len(trans_ids))}/{len(trans_ids)} transcriptions...")

        print(f"  Loaded {len(transcriptions_map)} transcriptions")

        unlabeled_meetings: List[UnlabeledMeeting] = []
        skipped_no_timing = 0
        skipped_has_labels = 0

        for rec_data in recordings_data:
            trans_id = rec_data.get('transcription_id')
            if not trans_id:
                continue

            trans_data = transcriptions_map.get(trans_id)
            if not trans_data:
                skipped_no_timing += 1
                continue

            transcript_json = trans_data.get('transcript_json')

            if not transcript_json:
                skipped_no_timing += 1
                continue

            # Check speaker_mapping - if any speaker has a participantId, it's labeled
            speaker_mapping = trans_data.get('speaker_mapping') or {}
            has_labels = any(
                isinstance(entry, dict) and entry.get('participantId')
                for entry in speaker_mapping.values()
            )
            if has_labels:
                skipped_has_labels += 1
                continue

            segments = _parse_azure_transcript_json(transcript_json)
            if not segments:
                skipped_no_timing += 1
                continue

            # Build Recording object
            recording = Recording(
                id=rec_data['id'],
                user_id=rec_data.get('user_id', user_id),
                partitionKey='recording',
                title=rec_data.get('title', ''),
                original_filename=rec_data.get('original_filename', ''),
                unique_filename=rec_data.get('unique_filename', ''),
                duration=rec_data.get('duration'),
                transcription_id=trans_id,
                transcription_status=rec_data.get('transcription_status'),
                upload_timestamp=rec_data.get('upload_timestamp'),
                recorded_timestamp=rec_data.get('recorded_timestamp'),
            )

            # Build Transcription object
            transcription = Transcription(
                id=trans_id,
                recording_id=rec_data['id'],
                user_id=user_id,
                partitionKey=user_id,
                transcript_json=transcript_json,
                diarized_transcript=trans_data.get('diarized_transcript', ''),
            )

            unlabeled_meetings.append(UnlabeledMeeting(
                recording=recording,
                transcription=transcription,
                speaker_segments=segments,
            ))

        print(f"  Found {len(unlabeled_meetings)} unlabeled meetings with diarization")
        if skipped_has_labels > 0:
            print(f"  (Skipped {skipped_has_labels} that have speaker labels in transcription.speaker_mapping)")
        if skipped_no_timing > 0:
            print(f"  (Skipped {skipped_no_timing} without timing data)")

        return unlabeled_meetings

    def download_audio(self, recording: Recording, output_dir: Optional[str] = None) -> str:
        """
        Download audio file for a recording. Uses atomic downloads via temp files.

        Args:
            recording: Recording to download
            output_dir: Directory to save file. Uses temp dir if None.

        Returns:
            Path to downloaded audio file
        """
        # Use unique_filename for blob path
        blob_name = recording.unique_filename

        # Determine output path
        if output_dir:
            output_path = os.path.join(output_dir, blob_name)
        else:
            output_path = os.path.join(tempfile.gettempdir(), f"qs_audio_{blob_name}")

        # Ensure parent directory exists (blob_name may include subdirectories like user-xxx/)
        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Download if not already cached
        if not os.path.exists(output_path):
            print(f"  Downloading {blob_name}...")
            # Use temp file for atomic download
            temp_path = output_path + ".tmp"
            try:
                self.blob_client.download_file(blob_name, temp_path)
                os.rename(temp_path, output_path)  # Atomic rename
            except Exception:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise
            print(f"  Downloaded to {output_path}")
        else:
            print(f"  Using cached {output_path}")

        return output_path

    def download_audio_with_fallback(self, unique_filename: str, user_id: str, output_path: str) -> bool:
        """
        Download audio file, trying fallback paths if needed.

        Some blobs are stored as just 'guid.mp3', others as 'user-xxx/guid.mp3'.
        This function tries both patterns. Uses atomic downloads via temp files.

        Args:
            unique_filename: The unique filename from the recording
            user_id: User ID for fallback path
            output_path: Local path to save the file

        Returns:
            True if download succeeded, False otherwise.
        """
        # Ensure parent directory exists (output_path may include subdirectories)
        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Use temp file for atomic download
        temp_path = output_path + ".tmp"

        # Try direct path first
        try:
            self.blob_client.download_file(unique_filename, temp_path)
            os.rename(temp_path, output_path)  # Atomic rename
            return True
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # Try with user prefix
        prefixed_path = f"{user_id}/{unique_filename}"
        try:
            self.blob_client.download_file(prefixed_path, temp_path)
            os.rename(temp_path, output_path)  # Atomic rename
            return True
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"    Error downloading {unique_filename} (tried both paths): {e}")
            return False

    def get_recording_by_id(self, recording_id: str, user_id: str) -> Optional[Recording]:
        """Get a recording by ID."""
        try:
            # Query directly since handler signature varies
            results = list(self.container.query_items(
                query="SELECT * FROM c WHERE c.id = @id AND c.user_id = @user_id",
                parameters=[
                    {'name': '@id', 'value': recording_id},
                    {'name': '@user_id', 'value': user_id}
                ],
                enable_cross_partition_query=True
            ))
            if results:
                rec_data = results[0]
                return Recording(
                    id=rec_data['id'],
                    user_id=rec_data.get('user_id', user_id),
                    partitionKey='recording',
                    title=rec_data.get('title', ''),
                    original_filename=rec_data.get('original_filename', ''),
                    unique_filename=rec_data.get('unique_filename', ''),
                    duration=rec_data.get('duration'),
                    transcription_id=rec_data.get('transcription_id'),
                    transcription_status=rec_data.get('transcription_status'),
                    upload_timestamp=rec_data.get('upload_timestamp'),
                    recorded_timestamp=rec_data.get('recorded_timestamp'),
                )
            return None
        except Exception as e:
            print(f"Error getting recording {recording_id}: {e}")
            return None

    def get_transcription(self, recording_id: str, user_id: str) -> Optional[Dict]:
        """Get transcription for a recording."""
        try:
            # First get the recording to find its transcription_id
            recording = self.get_recording_by_id(recording_id, user_id)
            if not recording or not recording.transcription_id:
                return None

            # Query transcription by its document ID (same approach as get_labeled_meetings)
            results = list(self.container.query_items(
                query="SELECT * FROM c WHERE c.id = @id",
                parameters=[{'name': '@id', 'value': recording.transcription_id}],
                enable_cross_partition_query=True
            ))
            if results:
                return results[0]
            return None
        except Exception as e:
            print(f"Error getting transcription for {recording_id}: {e}")
            return None

    def get_participant_by_id(self, participant_id: str, user_id: str) -> Optional[Dict]:
        """Get a participant by ID."""
        participant = self._get_participant(user_id, participant_id)
        if participant:
            # Convert Pydantic model to dict for compatibility
            return participant.model_dump()
        return None

    def save_transcription(self, transcription: Dict):
        """Save a transcription (used by apply_validations.py)."""
        try:
            # Use upsert to save the transcription directly
            self.container.upsert_item(transcription)
        except Exception as e:
            print(f"Error saving transcription: {e}")
            raise

    def get_all_participants(self, user_id: str) -> List[Participant]:
        """Get all participant profiles for a user."""
        return self.participant_handler.get_participants_for_user(user_id)

    def get_participant_stats(self, user_id: str) -> Dict[str, Dict]:
        """
        Get statistics about labeled participants across all meetings.

        Returns dict mapping participant_id to:
        - display_name
        - meeting_count: number of meetings they appear in
        - segment_count: total number of speech segments
        - total_duration_s: total speaking time in seconds
        """
        labeled = self.get_labeled_meetings(user_id)

        stats: Dict[str, Dict] = {}

        for meeting in labeled:
            for pid, participant in meeting.participant_map.items():
                if pid not in stats:
                    stats[pid] = {
                        "display_name": participant.displayName,
                        "meeting_count": 0,
                        "segment_count": 0,
                        "total_duration_s": 0.0,
                    }

                stats[pid]["meeting_count"] += 1

                for seg in meeting.speaker_segments:
                    if seg.participant_id == pid:
                        stats[pid]["segment_count"] += 1
                        stats[pid]["total_duration_s"] += (seg.end_s - seg.start_s)

        return stats


def print_participant_stats(user_id: str):
    """Print statistics about labeled participants for a user."""
    loader = DataLoader()
    stats = loader.get_participant_stats(user_id)

    print(f"\n=== Participant Statistics for User {user_id} ===\n")

    if not stats:
        print("No labeled participants found.")
        return

    # Sort by total duration
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]["total_duration_s"], reverse=True)

    for pid, s in sorted_stats:
        duration_min = s["total_duration_s"] / 60
        print(f"{s['display_name']} ({pid[:8]}...):")
        print(f"  Meetings: {s['meeting_count']}")
        print(f"  Segments: {s['segment_count']}")
        print(f"  Total duration: {duration_min:.1f} minutes")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="QuickScribe Data Loader")
    parser.add_argument("--user-id", required=True, help="User ID to query")
    parser.add_argument("--stats", action="store_true", help="Show participant statistics")

    args = parser.parse_args()

    if args.stats:
        print_participant_stats(args.user_id)
    else:
        loader = DataLoader()
        labeled = loader.get_labeled_meetings(args.user_id)
        unlabeled = loader.get_unlabeled_meetings(args.user_id)

        print(f"\nSummary:")
        print(f"  Labeled meetings: {len(labeled)}")
        print(f"  Unlabeled meetings: {len(unlabeled)}")
