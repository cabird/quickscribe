#!/usr/bin/env python3
"""
Script to sync recording participants from transcription speaker mappings.
This fixes recordings where participants were replaced instead of merged.
"""

import sys
import os

# Add the backend directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
backend_dir = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_dir)

from datetime import datetime
import argparse
import json
from db_handlers.recording_handler import RecordingHandler
from db_handlers.transcription_handler import TranscriptionHandler
from db_handlers.user_handler import UserHandler
from db_handlers.models import RecordingParticipant
from config import config
from logging_config import get_logger

logger = get_logger('sync_recording_participants')

def sync_participants_for_recording(recording_id: str, dry_run: bool = True) -> dict:
    """
    Sync participants for a single recording from its transcription speaker mapping.
    
    Args:
        recording_id: ID of the recording to sync
        dry_run: If True, only show what would be changed without updating
        
    Returns:
        Dict with sync results
    """
    recording_handler = RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
    transcription_handler = TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
    
    # Get recording
    recording = recording_handler.get_recording(recording_id)
    if not recording:
        return {'error': f'Recording {recording_id} not found'}
    
    # Get transcription if it exists
    if not recording.transcription_id:
        return {'error': f'Recording {recording_id} has no transcription'}
    
    try:
        transcription = transcription_handler.get_transcription(recording.transcription_id)
        if not transcription:
            return {'error': f'Transcription {recording.transcription_id} not found'}
    except Exception as e:
        # Handle case where transcription doesn't exist in DB
        return {'error': f'Transcription {recording.transcription_id} not found: {str(e)}'}
    
    # Get speaker mapping
    speaker_mapping = transcription.speaker_mapping or {}
    if not speaker_mapping:
        return {'info': 'No speaker mapping in transcription'}
    
    # Build participants from speaker mapping
    new_participants = []
    speaker_count = 0
    
    for speaker_label, speaker_data in speaker_mapping.items():
        # Handle different data formats
        if hasattr(speaker_data, 'model_dump'):
            # Pydantic model
            data = speaker_data.model_dump()
        elif isinstance(speaker_data, dict):
            data = speaker_data
        else:
            logger.warning(f"Unknown speaker data type for {speaker_label}: {type(speaker_data)}")
            continue
        
        participant_id = data.get('participantId')
        display_name = data.get('displayName') or data.get('name')
        manually_verified = data.get('manuallyVerified', False)
        confidence = data.get('confidence', 0.5)
        
        if participant_id and display_name:
            recording_participant = RecordingParticipant(
                participantId=participant_id,
                displayName=display_name,
                speakerLabel=speaker_label,
                confidence=confidence,
                manuallyVerified=manually_verified
            )
            new_participants.append(recording_participant)
            speaker_count += 1
    
    # Compare with existing
    existing_participants = recording.participants or []
    existing_count = len(existing_participants)
    
    result = {
        'recording_id': recording_id,
        'title': recording.title or recording.original_filename,
        'existing_participants': existing_count,
        'speakers_in_transcription': speaker_count,
        'new_participant_count': len(new_participants),
        'changes': []
    }
    
    # Check what would change
    existing_by_label = {p.speakerLabel: p for p in existing_participants if p.speakerLabel}
    
    for new_p in new_participants:
        if new_p.speakerLabel not in existing_by_label:
            result['changes'].append(f"Add {new_p.speakerLabel}: {new_p.displayName}")
        elif existing_by_label[new_p.speakerLabel].displayName != new_p.displayName:
            old_name = existing_by_label[new_p.speakerLabel].displayName
            result['changes'].append(f"Update {new_p.speakerLabel}: {old_name} → {new_p.displayName}")
    
    # Update if not dry run
    if not dry_run and new_participants:
        recording.participants = new_participants
        recording_handler.update_recording(recording)
        result['status'] = 'updated'
        logger.info(f"Updated recording {recording_id} with {len(new_participants)} participants")
    else:
        result['status'] = 'dry_run' if dry_run else 'no_changes'
    
    return result

def sync_all_recordings(user_id: str = None, dry_run: bool = True) -> list:
    """
    Sync participants for all recordings (or all recordings for a specific user).
    
    Args:
        user_id: Optional user ID to filter recordings
        dry_run: If True, only show what would be changed
        
    Returns:
        List of sync results
    """
    recording_handler = RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
    
    if user_id:
        recordings = recording_handler.get_user_recordings(user_id)
        logger.info(f"Processing {len(recordings)} recordings for user {user_id}")
    else:
        # Get all recordings (would need to implement this method)
        logger.error("Getting all recordings not implemented - please specify a user_id")
        return []
    
    results = []
    recordings_with_changes = 0
    total_changes = 0
    
    for recording in recordings:
        result = sync_participants_for_recording(recording.id, dry_run)
        
        # Skip errors for missing transcriptions
        if 'error' in result:
            # Only log if it's not a simple "not found" error
            if 'not found' not in result['error'].lower():
                logger.warning(f"Error processing recording {recording.id}: {result['error']}")
            continue
            
        if result.get('changes'):
            recordings_with_changes += 1
            total_changes += len(result['changes'])
            results.append(result)
    
    logger.info(f"Found {recordings_with_changes} recordings needing updates with {total_changes} total changes")
    return results

def main():
    parser = argparse.ArgumentParser(description='Sync recording participants from transcription speaker mappings')
    parser.add_argument('--user-id', help='User ID to sync recordings for')
    parser.add_argument('--recording-id', help='Specific recording ID to sync')
    parser.add_argument('--dry-run', action='store_true', default=True, 
                       help='Show what would be changed without updating (default: True)')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually perform the updates (overrides --dry-run)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show all recordings, even those without changes')
    
    args = parser.parse_args()
    
    # Override dry_run if execute is specified
    dry_run = not args.execute
    
    if dry_run:
        print("DRY RUN MODE - No changes will be made. Use --execute to apply changes.")
        print("-" * 60)
    
    if args.recording_id:
        # Sync single recording
        result = sync_participants_for_recording(args.recording_id, dry_run)
        if 'error' in result:
            print(f"Error: {result['error']}")
        else:
            print(f"\nRecording: {result['title']} ({result['recording_id']})")
            print(f"  Existing participants: {result['existing_participants']}")
            print(f"  Speakers in transcription: {result['speakers_in_transcription']}")
            if result['changes']:
                print("  Changes:")
                for change in result['changes']:
                    print(f"    - {change}")
            else:
                print("  No changes needed")
    
    elif args.user_id:
        # Sync all recordings for user
        results = sync_all_recordings(args.user_id, dry_run)
        
        if not results and not args.verbose:
            print("No recordings need updates.")
        else:
            for result in results:
                if result.get('changes') or args.verbose:
                    print(f"\nRecording: {result['title']} ({result['recording_id']})")
                    print(f"  Existing participants: {result['existing_participants']}")
                    print(f"  Speakers in transcription: {result['speakers_in_transcription']}")
                    if result['changes']:
                        print("  Changes:")
                        for change in result['changes']:
                            print(f"    - {change}")
                    else:
                        print("  No changes needed")
        
        # Summary
        total_changes = sum(len(r.get('changes', [])) for r in results)
        if total_changes > 0:
            print(f"\nSummary: {len(results)} recordings would be updated with {total_changes} changes")
            if dry_run:
                print("Run with --execute to apply these changes")
    
    else:
        print("Please specify either --user-id or --recording-id")
        parser.print_help()

if __name__ == "__main__":
    main()