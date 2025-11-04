# local_routes.py
from flask import Blueprint, request, jsonify
from shared_quickscribe_py.cosmos import get_user_handler, get_recording_handler, get_transcription_handler
from user_util import get_current_user
from shared_quickscribe_py.cosmos import Recording as RecordingModel
from datetime import datetime, UTC
import uuid
import os

from logging_config import get_logger
logger = get_logger('local_routes')

local_bp = Blueprint('local', __name__)

@local_bp.route('/users', methods=['GET'])
def get_local_test_users():
    """Get list of test users for local development"""
    if not os.getenv('LOCAL_AUTH_ENABLED'):
        return jsonify({'error': 'Local auth not enabled'}), 403
        
    try:
        user_handler = get_user_handler()
        test_users = user_handler.get_test_users()
        return jsonify(test_users), 200
    except Exception as e:
        logger.error(f"Error getting test users: {e}")
        return jsonify({'error': str(e)}), 500

@local_bp.route('/login', methods=['POST'])
def local_login():
    """Set current user session for local development"""
    if not os.getenv('LOCAL_AUTH_ENABLED'):
        return jsonify({'error': 'Local auth not enabled'}), 403
        
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id required'}), 400
            
        user_id = data['user_id']
        
        # Verify user exists and is a test user
        user_handler = get_user_handler()
        user = user_handler.get_user(user_id)
        if not user or not user.is_test_user:
            return jsonify({'error': 'Invalid test user'}), 400
            
        # Store user ID in session
        from flask import session
        session['local_user_id'] = user_id
        
        return jsonify({'message': 'Logged in successfully', 'user': {'id': user.id, 'name': user.name}}), 200
        
    except Exception as e:
        logger.error(f"Error during local login: {e}")
        return jsonify({'error': str(e)}), 500

@local_bp.route('/reset-user/<user_id>', methods=['POST'])
def reset_test_user(user_id):
    """Reset all data for a test user"""
    if not os.getenv('LOCAL_AUTH_ENABLED'):
        return jsonify({'error': 'Local auth not enabled'}), 403
        
    try:
        # Verify user exists and is a test user
        user_handler = get_user_handler()
        user = user_handler.get_user(user_id)
        if not user or not user.is_test_user:
            return jsonify({'error': 'Invalid test user'}), 400
            
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()
        
        # Get all user's recordings
        recordings = recording_handler.get_user_recordings(user_id)
        
        # Delete blob files from Azure Storage
        from blob_util import delete_recording_blob
        for recording in recordings:
            try:
                delete_recording_blob(recording.unique_filename)
            except Exception as blob_error:
                logger.warning(f"Failed to delete blob {recording.unique_filename}: {blob_error}")
        
        # Delete all recordings from database
        for recording in recordings:
            recording_handler.delete_recording(recording.id)
        
        # Get and delete all transcriptions
        transcriptions = transcription_handler.get_user_transcriptions(user_id)
        for transcription in transcriptions:
            transcription_handler.delete_transcription(transcription.id)
        
        # Reset user's plaud settings
        if user:
            user.plaudSettings = None
            user_handler.save_user(user)
        
        logger.info(f"Reset test user {user_id}: deleted {len(recordings)} recordings and {len(transcriptions)} transcriptions")
        
        return jsonify({
            'message': f'User data reset successfully',
            'deleted_recordings': len(recordings),
            'deleted_transcriptions': len(transcriptions)
        }), 200
        
    except Exception as e:
        logger.error(f"Error resetting test user: {e}")
        return jsonify({'error': str(e)}), 500

