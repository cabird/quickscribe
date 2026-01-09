#!/usr/bin/env python3
"""
Migration 003: Backfill Token Counts

This migration calculates and sets token_count for all existing transcriptions
and their linked recordings using tiktoken (o200k_base encoding).

The token_count field is used by the frontend to:
- Display token count on recording cards
- Show total tokens when multiple transcripts are selected for chat
- Warn users when selected tokens exceed context limits (>100k)

Usage:
    cd backend/src
    python ../migrations/003_backfill_token_counts.py --dry-run
    python ../migrations/003_backfill_token_counts.py --dry-run --limit 10
    python ../migrations/003_backfill_token_counts.py --execute
"""

import sys
import os
import argparse
import logging
from datetime import datetime, UTC
from typing import Tuple, Optional

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from config import Config
from shared_quickscribe_py.cosmos.transcription_handler import TranscriptionHandler
from shared_quickscribe_py.cosmos.recording_handler import RecordingHandler


class BackfillTokenCountsMigration:
    """Migration to backfill token_count for all transcriptions and recordings."""

    def __init__(self):
        self.migration_name = "003_backfill_token_counts"
        self.description = "Calculate and set token_count for all existing transcriptions and recordings"

        # Setup config and handlers
        self.config = Config()

        self.transcription_handler = TranscriptionHandler(
            cosmos_url=self.config.COSMOS_URL,
            cosmos_key=self.config.COSMOS_KEY,
            database_name=self.config.COSMOS_DB_NAME,
            container_name=self.config.COSMOS_CONTAINER_NAME
        )

        self.recording_handler = RecordingHandler(
            cosmos_url=self.config.COSMOS_URL,
            cosmos_key=self.config.COSMOS_KEY,
            database_name=self.config.COSMOS_DB_NAME,
            container_name=self.config.COSMOS_CONTAINER_NAME
        )

        # Setup logging
        self.logger = logging.getLogger(f'migration_{self.migration_name}')
        self.logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def setup_file_logging(self, dry_run: bool = False) -> str:
        """Setup file logging and return log filename."""
        mode = "dryrun" if dry_run else "execute"
        log_file = f"migration_{self.migration_name}_{mode}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        return log_file

    def format_cosmos_update_command(self, container: str, item_id: str, partition_key: str,
                                      field: str, old_value, new_value) -> str:
        """Format a Cosmos DB update as a readable command string."""
        return (
            f"  UPDATE {container}\n"
            f"    SET {field} = {new_value}\n"
            f"    WHERE id = '{item_id}'\n"
            f"      AND partitionKey = '{partition_key}'\n"
            f"    -- Previous value: {old_value}"
        )

    def process_transcription(self, transcription, dry_run: bool = False) -> Tuple[bool, str, Optional[dict]]:
        """
        Process a single transcription.
        Returns (changed, message, stats).
        """
        stats = {
            'transcription_updated': False,
            'recording_updated': False,
            'token_count': None,
            'text_length': 0
        }

        try:
            # Get transcript text
            transcript_text = transcription.diarized_transcript or transcription.text

            if not transcript_text:
                return False, "No transcript text available", stats

            # Check if already has token_count
            if transcription.token_count is not None:
                return False, f"Already has token_count: {transcription.token_count}", stats

            # Calculate token count using tiktoken
            token_count = TranscriptionHandler.calculate_token_count(transcript_text)
            stats['token_count'] = token_count
            stats['text_length'] = len(transcript_text)

            self.logger.info(f"Transcription {transcription.id}:")
            self.logger.info(f"  Text length: {len(transcript_text):,} chars")
            self.logger.info(f"  Token count: {token_count:,}")

            # Show the Cosmos update command for transcription
            transcription_update_cmd = self.format_cosmos_update_command(
                container="transcriptions",
                item_id=transcription.id,
                partition_key=transcription.partitionKey,
                field="token_count",
                old_value=transcription.token_count,
                new_value=token_count
            )
            self.logger.info(f"  Cosmos command (transcription):\n{transcription_update_cmd}")

            if not dry_run:
                # Update transcription
                transcription.token_count = token_count
                self.transcription_handler.update_transcription(transcription)
                stats['transcription_updated'] = True

            # Also update the linked recording if it exists
            recording = None
            if transcription.recording_id:
                recording = self.recording_handler.get_recording(transcription.recording_id)

            if recording:
                recording_update_cmd = self.format_cosmos_update_command(
                    container="recordings",
                    item_id=recording.id,
                    partition_key=recording.partitionKey,
                    field="token_count",
                    old_value=recording.token_count,
                    new_value=token_count
                )
                self.logger.info(f"  Cosmos command (recording):\n{recording_update_cmd}")

                # Track that a recording would be updated (for dry-run counts)
                stats['recording_updated'] = True

                if not dry_run:
                    recording.token_count = token_count
                    self.recording_handler.update_recording(recording)
            else:
                self.logger.info(f"  No linked recording found")

            return True, f"Token count: {token_count}", stats

        except Exception as e:
            error_msg = f"Error processing transcription {transcription.id}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, stats

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

    def run_migration(self, dry_run: bool = False, limit: Optional[int] = None):
        """Run the migration."""
        log_file = self.setup_file_logging(dry_run)

        self.logger.info(f"Starting migration: {self.migration_name}")
        self.logger.info(f"Description: {self.description}")
        self.logger.info(f"Dry run mode: {dry_run}")

        if not dry_run and not self.confirm_execution():
            self.logger.info("Migration cancelled by user")
            return

        self.logger.info("Fetching all transcriptions...")
        all_transcriptions = self.transcription_handler.get_all_transcriptions()

        if limit:
            all_transcriptions = all_transcriptions[:limit]
            self.logger.info(f"Limited to {limit} transcriptions for testing")

        total_count = len(all_transcriptions)
        processed_count = 0
        changed_count = 0
        skipped_count = 0
        error_count = 0
        total_tokens = 0
        recordings_updated = 0

        self.logger.info(f"Found {total_count} transcriptions to process")

        if dry_run:
            print("\n" + "=" * 70)
            print("DRY RUN MODE - No changes will be made")
            print("The following Cosmos DB commands would be executed:")
            print("=" * 70 + "\n")

        for i, transcription in enumerate(all_transcriptions):
            changed, message, stats = self.process_transcription(transcription, dry_run)

            if changed:
                changed_count += 1
                if stats and stats['token_count']:
                    total_tokens += stats['token_count']
                if stats and stats['recording_updated']:
                    recordings_updated += 1
            elif "Already has" in message or "No transcript" in message:
                skipped_count += 1
                self.logger.info(f"Skipped transcription {transcription.id}: {message}")

            if "Error" in message:
                error_count += 1

            processed_count += 1

            # Log progress every 10 items
            if processed_count % 10 == 0 or processed_count == total_count:
                pct = (processed_count / total_count * 100) if total_count > 0 else 0
                self.logger.info(f"Progress: {processed_count}/{total_count} ({pct:.1f}%) - "
                               f"Changed: {changed_count}, Skipped: {skipped_count}, Errors: {error_count}")

        # Summary
        mode_str = "DRY RUN" if dry_run else "EXECUTED"

        print("\n" + "=" * 70)
        print(f"Migration {mode_str}!")
        print("=" * 70)
        print(f"Total processed:         {processed_count}")
        print(f"Transcriptions to update: {changed_count}")
        print(f"Recordings to update:     {recordings_updated}")
        print(f"Skipped:                  {skipped_count}")
        print(f"Errors:                   {error_count}")
        print(f"Total tokens calculated:  {total_tokens:,}")
        print(f"Log file:                 {log_file}")

        if dry_run:
            print(f"\nTo execute this migration, run:")
            print(f"  cd backend/src && python ../migrations/003_backfill_token_counts.py --execute")

        self.logger.info("Migration completed!")


def main():
    parser = argparse.ArgumentParser(
        description="Migration 003: Backfill token counts for transcriptions and recordings"
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

    args = parser.parse_args()

    migration = BackfillTokenCountsMigration()
    migration.run_migration(
        dry_run=args.dry_run,
        limit=args.limit
    )


if __name__ == "__main__":
    main()
