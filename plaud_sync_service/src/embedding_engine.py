"""
ECAPA-TDNN Speaker Embedding Engine

Wraps EcapaEmbedder from the diarization experiment for use in the
speaker identification service.
"""
from __future__ import annotations

import json
import os
from typing import Optional, Tuple, List

import numpy as np
import torch
import torchaudio
from speechbrain.inference.speaker import EncoderClassifier


def l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2 normalize a vector."""
    return v / (np.linalg.norm(v) + 1e-12)


class EmbeddingEngine:
    """
    ECAPA-TDNN speaker embedding extractor.

    Uses SpeechBrain's pretrained model trained on VoxCeleb for robust
    speaker embeddings for cross-meeting identification.
    """

    def __init__(self, device: Optional[str] = None, cache_dir: str = "/app/pretrained_models"):
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
        """Load audio file as mono 16kHz waveform."""
        wav, sr = torchaudio.load(path)
        if wav.size(0) > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
            sr = 16000
        return wav, sr

    def slice_audio(self, wav: torch.Tensor, sr: int,
                    start_s: float, end_s: float) -> torch.Tensor:
        """Extract a time slice from waveform."""
        start = int(max(0.0, start_s) * sr)
        end = int(max(0.0, end_s) * sr)
        end = max(end, start + 1)
        return wav[:, start:end]

    @torch.inference_mode()
    def embedding_from_waveform(self, wav_16k_mono: torch.Tensor) -> np.ndarray:
        """Extract speaker embedding from waveform."""
        sig = wav_16k_mono.squeeze(0)
        emb = self.model.encode_batch(sig.unsqueeze(0))
        emb = emb.squeeze().detach().cpu().numpy()
        return emb.astype(np.float32)

    def embeddings_for_segments(self, audio_path: str,
                                segments: List[Tuple[float, float]],
                                min_dur_s: float = 1.8,
                                max_dur_s: float = 8.0) -> List[Optional[np.ndarray]]:
        """
        Extract embeddings for multiple segments from the same audio file.
        Loads audio once for efficiency.

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

        wav, sr = self.load_audio_mono_16k(audio_path)

        embeddings = []
        for start_s, end_s in segments:
            dur = end_s - start_s
            if dur < min_dur_s:
                embeddings.append(None)
                continue

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

    def build_speaker_centroids(self, audio_path: str,
                                 diarization: List[Tuple[float, float, str]]) -> dict[str, np.ndarray]:
        """
        Build per-speaker centroids for a single meeting.

        Args:
            audio_path: Path to audio file
            diarization: List of (start_s, end_s, speaker_label) tuples

        Returns:
            Dict mapping speaker_label to centroid embedding
        """
        local_to_embs: dict[str, List[np.ndarray]] = {}

        segments = [(s, e) for s, e, _ in diarization]
        labels = [spk for _, _, spk in diarization]

        embeddings = self.embeddings_for_segments(audio_path, segments)

        for emb, spk in zip(embeddings, labels):
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
    Creates better embedding windows from rapid turn-taking.
    """
    if not diarization:
        return diarization

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
