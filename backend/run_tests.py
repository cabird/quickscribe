#!/usr/bin/env python3
"""
Test runner script for QuickScribe backend tests.

Usage:
    python run_tests.py [category] [options]

Categories:
    unit        - Run only unit tests
    integration - Run only integration tests  
    e2e         - Run only end-to-end tests
    fast        - Run tests excluding slow ones
    all         - Run all tests (default)

Options:
    --coverage  - Include coverage report
    --verbose   - Verbose output
    --no-cov    - Skip coverage reporting
    --html      - Generate HTML coverage report
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(cmd: list, description: str = "") -> int:
    """Run a command and return exit code."""
    if description:
        print(f"\n🔧 {description}")
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    """Main test runner function."""
    # Check if virtual environment is activated
    if not os.environ.get('VIRTUAL_ENV'):
        print("❌ Virtual environment is not activated!")
        print("\nPlease activate the virtual environment first:")
        print("  cd /home/cbird/repos/quickscribe/backend")
        print("  source venv/bin/activate")
        print("\nThen run this script again.")
        return 1
    
    parser = argparse.ArgumentParser(description="QuickScribe Backend Test Runner")
    parser.add_argument(
        'category', 
        nargs='?', 
        default='all',
        choices=['unit', 'integration', 'e2e', 'fast', 'all'],
        help='Test category to run'
    )
    parser.add_argument('--coverage', action='store_true', help='Include coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--no-cov', action='store_true', help='Skip coverage reporting')
    parser.add_argument('--html', action='store_true', help='Generate HTML coverage report')
    parser.add_argument('--parallel', '-n', type=int, help='Run tests in parallel')
    
    args = parser.parse_args()
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # Check if pytest is available
    try:
        subprocess.run(['python', '-m', 'pytest', '--version'], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ pytest not found. Installing test dependencies...")
        install_result = run_command(
            ['pip', 'install', '-r', 'requirements.txt'],
            "Installing dependencies"
        )
        if install_result != 0:
            print("❌ Failed to install dependencies")
            return 1
    
    # Build pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add test directory based on category
    if args.category == 'unit':
        cmd.extend(['tests/unit/', '-m', 'unit'])
    elif args.category == 'integration':
        cmd.extend(['tests/integration/', '-m', 'integration'])
    elif args.category == 'e2e':
        cmd.extend(['tests/e2e/', '-m', 'e2e'])
    elif args.category == 'fast':
        cmd.extend(['-m', 'not slow'])
    else:  # all
        cmd.append('tests/')
    
    # Add verbose flag
    if args.verbose:
        cmd.append('-v')
    
    # Add coverage options
    if not args.no_cov and (args.coverage or args.category == 'all'):
        cmd.extend([
            '--cov=.',
            '--cov-report=term-missing',
            '--cov-fail-under=40'
        ])
        
        if args.html:
            cmd.append('--cov-report=html:htmlcov')
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(['-n', str(args.parallel)])
    
    # Add other useful flags
    cmd.extend([
        '--tb=short'
    ])
    
    print(f"\n🚀 Running {args.category} tests for QuickScribe backend")
    print("=" * 60)
    
    # Run the tests
    exit_code = run_command(cmd, f"Running {args.category} tests")
    
    # Print summary
    if exit_code == 0:
        print("\n✅ All tests passed!")
        if not args.no_cov and (args.coverage or args.category == 'all'):
            print("\n📊 Coverage report generated")
            if args.html:
                print("📄 HTML coverage report: htmlcov/index.html")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())