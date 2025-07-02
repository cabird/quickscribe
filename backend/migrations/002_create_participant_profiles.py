#!/usr/bin/env python3
"""
Migration 002: Create Participant Profiles from Existing Speaker Data

This migration converts the legacy participant system to the new participant entity system:
- Scans all recordings for unique speaker names in participants arrays
- Scans all transcriptions for speaker names in speaker_mapping
- Creates Participant entities for each unique speaker (per user)
- Converts recording.participants from string[] to RecordingParticipant[]
- Updates transcription.speaker_mapping to include participant references

Usage:
    python migrations/002_create_participant_profiles.py --dry-run    # Preview changes
    python migrations/002_create_participant_profiles.py --execute   # Apply changes
    python migrations/002_create_participant_profiles.py --help      # Show help
"""

import argparse
import sys
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
import re

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db_handlers.recording_handler import RecordingHandler
from db_handlers.transcription_handler import TranscriptionHandler
from db_handlers.participant_handler import ParticipantHandler
from db_handlers.models import Recording, Transcription, Participant, RecordingParticipant, SpeakerMapping
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ParticipantMigration:
    """Handles migration from legacy to participant entity system."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.recording_handler = RecordingHandler(
            config.COSMOS_URL, 
            config.COSMOS_KEY, 
            config.COSMOS_DB_NAME, 
            config.COSMOS_CONTAINER_NAME
        )
        self.transcription_handler = TranscriptionHandler(
            config.COSMOS_URL, 
            config.COSMOS_KEY, 
            config.COSMOS_DB_NAME, 
            config.COSMOS_CONTAINER_NAME
        )
        self.participant_handler = ParticipantHandler()
        
        # Migration statistics
        self.stats = {
            'recordings_scanned': 0,
            'transcriptions_scanned': 0,
            'unique_speakers_found': 0,
            'participants_created': 0,
            'recordings_updated': 0,
            'transcriptions_updated': 0,
            'errors': []
        }
        
        # Data structures for migration
        self.speakers_by_user: Dict[str, Set[str]] = defaultdict(set)
        self.participant_mappings: Dict[str, Dict[str, str]] = defaultdict(dict)  # user_id -> {speaker_name: participant_id}
        self.recordings_to_update: List[Tuple[Recording, List[str]]] = []
        self.transcriptions_to_update: List[Tuple[Transcription, Dict]] = []

    def is_generic_speaker_name(self, name: str) -> bool:
        """
        Check if a speaker name is generic and should be skipped.
        
        Args:
            name: Speaker name to check
            
        Returns:
            True if name is generic (Speaker 1, Unknown, etc.)
        """
        if not name or not name.strip():
            return True
        
        name_lower = name.strip().lower()
        
        # Generic patterns to skip
        generic_patterns = [
            r'^speaker\s*\d+$',        # "Speaker 1", "Speaker 2", etc.
            r'^unknown$',              # "Unknown"
            r'^unidentified$',         # "Unidentified"
            r'^participant\s*\d+$',    # "Participant 1", etc.
            r'^person\s*\d+$',         # "Person 1", etc.
            r'^voice\s*\d+$',          # "Voice 1", etc.
        ]
        
        for pattern in generic_patterns:
            if re.match(pattern, name_lower):
                return True
        
        return False

    def parse_speaker_name(self, name: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Parse a speaker name into firstName, lastName, and displayName.
        
        Args:
            name: Full speaker name
            
        Returns:
            Tuple of (firstName, lastName, displayName)
        """
        if not name or not name.strip():
            return None, None, ""
        
        name = name.strip()
        name_parts = name.split()
        
        if len(name_parts) == 0:
            return None, None, name
        elif len(name_parts) == 1:
            return name_parts[0], None, name
        else:
            return name_parts[0], " ".join(name_parts[1:]), name

    def discover_speakers_from_recordings(self) -> None:
        """
        Scan all recordings to find unique speaker names.
        """
        logger.info("Discovering speakers from recordings...")
        
        try:
            # Get all recordings (this might need pagination for large datasets)
            # For now, assuming reasonable dataset size
            all_recordings = self.recording_handler.get_all_recordings()
            
            for recording in all_recordings:
                self.stats['recordings_scanned'] += 1
                
                if not recording.participants:
                    continue
                
                user_id = recording.user_id
                
                # Handle both old string[] format and new RecordingParticipant[] format
                if isinstance(recording.participants, list):
                    for participant in recording.participants:
                        if isinstance(participant, str):
                            # Old format: string
                            speaker_name = participant.strip()
                        elif hasattr(participant, 'displayName'):
                            # New format: already migrated
                            continue
                        else:
                            # Unknown format
                            logger.warning(f"Unknown participant format in recording {recording.id}: {type(participant)}")
                            continue
                        
                        if not self.is_generic_speaker_name(speaker_name):
                            self.speakers_by_user[user_id].add(speaker_name)
                            
                            # Track this recording for update
                            existing_entry = next(
                                (entry for entry in self.recordings_to_update if entry[0].id == recording.id), 
                                None
                            )
                            if existing_entry:
                                if speaker_name not in existing_entry[1]:
                                    existing_entry[1].append(speaker_name)
                            else:
                                self.recordings_to_update.append((recording, [speaker_name]))
                
                if self.stats['recordings_scanned'] % 100 == 0:
                    logger.info(f"Scanned {self.stats['recordings_scanned']} recordings...")
                    
        except Exception as e:
            error_msg = f"Error discovering speakers from recordings: {e}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)

    def discover_speakers_from_transcriptions(self) -> None:
        """
        Scan all transcriptions to find additional speaker names.
        """
        logger.info("Discovering speakers from transcriptions...")
        
        try:
            # Get all transcriptions - handle potential format issues gracefully
            try:
                all_transcriptions = self.transcription_handler.get_all_transcriptions()
            except Exception as e:
                logger.warning(f"Error fetching transcriptions, will get raw data: {e}")
                # Fallback to getting raw data from container
                items = list(self.transcription_handler.container.query_items(
                    query="SELECT * FROM c",
                    enable_cross_partition_query=True
                ))
                all_transcriptions = []
                for item in items:
                    try:
                        # Try to create Transcription object, but handle missing fields gracefully
                        if 'speaker_mapping' in item and item['speaker_mapping']:
                            # Convert old format speaker_mapping to ensure compatibility
                            for speaker_label, speaker_data in item['speaker_mapping'].items():
                                if isinstance(speaker_data, dict) and 'displayName' not in speaker_data:
                                    speaker_data['displayName'] = speaker_data.get('name', '')
                        transcription = Transcription(**item)
                        all_transcriptions.append(transcription)
                    except Exception as item_error:
                        logger.warning(f"Skipping transcription {item.get('id', 'unknown')}: {item_error}")
                        continue
            
            for transcription in all_transcriptions:
                self.stats['transcriptions_scanned'] += 1
                
                if not transcription.speaker_mapping:
                    continue
                
                user_id = transcription.user_id
                speaker_names_in_transcription = []
                
                for speaker_label, speaker_data in transcription.speaker_mapping.items():
                    # Handle both old and new speaker_mapping formats
                    if hasattr(speaker_data, 'name'):
                        speaker_name = speaker_data.name
                    elif isinstance(speaker_data, dict) and 'name' in speaker_data:
                        speaker_name = speaker_data['name']
                    else:
                        logger.warning(f"Unknown speaker_mapping format in transcription {transcription.id}")
                        continue
                    
                    if speaker_name and not self.is_generic_speaker_name(speaker_name):
                        self.speakers_by_user[user_id].add(speaker_name)
                        speaker_names_in_transcription.append(speaker_name)
                
                # Track this transcription for update if it has valid speakers
                if speaker_names_in_transcription:
                    self.transcriptions_to_update.append((transcription, {
                        'speaker_names': speaker_names_in_transcription
                    }))
                
                if self.stats['transcriptions_scanned'] % 100 == 0:
                    logger.info(f"Scanned {self.stats['transcriptions_scanned']} transcriptions...")
                    
        except Exception as e:
            error_msg = f"Error discovering speakers from transcriptions: {e}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)

    def create_participant_profiles(self) -> None:
        """
        Create Participant entities for all discovered speakers.
        """
        logger.info("Creating participant profiles...")
        
        for user_id, speaker_names in self.speakers_by_user.items():
            logger.info(f"Creating {len(speaker_names)} participants for user {user_id}")
            
            for speaker_name in speaker_names:
                if speaker_name in self.participant_mappings[user_id]:
                    continue  # Already created
                
                try:
                    # Check if participant already exists
                    existing_participants = self.participant_handler.find_participants_by_name(
                        user_id, speaker_name, fuzzy=False
                    )
                    
                    if existing_participants:
                        # Use existing participant
                        participant_id = existing_participants[0].id
                        logger.info(f"Using existing participant {participant_id} for '{speaker_name}'")
                    else:
                        # Create new participant
                        if self.dry_run:
                            # Generate fake ID for dry run
                            participant_id = f"dry-run-{len(self.participant_mappings[user_id])}"
                            logger.info(f"[DRY RUN] Would create participant for '{speaker_name}'")
                        else:
                            firstName, lastName, displayName = self.parse_speaker_name(speaker_name)
                            
                            # Create participant data with ISO string timestamps
                            now_iso = datetime.now(timezone.utc).isoformat()
                            participant_data = {
                                'displayName': displayName,
                                'firstName': firstName,
                                'lastName': lastName,
                                'aliases': [],
                                'firstSeen': now_iso,
                                'lastSeen': now_iso,
                                'createdAt': now_iso,
                                'updatedAt': now_iso
                            }
                            
                            participant = self.participant_handler.create_participant(
                                user_id=user_id,
                                **participant_data
                            )
                            participant_id = participant.id
                            logger.info(f"Created participant {participant_id} for '{speaker_name}'")
                    
                    self.participant_mappings[user_id][speaker_name] = participant_id
                    self.stats['participants_created'] += 1
                    
                except Exception as e:
                    error_msg = f"Error creating participant for '{speaker_name}' (user {user_id}): {e}"
                    logger.error(error_msg)
                    self.stats['errors'].append(error_msg)

    def update_recordings_with_participants(self) -> None:
        """
        Update recordings to use RecordingParticipant[] instead of string[].
        """
        logger.info(f"Updating {len(self.recordings_to_update)} recordings...")
        
        for recording, speaker_names in self.recordings_to_update:
            try:
                user_id = recording.user_id
                new_participants = []
                
                # Convert string participants to RecordingParticipant objects
                if isinstance(recording.participants, list):
                    for i, participant in enumerate(recording.participants):
                        if isinstance(participant, str):
                            speaker_name = participant.strip()
                            
                            if self.is_generic_speaker_name(speaker_name):
                                continue  # Skip generic names
                            
                            participant_id = self.participant_mappings[user_id].get(speaker_name)
                            if participant_id:
                                new_participants.append(RecordingParticipant(
                                    participantId=participant_id,
                                    displayName=speaker_name,
                                    speakerLabel=f"Speaker {i + 1}",
                                    confidence=1.0,  # High confidence for migrated data
                                    manuallyVerified=True  # Consider migrated data as verified
                                ))
                        elif hasattr(participant, 'participantId'):
                            # Already in new format, keep as is
                            new_participants.append(participant)
                
                if new_participants:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would update recording {recording.id} with {len(new_participants)} participant links")
                    else:
                        recording.participants = new_participants
                        self.recording_handler.update_recording(recording)
                        logger.info(f"Updated recording {recording.id} with {len(new_participants)} participant links")
                    
                    self.stats['recordings_updated'] += 1
                
            except Exception as e:
                error_msg = f"Error updating recording {recording.id}: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)

    def update_transcriptions_with_participants(self) -> None:
        """
        Update transcriptions to include participant references in speaker_mapping.
        """
        logger.info(f"Updating {len(self.transcriptions_to_update)} transcriptions...")
        
        for transcription, update_data in self.transcriptions_to_update:
            try:
                user_id = transcription.user_id
                updated_speaker_mapping = {}
                
                if not transcription.speaker_mapping:
                    continue
                
                for speaker_label, speaker_data in transcription.speaker_mapping.items():
                    # Get speaker name from existing data
                    if hasattr(speaker_data, 'name'):
                        speaker_name = speaker_data.name
                        reasoning = getattr(speaker_data, 'reasoning', '')
                    elif isinstance(speaker_data, dict):
                        speaker_name = speaker_data.get('name', '')
                        reasoning = speaker_data.get('reasoning', '')
                    else:
                        logger.warning(f"Unknown speaker_mapping format in transcription {transcription.id}")
                        continue
                    
                    participant_id = None
                    if not self.is_generic_speaker_name(speaker_name):
                        participant_id = self.participant_mappings[user_id].get(speaker_name)
                    
                    # Create enhanced SpeakerMapping with optional fields
                    speaker_mapping_data = {
                        "name": speaker_name,
                        "reasoning": reasoning
                    }
                    
                    # Add optional fields only if they have meaningful values
                    if speaker_name:  # Only add displayName if we have a name
                        speaker_mapping_data["displayName"] = speaker_name
                    if participant_id:
                        speaker_mapping_data["participantId"] = participant_id
                        speaker_mapping_data["confidence"] = 1.0
                        speaker_mapping_data["manuallyVerified"] = True
                    
                    updated_speaker_mapping[speaker_label] = SpeakerMapping(**speaker_mapping_data)
                
                if updated_speaker_mapping:
                    if self.dry_run:
                        participant_count = sum(1 for data in updated_speaker_mapping.values() if data.participantId)
                        logger.info(f"[DRY RUN] Would update transcription {transcription.id} with {participant_count} participant links")
                    else:
                        transcription.speaker_mapping = updated_speaker_mapping
                        self.transcription_handler.update_transcription(transcription)
                        participant_count = sum(1 for data in updated_speaker_mapping.values() if data.participantId)
                        logger.info(f"Updated transcription {transcription.id} with {participant_count} participant links")
                    
                    self.stats['transcriptions_updated'] += 1
                
            except Exception as e:
                error_msg = f"Error updating transcription {transcription.id}: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)

    def validate_migration(self) -> bool:
        """
        Validate the migration results.
        
        Returns:
            True if validation passes
        """
        logger.info("Validating migration results...")
        
        if self.dry_run:
            logger.info("Skipping validation for dry run")
            return True
        
        validation_passed = True
        
        try:
            # Check that all expected participants were created
            for user_id, speaker_names in self.speakers_by_user.items():
                for speaker_name in speaker_names:
                    if speaker_name not in self.participant_mappings[user_id]:
                        logger.error(f"Participant not created for '{speaker_name}' (user {user_id})")
                        validation_passed = False
            
            # Verify some recordings were updated
            if self.recordings_to_update and self.stats['recordings_updated'] == 0:
                logger.error("No recordings were updated despite having recordings to update")
                validation_passed = False
            
            # Verify some transcriptions were updated
            if self.transcriptions_to_update and self.stats['transcriptions_updated'] == 0:
                logger.error("No transcriptions were updated despite having transcriptions to update")
                validation_passed = False
                
        except Exception as e:
            logger.error(f"Error during validation: {e}")
            validation_passed = False
        
        return validation_passed

    def print_summary(self) -> None:
        """
        Print migration summary statistics.
        """
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        
        mode = "DRY RUN" if self.dry_run else "EXECUTION"
        print(f"Mode: {mode}")
        print(f"Recordings scanned: {self.stats['recordings_scanned']}")
        print(f"Transcriptions scanned: {self.stats['transcriptions_scanned']}")
        print(f"Unique speakers found: {self.stats['unique_speakers_found']}")
        print(f"Participants created: {self.stats['participants_created']}")
        print(f"Recordings updated: {self.stats['recordings_updated']}")
        print(f"Transcriptions updated: {self.stats['transcriptions_updated']}")
        print(f"Errors encountered: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            print("\nErrors:")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        # Show sample participant mappings
        print(f"\nSample participant mappings:")
        for user_id, mappings in list(self.participant_mappings.items())[:3]:
            print(f"  User {user_id}:")
            for speaker_name, participant_id in list(mappings.items())[:5]:
                print(f"    '{speaker_name}' -> {participant_id}")
        
        print("="*60)

    def run_migration(self) -> bool:
        """
        Run the complete migration process.
        
        Returns:
            True if migration completed successfully
        """
        try:
            logger.info(f"Starting participant migration ({'DRY RUN' if self.dry_run else 'EXECUTION'})")
            
            # Step 1: Discover all speakers
            self.discover_speakers_from_recordings()
            self.discover_speakers_from_transcriptions()
            
            # Calculate unique speakers
            total_speakers = sum(len(speakers) for speakers in self.speakers_by_user.values())
            self.stats['unique_speakers_found'] = total_speakers
            
            logger.info(f"Found {total_speakers} unique speakers across {len(self.speakers_by_user)} users")
            
            if total_speakers == 0:
                logger.info("No speakers found to migrate")
                return True
            
            # Step 2: Create participant profiles
            self.create_participant_profiles()
            
            # Step 3: Update recordings
            self.update_recordings_with_participants()
            
            # Step 4: Update transcriptions
            self.update_transcriptions_with_participants()
            
            # Step 5: Validate results
            if not self.dry_run:
                validation_passed = self.validate_migration()
                if not validation_passed:
                    logger.error("Migration validation failed!")
                    return False
            
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main migration script entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy participant data to new participant entity system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrations/002_create_participant_profiles.py --dry-run
  python migrations/002_create_participant_profiles.py --execute
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true', 
        help='Apply the migration changes'
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")
    
    if args.dry_run and args.execute:
        parser.error("Cannot specify both --dry-run and --execute")
    
    # Run migration
    migration = ParticipantMigration(dry_run=args.dry_run)
    success = migration.run_migration()
    migration.print_summary()
    
    if success:
        print(f"\nMigration {'preview' if args.dry_run else 'execution'} completed successfully!")
        sys.exit(0)
    else:
        print(f"\nMigration {'preview' if args.dry_run else 'execution'} failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()