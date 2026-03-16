"""
Speaker Processor

Core identification logic: processes a single recording's speakers,
matches against profiles, and writes results to speaker_mapping.
"""
import json
import tempfile
import os
import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional, Tuple

import numpy as np

from shared_quickscribe_py.cosmos import Recording, Transcription
from shared_quickscribe_py.cosmos.models import SpeakerMapping, TopCandidate
from shared_quickscribe_py.azure_services import BlobStorageClient
from shared_quickscribe_py.speaker_profiles import SpeakerProfileDB

from embedding_engine import EmbeddingEngine, merge_adjacent_segments, l2_normalize
from logging_handler import JobLogger

logger = logging.getLogger(__name__)

# Confidence thresholds
AUTO_THRESHOLD = 0.78
SUGGEST_THRESHOLD = 0.68
MIN_CANDIDATE_THRESHOLD = 0.40  # Minimum for showing in top candidates


class SpeakerProcessor:
    """
    Processes speaker identification for a single recording.
    """

    def __init__(self, engine: EmbeddingEngine, blob_client: BlobStorageClient):
        self.engine = engine
        self.blob_client = blob_client

    def process_recording(self, recording: Recording, transcription: Transcription,
                          profile_db: SpeakerProfileDB,
                          job_logger: JobLogger) -> Dict[str, dict]:
        """
        Process speaker identification for a single recording.

        Args:
            recording: Recording to process
            transcription: Corresponding transcription with diarized segments
            profile_db: User's speaker profile database
            job_logger: Logger for job tracking

        Returns:
            Dict mapping speaker_label to identification result dict,
            each containing: status, participantId, similarity, topCandidates, embedding
        """
        recording_id = recording.id
        job_logger.info(f"Processing speaker identification for recording {recording_id}", recording_id)

        # Parse diarization segments from transcript_json
        diarization = self._parse_diarization(transcription, job_logger, recording_id)
        if not diarization:
            job_logger.warning(f"No diarization segments found for recording {recording_id}", recording_id)
            return {}

        # Merge adjacent segments for better embeddings
        diarization = merge_adjacent_segments(diarization)
        job_logger.info(f"Merged to {len(diarization)} segments", recording_id)

        # Get existing speaker mapping to determine which speakers to skip
        existing_mapping = transcription.speaker_mapping or {}
        skip_speakers = set()
        needs_embedding_only = set()  # Verified + useForTraining but missing embedding
        for label, data in (existing_mapping or {}).items():
            if hasattr(data, 'model_dump'):
                ex = data.model_dump()
            elif isinstance(data, dict):
                ex = data
            else:
                ex = {}
            if ex.get('identificationStatus') == 'dismissed':
                skip_speakers.add(label)
            elif ex.get('manuallyVerified'):
                # If training requested but no embedding, we need to extract one
                if ex.get('useForTraining') and not ex.get('embedding'):
                    needs_embedding_only.add(label)
                    job_logger.info(f"Need embedding for {label} (training requested, no embedding)", recording_id)
                else:
                    skip_speakers.add(label)

        if skip_speakers:
            job_logger.info(f"Skipping (verified/dismissed): {skip_speakers}", recording_id)

        # Check if all speakers are already handled
        all_speakers = set(s for _, _, s in diarization)
        active_speakers = all_speakers - skip_speakers  # includes needs_embedding_only
        if not active_speakers:
            job_logger.info(f"All speakers verified/dismissed, nothing to do", recording_id)
            return {}

        # Select top N longest segments per speaker (skip verified/dismissed, but keep needs_embedding_only)
        MAX_SEGMENTS_PER_SPEAKER = 15
        MIN_DURATION = 2.0
        EDGE_TRIM = 3.0
        TRIM_THRESHOLD = 10.0

        speaker_segments: dict[str, list] = {}
        for start_s, end_s, spk in diarization:
            if spk in skip_speakers:
                continue
            dur = end_s - start_s
            if dur >= MIN_DURATION:
                speaker_segments.setdefault(spk, []).append((start_s, end_s))

        selected_segments = []
        selected_labels = []
        for spk, segs in speaker_segments.items():
            segs.sort(key=lambda x: x[1] - x[0], reverse=True)
            top = segs[:MAX_SEGMENTS_PER_SPEAKER]
            selected_segments.extend(top)
            selected_labels.extend([spk] * len(top))

        total_valid = sum(len(s) for s in speaker_segments.values())
        job_logger.info(
            f"Selected {len(selected_segments)} best segments "
            f"(of {total_valid} valid, from {len(diarization)} total)",
            recording_id
        )

        # Download audio to temp file
        audio_path = self._download_audio(recording, job_logger)
        if not audio_path:
            return {}

        try:
            # Extract embeddings from selected segments only
            wav, sr = self.engine.load_audio_mono_16k(audio_path)
            local_embs: dict[str, list] = {}

            for (start_s, end_s), spk in zip(selected_segments, selected_labels):
                dur = end_s - start_s
                # Trim edges on long segments to avoid crosstalk/boundary issues
                if dur >= TRIM_THRESHOLD:
                    start_s += EDGE_TRIM
                    end_s -= EDGE_TRIM
                    dur = end_s - start_s
                # Window to center 10s
                if dur > 10.0:
                    mid = (start_s + end_s) / 2.0
                    start_s = mid - 5.0
                    end_s = mid + 5.0
                seg = self.engine.slice_audio(wav, sr, start_s, end_s)
                if seg.shape[1] < int(MIN_DURATION * sr):
                    continue
                emb = self.engine.embedding_from_waveform(seg)
                local_embs.setdefault(spk, []).append(l2_normalize(emb))

            centroids = {}
            for spk, embs in local_embs.items():
                mat = np.stack(embs, axis=0)
                centroids[spk] = l2_normalize(mat.mean(axis=0))

            job_logger.info(f"Built centroids for {len(centroids)} speakers", recording_id)

            # Match each speaker against profiles
            results = {}
            auto_matches = {}  # Track auto matches to detect duplicates

            for speaker_label, centroid in centroids.items():

                # For speakers that just need embedding (verified + training requested)
                if speaker_label in needs_embedding_only:
                    results[speaker_label] = {
                        "status": "embedding_only",
                        "participant_id": None,
                        "similarity": None,
                        "top_candidates": [],
                        "embedding": centroid.tolist(),
                    }
                    job_logger.info(f"  {speaker_label}: extracted embedding for training", recording_id)
                    continue

                # Match against profiles
                match = profile_db.match_with_confidence(
                    centroid,
                    high_threshold=AUTO_THRESHOLD,
                    low_threshold=SUGGEST_THRESHOLD,
                )

                # Filter top candidates below minimum threshold
                top_candidates = [
                    c for c in match["top_candidates"]
                    if c["similarity"] >= MIN_CANDIDATE_THRESHOLD
                ]

                result = {
                    "status": match["status"],
                    "participant_id": match["participant_id"],
                    "similarity": match["similarity"],
                    "top_candidates": top_candidates,
                    "embedding": centroid.tolist(),
                }

                # Track auto matches for duplicate detection
                if match["status"] == "auto" and match["participant_id"]:
                    pid = match["participant_id"]
                    if pid in auto_matches:
                        # Duplicate auto-match: demote the lower confidence one
                        prev_label = auto_matches[pid]
                        prev_sim = results[prev_label]["similarity"]
                        curr_sim = match["similarity"]

                        if curr_sim > prev_sim:
                            # Demote previous match
                            results[prev_label]["status"] = "suggest"
                            job_logger.info(
                                f"Duplicate auto-match for {pid}: keeping {speaker_label} "
                                f"({curr_sim:.3f}), demoting {prev_label} ({prev_sim:.3f})",
                                recording_id
                            )
                            auto_matches[pid] = speaker_label
                        else:
                            # Demote current match
                            result["status"] = "suggest"
                            job_logger.info(
                                f"Duplicate auto-match for {pid}: keeping {prev_label} "
                                f"({prev_sim:.3f}), demoting {speaker_label} ({curr_sim:.3f})",
                                recording_id
                            )
                    else:
                        auto_matches[pid] = speaker_label

                results[speaker_label] = result
                job_logger.info(
                    f"  {speaker_label}: {result['status']} "
                    f"(sim={result['similarity']:.3f if result['similarity'] else 'N/A'}, "
                    f"pid={result['participant_id'] or 'none'})",
                    recording_id
                )

            return results

        finally:
            # Clean up temp audio file
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    def _parse_diarization(self, transcription: Transcription,
                           job_logger: JobLogger,
                           recording_id: str) -> List[Tuple[float, float, str]]:
        """Parse diarization segments from transcript_json."""
        if not transcription.transcript_json:
            return []

        try:
            transcript_data = json.loads(transcription.transcript_json)
        except (json.JSONDecodeError, TypeError):
            job_logger.warning(f"Failed to parse transcript_json for {recording_id}", recording_id)
            return []

        segments = []

        # Handle Azure Speech Services format
        if isinstance(transcript_data, dict):
            # Try recognizedPhrases format
            phrases = transcript_data.get("recognizedPhrases", [])
            for phrase in phrases:
                speaker = phrase.get("speaker", 0)
                offset = phrase.get("offsetInTicks", 0) / 10_000_000  # ticks to seconds
                duration = phrase.get("durationInTicks", 0) / 10_000_000
                segments.append((offset, offset + duration, f"Speaker {speaker}"))
        elif isinstance(transcript_data, list):
            # List of segment objects
            for seg in transcript_data:
                if isinstance(seg, dict):
                    start = seg.get("start", seg.get("offset", 0))
                    end = seg.get("end", start + seg.get("duration", 0))
                    speaker = seg.get("speaker", seg.get("speakerLabel", "Speaker 0"))
                    if isinstance(speaker, int):
                        speaker = f"Speaker {speaker}"
                    segments.append((float(start), float(end), speaker))

        return segments

    def _download_audio(self, recording: Recording,
                        job_logger: JobLogger) -> Optional[str]:
        """Download recording audio to a temp file. Tries user-prefixed path first."""
        try:
            suffix = os.path.splitext(recording.unique_filename)[1] or ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.close()

            # Try user-prefixed path first (newer convention), then bare filename (older)
            candidate_paths = [
                f"{recording.user_id}/{recording.unique_filename}",
                recording.unique_filename,
            ]
            for blob_path in candidate_paths:
                try:
                    self.blob_client.download_file(blob_path, tmp.name)
                    job_logger.info(f"Downloaded audio: {blob_path}", recording.id)
                    return tmp.name
                except Exception:
                    continue

            job_logger.error(f"Audio blob not found for {recording.id} (tried both paths)", recording.id)
            os.remove(tmp.name)
            return None

        except Exception as e:
            job_logger.error(f"Failed to download audio for {recording.id}: {e}", recording.id)
            return None
