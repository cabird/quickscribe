"""
ECAPA-TDNN Speaker Embedding Module

Uses SpeechBrain's pretrained ECAPA-TDNN model to extract speaker embeddings
from audio segments. These embeddings can be used for cross-meeting speaker
identification.

Usage:
    embedder = EcapaEmbedder()
    embedding = embedder.embedding_for_segment("audio.wav", start_s=10.0, end_s=18.0)
"""

from __future__ import annotations

import json
import os
from typing import Optional, Tuple, List
from dataclasses import dataclass, field

import numpy as np
import torch
import torchaudio

# SpeechBrain ECAPA-TDNN model
from speechbrain.inference.speaker import EncoderClassifier


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a_norm = a / (np.linalg.norm(a) + 1e-12)
    b_norm = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a_norm, b_norm))


def l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2 normalize a vector."""
    return v / (np.linalg.norm(v) + 1e-12)


@dataclass
class SpeakerProfile:
    """
    Represents a speaker's voice profile built from multiple audio samples.

    The centroid is the mean of all L2-normalized embeddings, which provides
    a robust representation that improves with more samples.
    """
    participant_id: str
    display_name: str

    # L2-normalized centroid embedding for fast matching
    centroid: Optional[np.ndarray] = None

    # Number of samples used to build this profile
    n_samples: int = 0

    # Store embeddings for potential recalibration (bounded list)
    embeddings: List[np.ndarray] = field(default_factory=list)

    # Track which recordings contributed to this profile
    recording_ids: List[str] = field(default_factory=list)

    # Statistics for confidence estimation
    embedding_std: Optional[float] = None  # Standard deviation of embeddings from centroid

    def update(self, new_embs: List[np.ndarray], recording_id: Optional[str] = None,
               keep_max: int = 500) -> None:
        """
        Update the speaker profile with new embeddings.

        Args:
            new_embs: List of new embedding vectors to add
            recording_id: Optional recording ID for tracking provenance
            keep_max: Maximum number of embeddings to retain
        """
        if not new_embs:
            return

        # Track recording source
        if recording_id and recording_id not in self.recording_ids:
            self.recording_ids.append(recording_id)

        # Add new embeddings (normalized)
        for e in new_embs:
            self.embeddings.append(l2_normalize(e))

        # Trim if exceeding limit (keep most recent)
        if len(self.embeddings) > keep_max:
            self.embeddings = self.embeddings[-keep_max:]

        # Recompute centroid
        mat = np.stack(self.embeddings, axis=0)
        centroid = mat.mean(axis=0)
        self.centroid = l2_normalize(centroid)
        self.n_samples = len(self.embeddings)

        # Compute standard deviation for confidence estimation
        if len(self.embeddings) > 1:
            distances = [1.0 - cosine_similarity(e, self.centroid) for e in self.embeddings]
            self.embedding_std = float(np.std(distances))

    def similarity_to(self, embedding: np.ndarray) -> float:
        """Compute cosine similarity between this profile and an embedding."""
        if self.centroid is None:
            return -1.0
        return cosine_similarity(l2_normalize(embedding), self.centroid)

    def to_dict(self) -> dict:
        """Serialize profile to dictionary for storage."""
        return {
            "participant_id": self.participant_id,
            "display_name": self.display_name,
            "centroid": self.centroid.tolist() if self.centroid is not None else None,
            "n_samples": self.n_samples,
            "recording_ids": self.recording_ids,
            "embedding_std": self.embedding_std,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerProfile":
        """Deserialize profile from dictionary."""
        profile = cls(
            participant_id=data["participant_id"],
            display_name=data["display_name"],
        )
        if data.get("centroid"):
            profile.centroid = np.array(data["centroid"], dtype=np.float32)
        profile.n_samples = data.get("n_samples", 0)
        profile.recording_ids = data.get("recording_ids", [])
        profile.embedding_std = data.get("embedding_std")
        return profile


class SpeakerProfileDB:
    """
    In-memory database of speaker profiles.
    Can be persisted to/from JSON for reuse.
    """

    def __init__(self):
        self.profiles: dict[str, SpeakerProfile] = {}

    def get_or_create(self, participant_id: str, display_name: str = "") -> SpeakerProfile:
        """Get existing profile or create new one."""
        if participant_id not in self.profiles:
            self.profiles[participant_id] = SpeakerProfile(
                participant_id=participant_id,
                display_name=display_name or participant_id,
            )
        return self.profiles[participant_id]

    def get(self, participant_id: str) -> Optional[SpeakerProfile]:
        """Get profile by participant ID."""
        return self.profiles.get(participant_id)

    def all_profiles(self) -> List[SpeakerProfile]:
        """Get all profiles."""
        return list(self.profiles.values())

    def match(self, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Find the best matching speaker profile for an embedding.

        Returns:
            Tuple of (participant_id, similarity_score) or (None, -1.0)
        """
        if not self.profiles:
            return None, -1.0

        embedding_norm = l2_normalize(embedding)
        best_id, best_sim = None, -1.0

        for pid, profile in self.profiles.items():
            if profile.centroid is None:
                continue
            sim = cosine_similarity(embedding_norm, profile.centroid)
            if sim > best_sim:
                best_sim = sim
                best_id = pid

        return best_id, best_sim

    def match_with_confidence(self, embedding: np.ndarray,
                              high_threshold: float = 0.78,
                              low_threshold: float = 0.68) -> dict:
        """
        Match embedding with confidence bands.

        Returns:
            Dict with keys: status, participant_id, similarity, display_name
            status: "auto" (high confidence), "suggest" (medium), "unknown" (low)
        """
        best_id, best_sim = self.match(embedding)

        if best_id is None:
            return {
                "status": "unknown",
                "participant_id": None,
                "similarity": None,
                "display_name": None,
            }

        profile = self.profiles[best_id]

        if best_sim >= high_threshold:
            status = "auto"
        elif best_sim >= low_threshold:
            status = "suggest"
        else:
            status = "unknown"
            best_id = None

        return {
            "status": status,
            "participant_id": best_id,
            "similarity": float(best_sim),
            "display_name": profile.display_name if best_id else None,
        }

    def to_dict(self) -> dict:
        """Serialize database to dictionary."""
        return {
            "profiles": {pid: p.to_dict() for pid, p in self.profiles.items()}
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerProfileDB":
        """Deserialize database from dictionary."""
        db = cls()
        for pid, pdata in data.get("profiles", {}).items():
            db.profiles[pid] = SpeakerProfile.from_dict(pdata)
        return db

    def save_to_file(self, path: str) -> None:
        """Save database to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "SpeakerProfileDB":
        """Load database from JSON file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))


