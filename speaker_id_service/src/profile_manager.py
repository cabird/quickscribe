"""
Profile Manager

Handles loading and saving speaker profiles via the shared SpeakerProfileStore.
Provides convenience methods used by the speaker processor.
"""
import logging
from typing import Optional

import numpy as np

from shared_quickscribe_py.speaker_profiles import SpeakerProfileDB, SpeakerProfileStore

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Manages speaker profile loading/saving/matching for the identification worker.
    """

    def __init__(self, storage_connection_string: str):
        self.store = SpeakerProfileStore(storage_connection_string)

    def load_profiles(self, user_id: str) -> SpeakerProfileDB:
        """Load speaker profiles for a user."""
        return self.store.load_profiles(user_id)

    def save_profiles(self, user_id: str, db: SpeakerProfileDB) -> None:
        """Save speaker profiles for a user."""
        self.store.save_profiles(user_id, db)

    def update_profile(self, user_id: str, participant_id: str,
                       embedding: np.ndarray, recording_id: Optional[str] = None,
                       display_name: str = "") -> None:
        """Update a single speaker profile with a new embedding."""
        self.store.update_profile(
            user_id, participant_id, embedding,
            recording_id=recording_id, display_name=display_name
        )
