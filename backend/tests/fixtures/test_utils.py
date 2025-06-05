"""
Test utilities and helper functions for QuickScribe tests.
"""
import json
import tempfile
import os
from datetime import datetime, UTC
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock


class MockCosmosContainer:
    """Mock Cosmos DB container for testing."""
    
    def __init__(self):
        self.items = {}
        self.call_count = {
            'create_item': 0,
            'read_item': 0,
            'upsert_item': 0,
            'query_items': 0,
            'delete_item': 0
        }
    
    def create_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Mock create_item operation."""
        self.call_count['create_item'] += 1
        item_id = item.get('id')
        if item_id in self.items:
            raise ValueError(f"Item with id {item_id} already exists")
        self.items[item_id] = item.copy()
        return item.copy()
    
    def read_item(self, item: str, partition_key: str) -> Dict[str, Any]:
        """Mock read_item operation."""
        self.call_count['read_item'] += 1
        if item not in self.items:
            from azure.cosmos.exceptions import CosmosResourceNotFoundError
            raise CosmosResourceNotFoundError("Item not found")
        return self.items[item].copy()
    
    def upsert_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Mock upsert_item operation."""
        self.call_count['upsert_item'] += 1
        item_id = item.get('id')
        self.items[item_id] = item.copy()
        return item.copy()
    
    def query_items(self, query: str, **kwargs) -> list:
        """Mock query_items operation."""
        self.call_count['query_items'] += 1
        # Simple mock - return all items for now
        # In real tests, you'd parse the query and filter accordingly
        return list(self.items.values())
    
    def delete_item(self, item: str, partition_key: str) -> None:
        """Mock delete_item operation."""
        self.call_count['delete_item'] += 1
        if item in self.items:
            del self.items[item]


class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_user(
        user_id: str = "test_user_123",
        email: str = "test@example.com",
        name: str = "Test User",
        is_test_user: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Create test user data."""
        base_data = {
            'id': user_id,
            'email': email,
            'name': name,
            'isTestUser': is_test_user,
            'plaudSettings': {
                'bearerToken': None,
                'enableSync': False,
                'lastSyncTimestamp': None,
                'activeSyncStarted': None,
                'activeSyncToken': None
            },
            'tags': []
        }
        base_data.update(kwargs)
        return base_data
    
    @staticmethod
    def create_recording(
        recording_id: str = "test_recording_123",
        user_id: str = "test_user_123",
        filename: str = "test_audio.mp3",
        **kwargs
    ) -> Dict[str, Any]:
        """Create test recording data."""
        base_data = {
            'id': recording_id,
            'userId': user_id,
            'original_filename': filename,
            'title': 'Test Recording',
            'description': 'A test recording',
            'upload_timestamp': datetime.now(UTC).isoformat(),
            'recorded_timestamp': datetime.now(UTC).isoformat(),
            'duration_seconds': 120.5,
            'file_size_bytes': 1024000,
            'transcoding_status': 'completed',
            'blob_name': f'recordings/{filename}',
            'converted_blob_name': f'recordings/converted/{filename}',
            'source': 'manual_upload',
            'tags': []
        }
        base_data.update(kwargs)
        return base_data
    
    @staticmethod
    def create_transcription(
        transcription_id: str = "test_transcription_123",
        recording_id: str = "test_recording_123",
        user_id: str = "test_user_123",
        **kwargs
    ) -> Dict[str, Any]:
        """Create test transcription data."""
        base_data = {
            'id': transcription_id,
            'recording_id': recording_id,
            'userId': user_id,
            'status': 'completed',
            'transcript_text': 'This is a test transcription.',
            'diarized_transcript': 'Speaker 1: This is a test transcription.',
            'confidence_score': 0.95,
            'created_timestamp': datetime.now(UTC).isoformat(),
            'completed_timestamp': datetime.now(UTC).isoformat(),
            'azure_transcription_id': 'azure_test_123',
            'transcription_service': 'azure_speech',
            'speaker_labels': {'Speaker 1': 'Test Speaker'}
        }
        base_data.update(kwargs)
        return base_data
    
    @staticmethod
    def create_tag(
        tag_id: str = "test_tag_123",
        name: str = "Test Tag",
        color: str = "#FF0000",
        **kwargs
    ) -> Dict[str, Any]:
        """Create test tag data."""
        from util import slugify
        base_data = {
            'id': tag_id,
            'name': name,
            'color': color,
            'slug': slugify(name)
        }
        base_data.update(kwargs)
        return base_data


class MockFileUpload:
    """Mock file upload for testing."""
    
    def __init__(self, filename: str = "test.mp3", content: bytes = b"fake audio content"):
        self.filename = filename
        self.content = content
        self._temp_file = None
    
    def __enter__(self):
        """Create temporary file for upload testing."""
        self._temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=os.path.splitext(self.filename)[1]
        )
        self._temp_file.write(self.content)
        self._temp_file.flush()
        return self._temp_file.name
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary file."""
        if self._temp_file:
            try:
                os.unlink(self._temp_file.name)
            except OSError:
                pass


def assert_datetime_fields_serialized(data: Dict[str, Any], *field_paths):
    """Assert that datetime fields are properly serialized as ISO strings."""
    for field_path in field_paths:
        # Navigate nested fields using dot notation
        current = data
        parts = field_path.split('.')
        
        for part in parts[:-1]:
            current = current.get(part, {})
        
        field_value = current.get(parts[-1])
        if field_value is not None:
            assert isinstance(field_value, str), f"Field {field_path} should be string, got {type(field_value)}"
            assert 'T' in field_value, f"Field {field_path} should be ISO format, got {field_value}"


def create_mock_azure_client(service_type: str = "cosmos"):
    """Create mock Azure client based on service type."""
    if service_type == "cosmos":
        mock_client = Mock()
        mock_db = Mock()
        mock_container = MockCosmosContainer()
        
        mock_db.get_container_client.return_value = mock_container
        mock_client.get_database_client.return_value = mock_db
        
        return mock_client
    
    elif service_type == "blob":
        mock_client = Mock()
        mock_blob = Mock()
        mock_blob.upload_blob.return_value = None
        mock_blob.download_blob.return_value = Mock(readall=lambda: b'test_content')
        mock_blob.delete_blob.return_value = None
        mock_blob.generate_blob_sas.return_value = 'test_sas_token'
        
        mock_client.get_blob_client.return_value = mock_blob
        return mock_client
    
    elif service_type == "queue":
        mock_client = Mock()
        mock_queue = Mock()
        mock_queue.send_message.return_value = None
        mock_queue.receive_messages.return_value = []
        
        mock_client.return_value = mock_queue
        return mock_client
    
    else:
        raise ValueError(f"Unknown service type: {service_type}")


def run_test_category(category: str) -> str:
    """Generate pytest command for specific test category."""
    commands = {
        'unit': 'pytest tests/unit/ -m unit -v',
        'integration': 'pytest tests/integration/ -m integration -v',
        'e2e': 'pytest tests/e2e/ -m e2e -v',
        'fast': 'pytest -m "not slow" -v',
        'all': 'pytest -v'
    }
    
    return commands.get(category, 'pytest -v')