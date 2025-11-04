"""
Integration tests for analysis execution with LLM timing and token tracking.

These tests validate the complete analysis execution workflow including:
- LLM integration with timing metrics
- Token counting and performance tracking
- Error handling for LLM failures
- Analysis result storage and retrieval
"""
import pytest
import json
import time
import uuid
from unittest.mock import patch, Mock
from datetime import datetime, UTC

from shared_quickscribe_py.cosmos import (
    create_analysis_type_handler,
    create_user_handler,
    create_transcription_handler
)


@pytest.mark.integration
class TestAnalysisExecution:
    """Test analysis execution with real database and mocked LLM."""
    
    @classmethod
    def setup_class(cls):
        """Set up test users, transcription, and analysis types."""
        cls.test_user_id = f"test-exec-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        # Create handlers
        cls.user_handler = create_user_handler()
        cls.analysis_type_handler = create_analysis_type_handler()
        cls.transcription_handler = create_transcription_handler()
        
        # Create test user
        cls.test_user = cls.user_handler.create_user(
            email=f"{cls.test_user_id}@test.com",
            name=f"Exec Test User {cls.test_user_id}",
            role="user"
        )
        cls.test_user.is_test_user = True
        cls.user_handler.save_user(cls.test_user)
        
        # Create test transcription
        cls.test_transcription_id = f"test-transcript-{uuid.uuid4().hex[:8]}"
        cls.test_transcription = {
            'id': cls.test_transcription_id,
            'user_id': cls.test_user_id,
            'partitionKey': cls.test_user_id,
            'recording_id': f"test-recording-{uuid.uuid4().hex[:8]}",
            'text': 'This is a test transcription with some content for analysis.',
            'diarized_transcript': 'Speaker 1: This is a test transcription with some content for analysis.',
            'analysisResults': []
        }
        
        # Save transcription to database
        cls.transcription_handler.container.create_item(cls.test_transcription)
        
        # Create test analysis type
        cls.test_analysis_type = cls.analysis_type_handler.create_analysis_type(
            name="test-execution-summary",
            title="Test Execution Summary",
            short_title="Test Summary",
            description="Analysis type for execution testing",
            icon="file-text",
            prompt="Please provide a brief summary of the following transcript: {transcript}",
            user_id=cls.test_user_id
        )
        
        print(f"Created test user: {cls.test_user_id}")
        print(f"Created test transcription: {cls.test_transcription_id}")
        print(f"Created test analysis type: {cls.test_analysis_type.id}")
        
    @classmethod
    def teardown_class(cls):
        """Clean up test data."""
        try:
            # Delete transcription
            cls.transcription_handler.container.delete_item(
                item=cls.test_transcription_id,
                partition_key=cls.test_user_id
            )
            
            # Delete analysis type
            cls.analysis_type_handler.delete_analysis_type(
                cls.test_analysis_type.id, cls.test_user_id
            )
            
            print(f"Cleaned up test data for user: {cls.test_user_id}")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def _setup_test_client(self):
        """Set up test client with authentication."""
        from app import app
        client = app.test_client()
        
        # Login test user
        with client.session_transaction() as sess:
            sess['user_id'] = self.test_user_id
            
        return client

    @patch('llms.send_prompt_to_llm_with_timing')
    def test_successful_analysis_execution_with_timing(self, mock_llm):
        """Test successful analysis execution with timing and token metrics."""
        # Mock LLM response with timing data
        mock_llm.return_value = {
            'content': 'This is a test summary of the transcript content.',
            'llmResponseTimeMs': 2500,
            'promptTokens': 45,
            'responseTokens': 12
        }
        
        client = self._setup_test_client()
        
        payload = {
            "transcriptionId": self.test_transcription_id,
            "analysisTypeId": self.test_analysis_type.id
        }
        
        response = client.post(
            '/api/ai/execute-analysis',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify response structure
        assert data['status'] == 'success'
        assert data['message'] == 'Analysis completed successfully'
        assert 'data' in data
        
        result = data['data']
        
        # Verify analysis result fields
        assert result['analysisType'] == 'test-execution-summary'
        assert result['analysisTypeId'] == self.test_analysis_type.id
        assert result['content'] == 'This is a test summary of the transcript content.'
        assert result['status'] == 'completed'
        
        # Verify timing and token metrics
        assert result['llmResponseTimeMs'] == 2500
        assert result['promptTokens'] == 45
        assert result['responseTokens'] == 12
        
        # Verify timestamp
        assert 'createdAt' in result
        created_at = datetime.fromisoformat(result['createdAt'].replace('Z', '+00:00'))
        assert isinstance(created_at, datetime)
        
        # Verify LLM was called with correct prompt
        mock_llm.assert_called_once()
        called_prompt = mock_llm.call_args[0][0]
        assert '{transcript}' not in called_prompt  # Should be replaced
        assert 'This is a test transcription' in called_prompt
        
        # Verify analysis result was saved to transcription
        updated_transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
        assert len(updated_transcription.analysisResults) == 1
        
        saved_result = updated_transcription.analysisResults[0]
        assert saved_result['analysisType'] == 'test-execution-summary'
        assert saved_result['llmResponseTimeMs'] == 2500

    @patch('llms.send_prompt_to_llm_with_timing')
    def test_analysis_execution_with_custom_prompt(self, mock_llm):
        """Test analysis execution with custom prompt override."""
        mock_llm.return_value = {
            'content': 'Custom analysis result.',
            'llmResponseTimeMs': 1800,
            'promptTokens': 30,
            'responseTokens': 8
        }
        
        client = self._setup_test_client()
        
        custom_prompt = "Provide a custom analysis: {transcript}"
        payload = {
            "transcriptionId": self.test_transcription_id,
            "analysisTypeId": self.test_analysis_type.id,
            "customPrompt": custom_prompt
        }
        
        response = client.post(
            '/api/ai/execute-analysis',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        # Verify custom prompt was used
        mock_llm.assert_called_once()
        called_prompt = mock_llm.call_args[0][0]
        assert 'Provide a custom analysis:' in called_prompt
        assert 'Please provide a brief summary' not in called_prompt  # Original prompt should not be used

    @patch('llms.send_prompt_to_llm_with_timing')
    def test_analysis_execution_llm_failure(self, mock_llm):
        """Test analysis execution when LLM fails."""
        # Mock LLM failure
        mock_llm.side_effect = Exception("LLM request failed after 5000ms: Connection timeout")
        
        client = self._setup_test_client()
        
        payload = {
            "transcriptionId": self.test_transcription_id,
            "analysisTypeId": self.test_analysis_type.id
        }
        
        response = client.post(
            '/api/ai/execute-analysis',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        # Verify error response
        assert data['status'] == 'error'
        assert data['message'] == 'Analysis failed'
        assert 'data' in data
        
        failed_result = data['data']
        assert failed_result['status'] == 'failed'
        assert failed_result['content'] == ''
        assert 'LLM request failed' in failed_result['errorMessage']
        
        # Verify failed result was saved to transcription
        updated_transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
        # Should have 2 results now (success from previous test + this failure)
        failed_results = [r for r in updated_transcription.analysisResults if r['status'] == 'failed']
        assert len(failed_results) == 1
        assert 'LLM request failed' in failed_results[0]['errorMessage']

    def test_analysis_execution_invalid_transcription(self):
        """Test analysis execution with non-existent transcription."""
        client = self._setup_test_client()
        
        payload = {
            "transcriptionId": "non-existent-transcription-id",
            "analysisTypeId": self.test_analysis_type.id
        }
        
        response = client.post(
            '/api/ai/execute-analysis',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Transcription not found'

    def test_analysis_execution_invalid_analysis_type(self):
        """Test analysis execution with non-existent analysis type."""
        client = self._setup_test_client()
        
        payload = {
            "transcriptionId": self.test_transcription_id,
            "analysisTypeId": "non-existent-analysis-type-id"
        }
        
        response = client.post(
            '/api/ai/execute-analysis',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['error'] == 'Analysis type not found'

    def test_analysis_execution_empty_transcript(self):
        """Test analysis execution with empty transcript."""
        # Create transcription with no text
        empty_transcript_id = f"empty-transcript-{uuid.uuid4().hex[:8]}"
        empty_transcription = {
            'id': empty_transcript_id,
            'user_id': self.test_user_id,
            'partitionKey': self.test_user_id,
            'recording_id': f"test-recording-{uuid.uuid4().hex[:8]}",
            'text': None,
            'diarized_transcript': None,
            'analysisResults': []
        }
        
        # Save empty transcription
        self.transcription_handler.container.create_item(empty_transcription)
        
        try:
            client = self._setup_test_client()
            
            payload = {
                "transcriptionId": empty_transcript_id,
                "analysisTypeId": self.test_analysis_type.id
            }
            
            response = client.post(
                '/api/ai/execute-analysis',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['error'] == 'No transcript content available for analysis'
            
        finally:
            # Clean up empty transcription
            self.transcription_handler.container.delete_item(
                item=empty_transcript_id,
                partition_key=self.test_user_id
            )

    def test_analysis_execution_request_validation(self):
        """Test request validation for analysis execution."""
        client = self._setup_test_client()
        
        # Test missing required fields
        invalid_payloads = [
            {},  # Empty payload
            {"transcriptionId": "test"},  # Missing analysisTypeId
            {"analysisTypeId": "test"},  # Missing transcriptionId
            {"transcriptionId": "", "analysisTypeId": "test"},  # Empty transcriptionId
            {"transcriptionId": "test", "analysisTypeId": ""},  # Empty analysisTypeId
        ]
        
        for payload in invalid_payloads:
            response = client.post(
                '/api/ai/execute-analysis',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'error' in data
            assert 'Validation error' in data['error']

    def test_analysis_execution_user_isolation(self):
        """Test that users can only analyze their own transcriptions."""
        # Create another user
        other_user_id = f"other-user-{uuid.uuid4().hex[:8]}"
        other_user = self.user_handler.create_user(
            email=f"{other_user_id}@test.com",
            name=f"Other User {other_user_id}",
            role="user"
        )
        other_user.is_test_user = True
        self.user_handler.save_user(other_user)
        
        try:
            # Set up client with other user
            from app import app
            client = app.test_client()
            
            with client.session_transaction() as sess:
                sess['user_id'] = other_user_id
            
            # Try to analyze first user's transcription
            payload = {
                "transcriptionId": self.test_transcription_id,  # Belongs to test_user_id
                "analysisTypeId": self.test_analysis_type.id
            }
            
            response = client.post(
                '/api/ai/execute-analysis',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 403
            data = json.loads(response.data)
            assert data['error'] == 'Insufficient permissions'
            
        finally:
            # Clean up other user (if user handler supports deletion)
            pass

    @patch('llms.send_prompt_to_llm_with_timing')
    def test_multiple_analysis_results_accumulation(self, mock_llm):
        """Test that multiple analysis results accumulate correctly."""
        # Create second analysis type
        second_analysis_type = self.analysis_type_handler.create_analysis_type(
            name="test-execution-keywords",
            title="Test Keywords",
            short_title="Keywords",
            description="Extract keywords",
            icon="tag",
            prompt="Extract key words from: {transcript}",
            user_id=self.test_user_id
        )
        
        try:
            mock_llm.return_value = {
                'content': 'keywords, test, analysis',
                'llmResponseTimeMs': 1500,
                'promptTokens': 25,
                'responseTokens': 5
            }
            
            client = self._setup_test_client()
            
            payload = {
                "transcriptionId": self.test_transcription_id,
                "analysisTypeId": second_analysis_type.id
            }
            
            response = client.post(
                '/api/ai/execute-analysis',
                data=json.dumps(payload),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            
            # Verify transcription now has multiple analysis results
            updated_transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            
            # Should have results from previous tests plus this new one
            analysis_types_in_results = {r['analysisType'] for r in updated_transcription.analysisResults}
            assert 'test-execution-summary' in analysis_types_in_results
            assert 'test-execution-keywords' in analysis_types_in_results
            
        finally:
            # Clean up second analysis type
            self.analysis_type_handler.delete_analysis_type(
                second_analysis_type.id, self.test_user_id
            )


@pytest.mark.unit
class TestLLMTimingFunction:
    """Unit tests for the LLM timing functionality."""
    
    @patch('requests.post')
    def test_send_prompt_to_llm_with_timing_success(self, mock_post):
        """Test successful LLM call with timing extraction."""
        from llms import send_prompt_to_llm_with_timing
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Test LLM response"}
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        test_prompt = "Test prompt for timing"
        
        # Call function
        result = send_prompt_to_llm_with_timing(test_prompt)
        
        # Verify structure
        assert 'content' in result
        assert 'llmResponseTimeMs' in result
        assert 'promptTokens' in result
        assert 'responseTokens' in result
        
        # Verify values
        assert result['content'] == "Test LLM response"
        assert result['promptTokens'] == 100
        assert result['responseTokens'] == 25
        assert isinstance(result['llmResponseTimeMs'], int)
        assert result['llmResponseTimeMs'] > 0  # Should have some timing
    
    @patch('requests.post')
    def test_send_prompt_to_llm_with_timing_failure(self, mock_post):
        """Test LLM call failure with timing included in error."""
        from llms import send_prompt_to_llm_with_timing
        import requests
        
        # Mock failed response
        mock_post.side_effect = requests.RequestException("Network error")
        
        test_prompt = "Test prompt for failure"
        
        # Call function and expect exception
        with pytest.raises(Exception) as exc_info:
            send_prompt_to_llm_with_timing(test_prompt)
        
        # Verify timing is included in error message
        error_message = str(exc_info.value)
        assert "LLM request failed after" in error_message
        assert "ms:" in error_message
        assert "Network error" in error_message

    @patch('requests.post')
    def test_send_prompt_to_llm_with_timing_missing_usage(self, mock_post):
        """Test LLM call when usage information is missing."""
        from llms import send_prompt_to_llm_with_timing
        
        # Mock response without usage data
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Test response without usage"}
            }]
            # No usage field
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = send_prompt_to_llm_with_timing("test prompt")
        
        # Should handle missing usage gracefully
        assert result['content'] == "Test response without usage"
        assert result['promptTokens'] is None
        assert result['responseTokens'] is None
        assert isinstance(result['llmResponseTimeMs'], int)