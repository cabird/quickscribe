"""
Speaker Profile Storage

Wraps Azure Blob Storage for per-user speaker voice profiles.
Adapted from diarization_experiment/speaker_embedder.py.

Each user gets one blob: speaker-profiles/{userId}/profiles.json
containing their SpeakerProfileDB serialized as JSON (~1.5KB per profile).
"""
import json
import logging
from typing import Optional, List, Tuple

import numpy as np

from shared_quickscribe_py.azure_services import BlobStorageClient

logger = logging.getLogger(__name__)

PROFILES_CONTAINER = "speaker-profiles"


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a_norm = a / (np.linalg.norm(a) + 1e-12)
    b_norm = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a_norm, b_norm))


def l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2 normalize a vector."""
    return v / (np.linalg.norm(v) + 1e-12)


class SpeakerProfile:
    """
    Represents a speaker's voice profile built from multiple audio samples.

    The centroid is the mean of all L2-normalized embeddings, providing
    a robust representation that improves with more samples.
    """

    def __init__(self, participant_id: str, display_name: str = ""):
        self.participant_id = participant_id
        self.display_name = display_name
        self.centroid: Optional[np.ndarray] = None
        self.n_samples: int = 0
        self.embeddings: List[np.ndarray] = []
        self.recording_ids: List[str] = []
        self.embedding_std: Optional[float] = None

    def update(self, new_embs: List[np.ndarray], recording_id: Optional[str] = None,
               keep_max: int = 500) -> None:
        """Update the speaker profile with new embeddings."""
        if not new_embs:
            return

        if recording_id and recording_id not in self.recording_ids:
            self.recording_ids.append(recording_id)

        for e in new_embs:
            self.embeddings.append(l2_normalize(e))

        if len(self.embeddings) > keep_max:
            self.embeddings = self.embeddings[-keep_max:]

        mat = np.stack(self.embeddings, axis=0)
        centroid = mat.mean(axis=0)
        self.centroid = l2_normalize(centroid)
        self.n_samples = len(self.embeddings)

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
            display_name=data.get("display_name", ""),
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
    Can be persisted to/from JSON via SpeakerProfileStore.
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

    def match_top_n(self, embedding: np.ndarray, n: int = 5) -> List[dict]:
        """
        Find the top N matching profiles for an embedding.

        Returns:
            List of dicts with keys: participantId, displayName, similarity
            Sorted by similarity descending.
        """
        if not self.profiles:
            return []

        embedding_norm = l2_normalize(embedding)
        results = []

        for pid, profile in self.profiles.items():
            if profile.centroid is None:
                continue
            sim = cosine_similarity(embedding_norm, profile.centroid)
            results.append({
                "participantId": pid,
                "displayName": profile.display_name,
                "similarity": round(sim, 4),
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:n]

    def match_with_confidence(self, embedding: np.ndarray,
                              high_threshold: float = 0.78,
                              low_threshold: float = 0.68,
                              top_n: int = 5) -> dict:
        """
        Match embedding with confidence bands and top N candidates.

        Returns:
            Dict with keys: status, participant_id, similarity, display_name, top_candidates
            status: "auto" (high confidence), "suggest" (medium), "unknown" (low)
        """
        top_candidates = self.match_top_n(embedding, n=top_n)

        if not top_candidates:
            return {
                "status": "unknown",
                "participant_id": None,
                "similarity": None,
                "display_name": None,
                "top_candidates": [],
            }

        best = top_candidates[0]
        best_sim = best["similarity"]
        best_id = best["participantId"]

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
            "similarity": best_sim,
            "display_name": best["displayName"] if best_id else None,
            "top_candidates": top_candidates,
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


class SpeakerProfileStore:
    """
    Azure Blob Storage wrapper for per-user speaker profile databases.

    Each user's profiles are stored as a single JSON blob at:
        speaker-profiles/{userId}/profiles.json
    """

    def __init__(self, connection_string: str, container_name: str = PROFILES_CONTAINER):
        self.blob_client = BlobStorageClient(connection_string, container_name)

    def _blob_path(self, user_id: str) -> str:
        return f"{user_id}/profiles.json"

    def load_profiles(self, user_id: str) -> SpeakerProfileDB:
        """
        Load speaker profiles for a user from blob storage.

        Returns an empty SpeakerProfileDB if no profiles exist yet.
        """
        blob_path = self._blob_path(user_id)

        try:
            if not self.blob_client.blob_exists(blob_path):
                logger.info(f"No existing profiles for user {user_id}, returning empty DB")
                return SpeakerProfileDB()

            # Download to a temp file and parse
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".json", delete=True) as tmp:
                self.blob_client.download_file(blob_path, tmp.name)
                with open(tmp.name, 'r') as f:
                    data = json.load(f)

            db = SpeakerProfileDB.from_dict(data)
            logger.info(f"Loaded {len(db.profiles)} profiles for user {user_id}")
            return db

        except Exception as e:
            logger.error(f"Error loading profiles for user {user_id}: {e}")
            return SpeakerProfileDB()

    def save_profiles(self, user_id: str, db: SpeakerProfileDB) -> None:
        """Save speaker profiles for a user to blob storage."""
        blob_path = self._blob_path(user_id)

        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=True) as tmp:
                json.dump(db.to_dict(), tmp, indent=2)
                tmp.flush()
                self.blob_client.upload_file(tmp.name, blob_path)

            logger.info(f"Saved {len(db.profiles)} profiles for user {user_id}")

        except Exception as e:
            logger.error(f"Error saving profiles for user {user_id}: {e}")
            raise

    def update_profile(self, user_id: str, participant_id: str,
                       embedding: np.ndarray, recording_id: Optional[str] = None,
                       display_name: str = "") -> None:
        """
        Convenience method: load profiles, update one, save back.

        Args:
            user_id: Owner of the profile DB
            participant_id: Participant to update
            embedding: New embedding to add (will be L2-normalized)
            recording_id: Source recording for provenance tracking
            display_name: Display name for the participant
        """
        db = self.load_profiles(user_id)
        profile = db.get_or_create(participant_id, display_name)
        profile.update([embedding], recording_id=recording_id)
        self.save_profiles(user_id, db)
