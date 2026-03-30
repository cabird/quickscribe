"""Bootstrap speaker profiles from existing verified speaker_mapping data.

One-time migration helper: scans all recordings for a user, extracts
embeddings from speaker_mapping entries where manuallyVerified is True,
and builds initial profiles in the speaker_profiles table.
"""

from __future__ import annotations

import logging

from app.services import profile_store

logger = logging.getLogger(__name__)


async def bootstrap_profiles_from_mappings(user_id: str) -> int:
    """Build speaker profiles from verified speaker_mapping embeddings.

    This is a thin wrapper around profile_store.rebuild_all_profiles.
    It scans all recordings for the user, collects embeddings from manually
    verified speaker_mapping entries, and builds profiles.

    Args:
        user_id: The user to bootstrap profiles for.

    Returns:
        Number of profiles created.
    """
    logger.info("Bootstrapping speaker profiles for user %s", user_id)
    count = await profile_store.rebuild_all_profiles(user_id)
    logger.info("Bootstrap complete: %d profiles created for user %s", count, user_id)
    return count
