"""ECAPA-TDNN Speaker Embedding Engine.

Lazy-loads the SpeechBrain ECAPA-TDNN model on first use to avoid ~800MB
import cost at startup. All operations are synchronous and meant to be
called via asyncio.to_thread().
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import torch

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once, stays in memory
_engine: EmbeddingEngine | None = None


def l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2 normalize a vector."""
    return v / (np.linalg.norm(v) + 1e-12)


def get_engine(model_path: str | None = None) -> EmbeddingEngine:
    """Get or create the singleton EmbeddingEngine instance.

    The model is loaded on first call and kept in memory for the process lifetime.
    """
    global _engine
    if _engine is None:
        _engine = EmbeddingEngine(model_path=model_path)
    return _engine


class EmbeddingEngine:
    """ECAPA-TDNN speaker embedding extractor.

    Uses SpeechBrain's pretrained model trained on VoxCeleb to produce
    192-dimensional speaker embeddings.
    """

    def __init__(self, model_path: str | None = None):
        self._model = None
        self._model_path = model_path or "/app/pretrained_models/spkrec-ecapa-voxceleb"

    def _load_model(self):
        """Check that speaker-id dependencies are available."""
        try:
            import torch  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Speaker identification requires PyTorch. "
                "Install with: pip install quickscribe-v2[speaker-id]"
            )

    def _ensure_model(self):
        """Lazy-load the SpeechBrain model on first use."""
        if self._model is not None:
            return

        self._load_model()

        import torch  # noqa: F811
        from speechbrain.inference.speaker import EncoderClassifier

        logger.info("Loading ECAPA-TDNN model from %s (CPU)...", self._model_path)
        self._model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=self._model_path,
            run_opts={"device": "cpu"},
        )
        logger.info("ECAPA-TDNN model loaded successfully.")

    def load_audio_mono_16k(self, path: str) -> tuple["torch.Tensor", int]:
        """Load audio file as mono 16kHz waveform.

        MP3 files are converted to WAV via ffmpeg since torchaudio may not
        have an MP3 backend in CPU-only builds.
        """
        import torch
        import torchaudio

        if path.lower().endswith(".mp3"):
            wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav_tmp.close()
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", path, "-ar", "16000", "-ac", "1", wav_tmp.name],
                    capture_output=True,
                    check=True,
                    timeout=120,
                )
                wav, sr = torchaudio.load(wav_tmp.name)
                return wav, sr
            finally:
                if os.path.exists(wav_tmp.name):
                    os.remove(wav_tmp.name)

        wav, sr = torchaudio.load(path)
        if wav.size(0) > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)
        if sr != 16000:
            wav = torchaudio.functional.resample(wav, sr, 16000)
            sr = 16000
        return wav, sr

    def slice_audio(
        self, wav: "torch.Tensor", sr: int, start_s: float, end_s: float
    ) -> "torch.Tensor":
        """Extract a time slice from a waveform tensor."""
        start = int(max(0.0, start_s) * sr)
        end = int(max(0.0, end_s) * sr)
        end = max(end, start + 1)
        return wav[:, start:end]

    def embedding_from_waveform(self, wav_16k_mono: "torch.Tensor") -> np.ndarray:
        """Extract a 192-dim speaker embedding from a waveform.

        Returns:
            numpy float32 array of shape (192,).
        """
        import torch

        self._ensure_model()

        with torch.inference_mode():
            sig = wav_16k_mono.squeeze(0)
            emb = self._model.encode_batch(sig.unsqueeze(0))
            emb = emb.squeeze().detach().cpu().numpy()
            return emb.astype(np.float32)

    def embeddings_for_segments(
        self,
        audio_path: str,
        segments: list[tuple[float, float]],
        min_dur_s: float = 1.8,
        max_dur_s: float = 8.0,
    ) -> list[np.ndarray | None]:
        """Extract embeddings for multiple time segments from one audio file.

        Loads audio once for efficiency.

        Args:
            audio_path: Path to audio file.
            segments: List of (start_s, end_s) tuples.
            min_dur_s: Minimum segment duration to process.
            max_dur_s: Maximum duration; longer segments are center-windowed.

        Returns:
            List of embeddings (None for segments too short).
        """
        if not segments:
            return []

        wav, sr = self.load_audio_mono_16k(audio_path)
        embeddings: list[np.ndarray | None] = []

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


def merge_adjacent_segments(
    diarization: list[tuple[float, float, str]],
    gap_threshold: float = 0.35,
    min_keep_s: float = 0.6,
) -> list[tuple[float, float, str]]:
    """Merge consecutive same-speaker segments with small gaps.

    Args:
        diarization: List of (start_s, end_s, speaker_label) tuples.
        gap_threshold: Maximum gap between segments to merge.
        min_keep_s: Minimum segment duration to keep after merging.

    Returns:
        Merged list of (start_s, end_s, speaker_label) tuples.
    """
    if not diarization:
        return diarization

    sorted_diar = sorted(diarization, key=lambda x: x[0])
    merged: list[tuple[float, float, str]] = []
    cur_s, cur_e, cur_spk = sorted_diar[0]

    for s, e, spk in sorted_diar[1:]:
        if spk == cur_spk and (s - cur_e) <= gap_threshold:
            cur_e = max(cur_e, e)
        else:
            if (cur_e - cur_s) >= min_keep_s:
                merged.append((cur_s, cur_e, cur_spk))
            cur_s, cur_e, cur_spk = s, e, spk

    if (cur_e - cur_s) >= min_keep_s:
        merged.append((cur_s, cur_e, cur_spk))

    return merged
