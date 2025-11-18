"""
Deleted items handler for tracking items deleted from external sources.
Prevents re-syncing of deleted Plaud recordings and other items.
"""
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from datetime import datetime, UTC
from typing import Optional, List
from . import models
from .util import filter_cosmos_fields

from ..logging.config import get_logger
logger = get_logger('deleted_items.handler')


class DeletedItems(models.DeletedItems):
    """Extended DeletedItems model for Cosmos DB operations"""
    pass


class DeletedItemsHandler:
    """
    Handler for managing deleted items to prevent re-syncing from external sources.

    Use case: User deletes a Plaud recording in the web app. Without tracking,
    the next Plaud sync would re-download it since it still exists in Plaud cloud.
    This handler maintains a blocklist of deleted items per user.
    """

    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def _get_document_id(self, user_id: str) -> str:
        """Generate document ID for a user's deleted items"""
        return f"deleted_items_{user_id}"

    def get_user_deleted_items(self, user_id: str) -> Optional[DeletedItems]:
        """
        Get the deleted items document for a user.

        Args:
            user_id: User ID

        Returns:
            DeletedItems object if exists, None otherwise
        """
        try:
            doc_id = self._get_document_id(user_id)
            item = self.container.read_item(item=doc_id, partition_key="deleted_items")
            return DeletedItems(**filter_cosmos_fields(item))
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting deleted items for user {user_id}: {str(e)}")
            return None

    def get_deleted_plaud_ids(self, user_id: str) -> List[str]:
        """
        Get list of deleted Plaud recording IDs for a user.
        Used for deduplication during Plaud sync.

        Args:
            user_id: User ID

        Returns:
            List of Plaud IDs that have been deleted
        """
        deleted_items = self.get_user_deleted_items(user_id)
        if not deleted_items or not deleted_items.items:
            return []

        plaud_recordings = deleted_items.items.get('plaud_recording')
        return plaud_recordings if plaud_recordings else []

    def add_deleted_plaud_id(self, user_id: str, plaud_id: str) -> bool:
        """
        Add a Plaud recording ID to the deleted items list.
        Creates the document if it doesn't exist.

        Args:
            user_id: User ID
            plaud_id: Plaud recording ID to block

        Returns:
            True if successful, False otherwise
        """
        try:
            doc_id = self._get_document_id(user_id)
            existing = self.get_user_deleted_items(user_id)

            if existing:
                # Update existing document
                plaud_recordings = existing.items.get('plaud_recording', [])

                # Avoid duplicates
                if plaud_id in plaud_recordings:
                    logger.info(f"Plaud ID {plaud_id} already in deleted items for user {user_id}")
                    return True

                plaud_recordings.append(plaud_id)
                existing.items['plaud_recording'] = plaud_recordings
                existing.updatedAt = datetime.now(UTC).isoformat()

                # Update in Cosmos
                item_dict = existing.model_dump()
                self.container.replace_item(item=doc_id, body=item_dict)
                logger.info(f"Added Plaud ID {plaud_id} to deleted items for user {user_id}")

            else:
                # Create new document
                now = datetime.now(UTC).isoformat()
                new_doc = {
                    "id": doc_id,
                    "type": "deleted_items",
                    "userId": user_id,
                    "items": {
                        "plaud_recording": [plaud_id]
                    },
                    "partitionKey": "deleted_items",
                    "createdAt": now,
                    "updatedAt": now
                }
                self.container.create_item(body=new_doc)
                logger.info(f"Created deleted items document for user {user_id} with Plaud ID {plaud_id}")

            return True

        except Exception as e:
            logger.error(f"Error adding Plaud ID {plaud_id} to deleted items for user {user_id}: {str(e)}")
            return False

    def remove_deleted_plaud_id(self, user_id: str, plaud_id: str) -> bool:
        """
        Remove a Plaud recording ID from the deleted items list (unblock).
        Allows the recording to be re-synced on next Plaud sync.

        Args:
            user_id: User ID
            plaud_id: Plaud recording ID to unblock

        Returns:
            True if successful, False otherwise
        """
        try:
            existing = self.get_user_deleted_items(user_id)

            if not existing:
                logger.warning(f"No deleted items document for user {user_id}")
                return False

            plaud_recordings = existing.items.get('plaud_recording', [])

            if plaud_id not in plaud_recordings:
                logger.warning(f"Plaud ID {plaud_id} not in deleted items for user {user_id}")
                return False

            # Remove the ID
            plaud_recordings.remove(plaud_id)
            existing.items['plaud_recording'] = plaud_recordings
            existing.updatedAt = datetime.now(UTC).isoformat()

            # Update in Cosmos
            doc_id = self._get_document_id(user_id)
            item_dict = existing.model_dump()
            self.container.replace_item(item=doc_id, body=item_dict)
            logger.info(f"Removed Plaud ID {plaud_id} from deleted items for user {user_id}")

            return True

        except Exception as e:
            logger.error(f"Error removing Plaud ID {plaud_id} from deleted items for user {user_id}: {str(e)}")
            return False

    def delete_user_deleted_items(self, user_id: str) -> bool:
        """
        Delete the entire deleted items document for a user.
        This unblocks all items for re-syncing.

        Args:
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        try:
            doc_id = self._get_document_id(user_id)
            self.container.delete_item(item=doc_id, partition_key="deleted_items")
            logger.info(f"Deleted all deleted items for user {user_id}")
            return True
        except CosmosResourceNotFoundError:
            logger.warning(f"No deleted items document found for user {user_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting deleted items for user {user_id}: {str(e)}")
            return False