@local_bp.route('/create_test_user', methods=['POST'])
def create_test_user():
    """Create a new test user for local development"""
    if not os.getenv('LOCAL_AUTH_ENABLED'):
        return jsonify({'error': 'Local auth not enabled'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Create test user
        user_handler = get_user_handler()
        user_id = f"test-user-{str(uuid.uuid4())}"
        user_item = {
            "id": user_id,
            "email": email,
            "name": name,
            "role": "user",
            "created_at": datetime.now(UTC).isoformat(),
            "last_login": None,
            "partitionKey": "user",
            "is_test_user": True  # Mark as test user
        }
        
        created_user = user_handler.container.create_item(body=user_item)
        
        logger.info(f"Created test user {user_id}: {name} ({email})")
        
        return jsonify({
            'message': 'Test user created successfully',
            'user': {
                'id': user_id,
                'name': name,
                'email': email,
                'is_test_user': True
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        return jsonify({'error': str(e)}), 500

@local_bp.route('/delete_test_user/<user_id>', methods=['POST'])
def delete_test_user(user_id):
    """Delete a test user and all associated data"""
    if not os.getenv('LOCAL_AUTH_ENABLED'):
        return jsonify({'error': 'Local auth not enabled'}), 403
        
    try:
        # Verify user exists and is a test user
        user_handler = get_user_handler()
        user = user_handler.get_user(user_id)
        if not user or not user.is_test_user:
            return jsonify({'error': 'Invalid test user or user not found'}), 400
            
        recording_handler = get_recording_handler()
        transcription_handler = get_transcription_handler()
        
        # Get all user's recordings
        recordings = recording_handler.get_user_recordings(user_id)
        
        # Delete blob files from Azure Storage (only for non-dummy recordings)
        from blob_util import delete_recording_blob
        blob_delete_count = 0
        for recording in recordings:
            if not recording.is_dummy_recording:  # Only delete real blobs
                try:
                    delete_recording_blob(recording.unique_filename)
                    blob_delete_count += 1
                except Exception as blob_error:
                    logger.warning(f"Failed to delete blob {recording.unique_filename}: {blob_error}")
        
        # Delete all recordings from database
        for recording in recordings:
            recording_handler.delete_recording(recording.id)
        
        # Get and delete all transcriptions
        transcriptions = transcription_handler.get_user_transcriptions(user_id)
        for transcription in transcriptions:
            transcription_handler.delete_transcription(transcription.id)
        
        # Finally, delete the user
        user_handler.delete_user(user_id)
        
        logger.info(f"Deleted test user {user_id}: {len(recordings)} recordings, {len(transcriptions)} transcriptions, {blob_delete_count} blobs")
        
        return jsonify({
            'message': f'Test user deleted successfully',
            'deleted_recordings': len(recordings),
            'deleted_transcriptions': len(transcriptions),
            'deleted_blobs': blob_delete_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting test user: {e}")
        return jsonify({'error': str(e)}), 500

@local_bp.route('/create_dummy_recording', methods=['POST'])
def create_dummy_recording():
    """Create a dummy recording for testing purposes"""
    if not os.getenv('LOCAL_AUTH_ENABLED'):
        return jsonify({'error': 'Local auth not enabled'}), 403
    
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400
        
        title = data.get('title', '').strip()
        original_filename = data.get('original_filename', '').strip()
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not original_filename:
            return jsonify({'error': 'Original filename is required'}), 400
        
        # Create dummy recording
        recording_handler = get_recording_handler()
        recording_id = f"dummy-{str(uuid.uuid4())}"
        unique_filename = f"dummy-{recording_id}.mp3"
        
        recording_data = {
            "id": recording_id,
            "user_id": current_user.id,
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "title": title,
            "recorded_timestamp": datetime.now(UTC).isoformat(),
            "upload_timestamp": datetime.now(UTC).isoformat(),
            "source": "upload",
            "partitionKey": "recording",
            "is_dummy_recording": True,
            "transcoding_status": "completed",  # Skip transcoding for dummy
            "transcription_status": "not_started"
        }
        
        # Create recording in database
        recording = RecordingModel(**recording_data)
        created_recording = recording_handler.container.create_item(body=recording.model_dump())
        
        logger.info(f"Created dummy recording {recording_id} for user {current_user.id}")
        
        return jsonify({
            'message': 'Dummy recording created successfully',
            'recording': recording.model_dump()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating dummy recording: {e}")
        return jsonify({'error': str(e)}), 500