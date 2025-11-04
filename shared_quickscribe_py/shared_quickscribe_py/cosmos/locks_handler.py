"""
Distributed locking handler for Cosmos DB.
Provides mutex-like locking for coordinating distributed processes.
"""
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError
from datetime import datetime, UTC
from typing import Optional

from ..logging.config import get_logger
logger = get_logger('locks.handler')


class LocksHandler:
    """
    Handler for distributed locks using Cosmos DB.
    Uses document creation as a mutex mechanism with TTL for automatic cleanup.
    """

    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def acquire_lock(self, lock_id: str, owner_id: str, ttl_seconds: int = 1800) -> bool:
        """
        Attempt to acquire a distributed lock.

        Args:
            lock_id: Unique identifier for the lock
            owner_id: ID of the process/job attempting to acquire the lock
            ttl_seconds: Time-to-live for the lock (default 30 minutes)

        Returns:
            True if lock acquired, False if already held by another process
        """
        lock_document = {
            "id": lock_id,
            "ownerId": owner_id,
            "acquiredAt": datetime.now(UTC).isoformat(),
            "ttl": ttl_seconds,
            "partitionKey": "locks"
        }

        try:
            self.container.create_item(body=lock_document)
            logger.info(f"Acquired lock '{lock_id}' for owner '{owner_id}'")
            return True
        except CosmosResourceExistsError:
            logger.warning(f"Lock '{lock_id}' already exists, cannot acquire")
            return False
        except Exception as e:
            logger.error(f"Error acquiring lock '{lock_id}': {str(e)}")
            return False

    def release_lock(self, lock_id: str, owner_id: str) -> bool:
        """
        Release a distributed lock.

        Args:
            lock_id: Unique identifier for the lock
            owner_id: ID of the process/job that owns the lock

        Returns:
            True if lock released, False if not found or error
        """
        try:
            # Read the lock document first to verify ownership
            lock_doc = self.container.read_item(item=lock_id, partition_key="locks")

            # Verify ownership before deleting
            if lock_doc.get("ownerId") != owner_id:
                logger.warning(f"Lock '{lock_id}' owned by '{lock_doc.get('ownerId')}', "
                             f"cannot release by '{owner_id}'")
                return False

            # Delete the lock document
            self.container.delete_item(item=lock_id, partition_key="locks")
            logger.info(f"Released lock '{lock_id}' for owner '{owner_id}'")
            return True
        except CosmosResourceNotFoundError:
            logger.warning(f"Lock '{lock_id}' not found, may have already been released or expired")
            return False
        except Exception as e:
            logger.error(f"Error releasing lock '{lock_id}': {str(e)}")
            return False

    def is_lock_held(self, lock_id: str) -> bool:
        """
        Check if a lock is currently held.

        Args:
            lock_id: Unique identifier for the lock

        Returns:
            True if lock exists, False otherwise
        """
        try:
            self.container.read_item(item=lock_id, partition_key="locks")
            return True
        except CosmosResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking lock '{lock_id}': {str(e)}")
            return False

    def get_lock_owner(self, lock_id: str) -> Optional[str]:
        """
        Get the owner ID of a lock.

        Args:
            lock_id: Unique identifier for the lock

        Returns:
            Owner ID if lock exists, None otherwise
        """
        try:
            lock_doc = self.container.read_item(item=lock_id, partition_key="locks")
            return lock_doc.get("ownerId")
        except CosmosResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting lock owner for '{lock_id}': {str(e)}")
            return None
