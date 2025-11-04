"""
Unit tests for UserHandler class.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

from shared_quickscribe_py.cosmos import UserHandler, User, PlaudSettings
from shared_quickscribe_py.cosmos import Tag


@pytest.mark.unit
class TestUserHandler:
    """Unit tests for UserHandler."""
    
    @pytest.fixture
    def mock_container(self):
        """Mock Cosmos DB container."""
        container = Mock()
        container.create_item.return_value = {'id': 'test_user'}
        container.read_item.return_value = {'id': 'test_user'}
        container.upsert_item.return_value = {'id': 'test_user'}
        container.replace_item.return_value = {'id': 'test_user'}
        container.query_items.return_value = []
        return container
    
    @pytest.fixture
    def user_handler(self, mock_container):
        """Create UserHandler with mocked container."""
        # Mock the container at the handler initialization
        with patch.object(UserHandler, '__init__', lambda self: None):
            handler = UserHandler()
            handler.container = mock_container
            yield handler
    
    def test_create_user_success(self, user_handler, mock_container, sample_user_data):
        """Test successful user creation."""
        # Setup
        mock_container.create_item.return_value = sample_user_data
        
        # Execute - create_user generates its own ID
        result = user_handler.create_user(
            email=sample_user_data['email'],
            name=sample_user_data['name']
        )
        
        # Assert
        assert isinstance(result, User)
        assert result.email == sample_user_data['email']
        assert result.name == sample_user_data['name']
        mock_container.create_item.assert_called_once()
    
    def test_get_user_success(self, user_handler, mock_container, sample_user_data):
        """Test successful user retrieval."""
        # Setup
        mock_container.read_item.return_value = sample_user_data
        
        # Execute
        user = user_handler.get_user(sample_user_data['id'])
        
        # Assert
        assert isinstance(user, User)
        assert user.id == sample_user_data['id']
        assert user.email == sample_user_data['email']
        mock_container.read_item.assert_called_once_with(
            item=sample_user_data['id'],
            partition_key='user'  # Fixed partition key
        )
    
    def test_get_user_not_found(self, user_handler, mock_container):
        """Test user retrieval when user doesn't exist."""
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        
        # Setup - CosmosResourceNotFoundError needs status_code and message
        error = CosmosResourceNotFoundError(status_code=404, message="User not found")
        mock_container.read_item.side_effect = error
        
        # Execute & Assert
        user = user_handler.get_user('nonexistent_user')
        assert user is None
    
    def test_save_user_with_datetime_serialization(self, user_handler, mock_container, sample_user_data):
        """Test saving user with datetime fields properly serialized."""
        # Setup
        user = User(**sample_user_data)
        user.plaudSettings.activeSyncStarted = datetime.now(UTC)
        user.plaudSettings.lastSyncTimestamp = datetime.now(UTC)
        
        # Mock replace_item instead of upsert_item
        mock_container.replace_item.return_value = sample_user_data
        
        # Execute
        user_handler.save_user(user)
        
        # Assert
        mock_container.replace_item.assert_called_once()
        call_args = mock_container.replace_item.call_args[1]['body']
        
        # Check that datetime fields are serialized as ISO strings
        plaud_settings = call_args['plaudSettings']
        assert isinstance(plaud_settings['activeSyncStarted'], str)
        assert isinstance(plaud_settings['lastSyncTimestamp'], str)
        assert 'T' in plaud_settings['activeSyncStarted']  # ISO format check
    
    def test_create_tag(self, user_handler, mock_container, sample_user_data):
        """Test creating a tag for a user."""
        # Setup - ensure user has tags array and no duplicates
        test_user_data = sample_user_data.copy()
        test_user_data['tags'] = []  # Empty tags to avoid duplicates
        
        # Mock get_user to return the user
        mock_container.read_item.return_value = test_user_data
        # Mock save_user to return success
        updated_user_data = test_user_data.copy()
        updated_user_data['tags'] = [{'id': 'test-tag', 'name': 'Test Tag', 'color': '#FF0000'}]
        mock_container.replace_item.return_value = updated_user_data
        
        # Execute - use create_tag method
        result_tag = user_handler.create_tag(
            user_id=sample_user_data['id'],
            name='Test Tag',
            color='#FF0000'
        )
        
        # Assert
        assert result_tag is not None
        assert isinstance(result_tag, Tag)
        assert result_tag.name == 'Test Tag'
        assert result_tag.color == '#FF0000'
        mock_container.read_item.assert_called()  # get_user called
        mock_container.replace_item.assert_called()  # save_user called
    
    def test_get_test_users(self, user_handler, mock_container):
        """Test retrieving test users."""
        # Setup
        test_users = [
            {'id': 'test1', 'isTestUser': True, 'name': 'Test User 1'},
            {'id': 'test2', 'isTestUser': True, 'name': 'Test User 2'}
        ]
        mock_container.query_items.return_value = test_users
        
        # Execute
        result = user_handler.get_test_users()
        
        # Assert
        assert len(result) == 2
        assert result[0]['name'] == 'Test User 1'
        mock_container.query_items.assert_called_once()
    
    def test_update_user_partial(self, user_handler, mock_container, sample_user_data):
        """Test partial user update."""
        # Setup
        mock_container.read_item.return_value = sample_user_data
        updated_data = sample_user_data.copy()
        updated_data['name'] = 'Updated Name'
        mock_container.upsert_item.return_value = updated_data
        
        # Execute
        result = user_handler.update_user(sample_user_data['id'], name='Updated Name')
        
        # Assert
        if result:
            assert result.name == 'Updated Name'
        mock_container.read_item.assert_called_once()
        mock_container.replace_item.assert_called_once()


@pytest.mark.unit
class TestPlaudSettings:
    """Unit tests for PlaudSettings model."""
    
    def test_datetime_field_validation(self):
        """Test datetime field validation and serialization."""
        # Setup
        now = datetime.now(UTC)
        settings = PlaudSettings(
            bearerToken='test_token',  # Required field
            activeSyncStarted=now,
            lastSyncTimestamp=now
        )
        
        # Assert datetime objects are preserved
        assert isinstance(settings.activeSyncStarted, datetime)
        assert isinstance(settings.lastSyncTimestamp, datetime)
    
    def test_datetime_serialization(self):
        """Test datetime serialization to ISO string."""
        # Setup
        now = datetime.now(UTC)
        settings = PlaudSettings(
            bearerToken='test_token',  # Required field
            activeSyncStarted=now,
            lastSyncTimestamp=now
        )
        
        # Execute
        serialized = settings.model_dump()
        
        # Assert ISO string format
        assert isinstance(serialized['activeSyncStarted'], str)
        assert isinstance(serialized['lastSyncTimestamp'], str)
        assert 'T' in serialized['activeSyncStarted']
    
    def test_iso_string_parsing(self):
        """Test parsing ISO string back to datetime."""
        # Setup
        iso_string = "2024-01-01T12:00:00Z"
        settings = PlaudSettings(
            bearerToken='test_token',  # Required field
            activeSyncStarted=iso_string,
            lastSyncTimestamp=iso_string
        )
        
        # Assert datetime objects are created
        assert isinstance(settings.activeSyncStarted, datetime)
        assert isinstance(settings.lastSyncTimestamp, datetime)
        assert settings.activeSyncStarted.year == 2024