class EcapaEmbedder:
    """
    ECAPA-TDNN speaker embedding extractor.

    Uses SpeechBrain's pretrained model trained on VoxCeleb for robust
    speaker embeddings that work well for cross-meeting identification.
    """

    def __init__(self, device: Optional[str] = None, cache_dir: str = "pretrained_models"):
        """
        Initialize the ECAPA-TDNN embedder.

        Args:
            device: "cuda" or "cpu". Auto-detects if None.
            cache_dir: Directory to cache the pretrained model.
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_dir = cache_dir

        print(f"Loading ECAPA-TDNN model on {self.device}...")
        self.model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=os.path.join(cache_dir, "spkrec-ecapa-voxceleb"),
            run_opts={"device": self.device},
        )
        print("Model loaded successfully.")

    def load_audio_mono_16k(self, path: str) -> Tuple[torch.Tensor, int]:
        """
        Load audio file as mono 16kHz waveform.

        Args:
            path: Path to audio file

        Returns:
            Tuple of (waveform tensor [1, T], sample_rate)
        """
        wav, sr = torchaudio.load(path)

        # Convert to mono if stereo
        if wav.size(0) > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)

        # Resample to 16kHz if needed
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
            sr = 16000

        return wav, sr

    def slice_audio(self, wav: torch.Tensor, sr: int,
                    start_s: float, end_s: float) -> torch.Tensor:
        """
        Extract a time slice from waveform.

        Args:
            wav: Waveform tensor [1, T]
            sr: Sample rate
            start_s: Start time in seconds
            end_s: End time in seconds

        Returns:
            Sliced waveform tensor [1, T']
        """
        start = int(max(0.0, start_s) * sr)
        end = int(max(0.0, end_s) * sr)
        end = max(end, start + 1)  # Ensure at least 1 sample
        return wav[:, start:end]

    @torch.inference_mode()
    def embedding_from_waveform(self, wav_16k_mono: torch.Tensor) -> np.ndarray:
        """
        Extract speaker embedding from waveform.

        Args:
            wav_16k_mono: Waveform tensor [1, T] at 16kHz

        Returns:
            1D numpy embedding vector (typically 192 dimensions)
        """
        sig = wav_16k_mono.squeeze(0)  # [T]
        emb = self.model.encode_batch(sig.unsqueeze(0))  # [1, 1, D] or [1, D]
        emb = emb.squeeze().detach().cpu().numpy()
        return emb.astype(np.float32)

    def embedding_for_segment(self, audio_path: str, start_s: float, end_s: float,
                              min_dur_s: float = 1.8, max_dur_s: float = 8.0) -> Optional[np.ndarray]:
        """
        Extract speaker embedding for a diarized segment.

        Best practice: use 2-8 second segments for optimal embeddings.
        Very short segments (<1.8s) produce noisy embeddings.
        Very long segments are windowed to the center.

        Args:
            audio_path: Path to audio file
            start_s: Start time in seconds
            end_s: End time in seconds
            min_dur_s: Minimum duration threshold (returns None if shorter)
            max_dur_s: Maximum duration (longer segments are windowed)

        Returns:
            Embedding vector or None if segment too short
        """
        dur = end_s - start_s
        if dur < min_dur_s:
            return None

        wav, sr = self.load_audio_mono_16k(audio_path)

        # Window long segments to center
        if dur > max_dur_s:
            mid = (start_s + end_s) / 2.0
            start_s = mid - max_dur_s / 2.0
            end_s = mid + max_dur_s / 2.0

        seg = self.slice_audio(wav, sr, start_s, end_s)

        # Check if too short after slicing
        if seg.shape[1] < int(min_dur_s * sr):
            return None

        return self.embedding_from_waveform(seg)

    def embeddings_for_segments(self, audio_path: str,
                                segments: List[Tuple[float, float]],
                                min_dur_s: float = 1.8,
                                max_dur_s: float = 8.0) -> List[Optional[np.ndarray]]:
        """
        Extract embeddings for multiple segments from the same audio file.
        More efficient than calling embedding_for_segment repeatedly.

        Args:
            audio_path: Path to audio file
            segments: List of (start_s, end_s) tuples
            min_dur_s: Minimum duration threshold
            max_dur_s: Maximum duration for windowing

        Returns:
            List of embeddings (None for segments that are too short)
        """
        if not segments:
            return []

        # Load audio once
        wav, sr = self.load_audio_mono_16k(audio_path)

        embeddings = []
        for start_s, end_s in segments:
            dur = end_s - start_s
            if dur < min_dur_s:
                embeddings.append(None)
                continue

            # Window long segments
            if dur > max_dur_s:
                mid = (start_s + end_s) / 2.0
                start_s = mid - max_dur_s / 2.0
                end_s = mid + max_dur_s / 2.0

            seg = self.slice_audio(wav, sr, start_s, end_s)

            if seg.shape[1] < int(min_dur_s * sr):
                embeddings.append(None)
                continue

            emb = self.embedding_from_waveform(seg)
            embeddings.append(emb)

        return embeddings


# Convenience functions for common operations

def build_meeting_speaker_centroids(embedder: EcapaEmbedder, audio_path: str,
                                    diarization: List[Tuple[float, float, str]]) -> dict[str, np.ndarray]:
    """
    Build per-speaker centroids for a single meeting.

    Args:
        embedder: EcapaEmbedder instance
        audio_path: Path to audio file
        diarization: List of (start_s, end_s, speaker_label) tuples

    Returns:
        Dict mapping speaker_label to centroid embedding
    """
    local_to_embs: dict[str, List[np.ndarray]] = {}

    for start_s, end_s, spk in diarization:
        emb = embedder.embedding_for_segment(audio_path, start_s, end_s)
        if emb is None:
            continue
        local_to_embs.setdefault(spk, []).append(l2_normalize(emb))

    centroids: dict[str, np.ndarray] = {}
    for spk, embs in local_to_embs.items():
        mat = np.stack(embs, axis=0)
        centroids[spk] = l2_normalize(mat.mean(axis=0))

    return centroids


def merge_adjacent_segments(diarization: List[Tuple[float, float, str]],
                           max_gap_s: float = 0.35,
                           min_keep_s: float = 0.6) -> List[Tuple[float, float, str]]:
    """
    Merge consecutive segments for the same speaker if gap is small.
    This creates better embedding windows from rapid turn-taking.

    Args:
        diarization: List of (start_s, end_s, speaker_label) tuples
        max_gap_s: Maximum gap between segments to merge
        min_keep_s: Minimum duration to keep a segment

    Returns:
        Merged diarization list
    """
    if not diarization:
        return diarization

    # Sort by start time
    sorted_diar = sorted(diarization, key=lambda x: x[0])

    merged: List[Tuple[float, float, str]] = []
    cur_s, cur_e, cur_spk = sorted_diar[0]

    for s, e, spk in sorted_diar[1:]:
        if spk == cur_spk and (s - cur_e) <= max_gap_s:
            cur_e = max(cur_e, e)
        else:
            if (cur_e - cur_s) >= min_keep_s:
                merged.append((cur_s, cur_e, cur_spk))
            cur_s, cur_e, cur_spk = s, e, spk

    if (cur_e - cur_s) >= min_keep_s:
        merged.append((cur_s, cur_e, cur_spk))

    return merged
