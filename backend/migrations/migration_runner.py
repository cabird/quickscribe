"""
Common utilities for running database migrations.
"""
import sys
import os
import argparse
import logging
from datetime import datetime, UTC
from typing import Dict, Any

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from db_handlers.transcription_handler import TranscriptionHandler
from logging_config import get_logger

class MigrationRunner:
    """Base class for database migrations."""
    
    def __init__(self, migration_name: str, description: str):
        self.migration_name = migration_name
        self.description = description
        self.logger = get_logger(f'migration_{migration_name}', '1.0.0')
        self.config = Config()
        
        # Initialize handlers directly without Flask context
        self.transcription_handler = TranscriptionHandler(
            cosmos_url=self.config.COSMOS_URL,
            cosmos_key=self.config.COSMOS_KEY,
            database_name=self.config.COSMOS_DB_NAME,
            container_name=self.config.COSMOS_CONTAINER_NAME
        )
        
    def setup_logging(self, dry_run: bool = False):
        """Setup logging for the migration."""
        log_level = logging.INFO
        log_file = f"migration_{self.migration_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
        
        if dry_run:
            log_file = f"migration_{self.migration_name}_dryrun_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
        
        # Configure file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add to logger
        self.logger.addHandler(file_handler)
        
        self.logger.info(f"Starting migration: {self.migration_name}")
        self.logger.info(f"Description: {self.description}")
        self.logger.info(f"Dry run mode: {dry_run}")
        
        return log_file
    
    def create_argument_parser(self) -> argparse.ArgumentParser:
        """Create standard argument parser for migrations."""
        parser = argparse.ArgumentParser(
            description=f"Migration: {self.migration_name} - {self.description}"
        )
        
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--dry-run', 
            action='store_true',
            help='Preview changes without executing them'
        )
        group.add_argument(
            '--execute', 
            action='store_true',
            help='Execute the migration'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records to process (for testing)'
        )
        
        return parser
    
    def confirm_execution(self) -> bool:
        """Prompt user to confirm migration execution."""
        print(f"\n⚠️  MIGRATION: {self.migration_name}")
        print(f"Description: {self.description}")
        print("\nThis will modify data in your database.")
        
        while True:
            response = input("Are you sure you want to proceed? (yes/no): ").lower().strip()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please enter 'yes' or 'no'")
    
    def log_progress(self, current: int, total: int, message: str = ""):
        """Log migration progress."""
        percentage = (current / total * 100) if total > 0 else 0
        log_message = f"Progress: {current}/{total} ({percentage:.1f}%)"
        if message:
            log_message += f" - {message}"
        self.logger.info(log_message)
        
        # Also print to console every 10% or every 100 records
        if current % max(1, total // 10) == 0 or current % 100 == 0:
            print(log_message)