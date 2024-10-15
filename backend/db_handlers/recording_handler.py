from azure.cosmos import CosmosClient, PartitionKey
from .transcription_handler import TranscriptionHandler
from datetime import datetime
import uuid

class RecordingHandler:
    def __init__(self, cosmos_url, cosmos_key, database_name, container_name):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)
        self.transcription_handler = TranscriptionHandler(cosmos_url, cosmos_key, database_name, container_name)

    def create_recording(self, user_id, original_filename, unique_filename):
        """Create a new recording entry in Cosmos DB."""
        recording_id = str(uuid.uuid4())
        recording_item = {
            "id": recording_id,
            "user_id": user_id,
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "upload_timestamp": datetime.utcnow().isoformat(),
            "partitionKey": "recording"
        }
        item = self.container.create_item(body=recording_item)
        return item

    def get_recording(self, recording_id):
        """Retrieve a recording by its ID."""
        try:
            recording = self.container.read_item(item=recording_id, partition_key="recording")
            return recording
        except Exception as e:
            print(f"Error retrieving recording: {e}")
            return None

    def get_user_recordings(self, user_id):
        """Get all recordings for a specific user."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id"
        parameters = [{"name": "@user_id", "value": user_id}]
        recordings = list(self.container.query_items(query=query, parameters=parameters, partition_key="recording"))
        return recordings

    def link_to_transcription(self, recording_id, transcription_id):
        """Link a recording to a transcription by updating the recording with a transcription ID."""
        recording = self.get_recording(recording_id)
        if recording:
            recording['transcription_id'] = transcription_id
            self.container.replace_item(item=recording_id, body=recording)

    def get_transcription_status(self, recording_id):
        """Check if there is a transcription linked to the recording and return its status."""
        recording = self.get_recording(recording_id)
        if 'transcription_id' in recording:
            transcription_id = recording['transcription_id']
            transcription = self.transcription_handler.get_transcription(transcription_id)
            return transcription['transcription_status'] if transcription else "No Transcription Found"
        return "No Transcription"

    def delete_recording(self, recording_id):
        """Delete a recording by its ID."""
        self.container.delete_item(item=recording_id, partition_key="recording")

    def update_recording(self, recording):
        """Update a recording in Cosmos DB."""
        self.container.replace_item(item=recording['id'], body=recording)
