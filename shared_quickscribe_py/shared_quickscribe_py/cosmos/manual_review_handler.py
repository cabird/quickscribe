"""
Handler for ManualReviewItem documents in Cosmos DB.
Manages recordings that require manual review after repeated failures.
"""
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from typing import Optional, List
from datetime import datetime, UTC
import uuid

from ..logging.config import get_logger
from .models import ManualReviewItem

logger = get_logger('manual_review.handler')


class ManualReviewItemHandler:
    """
    Handler for ManualReviewItem operations in Cosmos DB.
    """

    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_manual_review_item(self, manual_review_item: ManualReviewItem) -> ManualReviewItem:
        """
        Create a new manual review item.

        Args:
            manual_review_item: ManualReviewItem model to create

        Returns:
            Created ManualReviewItem
        """
        try:
            item_dict = manual_review_item.model_dump(mode='json')
            item_dict['type'] = 'manual_review_item'

            created = self.container.create_item(body=item_dict)
            logger.info(f"Created manual review item: {manual_review_item.id} for recording {manual_review_item.recordingId}")

            return ManualReviewItem(**created)
        except Exception as e:
            logger.error(f"Error creating manual review item for recording {manual_review_item.recordingId}: {str(e)}")
            raise

    def get_manual_review_item(self, item_id: str) -> Optional[ManualReviewItem]:
        """
        Get a manual review item by ID.

        Args:
            item_id: Manual review item ID

        Returns:
            ManualReviewItem if found, None otherwise
        """
        try:
            item = self.container.read_item(item=item_id, partition_key="manual_review")
            return ManualReviewItem(**item)
        except CosmosResourceNotFoundError:
            logger.warning(f"Manual review item not found: {item_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting manual review item {item_id}: {str(e)}")
            raise

    def get_by_recording_id(self, recording_id: str) -> Optional[ManualReviewItem]:
        """
        Get manual review item by recording ID.

        Args:
            recording_id: Recording ID to search for

        Returns:
            ManualReviewItem if found, None otherwise
        """
        try:
            query = """
            SELECT * FROM c
            WHERE c.type = 'manual_review_item'
            AND c.recordingId = @recording_id
            """
            parameters = [{"name": "@recording_id", "value": recording_id}]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key="manual_review"
            ))

            if items:
                return ManualReviewItem(**items[0])
            return None
        except Exception as e:
            logger.error(f"Error getting manual review item for recording {recording_id}: {str(e)}")
            raise

    def update_manual_review_item(self, manual_review_item: ManualReviewItem) -> ManualReviewItem:
        """
        Update an existing manual review item.

        Args:
            manual_review_item: ManualReviewItem model with updates

        Returns:
            Updated ManualReviewItem
        """
        try:
            item_dict = manual_review_item.model_dump(mode='json')
            item_dict['type'] = 'manual_review_item'

            updated = self.container.upsert_item(body=item_dict)
            logger.info(f"Updated manual review item: {manual_review_item.id}")

            return ManualReviewItem(**updated)
        except Exception as e:
            logger.error(f"Error updating manual review item {manual_review_item.id}: {str(e)}")
            raise

    def get_pending_items(self, limit: int = 50) -> List[ManualReviewItem]:
        """
        Get pending manual review items.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of ManualReviewItem records with status 'pending'
        """
        try:
            query = """
            SELECT TOP @limit * FROM c
            WHERE c.type = 'manual_review_item'
            AND c.status = 'pending'
            ORDER BY c.createdAt DESC
            """
            parameters = [{"name": "@limit", "value": limit}]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key="manual_review"
            ))

            return [ManualReviewItem(**item) for item in items]
        except Exception as e:
            logger.error(f"Error getting pending manual review items: {str(e)}")
            raise

    def get_items_by_user(self, user_id: str, limit: int = 50) -> List[ManualReviewItem]:
        """
        Get manual review items for a specific user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of items to return

        Returns:
            List of ManualReviewItem records
        """
        try:
            query = """
            SELECT TOP @limit * FROM c
            WHERE c.type = 'manual_review_item'
            AND c.userId = @user_id
            ORDER BY c.createdAt DESC
            """
            parameters = [
                {"name": "@limit", "value": limit},
                {"name": "@user_id", "value": user_id}
            ]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key="manual_review"
            ))

            return [ManualReviewItem(**item) for item in items]
        except Exception as e:
            logger.error(f"Error getting manual review items for user {user_id}: {str(e)}")
            raise

    def delete_manual_review_item(self, item_id: str) -> None:
        """
        Delete a manual review item by ID.

        Args:
            item_id: Manual review item ID to delete
        """
        try:
            self.container.delete_item(item=item_id, partition_key="manual_review")
            logger.info(f"Deleted manual review item: {item_id}")
        except CosmosResourceNotFoundError:
            logger.warning(f"Manual review item not found for deletion: {item_id}")
        except Exception as e:
            logger.error(f"Error deleting manual review item {item_id}: {str(e)}")
            raise
