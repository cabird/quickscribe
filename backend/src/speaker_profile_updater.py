"""
Speaker Profile Updater (Learning Loop)

When a user accepts/verifies a speaker, this module updates the speaker's
voice profile with the stored embedding from speaker_mapping.

Uses numpy-only math — no torch/speechbrain needed in the backend.
"""
import logging
import numpy as np

from shared_quickscribe_py.speaker_profiles import SpeakerProfileStore
from config import config

logger = logging.getLogger(__name__)


def get_profile_store() -> SpeakerProfileStore:
    """Get a SpeakerProfileStore instance using backend config."""
    connection_string = config.AZURE_STORAGE_CONNECTION_STRING
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not configured")
    return SpeakerProfileStore(connection_string)


def update_profile_from_mapping(user_id: str, participant_id: str,
                                 embedding_list: list, recording_id: str = None,
                                 display_name: str = "") -> bool:
    """
    Update a speaker profile with an embedding stored in speaker_mapping.

    This is the learning loop: when a user accepts/verifies a speaker
    identification, the stored centroid embedding is added to the
    participant's voice profile.

    Args:
        user_id: User who owns the profile
        participant_id: Participant being updated
        embedding_list: List of floats (192-dim centroid from speaker_mapping)
        recording_id: Source recording for provenance
        display_name: Display name for the participant

    Returns:
        True if profile was updated successfully
    """
    if not embedding_list:
        logger.warning(f"No embedding provided for profile update (participant {participant_id})")
        return False

    try:
        store = get_profile_store()
        embedding = np.array(embedding_list, dtype=np.float32)
        store.update_profile(
            user_id, participant_id, embedding,
            recording_id=recording_id,
            display_name=display_name
        )
        logger.info(f"Updated speaker profile for participant {participant_id} (user {user_id})")
        return True

    except Exception as e:
        logger.error(f"Failed to update speaker profile for {participant_id}: {e}")
        return False


def rebuild_all_profiles(user_id: str, transcription_handler, recording_handler) -> dict:
    """
    Rebuild all speaker profiles from verified mappings.

    Iterates through all transcriptions for a user, finds speakers with
    manuallyVerified=True and stored embeddings, and rebuilds profiles.

    Args:
        user_id: User whose profiles to rebuild
        transcription_handler: TranscriptionHandler instance
        recording_handler: RecordingHandler instance

    Returns:
        Dict with stats: profiles_rebuilt, embeddings_processed, errors
    """
    stats = {"profiles_rebuilt": 0, "embeddings_processed": 0, "errors": 0}

    try:
        store = get_profile_store()

        # Start with empty profile DB
        from shared_quickscribe_py.speaker_profiles import SpeakerProfileDB
        db = SpeakerProfileDB()

        # Get all recordings for this user with completed transcriptions
        query = """
        SELECT * FROM c
        WHERE c.type = 'recording'
        AND c.user_id = @user_id
        AND c.transcription_status = 'completed'
        AND c.transcription_id != null
        """
        parameters = [{"name": "@user_id", "value": user_id}]

        items = list(recording_handler.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        for item in items:
            try:
                recording_id = item.get("id")
                transcription_id = item.get("transcription_id")

                if not transcription_id:
                    continue

                transcription = transcription_handler.get_transcription(transcription_id)
                if not transcription or not transcription.speaker_mapping:
                    continue

                for speaker_label, mapping in transcription.speaker_mapping.items():
                    if hasattr(mapping, 'model_dump'):
                        mapping_dict = mapping.model_dump()
                    elif isinstance(mapping, dict):
                        mapping_dict = mapping
                    else:
                        continue

                    # Only use verified speakers explicitly approved for training
                    if not mapping_dict.get('manuallyVerified'):
                        continue
                    if not mapping_dict.get('useForTraining'):
                        continue

                    participant_id = mapping_dict.get('participantId')
                    embedding_list = mapping_dict.get('embedding')

                    if not participant_id or not embedding_list:
                        continue

                    embedding = np.array(embedding_list, dtype=np.float32)
                    profile = db.get_or_create(participant_id)
                    profile.update([embedding], recording_id=recording_id)
                    stats["embeddings_processed"] += 1

            except Exception as e:
                logger.error(f"Error processing recording {item.get('id')}: {e}")
                stats["errors"] += 1

        # Save rebuilt profiles
        store.save_profiles(user_id, db)
        stats["profiles_rebuilt"] = len(db.profiles)
        logger.info(
            f"Rebuilt {stats['profiles_rebuilt']} profiles for user {user_id} "
            f"from {stats['embeddings_processed']} embeddings"
        )

    except Exception as e:
        logger.error(f"Failed to rebuild profiles for user {user_id}: {e}")
        stats["errors"] += 1

    return stats
