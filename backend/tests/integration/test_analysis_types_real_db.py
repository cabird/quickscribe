"""
Real database integration tests for analysis types functionality.

These tests create actual test users and interact with the real CosmosDB
to validate the complete analysis types system including CRUD operations,
user isolation, and API endpoints.
"""
import pytest
import uuid
import time
import json
from datetime import datetime, UTC
from flask import Flask

from shared_quickscribe_py.cosmos import create_analysis_type_handler, create_user_handler
from shared_quickscribe_py.cosmos import AnalysisTypeHandler
from shared_quickscribe_py.cosmos import UserHandler


@pytest.mark.integration
class TestAnalysisTypesRealDatabase:
    """Test analysis types with real database operations."""
    
    @classmethod
    def setup_class(cls):
        """Create test user and initialize database connections."""
        cls.test_user_id = f"test-analysis-types-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        cls.test_user_id_2 = f"test-analysis-types-2-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        # Create handlers
        cls.analysis_type_handler: AnalysisTypeHandler = create_analysis_type_handler()
        cls.user_handler: UserHandler = create_user_handler()
        
        # Create test users
        cls.test_user = cls.user_handler.create_user(
            email=f"{cls.test_user_id}@test.com",
            name=f"Test User {cls.test_user_id}",
            role="user"
        )
        cls.test_user.is_test_user = True
        cls.user_handler.save_user(cls.test_user)
        
        cls.test_user_2 = cls.user_handler.create_user(
            email=f"{cls.test_user_id_2}@test.com", 
            name=f"Test User {cls.test_user_id_2}",
            role="user"
        )
        cls.test_user_2.is_test_user = True
        cls.user_handler.save_user(cls.test_user_2)
        
        print(f"Created test users: {cls.test_user_id} and {cls.test_user_id_2}")
        
    @classmethod
    def teardown_class(cls):
        """Clean up test users and all associated data."""
        try:
            # Delete any custom analysis types created during tests
            user_types = cls.analysis_type_handler.get_analysis_types_for_user(cls.test_user_id)
            for analysis_type in user_types:
                if not analysis_type.isBuiltIn and analysis_type.userId == cls.test_user_id:
                    cls.analysis_type_handler.delete_analysis_type(analysis_type.id, cls.test_user_id)
                    
            user_types_2 = cls.analysis_type_handler.get_analysis_types_for_user(cls.test_user_id_2)
            for analysis_type in user_types_2:
                if not analysis_type.isBuiltIn and analysis_type.userId == cls.test_user_id_2:
                    cls.analysis_type_handler.delete_analysis_type(analysis_type.id, cls.test_user_id_2)
            
            # Delete test users
            # Note: This assumes the user handler has a delete method
            # If not available, we'd need to implement cleanup differently
            print(f"Cleaned up test users: {cls.test_user_id} and {cls.test_user_id_2}")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def test_create_custom_analysis_type(self):
        """Test creating a custom analysis type in real database."""
        custom_type = self.analysis_type_handler.create_analysis_type(
            name="test-custom-summary",
            title="Test Custom Summary",
            description="A test custom summary analysis",
            icon="file-text",
            prompt="Create a test summary: {transcript}",
            user_id=self.test_user_id
        )
        
        assert custom_type is not None
        assert custom_type.name == "test-custom-summary"
        assert custom_type.title == "Test Custom Summary"
        assert custom_type.userId == self.test_user_id
        assert custom_type.isBuiltIn is False
        assert custom_type.isActive is True
        assert custom_type.partitionKey == self.test_user_id
        assert isinstance(custom_type.createdAt, datetime)
        assert isinstance(custom_type.updatedAt, datetime)

    def test_list_analysis_types_includes_builtin_and_custom(self):
        """Test that listing returns both built-in and user's custom types."""
        # First, ensure we have some built-in types by checking if any exist
        builtin_types = self.analysis_type_handler.get_builtin_analysis_types()
        print(f"Found {len(builtin_types)} built-in analysis types")
        
        # Create a custom type for this user
        custom_type = self.analysis_type_handler.create_analysis_type(
            name="test-list-custom",
            title="Test List Custom",
            description="Custom type for list testing",
            icon="tag",
            prompt="Test prompt: {transcript}",
            user_id=self.test_user_id
        )
        
        # Get all types for user
        all_types = self.analysis_type_handler.get_analysis_types_for_user(self.test_user_id)
        
        # Should include built-in types plus our custom type
        assert len(all_types) >= len(builtin_types) + 1
        
        # Check that we have both built-in and custom types
        has_builtin = any(t.isBuiltIn for t in all_types)
        has_custom = any(not t.isBuiltIn and t.userId == self.test_user_id for t in all_types)
        
        assert has_builtin, "Should include built-in analysis types"
        assert has_custom, "Should include user's custom analysis types"
        
        # Verify our custom type is in the list
        custom_in_list = any(t.name == "test-list-custom" for t in all_types)
        assert custom_in_list, "Should include the custom type we just created"

    def test_update_custom_analysis_type(self):
        """Test updating a custom analysis type."""
        # Create a custom type
        custom_type = self.analysis_type_handler.create_analysis_type(
            name="test-update-type",
            title="Original Title",
            description="Original description",
            icon="file-text",
            prompt="Original prompt: {transcript}",
            user_id=self.test_user_id
        )
        
        # Update it
        updates = {
            "title": "Updated Title",
            "description": "Updated description",
            "prompt": "Updated prompt: {transcript}"
        }
        
        updated_type = self.analysis_type_handler.update_analysis_type(
            custom_type.id, self.test_user_id, updates
        )
        
        assert updated_type is not None
        assert updated_type.title == "Updated Title"
        assert updated_type.description == "Updated description"
        assert updated_type.prompt == "Updated prompt: {transcript}"
        assert updated_type.name == "test-update-type"  # Name should remain the same
        assert updated_type.updatedAt > updated_type.createdAt

    def test_delete_custom_analysis_type(self):
        """Test deleting a custom analysis type."""
        # Create a custom type
        custom_type = self.analysis_type_handler.create_analysis_type(
            name="test-delete-type",
            title="Type to Delete",
            description="This type will be deleted",
            icon="trash",
            prompt="Delete me: {transcript}",
            user_id=self.test_user_id
        )
        
        # Verify it exists
        retrieved = self.analysis_type_handler.get_analysis_type_by_id(
            custom_type.id, self.test_user_id
        )
        assert retrieved is not None
        
        # Delete it
        success = self.analysis_type_handler.delete_analysis_type(
            custom_type.id, self.test_user_id
        )
        assert success is True
        
        # Verify it's gone
        deleted = self.analysis_type_handler.get_analysis_type_by_id(
            custom_type.id, self.test_user_id
        )
        assert deleted is None

    def test_user_isolation_custom_types(self):
        """Test that users can't see other users' custom types."""
        # User 1 creates a custom type
        user1_type = self.analysis_type_handler.create_analysis_type(
            name="user1-private-type",
            title="User 1 Private Type",
            description="This should only be visible to user 1",
            icon="lock",
            prompt="Private prompt: {transcript}",
            user_id=self.test_user_id
        )
        
        # User 2 creates a custom type
        user2_type = self.analysis_type_handler.create_analysis_type(
            name="user2-private-type", 
            title="User 2 Private Type",
            description="This should only be visible to user 2",
            icon="shield",
            prompt="Another private prompt: {transcript}",
            user_id=self.test_user_id_2
        )
        
        # Get types for each user
        user1_types = self.analysis_type_handler.get_analysis_types_for_user(self.test_user_id)
        user2_types = self.analysis_type_handler.get_analysis_types_for_user(self.test_user_id_2)
        
        # User 1 should see their own type but not user 2's
        user1_custom_types = [t for t in user1_types if not t.isBuiltIn]
        user1_has_own = any(t.name == "user1-private-type" for t in user1_custom_types)
        user1_has_other = any(t.name == "user2-private-type" for t in user1_custom_types)
        
        assert user1_has_own, "User 1 should see their own custom type"
        assert not user1_has_other, "User 1 should not see user 2's custom type"
        
        # User 2 should see their own type but not user 1's
        user2_custom_types = [t for t in user2_types if not t.isBuiltIn]
        user2_has_own = any(t.name == "user2-private-type" for t in user2_custom_types)
        user2_has_other = any(t.name == "user1-private-type" for t in user2_custom_types)
        
        assert user2_has_own, "User 2 should see their own custom type"
        assert not user2_has_other, "User 2 should not see user 1's custom type"

    def test_cannot_modify_builtin_types(self):
        """Test that built-in types are protected from modification."""
        builtin_types = self.analysis_type_handler.get_builtin_analysis_types()
        
        if not builtin_types:
            pytest.skip("No built-in types available for testing")
            
        builtin_type = builtin_types[0]
        
        # Try to update a built-in type (should fail)
        updated = self.analysis_type_handler.update_analysis_type(
            builtin_type.id, "global", {"title": "Modified Title"}
        )
        assert updated is None, "Should not be able to update built-in types"
        
        # Try to delete a built-in type (should fail)
        deleted = self.analysis_type_handler.delete_analysis_type(
            builtin_type.id, "global"
        )
        assert deleted is False, "Should not be able to delete built-in types"

    def test_name_uniqueness_per_user(self):
        """Test that analysis type names must be unique per user."""
        # Create first custom type
        first_type = self.analysis_type_handler.create_analysis_type(
            name="unique-name-test",
            title="First Type",
            description="First type with this name",
            icon="file-text",
            prompt="First prompt: {transcript}",
            user_id=self.test_user_id
        )
        assert first_type is not None
        
        # Try to create second type with same name for same user (should fail)
        second_type = self.analysis_type_handler.create_analysis_type(
            name="unique-name-test",  # Same name
            title="Second Type",
            description="Second type with same name",
            icon="tag",
            prompt="Second prompt: {transcript}",
            user_id=self.test_user_id  # Same user
        )
        assert second_type is None, "Should not allow duplicate names for same user"
        
        # But different user should be able to use the same name
        third_type = self.analysis_type_handler.create_analysis_type(
            name="unique-name-test",  # Same name
            title="Third Type",
            description="Third type for different user",
            icon="star",
            prompt="Third prompt: {transcript}",
            user_id=self.test_user_id_2  # Different user
        )
        assert third_type is not None, "Different users should be able to use same name"

    def test_get_analysis_type_by_id(self):
        """Test retrieving a specific analysis type by ID."""
        # Create a custom type
        custom_type = self.analysis_type_handler.create_analysis_type(
            name="test-get-by-id",
            title="Test Get By ID",
            description="Type for testing ID retrieval",
            icon="search",
            prompt="Get by ID test: {transcript}",
            user_id=self.test_user_id
        )
        
        # Retrieve by ID
        retrieved = self.analysis_type_handler.get_analysis_type_by_id(
            custom_type.id, self.test_user_id
        )
        
        assert retrieved is not None
        assert retrieved.id == custom_type.id
        assert retrieved.name == "test-get-by-id"
        assert retrieved.title == "Test Get By ID"
        
        # Test with wrong partition key (should fail)
        wrong_partition = self.analysis_type_handler.get_analysis_type_by_id(
            custom_type.id, self.test_user_id_2
        )
        assert wrong_partition is None


