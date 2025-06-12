#!/usr/bin/env python3
"""
Migration 001: Normalize Diarized Transcripts

This migration converts existing diarized transcripts from the old format 
(with speaker names like "John:", "Jane:") to the new normalized format 
(with "Speaker 1:", "Speaker 2:", etc.) and creates proper speaker_mapping.

BEFORE:
- diarized_transcript: "John: Hello there\nJane: Hi John\nJohn: How are you?"
- speaker_mapping: {"Speaker 1": {"name": "John", ...}, "Speaker 2": {"name": "Jane", ...}}

AFTER:
- diarized_transcript: "Speaker 1: Hello there\nSpeaker 2: Hi John\nSpeaker 1: How are you?"
- speaker_mapping: {"Speaker 1": {"name": "John", ...}, "Speaker 2": {"name": "Jane", ...}}

Usage:
    python migrations/001_normalize_diarized_transcripts.py --dry-run
    python migrations/001_normalize_diarized_transcripts.py --execute
"""

import re
import sys
import os
from typing import Dict, List, Tuple, Optional

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_handlers.models import SpeakerMapping
from migration_runner import MigrationRunner

class NormalizeDiarizedTranscriptsMigration(MigrationRunner):
    """Migration to normalize diarized transcripts to use Speaker X format."""
    
    def __init__(self):
        super().__init__(
            migration_name="001_normalize_diarized_transcripts",
            description="Convert diarized transcripts from speaker names to 'Speaker X' format"
        )
    
    def is_already_normalized(self, transcript: str) -> bool:
        """Check if transcript is already in normalized format (Speaker 1:, Speaker 2:, etc.)"""
        if not transcript:
            return True
            
        lines = transcript.split('\n')
        speaker_lines = [line for line in lines if ':' in line and line.strip()]
        
        if not speaker_lines:
            return True
            
        # Check if all speaker lines start with "Speaker X:"
        speaker_pattern = re.compile(r'^Speaker \d+:')
        normalized_lines = [line for line in speaker_lines if speaker_pattern.match(line.strip())]
        
        # If more than 80% of speaker lines are already normalized, consider it normalized
        return len(normalized_lines) / len(speaker_lines) > 0.8
    
    def extract_speakers_in_order(self, transcript: str) -> List[str]:
        """Extract unique speaker names in order of first appearance."""
        if not transcript:
            return []
            
        speakers_seen = []
        lines = transcript.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
                
            # Extract speaker name (everything before first colon)
            speaker_match = line.split(':', 1)
            if len(speaker_match) >= 2:
                speaker_name = speaker_match[0].strip()
                
                # Skip if already a normalized format
                if re.match(r'^Speaker \d+$', speaker_name):
                    continue
                    
                # Add to list if not seen before
                if speaker_name not in speakers_seen:
                    speakers_seen.append(speaker_name)
        
        return speakers_seen
    
    def normalize_transcript(self, transcript: str, speaker_mapping: Dict[str, str]) -> str:
        """Convert transcript to use Speaker X format."""
        if not transcript:
            return transcript
            
        lines = transcript.split('\n')
        normalized_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                normalized_lines.append('')
                continue
                
            if ':' not in line:
                normalized_lines.append(line)
                continue
                
            # Split speaker and content
            speaker_match = line.split(':', 1)
            if len(speaker_match) >= 2:
                original_speaker = speaker_match[0].strip()
                content = speaker_match[1].strip()
                
                # Use mapping if available, otherwise keep original
                normalized_speaker = speaker_mapping.get(original_speaker, original_speaker)
                normalized_lines.append(f"{normalized_speaker}: {content}")
            else:
                normalized_lines.append(line)
        
        return '\n'.join(normalized_lines)
    
    def create_speaker_mapping(self, speakers: List[str]) -> Dict[str, SpeakerMapping]:
        """Create speaker mapping from list of speaker names."""
        mapping = {}
        for i, speaker_name in enumerate(speakers, 1):
            speaker_label = f"Speaker {i}"
            mapping[speaker_label] = SpeakerMapping(
                name=speaker_name,
                reasoning="Migrated from old format"
            )
        return mapping
    
    def process_transcription(self, transcription, dry_run: bool = False) -> Tuple[bool, str]:
        """Process a single transcription. Returns (changed, message)."""
        try:
            # Skip if no diarized transcript
            if not transcription.diarized_transcript:
                return False, "No diarized transcript"
            
            # Skip if already normalized
            if self.is_already_normalized(transcription.diarized_transcript):
                return False, "Already normalized"
            
            # Extract speakers in order
            speakers = self.extract_speakers_in_order(transcription.diarized_transcript)
            if not speakers:
                return False, "No speakers found"
            
            # Create mapping from original names to Speaker X
            name_to_label_mapping = {}
            for i, speaker_name in enumerate(speakers, 1):
                name_to_label_mapping[speaker_name] = f"Speaker {i}"
            
            # Normalize the transcript
            normalized_transcript = self.normalize_transcript(
                transcription.diarized_transcript, 
                name_to_label_mapping
            )
            
            # Create proper speaker mapping
            new_speaker_mapping = self.create_speaker_mapping(speakers)
            
            # Log the changes
            self.logger.info(f"Transcription {transcription.id}:")
            self.logger.info(f"  Speakers found: {speakers}")
            self.logger.info(f"  Mapping: {name_to_label_mapping}")
            
            if not dry_run:
                # Update the transcription
                transcription.diarized_transcript = normalized_transcript
                transcription.speaker_mapping = new_speaker_mapping
                self.transcription_handler.update_transcription(transcription)
            
            return True, f"Normalized {len(speakers)} speakers"
            
        except Exception as e:
            error_msg = f"Error processing transcription {transcription.id}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def run_migration(self, dry_run: bool = False, limit: Optional[int] = None):
        """Run the migration."""
        log_file = self.setup_logging(dry_run)
        
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
        error_count = 0
        
        self.logger.info(f"Found {total_count} transcriptions to process")
        
        for i, transcription in enumerate(all_transcriptions):
            changed, message = self.process_transcription(transcription, dry_run)
            
            if changed:
                changed_count += 1
            
            if "Error" in message:
                error_count += 1
            
            processed_count += 1
            
            # Log progress
            if processed_count % 10 == 0 or processed_count == total_count:
                self.log_progress(
                    processed_count, 
                    total_count, 
                    f"Changed: {changed_count}, Errors: {error_count}"
                )
        
        # Summary
        self.logger.info("Migration completed!")
        self.logger.info(f"Total processed: {processed_count}")
        self.logger.info(f"Total changed: {changed_count}")
        self.logger.info(f"Total errors: {error_count}")
        self.logger.info(f"Log file: {log_file}")
        
        print(f"\n✅ Migration completed!")
        print(f"📊 Results: {changed_count} changed, {error_count} errors out of {processed_count} processed")
        print(f"📄 Full log: {log_file}")

def main():
    migration = NormalizeDiarizedTranscriptsMigration()
    parser = migration.create_argument_parser()
    args = parser.parse_args()
    
    migration.run_migration(
        dry_run=args.dry_run,
        limit=args.limit
    )

if __name__ == "__main__":
    main()