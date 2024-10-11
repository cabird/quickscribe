from azure.cosmos import CosmosClient, PartitionKey
from datetime import datetime
import uuid

class TranscriptionHandler:
    def __init__(self, cosmos_url, cosmos_key, database_name, container_name):
        self.client = CosmosClient(cosmos_url, credential=cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_transcription(self, user_id, recording_id, recording_link, language="en-US"):
        """Create a new transcription entry in Cosmos DB."""
        transcription_id = str(uuid.uuid4())
        transcription_item = {
            "id": transcription_id,
            "user_id": user_id,
            "recording_id": recording_id,
            "recording_link": recording_link,
            "transcription_status": "not_started",  # Default status
            "transcription_progress": 0,
            "transcript_text": "",
            "language": language,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "partitionKey": "transcription"
        }
        self.container.create_item(body=transcription_item)
        return transcription_id

    def get_transcription_by_recording(self, recording_id):
        """Get a transcription entry by the associated recording ID."""
        query = "SELECT * FROM c WHERE c.recording_id = @recording_id AND c.partitionKey = 'transcription'"
        parameters = [{"name": "@recording_id", "value": recording_id}]
        transcriptions = list(self.container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        return transcriptions[0] if transcriptions else None

    def update_transcription_status(self, transcription_id, status, progress=None, transcript_text=None):
        """Update the transcription status, progress, or transcript text."""
        transcription = self.get_transcription(transcription_id)
        if transcription:
            transcription['transcription_status'] = status
            if progress is not None:
                transcription['transcription_progress'] = progress
            if transcript_text is not None:
                transcription['transcript_text'] = transcript_text
            transcription['updated_at'] = datetime.utcnow().isoformat()
            self.container.replace_item(item=transcription_id, body=transcription)

    def get_transcription(self, transcription_id):
        """Retrieve a transcription by its ID."""
        try:
            transcription = self.container.read_item(item=transcription_id, partition_key="transcription")
            return transcription
        except Exception as e:
            print(f"Error retrieving transcription: {e}")
            return None
