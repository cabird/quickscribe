#!/usr/bin/env python3
"""
Database Consistency Checker for QuickScribe

This script performs comprehensive consistency checks on the QuickScribe database,
including referential integrity, data validation, and business rule enforcement.

NOTE: As of Jan 2026, recording.participants is DEPRECATED. Speaker mappings
are now stored only in transcription.speaker_mapping. Many checks in this script
that reference recording.participants are obsolete and should be updated.

Usage:
    python db_consistency_checker.py [options]

Options:
    --fix           Attempt to fix issues where possible (use with caution)
    --check TYPE    Run specific check type (integrity, quality, migration, etc.)
    --user USER_ID  Check only a specific user's data
    --verbose       Show detailed output for each issue
    --report FILE   Save detailed report to file
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set, Optional, Tuple, Any
import re
from pathlib import Path

# Add backend directory to path to import modules correctly
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from db_handlers.handler_factory import (
    create_user_handler,
    create_recording_handler,
    create_transcription_handler,
    create_participant_handler,
    create_analysis_type_handler,
    create_sync_progress_handler
)
from db_handlers.models import (
    User, Recording, Transcription, Participant,
    AnalysisType, RecordingParticipant, SyncProgress,
    TranscriptionStatus, TranscodingStatus, Source
)


class ConsistencyIssue:
    """Represents a single consistency issue found during checking"""
    
    def __init__(self, category: str, severity: str, description: str, 
                 affected_items: List[str], fix_available: bool = False,
                 fix_action: Optional[str] = None):
        self.category = category
        self.severity = severity  # 'critical', 'warning', 'info'
        self.description = description
        self.affected_items = affected_items
        self.fix_available = fix_available
        self.fix_action = fix_action
        self.timestamp = datetime.now(timezone.utc)


class DatabaseConsistencyChecker:
    """Main consistency checker class"""
    
    def __init__(self, fix_mode: bool = False, verbose: bool = False):
        self.fix_mode = fix_mode
        self.verbose = verbose
        self.issues: List[ConsistencyIssue] = []
        self.stats = defaultdict(int)
        
        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize handlers
        self.user_handler = create_user_handler()
        self.recording_handler = create_recording_handler()
        self.transcription_handler = create_transcription_handler()
        self.participant_handler = create_participant_handler()
        self.analysis_type_handler = create_analysis_type_handler()
        self.sync_progress_handler = create_sync_progress_handler()
        
        # Cache for performance
        self.users_cache: Dict[str, User] = {}
        self.recordings_cache: Dict[str, Recording] = {}
        self.transcriptions_cache: Dict[str, Transcription] = {}
        self.participants_cache: Dict[str, Participant] = {}
        self.analysis_types_cache: Dict[str, AnalysisType] = {}
        
    def load_all_data(self, user_id: Optional[str] = None):
        """Load all data into cache for efficient checking"""
        self.logger.info("Loading data from database...")
        
        # Load users
        if user_id:
            user = self.user_handler.get_user(user_id)
            if user:
                self.users_cache[user.id] = user
        else:
            users = self.user_handler.get_all_users()
            for user in users:
                self.users_cache[user.id] = user
        
        self.logger.info(f"Loaded {len(self.users_cache)} users")
        
        # Load recordings
        for user in self.users_cache.values():
            recordings = self.recording_handler.get_user_recordings(user.id)
            for recording in recordings:
                self.recordings_cache[recording.id] = recording
        
        self.logger.info(f"Loaded {len(self.recordings_cache)} recordings")
        
        # Load transcriptions
        for recording_id in self.recordings_cache:
            transcription = self.transcription_handler.get_transcription_by_recording(recording_id)
            if transcription:
                self.transcriptions_cache[transcription.id] = transcription
        
        self.logger.info(f"Loaded {len(self.transcriptions_cache)} transcriptions")
        
        # Load participants
        for user in self.users_cache.values():
            participants = self.participant_handler.get_participants_for_user(user.id)
            for participant in participants:
                self.participants_cache[participant.id] = participant
        
        self.logger.info(f"Loaded {len(self.participants_cache)} participants")
        
        # Load analysis types
        analysis_types = self.analysis_type_handler.get_all_analysis_types()
        for at in analysis_types:
            self.analysis_types_cache[at.id] = at
        
        self.logger.info(f"Loaded {len(self.analysis_types_cache)} analysis types")
        
    def add_issue(self, issue: ConsistencyIssue):
        """Add an issue to the list and update stats"""
        self.issues.append(issue)
        self.stats[f"{issue.category}_{issue.severity}"] += 1
        
        if self.verbose:
            self.logger.debug(f"{issue.severity.upper()}: {issue.description}")
            for item in issue.affected_items[:5]:  # Show first 5 items
                self.logger.debug(f"  - {item}")
            if len(issue.affected_items) > 5:
                self.logger.debug(f"  ... and {len(issue.affected_items) - 5} more")
    
    def check_referential_integrity(self):
        """Check all foreign key references"""
        self.logger.info("Checking referential integrity...")
        
        # Check recording.user_id references
        invalid_user_refs = []
        for recording in self.recordings_cache.values():
            if recording.user_id not in self.users_cache:
                invalid_user_refs.append(f"Recording {recording.id} references non-existent user {recording.user_id}")
        
        if invalid_user_refs:
            self.add_issue(ConsistencyIssue(
                category="referential_integrity",
                severity="critical",
                description="Recordings reference non-existent users",
                affected_items=invalid_user_refs
            ))
        
        # Check transcription references
        invalid_recording_refs = []
        invalid_trans_user_refs = []
        for transcription in self.transcriptions_cache.values():
            if transcription.recording_id not in self.recordings_cache:
                invalid_recording_refs.append(f"Transcription {transcription.id} references non-existent recording {transcription.recording_id}")
            if transcription.user_id not in self.users_cache:
                invalid_trans_user_refs.append(f"Transcription {transcription.id} references non-existent user {transcription.user_id}")
        
        if invalid_recording_refs:
            self.add_issue(ConsistencyIssue(
                category="referential_integrity",
                severity="critical",
                description="Transcriptions reference non-existent recordings",
                affected_items=invalid_recording_refs
            ))
        
        if invalid_trans_user_refs:
            self.add_issue(ConsistencyIssue(
                category="referential_integrity",
                severity="critical",
                description="Transcriptions reference non-existent users",
                affected_items=invalid_trans_user_refs
            ))
        
        # Check participant references in recordings
        invalid_participant_refs = []
        for recording in self.recordings_cache.values():
            if recording.participants and isinstance(recording.participants, list):
                for i, participant in enumerate(recording.participants):
                    if hasattr(participant, 'participantId') and participant.participantId:
                        if participant.participantId not in self.participants_cache:
                            invalid_participant_refs.append(
                                f"Recording {recording.id} references non-existent participant {participant.participantId}"
                            )
        
        if invalid_participant_refs:
            self.add_issue(ConsistencyIssue(
                category="referential_integrity",
                severity="warning",
                description="Recordings reference non-existent participants",
                affected_items=invalid_participant_refs
            ))
        
        # Check tag references
        invalid_tag_refs = []
        for recording in self.recordings_cache.values():
            if recording.tagIds:
                user = self.users_cache.get(recording.user_id)
                if user and user.tags:
                    user_tag_ids = {tag.id for tag in user.tags}
                    for tag_id in recording.tagIds:
                        if tag_id not in user_tag_ids:
                            invalid_tag_refs.append(
                                f"Recording {recording.id} references non-existent tag {tag_id}"
                            )
        
        if invalid_tag_refs:
            self.add_issue(ConsistencyIssue(
                category="referential_integrity",
                severity="warning",
                description="Recordings reference non-existent tags",
                affected_items=invalid_tag_refs,
                fix_available=True,
                fix_action="Remove invalid tag references from recordings"
            ))
    
    def check_one_to_one_relationships(self):
        """Check one-to-one relationship constraints"""
        self.logger.info("Checking one-to-one relationships...")
        
        # Check for duplicate transcriptions per recording
        recording_transcription_map = defaultdict(list)
        for transcription in self.transcriptions_cache.values():
            recording_transcription_map[transcription.recording_id].append(transcription.id)
        
        duplicate_transcriptions = []
        for recording_id, trans_ids in recording_transcription_map.items():
            if len(trans_ids) > 1:
                duplicate_transcriptions.append(
                    f"Recording {recording_id} has {len(trans_ids)} transcriptions: {trans_ids}"
                )
        
        if duplicate_transcriptions:
            self.add_issue(ConsistencyIssue(
                category="relationship_constraint",
                severity="critical",
                description="Recordings with multiple transcriptions (should be 1:1)",
                affected_items=duplicate_transcriptions
            ))
        
        # Check for orphaned transcriptions
        orphaned_transcriptions = []
        for transcription in self.transcriptions_cache.values():
            if transcription.recording_id not in self.recordings_cache:
                orphaned_transcriptions.append(
                    f"Transcription {transcription.id} has no matching recording"
                )
        
        if orphaned_transcriptions:
            self.add_issue(ConsistencyIssue(
                category="orphaned_data",
                severity="warning",
                description="Orphaned transcriptions without recordings",
                affected_items=orphaned_transcriptions,
                fix_available=True,
                fix_action="Delete orphaned transcriptions"
            ))
        
        # Check recordings marked as completed without transcriptions
        missing_transcriptions = []
        for recording in self.recordings_cache.values():
            if recording.transcription_status == TranscriptionStatus.completed:
                if recording.id not in recording_transcription_map:
                    missing_transcriptions.append(
                        f"Recording {recording.id} marked as completed but has no transcription"
                    )
        
        if missing_transcriptions:
            self.add_issue(ConsistencyIssue(
                category="data_consistency",
                severity="critical",
                description="Recordings marked as completed without transcriptions",
                affected_items=missing_transcriptions,
                fix_available=True,
                fix_action="Update transcription status to 'failed'"
            ))
    
    def check_data_consistency(self):
        """Check data format and value consistency"""
        self.logger.info("Checking data consistency...")
        
        # Check recording participants format
        legacy_participant_formats = []
        mixed_participant_formats = []
        invalid_participant_objects = []
        
        for recording in self.recordings_cache.values():
            if recording.participants:
                has_strings = any(isinstance(p, str) for p in recording.participants)
                has_objects = any(hasattr(p, 'participantId') for p in recording.participants)
                
                if has_strings and not has_objects:
                    legacy_participant_formats.append(
                        f"Recording {recording.id} uses legacy string[] participant format"
                    )
                elif has_strings and has_objects:
                    mixed_participant_formats.append(
                        f"Recording {recording.id} has mixed participant formats"
                    )
                elif has_objects:
                    # Validate the new format objects
                    for idx, p in enumerate(recording.participants):
                        if hasattr(p, 'participantId'):
                            # Check required fields
                            if not hasattr(p, 'name') or not p.name:
                                invalid_participant_objects.append(
                                    f"Recording {recording.id} participant[{idx}] missing required 'name' field"
                                )
                            # Validate participantId is not just a string (should be None or valid UUID)
                            if p.participantId and not isinstance(p.participantId, str):
                                invalid_participant_objects.append(
                                    f"Recording {recording.id} participant[{idx}] has invalid participantId type"
                                )
        
        if legacy_participant_formats:
            self.add_issue(ConsistencyIssue(
                category="data_migration",
                severity="info",
                description="Recordings using legacy participant format",
                affected_items=legacy_participant_formats,
                fix_available=True,
                fix_action="Migrate to RecordingParticipant format"
            ))
        
        if mixed_participant_formats:
            self.add_issue(ConsistencyIssue(
                category="data_consistency",
                severity="critical",
                description="Recordings with mixed participant formats",
                affected_items=mixed_participant_formats
            ))
        
        if invalid_participant_objects:
            self.add_issue(ConsistencyIssue(
                category="data_consistency",
                severity="warning",
                description="Recordings with invalid participant object structure",
                affected_items=invalid_participant_objects,
                fix_available=True,
                fix_action="Fix invalid participant object fields"
            ))
        
        # Check duration validity
        invalid_durations = []
        for recording in self.recordings_cache.values():
            if recording.duration is not None:
                if recording.duration <= 0 or recording.duration > 86400:  # > 24 hours
                    invalid_durations.append(
                        f"Recording {recording.id} has invalid duration: {recording.duration}s"
                    )
        
        if invalid_durations:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="warning",
                description="Recordings with invalid durations",
                affected_items=invalid_durations
            ))
        
        # Check datetime format validity
        invalid_datetimes = []
        for recording in self.recordings_cache.values():
            try:
                if recording.upload_timestamp:
                    datetime.fromisoformat(recording.upload_timestamp.replace('Z', '+00:00'))
                if recording.recorded_timestamp:
                    datetime.fromisoformat(recording.recorded_timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError) as e:
                invalid_datetimes.append(
                    f"Recording {recording.id} has invalid datetime format"
                )
        
        if invalid_datetimes:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="warning",
                description="Records with invalid datetime formats",
                affected_items=invalid_datetimes
            ))
        
        # Check enum value validity
        invalid_enums = []
        valid_transcription_statuses = {s.value for s in TranscriptionStatus}
        valid_transcoding_statuses = {s.value for s in TranscodingStatus}
        valid_sources = {s.value for s in Source}
        
        for recording in self.recordings_cache.values():
            if recording.transcription_status and recording.transcription_status not in valid_transcription_statuses:
                invalid_enums.append(
                    f"Recording {recording.id} has invalid transcription_status: {recording.transcription_status}"
                )
            if recording.transcoding_status and recording.transcoding_status not in valid_transcoding_statuses:
                invalid_enums.append(
                    f"Recording {recording.id} has invalid transcoding_status: {recording.transcoding_status}"
                )
            if recording.source and recording.source not in valid_sources:
                invalid_enums.append(
                    f"Recording {recording.id} has invalid source: {recording.source}"
                )
        
        if invalid_enums:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="critical",
                description="Records with invalid enum values",
                affected_items=invalid_enums
            ))
    
    def check_business_rules(self):
        """Check business rule compliance"""
        self.logger.info("Checking business rules...")
        
        # Check built-in analysis types
        invalid_builtin_types = []
        for at in self.analysis_types_cache.values():
            if at.isBuiltIn and at.userId is not None:
                invalid_builtin_types.append(
                    f"Built-in analysis type {at.id} has userId: {at.userId}"
                )
            if not at.isBuiltIn and at.userId is None:
                invalid_builtin_types.append(
                    f"Custom analysis type {at.id} has no userId"
                )
        
        if invalid_builtin_types:
            self.add_issue(ConsistencyIssue(
                category="business_rule",
                severity="critical",
                description="Analysis types violate built-in/custom rules",
                affected_items=invalid_builtin_types
            ))
        
        # Check multiple isUser participants per user
        user_participant_count = defaultdict(list)
        for participant in self.participants_cache.values():
            if participant.isUser:
                user_participant_count[participant.userId].append(participant.id)
        
        multiple_user_participants = []
        for user_id, participant_ids in user_participant_count.items():
            if len(participant_ids) > 1:
                multiple_user_participants.append(
                    f"User {user_id} has {len(participant_ids)} participants marked as isUser"
                )
        
        if multiple_user_participants:
            self.add_issue(ConsistencyIssue(
                category="business_rule",
                severity="warning",
                description="Users with multiple participants marked as self",
                affected_items=multiple_user_participants,
                fix_available=True,
                fix_action="Keep only the most recently used isUser participant"
            ))
        
        # Check unique tag names within user
        for user in self.users_cache.values():
            if user.tags:
                tag_names = [tag.name.lower() for tag in user.tags]
                duplicates = [name for name in tag_names if tag_names.count(name) > 1]
                if duplicates:
                    self.add_issue(ConsistencyIssue(
                        category="business_rule",
                        severity="warning",
                        description=f"User {user.id} has duplicate tag names",
                        affected_items=list(set(duplicates)),
                        fix_available=True,
                        fix_action="Merge duplicate tags"
                    ))
        
        # Check Plaud recordings have metadata
        missing_plaud_metadata = []
        for recording in self.recordings_cache.values():
            if recording.source == Source.plaud and not recording.plaudMetadata:
                missing_plaud_metadata.append(
                    f"Plaud recording {recording.id} missing plaudMetadata"
                )
        
        if missing_plaud_metadata:
            self.add_issue(ConsistencyIssue(
                category="business_rule",
                severity="warning",
                description="Plaud recordings missing required metadata",
                affected_items=missing_plaud_metadata
            ))
    
    def check_data_migration_health(self):
        """Check for data migration issues"""
        self.logger.info("Checking data migration health...")
        
        # Check for missing required fields with defaults
        missing_titles = []
        missing_descriptions = []
        missing_timestamps = []
        
        for recording in self.recordings_cache.values():
            if not recording.title:
                missing_titles.append(f"Recording {recording.id}")
            if not recording.description and recording.transcription_status == TranscriptionStatus.completed:
                missing_descriptions.append(f"Recording {recording.id}")
            if not recording.recorded_timestamp:
                missing_timestamps.append(f"Recording {recording.id}")
        
        if missing_titles:
            self.add_issue(ConsistencyIssue(
                category="data_migration",
                severity="warning",
                description="Recordings missing titles (should default to filename)",
                affected_items=missing_titles,
                fix_available=True,
                fix_action="Set title to original_filename"
            ))
        
        if missing_descriptions:
            self.add_issue(ConsistencyIssue(
                category="data_migration",
                severity="info",
                description="Completed recordings missing AI descriptions",
                affected_items=missing_descriptions,
                fix_available=True,
                fix_action="Queue for AI description generation"
            ))
        
        # Check for legacy speaker formats in transcriptions
        legacy_speaker_formats = []
        for transcription in self.transcriptions_cache.values():
            if transcription.speaker_mapping:
                for speaker_id, mapping in transcription.speaker_mapping.items():
                    if isinstance(mapping, str):  # Legacy format
                        legacy_speaker_formats.append(
                            f"Transcription {transcription.id} has legacy speaker mapping"
                        )
                        break
        
        if legacy_speaker_formats:
            self.add_issue(ConsistencyIssue(
                category="data_migration",
                severity="info",
                description="Transcriptions using legacy speaker mapping format",
                affected_items=legacy_speaker_formats,
                fix_available=True,
                fix_action="Migrate to new speaker mapping format"
            ))
    
    def check_orphaned_data(self):
        """Check for orphaned data that should be cleaned up"""
        self.logger.info("Checking for orphaned data...")
        
        # Find participants not referenced by any recordings
        referenced_participants = set()
        for recording in self.recordings_cache.values():
            if recording.participants and isinstance(recording.participants, list):
                for participant in recording.participants:
                    if hasattr(participant, 'participantId') and participant.participantId:
                        referenced_participants.add(participant.participantId)
        
        orphaned_participants = []
        for participant in self.participants_cache.values():
            if participant.id not in referenced_participants:
                orphaned_participants.append(
                    f"Participant {participant.id} ({participant.displayName}) not referenced by any recordings"
                )
        
        if orphaned_participants:
            self.add_issue(ConsistencyIssue(
                category="orphaned_data",
                severity="info",
                description="Participants not referenced by any recordings",
                affected_items=orphaned_participants[:20],  # Limit output
                fix_available=True,
                fix_action="Archive or delete unused participants"
            ))
        
        # Check for old sync progress records (should have TTL)
        # This would require loading sync progress data
        # Skipping for now as it requires additional container access
    
    def check_data_quality(self):
        """Check overall data quality"""
        self.logger.info("Checking data quality...")
        
        # Validate email formats
        invalid_emails = []
        email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        for user in self.users_cache.values():
            if user.email and not email_regex.match(user.email):
                invalid_emails.append(f"User {user.id}: {user.email}")
        
        for participant in self.participants_cache.values():
            if participant.email and not email_regex.match(participant.email):
                invalid_emails.append(f"Participant {participant.id}: {participant.email}")
        
        if invalid_emails:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="warning",
                description="Invalid email formats",
                affected_items=invalid_emails
            ))
        
        # Check for duplicate participants
        user_participants = defaultdict(list)
        for participant in self.participants_cache.values():
            key = (participant.userId, participant.displayName.lower())
            user_participants[key].append(participant.id)
        
        duplicate_participants = []
        for (user_id, name), ids in user_participants.items():
            if len(ids) > 1:
                duplicate_participants.append(
                    f"User {user_id} has {len(ids)} participants named '{name}'"
                )
        
        if duplicate_participants:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="warning",
                description="Potential duplicate participants",
                affected_items=duplicate_participants,
                fix_available=True,
                fix_action="Merge duplicate participants"
            ))
        
        # Check for failed recordings without retry attempts
        failed_no_retry = []
        for recording in self.recordings_cache.values():
            if (recording.transcription_status == TranscriptionStatus.failed and 
                (not hasattr(recording, 'transcoding_retry_count') or recording.transcoding_retry_count == 0)):
                failed_no_retry.append(
                    f"Recording {recording.id} failed but has no retry attempts"
                )
        
        if failed_no_retry:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="info",
                description="Failed recordings without retry attempts",
                affected_items=failed_no_retry,
                fix_available=True,
                fix_action="Queue for retry"
            ))
        
        # Check for empty transcriptions
        empty_transcriptions = []
        for transcription in self.transcriptions_cache.values():
            if not transcription.text and not transcription.diarized_transcript:
                empty_transcriptions.append(f"Transcription {transcription.id}")
        
        if empty_transcriptions:
            self.add_issue(ConsistencyIssue(
                category="data_quality",
                severity="warning",
                description="Transcriptions with no content",
                affected_items=empty_transcriptions
            ))
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report of all issues found"""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_users": len(self.users_cache),
                "total_recordings": len(self.recordings_cache),
                "total_transcriptions": len(self.transcriptions_cache),
                "total_participants": len(self.participants_cache),
                "total_analysis_types": len(self.analysis_types_cache),
                "total_issues": len(self.issues),
                "critical_issues": sum(1 for i in self.issues if i.severity == "critical"),
                "warning_issues": sum(1 for i in self.issues if i.severity == "warning"),
                "info_issues": sum(1 for i in self.issues if i.severity == "info"),
                "fixable_issues": sum(1 for i in self.issues if i.fix_available)
            },
            "issues_by_category": defaultdict(list),
            "all_issues": []
        }
        
        # Group issues by category
        for issue in self.issues:
            issue_dict = {
                "severity": issue.severity,
                "description": issue.description,
                "affected_count": len(issue.affected_items),
                "affected_items": issue.affected_items[:10],  # Limit to first 10
                "fix_available": issue.fix_available,
                "fix_action": issue.fix_action
            }
            report["issues_by_category"][issue.category].append(issue_dict)
            report["all_issues"].append({
                "category": issue.category,
                **issue_dict
            })
        
        return report
    
    def run_all_checks(self):
        """Run all consistency checks"""
        self.logger.info("Starting comprehensive database consistency check...")
        
        self.check_referential_integrity()
        self.check_one_to_one_relationships()
        self.check_data_consistency()
        self.check_business_rules()
        self.check_data_migration_health()
        self.check_orphaned_data()
        self.check_data_quality()
        
        self.logger.info(f"Consistency check complete. Found {len(self.issues)} issues.")
    
    def apply_fixes(self):
        """Apply available fixes (if in fix mode) with user confirmation"""
        if not self.fix_mode:
            self.logger.warning("Fix mode not enabled. Run with --fix to apply fixes.")
            return
        
        print("\n" + "="*60)
        print("FIX MODE - Database Modifications")
        print("="*60)
        
        # Group issues by fix type
        fix_groups = {
            "recordings_missing_transcriptions": [],
            "orphaned_participants": [],
            "duplicate_participants": [],
            "empty_transcriptions": [],
            "legacy_participant_formats": [],
            "invalid_participant_objects": []
        }
        
        for issue in self.issues:
            if not issue.fix_available:
                continue
                
            if "completed without transcriptions" in issue.description:
                fix_groups["recordings_missing_transcriptions"].append(issue)
            elif "not referenced by any recordings" in issue.description:
                fix_groups["orphaned_participants"].append(issue)
            elif "duplicate participants" in issue.description:
                fix_groups["duplicate_participants"].append(issue)
            elif "Transcriptions with no content" in issue.description:
                fix_groups["empty_transcriptions"].append(issue)
            elif "legacy participant format" in issue.description:
                fix_groups["legacy_participant_formats"].append(issue)
            elif "invalid participant object structure" in issue.description:
                fix_groups["invalid_participant_objects"].append(issue)
        
        # Fix 1: Recordings marked as completed without transcriptions
        if fix_groups["recordings_missing_transcriptions"]:
            self._fix_recordings_missing_transcriptions(fix_groups["recordings_missing_transcriptions"])
        
        # Fix 2: Orphaned participants
        if fix_groups["orphaned_participants"]:
            self._fix_orphaned_participants(fix_groups["orphaned_participants"])
        
        # Fix 3: Duplicate participants
        if fix_groups["duplicate_participants"]:
            self._fix_duplicate_participants(fix_groups["duplicate_participants"])
        
        # Fix 4: Empty transcriptions
        if fix_groups["empty_transcriptions"]:
            self._fix_empty_transcriptions(fix_groups["empty_transcriptions"])
        
        # Fix 5: Legacy participant formats
        if fix_groups["legacy_participant_formats"]:
            self._fix_legacy_participant_formats(fix_groups["legacy_participant_formats"])
        
        # Fix 6: Invalid participant objects
        if fix_groups["invalid_participant_objects"]:
            self._fix_invalid_participant_objects(fix_groups["invalid_participant_objects"])
    
    def _confirm_action(self, action_description: str, affected_count: int = None) -> bool:
        """Ask user for confirmation before applying fixes"""
        print(f"\n{action_description}")
        if affected_count is not None:
            print(f"This will affect {affected_count} items.")
        response = input("Do you want to proceed? (yes/no/all/skip): ").strip().lower()
        if response in ['all', 'a']:
            return 'all'
        elif response in ['skip', 's']:
            return 'skip'
        return response in ['yes', 'y']
    
    def _fix_recordings_missing_transcriptions(self, issues: List[ConsistencyIssue]):
        """Fix recordings marked as completed but missing transcriptions"""
        all_recording_ids = []
        for issue in issues:
            for item in issue.affected_items:
                # Extract recording ID from the message
                recording_id = item.split()[1]
                all_recording_ids.append(recording_id)
        
        print(f"\n1. RECORDINGS WITH MISSING TRANSCRIPTIONS")
        print(f"   Found {len(all_recording_ids)} recordings marked as 'completed' but have no transcriptions.")
        print("   These recordings will have their status changed to 'failed' so they can be retried.")
        print("\n   Options: yes (y), no (n), all (a) - fix all remaining, skip (s) - skip this category\n")
        
        fixed_count = 0
        apply_to_all = False
        
        for idx, recording_id in enumerate(all_recording_ids, 1):
            recording = self.recordings_cache.get(recording_id)
            if not recording:
                continue
                
            user = self.users_cache.get(recording.user_id)
            user_name = user.name if user else "Unknown User"
            
            print(f"\n   [{idx}/{len(all_recording_ids)}] Recording to fix:")
            print(f"   • Recording ID: {recording_id}")
            print(f"     Title: {recording.title or recording.original_filename}")
            print(f"     User: {user_name} ({recording.user_id})")
            print(f"     Duration: {recording.duration}s" if recording.duration else "     Duration: Unknown")
            print(f"     Recorded: {recording.recorded_timestamp[:19] if recording.recorded_timestamp else 'Unknown'}")
            print(f"     Source: {recording.source}")
            print(f"     Current Status: {recording.transcription_status} → will change to: failed")
            
            if not apply_to_all:
                response = self._confirm_action("Change this recording's status to 'failed'?")
                if response == 'skip':
                    print("   ✗ Skipping remaining recordings in this category")
                    break
                elif response == 'all':
                    apply_to_all = True
                elif not response:
                    print("   ✗ Skipped this recording")
                    continue
            
            # Apply the fix
            recording.transcription_status = TranscriptionStatus.failed
            updated = self.recording_handler.update_recording(recording)
            if updated:
                fixed_count += 1
                print("   ✓ Updated successfully")
                self.logger.info(f"Updated recording {recording_id} status to 'failed'")
            else:
                print("   ✗ Failed to update")
                self.logger.error(f"Failed to update recording {recording_id}")
        
        print(f"\n   Summary: Updated {fixed_count}/{len(all_recording_ids)} recordings")
    
    def _fix_orphaned_participants(self, issues: List[ConsistencyIssue]):
        """Delete participants not referenced by any recordings"""
        all_participants = []
        for issue in issues:
            for item in issue.affected_items:
                # Extract participant ID and name from the message
                parts = item.split()
                participant_id = parts[1]
                name = ' '.join(parts[2:]).strip('()')
                if "not referenced" in item:
                    name = name.rsplit(' not', 1)[0]
                all_participants.append((participant_id, name))
        
        print(f"\n2. ORPHANED PARTICIPANTS")
        print(f"   Found {len(all_participants)} participants not referenced by any recordings.")
        print("   These participants will be permanently deleted.")
        print("\n   Options: yes (y), no (n), all (a) - delete all remaining, skip (s) - skip this category\n")
        
        deleted_count = 0
        apply_to_all = False
        
        for idx, (participant_id, _) in enumerate(all_participants, 1):
            participant = self.participants_cache.get(participant_id)
            if not participant:
                continue
                
            user = self.users_cache.get(participant.userId)
            user_name = user.name if user else "Unknown User"
            
            print(f"\n   [{idx}/{len(all_participants)}] Participant to delete:")
            print(f"   • Participant: {participant.displayName}")
            print(f"     ID: {participant_id}")
            print(f"     User: {user_name} ({participant.userId})")
            print(f"     Email: {participant.email or 'Not provided'}")
            print(f"     Role: {participant.role or 'Not specified'}")
            print(f"     Organization: {participant.organization or 'Not specified'}")
            print(f"     Relationship: {participant.relationshipToUser or 'Not specified'}")
            print(f"     Created: {participant.createdAt[:19] if participant.createdAt else 'Unknown'}")
            print(f"     Last Seen: {participant.lastSeen[:19] if participant.lastSeen else 'Never'}")
            if participant.aliases:
                print(f"     Aliases: {', '.join(participant.aliases)}")
            
            if not apply_to_all:
                response = self._confirm_action("Delete this participant?")
                if response == 'skip':
                    print("   ✗ Skipping remaining participants in this category")
                    break
                elif response == 'all':
                    apply_to_all = True
                elif not response:
                    print("   ✗ Skipped this participant")
                    continue
            
            # Apply the fix
            try:
                self.participant_handler.delete_participant(participant.userId, participant_id)
                deleted_count += 1
                print("   ✓ Deleted successfully")
                self.logger.info(f"Deleted participant {participant_id} ({participant.displayName})")
            except Exception as e:
                print(f"   ✗ Failed to delete: {e}")
                self.logger.error(f"Failed to delete participant {participant_id}: {e}")
        
        print(f"\n   Summary: Deleted {deleted_count}/{len(all_participants)} participants")
    
    def _fix_duplicate_participants(self, issues: List[ConsistencyIssue]):
        """Merge duplicate participants"""
        duplicates_by_user = defaultdict(lambda: defaultdict(list))
        
        for issue in issues:
            for item in issue.affected_items:
                # Parse: "User user-xxx has N participants named 'name'"
                parts = item.split()
                user_id = parts[1]
                name = item.split("'")[1]
                
                # Find all participants with this name for this user
                for participant in self.participants_cache.values():
                    if participant.userId == user_id and participant.displayName.lower() == name:
                        duplicates_by_user[user_id][name].append(participant)
        
        print(f"\n3. DUPLICATE PARTICIPANTS")
        total_sets = sum(len(names) for names in duplicates_by_user.values())
        print(f"   Found {total_sets} sets of duplicate participants.")
        
        for user_id, name_groups in duplicates_by_user.items():
            for name, participants in name_groups.items():
                if len(participants) < 2:
                    continue
                    
                user = self.users_cache.get(user_id)
                user_name = user.name if user else "Unknown User"
                print(f"\n   User: {user_name} ({user_id})")
                print(f"   Has {len(participants)} participants named '{name}':")
                
                # Gather detailed info about each duplicate
                participant_info = []
                for p in participants:
                    # Count how many recordings reference this participant
                    ref_count = 0
                    referenced_recordings = []
                    for recording in self.recordings_cache.values():
                        if recording.participants and isinstance(recording.participants, list):
                            for rp in recording.participants:
                                if hasattr(rp, 'participantId') and rp.participantId == p.id:
                                    ref_count += 1
                                    referenced_recordings.append(recording)
                    
                    participant_info.append({
                        'participant': p,
                        'ref_count': ref_count,
                        'recordings': referenced_recordings
                    })
                
                # Sort by reference count and last seen
                participant_info.sort(key=lambda x: (x['ref_count'], x['participant'].lastSeen or x['participant'].createdAt), reverse=True)
                
                # Display detailed info
                for info in participant_info:
                    p = info['participant']
                    print(f"\n     • Participant ID: {p.id}")
                    print(f"       Display Name: {p.displayName}")
                    print(f"       Email: {p.email or 'Not provided'}")
                    print(f"       Role: {p.role or 'Not specified'}")
                    print(f"       Created: {p.createdAt[:19] if p.createdAt else 'Unknown'}")
                    print(f"       Last Seen: {p.lastSeen[:19] if p.lastSeen else 'Never'}")
                    print(f"       Recording References: {info['ref_count']}")
                    if info['recordings']:
                        print(f"       Referenced in: {', '.join([r.title or r.original_filename for r in info['recordings'][:3]])}" +
                              (f" and {len(info['recordings'])-3} more" if len(info['recordings']) > 3 else ""))
                
                # The primary is the first one (most references/most recent)
                primary = participant_info[0]['participant']
                others = [info['participant'] for info in participant_info[1:]]
                
                print(f"\n   → Will keep participant {primary.id} (most references/recent)")
                print(f"   → Will merge {len(others)} duplicate(s) into it")
                
                response = self._confirm_action(f"Merge these {len(participants)} duplicates?")
                if response == 'skip':
                    print("   ✗ Skipping remaining duplicate sets")
                    break
                elif response in [True, 'all']:
                    # Update all recordings to use the primary participant
                    updated_recordings = 0
                    recordings_to_update = []
                    
                    # Find all recordings that need updating
                    for recording in self.recordings_cache.values():
                        if recording.participants and isinstance(recording.participants, list):
                            needs_update = False
                            for rp in recording.participants:
                                if hasattr(rp, 'participantId') and rp.participantId in [o.id for o in others]:
                                    needs_update = True
                                    recordings_to_update.append(recording)
                                    break
                    
                    print(f"\n   Will update {len(recordings_to_update)} recordings to use primary participant")
                    
                    # Update recordings
                    for recording in recordings_to_update:
                        for i, rp in enumerate(recording.participants):
                            if hasattr(rp, 'participantId') and rp.participantId in [o.id for o in others]:
                                recording.participants[i].participantId = primary.id
                        
                        if self.recording_handler.update_recording(recording):
                            updated_recordings += 1
                    
                    # Delete the duplicate participants
                    deleted = 0
                    for other in others:
                        try:
                            self.participant_handler.delete_participant(other.userId, other.id)
                            deleted += 1
                            self.logger.info(f"Deleted duplicate participant {other.id}")
                        except Exception as e:
                            self.logger.error(f"Failed to delete duplicate {other.id}: {e}")
                    
                    print(f"   ✓ Updated {updated_recordings} recordings, deleted {deleted} duplicate participants")
                else:
                    print("   ✗ Skipped this duplicate set")
    
    def _fix_empty_transcriptions(self, issues: List[ConsistencyIssue]):
        """Delete empty transcriptions and reset recording status"""
        transcription_ids = []
        for issue in issues:
            for item in issue.affected_items:
                # Extract transcription ID
                trans_id = item.split()[1]
                transcription_ids.append(trans_id)
        
        print(f"\n4. EMPTY TRANSCRIPTIONS")
        print(f"   Found {len(transcription_ids)} transcriptions with no content.")
        print("   These transcriptions will be deleted and their recordings reset to 'not_started'.")
        print("\n   Options: yes (y), no (n), all (a) - fix all remaining, skip (s) - skip this category\n")
        
        fixed_count = 0
        apply_to_all = False
        
        for idx, trans_id in enumerate(transcription_ids, 1):
            transcription = self.transcriptions_cache.get(trans_id)
            if not transcription:
                continue
                
            recording = self.recordings_cache.get(transcription.recording_id)
            if not recording:
                continue
                
            user = self.users_cache.get(recording.user_id)
            user_name = user.name if user else "Unknown User"
            
            print(f"\n   [{idx}/{len(transcription_ids)}] Transcription to fix:")
            print(f"   • Transcription ID: {trans_id}")
            print(f"     Recording ID: {recording.id}")
            print(f"     Recording Title: {recording.title or recording.original_filename}")
            print(f"     User: {user_name} ({recording.user_id})")
            print(f"     Duration: {recording.duration}s" if recording.duration else "     Duration: Unknown")
            print(f"     Source: {recording.source}")
            print(f"     Recorded: {recording.recorded_timestamp[:19] if recording.recorded_timestamp else 'Unknown'}")
            print(f"     Current Status: {recording.transcription_status} → will change to: not_started")
            print(f"     Has Text: {'No' if not transcription.text else f'Yes ({len(transcription.text)} chars)'}")
            print(f"     Has Diarized: {'No' if not transcription.diarized_transcript else f'Yes ({len(transcription.diarized_transcript)} chars)'}")
            print(f"     Action: Delete transcription and reset recording status")
            
            if not apply_to_all:
                response = self._confirm_action("Fix this empty transcription?")
                if response == 'skip':
                    print("   ✗ Skipping remaining transcriptions in this category")
                    break
                elif response == 'all':
                    apply_to_all = True
                elif not response:
                    print("   ✗ Skipped this transcription")
                    continue
            
            # Apply the fix
            try:
                # Delete the transcription
                self.transcription_handler.delete_transcription(trans_id)
                
                # Reset recording status
                recording.transcription_status = TranscriptionStatus.not_started
                if self.recording_handler.update_recording(recording):
                    fixed_count += 1
                    print("   ✓ Fixed successfully")
                    self.logger.info(f"Deleted transcription {trans_id} and reset recording {recording.id}")
                else:
                    print("   ✗ Failed to update recording status")
                    self.logger.error(f"Failed to update recording {recording.id}")
            except Exception as e:
                print(f"   ✗ Failed to delete transcription: {e}")
                self.logger.error(f"Failed to delete transcription {trans_id}: {e}")
        
        print(f"\n   Summary: Fixed {fixed_count}/{len(transcription_ids)} empty transcriptions")
    
    def _fix_legacy_participant_formats(self, issues: List[ConsistencyIssue]):
        """Convert legacy string[] participant formats to new RecordingParticipant format"""
        all_recording_ids = []
        for issue in issues:
            for item in issue.affected_items:
                # Extract recording ID from the message
                recording_id = item.split()[1]
                all_recording_ids.append(recording_id)
        
        print(f"\n5. LEGACY PARTICIPANT FORMATS")
        print(f"   Found {len(all_recording_ids)} recordings using legacy string[] participant format.")
        print("   These will be converted to the new RecordingParticipant object format.")
        print("\n   Options: yes (y), no (n), all (a) - fix all remaining, skip (s) - skip this category\n")
        
        fixed_count = 0
        apply_to_all = False
        
        for idx, recording_id in enumerate(all_recording_ids, 1):
            recording = self.recordings_cache.get(recording_id)
            if not recording or not recording.participants:
                continue
            
            user = self.users_cache.get(recording.user_id)
            user_name = user.name if user else "Unknown User"
            
            # Show current participants
            print(f"\n   [{idx}/{len(all_recording_ids)}] Recording to fix:")
            print(f"   • Recording ID: {recording_id}")
            print(f"     Title: {recording.title or recording.original_filename}")
            print(f"     User: {user_name} ({recording.user_id})")
            print(f"     Current participants (strings):")
            
            string_participants = [p for p in recording.participants if isinstance(p, str)]
            for participant_name in string_participants:
                print(f"       - {participant_name}")
            
            print(f"\n     Will convert to RecordingParticipant objects with:")
            print(f"       - name: <participant name>")
            print(f"       - participantId: null (unlinked)")
            print(f"       - startTime: 0")
            print(f"       - endTime: null")
            
            if not apply_to_all:
                response = self._confirm_action("Convert this recording's participants to new format?")
                if response == 'skip':
                    print("   ✗ Skipping remaining recordings in this category")
                    break
                elif response == 'all':
                    apply_to_all = True
                elif not response:
                    print("   ✗ Skipped this recording")
                    continue
            
            # Apply the fix - convert strings to RecordingParticipant objects
            try:
                new_participants = []
                for p in recording.participants:
                    if isinstance(p, str):
                        # Create a new RecordingParticipant object
                        new_participant = type('RecordingParticipant', (), {
                            'name': p,
                            'participantId': None,
                            'startTime': 0,
                            'endTime': None
                        })()
                        new_participants.append(new_participant)
                    else:
                        # Keep existing objects
                        new_participants.append(p)
                
                recording.participants = new_participants
                if self.recording_handler.update_recording(recording):
                    fixed_count += 1
                    print("   ✓ Converted successfully")
                    self.logger.info(f"Converted recording {recording_id} participants to new format")
                else:
                    print("   ✗ Failed to update recording")
                    self.logger.error(f"Failed to update recording {recording_id}")
            except Exception as e:
                print(f"   ✗ Failed to convert: {e}")
                self.logger.error(f"Failed to convert participants for recording {recording_id}: {e}")
        
        print(f"\n   Summary: Converted {fixed_count}/{len(all_recording_ids)} recordings to new participant format")
    
    def _fix_invalid_participant_objects(self, issues: List[ConsistencyIssue]):
        """Fix invalid participant objects by regenerating from transcription data"""
        # Parse affected recordings from issue messages
        affected_recordings = {}
        for issue in issues:
            for item in issue.affected_items:
                # Extract recording ID from messages like "Recording {id} participant[{idx}] missing required 'name' field"
                parts = item.split()
                if len(parts) >= 2:
                    recording_id = parts[1]
                    if recording_id not in affected_recordings:
                        affected_recordings[recording_id] = []
                    affected_recordings[recording_id].append(item)
        
        print(f"\n6. INVALID PARTICIPANT OBJECTS")
        print(f"   Found {len(affected_recordings)} recordings with invalid participant structures.")
        print("   These will be regenerated from transcription speaker data.")
        print("\n   Options: yes (y), no (n), all (a) - fix all remaining, skip (s) - skip this category\n")
        
        fixed_count = 0
        skipped_no_transcription = 0
        apply_to_all = False
        
        for idx, (recording_id, issues_list) in enumerate(affected_recordings.items(), 1):
            recording = self.recordings_cache.get(recording_id)
            if not recording:
                continue
            
            # Get the transcription for this recording
            transcription = None
            for trans in self.transcriptions_cache.values():
                if trans.recording_id == recording_id:
                    transcription = trans
                    break
            
            if not transcription:
                skipped_no_transcription += 1
                print(f"\n   [{idx}/{len(affected_recordings)}] Skipping recording {recording_id} - no transcription found")
                continue
            
            user = self.users_cache.get(recording.user_id)
            user_name = user.name if user else "Unknown User"
            
            print(f"\n   [{idx}/{len(affected_recordings)}] Recording to fix:")
            print(f"   • Recording ID: {recording_id}")
            print(f"     Title: {recording.title or recording.original_filename}")
            print(f"     User: {user_name} ({recording.user_id})")
            
            # Show current invalid participants
            print(f"\n     Current issues:")
            for issue_msg in issues_list[:3]:  # Show first 3 issues
                print(f"       - {issue_msg.split(recording_id)[1].strip()}")
            if len(issues_list) > 3:
                print(f"       ... and {len(issues_list) - 3} more issues")
            
            # Analyze transcription to determine participants
            print(f"\n     Transcription analysis:")
            
            # Extract unique speakers from diarized transcript
            speakers_found = set()
            if transcription.diarized_transcript:
                # Parse diarized transcript for speaker labels
                import re
                speaker_pattern = r'\[([^\]]+)\]:'
                speakers_found = set(re.findall(speaker_pattern, transcription.diarized_transcript))
                print(f"       Found {len(speakers_found)} speakers in diarized transcript: {', '.join(sorted(speakers_found))}")
            elif transcription.transcript_json:
                # Try to extract from transcript_json if available
                try:
                    import json
                    transcript_data = json.loads(transcription.transcript_json)
                    # This structure varies by provider, but we'll try common patterns
                    if isinstance(transcript_data, dict):
                        if 'speakers' in transcript_data:
                            speakers_found = set(transcript_data['speakers'])
                        elif 'utterances' in transcript_data:
                            for utterance in transcript_data['utterances']:
                                if 'speaker' in utterance:
                                    speakers_found.add(utterance['speaker'])
                    if speakers_found:
                        print(f"       Found {len(speakers_found)} speakers in transcript JSON: {', '.join(sorted(speakers_found))}")
                except:
                    pass
            
            # Check speaker_mapping for better names
            mapped_participants = []
            if transcription.speaker_mapping and speakers_found:
                print(f"\n     Speaker mappings:")
                for speaker_label in sorted(speakers_found):
                    if speaker_label in transcription.speaker_mapping:
                        mapping = transcription.speaker_mapping[speaker_label]
                        if isinstance(mapping, dict) and 'name' in mapping:
                            participant_name = mapping['name']
                            participant_id = mapping.get('participantId')
                            print(f"       {speaker_label} → {participant_name}" + 
                                  (f" (linked to participant {participant_id})" if participant_id else " (unlinked)"))
                            mapped_participants.append({
                                'name': participant_name,
                                'participantId': participant_id,
                                'speaker_label': speaker_label
                            })
                        elif isinstance(mapping, str):
                            # Legacy format
                            print(f"       {speaker_label} → {mapping} (legacy format)")
                            mapped_participants.append({
                                'name': mapping,
                                'participantId': None,
                                'speaker_label': speaker_label
                            })
            
            # If no mapped participants but we have speakers, create basic entries
            if not mapped_participants and speakers_found:
                print(f"\n     No speaker mappings found, will create basic entries for {len(speakers_found)} speakers")
                for speaker_label in sorted(speakers_found):
                    mapped_participants.append({
                        'name': speaker_label,
                        'participantId': None,
                        'speaker_label': speaker_label
                    })
            
            if not mapped_participants:
                print(f"\n     ⚠ No speaker data found in transcription - cannot regenerate participants")
                continue
            
            print(f"\n     Will regenerate with {len(mapped_participants)} participants")
            
            if not apply_to_all:
                response = self._confirm_action("Regenerate participant structure from transcription?")
                if response == 'skip':
                    print("   ✗ Skipping remaining recordings in this category")
                    break
                elif response == 'all':
                    apply_to_all = True
                elif not response:
                    print("   ✗ Skipped this recording")
                    continue
            
            # Apply the fix - regenerate participants from transcription
            try:
                new_participants = []
                for mp in mapped_participants:
                    # Create a new RecordingParticipant object
                    new_participant = type('RecordingParticipant', (), {
                        'name': mp['name'],
                        'participantId': mp['participantId'],
                        'startTime': 0,
                        'endTime': None
                    })()
                    new_participants.append(new_participant)
                
                recording.participants = new_participants
                if self.recording_handler.update_recording(recording):
                    fixed_count += 1
                    print("   ✓ Regenerated successfully")
                    self.logger.info(f"Regenerated participants for recording {recording_id} from transcription")
                else:
                    print("   ✗ Failed to update recording")
                    self.logger.error(f"Failed to update recording {recording_id}")
            except Exception as e:
                print(f"   ✗ Failed to regenerate: {e}")
                self.logger.error(f"Failed to regenerate participants for recording {recording_id}: {e}")
        
        print(f"\n   Summary: Fixed {fixed_count}/{len(affected_recordings)} recordings")
        if skipped_no_transcription > 0:
            print(f"   Skipped {skipped_no_transcription} recordings without transcriptions")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Database Consistency Checker for QuickScribe",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix issues where possible (use with caution)"
    )
    
    parser.add_argument(
        "--check",
        choices=["integrity", "quality", "migration", "orphaned", "business", "all"],
        default="all",
        help="Run specific check type"
    )
    
    parser.add_argument(
        "--user",
        help="Check only a specific user's data"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each issue"
    )
    
    parser.add_argument(
        "--report",
        help="Save detailed report to file"
    )
    
    args = parser.parse_args()
    
    # Initialize checker
    checker = DatabaseConsistencyChecker(
        fix_mode=args.fix,
        verbose=args.verbose
    )
    
    # Load data
    checker.load_all_data(user_id=args.user)
    
    # Run checks based on selection
    if args.check == "all":
        checker.run_all_checks()
    elif args.check == "integrity":
        checker.check_referential_integrity()
        checker.check_one_to_one_relationships()
    elif args.check == "quality":
        checker.check_data_quality()
        checker.check_data_consistency()
    elif args.check == "migration":
        checker.check_data_migration_health()
    elif args.check == "orphaned":
        checker.check_orphaned_data()
    elif args.check == "business":
        checker.check_business_rules()
    
    # Generate report
    report = checker.generate_report()
    
    # Print summary
    print("\n" + "="*60)
    print("DATABASE CONSISTENCY CHECK SUMMARY")
    print("="*60)
    print(f"Total Issues Found: {report['summary']['total_issues']}")
    print(f"  Critical: {report['summary']['critical_issues']}")
    print(f"  Warning:  {report['summary']['warning_issues']}")
    print(f"  Info:     {report['summary']['info_issues']}")
    print(f"  Fixable:  {report['summary']['fixable_issues']}")
    print("\nDatabase Statistics:")
    print(f"  Users:         {report['summary']['total_users']}")
    print(f"  Recordings:    {report['summary']['total_recordings']}")
    print(f"  Transcriptions: {report['summary']['total_transcriptions']}")
    print(f"  Participants:  {report['summary']['total_participants']}")
    print("="*60)
    
    # Show issues by category
    if report['issues_by_category']:
        print("\nIssues by Category:")
        for category, issues in report['issues_by_category'].items():
            print(f"\n{category.upper().replace('_', ' ')}:")
            for issue in issues:
                print(f"  [{issue['severity'].upper()}] {issue['description']}")
                print(f"    Affects: {issue['affected_count']} items")
                if issue['fix_available']:
                    print(f"    Fix available: {issue['fix_action']}")
    
    # Save detailed report if requested
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nDetailed report saved to: {args.report}")
    
    # Apply fixes if requested
    if args.fix:
        checker.apply_fixes()
    
    # Exit with appropriate code
    if report['summary']['critical_issues'] > 0:
        sys.exit(2)
    elif report['summary']['warning_issues'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()