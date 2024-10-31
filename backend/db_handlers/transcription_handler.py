from azure.cosmos import CosmosClient, PartitionKey
from datetime import datetime
import uuid
from db_handlers.models import Transcription, TranscriptionStatus  # Import the Pydantic Transcription model and TranscriptionStatus enum
from db_handlers.util import filter_cosmos_fields  # Import the utility function
from typing import Optional, List

class TranscriptionHandler:
    def __init__(self, cosmos_url: str, cosmos_key: str, database_name: str, container_name: str):
        """
        Initialize the TranscriptionHandler with Cosmos DB connection details.

        :param cosmos_url: URL for the Cosmos DB account.
        :param cosmos_key: Key for the Cosmos DB account.
        :param database_name: Name of the database.
        :param container_name: Name of the container.
        """
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_transcription(self, user_id: str, recording_id: str) -> Transcription:
        """
        Create a new transcription entry in Cosmos DB and return as a Transcription model.

        :param user_id: ID of the user.
        :param recording_id: ID of the recording.
        :return: Transcription model instance.
        """
        transcription_id = str(uuid.uuid4())
        transcription_item = {
            "id": transcription_id,
            "az_transcription_id": "",
            "user_id": user_id,
            "recording_id": recording_id,
            "transcription_status": TranscriptionStatus.not_started.value,  # Use Enum value for status
            "transcription_progress": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "partitionKey": "transcription",
            "text": "",
            "transcript_json": ""
        }
        item = self.container.create_item(body=transcription_item)
        return Transcription(**filter_cosmos_fields(item))

    def get_transcription_by_recording(self, recording_id: str) -> Optional[Transcription]:
        """
        Get a transcription entry by the associated recording ID and return as a Transcription model.

        :param recording_id: ID of the recording.
        :return: Transcription model instance or None if not found.
        """
        query = "SELECT * FROM c WHERE c.recording_id = @recording_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@recording_id", "value": recording_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return Transcription(**filter_cosmos_fields(transcriptions[0])) if transcriptions else None

    def get_transcription_by_az_id(self, az_transcription_id: str) -> Optional[Transcription]:
        """
        Get a transcription entry by the associated Azure Speech Services transcription ID and return as a Transcription model.

        :param az_transcription_id: ID of the Azure transcription.
        :return: Transcription model instance or None if not found.
        """
        query = "SELECT * FROM c WHERE c.az_transcription_id = @az_transcription_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@az_transcription_id", "value": az_transcription_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return Transcription(**filter_cosmos_fields(transcriptions[0])) if transcriptions else None

    def get_transcription(self, transcription_id: str) -> Optional[Transcription]:
        """
        Retrieve a transcription by its ID and return as a Transcription model.

        :param transcription_id: ID of the transcription.
        :return: Transcription model instance or None if not found.
        """
        try:
            transcription = self.container.read_item(item=transcription_id, partition_key="transcription")
            return Transcription(**filter_cosmos_fields(transcription))
        except Exception as e:
            print(f"Error retrieving transcription: {e}")
            return None

    def update_transcription(self, transcription: Transcription) -> Transcription:
        """
        Update an existing transcription in Cosmos DB and return the updated Transcription model.

        :param transcription: Transcription model instance with updated data.
        :return: Updated Transcription model instance.
        """
        transcription_data = transcription.dict(exclude_unset=True)
        updated_item = self.container.upsert_item(body=transcription_data)
        return Transcription(**filter_cosmos_fields(updated_item))

    def delete_transcription(self, transcription_id: str) -> None:
        """
        Delete a transcription from Cosmos DB.

        :param transcription_id: ID of the transcription to delete.
        """
        self.container.delete_item(item=transcription_id, partition_key="transcription")