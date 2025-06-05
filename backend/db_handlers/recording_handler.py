from azure.cosmos import CosmosClient, PartitionKey
from .transcription_handler import TranscriptionHandler
from datetime import datetime, UTC
import uuid
import db_handlers.models as models# Import the Pydantic Recording model
from pydantic import Field, field_validator
from db_handlers.util import filter_cosmos_fields  # Import the utility function
from typing import Optional, List, Any, Dict, Union

from logging_config import get_logger
logger = get_logger('recording.handler')

class Recording(models.Recording):
    #transcription_status_updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __init__(self, **data):
        # Convert string values to enum objects if they are strings
        if 'transcription_status' in data and isinstance(data['transcription_status'], str):
            data['transcription_status'] = models.TranscriptionStatus(data['transcription_status'])
        if 'transcoding_status' in data and isinstance(data['transcoding_status'], str):
            data['transcoding_status'] = models.TranscodingStatus(data['transcoding_status'])
        super().__init__(**data)
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override model_dump to handle enum conversions properly"""
        data = super().model_dump(**kwargs)

        # Ensure enums are converted to their string values for serialization
        if 'transcription_status' in data and isinstance(data['transcription_status'], models.TranscriptionStatus):
            data['transcription_status'] = data['transcription_status'].value
        if 'transcoding_status' in data and isinstance(data['transcoding_status'], models.TranscodingStatus):
            data['transcoding_status'] = data['transcoding_status'].value
            
        return data


class RecordingHandler:
    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)
        self.transcription_handler = TranscriptionHandler(cosmos_url, cosmos_key, database_name, container_name)

    def create_recording(self, user_id: str, original_filename: str, unique_filename: str, 
                         transcription_status: models.TranscriptionStatus = models.TranscriptionStatus.not_started,
                         transcoding_status: models.TranscodingStatus = models.TranscodingStatus.not_started,
                         source: Optional[models.Source] = None) -> Recording:
        """Create a new recording entry in Cosmos DB and return as a Recording model."""
        recording_id = str(uuid.uuid4())
        recording_item = {
            "id": recording_id,
            "user_id": user_id,
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "transcription_status": transcription_status.value,
            "transcoding_status": transcoding_status.value,
            "transcoding_retry_count": 0,
            "partitionKey": "recording"
        }
        
        # Add source if provided
        if source is not None:
            recording_item["source"] = source.value if hasattr(source, 'value') else source
        item = self.container.create_item(body=recording_item)
        return Recording(**filter_cosmos_fields(item))

    def get_recording(self, recording_id: str) -> Optional[Recording]:
        """Retrieve a recording by its ID and return as a Recording model."""
        try:
            recording = self.container.read_item(item=recording_id, partition_key="recording")
            return Recording(**filter_cosmos_fields(recording))
        except Exception as e:
            print(f"Error retrieving recording: {e}")
            return None

    def get_user_recordings(self, user_id: str) -> List[Recording]:
        """Get all recordings for a specific user and return as Recording models."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id"
        parameters = [{"name": "@user_id", "value": user_id}]
        recordings = self.container.query_items(query=query, parameters=parameters, partition_key="recording")
        logger.info(f"Querying recordings for user {user_id}")
        recordings = [Recording(**filter_cosmos_fields(rec)) for rec in recordings]
        logger.info(f"Found {len(recordings)} recordings for user {user_id}")
        return recordings

    def get_all_recordings(self, user_id: str = None) -> List[Recording]:
        """Get all recordings and return as Recording models."""
        if user_id:
            query = "SELECT * FROM c WHERE c.partitionKey = 'recording' AND c.user_id = @user_id"
            parameters = [{"name": "@user_id", "value": user_id}]
        else:
            query = "SELECT * FROM c WHERE c.partitionKey = 'recording'"
            parameters = []
        recordings = self.container.query_items(query=query, parameters=parameters, partition_key="recording")
        logger.info("Querying all recordings")
        recordings = [Recording(**filter_cosmos_fields(rec)) for rec in recordings]
        logger.info(f"Found {len(recordings)} recordings")
        return recordings   

    def get_user_plaud_ids(self, user_id: str) -> List[str]:
        """Get all Plaud IDs that have been synced for a user."""
        query = """
        SELECT c.plaudMetadata.plaudId 
        FROM c 
        WHERE c.user_id = @user_id 
        AND c.source = 'plaud' 
        AND IS_DEFINED(c.plaudMetadata.plaudId)
        """
        parameters = [{"name": "@user_id", "value": user_id}]
        results = self.container.query_items(
            query=query, 
            parameters=parameters, 
            partition_key="recording"
        )
        plaud_ids = [item['plaudId'] for item in results if 'plaudId' in item]
        logger.info(f"Found {len(plaud_ids)} Plaud IDs for user {user_id}")
        return plaud_ids

    def delete_recording(self, recording_id: str) -> None:
        """Delete a recording by its ID."""
        self.container.delete_item(item=recording_id, partition_key="recording")

    def update_recording(self, recording: Recording) -> Recording:
        """Update a recording in Cosmos DB."""
        recording_data = recording.model_dump(exclude_unset=True)
        # Ensure ID is available for the replace_item operation
        if 'id' not in recording_data:
            recording_data['id'] = recording.id
        updated_record = self.container.replace_item(item=recording_data['id'], body=recording_data)
        return Recording(**filter_cosmos_fields(updated_record))
