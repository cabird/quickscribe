from azure.cosmos import CosmosClient, PartitionKey
from datetime import datetime
import uuid

from enum import Enum

class TranscribingStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"



class TranscriptionHandler:
    def __init__(self, cosmos_url, cosmos_key, database_name, container_name):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_transcription(self, user_id, recording_id):
        """Create a new transcription entry in Cosmos DB."""
        transcription_id = str(uuid.uuid4())
        transcription_item = {
            "id": transcription_id,
            "user_id": user_id,
            "recording_id": recording_id,
            "transcription_status": "not_started",  # Default status
            "transcription_progress": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "partitionKey": "transcription",
            "text": "",
            "transcript_json": ""
        }
        item = self.container.create_item(body=transcription_item)
        return item

    def get_transcription_by_recording(self, recording_id):
        """Get a transcription entry by the associated recording ID."""
        query = "SELECT * FROM c WHERE c.recording_id = @recording_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@recording_id", "value": recording_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return transcriptions[0] if transcriptions else None

    def get_transcription_by_az_id(self, az_transcription_id):
        """Get a transcription entry by the associated Azure Speech Services transcription ID."""
        query = "SELECT * FROM c WHERE c.az_transcription_id = @az_transcription_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@az_transcription_id", "value": az_transcription_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return transcriptions[0] if transcriptions else None

    def get_transcription(self, transcription_id):
        """Retrieve a transcription by its ID."""
        try:
            transcription = self.container.read_item(item=transcription_id, partition_key="transcription")
            return transcription
        except Exception as e:
            print(f"Error retrieving transcription: {e}")
            return None

    def update_transcription(self, transcription):
        """Update an existing transcription in Cosmos DB."""
        self.container.upsert_item(body=transcription)
