#!/usr/bin/env python3
"""
End-to-end test script for the dynamic analysis types system.

This script tests the complete workflow from analysis type creation
through analysis execution with real LLM calls and timing metrics.

Usage:
    python test_dynamic_analysis_e2e.py [--no-llm]
    
    --no-llm: Skip tests that require actual LLM calls
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, UTC

# Add the current directory to Python path for imports
sys.path.append('.')

from db_handlers.handler_factory import (
    create_analysis_type_handler,
    create_user_handler, 
    create_transcription_handler
)
from llms import send_prompt_to_llm_with_timing


class DynamicAnalysisE2ETest:
    """End-to-end test for the dynamic analysis types system."""
    
    def __init__(self, skip_llm_tests=False):
        self.skip_llm_tests = skip_llm_tests
        self.test_user_id = f"e2e-test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        self.test_results = []
        
        # Initialize handlers
        self.user_handler = create_user_handler()
        self.analysis_type_handler = create_analysis_type_handler()
        self.transcription_handler = create_transcription_handler()
        
        # Test data
        self.test_user = None
        self.test_transcription_id = None
        self.test_analysis_type = None
        
    def run_all_tests(self):
        """Run all end-to-end tests."""
        print(f"🚀 Starting Dynamic Analysis Types E2E Tests")
        print(f"Test User ID: {self.test_user_id}")
        print(f"Skip LLM Tests: {self.skip_llm_tests}")
        print("-" * 60)
        
        try:
            self.setup_test_data()
            
            # Core functionality tests
            self.test_builtin_analysis_types_exist()
            self.test_create_custom_analysis_type()
            self.test_analysis_type_user_isolation()
            self.test_crud_operations()
            
            # Analysis execution tests
            self.test_create_test_transcription()
            if not self.skip_llm_tests:
                self.test_analysis_execution_with_llm()
                self.test_analysis_execution_timing_metrics()
                self.test_custom_prompt_execution()
            else:
                print("⏭️  Skipping LLM tests as requested")
                
            self.test_analysis_result_persistence()
            self.test_multiple_analysis_accumulation()
            
            # Cleanup
            self.cleanup_test_data()
            
            # Report results
            self.print_test_results()
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {e}")
            self.cleanup_test_data()
            return False
            
        return all(result['passed'] for result in self.test_results)
    
    def setup_test_data(self):
        """Set up test user and basic data."""
        print("📋 Setting up test data...")
        
        # Create test user
        self.test_user = self.user_handler.create_user(
            email=f"{self.test_user_id}@e2etest.com",
            name=f"E2E Test User {self.test_user_id}",
            role="user"
        )
        self.test_user.is_test_user = True
        self.user_handler.save_user(self.test_user)
        
        print(f"✅ Created test user: {self.test_user_id}")
    
    def cleanup_test_data(self):
        """Clean up all test data."""
        print("🧹 Cleaning up test data...")
        
        try:
            # Delete test transcription
            if self.test_transcription_id:
                self.transcription_handler.container.delete_item(
                    item=self.test_transcription_id,
                    partition_key=self.test_user_id
                )
            
            # Delete custom analysis types
            user_types = self.analysis_type_handler.get_analysis_types_for_user(self.test_user_id)
            for analysis_type in user_types:
                if not analysis_type.isBuiltIn and analysis_type.userId == self.test_user_id:
                    self.analysis_type_handler.delete_analysis_type(analysis_type.id, self.test_user_id)
            
            print("✅ Cleaned up test data")
            
        except Exception as e:
            print(f"⚠️  Warning during cleanup: {e}")
    
    def log_test_result(self, test_name, passed, message="", details=None):
        """Log a test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if message:
            print(f"    {message}")
        if details:
            print(f"    Details: {details}")
            
        self.test_results.append({
            'test_name': test_name,
            'passed': passed,
            'message': message,
            'details': details
        })
    
    def test_builtin_analysis_types_exist(self):
        """Test that built-in analysis types are available."""
        test_name = "Built-in Analysis Types Exist"
        
        try:
            builtin_types = self.analysis_type_handler.get_builtin_analysis_types()
            
            if len(builtin_types) == 0:
                self.log_test_result(test_name, False, "No built-in analysis types found")
                return
            
            # Check for expected built-in types
            expected_types = ['summary', 'keywords', 'sentiment', 'qa', 'action-items', 'topic-detection']
            found_types = [t.name for t in builtin_types]
            
            missing_types = [t for t in expected_types if t not in found_types]
            if missing_types:
                self.log_test_result(test_name, False, f"Missing built-in types: {missing_types}")
                return
            
            # Verify properties of built-in types
            for builtin_type in builtin_types:
                if not builtin_type.isBuiltIn:
                    self.log_test_result(test_name, False, f"Type {builtin_type.name} should be marked as built-in")
                    return
                    
                if builtin_type.userId is not None:
                    self.log_test_result(test_name, False, f"Built-in type {builtin_type.name} should not have userId")
                    return
                    
                if not builtin_type.prompt or '{transcript}' not in builtin_type.prompt:
                    self.log_test_result(test_name, False, f"Built-in type {builtin_type.name} should have valid prompt with placeholder")
                    return
            
            self.log_test_result(test_name, True, f"Found {len(builtin_types)} built-in analysis types")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_create_custom_analysis_type(self):
        """Test creating a custom analysis type."""
        test_name = "Create Custom Analysis Type"
        
        try:
            # Create custom analysis type
            self.test_analysis_type = self.analysis_type_handler.create_analysis_type(
                name="e2e-custom-summary",
                title="E2E Custom Summary",
                short_title="E2E Summary",
                description="Custom summary for end-to-end testing",
                icon="file-text",
                prompt="Provide a detailed summary of this transcript: {transcript}",
                user_id=self.test_user_id
            )
            
            if not self.test_analysis_type:
                self.log_test_result(test_name, False, "Failed to create custom analysis type")
                return
            
            # Verify properties
            if self.test_analysis_type.name != "e2e-custom-summary":
                self.log_test_result(test_name, False, "Custom type has incorrect name")
                return
                
            if self.test_analysis_type.userId != self.test_user_id:
                self.log_test_result(test_name, False, "Custom type should belong to test user")
                return
                
            if self.test_analysis_type.isBuiltIn:
                self.log_test_result(test_name, False, "Custom type should not be marked as built-in")
                return
                
            if not self.test_analysis_type.isActive:
                self.log_test_result(test_name, False, "Custom type should be active by default")
                return
            
            self.log_test_result(test_name, True, f"Created custom analysis type: {self.test_analysis_type.id}")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_analysis_type_user_isolation(self):
        """Test that analysis types are properly isolated between users."""
        test_name = "Analysis Type User Isolation"
        
        try:
            # Create another test user
            other_user_id = f"other-{self.test_user_id}"
            other_user = self.user_handler.create_user(
                email=f"{other_user_id}@e2etest.com",
                name=f"Other E2E User {other_user_id}",
                role="user"
            )
            other_user.is_test_user = True
            self.user_handler.save_user(other_user)
            
            try:
                # Create analysis type for other user
                other_analysis_type = self.analysis_type_handler.create_analysis_type(
                    name="other-user-type",
                    title="Other User Type",
                    short_title="Other",
                    description="Type for other user",
                    icon="user",
                    prompt="Other user prompt: {transcript}",
                    user_id=other_user_id
                )
                
                # Get types for first user
                user1_types = self.analysis_type_handler.get_analysis_types_for_user(self.test_user_id)
                user1_custom_types = [t for t in user1_types if not t.isBuiltIn]
                
                # Get types for other user
                user2_types = self.analysis_type_handler.get_analysis_types_for_user(other_user_id)
                user2_custom_types = [t for t in user2_types if not t.isBuiltIn]
                
                # User 1 should not see user 2's custom type
                user1_has_other_type = any(t.name == "other-user-type" for t in user1_custom_types)
                if user1_has_other_type:
                    self.log_test_result(test_name, False, "User 1 should not see user 2's custom type")
                    return
                
                # User 2 should not see user 1's custom type  
                user2_has_user1_type = any(t.name == "e2e-custom-summary" for t in user2_custom_types)
                if user2_has_user1_type:
                    self.log_test_result(test_name, False, "User 2 should not see user 1's custom type")
                    return
                
                # Both should see built-in types
                user1_builtin_count = len([t for t in user1_types if t.isBuiltIn])
                user2_builtin_count = len([t for t in user2_types if t.isBuiltIn])
                
                if user1_builtin_count != user2_builtin_count:
                    self.log_test_result(test_name, False, "Both users should see same number of built-in types")
                    return
                
                self.log_test_result(test_name, True, "User isolation working correctly")
                
                # Cleanup other user's type
                self.analysis_type_handler.delete_analysis_type(other_analysis_type.id, other_user_id)
                
            finally:
                # Cleanup other user (if supported)
                pass
                
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_crud_operations(self):
        """Test CRUD operations on analysis types."""
        test_name = "CRUD Operations"
        
        try:
            if not self.test_analysis_type:
                self.log_test_result(test_name, False, "No test analysis type available")
                return
            
            # Test READ
            retrieved = self.analysis_type_handler.get_analysis_type_by_id(
                self.test_analysis_type.id, self.test_user_id
            )
            if not retrieved:
                self.log_test_result(test_name, False, "Failed to retrieve analysis type by ID")
                return
            
            # Test UPDATE
            updates = {
                "title": "Updated E2E Title",
                "description": "Updated description for testing"
            }
            updated = self.analysis_type_handler.update_analysis_type(
                self.test_analysis_type.id, self.test_user_id, updates
            )
            
            if not updated:
                self.log_test_result(test_name, False, "Failed to update analysis type")
                return
                
            if updated.title != "Updated E2E Title":
                self.log_test_result(test_name, False, "Update did not persist title change")
                return
            
            # Test protection of built-in types
            builtin_types = self.analysis_type_handler.get_builtin_analysis_types()
            if builtin_types:
                builtin_type = builtin_types[0]
                
                # Try to update built-in type (should fail)
                builtin_updated = self.analysis_type_handler.update_analysis_type(
                    builtin_type.id, "global", {"title": "Modified Built-in"}
                )
                if builtin_updated:
                    self.log_test_result(test_name, False, "Should not be able to update built-in types")
                    return
                
                # Try to delete built-in type (should fail)
                builtin_deleted = self.analysis_type_handler.delete_analysis_type(
                    builtin_type.id, "global"
                )
                if builtin_deleted:
                    self.log_test_result(test_name, False, "Should not be able to delete built-in types")
                    return
            
            self.log_test_result(test_name, True, "All CRUD operations working correctly")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_create_test_transcription(self):
        """Create a test transcription for analysis testing."""
        test_name = "Create Test Transcription"
        
        try:
            self.test_transcription_id = f"e2e-transcript-{uuid.uuid4().hex[:8]}"
            
            test_transcription = {
                'id': self.test_transcription_id,
                'user_id': self.test_user_id,
                'partitionKey': self.test_user_id,
                'recording_id': f"e2e-recording-{uuid.uuid4().hex[:8]}",
                'text': 'This is a comprehensive test transcription for end-to-end testing. It contains multiple topics including technology, business processes, and team collaboration. The content should provide enough context for various types of analysis including summaries, keyword extraction, and sentiment analysis.',
                'diarized_transcript': 'Speaker 1: This is a comprehensive test transcription for end-to-end testing. Speaker 2: It contains multiple topics including technology, business processes, and team collaboration. Speaker 1: The content should provide enough context for various types of analysis including summaries, keyword extraction, and sentiment analysis.',
                'analysisResults': []
            }
            
            # Save to database
            self.transcription_handler.container.create_item(test_transcription)
            
            # Verify it was created
            retrieved = self.transcription_handler.get_transcription(self.test_transcription_id)
            if not retrieved:
                self.log_test_result(test_name, False, "Failed to create test transcription")
                return
            
            self.log_test_result(test_name, True, f"Created test transcription: {self.test_transcription_id}")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_analysis_execution_with_llm(self):
        """Test actual analysis execution with LLM calls."""
        test_name = "Analysis Execution with LLM"
        
        try:
            if not self.test_analysis_type or not self.test_transcription_id:
                self.log_test_result(test_name, False, "Missing test data for LLM test")
                return
            
            # Get transcription
            transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            if not transcription:
                self.log_test_result(test_name, False, "Test transcription not found")
                return
            
            # Prepare prompt
            prompt = self.test_analysis_type.prompt.replace(
                '{transcript}', 
                transcription.diarized_transcript or transcription.text
            )
            
            # Execute LLM call with timing
            start_time = time.time()
            llm_result = send_prompt_to_llm_with_timing(prompt)
            end_time = time.time()
            
            # Verify LLM result structure
            required_fields = ['content', 'llmResponseTimeMs', 'promptTokens', 'responseTokens']
            for field in required_fields:
                if field not in llm_result:
                    self.log_test_result(test_name, False, f"LLM result missing field: {field}")
                    return
            
            # Verify content is not empty
            if not llm_result['content'] or len(llm_result['content'].strip()) == 0:
                self.log_test_result(test_name, False, "LLM returned empty content")
                return
            
            # Verify timing is reasonable
            if llm_result['llmResponseTimeMs'] <= 0:
                self.log_test_result(test_name, False, "LLM response time should be positive")
                return
            
            # Verify timing is within reasonable bounds of actual time
            actual_time_ms = (end_time - start_time) * 1000
            reported_time_ms = llm_result['llmResponseTimeMs']
            
            # Allow for some variance but should be in the same ballpark
            if abs(actual_time_ms - reported_time_ms) > actual_time_ms * 0.5:
                self.log_test_result(test_name, False, f"Timing mismatch: actual={actual_time_ms:.0f}ms, reported={reported_time_ms}ms")
                return
            
            # Create analysis result
            analysis_result = {
                'analysisType': self.test_analysis_type.name,
                'analysisTypeId': self.test_analysis_type.id,
                'content': llm_result['content'],
                'createdAt': datetime.now(UTC).isoformat(),
                'status': 'completed',
                'llmResponseTimeMs': llm_result['llmResponseTimeMs'],
                'promptTokens': llm_result['promptTokens'],
                'responseTokens': llm_result['responseTokens']
            }
            
            # Add to transcription
            transcription.analysisResults.append(analysis_result)
            self.transcription_handler.update_transcription(self.test_transcription_id, transcription.model_dump())
            
            self.log_test_result(test_name, True, 
                f"LLM analysis completed in {llm_result['llmResponseTimeMs']}ms, "
                f"tokens: {llm_result['promptTokens']}+{llm_result['responseTokens']}")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_analysis_execution_timing_metrics(self):
        """Test that timing metrics are captured correctly."""
        test_name = "Analysis Execution Timing Metrics"
        
        try:
            # Get updated transcription
            transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            if not transcription or not transcription.analysisResults:
                self.log_test_result(test_name, False, "No analysis results found for timing test")
                return
            
            result = transcription.analysisResults[0]
            
            # Check all timing fields are present and valid
            if 'llmResponseTimeMs' not in result or result['llmResponseTimeMs'] is None:
                self.log_test_result(test_name, False, "Missing llmResponseTimeMs")
                return
            
            if 'promptTokens' not in result or result['promptTokens'] is None:
                self.log_test_result(test_name, False, "Missing promptTokens")
                return
                
            if 'responseTokens' not in result or result['responseTokens'] is None:
                self.log_test_result(test_name, False, "Missing responseTokens")
                return
            
            # Verify reasonable values
            if result['llmResponseTimeMs'] <= 0:
                self.log_test_result(test_name, False, "Response time should be positive")
                return
                
            if result['promptTokens'] <= 0:
                self.log_test_result(test_name, False, "Prompt tokens should be positive")
                return
                
            if result['responseTokens'] <= 0:
                self.log_test_result(test_name, False, "Response tokens should be positive")
                return
            
            self.log_test_result(test_name, True, 
                f"Timing metrics captured: {result['llmResponseTimeMs']}ms, "
                f"{result['promptTokens']}+{result['responseTokens']} tokens")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_custom_prompt_execution(self):
        """Test analysis execution with custom prompt."""
        test_name = "Custom Prompt Execution"
        
        try:
            if not self.test_analysis_type or not self.test_transcription_id:
                self.log_test_result(test_name, False, "Missing test data for custom prompt test")
                return
            
            # Get transcription
            transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            
            # Custom prompt
            custom_prompt = "Extract exactly 3 key points from this transcript: {transcript}"
            
            # Prepare prompt with transcript
            final_prompt = custom_prompt.replace(
                '{transcript}',
                transcription.diarized_transcript or transcription.text
            )
            
            # Execute with custom prompt
            llm_result = send_prompt_to_llm_with_timing(final_prompt)
            
            # Verify we got a response
            if not llm_result['content']:
                self.log_test_result(test_name, False, "Custom prompt returned empty content")
                return
            
            # Create analysis result with custom prompt
            custom_result = {
                'analysisType': 'custom-prompt-test',
                'analysisTypeId': self.test_analysis_type.id,
                'content': llm_result['content'],
                'createdAt': datetime.now(UTC).isoformat(),
                'status': 'completed',
                'llmResponseTimeMs': llm_result['llmResponseTimeMs'],
                'promptTokens': llm_result['promptTokens'],
                'responseTokens': llm_result['responseTokens']
            }
            
            # Add to transcription
            transcription.analysisResults.append(custom_result)
            self.transcription_handler.update_transcription(self.test_transcription_id, transcription.model_dump())
            
            self.log_test_result(test_name, True, "Custom prompt execution successful")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_analysis_result_persistence(self):
        """Test that analysis results are properly persisted."""
        test_name = "Analysis Result Persistence"
        
        try:
            # Get fresh copy of transcription from database
            transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            
            if not transcription:
                self.log_test_result(test_name, False, "Transcription not found")
                return
            
            if not transcription.analysisResults:
                self.log_test_result(test_name, False, "No analysis results found")
                return
            
            # Should have at least 2 results (standard + custom prompt)
            if len(transcription.analysisResults) < 2:
                self.log_test_result(test_name, False, f"Expected at least 2 results, got {len(transcription.analysisResults)}")
                return
            
            # Verify each result has required fields
            for i, result in enumerate(transcription.analysisResults):
                required_fields = ['analysisType', 'analysisTypeId', 'content', 'createdAt', 'status']
                for field in required_fields:
                    if field not in result:
                        self.log_test_result(test_name, False, f"Result {i} missing field: {field}")
                        return
                
                # Verify timestamp is valid
                try:
                    datetime.fromisoformat(result['createdAt'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    self.log_test_result(test_name, False, f"Result {i} has invalid timestamp")
                    return
            
            self.log_test_result(test_name, True, f"Found {len(transcription.analysisResults)} persisted analysis results")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def test_multiple_analysis_accumulation(self):
        """Test that multiple analysis results accumulate correctly."""
        test_name = "Multiple Analysis Accumulation"
        
        try:
            transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            
            # Get a built-in analysis type for additional test
            builtin_types = self.analysis_type_handler.get_builtin_analysis_types()
            keywords_type = next((t for t in builtin_types if t.name == 'keywords'), None)
            
            if not keywords_type:
                self.log_test_result(test_name, False, "Keywords analysis type not found")
                return
            
            # Execute keywords analysis
            keywords_prompt = keywords_type.prompt.replace(
                '{transcript}',
                transcription.diarized_transcript or transcription.text
            )
            
            llm_result = send_prompt_to_llm_with_timing(keywords_prompt)
            
            # Create keywords result
            keywords_result = {
                'analysisType': keywords_type.name,
                'analysisTypeId': keywords_type.id,
                'content': llm_result['content'],
                'createdAt': datetime.now(UTC).isoformat(),
                'status': 'completed',
                'llmResponseTimeMs': llm_result['llmResponseTimeMs'],
                'promptTokens': llm_result['promptTokens'],
                'responseTokens': llm_result['responseTokens']
            }
            
            # Add to existing results
            transcription.analysisResults.append(keywords_result)
            self.transcription_handler.update_transcription(self.test_transcription_id, transcription.model_dump())
            
            # Verify accumulation
            updated_transcription = self.transcription_handler.get_transcription(self.test_transcription_id)
            
            if len(updated_transcription.analysisResults) < 3:
                self.log_test_result(test_name, False, f"Expected at least 3 results, got {len(updated_transcription.analysisResults)}")
                return
            
            # Verify we have different analysis types
            analysis_types = {r['analysisType'] for r in updated_transcription.analysisResults}
            if 'keywords' not in analysis_types:
                self.log_test_result(test_name, False, "Keywords analysis not found in results")
                return
            
            self.log_test_result(test_name, True, 
                f"Successfully accumulated {len(updated_transcription.analysisResults)} analysis results "
                f"with types: {', '.join(analysis_types)}")
            
        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {e}")
    
    def print_test_results(self):
        """Print summary of all test results."""
        print("\n" + "=" * 60)
        print("🧪 E2E TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = sum(1 for r in self.test_results if not r['passed'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  ❌ {result['test_name']}: {result['message']}")
        
        print("\n📊 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            print(f"  {status} {result['test_name']}")
            if result['message']:
                print(f"      {result['message']}")


def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(description='Run end-to-end tests for dynamic analysis types')
    parser.add_argument('--no-llm', action='store_true', 
                       help='Skip tests that require actual LLM calls')
    
    args = parser.parse_args()
    
    test_runner = DynamicAnalysisE2ETest(skip_llm_tests=args.no_llm)
    success = test_runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()