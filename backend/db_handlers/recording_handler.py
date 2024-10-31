from azure.cosmos import CosmosClient, PartitionKey
from .transcription_handler import TranscriptionHandler
from datetime import datetime, UTC
import uuid
import db_handlers.models as models# Import the Pydantic Recording model
from pydantic import Field, field_validator
from db_handlers.util import filter_cosmos_fields  # Import the utility function
from typing import Optional, List, Any

class Recording(models.Recording):
    transcription_status: models.TranscriptionStatus = Field(default=models.TranscriptionStatus.not_started)
    transcription_status_updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __init__(self, **data):
        super().__init__(**data)
        self._transcription_status = data.get('transcription_status', models.TranscriptionStatus.not_started)

    @property
    def transcription_status(self) -> models.TranscriptionStatus:
        return self._transcription_status  

    @transcription_status.setter
    def transcription_status(self, value: models.TranscriptionStatus):
        if value != self._transcription_status: 
            self._transcription_status = value
            self.transcription_status_updated_at = datetime.now(UTC).isoformat()

    @field_validator('transcription_status')
    @classmethod
    def validate_transcription_status(cls, value):
        print(f"validate_transcription_status: {value}")
        # Convert string value back to TranscriptionStatus Enum
        if isinstance(value, str):
            return models.TranscriptionStatus(value)
        return value
    
    def model_dump(self, *args: Any, **kwargs: Any) -> dict:
        data = super().model_dump(*args, **kwargs)
        # Convert Enum to string for JSON serialization
        data['transcription_status'] = data['transcription_status'].value
        return data

class RecordingHandler:
    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)
        self.transcription_handler = TranscriptionHandler(cosmos_url, cosmos_key, database_name, container_name)

    def create_recording(self, user_id: str, original_filename: str, unique_filename: str, transcription_status: models.TranscriptionStatus = models.TranscriptionStatus.not_started) -> Recording:
        """Create a new recording entry in Cosmos DB and return as a Recording model."""
        recording_id = str(uuid.uuid4())
        recording_item = {
            "id": recording_id,
            "user_id": user_id,
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "transcription_status": transcription_status.value,
            "partitionKey": "recording"
        }
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
        return [Recording(**filter_cosmos_fields(rec)) for rec in recordings]

    def get_all_recordings(self) -> List[Recording]:
        """Get all recordings and return as Recording models."""
        query = "SELECT * FROM c WHERE c.partitionKey = 'recording'"
        recordings = self.container.query_items(query=query, partition_key="recording")
        return [Recording(**filter_cosmos_fields(rec)) for rec in recordings]

    def delete_recording(self, recording_id: str) -> None:
        """Delete a recording by its ID."""
        self.container.delete_item(item=recording_id, partition_key="recording")

    def update_recording(self, recording: Recording) -> Recording:
        """Update a recording in Cosmos DB."""
        recording_data = recording.model_dump(exclude_unset=True)   
        updated_record = self.container.replace_item(item=recording_data['id'], body=recording_data)
        return Recording(**filter_cosmos_fields(updated_record))