@pytest.mark.integration 
class TestAnalysisTypesAPI:
    """Test analysis types API endpoints with real database."""
    
    @classmethod
    def setup_class(cls):
        """Set up test client and users."""
        from app import app
        cls.client = app.test_client()
        cls.app = app
        
        # Create test user (reusing the handler from above)
        cls.test_user_id = f"test-api-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        cls.user_handler = create_user_handler()
        cls.analysis_type_handler = create_analysis_type_handler()
        
        cls.test_user = cls.user_handler.create_user(
            email=f"{cls.test_user_id}@test.com",
            name=f"API Test User {cls.test_user_id}",
            role="user"
        )
        cls.test_user.is_test_user = True
        cls.user_handler.save_user(cls.test_user)
        
    @classmethod
    def teardown_class(cls):
        """Clean up API test data."""
        try:
            # Delete custom analysis types
            user_types = cls.analysis_type_handler.get_analysis_types_for_user(cls.test_user_id)
            for analysis_type in user_types:
                if not analysis_type.isBuiltIn and analysis_type.userId == cls.test_user_id:
                    cls.analysis_type_handler.delete_analysis_type(analysis_type.id, cls.test_user_id)
        except Exception as e:
            print(f"Error during API test cleanup: {e}")

    def _login_test_user(self):
        """Helper to log in the test user for local auth."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id

    def test_get_analysis_types_endpoint(self):
        """Test GET /api/ai/analysis-types endpoint."""
        self._login_test_user()
        
        response = self.client.get('/api/ai/analysis-types')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'data' in data
        assert 'count' in data
        assert isinstance(data['data'], list)
        assert data['count'] >= 0

    def test_create_analysis_type_endpoint(self):
        """Test POST /api/ai/analysis-types endpoint."""
        self._login_test_user()
        
        payload = {
            "name": "api-test-type",
            "title": "API Test Type",
            "description": "Created via API test",
            "icon": "api",
            "prompt": "API test prompt: {transcript}"
        }
        
        response = self.client.post(
            '/api/ai/analysis-types',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['data']['name'] == 'api-test-type'
        assert data['data']['title'] == 'API Test Type'
        assert data['data']['userId'] == self.test_user_id

    def test_create_analysis_type_validation(self):
        """Test validation on POST /api/ai/analysis-types endpoint."""
        self._login_test_user()
        
        # Test missing required fields
        payload = {
            "name": "incomplete-type"
            # Missing title, description, icon, prompt
        }
        
        response = self.client.post(
            '/api/ai/analysis-types',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Missing required fields' in data['error']

    def test_update_analysis_type_endpoint(self):
        """Test PUT /api/ai/analysis-types/{id} endpoint."""
        self._login_test_user()
        
        # First create a type to update
        created_type = self.analysis_type_handler.create_analysis_type(
            name="api-update-test",
            title="Original API Title", 
            description="Original description",
            icon="edit",
            prompt="Original prompt: {transcript}",
            user_id=self.test_user_id
        )
        
        # Update it via API
        update_payload = {
            "title": "Updated API Title",
            "description": "Updated via API"
        }
        
        response = self.client.put(
            f'/api/ai/analysis-types/{created_type.id}',
            data=json.dumps(update_payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['data']['title'] == 'Updated API Title'
        assert data['data']['description'] == 'Updated via API'

    def test_delete_analysis_type_endpoint(self):
        """Test DELETE /api/ai/analysis-types/{id} endpoint."""
        self._login_test_user()
        
        # Create a type to delete
        created_type = self.analysis_type_handler.create_analysis_type(
            name="api-delete-test",
            title="API Delete Test",
            description="Will be deleted via API",
            icon="trash",
            prompt="Delete test: {transcript}",
            user_id=self.test_user_id
        )
        
        # Delete it via API
        response = self.client.delete(f'/api/ai/analysis-types/{created_type.id}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert 'deleted successfully' in data['message']
        
        # Verify it's actually deleted
        deleted_type = self.analysis_type_handler.get_analysis_type_by_id(
            created_type.id, self.test_user_id
        )
        assert deleted_type is None

    def test_execute_analysis_endpoint_structure(self):
        """Test POST /api/ai/execute-analysis endpoint structure (without actual LLM)."""
        self._login_test_user()
        
        # For this test, we just validate the endpoint structure
        # Real LLM integration would be tested separately
        payload = {
            "transcriptionId": "test-transcription-id",
            "analysisTypeId": "test-analysis-type-id"
        }
        
        response = self.client.post(
            '/api/ai/execute-analysis',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # We expect this to fail since transcription doesn't exist
        # But it should fail with proper error handling, not crash
        assert response.status_code in [400, 404]
        data = json.loads(response.data)
        assert 'error' in data

    def test_authentication_required(self):
        """Test that all endpoints require authentication."""
        endpoints = [
            ('GET', '/api/ai/analysis-types'),
            ('POST', '/api/ai/analysis-types'),
            ('PUT', '/api/ai/analysis-types/test-id'),
            ('DELETE', '/api/ai/analysis-types/test-id'),
            ('POST', '/api/ai/execute-analysis')
        ]
        
        for method, endpoint in endpoints:
            if method == 'GET':
                response = self.client.get(endpoint)
            elif method == 'POST':
                response = self.client.post(endpoint, data='{}', content_type='application/json')
            elif method == 'PUT':
                response = self.client.put(endpoint, data='{}', content_type='application/json')
            elif method == 'DELETE':
                response = self.client.delete(endpoint)
                
            # Should require authentication
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should require auth"