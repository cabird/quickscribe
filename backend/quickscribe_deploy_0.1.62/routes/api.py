# api.py
from flask import Blueprint, request, jsonify, url_for
from db_handlers.handler_factory import get_user_handler, get_recording_handler, get_transcription_handler
from user_util import get_current_user
from db_handlers.models import User, Recording, Transcription, TranscodingStatus, TranscriptionStatus, Tag
from util import update_diarized_transcript, get_recording_duration_in_seconds
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

@api_bp.route('/get_api_version', methods=['GET'])
def get_api_version():
    return jsonify({'version': API_VERSION}), 200

# Route to get a user by ID
@api_bp.route('/user/<user_id>', methods=['GET'])
def get_user_by_id(user_id):
    user_handler = get_user_handler()
    user = user_handler.get_user(user_id)
    if user:
        return jsonify(user.model_dump()), 200
    return jsonify({'error': 'User not found'}), 404

# Route to list all users
@api_bp.route('/users', methods=['GET'])
def list_users():
    user_handler = get_user_handler()
    users = user_handler.get_all_users()
    return jsonify([user.model_dump() for user in users]), 200

# Route to get a recording by ID
@api_bp.route('/recording/<recording_id>', methods=['GET'])
def get_recording_by_id(recording_id):
    recording_handler = get_recording_handler()
    recording = recording_handler.get_recording(recording_id)
    if recording:
        return jsonify(recording.model_dump()), 200
    return jsonify({'error': 'Recording not found'}), 404

# Route to list all recordings
@api_bp.route('/recordings', methods=['GET'])
def list_recordings():
    recording_handler = get_recording_handler()
    user = get_current_user()
    recordings = recording_handler.get_all_recordings(user.id)

    logger.info(f"list_recordings: found {len(recordings)} recordings for user {user.id}")
    recording_list = [recording.model_dump() for recording in recordings]
    logger.info(f"list_recordings done")

    return jsonify(recording_list), 200

# Route to get a transcription by ID
@api_bp.route('/transcription/<transcription_id>', methods=['GET'])
def get_transcription_by_id(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription:
        return jsonify(transcription.model_dump()), 200
    return jsonify({'error': 'Transcription not found'}), 404

# Route to get all transcriptions for a user
@api_bp.route('/user/<user_id>/transcriptions', methods=['GET'])
def get_user_transcriptions(user_id):
    transcription_handler = get_transcription_handler()
    transcriptions = transcription_handler.get_user_transcriptions(user_id)
    return jsonify([transcription.model_dump() for transcription in transcriptions]), 200

# Route to get all recordings for a user
@api_bp.route('/user/<user_id>/recordings', methods=['GET'])
def get_user_recordings(user_id):
    recording_handler = get_recording_handler()
    recordings = recording_handler.get_user_recordings(user_id)
    return jsonify([recording.model_dump() for recording in recordings]), 200

# Route to get users by a list of IDs
@api_bp.route('/users', methods=['POST'])
def get_users_by_ids():
    user_handler = get_user_handler()
    ids = request.json.get('ids', [])
    users = [user_handler.get_user(user_id) for user_id in ids]
    return jsonify([user.model_dump() for user in users if user]), 200

# Route to get recordings by a list of IDs
@api_bp.route('/recordings', methods=['POST'])
def get_recordings_by_ids():
    recording_handler = get_recording_handler()
    ids = request.json.get('ids', [])
    recordings = [recording_handler.get_recording(recording_id) for recording_id in ids]
    return jsonify([recording.model_dump() for recording in recordings if recording]), 200

# Route to get transcriptions by a list of IDs
@api_bp.route('/transcriptions', methods=['POST'])
def get_transcriptions_by_ids():
    transcription_handler = get_transcription_handler()
    ids = request.json.get('ids', [])
    transcriptions = [transcription_handler.get_transcription(transcription_id) for transcription_id in ids]
    return jsonify([transcription.model_dump() for transcription in transcriptions if transcription]), 200

# Route to delete items by ID
@api_bp.route('/delete_user/<user_id>', methods=['GET'])
def delete_user(user_id):
    user_handler = get_user_handler()
    user_handler.delete_user(user_id)
    return jsonify({'message': 'User deleted successfully'}), 200

@api_bp.route('/delete_recording/<recording_id>', methods=['GET'])
def delete_recording(recording_id):
    recording_handler = get_recording_handler()
    recording_handler.delete_recording(recording_id)
    return jsonify({'message': 'Recording deleted successfully'}), 200

@api_bp.route('/delete_transcription/<transcription_id>', methods=['GET'])
def delete_transcription(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription_handler.delete_transcription(transcription_id)
    return jsonify({'message': 'Transcription deleted successfully'}), 200

# Route to update items by ID
@api_bp.route('/user/<user_id>', methods=['PUT'])
def update_user(user_id):
    user_handler = get_user_handler()
    user_data = request.json
    updated_user = user_handler.update_user(user_id, **user_data)
    if updated_user:
        return jsonify(updated_user.model_dump()), 200
    return jsonify({'error': 'User not found'}), 404

@api_bp.route('/recording/<recording_id>', methods=['PUT'])
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


@api_bp.route('/update_speaker_labels/<transcription_id>', methods=['POST'])
def update_speaker_labels(transcription_id):
    logger.info(f"update_speaker_labels: transcription_id {transcription_id}")
    #output the request json
    logger.info(f"update_speaker_labels: request json {request.json}")
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        speaker_labels = request.json
        # TODO - update the speaker labels... do we need them?
        updated_transcript = update_diarized_transcript(transcription.diarized_transcript, speaker_labels)
        transcription.diarized_transcript = updated_transcript

        #transcription.speaker_mapping = speaker_labels
        logger.info(f"update_speaker_labels: updated_transcript")
        transcription_handler.update_transcription(transcription)
        return jsonify({'message': 'Speaker labels updated successfully'}), 200
    return jsonify({'error': 'Transcription not found or does not have a diarized transcript'}), 404



#support upload from iphone share context menu
@api_bp.route("/upload_from_ios_share", methods=['POST'])
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


# Tag routes
@api_bp.route('/tags/get', methods=['GET'])
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
