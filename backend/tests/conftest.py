"""
Pytest configuration and shared fixtures for QuickScribe backend tests.
"""
import os
import pytest
from unittest.mock import Mock, patch
from flask import Flask
import tempfile
from datetime import datetime, UTC

# Set testing environment before importing app
os.environ['TESTING'] = '1'
os.environ['LOCAL_AUTH_ENABLED'] = '1'
os.environ['FLASK_ENV'] = 'testing'

from app import create_app
from config import config


@pytest.fixture(scope='session')
def app():
    """Create and configure a test Flask application."""
    test_config = {
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'LOCAL_AUTH_ENABLED': True,
        'SECRET_KEY': 'test-secret-key'
    }
    
    app = create_app(test_config=test_config)
    
    # Create application context
    ctx = app.app_context()
    ctx.push()
    
    yield app
    
    ctx.pop()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner for the Flask application."""
    return app.test_cli_runner()


@pytest.fixture
def mock_config():
    """Mock the config object with test values."""
    with patch('config.config') as mock_cfg:
        mock_cfg.AZURE_COSMOS_ENDPOINT = 'https://test.documents.azure.com:443/'
        mock_cfg.AZURE_COSMOS_KEY = 'test_key'
        mock_cfg.AZURE_STORAGE_CONNECTION_STRING = 'test_connection_string'
        mock_cfg.AZURE_CLIENT_ID = 'test_client_id'
        mock_cfg.AZURE_CLIENT_SECRET = 'test_client_secret'
        mock_cfg.AZURE_TENANT_ID = 'test_tenant_id'
        mock_cfg.OPENAI_API_KEY = 'test_openai_key'
        mock_cfg.ASSEMBLYAI_API_KEY = 'test_assemblyai_key'
        mock_cfg.CALLBACK_URL = 'http://test-callback.com'
        yield mock_cfg


@pytest.fixture
def mock_cosmos_client():
    """Mock Azure Cosmos DB client."""
    with patch('azure.cosmos.CosmosClient') as mock_client:
        mock_db = Mock()
        mock_container = Mock()
        
        # Setup mock container methods
        mock_container.create_item.return_value = {'id': 'test_id'}
        mock_container.read_item.return_value = {'id': 'test_id'}
        mock_container.query_items.return_value = []
        mock_container.upsert_item.return_value = {'id': 'test_id'}
        mock_container.delete_item.return_value = None
        
        mock_db.get_container_client.return_value = mock_container
        mock_client.return_value.get_database_client.return_value = mock_db
        
        yield mock_client


@pytest.fixture
def mock_blob_client():
    """Mock Azure Blob Storage client."""
    with patch('azure.storage.blob.BlobServiceClient') as mock_client:
        mock_blob = Mock()
        mock_blob.upload_blob.return_value = None
        mock_blob.download_blob.return_value = Mock(readall=lambda: b'test_content')
        mock_blob.delete_blob.return_value = None
        mock_blob.generate_blob_sas.return_value = 'test_sas_token'
        
        mock_client.return_value.get_blob_client.return_value = mock_blob
        
        yield mock_client


@pytest.fixture
def mock_queue_client():
    """Mock Azure Storage Queue client."""
    with patch('azure.storage.queue.QueueClient') as mock_client:
        mock_queue = Mock()
        mock_queue.send_message.return_value = None
        mock_queue.receive_messages.return_value = []
        
        mock_client.return_value = mock_queue
        
        yield mock_client


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'id': 'test_user_123',
        'email': 'test@example.com',
        'name': 'Test User',
        'partitionKey': 'test_user_123',  # Required field
        'is_test_user': True,  # Fixed field name (was isTestUser)
        'plaudSettings': {
            'bearerToken': 'test_bearer_token',  # Required field
            'enableSync': False,
            'lastSyncTimestamp': None,
            'activeSyncStarted': None,
            'activeSyncToken': None
        },
        'tags': []
    }


@pytest.fixture
def sample_recording_data():
    """Sample recording data for testing."""
    return {
        'id': 'test_recording_123',
        'user_id': 'test_user_123',  # Fixed field name (was userId)
        'partitionKey': 'test_user_123',  # Required field
        'original_filename': 'test_audio.mp3',
        'unique_filename': 'test_audio_unique.mp3',  # Required field
        'title': 'Test Recording',
        'description': 'A test recording',
        'upload_timestamp': datetime.now(UTC).isoformat(),
        'recorded_timestamp': datetime.now(UTC).isoformat(),
        'duration_seconds': 120.5,
        'file_size_bytes': 1024000,
        'transcoding_status': 'completed',
        'blob_name': 'recordings/test_audio.mp3',
        'converted_blob_name': 'recordings/converted/test_audio.mp3',
        'source': 'upload',  # Fixed enum value
        'tagIds': [],  # Fixed field name (was tags)
        'transcoding_token': 'test_token_123'  # Required for callback validation
    }


@pytest.fixture
def sample_transcription_data():
    """Sample transcription data for testing."""
    return {
        'id': 'test_transcription_123',
        'partitionKey': 'test_user_123',  # Required field
        'recording_id': 'test_recording_123',
        'user_id': 'test_user_123',  # Fixed field name
        'transcription_status': 'completed',  # Fixed field name
        'transcript_text': 'This is a test transcription.',
        'diarized_transcript': 'Speaker 1: This is a test transcription.',
        'transcription_completed_at': datetime.now(UTC).isoformat(),
        'transcription_started_at': datetime.now(UTC).isoformat(),
        'az_transcription_id': 'azure_test_123',
        'speaker_mappings': {'Speaker 1': {'name': 'Test Speaker', 'reasoning': 'Test'}},
        'original_speaker_labels': {'Speaker 1': 'Test Speaker'}
    }


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
        tmp.write(b'fake audio content')
        tmp.flush()
        yield tmp.name
    
    # Cleanup
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def cleanup_environment():
    """Automatically cleanup environment after each test."""
    yield
    
    # Reset any global state if needed
    # Clear any cached handlers, etc.