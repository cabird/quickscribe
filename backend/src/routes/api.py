# api.py
from flask import Blueprint, request, jsonify, url_for
from shared_quickscribe_py.cosmos import get_user_handler, get_recording_handler, get_transcription_handler, get_deleted_items_handler, get_participant_handler
from user_util import get_current_user, require_auth
from shared_quickscribe_py.cosmos import User, Recording, Transcription, TranscodingStatus, TranscriptionStatus, Tag
from util import get_recording_duration_in_seconds
from ai_postprocessing import postprocess_recording_full, update_transcription_speaker_data, update_transcription_speaker_data_with_participants
import re
import uuid
import os
from werkzeug.utils import secure_filename
from datetime import datetime, UTC
import time
from blob_util import store_recording_as_blob, send_to_transcoding_queue
from api_version import API_VERSION
from config import config

from logging_config import get_logger
# Initialize logger
logger = get_logger('api', API_VERSION)
logger.info(f"Starting QuickScribe API ({API_VERSION})")

api_bp = Blueprint('api', __name__)

def validate_hex_color(color: str) -> bool:
    """Validate that a string is a valid hex color code."""
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', color))


def enrich_transcription_with_participants(transcription: Transcription, user_id: str) -> dict:
    """
    Enrich a transcription's speaker_mapping with participant displayNames.

    This resolves participantId references to actual displayNames at query time,
    providing a single source of truth for participant names.

    Args:
        transcription: The transcription object to enrich
        user_id: The user ID for fetching participants

    Returns:
        Transcription data dict with enriched speaker_mapping
    """
    transcription_data = transcription.model_dump()

    if not transcription.speaker_mapping:
        return transcription_data

    # Fetch all participants for this user
    participant_handler = get_participant_handler()
    participants = participant_handler.get_participants_for_user(user_id)
    participant_map = {p.id: p for p in participants}

    # Enrich each speaker mapping entry with displayName from participant lookup
    enriched_mapping = {}
    for speaker_label, mapping in transcription.speaker_mapping.items():
        # Convert mapping to dict if it's a Pydantic model
        if hasattr(mapping, 'model_dump'):
            mapping_dict = mapping.model_dump()
        else:
            mapping_dict = dict(mapping) if mapping else {}

        # Look up participant and add displayName
        participant_id = mapping_dict.get('participantId')
        if participant_id and participant_id in participant_map:
            participant = participant_map[participant_id]
            mapping_dict['displayName'] = participant.displayName
        else:
            # No participant linked or not found - displayName will be None
            mapping_dict['displayName'] = None

        # Enrich suggestedParticipantId with suggestedDisplayName
        suggested_id = mapping_dict.get('suggestedParticipantId')
        if suggested_id and suggested_id in participant_map:
            mapping_dict['suggestedDisplayName'] = participant_map[suggested_id].displayName

        # Enrich topCandidates displayNames
        top_candidates = mapping_dict.get('topCandidates')
        if top_candidates:
            for candidate in top_candidates:
                cid = candidate.get('participantId')
                if cid and cid in participant_map:
                    candidate['displayName'] = participant_map[cid].displayName

        # Strip embedding from API response (large, internal-only)
        mapping_dict.pop('embedding', None)

        enriched_mapping[speaker_label] = mapping_dict

    transcription_data['speaker_mapping'] = enriched_mapping
    return transcription_data


@api_bp.route('/get_api_version', methods=['GET'])
def get_api_version():
    return jsonify({'version': API_VERSION}), 200

@api_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint with version and system status."""
    return jsonify({
        'status': 'healthy',
        'version': API_VERSION,
        'timestamp': datetime.now(UTC).isoformat(),
        'service': 'quickscribe-backend'
    }), 200


@api_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user_info():
    """Get the current authenticated user's profile."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    return jsonify(current_user.model_dump()), 200


