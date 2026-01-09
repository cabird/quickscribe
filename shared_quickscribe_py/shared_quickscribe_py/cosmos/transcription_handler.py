from azure.cosmos import CosmosClient, PartitionKey
from datetime import datetime, UTC
import uuid
from .models import Transcription as BaseTranscription, TranscriptionStatus, SpeakerMapping  # Import the Pydantic Transcription model and TranscriptionStatus enum
from .util import filter_cosmos_fields  # Import the utility function
from typing import Optional, List, Dict
from pydantic import field_validator
import tiktoken

class Transcription(BaseTranscription):
    """Extended Transcription model with proper speaker_mapping handling."""
    
    @field_validator('speaker_mapping', mode='before')
    @classmethod
    def parse_speaker_mapping(cls, v):
        """Convert dict values to SpeakerMapping objects if needed."""
        if v is None:
            return v
        if isinstance(v, dict):
            # Convert each value to SpeakerMapping if it's a plain dict
            converted = {}
            for speaker_label, mapping_data in v.items():
                if isinstance(mapping_data, dict):
                    # Convert dict to SpeakerMapping
                    converted[speaker_label] = SpeakerMapping(**mapping_data)
                elif isinstance(mapping_data, SpeakerMapping):
                    # Already a SpeakerMapping object
                    converted[speaker_label] = mapping_data
                else:
                    # Unexpected type, keep as-is
                    converted[speaker_label] = mapping_data
            return converted
        return v

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

    def create_transcription(self, user_id: str, recording_id: str, test_run_id: Optional[str] = None) -> Transcription:
        """
        Create a new transcription entry in Cosmos DB and return as a Transcription model.

        :param user_id: ID of the user.
        :param recording_id: ID of the recording.
        :param test_run_id: Optional test run identifier for cleanup purposes.
        :return: Transcription model instance.
        """
        transcription_id = str(uuid.uuid4())
        transcription_item = {
            "id": transcription_id,
            "type": "transcription",
            "az_transcription_id": "",
            "user_id": user_id,
            "recording_id": recording_id,
            "transcription_status": TranscriptionStatus.not_started.value,  # Use Enum value for status
            "transcription_progress": 0,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "partitionKey": "transcription",
            "text": "",
            "transcript_json": ""
        }
        if test_run_id:
            transcription_item["testRunId"] = test_run_id
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

        Automatically calculates token_count if transcript text exists.

        :param transcription: Transcription model instance with updated data.
        :return: Updated Transcription model instance.
        """
        # Auto-calculate token_count if transcript text exists
        transcript_text = transcription.diarized_transcript or transcription.text
        if transcript_text:
            transcription.token_count = self.calculate_token_count(transcript_text)

        transcription_data = transcription.model_dump(exclude_unset=True)
        updated_item = self.container.upsert_item(body=transcription_data)
        return Transcription(**filter_cosmos_fields(updated_item))

    # Cache the tokenizer instance for performance
    _tokenizer = None

    @classmethod
    def _get_tokenizer(cls):
        """Get or create the cached tiktoken tokenizer."""
        if cls._tokenizer is None:
            # o200k_base is used by GPT-4o and newer models
            cls._tokenizer = tiktoken.get_encoding("o200k_base")
        return cls._tokenizer

    @classmethod
    def calculate_token_count(cls, text: str) -> int:
        """
        Calculate token count for text using tiktoken.

        Uses the o200k_base encoding (GPT-4o tokenizer),
        which provides accurate counts for modern LLMs.

        :param text: The text to count tokens for.
        :return: Token count.
        """
        if not text:
            return 0
        tokenizer = cls._get_tokenizer()
        return len(tokenizer.encode(text))

    def delete_transcription(self, transcription_id: str) -> None:
        """
        Delete a transcription from Cosmos DB.

        :param transcription_id: ID of the transcription to delete.
        """
        self.container.delete_item(item=transcription_id, partition_key="transcription")
    
    def get_all_transcriptions(self) -> List[Transcription]:
        """
        Get all transcriptions from all users.
        
        :return: List of Transcription model instances.
        """
        query = "SELECT * FROM c WHERE c.partitionKey = 'transcription'"
        items = list(self.container.query_items(
            query=query, 
            enable_cross_partition_query=True
        ))
        return [Transcription(**filter_cosmos_fields(item)) for item in items]
    
    @staticmethod
    def transform_transcript_with_speaker_names(transcript_text: str, speaker_mapping: Optional[Dict[str, SpeakerMapping]]) -> str:
        """
        Transform a diarized transcript to use speaker names from the mapping.
        
        Args:
            transcript_text: The diarized transcript with "Speaker 1:", "Speaker 2:", etc.
            speaker_mapping: Optional mapping from speaker labels to SpeakerMapping objects
            
        Returns:
            Transformed transcript with actual speaker names, or original if no mapping
        """
        if not transcript_text or not speaker_mapping:
            return transcript_text
            
        lines = transcript_text.split('\n')
        transformed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line starts with a speaker pattern (Speaker X:)
            speaker_match = line.split(':', 1)
            if len(speaker_match) == 2:
                speaker_label = speaker_match[0].strip()
                content = speaker_match[1].strip()
                
                # Use speaker mapping if available
                if speaker_label in speaker_mapping:
                    speaker_name = speaker_mapping[speaker_label].name
                    transformed_lines.append(f"{speaker_name}: {content}")
                else:
                    transformed_lines.append(line)
            else:
                transformed_lines.append(line)
        
        return '\n'.join(transformed_lines)