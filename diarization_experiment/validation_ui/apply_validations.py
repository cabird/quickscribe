#!/usr/bin/env python3
"""
Apply Validation Decisions to Database

This script reads validation session JSON files and applies the decisions
to the database by updating speaker participant mappings.

Usage:
    python apply_validations.py --session validation-user-20240112-154530.json
    python apply_validations.py --all
    python apply_validations.py --latest
    python apply_validations.py --dry-run --session <file>
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader

VALIDATIONS_DIR = './validations'
USER_ID = os.environ.get('QUICKSCRIBE_USER_ID', 'user-bd639cf9-a105-44f5-80e0-478a8ec2e5c2')


class ValidationApplier:
    """Applies validation decisions to the database."""

    def __init__(self, user_id: str, dry_run: bool = False):
        self.user_id = user_id
        self.dry_run = dry_run
        self.data_loader = DataLoader()

        print(f"\n{'DRY RUN - ' if dry_run else ''}Validation Applier")
        print(f"User ID: {user_id}")
        print(f"Mode: {'Dry run (no changes will be made)' if dry_run else 'Live (will modify database)'}")

    def load_session_file(self, filepath: str) -> Dict:
        """Load a validation session JSON file."""
        with open(filepath, 'r') as f:
            return json.load(f)

    def apply_session(self, session_data: Dict, session_file: str) -> Dict:
        """
        Apply all decisions from a session.

        Returns summary dict with counts.
        """
        decisions = session_data.get('decisions', [])

        summary = {
            'session_file': session_file,
            'total_decisions': len(decisions),
            'confirmed': 0,
            'reassigned': 0,
            'rejected': 0,
            'skipped': 0,
            'applied': 0,
            'errors': []
        }

        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Processing {len(decisions)} decisions from {session_file}")

        for decision in decisions:
            decision_type = decision.get('decision')
            item_id = decision.get('item_id')  # Format: "recording_id::speaker_label"
            participant_id = decision.get('participant_id')

            # Count by type
            if decision_type == 'confirmed':
                summary['confirmed'] += 1
            elif decision_type == 'reassigned':
                summary['reassigned'] += 1
            elif decision_type == 'rejected':
                summary['rejected'] += 1
            elif decision_type == 'skipped':
                summary['skipped'] += 1

            # Apply confirmed and reassigned decisions (both have a valid participant_id)
            # - confirmed: user verified the suggested match
            # - reassigned: user said it's a different person and specified who
            if decision_type not in ('confirmed', 'reassigned'):
                continue

            # Parse item_id
            try:
                recording_id, speaker_label = item_id.split('::', 1)
            except ValueError:
                summary['errors'].append(f"Invalid item_id format: {item_id}")
                continue

            # Apply the decision
            try:
                if not self.dry_run:
                    self._apply_participant_mapping(
                        recording_id,
                        speaker_label,
                        participant_id
                    )
                summary['applied'] += 1
                print(f"  ✓ {recording_id}::{speaker_label} -> {participant_id}")
            except Exception as e:
                error_msg = f"Error applying {item_id}: {str(e)}"
                summary['errors'].append(error_msg)
                print(f"  ✗ {error_msg}")

        return summary

    def _apply_participant_mapping(
        self,
        recording_id: str,
        speaker_label: str,
        participant_id: str
    ):
        """
        Apply a participant mapping to a speaker in a recording.

        This updates the transcription's speaker_mapping field.
        Schema: transcription.speaker_mapping[speakerLabel] = {
            participantId: string,
            confidence: number,
            manuallyVerified: boolean
        }
        """
        # Get the transcription
        transcription = self.data_loader.get_transcription(recording_id, self.user_id)

        if not transcription:
            raise ValueError(f"Transcription not found: {recording_id}")

        # Update the speaker_mapping (note: field uses camelCase per schema)
        if 'speaker_mapping' not in transcription or transcription['speaker_mapping'] is None:
            transcription['speaker_mapping'] = {}

        if speaker_label not in transcription['speaker_mapping']:
            transcription['speaker_mapping'][speaker_label] = {}

        # Get participant info to verify it exists
        participant = self.data_loader.get_participant_by_id(participant_id, self.user_id)
        if not participant:
            raise ValueError(f"Participant not found: {participant_id}")

        # Update speaker mapping with participant info (camelCase fields per schema)
        transcription['speaker_mapping'][speaker_label]['participantId'] = participant_id
        transcription['speaker_mapping'][speaker_label]['manuallyVerified'] = True

        # Save the transcription
        self.data_loader.save_transcription(transcription)

        print(f"    Updated speaker {speaker_label} in {recording_id}")

    def apply_all_sessions(self, validations_dir: str) -> List[Dict]:
        """Apply all validation sessions in the directory."""
        session_files = sorted(Path(validations_dir).glob('validation-*.json'))

        if not session_files:
            print(f"\nNo validation session files found in {validations_dir}")
            return []

        print(f"\nFound {len(session_files)} session files")

        summaries = []
        for session_file in session_files:
            session_data = self.load_session_file(str(session_file))
            summary = self.apply_session(session_data, session_file.name)
            summaries.append(summary)

            # Move processed file to prevent re-processing
            if not self.dry_run and not summary['errors']:
                processed_dir = session_file.parent / 'processed'
                processed_dir.mkdir(exist_ok=True)
                new_path = processed_dir / session_file.name
                session_file.rename(new_path)
                print(f"  -> Moved {session_file.name} to processed/ directory")

        return summaries

    def apply_latest_session(self, validations_dir: str) -> Optional[Dict]:
        """Apply only the most recent validation session."""
        session_files = sorted(Path(validations_dir).glob('validation-*.json'))

        if not session_files:
            print(f"\nNo validation session files found in {validations_dir}")
            return None

        latest_file = session_files[-1]
        print(f"\nApplying latest session: {latest_file.name}")

        session_data = self.load_session_file(str(latest_file))
        summary = self.apply_session(session_data, latest_file.name)

        # Move processed file to prevent re-processing
        if not self.dry_run and not summary['errors']:
            processed_dir = latest_file.parent / 'processed'
            processed_dir.mkdir(exist_ok=True)
            new_path = processed_dir / latest_file.name
            latest_file.rename(new_path)
            print(f"  -> Moved {latest_file.name} to processed/ directory")

        return summary


def print_summary(summaries: List[Dict]):
    """Print a summary of applied validations."""
    print("\n" + "=" * 70)
    print("VALIDATION APPLICATION SUMMARY")
    print("=" * 70)

    total_decisions = sum(s['total_decisions'] for s in summaries)
    total_confirmed = sum(s['confirmed'] for s in summaries)
    total_reassigned = sum(s['reassigned'] for s in summaries)
    total_rejected = sum(s['rejected'] for s in summaries)
    total_skipped = sum(s['skipped'] for s in summaries)
    total_applied = sum(s['applied'] for s in summaries)
    total_errors = sum(len(s['errors']) for s in summaries)

    print(f"\nSessions processed: {len(summaries)}")
    print(f"Total decisions: {total_decisions}")
    print(f"  - Confirmed: {total_confirmed}")
    print(f"  - Reassigned: {total_reassigned}")
    print(f"  - Rejected: {total_rejected}")
    print(f"  - Skipped: {total_skipped}")
    print(f"\nApplied to database: {total_applied} (confirmed + reassigned)")

    if total_errors > 0:
        print(f"\n⚠ Errors: {total_errors}")
        print("\nError details:")
        for summary in summaries:
            if summary['errors']:
                print(f"\n  {summary['session_file']}:")
                for error in summary['errors']:
                    print(f"    - {error}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Apply speaker identification validation decisions to database"
    )
    parser.add_argument(
        '--session',
        type=str,
        help='Specific session file to apply (in validations/ directory)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Apply all validation sessions'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Apply only the latest validation session'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying database'
    )
    parser.add_argument(
        '--validations-dir',
        type=str,
        default=VALIDATIONS_DIR,
        help=f'Directory containing validation files (default: {VALIDATIONS_DIR})'
    )

    args = parser.parse_args()

    if not USER_ID:
        print("Error: QUICKSCRIBE_USER_ID environment variable not set")
        print("\nUsage:")
        print("  export QUICKSCRIBE_USER_ID='your_user_id'")
        print("  python apply_validations.py --latest")
        sys.exit(1)

    # Ensure validations directory exists
    if not os.path.exists(args.validations_dir):
        print(f"Error: Validations directory not found: {args.validations_dir}")
        sys.exit(1)

    applier = ValidationApplier(USER_ID, dry_run=args.dry_run)

    summaries = []

    try:
        if args.session:
            # Apply specific session
            session_path = os.path.join(args.validations_dir, args.session)
            if not os.path.exists(session_path):
                print(f"Error: Session file not found: {session_path}")
                sys.exit(1)

            session_data = applier.load_session_file(session_path)
            summary = applier.apply_session(session_data, args.session)
            summaries = [summary]

        elif args.latest:
            # Apply latest session
            summary = applier.apply_latest_session(args.validations_dir)
            if summary:
                summaries = [summary]

        elif args.all:
            # Apply all sessions
            summaries = applier.apply_all_sessions(args.validations_dir)

        else:
            print("Error: Must specify --session, --latest, or --all")
            parser.print_help()
            sys.exit(1)

        # Print summary
        if summaries:
            print_summary(summaries)

            if args.dry_run:
                print("\n💡 This was a dry run. No changes were made to the database.")
                print("   Remove --dry-run to apply these changes.")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.dry_run:
            print("\n💡 Even in dry-run mode, database access is required to validate decisions.")
        sys.exit(1)


if __name__ == "__main__":
    main()