@api_bp.route('/me/plaud-settings', methods=['PUT'])
@require_auth
def update_current_user_plaud_settings():
    """Update the current user's Plaud integration settings."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_handler = get_user_handler()

    # Get fresh user data
    user = user_handler.get_user(current_user.id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Initialize plaudSettings if it doesn't exist
    if not user.plaudSettings:
        from shared_quickscribe_py.cosmos import PlaudSettings
        user.plaudSettings = PlaudSettings(bearerToken='')

    # Update only the allowed fields
    if 'enableSync' in data:
        user.plaudSettings.enableSync = data['enableSync']
    if 'bearerToken' in data:
        user.plaudSettings.bearerToken = data['bearerToken']

    # Save the user
    user_handler.save_user(user)

    return jsonify({
        'status': 'success',
        'message': 'Plaud settings updated',
        'plaudSettings': user.plaudSettings.model_dump() if user.plaudSettings else None
    }), 200


# Route to get a user by ID
@api_bp.route('/user/<user_id>', methods=['GET'])
@require_auth
def get_user_by_id(user_id):
    user_handler = get_user_handler()
    user = user_handler.get_user(user_id)
    if user:
        return jsonify(user.model_dump()), 200
    return jsonify({'error': 'User not found'}), 404

# Route to list all users
@api_bp.route('/users', methods=['GET'])
@require_auth
def list_users():
    user_handler = get_user_handler()
    users = user_handler.get_all_users()
    return jsonify([user.model_dump() for user in users]), 200

# Route to get a recording by ID
@api_bp.route('/recording/<recording_id>', methods=['GET'])
@require_auth
def get_recording_by_id(recording_id):
    recording_handler = get_recording_handler()
    recording = recording_handler.get_recording(recording_id)
    if recording:
        return jsonify(recording.model_dump()), 200
    return jsonify({'error': 'Recording not found'}), 404

# Route to get audio URL for a recording
@api_bp.route('/recording/<recording_id>/audio-url', methods=['GET'])
@require_auth
def get_recording_audio_url(recording_id):
    """Generate a time-limited SAS URL for streaming the recording's audio file."""
    try:
        logger.info(f"Audio URL requested for recording {recording_id}")
        
        # Get current user for authorization
        current_user = get_current_user()
        if not current_user:
            logger.error(f"No authenticated user for recording {recording_id}")
            return jsonify({'error': 'User not authenticated'}), 401
        
        logger.info(f"User {current_user.id} requesting audio for recording {recording_id}")
        
        # Get the recording
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        
        if not recording:
            logger.error(f"Recording {recording_id} not found")
            return jsonify({'error': 'Recording not found'}), 404
            
        # Verify the recording belongs to the current user
        if recording.user_id != current_user.id:
            logger.error(f"Recording {recording_id} belongs to {recording.user_id}, not {current_user.id}")
            return jsonify({'error': 'Recording does not belong to current user'}), 403
        
        # Check if the recording has been transcoded
        logger.info(f"Recording {recording_id} transcoding status: {recording.transcoding_status}")
        
        # If transcoding_status is None but transcription is completed, assume audio is available
        # This handles older recordings that don't have transcoding_status set
        if recording.transcription_status == TranscriptionStatus.completed:
            logger.info(f"Recording {recording_id} has completed transcription, assuming audio is available")
        elif recording.transcoding_status != TranscodingStatus.completed:
            return jsonify({'error': 'Recording audio is not ready yet', 'status': str(recording.transcoding_status)}), 400
        
        # Generate SAS URL for the blob
        from blob_util import generate_recording_sas_url
        
        # The transcoded file should be at the blob_name location
        # Try blob_name first (newer recordings), then fall back to unique_filename
        # Blobs may be stored with user_id prefix: {user_id}/{filename}
        blob_name = None

        if hasattr(recording, 'blob_name') and recording.blob_name:
            blob_name = recording.blob_name
            logger.info(f"Recording {recording_id} has blob_name: {blob_name}")
        elif hasattr(recording, 'unique_filename') and recording.unique_filename:
            # Try with user_id prefix first (newer storage pattern), then fall back to just filename
            from blob_util import _get_blob_client
            blob_client = _get_blob_client()

            # Try {user_id}/{filename} first
            user_prefixed_path = f"{recording.user_id}/{recording.unique_filename}"
            if blob_client.blob_exists(user_prefixed_path):
                blob_name = user_prefixed_path
                logger.info(f"Recording {recording_id} found at user-prefixed path: {blob_name}")
            elif blob_client.blob_exists(recording.unique_filename):
                # Fall back to just the filename (older storage pattern)
                blob_name = recording.unique_filename
                logger.info(f"Recording {recording_id} found at filename only: {blob_name}")
            else:
                logger.error(f"Recording {recording_id} blob not found at either {user_prefixed_path} or {recording.unique_filename}")
                return jsonify({'error': 'Audio file not found in storage'}), 404
        else:
            logger.error(f"Recording {recording_id} has no blob_name or unique_filename")
            return jsonify({'error': 'Recording has no associated audio file'}), 400
        
        # Generate a read-only SAS URL valid for 24 hours
        audio_url = generate_recording_sas_url(blob_name, read=True, write=False)
        
        logger.info(f"Successfully generated audio URL for recording {recording_id}")
        return jsonify({
            'audio_url': audio_url,
            'expires_in': 86400,  # 24 hours in seconds
            'content_type': 'audio/mpeg'
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating audio URL for recording {recording_id}: {str(e)}")
        return jsonify({'error': 'Failed to generate audio URL'}), 500

# Route to list all recordings
@api_bp.route('/recordings', methods=['GET'])
@require_auth
def list_recordings():
    import time
    t0 = time.time()

    recording_handler = get_recording_handler()
    transcription_handler = get_transcription_handler()
    participant_handler = get_participant_handler()
    user = get_current_user()
    recordings = recording_handler.get_recording_summaries(user.id)

    t1 = time.time()
    logger.info(f"list_recordings: fetched {len(recordings)} recordings in {t1-t0:.2f}s")

    # Build speaker names map using optimized query (avoids fetching full transcript text)
    speaker_names_map = {}  # recording_id -> list of speaker names
    speaker_mapping_rows = transcription_handler.get_speaker_mappings_for_user(user.id)

    t2 = time.time()
    logger.info(f"list_recordings: fetched speaker mappings in {t2-t1:.2f}s")

    if speaker_mapping_rows:
        # Collect all participant IDs we need to look up
        all_participant_ids = set()
        for row in speaker_mapping_rows:
            sm = row.get('speaker_mapping')
            if sm:
                for mapping in sm.values():
                    pid = mapping.get('participantId') if isinstance(mapping, dict) else getattr(mapping, 'participantId', None)
                    if pid:
                        all_participant_ids.add(pid)

        # Batch fetch all user's participants and build lookup
        participants_map = {}
        if all_participant_ids:
            all_participants = participant_handler.get_participants_for_user(user.id)
            for p in all_participants:
                if p.id in all_participant_ids:
                    participants_map[p.id] = p.displayName

        t3 = time.time()
        logger.info(f"list_recordings: fetched {len(participants_map)} participants in {t3-t2:.2f}s")

        # Build speaker names for each recording
        for row in speaker_mapping_rows:
            recording_id = row.get('recording_id')
            sm = row.get('speaker_mapping')
            if not recording_id or not sm:
                continue
            names = []
            for mapping in sm.values():
                pid = mapping.get('participantId') if isinstance(mapping, dict) else getattr(mapping, 'participantId', None)
                if pid and pid in participants_map:
                    names.append(participants_map[pid])
            speaker_names_map[recording_id] = names

    # Build response with enriched speaker_names
    recording_list = []
    for rec in recordings:
        if rec.get('id') and rec.get('id') in speaker_names_map:
            rec['speaker_names'] = speaker_names_map[rec['id']]
        recording_list.append(rec)

    t_end = time.time()
    logger.info(f"list_recordings: total {t_end-t0:.2f}s")

    return jsonify(recording_list), 200

# Route to get a transcription by ID
@api_bp.route('/transcription/<transcription_id>', methods=['GET'])
@require_auth
def get_transcription_by_id(transcription_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if not transcription:
        return jsonify({'error': 'Transcription not found'}), 404

    # Verify ownership
    if transcription.user_id != current_user.id:
        return jsonify({'error': 'Transcription does not belong to current user'}), 403

    # Enrich speaker_mapping with participant displayNames
    enriched_data = enrich_transcription_with_participants(transcription, current_user.id)
    return jsonify(enriched_data), 200

# Route to get all transcriptions for a user
@api_bp.route('/user/<user_id>/transcriptions', methods=['GET'])
@require_auth
def get_user_transcriptions(user_id):
    transcription_handler = get_transcription_handler()
    transcriptions = transcription_handler.get_user_transcriptions(user_id)
    return jsonify([transcription.model_dump() for transcription in transcriptions]), 200

# Route to get all recordings for a user
@api_bp.route('/user/<user_id>/recordings', methods=['GET'])
@require_auth
def get_user_recordings(user_id):
    recording_handler = get_recording_handler()
    recordings = recording_handler.get_user_recordings(user_id)
    return jsonify([recording.model_dump() for recording in recordings]), 200

# Route to get users by a list of IDs
@api_bp.route('/users', methods=['POST'])
@require_auth
def get_users_by_ids():
    user_handler = get_user_handler()
    ids = request.json.get('ids', [])
    users = [user_handler.get_user(user_id) for user_id in ids]
    return jsonify([user.model_dump() for user in users if user]), 200

# Route to get recordings by a list of IDs
@api_bp.route('/recordings', methods=['POST'])
@require_auth
def get_recordings_by_ids():
    recording_handler = get_recording_handler()
    ids = request.json.get('ids', [])
    recordings = [recording_handler.get_recording(recording_id) for recording_id in ids]
    return jsonify([recording.model_dump() for recording in recordings if recording]), 200

# Route to get transcriptions by a list of IDs
@api_bp.route('/transcriptions', methods=['POST'])
@require_auth
def get_transcriptions_by_ids():
    transcription_handler = get_transcription_handler()
    ids = request.json.get('ids', [])
    transcriptions = [transcription_handler.get_transcription(transcription_id) for transcription_id in ids]
    return jsonify([transcription.model_dump() for transcription in transcriptions if transcription]), 200

# Route to delete items by ID
@api_bp.route('/delete_user/<user_id>', methods=['GET'])
@require_auth
def delete_user(user_id):
    user_handler = get_user_handler()
    user_handler.delete_user(user_id)
    return jsonify({'message': 'User deleted successfully'}), 200

@api_bp.route('/delete_recording/<recording_id>', methods=['GET'])
@require_auth
def delete_recording(recording_id):
    recording_handler = get_recording_handler()
    deleted_items_handler = get_deleted_items_handler()

    # Get the recording before deleting to check if it's from Plaud
    recording = recording_handler.get_recording(recording_id)

    # If it's a Plaud recording, add to deleted items to prevent re-sync
    if recording and recording.plaudMetadata and recording.plaudMetadata.plaudId:
        plaud_id = recording.plaudMetadata.plaudId
        user_id = recording.user_id
        logger.info(f"Adding Plaud ID {plaud_id} to deleted items for user {user_id}")
        deleted_items_handler.add_deleted_plaud_id(user_id, plaud_id)

    # Delete the recording
    recording_handler.delete_recording(recording_id)
    return jsonify({'message': 'Recording deleted successfully'}), 200

@api_bp.route('/delete_transcription/<transcription_id>', methods=['GET'])
@require_auth
def delete_transcription(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription_handler.delete_transcription(transcription_id)
    return jsonify({'message': 'Transcription deleted successfully'}), 200

# Route to update items by ID
@api_bp.route('/user/<user_id>', methods=['PUT'])
@require_auth
def update_user(user_id):
    user_handler = get_user_handler()
    user_data = request.json
    updated_user = user_handler.update_user(user_id, **user_data)
    if updated_user:
        return jsonify(updated_user.model_dump()), 200
    return jsonify({'error': 'User not found'}), 404

@api_bp.route('/recording/<recording_id>', methods=['PUT'])
@require_auth
def update_recording(recording_id):
    recording_handler = get_recording_handler()
    recording_data = request.json
    recording = recording_handler.get_recording(recording_id)
    if recording:
        for key, value in recording_data.items():
            setattr(recording, key, value)
        updated_recording = recording_handler.update_recording(recording)
        return jsonify(updated_recording.model_dump()), 200
    return jsonify({'error': 'Recording not found'}), 404

@api_bp.route('/transcription/<transcription_id>', methods=['PUT'])
@require_auth
def update_transcription(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription_data = request.json
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription:
        for key, value in transcription_data.items():
            setattr(transcription, key, value)
        updated_transcription = transcription_handler.update_transcription(transcription)
        return jsonify(updated_transcription.model_dump()), 200
    return jsonify({'error': 'Transcription not found'}), 404





#support upload from iphone share context menu
@api_bp.route("/upload_from_ios_share", methods=['POST'])
@require_auth
def upload_from_ios_share():
    logger.info("upload_from_ios_share endpoint called")

    # log file details
    filenames = [request.files[key].filename for key in request.files.keys()]
    #output the list of files in the request
    for file in request.files.values():
        #output all the fields in the file:
        logger.info(f"upload_from_ios_share: file {file}")
        logger.info(f"upload_from_ios_share: file.filename {file.filename}")
        logger.info(f"upload_from_ios_share: file.content_type {file.content_type}")
        logger.info(f"upload_from_ios_share: file.mimetype {file.mimetype}")
        logger.info(f"upload_from_ios_share: file.content_length {file.content_length}")
        logger.info(f"upload_from_ios_share: file.headers {file.headers}")

    logger.info(f"upload_from_ios_share: request files {filenames}")

    if 'audio_file' not in request.files:
        return jsonify({'error': 'No audio file part'}), 400

    audio_file = request.files['audio_file']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if audio_file:
        logger.info(f"handling upload of audio file: {audio_file}")

        try:
            logger.info(f"handling upload of file: {audio_file}")
            original_filename = secure_filename(audio_file.filename)

            #get the file extension
            file_extension = os.path.splitext(audio_file.filename)[1]
            unique_original_filename = uuid.uuid4().hex + file_extension
            unique_transcoded_filename = uuid.uuid4().hex + ".mp3"

            temp_path = os.path.join('/tmp', unique_original_filename)
            audio_file.save(temp_path)
            logger.info(f"file saved to {temp_path}")

            #store the original file in blob storage
            store_recording_as_blob(temp_path, unique_original_filename)
            logger.info(f"stored original file in blob storage as {unique_original_filename}")

            recording_handler = get_recording_handler()
            user = get_current_user()

            recording = recording_handler.create_recording(
                user.id, 
                original_filename, 
                unique_original_filename,
                transcoding_status=TranscodingStatus.queued,
                title=original_filename,  # Default title to filename
                recorded_timestamp=datetime.now(UTC).isoformat()  # Use upload time as fallback
            )
            recording.upload_timestamp = datetime.now(UTC).isoformat()
            recording.duration = get_recording_duration_in_seconds(temp_path)
            recording_handler.update_recording(recording)

            send_to_transcoding_queue(recording.id,
                                      unique_original_filename,
                                      unique_transcoded_filename,
                                      original_filename,
                                      user.id)

            logger.info(f"sent to transcoding queue: {recording.id}, {unique_original_filename}, {unique_transcoded_filename}, {original_filename}, {user.id}")

            os.remove(temp_path)

            return jsonify({'success': 'File uploaded successfully!', 
                            'filename': original_filename, 
                            'recording_id': recording.id, 
                            'transcoding_status': 'queued'}), 200



        except Exception as e:
            logger.error(f"error uploading file: {e}")
            #print the stack trace
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        
    return jsonify({'error': 'No valid audio file provided'}), 400


def generate_callbacks(request, callback_token):
    callbacks = []
    
    # Use configured backend URL for Docker environments
    backend_base_url = os.getenv('BACKEND_BASE_URL')
    if backend_base_url:
        callback_url = f"{backend_base_url.rstrip('/')}/api/transcoding_callback"
    else:
        callback_url = url_for('api.transcoding_callback', _external=True)
    
    callbacks.append( { "url": callback_url, "token": callback_token })
    
    # Add test webhook for production environments
    if config.RUNNING_IN_AZURE:
        callbacks.append( { "url": "https://www.postb.in/1747433051215-4530967178288", "token": callback_token })
    
    return callbacks
   

# File upload form route
@api_bp.route('/upload', methods=['POST'])
@require_auth
def upload():
    logger.info("upload endpoint called")
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            logger.info(f"handling upload of file: {file}")
            original_filename = secure_filename(file.filename)
            
            # Generate unique filename for the original upload
            file_extension = os.path.splitext(original_filename)[1]
            unique_original_filename = str(uuid.uuid4()) + file_extension
            
            # Generate target filename for transcoded version (always .mp3)
            unique_transcoded_filename = str(uuid.uuid4()) + ".mp3"
            
            # Save original file to temporary location
            temp_path = os.path.join('/tmp', unique_original_filename)
            file.save(temp_path)
            logger.info(f"file saved to {temp_path}")

            # Store original file in blob storage
            store_recording_as_blob(temp_path, unique_original_filename)
            logger.info(f"stored original file in blob storage as {unique_original_filename}")

            # Create recording in database with transcoding status "queued"
            recording_handler = get_recording_handler()
            user = get_current_user()
            
            recording = recording_handler.create_recording(
                user.id, 
                original_filename, 
                unique_original_filename,  # This will be the final transcoded filename
                transcoding_status=TranscodingStatus.queued,
                title=original_filename,  # Default title to filename
                recorded_timestamp=datetime.now(UTC).isoformat()  # Use upload time as fallback
            )
            recording.upload_timestamp = datetime.now(UTC).isoformat()
            recording.transcoding_token = str(uuid.uuid4())
            recording_handler.update_recording(recording)
            
            # Queue transcoding job
            send_to_transcoding_queue(
                recording.id,
                unique_original_filename,  # Source file
                unique_transcoded_filename,  # Target file
                original_filename,
                user.id,
                generate_callbacks(request, recording.transcoding_token)
            )
            logger.info(f"queued transcoding job for recording {recording.id}")

            # Clean up temporary file
            os.remove(temp_path)
            
            return jsonify({
                'message': 'File uploaded successfully and queued for transcoding!', 
                'filename': original_filename, 
                'recording_id': recording.id,
                'transcoding_status': 'queued',
                'token': recording.transcoding_token
            }), 200

        except Exception as e:
            logger.error(f"error uploading file: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Only supported audio files are allowed'}), 400

@api_bp.route('/transcoding_status/<recording_id>', methods=['GET'])
@require_auth
def get_transcoding_status(recording_id):
    recording_handler = get_recording_handler()
    recording = recording_handler.get_recording(recording_id)
    
    if not recording:
        return jsonify({'error': 'Recording not found'}), 404
    
    return jsonify({
        'recording_id': recording_id,
        'transcoding_status': recording.transcoding_status.value,
        'transcoding_started_at': recording.transcoding_started_at,
        'transcoding_completed_at': recording.transcoding_completed_at,
        'transcoding_error_message': recording.transcoding_error_message,
        'transcoding_retry_count': recording.transcoding_retry_count
    }), 200

# Transcoding callback route - handles callbacks from the transcoding container
@api_bp.route('/transcoding_callback', methods=['POST'])
def transcoding_callback():
    logger.info("transcoding_callback endpoint called")

    try:
        # Get the data from the request
        data = request.get_json()
        action = data.get('action', "None")
        logger.info(f"transcoding_callback: '{action}' request json {data}")

        # Check if this is a test message
        if data.get('action') == 'test':
            logger.info(f"transcoding_callback: test message received - original content: {data.get('content', 'None')}, message from container: {data.get('message', 'None')}")
            return jsonify({'message': 'Test callback received'}), 200
        
        # Validate required fields for transcoding callback
        if data.get('action') != 'transcode' or 'recording_id' not in data or 'status' not in data:
            logger.error(f"Invalid callback format: {data}")
            return jsonify({'error': 'Invalid callback format'}), 400
        
        # Get necessary fields
        recording_id = data.get('recording_id')
        status = data.get('status')
        callback_token = data.get('callback_token')
        
        # Retrieve the recording
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        
        if not recording:
            logger.error(f"Recording not found: {recording_id}")
            return jsonify({'error': f'Recording not found: {recording_id}'}), 404
            
        # Verify callback token
        if recording.transcoding_token != callback_token:
            logger.error(f"Invalid callback token for recording {recording_id}")
            return jsonify({'error': 'Invalid callback token'}), 401
        
        # Update recording based on status
        if status == 'in_progress':
            recording.transcoding_status = TranscodingStatus.in_progress
            
        elif status == 'completed':
            recording.transcoding_status = TranscodingStatus.completed
            
            # Update duration if available in the metadata
            if 'output_metadata' in data and 'duration' in data['output_metadata']:
                recording.duration = data['output_metadata']['duration']
                
            # Track processing time
            if 'processing_time' in data:
                logger.info(f"Transcoding completed in {data['processing_time']} seconds")
            
            # Trigger AI post-processing for completed recordings
            try:
                logger.info(f"Starting AI post-processing for recording {recording_id}")
                postprocess_results = postprocess_recording_full(recording_id)
                
                if postprocess_results['errors']:
                    logger.warning(f"AI post-processing completed with errors for {recording_id}: {postprocess_results['errors']}")
                else:
                    logger.info(f"AI post-processing completed successfully for recording {recording_id}")
                    
            except Exception as e:
                # Log error but don't fail the callback - transcoding was successful
                logger.warning(f"AI post-processing failed for recording {recording_id}: {e}")
                # Don't re-raise - we want the transcoding callback to succeed

        elif status == 'failed':
            recording.transcoding_status = TranscodingStatus.failed
            
            # Store error message
            if 'error_message' in data:
                recording.transcoding_error_message = data['error_message']
                
            # Increment retry count
            if recording.transcoding_retry_count is None:
                recording.transcoding_retry_count = 1
            else:
                recording.transcoding_retry_count += 1
                
        # Save the updated recording
        recording_handler.update_recording(recording)
        
        return jsonify({'message': 'Transcoding callback processed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error processing transcoding callback: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/recording/<recording_id>/postprocess', methods=['POST'])
@require_auth
def manual_postprocess_recording(recording_id):
    """
    Manually trigger AI post-processing for an existing recording.
    This endpoint allows the frontend to request post-processing for recordings
    that have been transcribed but need AI-generated title, description, or speaker inference.
    """
    logger.info(f"Manual post-processing requested for recording {recording_id}")
    
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Verify recording exists and belongs to user
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        
        if not recording:
            logger.error(f"Recording not found: {recording_id}")
            return jsonify({'error': f'Recording not found: {recording_id}'}), 404
            
        if recording.user_id != current_user.id:
            logger.error(f"Recording {recording_id} does not belong to user {current_user.id}")
            return jsonify({'error': 'Recording does not belong to current user'}), 403
        
        # Check if recording has been transcribed
        if recording.transcription_status != TranscriptionStatus.completed:
            return jsonify({
                'error': 'Recording must be transcribed before post-processing',
                'current_status': recording.transcription_status
            }), 400
        
        # Perform AI post-processing
        postprocess_results = postprocess_recording_full(recording_id)
        
        # Fetch updated recording and transcription data to include in response
        updated_recording = recording_handler.get_recording(recording_id)
        transcription_data = None
        
        if updated_recording and updated_recording.transcription_id:
            transcription_handler = get_transcription_handler()
            transcription = transcription_handler.get_transcription(updated_recording.transcription_id)
            if transcription:
                transcription_data = transcription.model_dump()
        
        # Prepare response based on results
        response_data = {
            'recording_id': recording_id,
            'status': 'completed' if not postprocess_results['errors'] else 'partial',
            'results': {
                'title_generated': bool(postprocess_results['title']),
                'description_generated': bool(postprocess_results['description']),
                'speakers_updated': bool(postprocess_results['speaker_update'])
            },
            'updated_recording': updated_recording.model_dump() if updated_recording else None,
            'updated_transcription': transcription_data
        }
        
        if postprocess_results['errors']:
            response_data['errors'] = postprocess_results['errors']
            logger.warning(f"Manual post-processing completed with errors for {recording_id}: {postprocess_results['errors']}")
        else:
            logger.info(f"Manual post-processing completed successfully for recording {recording_id}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in manual post-processing for {recording_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/recording/<recording_id>/update_speakers', methods=['POST'])
@require_auth
def update_speakers(recording_id):
    """
    Update speaker names for a recording.
    Accepts a mapping of speaker labels to names and updates the transcription
    speaker mapping (single source of truth for speaker data).
    """
    logger.info(f"Update speakers requested for recording {recording_id}")
    
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Validate request data
        if not request.json:
            return jsonify({'error': 'No speaker mapping provided'}), 400
            
        speaker_mapping = request.json
        
        # Validate speaker mapping format
        if not isinstance(speaker_mapping, dict):
            return jsonify({'error': 'Speaker mapping must be a dictionary'}), 400
            
        # Validate speaker data - handle both old string format and new participant format
        errors = []
        
        for speaker_label, speaker_data in speaker_mapping.items():
            if isinstance(speaker_data, str):
                # Old format - just validate the name
                if not speaker_data or not speaker_data.strip():
                    errors.append(f"Speaker name cannot be empty for {speaker_label}")
                elif len(speaker_data.strip()) > 50:
                    errors.append(f"Speaker name too long for {speaker_label} (max 50 characters)")
            elif isinstance(speaker_data, dict):
                # New format with participant data
                participant_id = speaker_data.get('participantId')
                display_name = speaker_data.get('displayName', '').strip()
                
                if not participant_id:
                    errors.append(f"Participant ID required for {speaker_label}")
                
                if not display_name:
                    errors.append(f"Display name required for {speaker_label}")
                elif len(display_name) > 50:
                    errors.append(f"Display name too long for {speaker_label} (max 50 characters)")
            else:
                errors.append(f"Invalid speaker data format for {speaker_label}")
        
        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Verify recording exists and belongs to user
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        
        if not recording:
            logger.error(f"Recording not found: {recording_id}")
            return jsonify({'error': f'Recording not found: {recording_id}'}), 404
            
        if recording.user_id != current_user.id:
            logger.error(f"Recording {recording_id} does not belong to user {current_user.id}")
            return jsonify({'error': 'Recording does not belong to current user'}), 403
        
        # Check if recording has been transcribed
        if not recording.transcription_id:
            return jsonify({'error': 'Recording has not been transcribed yet'}), 400
            
        # Update transcription speaker mapping (single source of truth)
        try:
            # Handle both old and new format
            if all(isinstance(data, str) for data in speaker_mapping.values()):
                # Old format: just speaker names
                speaker_results = update_transcription_speaker_data(
                    recording.transcription_id,
                    speaker_mapping,
                    reasoning="User edited"
                )
            else:
                # New format: participant-aware updates
                speaker_results = update_transcription_speaker_data_with_participants(
                    recording.transcription_id,
                    speaker_mapping,
                    reasoning="User edited"
                )
            
            # Fetch updated data for response
            updated_recording = recording_handler.get_recording(recording_id)
            transcription_handler = get_transcription_handler()
            updated_transcription = transcription_handler.get_transcription(recording.transcription_id)
            
            response_data = {
                'status': 'success',
                'message': 'Speaker mapping updated successfully',
                'updated_recording': updated_recording.model_dump() if updated_recording else None,
                'updated_transcription': updated_transcription.model_dump() if updated_transcription else None,
                'speaker_results': speaker_results
            }
            
            logger.info(f"Successfully updated speakers for recording {recording_id}")
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.error(f"Error updating speaker data for recording {recording_id}: {e}")
            return jsonify({'error': f'Failed to update speaker data: {str(e)}'}), 500
        
    except Exception as e:
        logger.error(f"Error in update_speakers for {recording_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/speaker', methods=['POST'])
@require_auth
def update_single_speaker(transcription_id):
    """
    Update a single speaker assignment in a transcription.
    Expects: {
        "speaker_label": "Speaker 1", 
        "participant_id": "participant-uuid",
        "manually_verified": true
    }
    """
    logger.info(f"Update single speaker requested for transcription {transcription_id}")
    
    try:
        current_user = get_current_user()
        
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        speaker_label = data.get('speaker_label')
        participant_id = data.get('participant_id')
        manually_verified = data.get('manually_verified', True)
        
        if not speaker_label:
            return jsonify({'error': 'Speaker label is required'}), 400
        if not participant_id:
            return jsonify({'error': 'Participant ID is required'}), 400
        
        # Get transcription and verify ownership
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)
        
        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
            
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403
        
        # Get participant to ensure it exists and belongs to user
        from shared_quickscribe_py.cosmos import get_participant_handler
        participant_handler = get_participant_handler()
        
        participant = participant_handler.get_participant(current_user.id, participant_id)
        if not participant:
            return jsonify({'error': 'Participant not found'}), 404
            
        # No need to check ownership again since we're using the user_id as partition key
        
        # Get existing speaker mapping and merge the update
        existing_mapping = transcription.speaker_mapping or {}
        logger.info(f"Existing speaker mapping has {len(existing_mapping)} speakers")
        
        # Convert existing mapping to dict format if needed
        merged_mapping = {}
        for label, data in existing_mapping.items():
            if hasattr(data, 'model_dump'):
                # It's a Pydantic model
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                logger.warning(f"Unknown speaker data type for {label}: {type(data)}")
                merged_mapping[label] = {}
        
        # Merge into existing speaker data (preserve embedding, history, etc.)
        existing_speaker = merged_mapping.get(speaker_label, {})
        existing_speaker.update({
            'participantId': participant_id,
            'confidence': 1.0,
            'manuallyVerified': manually_verified,
            'identificationStatus': 'auto',
        })

        # Audit log
        _append_history(
            existing_speaker, action='manual_assigned', source='user_inline',
            participant_id=participant_id, display_name=participant.displayName,
        )

        # Update the specific speaker
        merged_mapping[speaker_label] = existing_speaker
        logger.info(f"Updated speaker {speaker_label}, merged mapping now has {len(merged_mapping)} speakers")

        # Update transcription with the merged speaker mapping
        update_transcription_speaker_data_with_participants(
            transcription_id,
            merged_mapping,
            reasoning="Manual assignment by user"
        )

        # Return enriched data for immediate frontend feedback
        enriched_speaker_data = {
            **speaker_data,
            'displayName': participant.displayName  # Enriched for response only
        }

        return jsonify({
            'success': True,
            'message': f'Speaker {speaker_label} assigned to {participant.displayName}',
            'speaker_data': enriched_speaker_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating single speaker for transcription {transcription_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Tag routes
@api_bp.route('/tags/get', methods=['GET'])
@require_auth
def get_user_tags():
    """Get all tags for the current user."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        user_handler = get_user_handler()
        tags = user_handler.get_user_tags(current_user.id)
        return jsonify([tag.model_dump() for tag in tags]), 200
    except Exception as e:
        logger.error(f"Error getting user tags: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/tags/create', methods=['POST'])
@require_auth
def create_tag():
    """Create a new tag for the current user."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON data required'}), 400
    
    name = data.get('name', '').strip()
    color = data.get('color', '').strip()
    
    # Validation
    if not name:
        return jsonify({'error': 'Tag name is required'}), 400
    if len(name) > 32:
        return jsonify({'error': 'Tag name must be 32 characters or less'}), 400
    if not color:
        return jsonify({'error': 'Tag color is required'}), 400
    if not validate_hex_color(color):
        return jsonify({'error': 'Color must be a valid hex code (e.g., #FF5733)'}), 400
    
    try:
        user_handler = get_user_handler()
        tag = user_handler.create_tag(current_user.id, name, color)
        if tag:
            return jsonify(tag.model_dump()), 201
        else:
            return jsonify({'error': 'Tag with this name already exists'}), 409
    except Exception as e:
        logger.error(f"Error creating tag: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/tags/update', methods=['POST'])
@require_auth
def update_tag():
    """Update an existing tag."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON data required'}), 400
    
    tag_id = data.get('tagId', '').strip()
    name = data.get('name', '').strip() if 'name' in data else None
    color = data.get('color', '').strip() if 'color' in data else None
    
    if not tag_id:
        return jsonify({'error': 'Tag ID is required'}), 400
    
    # Validation
    if name is not None:
        if not name:
            return jsonify({'error': 'Tag name cannot be empty'}), 400
        if len(name) > 32:
            return jsonify({'error': 'Tag name must be 32 characters or less'}), 400
    
    if color is not None:
        if not color:
            return jsonify({'error': 'Tag color cannot be empty'}), 400
        if not validate_hex_color(color):
            return jsonify({'error': 'Color must be a valid hex code (e.g., #FF5733)'}), 400
    
    if name is None and color is None:
        return jsonify({'error': 'At least one field (name or color) must be provided'}), 400
    
    try:
        user_handler = get_user_handler()
        tag = user_handler.update_tag(current_user.id, tag_id, name, color)
        if tag:
            return jsonify(tag.model_dump()), 200
        else:
            return jsonify({'error': 'Tag not found or name already exists'}), 404
    except Exception as e:
        logger.error(f"Error updating tag: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/tags/delete/<tag_id>', methods=['GET'])
@require_auth
def delete_tag(tag_id):
    """Delete a tag and remove it from all recordings."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        user_handler = get_user_handler()
        success = user_handler.delete_tag(current_user.id, tag_id)
        if success:
            return jsonify({'message': 'Tag deleted successfully'}), 200
        else:
            return jsonify({'error': 'Tag not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting tag: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/recordings/<recording_id>/add_tag/<tag_id>', methods=['GET'])
@require_auth
def add_tag_to_recording(recording_id, tag_id):
    """Add a single tag to a recording."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        # First verify the recording belongs to the user
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        if not recording or recording.user_id != current_user.id:
            return jsonify({'error': 'Recording not found'}), 404
        
        # Verify tag belongs to the user
        user_handler = get_user_handler()
        user_tags = user_handler.get_user_tags(current_user.id)
        valid_tag_ids = {tag.id for tag in user_tags}
        
        if tag_id not in valid_tag_ids:
            return jsonify({'error': 'Tag not found'}), 404
        
        # Add tag to recording
        updated_recording = recording_handler.add_tags_to_recording(recording_id, [tag_id])
        if updated_recording:
            return jsonify(updated_recording.model_dump()), 200
        else:
            return jsonify({'error': 'Failed to update recording'}), 500
    except Exception as e:
        logger.error(f"Error adding tag to recording: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/recordings/<recording_id>/remove_tag/<tag_id>', methods=['GET'])
@require_auth
def remove_tag_from_recording(recording_id, tag_id):
    """Remove a specific tag from a recording."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        # First verify the recording belongs to the user
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(recording_id)
        if not recording or recording.user_id != current_user.id:
            return jsonify({'error': 'Recording not found'}), 404

        # Remove tag from recording
        updated_recording = recording_handler.remove_tags_from_recording(recording_id, [tag_id])
        if updated_recording:
            return jsonify(updated_recording.model_dump()), 200
        else:
            return jsonify({'error': 'Failed to update recording'}), 500
    except Exception as e:
        logger.error(f"Error removing tag from recording: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Speaker Identification Review Endpoints
# =============================================================================

def _append_history(speaker_dict: dict, action: str, source: str,
                    participant_id: str = None, display_name: str = None,
                    similarity: float = None, candidates: list = None) -> None:
    """Append an entry to identificationHistory on a speaker mapping dict."""
    history = speaker_dict.get('identificationHistory') or []
    entry = {
        'timestamp': datetime.now(UTC).isoformat(),
        'action': action,
        'source': source,
    }
    if participant_id:
        entry['participantId'] = participant_id
    if display_name:
        entry['displayName'] = display_name
    if similarity is not None:
        entry['similarity'] = similarity
    if candidates:
        entry['candidatesPresented'] = candidates
    history.append(entry)
    speaker_dict['identificationHistory'] = history


@api_bp.route('/speaker-audit', methods=['GET'])
@require_auth
def get_speaker_audit_log():
    """
    Get the audit trail of all speaker identification actions across recordings.
    Returns flattened list of history entries enriched with recording/speaker context.

    Query params:
        limit: Max results (default 100)
        offset: Pagination offset (default 0)
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        limit = min(int(request.args.get('limit', 100)), 200)
        offset = int(request.args.get('offset', 0))

        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()

        # Get all recordings with completed speaker identification
        query = """
        SELECT * FROM c
        WHERE c.type = 'recording'
        AND c.user_id = @user_id
        AND c.transcription_status = 'completed'
        AND IS_DEFINED(c.speaker_identification_status)
        AND c.speaker_identification_status != null
        ORDER BY c.recorded_timestamp DESC
        """
        parameters = [{"name": "@user_id", "value": current_user.id}]

        items = list(recording_handler.container.query_items(
            query=query, parameters=parameters,
            enable_cross_partition_query=True
        ))

        # Flatten history entries across all recordings/speakers
        audit_entries = []
        for item in items:
            recording = Recording(**item)
            if not recording.transcription_id:
                continue

            transcription = transcription_handler.get_transcription(recording.transcription_id)
            if not transcription or not transcription.speaker_mapping:
                continue

            # Enrich for display names
            enriched = enrich_transcription_with_participants(transcription, current_user.id)
            enriched_mapping = enriched.get('speaker_mapping', {})

            for speaker_label, mapping_data in enriched_mapping.items():
                history = mapping_data.get('identificationHistory') or []
                current_status = mapping_data.get('identificationStatus')
                current_display = mapping_data.get('displayName')
                current_pid = mapping_data.get('participantId')

                for entry in history:
                    audit_entries.append({
                        'recordingId': recording.id,
                        'recordingTitle': recording.title or recording.original_filename,
                        'transcriptionId': transcription.id,
                        'speakerLabel': speaker_label,
                        'currentDisplayName': current_display,
                        'currentParticipantId': current_pid,
                        'currentStatus': current_status,
                        **entry,
                    })

        # Sort by timestamp descending (most recent first)
        audit_entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        total = len(audit_entries)
        audit_entries = audit_entries[offset:offset + limit]

        return jsonify({
            'status': 'success',
            'data': audit_entries,
            'total': total,
            'limit': limit,
            'offset': offset,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching speaker audit log: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/speaker-reviews', methods=['GET'])
@require_auth
def get_speaker_reviews():
    """
    Get recordings with pending speaker identification reviews.
    Returns recordings where speaker_identification_status is 'needs_review' or 'completed',
    and at least one speaker has identificationStatus of 'suggest' or 'unknown'.

    Query params:
        status: Filter by identificationStatus ('suggest', 'unknown', or 'all') - default 'all'
        limit: Max results (default 50)
        offset: Pagination offset (default 0)
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        status_filter = request.args.get('status', 'all')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()

        # Query recordings needing review
        query = """
        SELECT * FROM c
        WHERE c.type = 'recording'
        AND c.user_id = @user_id
        AND c.transcription_status = 'completed'
        AND c.speaker_identification_status IN ('needs_review', 'completed')
        ORDER BY c.recorded_timestamp DESC
        """
        parameters = [{"name": "@user_id", "value": current_user.id}]

        items = list(recording_handler.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        # Filter recordings that have suggest/unknown speakers
        review_items = []
        for item in items:
            recording = Recording(**item)
            if not recording.transcription_id:
                continue

            transcription = transcription_handler.get_transcription(recording.transcription_id)
            if not transcription or not transcription.speaker_mapping:
                continue

            # Count speakers needing review
            suggest_count = 0
            unknown_count = 0
            for label, mapping in transcription.speaker_mapping.items():
                if hasattr(mapping, 'model_dump'):
                    m = mapping.model_dump()
                elif isinstance(mapping, dict):
                    m = mapping
                else:
                    continue

                id_status = m.get('identificationStatus')
                if id_status == 'suggest':
                    suggest_count += 1
                elif id_status == 'unknown':
                    unknown_count += 1

            if status_filter == 'suggest' and suggest_count == 0:
                continue
            if status_filter == 'unknown' and unknown_count == 0:
                continue
            if status_filter == 'all' and suggest_count == 0 and unknown_count == 0:
                continue

            # Enrich transcription
            enriched = enrich_transcription_with_participants(transcription, current_user.id)

            review_items.append({
                'recording': recording.model_dump(),
                'transcription': enriched,
                'suggestCount': suggest_count,
                'unknownCount': unknown_count,
            })

        # Apply pagination
        total = len(review_items)
        review_items = review_items[offset:offset + limit]

        return jsonify({
            'status': 'success',
            'data': review_items,
            'total': total,
            'limit': limit,
            'offset': offset,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching speaker reviews: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/speaker/<speaker_label>/accept', methods=['POST'])
@require_auth
def accept_speaker_suggestion(transcription_id, speaker_label):
    """
    Accept a speaker identification suggestion.
    Copies suggestedParticipantId to participantId, sets manuallyVerified=True,
    and triggers profile update with stored embedding.

    Optionally accepts a body with { "participantId": "..." } to accept a
    specific candidate from topCandidates instead of the top suggestion.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)

        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403

        mapping = transcription.speaker_mapping or {}
        if speaker_label not in mapping:
            return jsonify({'error': f'Speaker {speaker_label} not found'}), 404

        speaker_data = mapping[speaker_label]
        if hasattr(speaker_data, 'model_dump'):
            speaker_dict = speaker_data.model_dump()
        elif isinstance(speaker_data, dict):
            speaker_dict = speaker_data.copy()
        else:
            return jsonify({'error': 'Invalid speaker data'}), 500

        # Check if a specific participantId was provided (quick-pick from candidates)
        body = request.get_json(silent=True) or {}
        participant_id = body.get('participantId') or speaker_dict.get('suggestedParticipantId')

        if not participant_id:
            return jsonify({'error': 'No suggestion to accept'}), 400

        # Verify participant exists
        participant_handler = get_participant_handler()
        participant = participant_handler.get_participant(current_user.id, participant_id)
        if not participant:
            return jsonify({'error': 'Participant not found'}), 404

        # Accept identity but do NOT train by default — user must explicitly approve training
        use_for_training = body.get('useForTraining', False)

        logger.info(
            f"SPEAKER ASSIGN: transcription={transcription_id}, speaker={speaker_label}, "
            f"participant={participant_id} ({participant.displayName}), "
            f"useForTraining={use_for_training}, similarity={speaker_dict.get('similarity')}"
        )

        # Audit log
        _append_history(
            speaker_dict, action='accepted', source='user_review_queue',
            participant_id=participant_id, display_name=participant.displayName,
            similarity=speaker_dict.get('similarity'),
            candidates=speaker_dict.get('topCandidates'),
        )

        # Update speaker mapping
        speaker_dict['participantId'] = participant_id
        speaker_dict['manuallyVerified'] = True
        speaker_dict['confidence'] = speaker_dict.get('similarity', 1.0)
        speaker_dict['identificationStatus'] = 'auto'
        speaker_dict['useForTraining'] = use_for_training
        speaker_dict.pop('suggestedParticipantId', None)
        speaker_dict.pop('suggestedDisplayName', None)

        # Update in transcription
        merged_mapping = {}
        for label, data in mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}
        merged_mapping[speaker_label] = speaker_dict

        update_transcription_speaker_data_with_participants(
            transcription_id, merged_mapping,
            reasoning="Accepted speaker identification suggestion"
        )

        # Only trigger profile update if user explicitly approved training
        if use_for_training:
            embedding = speaker_dict.get('embedding')
            if embedding:
                logger.info(
                    f"TRAINING UPDATE: participant={participant_id} ({participant.displayName}), "
                    f"embedding_dim={len(embedding)}, recording={transcription.recording_id}"
                )
                from speaker_profile_updater import update_profile_from_mapping
                result = update_profile_from_mapping(
                    current_user.id, participant_id, embedding,
                    recording_id=transcription.recording_id,
                    display_name=participant.displayName
                )
                logger.info(f"TRAINING UPDATE RESULT: success={result}")
            else:
                logger.warning(f"TRAINING SKIPPED: no embedding stored for {speaker_label}")
        else:
            logger.info(f"TRAINING NOT REQUESTED for {speaker_label}")

        # Check if recording still needs review
        _update_recording_review_status(transcription, merged_mapping)

        return jsonify({
            'success': True,
            'message': f'Speaker {speaker_label} accepted as {participant.displayName}',
            'useForTraining': use_for_training,
            'speaker_data': {
                **speaker_dict,
                'displayName': participant.displayName,
            }
        }), 200

    except Exception as e:
        logger.error(f"Error accepting suggestion for {transcription_id}/{speaker_label}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/speaker/<speaker_label>/reject', methods=['POST'])
@require_auth
def reject_speaker_suggestion(transcription_id, speaker_label):
    """
    Reject a speaker identification suggestion.
    Clears suggestedParticipantId and sets identificationStatus to 'unknown'.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)

        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403

        mapping = transcription.speaker_mapping or {}
        if speaker_label not in mapping:
            return jsonify({'error': f'Speaker {speaker_label} not found'}), 404

        speaker_data = mapping[speaker_label]
        if hasattr(speaker_data, 'model_dump'):
            speaker_dict = speaker_data.model_dump()
        elif isinstance(speaker_data, dict):
            speaker_dict = speaker_data.copy()
        else:
            return jsonify({'error': 'Invalid speaker data'}), 500

        # Audit log
        _append_history(
            speaker_dict, action='rejected', source='user_review_queue',
            participant_id=speaker_dict.get('suggestedParticipantId'),
            similarity=speaker_dict.get('similarity'),
            candidates=speaker_dict.get('topCandidates'),
        )

        # Clear suggestion, mark as unknown
        speaker_dict['identificationStatus'] = 'unknown'
        speaker_dict.pop('suggestedParticipantId', None)
        speaker_dict.pop('suggestedDisplayName', None)

        # Update in transcription
        merged_mapping = {}
        for label, data in mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}
        merged_mapping[speaker_label] = speaker_dict

        update_transcription_speaker_data_with_participants(
            transcription_id, merged_mapping,
            reasoning="Rejected speaker identification suggestion"
        )

        return jsonify({
            'success': True,
            'message': f'Suggestion for {speaker_label} rejected',
        }), 200

    except Exception as e:
        logger.error(f"Error rejecting suggestion for {transcription_id}/{speaker_label}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/speaker/<speaker_label>/dismiss', methods=['POST'])
@require_auth
def dismiss_speaker(transcription_id, speaker_label):
    """
    Dismiss a speaker — mark as "don't care" so the worker never re-analyzes them.
    Sets identificationStatus to 'dismissed'.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)

        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403

        mapping = transcription.speaker_mapping or {}
        if speaker_label not in mapping:
            return jsonify({'error': f'Speaker {speaker_label} not found'}), 404

        speaker_data = mapping[speaker_label]
        if hasattr(speaker_data, 'model_dump'):
            speaker_dict = speaker_data.model_dump()
        elif isinstance(speaker_data, dict):
            speaker_dict = speaker_data.copy()
        else:
            return jsonify({'error': 'Invalid speaker data'}), 500

        # Audit log
        _append_history(
            speaker_dict, action='dismissed', source='user_review_queue',
            similarity=speaker_dict.get('similarity'),
            candidates=speaker_dict.get('topCandidates'),
        )

        speaker_dict['identificationStatus'] = 'dismissed'
        speaker_dict.pop('suggestedParticipantId', None)
        speaker_dict.pop('suggestedDisplayName', None)

        # Update in transcription
        merged_mapping = {}
        for label, data in mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}
        merged_mapping[speaker_label] = speaker_dict

        update_transcription_speaker_data_with_participants(
            transcription_id, merged_mapping,
            reasoning="Speaker dismissed by user"
        )

        # Check if recording still needs review
        _update_recording_review_status(transcription, merged_mapping)

        return jsonify({
            'success': True,
            'message': f'Speaker {speaker_label} dismissed',
        }), 200

    except Exception as e:
        logger.error(f"Error dismissing speaker {transcription_id}/{speaker_label}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/speaker/<speaker_label>/reassign', methods=['POST'])
@require_auth
def reassign_speaker(transcription_id, speaker_label):
    """
    Reassign a speaker from the audit view. Creates a 'reassigned' audit entry
    and updates the speaker mapping to the new participant.
    Expects: { "participantId": "...", "useForTraining": false }
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        body = request.get_json(silent=True) or {}
        new_participant_id = body.get('participantId')
        use_for_training = body.get('useForTraining', False)

        if not new_participant_id:
            return jsonify({'error': 'participantId is required'}), 400

        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)

        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403

        mapping = transcription.speaker_mapping or {}
        if speaker_label not in mapping:
            return jsonify({'error': f'Speaker {speaker_label} not found'}), 404

        speaker_data = mapping[speaker_label]
        if hasattr(speaker_data, 'model_dump'):
            speaker_dict = speaker_data.model_dump()
        elif isinstance(speaker_data, dict):
            speaker_dict = speaker_data.copy()
        else:
            return jsonify({'error': 'Invalid speaker data'}), 500

        # Verify new participant exists
        participant_handler = get_participant_handler()
        participant = participant_handler.get_participant(current_user.id, new_participant_id)
        if not participant:
            return jsonify({'error': 'Participant not found'}), 404

        old_participant_id = speaker_dict.get('participantId')

        # Audit log — record the reassignment
        _append_history(
            speaker_dict, action='reassigned', source='user_audit_view',
            participant_id=new_participant_id, display_name=participant.displayName,
            similarity=speaker_dict.get('similarity'),
            candidates=speaker_dict.get('topCandidates'),
        )

        # Update speaker mapping
        speaker_dict['participantId'] = new_participant_id
        speaker_dict['manuallyVerified'] = True
        speaker_dict['confidence'] = 1.0
        speaker_dict['identificationStatus'] = 'auto'
        speaker_dict['useForTraining'] = use_for_training
        speaker_dict.pop('suggestedParticipantId', None)
        speaker_dict.pop('suggestedDisplayName', None)

        # Update in transcription
        merged_mapping = {}
        for label, data in mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}
        merged_mapping[speaker_label] = speaker_dict

        update_transcription_speaker_data_with_participants(
            transcription_id, merged_mapping,
            reasoning="Reassigned from audit view"
        )

        # Trigger profile update if training approved
        if use_for_training:
            embedding = speaker_dict.get('embedding')
            if embedding:
                from speaker_profile_updater import update_profile_from_mapping
                update_profile_from_mapping(
                    current_user.id, new_participant_id, embedding,
                    recording_id=transcription.recording_id,
                    display_name=participant.displayName
                )

        return jsonify({
            'success': True,
            'message': f'Speaker {speaker_label} reassigned to {participant.displayName}',
            'previousParticipantId': old_participant_id,
        }), 200

    except Exception as e:
        logger.error(f"Error reassigning speaker {transcription_id}/{speaker_label}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/speaker/<speaker_label>/training', methods=['POST'])
@require_auth
def toggle_speaker_training(transcription_id, speaker_label):
    """
    Toggle whether a speaker's embedding is approved for voice profile training.
    Expects: { "useForTraining": true/false }

    When enabling training, triggers the profile update with the stored embedding.
    When disabling, just sets the flag (does not remove from existing profile).
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        body = request.get_json(silent=True) or {}
        use_for_training = body.get('useForTraining')
        if use_for_training is None:
            return jsonify({'error': 'useForTraining is required'}), 400

        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)

        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403

        mapping = transcription.speaker_mapping or {}
        if speaker_label not in mapping:
            return jsonify({'error': f'Speaker {speaker_label} not found'}), 404

        speaker_data = mapping[speaker_label]
        if hasattr(speaker_data, 'model_dump'):
            speaker_dict = speaker_data.model_dump()
        elif isinstance(speaker_data, dict):
            speaker_dict = speaker_data.copy()
        else:
            return jsonify({'error': 'Invalid speaker data'}), 500

        action = 'training_approved' if use_for_training else 'training_revoked'
        logger.info(
            f"TRAINING TOGGLE: transcription={transcription_id}, speaker={speaker_label}, "
            f"participant={speaker_dict.get('participantId')}, useForTraining={use_for_training}"
        )
        _append_history(
            speaker_dict, action=action, source='user_review_queue',
            participant_id=speaker_dict.get('participantId'),
        )

        speaker_dict['useForTraining'] = use_for_training

        # Update in transcription
        merged_mapping = {}
        for label, data in mapping.items():
            if hasattr(data, 'model_dump'):
                merged_mapping[label] = data.model_dump()
            elif isinstance(data, dict):
                merged_mapping[label] = data.copy()
            else:
                merged_mapping[label] = {}
        merged_mapping[speaker_label] = speaker_dict

        update_transcription_speaker_data_with_participants(
            transcription_id, merged_mapping,
            reasoning="Updated training approval"
        )

        # If enabling training, trigger profile update
        if use_for_training:
            participant_id = speaker_dict.get('participantId')
            embedding = speaker_dict.get('embedding')
            if participant_id and embedding:
                participant_handler = get_participant_handler()
                participant = participant_handler.get_participant(current_user.id, participant_id)
                display_name = participant.displayName if participant else ""

                logger.info(
                    f"TRAINING UPDATE (toggle): participant={participant_id} ({display_name}), "
                    f"embedding_dim={len(embedding)}, recording={transcription.recording_id}"
                )
                from speaker_profile_updater import update_profile_from_mapping
                result = update_profile_from_mapping(
                    current_user.id, participant_id, embedding,
                    recording_id=transcription.recording_id,
                    display_name=display_name
                )
                logger.info(f"TRAINING UPDATE RESULT (toggle): success={result}")
            else:
                logger.warning(
                    f"TRAINING SKIPPED (toggle): participant={participant_id}, "
                    f"has_embedding={embedding is not None}"
                )
        else:
            logger.info(f"TRAINING REVOKED: speaker={speaker_label}")

        action = "approved for" if use_for_training else "excluded from"
        return jsonify({
            'success': True,
            'message': f'Speaker {speaker_label} {action} voice training',
            'useForTraining': use_for_training,
        }), 200

    except Exception as e:
        logger.error(f"Error toggling training for {transcription_id}/{speaker_label}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/transcription/<transcription_id>/reidentify', methods=['POST'])
@require_auth
def reidentify_speakers(transcription_id):
    """
    Re-trigger speaker identification for a transcription.
    Sets speaker_identification_status to 'not_started' so the worker picks it up.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        transcription_handler = get_transcription_handler()
        transcription = transcription_handler.get_transcription(transcription_id)

        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        if transcription.user_id != current_user.id:
            return jsonify({'error': 'Transcription does not belong to current user'}), 403

        # Clear auto/suggest results (keep manually verified)
        if transcription.speaker_mapping:
            mapping = {}
            for label, data in transcription.speaker_mapping.items():
                if hasattr(data, 'model_dump'):
                    d = data.model_dump()
                elif isinstance(data, dict):
                    d = data.copy()
                else:
                    d = {}

                if d.get('manuallyVerified') or d.get('identificationStatus') == 'dismissed':
                    mapping[label] = d
                else:
                    # Keep only basic fields, clear identification data
                    mapping[label] = {
                        k: v for k, v in d.items()
                        if k not in ('identificationStatus', 'similarity', 'suggestedParticipantId',
                                     'suggestedDisplayName', 'topCandidates', 'identifiedAt',
                                     'embedding', 'participantId', 'confidence')
                    }

            transcription.speaker_mapping = mapping
            transcription_handler.update_transcription(transcription)

        # Reset recording status
        recording_handler = get_recording_handler()
        recording = recording_handler.get_recording(transcription.recording_id)
        if recording:
            recording.speaker_identification_status = 'not_started'
            recording_handler.update_recording(recording)

        return jsonify({
            'success': True,
            'message': 'Speaker re-identification queued',
        }), 200

    except Exception as e:
        logger.error(f"Error re-identifying speakers for {transcription_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/speaker-profiles/rebuild', methods=['POST'])
@require_auth
def rebuild_speaker_profiles():
    """
    Rebuild all speaker profiles from verified mappings.
    Useful after corrections or when profiles need recalibration.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        from speaker_profile_updater import rebuild_all_profiles
        transcription_handler = get_transcription_handler()
        recording_handler = get_recording_handler()

        stats = rebuild_all_profiles(
            current_user.id,
            transcription_handler,
            recording_handler
        )

        return jsonify({
            'success': True,
            'message': f'Rebuilt {stats["profiles_rebuilt"]} profiles from {stats["embeddings_processed"]} embeddings',
            'stats': stats,
        }), 200

    except Exception as e:
        logger.error(f"Error rebuilding speaker profiles: {e}")
        return jsonify({'error': str(e)}), 500


def _update_recording_review_status(transcription: Transcription, mapping: dict) -> None:
    """
    Check if a recording still needs review after an accept/reject action.
    Updates speaker_identification_status to 'completed' if no more pending reviews.
    """
    try:
        has_pending = False
        for label, data in mapping.items():
            if isinstance(data, dict):
                status = data.get('identificationStatus')
            elif hasattr(data, 'identificationStatus'):
                status = data.identificationStatus
            else:
                continue

            if status in ('suggest', 'unknown'):
                has_pending = True
                break

        if not has_pending:
            recording_handler = get_recording_handler()
            recording = recording_handler.get_recording(transcription.recording_id)
            if recording and recording.speaker_identification_status == 'needs_review':
                recording.speaker_identification_status = 'completed'
                recording_handler.update_recording(recording)

    except Exception as e:
        logger.error(f"Error updating recording review status: {e}")
