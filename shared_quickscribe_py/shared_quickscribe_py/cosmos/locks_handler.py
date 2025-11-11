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
            # Lock document exists - check if it's expired
            try:
                existing_lock = self.container.read_item(item=lock_id, partition_key="locks")
                acquired_at_str = existing_lock.get("acquiredAt")
                lock_ttl = existing_lock.get("ttl", ttl_seconds)
                existing_owner = existing_lock.get("ownerId")

                if acquired_at_str:
                    from dateutil import parser as date_parser
                    from datetime import timedelta

                    acquired_at = date_parser.parse(acquired_at_str)
                    expiry_time = acquired_at + timedelta(seconds=lock_ttl)
                    now = datetime.now(UTC)

                    if now > expiry_time:
                        # Lock has expired - force release and retry
                        logger.warning(
                            f"Lock '{lock_id}' held by '{existing_owner}' has expired "
                            f"(acquired: {acquired_at_str}, TTL: {lock_ttl}s). Force releasing..."
                        )
                        try:
                            self.container.delete_item(item=lock_id, partition_key="locks")
                            logger.info(f"Deleted expired lock '{lock_id}'")

                            # Retry acquisition after deleting stale lock
                            self.container.create_item(body=lock_document)
                            logger.info(f"Acquired lock '{lock_id}' for owner '{owner_id}' after removing stale lock")
                            return True
                        except Exception as delete_error:
                            logger.error(f"Error deleting expired lock '{lock_id}': {str(delete_error)}")
                            return False
                    else:
                        # Lock is still valid
                        time_remaining = (expiry_time - now).total_seconds()
                        logger.warning(
                            f"Lock '{lock_id}' already held by '{existing_owner}' "
                            f"(expires in {time_remaining / 60:.1f} minutes)"
                        )
                        return False
                else:
                    logger.warning(f"Lock '{lock_id}' exists but missing acquiredAt timestamp")
                    return False

            except CosmosResourceNotFoundError:
                # Lock was deleted between our attempts - retry once
                logger.info(f"Lock '{lock_id}' was deleted, retrying acquisition...")
                try:
                    self.container.create_item(body=lock_document)
                    logger.info(f"Acquired lock '{lock_id}' for owner '{owner_id}' on retry")
                    return True
                except Exception as retry_error:
                    logger.error(f"Error acquiring lock '{lock_id}' on retry: {str(retry_error)}")
                    return False
            except Exception as read_error:
                logger.error(f"Error reading existing lock '{lock_id}': {str(read_error)}")
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
