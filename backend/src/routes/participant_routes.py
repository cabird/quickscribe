"""
Participant management API routes.
Handles CRUD operations for participant profiles.
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any

from user_util import require_auth, get_current_user
from shared_quickscribe_py.cosmos import get_participant_handler
from pydantic import ValidationError

logger = logging.getLogger(__name__)

participant_bp = Blueprint('participants', __name__)

@participant_bp.route('', methods=['GET'])
@require_auth
def get_participants():
    """
    Get all participants for the current user.
    
    Returns:
        JSON response with list of participants
    """
    try:
        user_id = get_current_user().id
        handler = get_participant_handler()
        
        participants = handler.get_participants_for_user(user_id)
        
        return jsonify({
            'status': 'success',
            'data': [p.model_dump() for p in participants],
            'count': len(participants)
        })
        
    except Exception as e:
        logger.error(f"Error fetching participants for user {user_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to fetch participants'
        }), 500

@participant_bp.route('/<participant_id>', methods=['GET'])
@require_auth
def get_participant(participant_id: str):
    """
    Get a specific participant by ID.
    
    Args:
        participant_id: ID of the participant to retrieve
        
    Returns:
        JSON response with participant data
    """
    try:
        user_id = get_current_user().id
        handler = get_participant_handler()
        
        participant = handler.get_participant(user_id, participant_id)
        
        if not participant:
            return jsonify({
                'status': 'error',
                'error': 'Participant not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': participant.model_dump()
        })
        
    except Exception as e:
        logger.error(f"Error fetching participant {participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to fetch participant'
        }), 500

@participant_bp.route('', methods=['POST'])
@require_auth
def create_participant():
    """
    Create a new participant profile.
    
    Expected JSON body:
        {
            "displayName": "John Smith",
            "firstName": "John", (optional)
            "lastName": "Smith", (optional)
            "email": "john@example.com", (optional)
            "role": "Project Manager", (optional)
            "organization": "Acme Corp", (optional)
            "relationshipToUser": "Colleague", (optional)
            "notes": "Additional notes", (optional)
            "aliases": ["Johnny", "J. Smith"] (optional)
        }
        
    Returns:
        JSON response with created participant data
    """
    try:
        user_id = get_current_user().id
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'error': 'Request body is required'
            }), 400
        
        # Validate required fields
        if 'displayName' not in data or not data['displayName'].strip():
            return jsonify({
                'status': 'error',
                'error': 'displayName is required'
            }), 400
        
        handler = get_participant_handler()
        
        # Create participant
        participant = handler.create_participant(user_id, **data)
        
        logger.info(f"Created participant {participant.id} for user {user_id}")
        
        return jsonify({
            'status': 'success',
            'data': participant.model_dump()
        }), 201
        
    except ValidationError as e:
        logger.error(f"Validation error creating participant: {e}")
        return jsonify({
            'status': 'error',
            'error': f'Validation error: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Error creating participant: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to create participant'
        }), 500

@participant_bp.route('/<participant_id>', methods=['PUT'])
@require_auth
def update_participant(participant_id: str):
    """
    Update an existing participant profile.
    
    Args:
        participant_id: ID of the participant to update
        
    Expected JSON body:
        {
            "displayName": "John Smith Jr.", (optional)
            "firstName": "John", (optional)
            "lastName": "Smith Jr.", (optional)
            "email": "john.jr@example.com", (optional)
            "role": "Senior Project Manager", (optional)
            "organization": "Acme Corp", (optional)
            "relationshipToUser": "Boss", (optional)
            "notes": "Updated notes", (optional)
            "aliases": ["Johnny", "J. Smith", "JS"] (optional)
        }
        
    Returns:
        JSON response with updated participant data
    """
    try:
        user_id = get_current_user().id
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'error': 'Request body is required'
            }), 400
        
        handler = get_participant_handler()
        
        # Update participant
        updated_participant = handler.update_participant(user_id, participant_id, data)
        
        if not updated_participant:
            return jsonify({
                'status': 'error',
                'error': 'Participant not found'
            }), 404
        
        logger.info(f"Updated participant {participant_id}")
        
        return jsonify({
            'status': 'success',
            'data': updated_participant.model_dump()
        })
        
    except ValidationError as e:
        logger.error(f"Validation error updating participant {participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': f'Validation error: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Error updating participant {participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to update participant'
        }), 500

@participant_bp.route('/<participant_id>', methods=['DELETE'])
@require_auth
def delete_participant(participant_id: str):
    """
    Delete a participant profile.
    
    Note: This will also need to clean up references in recordings and transcriptions.
    
    Args:
        participant_id: ID of the participant to delete
        
    Returns:
        JSON response confirming deletion
    """
    try:
        user_id = get_current_user().id
        handler = get_participant_handler()
        
        # TODO: Add logic to clean up participant references in recordings/transcriptions
        # This should be done in a transaction or with proper cleanup handling
        
        deleted = handler.delete_participant(user_id, participant_id)
        
        if not deleted:
            return jsonify({
                'status': 'error',
                'error': 'Participant not found'
            }), 404
        
        logger.info(f"Deleted participant {participant_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Participant deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting participant {participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to delete participant'
        }), 500

@participant_bp.route('/search', methods=['GET'])
@require_auth
def search_participants():
    """
    Search participants by name.
    
    Query parameters:
        - name: Name to search for (required)
        - fuzzy: Whether to use fuzzy matching (default: true)
        
    Returns:
        JSON response with matching participants
    """
    try:
        user_id = get_current_user().id
        name = request.args.get('name')
        fuzzy = request.args.get('fuzzy', 'true').lower() == 'true'
        
        if not name:
            return jsonify({
                'status': 'error',
                'error': 'name parameter is required'
            }), 400
        
        handler = get_participant_handler()
        
        participants = handler.find_participants_by_name(user_id, name, fuzzy=fuzzy)
        
        return jsonify({
            'status': 'success',
            'data': [p.model_dump() for p in participants],
            'count': len(participants),
            'search_term': name,
            'fuzzy_search': fuzzy
        })
        
    except Exception as e:
        logger.error(f"Error searching participants for '{name}': {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to search participants'
        }), 500

@participant_bp.route('/<participant_id>/merge/<other_participant_id>', methods=['POST'])
@require_auth
def merge_participants(participant_id: str, other_participant_id: str):
    """
    Merge two participant profiles.
    
    The first participant (participant_id) will be kept, and the second 
    (other_participant_id) will be deleted after merging data.
    
    Args:
        participant_id: ID of the participant to keep
        other_participant_id: ID of the participant to merge and delete
        
    Expected JSON body:
        {
            "merge_fields": {
                "displayName": "John Smith", (optional - override display name)
                "aliases": ["Johnny", "J. Smith"], (optional - override aliases)
                "notes": "Combined notes" (optional - override notes)
            }
        }
        
    Returns:
        JSON response with the merged participant data
    """
    try:
        user_id = get_current_user().id
        data = request.get_json() or {}
        merge_fields = data.get('merge_fields', {})
        
        handler = get_participant_handler()
        
        # Get both participants
        primary = handler.get_participant(user_id, participant_id)
        secondary = handler.get_participant(user_id, other_participant_id)
        
        if not primary:
            return jsonify({
                'status': 'error',
                'error': 'Primary participant not found'
            }), 404
        
        if not secondary:
            return jsonify({
                'status': 'error',
                'error': 'Secondary participant not found'
            }), 404
        
        # Merge aliases from both participants
        combined_aliases = list(set(primary.aliases + secondary.aliases))
        
        # Add secondary's display name to aliases if different
        if secondary.displayName != primary.displayName:
            combined_aliases.append(secondary.displayName)
        
        # Add secondary's names to aliases if they exist and are different
        if secondary.firstName and secondary.firstName not in combined_aliases:
            combined_aliases.append(secondary.firstName)
        if secondary.lastName and secondary.lastName not in combined_aliases:
            combined_aliases.append(secondary.lastName)
        
        # Prepare merge data
        merge_data = {
            'aliases': merge_fields.get('aliases', combined_aliases),
            'lastSeen': max(primary.lastSeen, secondary.lastSeen),
            'firstSeen': min(primary.firstSeen, secondary.firstSeen)
        }
        
        # Override with any provided merge fields
        merge_data.update(merge_fields)
        
        # Combine notes if not overridden
        if 'notes' not in merge_fields:
            primary_notes = primary.notes or ""
            secondary_notes = secondary.notes or ""
            if primary_notes and secondary_notes:
                merge_data['notes'] = f"{primary_notes}\n\n--- Merged from {secondary.displayName} ---\n{secondary_notes}"
            elif secondary_notes:
                merge_data['notes'] = secondary_notes
        
        # Update primary participant with merged data
        updated_participant = handler.update_participant(user_id, participant_id, merge_data)
        
        if not updated_participant:
            return jsonify({
                'status': 'error',
                'error': 'Failed to update primary participant'
            }), 500
        
        # TODO: Update all recordings and transcriptions to point to primary participant
        # This should be done before deleting the secondary participant
        
        # Delete secondary participant
        deleted = handler.delete_participant(user_id, other_participant_id)
        
        if not deleted:
            logger.warning(f"Failed to delete secondary participant {other_participant_id} during merge")
        
        logger.info(f"Merged participant {other_participant_id} into {participant_id}")
        
        return jsonify({
            'status': 'success',
            'data': updated_participant.model_dump(),
            'message': f'Successfully merged participants'
        })
        
    except Exception as e:
        logger.error(f"Error merging participants {participant_id} and {other_participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to merge participants'
        }), 500

@participant_bp.route('/<participant_id>/update_last_seen', methods=['POST'])
@require_auth
def update_participant_last_seen(participant_id: str):
    """
    Update the last seen timestamp for a participant.
    
    Args:
        participant_id: ID of the participant to update
        
    Expected JSON body:
        {
            "timestamp": "2024-01-15T10:30:00Z" (optional - defaults to now)
        }
        
    Returns:
        JSON response confirming the update
    """
    try:
        user_id = get_current_user().id
        data = request.get_json() or {}
        
        handler = get_participant_handler()
        
        # Parse timestamp if provided
        timestamp = None
        if 'timestamp' in data:
            from datetime import datetime
            timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        
        success = handler.update_participant_last_seen(user_id, participant_id, timestamp)
        
        if not success:
            return jsonify({
                'status': 'error',
                'error': 'Participant not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Last seen timestamp updated'
        })
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'error': f'Invalid timestamp format: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Error updating last seen for participant {participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to update last seen timestamp'
        }), 500

@participant_bp.route('/<participant_id>/recordings', methods=['GET'])
@require_auth
def get_participant_recordings(participant_id: str):
    """
    Get recordings where a participant appears.

    Args:
        participant_id: ID of the participant

    Query parameters:
        - limit: Maximum number of recordings to return (default: 5)
        - offset: Number of recordings to skip (default: 0)

    Returns:
        JSON response with recordings and total count
    """
    try:
        user_id = get_current_user().id
        limit = request.args.get('limit', '5')
        offset = request.args.get('offset', '0')

        try:
            limit = int(limit)
            offset = int(offset)
        except ValueError:
            return jsonify({
                'status': 'error',
                'error': 'limit and offset must be integers'
            }), 400

        # Verify participant exists and belongs to user
        handler = get_participant_handler()
        participant = handler.get_participant(user_id, participant_id)

        if not participant:
            return jsonify({
                'status': 'error',
                'error': 'Participant not found'
            }), 404

        # Get recordings where this participant appears via transcription.speaker_mapping
        from shared_quickscribe_py.cosmos import get_recording_handler, get_transcription_handler
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()

        # Get only recording_id and speaker_mapping (optimized - no transcript text)
        speaker_mappings = transcription_handler.get_speaker_mappings_for_user(user_id)

        # Find recording IDs where this participant appears in speaker_mapping
        matching_recording_ids = set()
        for item in speaker_mappings:
            speaker_mapping = item.get('speaker_mapping') or {}
            for speaker_label, mapping in speaker_mapping.items():
                # Handle both dict and SpeakerMapping Pydantic object
                if isinstance(mapping, dict):
                    pid = mapping.get('participantId')
                elif hasattr(mapping, 'participantId'):
                    pid = mapping.participantId
                else:
                    continue
                if pid == participant_id:
                    matching_recording_ids.add(item.get('recording_id'))
                    break

        # Get all matching recordings in a single batch query
        matching_recordings = recording_handler.get_recordings_by_ids(list(matching_recording_ids))

        # Sort by recorded_timestamp descending (most recent first)
        matching_recordings.sort(key=lambda r: r.recorded_timestamp or '', reverse=True)

        # Get total count before pagination
        total = len(matching_recordings)

        # Apply pagination
        paginated_recordings = matching_recordings[offset:offset + limit]

        return jsonify({
            'status': 'success',
            'data': [r.model_dump() for r in paginated_recordings],
            'count': len(paginated_recordings),
            'total': total
        })

    except Exception as e:
        logger.error(f"Error fetching recordings for participant {participant_id}: {e}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to fetch participant recordings'
        }), 500