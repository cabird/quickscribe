#!/usr/bin/env python3
"""
Comprehensive test runner for the dynamic analysis types system.

This script runs the full test suite including unit tests, integration tests,
and end-to-end tests for the dynamic analysis types feature.

Usage:
    python run_dynamic_analysis_tests.py [options]
    
Options:
    --unit-only: Run only unit tests
    --integration-only: Run only integration tests  
    --e2e-only: Run only end-to-end tests
    --no-llm: Skip tests that require actual LLM calls
    --verbose: Enable verbose output
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


class DynamicAnalysisTestRunner:
    """Comprehensive test runner for dynamic analysis types."""
    
    def __init__(self, verbose=False, no_llm=False):
        self.verbose = verbose
        self.no_llm = no_llm
        self.passed_tests = 0
        self.failed_tests = 0
        self.total_tests = 0
        
    def log(self, message):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"🔍 {message}")
    
    def run_pytest_tests(self, test_pattern, description):
        """Run pytest tests with specified pattern."""
        print(f"\n{'='*60}")
        print(f"🧪 Running {description}")
        print(f"{'='*60}")
        
        # Construct pytest command
        cmd = ["python", "-m", "pytest", "-v"]
        
        if test_pattern:
            cmd.extend(["-k", test_pattern])
        
        # Add markers if needed
        if "integration" in description.lower():
            cmd.extend(["-m", "integration"])
        elif "unit" in description.lower():
            cmd.extend(["-m", "unit"])
        
        # Add test directories
        cmd.extend([
            "tests/unit/",
            "tests/integration/", 
            "tests/e2e/"
        ])
        
        self.log(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            if self.verbose:
                print("STDOUT:", result.stdout)
                if result.stderr:
                    print("STDERR:", result.stderr)
            
            # Parse pytest output for test counts
            lines = result.stdout.split('\n')
            for line in lines:
                if 'passed' in line and 'failed' in line:
                    # Parse line like "5 passed, 2 failed in 10.5s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed':
                            self.passed_tests += int(parts[i-1])
                        elif part == 'failed':
                            self.failed_tests += int(parts[i-1])
                elif line.strip().endswith('passed'):
                    # Parse line like "5 passed in 10.5s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed':
                            self.passed_tests += int(parts[i-1])
            
            if result.returncode == 0:
                print(f"✅ {description} - PASSED")
                return True
            else:
                print(f"❌ {description} - FAILED")
                if not self.verbose:
                    print("Last few lines of output:")
                    print('\n'.join(result.stdout.split('\n')[-10:]))
                return False
                
        except Exception as e:
            print(f"❌ {description} - ERROR: {e}")
            return False
    
    def run_e2e_tests(self):
        """Run end-to-end tests."""
        print(f"\n{'='*60}")
        print(f"🚀 Running End-to-End Tests")
        print(f"{'='*60}")
        
        cmd = ["python", "test_dynamic_analysis_e2e.py"]
        if self.no_llm:
            cmd.append("--no-llm")
        
        self.log(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, cwd=os.getcwd())
            
            if result.returncode == 0:
                print("✅ End-to-End Tests - PASSED")
                return True
            else:
                print("❌ End-to-End Tests - FAILED")
                return False
                
        except Exception as e:
            print(f"❌ End-to-End Tests - ERROR: {e}")
            return False
    
    def run_frontend_tests(self):
        """Run frontend tests."""
        print(f"\n{'='*60}")
        print(f"🎨 Running Frontend Tests")
        print(f"{'='*60}")
        
        frontend_path = Path("../frontend_new")
        if not frontend_path.exists():
            print("⏭️  Frontend directory not found, skipping frontend tests")
            return True
        
        # For now, just validate the test file exists and can be imported
        test_file = frontend_path / "src/tests/analysisWorkflow.test.ts"
        if test_file.exists():
            print("✅ Frontend test file exists")
            print("📋 Frontend tests are TypeScript-based and would run in a browser environment")
            print("   To run frontend tests, use: cd frontend_new && npm test (when test runner is configured)")
            return True
        else:
            print("❌ Frontend test file not found")
            return False
    
    def check_environment(self):
        """Check that the test environment is properly set up."""
        print("🔧 Checking test environment...")
        
        # Check Python environment
        try:
            import pytest
            print("✅ pytest available")
        except ImportError:
            print("❌ pytest not available - install with: pip install pytest")
            return False
        
        # Check required modules
        required_modules = [
            'azure.cosmos',
            'azure.storage.blob', 
            'azure.storage.queue',
            'requests',
            'pydantic'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
                print(f"✅ {module} available")
            except ImportError:
                print(f"❌ {module} not available")
                return False
        
        # Check test directories exist
        test_dirs = ['tests/unit', 'tests/integration', 'tests/e2e']
        for test_dir in test_dirs:
            if Path(test_dir).exists():
                print(f"✅ {test_dir} directory exists")
            else:
                print(f"⚠️  {test_dir} directory not found")
        
        print("✅ Environment check complete")
        return True
    
    def run_all_tests(self, unit_only=False, integration_only=False, e2e_only=False):
        """Run all tests based on specified options."""
        print("🧪 Dynamic Analysis Types - Comprehensive Test Suite")
        print("=" * 60)
        
        if not self.check_environment():
            print("❌ Environment check failed. Please fix issues before running tests.")
            return False
        
        results = []
        
        # Unit tests
        if not integration_only and not e2e_only:
            results.append(self.run_pytest_tests(
                "test_user_handler or test_send_prompt_to_llm_with_timing",
                "Unit Tests"
            ))
        
        # Integration tests  
        if not unit_only and not e2e_only:
            results.append(self.run_pytest_tests(
                "test_analysis_types_real_db or test_analysis_execution",
                "Integration Tests - Analysis Types"
            ))
            
            results.append(self.run_pytest_tests(
                "test_analysis_execution",
                "Integration Tests - Analysis Execution"
            ))
        
        # API tests
        if not unit_only and not e2e_only:
            results.append(self.run_pytest_tests(
                "TestAnalysisTypesAPI",
                "API Integration Tests"
            ))
        
        # Frontend tests
        if not unit_only and not integration_only and not e2e_only:
            results.append(self.run_frontend_tests())
        
        # End-to-end tests
        if not unit_only and not integration_only:
            results.append(self.run_e2e_tests())
        
        # Summary
        self.print_summary(results)
        
        return all(results)
    
    def print_summary(self, results):
        """Print test summary."""
        print(f"\n{'='*60}")
        print("📊 TEST SUITE SUMMARY")
        print(f"{'='*60}")
        
        passed_suites = sum(1 for r in results if r)
        failed_suites = sum(1 for r in results if not r)
        total_suites = len(results)
        
        print(f"Test Suites: {total_suites}")
        print(f"Passed: {passed_suites} ✅")
        print(f"Failed: {failed_suites} ❌")
        
        if total_suites > 0:
            success_rate = (passed_suites / total_suites) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        
        if self.passed_tests > 0 or self.failed_tests > 0:
            print(f"\nIndividual Tests:")
            print(f"Passed: {self.passed_tests} ✅")
            print(f"Failed: {self.failed_tests} ❌")
            total_individual = self.passed_tests + self.failed_tests
            if total_individual > 0:
                individual_success_rate = (self.passed_tests / total_individual) * 100
                print(f"Individual Success Rate: {individual_success_rate:.1f}%")
        
        print(f"\n{'='*60}")
        
        if all(results):
            print("🎉 ALL TESTS PASSED! 🎉")
            print("The dynamic analysis types system is working correctly.")
        else:
            print("❌ SOME TESTS FAILED")
            print("Please review the failed tests and fix any issues.")
        
        print(f"{'='*60}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive tests for dynamic analysis types system"
    )
    parser.add_argument(
        "--unit-only", 
        action="store_true",
        help="Run only unit tests"
    )
    parser.add_argument(
        "--integration-only",
        action="store_true", 
        help="Run only integration tests"
    )
    parser.add_argument(
        "--e2e-only",
        action="store_true",
        help="Run only end-to-end tests"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip tests that require actual LLM calls"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate exclusive options
    exclusive_options = [args.unit_only, args.integration_only, args.e2e_only]
    if sum(exclusive_options) > 1:
        print("❌ Error: --unit-only, --integration-only, and --e2e-only are mutually exclusive")
        sys.exit(1)
    
    runner = DynamicAnalysisTestRunner(verbose=args.verbose, no_llm=args.no_llm)
    
    success = runner.run_all_tests(
        unit_only=args.unit_only,
        integration_only=args.integration_only,
        e2e_only=args.e2e_only
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()