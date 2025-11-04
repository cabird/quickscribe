"""Admin API routes for managing the QuickScribe database."""

from flask import Blueprint, jsonify, request, abort
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
import logging

from user_util import get_current_user, require_auth
from shared_quickscribe_py.cosmos import (
    get_user_handler,
    get_recording_handler,
    get_transcription_handler,
    get_analysis_type_handler,
    get_sync_progress_handler
)
from shared_quickscribe_py.cosmos import User, Recording, Transcription, Tag, AnalysisType, SyncProgress

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

# For now, anyone can be an admin - we'll add proper checks later
def require_admin(f):
    """Decorator to require admin access (currently allows all authenticated users)."""
    return require_auth(f)


# ============================================================================
# Overview Endpoints
# ============================================================================

@admin_bp.route('/overview', methods=['GET'])
@require_admin
def get_overview():
    """Get entity counts and summary for the admin dashboard."""
    try:
        user_handler = get_user_handler()
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()
        analysis_type_handler = get_analysis_type_handler()
        
        # Get counts for each entity type
        users = user_handler.get_all_users()
        recordings = recording_handler.get_all_recordings()
        transcriptions = transcription_handler.get_all_transcriptions()
        analysis_types = analysis_type_handler.get_all_analysis_types()
        
        # Calculate additional statistics
        recordings_with_transcriptions = sum(1 for r in recordings if r.transcription_id)
        recordings_in_progress = sum(1 for r in recordings if r.transcription_status == 'in_progress')
        recordings_failed = sum(1 for r in recordings if r.transcription_status == 'failed')
        
        # Count tags across all users
        all_tags = []
        for user in users:
            if hasattr(user, 'tags') and user.tags:
                all_tags.extend(user.tags)
        
        return jsonify({
            'status': 'success',
            'data': {
                'counts': {
                    'users': len(users),
                    'recordings': len(recordings),
                    'transcriptions': len(transcriptions),
                    'tags': len(all_tags),
                    'analysisTypes': len(analysis_types)
                },
                'statistics': {
                    'recordingsWithTranscriptions': recordings_with_transcriptions,
                    'recordingsInProgress': recordings_in_progress,
                    'recordingsFailed': recordings_failed,
                    'averageRecordingsPerUser': round(len(recordings) / max(len(users), 1), 2)
                },
                'recentActivity': {
                    'lastRecordingDate': max((r.upload_timestamp for r in recordings), default=None),
                    'activeUsers24h': sum(1 for u in users if hasattr(u, 'last_login') and u.last_login and
                                        (datetime.now(UTC) - datetime.fromisoformat(u.last_login.replace('Z', '+00:00'))).days < 1)
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting admin overview: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# List Endpoints
# ============================================================================

@admin_bp.route('/users', methods=['GET'])
@require_admin
def get_all_users():
    """Get all users with summary information."""
    try:
        user_handler = get_user_handler()
        recording_handler = get_recording_handler()
        
        users = user_handler.get_all_users()
        
        # Add recording counts for each user
        user_summaries = []
        for user in users:
            recordings = recording_handler.get_recordings_for_user(user.id)
            
            user_summary = {
                'id': user.id,
                'email': getattr(user, 'email', 'Unknown'),
                'name': getattr(user, 'name', getattr(user, 'email', 'Unknown')),
                'created_at': getattr(user, 'created_at', None),
                'last_login': getattr(user, 'last_login', None),
                'is_test_user': getattr(user, 'is_test_user', False),
                'recordingCount': len(recordings),
                'tagCount': len(user.tags) if hasattr(user, 'tags') and user.tags else 0,
                'hasPlaudSettings': bool(getattr(user, 'plaudSettings', None))
            }
            user_summaries.append(user_summary)
        
        return jsonify({
            'status': 'success',
            'data': user_summaries,
            'count': len(user_summaries)
        })
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/recordings', methods=['GET'])
@require_admin
def get_all_recordings():
    """Get all recordings with summary information."""
    try:
        recording_handler = get_recording_handler()
        user_handler = get_user_handler()
        
        recordings = recording_handler.get_all_recordings()
        
        # Create a user lookup for efficiency
        users = {u.id: u for u in user_handler.get_all_users()}
        
        recording_summaries = []
        for recording in recordings:
            user = users.get(recording.user_id)
            user_name = getattr(user, 'name', getattr(user, 'email', 'Unknown')) if user else 'Unknown User'
            
            recording_summary = {
                'id': recording.id,
                'title': recording.title or recording.original_filename,
                'original_filename': recording.original_filename,
                'user_id': recording.user_id,
                'user_name': user_name,
                'duration': recording.duration,
                'recorded_timestamp': recording.recorded_timestamp,
                'upload_timestamp': recording.upload_timestamp,
                'transcription_status': recording.transcription_status,
                'transcription_id': recording.transcription_id,
                'source': recording.source,
                'tagCount': len(recording.tagIds) if recording.tagIds else 0,
                'hasTranscription': bool(recording.transcription_id)
            }
            recording_summaries.append(recording_summary)
        
        return jsonify({
            'status': 'success',
            'data': recording_summaries,
            'count': len(recording_summaries)
        })
    except Exception as e:
        logger.error(f"Error getting all recordings: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/transcriptions', methods=['GET'])
@require_admin
def get_all_transcriptions():
    """Get all transcriptions with summary information."""
    try:
        transcription_handler = get_transcription_handler()
        recording_handler = get_recording_handler()
        
        transcriptions = transcription_handler.get_all_transcriptions()
        
        # Create a recording lookup for efficiency
        recordings = {r.id: r for r in recording_handler.get_all_recordings()}
        
        transcription_summaries = []
        for transcription in transcriptions:
            recording = recordings.get(transcription.recording_id)
            recording_title = recording.title or recording.original_filename if recording else 'Unknown Recording'
            
            # Count analysis results if present
            analysis_count = len(transcription.analysisResults) if hasattr(transcription, 'analysisResults') and transcription.analysisResults else 0
            
            # Get snippet of transcript text
            text_snippet = ''
            if transcription.diarized_transcript:
                text_snippet = transcription.diarized_transcript[:100] + '...' if len(transcription.diarized_transcript) > 100 else transcription.diarized_transcript
            elif transcription.text:
                text_snippet = transcription.text[:100] + '...' if len(transcription.text) > 100 else transcription.text
            
            transcription_summary = {
                'id': transcription.id,
                'recording_id': transcription.recording_id,
                'recording_title': recording_title,
                'user_id': transcription.user_id,
                'created_at': getattr(transcription, 'created_at', None),
                'text_snippet': text_snippet,
                'hasDiarization': bool(transcription.diarized_transcript),
                'hasSpeakerMapping': bool(getattr(transcription, 'speaker_mapping', None)),
                'analysisCount': analysis_count
            }
            transcription_summaries.append(transcription_summary)
        
        return jsonify({
            'status': 'success',
            'data': transcription_summaries,
            'count': len(transcription_summaries)
        })
    except Exception as e:
        logger.error(f"Error getting all transcriptions: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/tags', methods=['GET'])
@require_admin
def get_all_tags():
    """Get all tags across all users with usage counts."""
    try:
        user_handler = get_user_handler()
        recording_handler = get_recording_handler()
        
        users = user_handler.get_all_users()
        recordings = recording_handler.get_all_recordings()
        
        # Aggregate all tags with their usage
        tag_usage = {}  # tag_id -> {tag_info, usage_count, user_count}
        
        for user in users:
            if hasattr(user, 'tags') and user.tags:
                for tag in user.tags:
                    tag_id = tag.get('id', tag.get('name', 'unknown'))
                    if tag_id not in tag_usage:
                        tag_usage[tag_id] = {
                            'id': tag_id,
                            'name': tag.get('name', tag_id),
                            'color': tag.get('color', '#666666'),
                            'usage_count': 0,
                            'user_ids': set()
                        }
                    tag_usage[tag_id]['user_ids'].add(user.id)
        
        # Count tag usage in recordings
        for recording in recordings:
            if recording.tagIds:
                for tag_id in recording.tagIds:
                    if tag_id in tag_usage:
                        tag_usage[tag_id]['usage_count'] += 1
        
        # Convert to list format
        tag_summaries = []
        for tag_id, info in tag_usage.items():
            tag_summaries.append({
                'id': info['id'],
                'name': info['name'],
                'color': info['color'],
                'usage_count': info['usage_count'],
                'user_count': len(info['user_ids'])
            })
        
        return jsonify({
            'status': 'success',
            'data': tag_summaries,
            'count': len(tag_summaries)
        })
    except Exception as e:
        logger.error(f"Error getting all tags: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/analysis-types', methods=['GET'])
@require_admin
def get_all_analysis_types():
    """Get all analysis types with usage information."""
    try:
        analysis_type_handler = get_analysis_type_handler()
        transcription_handler = get_transcription_handler()
        
        analysis_types = analysis_type_handler.get_all_analysis_types()
        transcriptions = transcription_handler.get_all_transcriptions()
        
        # Count usage of each analysis type
        usage_counts = {}
        for transcription in transcriptions:
            if hasattr(transcription, 'analysisResults') and transcription.analysisResults:
                for result in transcription.analysisResults:
                    type_id = getattr(result, 'analysisTypeId', None)
                    if type_id:
                        usage_counts[type_id] = usage_counts.get(type_id, 0) + 1
        
        analysis_type_summaries = []
        for analysis_type in analysis_types:
            analysis_type_summary = {
                'id': analysis_type.id,
                'name': analysis_type.name,
                'title': analysis_type.title,
                'description': analysis_type.description,
                'icon': analysis_type.icon,
                'isBuiltIn': analysis_type.isBuiltIn,
                'isActive': analysis_type.isActive,
                'userId': analysis_type.userId,
                'usage_count': usage_counts.get(analysis_type.id, 0),
                'created_at': analysis_type.createdAt
            }
            analysis_type_summaries.append(analysis_type_summary)
        
        return jsonify({
            'status': 'success',
            'data': analysis_type_summaries,
            'count': len(analysis_type_summaries)
        })
    except Exception as e:
        logger.error(f"Error getting all analysis types: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Detail Endpoints with Relationships
# ============================================================================

@admin_bp.route('/users/<user_id>', methods=['GET'])
@require_admin
def get_user_detail(user_id: str):
    """Get detailed user information with related entities."""
    try:
        user_handler = get_user_handler()
        recording_handler = get_recording_handler()
        
        user = user_handler.get_user(user_id)
        if not user:
            return jsonify({'status': 'error', 'error': 'User not found'}), 404
        
        # Get related recordings
        recordings = recording_handler.get_recordings_for_user(user_id)
        recording_summaries = [{
            'id': r.id,
            'title': r.title or r.original_filename,
            'recorded_timestamp': r.recorded_timestamp,
            'transcription_status': r.transcription_status
        } for r in recordings]
        
        # Get user's tags
        tag_summaries = []
        if hasattr(user, 'tags') and user.tags:
            tag_summaries = [{
                'id': tag.get('id'),
                'name': tag.get('name'),
                'color': tag.get('color')
            } for tag in user.tags]
        
        user_detail = {
            'id': user.id,
            'email': getattr(user, 'email', 'Unknown'),
            'name': getattr(user, 'name', getattr(user, 'email', 'Unknown')),
            'created_at': getattr(user, 'created_at', None),
            'last_login': getattr(user, 'last_login', None),
            'is_test_user': getattr(user, 'is_test_user', False),
            'plaudSettings': user.plaudSettings.dict() if getattr(user, 'plaudSettings', None) else None,
            'recordings': {
                'count': len(recording_summaries),
                'items': recording_summaries
            },
            'tags': {
                'count': len(tag_summaries),
                'items': tag_summaries
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': user_detail
        })
    except Exception as e:
        logger.error(f"Error getting user detail: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/recordings/<recording_id>', methods=['GET'])
@require_admin
def get_recording_detail(recording_id: str):
    """Get detailed recording information with related entities."""
    try:
        recording_handler = get_recording_handler()
        user_handler = get_user_handler()
        transcription_handler = get_transcription_handler()
        
        recording = recording_handler.get_recording(recording_id)
        if not recording:
            return jsonify({'status': 'error', 'error': 'Recording not found'}), 404
        
        # Get user info
        user = user_handler.get_user(recording.user_id)
        user_name = getattr(user, 'name', getattr(user, 'email', 'Unknown')) if user else 'Unknown User'
        
        # Get transcription info if exists
        transcription_summary = None
        if recording.transcription_id:
            transcription = transcription_handler.get_transcription(recording.transcription_id)
            if transcription:
                transcription_summary = {
                    'id': transcription.id,
                    'created_at': getattr(transcription, 'created_at', None),
                    'hasDiarization': bool(transcription.diarized_transcript),
                    'analysisCount': len(transcription.analysisResults) if hasattr(transcription, 'analysisResults') and transcription.analysisResults else 0
                }
        
        # Get tag info
        tag_summaries = []
        if recording.tagIds and user and hasattr(user, 'tags') and user.tags:
            user_tags = {tag.get('id'): tag for tag in user.tags}
            tag_summaries = [{
                'id': tag_id,
                'name': user_tags.get(tag_id, {}).get('name', tag_id),
                'color': user_tags.get(tag_id, {}).get('color', '#666666')
            } for tag_id in recording.tagIds if tag_id in user_tags]
        
        recording_detail = {
            'id': recording.id,
            'title': recording.title,
            'description': recording.description,
            'original_filename': recording.original_filename,
            'unique_filename': recording.unique_filename,
            'duration': recording.duration,
            'recorded_timestamp': recording.recorded_timestamp,
            'upload_timestamp': recording.upload_timestamp,
            'transcription_status': recording.transcription_status,
            'transcoding_status': recording.transcoding_status,
            'source': recording.source,
            'plaudMetadata': recording.plaudMetadata.dict() if recording.plaudMetadata else None,
            'user': {
                'id': recording.user_id,
                'name': user_name
            },
            'transcription': transcription_summary,
            'tags': {
                'count': len(tag_summaries),
                'items': tag_summaries
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': recording_detail
        })
    except Exception as e:
        logger.error(f"Error getting recording detail: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/transcriptions/<transcription_id>', methods=['GET'])
@require_admin
def get_transcription_detail(transcription_id: str):
    """Get detailed transcription information with related entities."""
    try:
        transcription_handler = get_transcription_handler()
        recording_handler = get_recording_handler()
        user_handler = get_user_handler()
        
        transcription = transcription_handler.get_transcription(transcription_id)
        if not transcription:
            return jsonify({'status': 'error', 'error': 'Transcription not found'}), 404
        
        # Get recording info
        recording = recording_handler.get_recording(transcription.recording_id)
        recording_title = recording.title or recording.original_filename if recording else 'Unknown Recording'
        
        # Get user info
        user = user_handler.get_user(transcription.user_id)
        user_name = getattr(user, 'name', getattr(user, 'email', 'Unknown')) if user else 'Unknown User'
        
        # Get analysis results summaries
        analysis_summaries = []
        if hasattr(transcription, 'analysisResults') and transcription.analysisResults:
            analysis_summaries = [{
                'analysisType': result.analysisType,
                'analysisTypeId': getattr(result, 'analysisTypeId', None),
                'status': result.status,
                'createdAt': result.createdAt,
                'hasContent': bool(result.content)
            } for result in transcription.analysisResults]
        
        transcription_detail = {
            'id': transcription.id,
            'created_at': getattr(transcription, 'created_at', None),
            'text_length': len(transcription.text) if transcription.text else 0,
            'diarized_transcript_length': len(transcription.diarized_transcript) if transcription.diarized_transcript else 0,
            'hasDiarization': bool(transcription.diarized_transcript),
            'speaker_mapping': transcription.speaker_mapping if hasattr(transcription, 'speaker_mapping') else None,
            'user': {
                'id': transcription.user_id,
                'name': user_name
            },
            'recording': {
                'id': transcription.recording_id,
                'title': recording_title
            },
            'analysisResults': {
                'count': len(analysis_summaries),
                'items': analysis_summaries
            }
        }
        
        return jsonify({
            'status': 'success',
            'data': transcription_detail
        })
    except Exception as e:
        logger.error(f"Error getting transcription detail: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Related Entity Endpoints
# ============================================================================

@admin_bp.route('/users/<user_id>/related/<relation_type>', methods=['GET'])
@require_admin
def get_user_related(user_id: str, relation_type: str):
    """Get related entities for a user."""
    try:
        if relation_type == 'recordings':
            recording_handler = get_recording_handler()
            recordings = recording_handler.get_recordings_for_user(user_id)
            
            recording_summaries = [{
                'id': r.id,
                'title': r.title or r.original_filename,
                'recorded_timestamp': r.recorded_timestamp,
                'upload_timestamp': r.upload_timestamp,
                'duration': r.duration,
                'transcription_status': r.transcription_status
            } for r in recordings]
            
            return jsonify({
                'status': 'success',
                'data': recording_summaries,
                'count': len(recording_summaries)
            })
            
        elif relation_type == 'tags':
            user_handler = get_user_handler()
            user = user_handler.get_user(user_id)
            if not user:
                return jsonify({'status': 'error', 'error': 'User not found'}), 404
            
            tag_summaries = []
            if hasattr(user, 'tags') and user.tags:
                recording_handler = get_recording_handler()
                recordings = recording_handler.get_recordings_for_user(user_id)
                
                # Count usage for each tag
                tag_usage = {}
                for recording in recordings:
                    if recording.tagIds:
                        for tag_id in recording.tagIds:
                            tag_usage[tag_id] = tag_usage.get(tag_id, 0) + 1
                
                tag_summaries = [{
                    'id': tag.get('id'),
                    'name': tag.get('name'),
                    'color': tag.get('color'),
                    'usage_count': tag_usage.get(tag.get('id'), 0)
                } for tag in user.tags]
            
            return jsonify({
                'status': 'success',
                'data': tag_summaries,
                'count': len(tag_summaries)
            })
            
        else:
            return jsonify({'status': 'error', 'error': f'Unknown relation type: {relation_type}'}), 400
            
    except Exception as e:
        logger.error(f"Error getting user related {relation_type}: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/recordings/<recording_id>/related/<relation_type>', methods=['GET'])
@require_admin
def get_recording_related(recording_id: str, relation_type: str):
    """Get related entities for a recording."""
    try:
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        if not recording:
            return jsonify({'status': 'error', 'error': 'Recording not found'}), 404
        
        if relation_type == 'transcription':
            if not recording.transcription_id:
                return jsonify({'status': 'success', 'data': None})
            
            transcription_handler = get_transcription_handler()
            transcription = transcription_handler.get_transcription(recording.transcription_id)
            
            if transcription:
                transcription_summary = {
                    'id': transcription.id,
                    'created_at': getattr(transcription, 'created_at', None),
                    'text_snippet': (transcription.text[:100] + '...') if transcription.text and len(transcription.text) > 100 else transcription.text,
                    'hasDiarization': bool(transcription.diarized_transcript),
                    'analysisCount': len(transcription.analysisResults) if hasattr(transcription, 'analysisResults') and transcription.analysisResults else 0
                }
                return jsonify({'status': 'success', 'data': transcription_summary})
            
        elif relation_type == 'tags':
            if not recording.tagIds:
                return jsonify({'status': 'success', 'data': [], 'count': 0})
            
            user_handler = get_user_handler()
            user = user_handler.get_user(recording.user_id)
            
            tag_summaries = []
            if user and hasattr(user, 'tags') and user.tags:
                user_tags = {tag.get('id'): tag for tag in user.tags}
                tag_summaries = [{
                    'id': tag_id,
                    'name': user_tags.get(tag_id, {}).get('name', tag_id),
                    'color': user_tags.get(tag_id, {}).get('color', '#666666')
                } for tag_id in recording.tagIds if tag_id in user_tags]
            
            return jsonify({
                'status': 'success',
                'data': tag_summaries,
                'count': len(tag_summaries)
            })
            
        else:
            return jsonify({'status': 'error', 'error': f'Unknown relation type: {relation_type}'}), 400
            
    except Exception as e:
        logger.error(f"Error getting recording related {relation_type}: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Data Integrity Check Endpoints
# ============================================================================

@admin_bp.route('/integrity-check', methods=['POST'])
@require_admin
def run_integrity_check():
    """Run data integrity checks and find orphaned records."""
    try:
        user_handler = get_user_handler()
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()
        
        # Get all entities
        users = user_handler.get_all_users()
        recordings = recording_handler.get_all_recordings()
        transcriptions = transcription_handler.get_all_transcriptions()
        
        # Create lookup sets
        user_ids = {u.id for u in users}
        recording_ids = {r.id for r in recordings}
        transcription_ids = {t.id for t in transcriptions}
        
        issues = []
        
        # Check recordings with non-existent users
        for recording in recordings:
            if recording.user_id not in user_ids:
                issues.append({
                    'type': 'orphaned_recording',
                    'severity': 'high',
                    'entity_type': 'recording',
                    'entity_id': recording.id,
                    'entity_name': recording.title or recording.original_filename,
                    'issue': f'Recording belongs to non-existent user: {recording.user_id}'
                })
        
        # Check transcriptions with non-existent recordings
        for transcription in transcriptions:
            if transcription.recording_id not in recording_ids:
                issues.append({
                    'type': 'orphaned_transcription',
                    'severity': 'high',
                    'entity_type': 'transcription',
                    'entity_id': transcription.id,
                    'entity_name': f'Transcription for recording {transcription.recording_id}',
                    'issue': f'Transcription belongs to non-existent recording: {transcription.recording_id}'
                })
        
        # Check recordings with transcription_id that doesn't exist
        for recording in recordings:
            if recording.transcription_id and recording.transcription_id not in transcription_ids:
                issues.append({
                    'type': 'broken_reference',
                    'severity': 'medium',
                    'entity_type': 'recording',
                    'entity_id': recording.id,
                    'entity_name': recording.title or recording.original_filename,
                    'issue': f'Recording references non-existent transcription: {recording.transcription_id}'
                })
        
        # Check tags referenced in recordings that don't exist in user's tag list
        for recording in recordings:
            if recording.tagIds:
                user = next((u for u in users if u.id == recording.user_id), None)
                if user and hasattr(user, 'tags') and user.tags:
                    user_tag_ids = {tag.get('id') for tag in user.tags}
                    for tag_id in recording.tagIds:
                        if tag_id not in user_tag_ids:
                            issues.append({
                                'type': 'missing_tag',
                                'severity': 'low',
                                'entity_type': 'recording',
                                'entity_id': recording.id,
                                'entity_name': recording.title or recording.original_filename,
                                'issue': f'Recording references non-existent tag: {tag_id}'
                            })
        
        # Group issues by type
        issues_by_type = {}
        for issue in issues:
            issue_type = issue['type']
            if issue_type not in issues_by_type:
                issues_by_type[issue_type] = []
            issues_by_type[issue_type].append(issue)
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_issues': len(issues),
                'issues_by_type': {k: len(v) for k, v in issues_by_type.items()},
                'issues': issues
            }
        })
    except Exception as e:
        logger.error(f"Error running integrity check: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Delete Endpoints with Cascading
# ============================================================================

@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id: str):
    """Delete a user and all related data (recordings, transcriptions, tags)."""
    try:
        user_handler = get_user_handler()
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()
        
        # Check if user exists
        user = user_handler.get_user(user_id)
        if not user:
            return jsonify({'status': 'error', 'error': 'User not found'}), 404
        
        # Get all related data for cascade preview
        recordings = recording_handler.get_recordings_for_user(user_id)
        recording_ids = [r.id for r in recordings]
        
        transcription_count = 0
        for recording in recordings:
            if recording.transcription_id:
                transcription_count += 1
        
        # Perform cascading delete
        deleted_counts = {
            'recordings': 0,
            'transcriptions': 0
        }
        
        # Delete transcriptions
        for recording in recordings:
            if recording.transcription_id:
                try:
                    transcription_handler.delete_transcription(recording.transcription_id)
                    deleted_counts['transcriptions'] += 1
                except Exception as e:
                    logger.warning(f"Failed to delete transcription {recording.transcription_id}: {e}")
        
        # Delete recordings
        for recording_id in recording_ids:
            try:
                recording_handler.delete_recording(recording_id)
                deleted_counts['recordings'] += 1
            except Exception as e:
                logger.warning(f"Failed to delete recording {recording_id}: {e}")
        
        # Delete user
        user_handler.delete_user(user_id)
        
        return jsonify({
            'status': 'success',
            'message': f'User {user_id} deleted successfully',
            'cascade_summary': {
                'recordings_deleted': deleted_counts['recordings'],
                'transcriptions_deleted': deleted_counts['transcriptions']
            }
        })
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@admin_bp.route('/recordings/<recording_id>', methods=['DELETE'])
@require_admin
def delete_recording(recording_id: str):
    """Delete a recording and its transcription."""
    try:
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()
        
        # Check if recording exists
        recording = recording_handler.get_recording(recording_id)
        if not recording:
            return jsonify({'status': 'error', 'error': 'Recording not found'}), 404
        
        # Delete transcription if exists
        transcription_deleted = False
        if recording.transcription_id:
            try:
                transcription_handler.delete_transcription(recording.transcription_id)
                transcription_deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete transcription {recording.transcription_id}: {e}")
        
        # Delete recording
        recording_handler.delete_recording(recording_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Recording {recording_id} deleted successfully',
            'cascade_summary': {
                'transcription_deleted': transcription_deleted
            }
        })
    except Exception as e:
        logger.error(f"Error deleting recording: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Bulk Operations Endpoints
# ============================================================================

@admin_bp.route('/bulk-operations', methods=['POST'])
@require_admin
def bulk_operations():
    """Perform bulk operations on multiple entities."""
    try:
        data = request.get_json()
        operation = data.get('operation')
        entity_type = data.get('entity_type')
        entity_ids = data.get('entity_ids', [])
        
        if not operation or not entity_type or not entity_ids:
            return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
        
        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        if operation == 'delete':
            if entity_type == 'recordings':
                recording_handler = get_recording_handler()
                transcription_handler = get_transcription_handler()
                
                for recording_id in entity_ids:
                    try:
                        recording = recording_handler.get_recording(recording_id)
                        if recording:
                            # Delete transcription first if exists
                            if recording.transcription_id:
                                try:
                                    transcription_handler.delete_transcription(recording.transcription_id)
                                except Exception as e:
                                    logger.warning(f"Failed to delete transcription {recording.transcription_id}: {e}")
                            
                            recording_handler.delete_recording(recording_id)
                            results['success'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append(f"Recording {recording_id} not found")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to delete recording {recording_id}: {str(e)}")
            
            elif entity_type == 'users':
                # For users, we need to cascade delete all their data
                user_handler = get_user_handler()
                recording_handler = get_recording_handler()
                transcription_handler = get_transcription_handler()
                
                for user_id in entity_ids:
                    try:
                        user = user_handler.get_user(user_id)
                        if user:
                            # Delete all user's recordings and transcriptions
                            recordings = recording_handler.get_recordings_for_user(user_id)
                            for recording in recordings:
                                if recording.transcription_id:
                                    try:
                                        transcription_handler.delete_transcription(recording.transcription_id)
                                    except:
                                        pass
                                try:
                                    recording_handler.delete_recording(recording.id)
                                except:
                                    pass
                            
                            user_handler.delete_user(user_id)
                            results['success'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append(f"User {user_id} not found")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to delete user {user_id}: {str(e)}")
            
            else:
                return jsonify({'status': 'error', 'error': f'Unsupported entity type for bulk delete: {entity_type}'}), 400
        
        else:
            return jsonify({'status': 'error', 'error': f'Unsupported operation: {operation}'}), 400
        
        return jsonify({
            'status': 'success',
            'data': results
        })
        
    except Exception as e:
        logger.error(f"Error performing bulk operation: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Export Endpoints
# ============================================================================

@admin_bp.route('/export', methods=['GET'])
@require_admin
def export_data():
    """Export all or selected data in JSON format."""
    try:
        # Get query parameters
        entity_types = request.args.getlist('types')  # Can specify multiple types
        
        export_data = {}
        
        if not entity_types or 'users' in entity_types:
            user_handler = get_user_handler()
            users = user_handler.get_all_users()
            export_data['users'] = [user.dict() for user in users]
        
        if not entity_types or 'recordings' in entity_types:
            recording_handler = get_recording_handler()
            recordings = recording_handler.get_all_recordings()
            export_data['recordings'] = [recording.dict() for recording in recordings]
        
        if not entity_types or 'transcriptions' in entity_types:
            transcription_handler = get_transcription_handler()
            transcriptions = transcription_handler.get_all_transcriptions()
            export_data['transcriptions'] = [transcription.dict() for transcription in transcriptions]
        
        if not entity_types or 'analysis_types' in entity_types:
            analysis_type_handler = get_analysis_type_handler()
            analysis_types = analysis_type_handler.get_all_analysis_types()
            export_data['analysis_types'] = [at.dict() for at in analysis_types]
        
        return jsonify({
            'status': 'success',
            'data': export_data,
            'export_timestamp': datetime.now(UTC).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


# ============================================================================
# Search Endpoint
# ============================================================================

@admin_bp.route('/search', methods=['GET'])
@require_admin
def search():
    """Global search across all entity types."""
    try:
        query = request.args.get('q', '').lower()
        if not query:
            return jsonify({'status': 'error', 'error': 'Search query required'}), 400
        
        results = {
            'users': [],
            'recordings': [],
            'transcriptions': [],
            'tags': []
        }
        
        # Search users
        user_handler = get_user_handler()
        users = user_handler.get_all_users()
        for user in users:
            if (query in getattr(user, 'email', '').lower() or 
                query in getattr(user, 'name', '').lower() or
                query in user.id.lower()):
                results['users'].append({
                    'id': user.id,
                    'name': getattr(user, 'name', getattr(user, 'email', 'Unknown')),
                    'email': getattr(user, 'email', '')
                })
        
        # Search recordings
        recording_handler = get_recording_handler()
        recordings = recording_handler.get_all_recordings()
        for recording in recordings:
            if (query in (recording.title or '').lower() or 
                query in recording.original_filename.lower() or
                query in recording.id.lower()):
                results['recordings'].append({
                    'id': recording.id,
                    'title': recording.title or recording.original_filename,
                    'user_id': recording.user_id
                })
        
        # Search tags
        tag_results = {}
        for user in users:
            if hasattr(user, 'tags') and user.tags:
                for tag in user.tags:
                    if query in tag.get('name', '').lower():
                        tag_id = tag.get('id')
                        if tag_id not in tag_results:
                            tag_results[tag_id] = {
                                'id': tag_id,
                                'name': tag.get('name'),
                                'color': tag.get('color'),
                                'user_count': 0
                            }
                        tag_results[tag_id]['user_count'] += 1
        
        results['tags'] = list(tag_results.values())
        
        # Count total results
        total_results = sum(len(v) for v in results.values())
        
        return jsonify({
            'status': 'success',
            'data': results,
            'total_results': total_results
        })
        
    except Exception as e:
        logger.error(f"Error searching: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500