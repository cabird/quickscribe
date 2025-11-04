from azure.cosmos import CosmosClient
from datetime import datetime, UTC, timedelta
import uuid
from . import models
from .util import filter_cosmos_fields
from typing import Optional, List
from pydantic import field_validator, field_serializer
import logging

logger = logging.getLogger(__name__)

class SyncProgress(models.SyncProgress):
    """Extended SyncProgress model with datetime handling and TTL calculation"""
    
    # Override datetime fields to use actual datetime objects
    startTime: datetime
    lastUpdate: datetime
    estimatedCompletion: Optional[datetime] = None
    
    @field_validator('startTime', 'lastUpdate', 'estimatedCompletion', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        raise ValueError(f"Cannot parse datetime from {type(v)}")
    
    @field_serializer('startTime', 'lastUpdate', 'estimatedCompletion')
    def serialize_datetime(self, value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
    
    def __init__(self, **data):
        # Calculate TTL as 24 hours from start time
        if 'ttl' not in data or data['ttl'] is None:
            start_time = data.get('startTime')
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            elif start_time is None:
                start_time = datetime.now(UTC)
            
            # TTL is in seconds from start time + 24 hours
            ttl_time = start_time + timedelta(hours=24)
            data['ttl'] = int(ttl_time.timestamp())
        
        # Ensure required defaults
        if 'processedRecordings' not in data:
            data['processedRecordings'] = 0
        if 'failedRecordings' not in data:
            data['failedRecordings'] = 0
        if 'errors' not in data:
            data['errors'] = []
        if 'partitionKey' not in data:
            data['partitionKey'] = data.get('userId', '')
        if 'lastUpdate' not in data:
            data['lastUpdate'] = data.get('startTime', datetime.now(UTC))
            
        super().__init__(**data)

class SyncProgressHandler:
    def __init__(self, cosmos_client: CosmosClient, database_name: str, container_name: str = "sync_progress"):
        self.client = cosmos_client
        self.database_name = database_name
        self.container_name = container_name
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)
        logger.info(f"SyncProgressHandler initialized for container: {container_name}")

    def _ensure_container_exists(self):
        """Ensure the sync_progress container exists, create if it doesn't"""
        try:
            # Try to get container properties (will raise exception if doesn't exist)
            self.container.read()
        except Exception:
            try:
                # Container doesn't exist, try to create it
                from azure.cosmos import PartitionKey
                self.database.create_container(
                    id=self.container_name,
                    partition_key=PartitionKey(path="/partitionKey"),
                    default_ttl=-1  # No default TTL, we'll set per-document
                )
                logger.info(f"Created sync_progress container: {self.container_name}")
                # Re-initialize container client
                self.container = self.database.get_container_client(self.container_name)
            except Exception as create_error:
                logger.error(f"Failed to create sync_progress container: {create_error}")
                raise

    def create_progress(self, sync_token: str, user_id: str, status: str = 'queued', current_step: str = 'Initiating sync...') -> SyncProgress:
        """Create a new sync progress record"""
        try:
            # Ensure container exists
            self._ensure_container_exists()
            
            now = datetime.now(UTC)
            progress_data = {
                'id': sync_token,
                'type': 'sync_progress',
                'syncToken': sync_token,
                'userId': user_id,
                'status': status,
                'processedRecordings': 0,
                'failedRecordings': 0,
                'currentStep': current_step,
                'errors': [],
                'startTime': now,
                'lastUpdate': now,
                'partitionKey': user_id
            }
            
            progress = SyncProgress(**progress_data)
            
            # Convert to dict for CosmosDB
            progress_dict = progress.model_dump()
            progress_dict = filter_cosmos_fields(progress_dict)
            
            # Create the document
            created_item = self.container.create_item(progress_dict)
            logger.info(f"Created sync progress for token: {sync_token}")
            
            return progress
            
        except Exception as e:
            logger.error(f"Error creating sync progress: {str(e)}")
            raise

    def get_progress(self, sync_token: str, user_id: str) -> Optional[SyncProgress]:
        """Get sync progress by token and user ID"""
        try:
            # Ensure container exists
            self._ensure_container_exists()
            
            query = "SELECT * FROM c WHERE c.id = @sync_token AND c.userId = @user_id"
            parameters = [
                {"name": "@sync_token", "value": sync_token},
                {"name": "@user_id", "value": user_id}
            ]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))
            
            if items:
                return SyncProgress(**items[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting sync progress for token {sync_token}: {str(e)}")
            return None

    def update_progress(self, sync_token: str, user_id: str, **updates) -> Optional[SyncProgress]:
        """Update sync progress fields"""
        try:
            # Get current progress
            current_progress = self.get_progress(sync_token, user_id)
            if not current_progress:
                logger.warning(f"Sync progress not found for token: {sync_token}")
                return None
            
            # Update fields
            progress_dict = current_progress.model_dump()
            progress_dict.update(updates)
            progress_dict['lastUpdate'] = datetime.now(UTC)
            
            # Create updated model
            updated_progress = SyncProgress(**progress_dict)
            
            # Convert to dict for CosmosDB
            update_dict = updated_progress.model_dump()
            update_dict = filter_cosmos_fields(update_dict)
            
            # Replace the document
            self.container.replace_item(item=sync_token, body=update_dict)
            logger.info(f"Updated sync progress for token: {sync_token}")
            
            return updated_progress
            
        except Exception as e:
            logger.error(f"Error updating sync progress for token {sync_token}: {str(e)}")
            return None

    def add_error(self, sync_token: str, user_id: str, error_message: str) -> Optional[SyncProgress]:
        """Add an error message to the progress record"""
        try:
            current_progress = self.get_progress(sync_token, user_id)
            if not current_progress:
                return None
            
            # Add error and increment failed count
            errors = list(current_progress.errors)
            errors.append(error_message)
            
            return self.update_progress(
                sync_token, 
                user_id,
                errors=errors,
                failedRecordings=current_progress.failedRecordings + 1
            )
            
        except Exception as e:
            logger.error(f"Error adding error to sync progress {sync_token}: {str(e)}")
            return None

    def mark_completed(self, sync_token: str, user_id: str) -> Optional[SyncProgress]:
        """Mark sync as completed"""
        return self.update_progress(
            sync_token,
            user_id,
            status='completed',
            currentStep='Sync completed successfully'
        )

    def mark_failed(self, sync_token: str, user_id: str, error_message: str = None) -> Optional[SyncProgress]:
        """Mark sync as failed"""
        updates = {
            'status': 'failed',
            'currentStep': 'Sync failed'
        }
        
        if error_message:
            current_progress = self.get_progress(sync_token, user_id)
            if current_progress:
                errors = list(current_progress.errors)
                errors.append(error_message)
                updates['errors'] = errors
        
        return self.update_progress(sync_token, user_id, **updates)

    def check_stale_syncs(self) -> int:
        """Check for syncs that have been queued for 2+ hours and mark them as failed"""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(hours=2)
            
            # Find syncs that are still 'queued' after 2 hours
            query = "SELECT * FROM c WHERE c.status = 'queued' AND c.startTime < @cutoff_time"
            parameters = [{"name": "@cutoff_time", "value": cutoff_time.isoformat()}]
            
            stale_syncs = list(self.container.query_items(
                query=query,
                parameters=parameters
            ))
            
            cleaned_count = 0
            for item in stale_syncs:
                try:
                    sync_progress = SyncProgress(**item)
                    elapsed_hours = (datetime.now(UTC) - sync_progress.startTime).total_seconds() / 3600
                    
                    logger.warning(f"Marking stale sync as failed: {sync_progress.syncToken} " +
                                 f"(queued for {elapsed_hours:.1f} hours)")
                    
                    # Mark as failed with timeout message
                    self.mark_failed(
                        sync_progress.syncToken,
                        sync_progress.userId,
                        f"Sync timeout after {elapsed_hours:.1f} hours - transcoder may be unavailable"
                    )
                    cleaned_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to mark stale sync as failed {item.get('id', 'unknown')}: {str(e)}")
            
            if cleaned_count > 0:
                logger.info(f"Marked {cleaned_count} stale sync operations as failed")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during stale sync cleanup: {str(e)}")
            return 0

    def cleanup_expired_progress(self) -> int:
        """Clean up expired progress records (those older than 24 hours)"""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(hours=24)
            
            query = "SELECT * FROM c WHERE c.startTime < @cutoff_time"
            parameters = [{"name": "@cutoff_time", "value": cutoff_time.isoformat()}]
            
            expired_items = list(self.container.query_items(
                query=query,
                parameters=parameters
            ))
            
            deleted_count = 0
            for item in expired_items:
                try:
                    self.container.delete_item(item=item['id'], partition_key=item['partitionKey'])
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete expired progress {item['id']}: {str(e)}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired sync progress records")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during cleanup of expired progress records: {str(e)}")
            return 0

def get_sync_progress_handler(cosmos_client: CosmosClient, database_name: str) -> SyncProgressHandler:
    """Factory function to get a SyncProgressHandler instance"""
    return SyncProgressHandler(cosmos_client, database_name)