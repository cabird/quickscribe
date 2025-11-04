# Add these imports to the top of routes/api.py
from azure.storage.queue import QueueClient
from shared_quickscribe_py.cosmos import create_user_handler, get_sync_progress_handler, get_user_handler
from datetime import datetime, UTC
import uuid
import json
import os
from flask import Blueprint, jsonify, request, url_for
from user_util import get_current_user
from config import config
from api_version import API_VERSION
from shared_quickscribe_py.cosmos import get_recording_handler
from blob_util import generate_recording_sas_url
from logging_config import get_logger
# Initialize logger
logger = get_logger('plaud', API_VERSION)
logger.info(f"Starting Plaud API ({API_VERSION})")

plaud_bp = Blueprint('plaud', __name__)

@plaud_bp.route('/user/plaud_settings', methods=['GET'])
def get_plaud_settings():
    """Get current user's Plaud settings (without exposing bearer token)"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not authenticated or not found'}), 401
        
           
        # Return settings without bearer token for security
        plaud_settings = user.plaudSettings or {}
        safe_settings = {
            'hasToken': bool(plaud_settings.get('bearerToken')),
            'lastSyncTimestamp': plaud_settings.get('lastSyncTimestamp'),
            'enableSync': plaud_settings.get('enableSync', False)
        }
        
        return jsonify(safe_settings), 200
        
    except Exception as e:
        logger.error(f"Error getting Plaud settings: {e}")
        return jsonify({'error': str(e)}), 500

@plaud_bp.route('/user/plaud_settings', methods=['PUT'])
def update_plaud_settings():
    """Update current user's Plaud settings"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not authenticated or not found'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Get current settings or create new ones
        current_settings = user.plaudSettings or {}
        
        # Update settings - only update provided fields
        if 'bearerToken' in data:
            bearer_token = data['bearerToken'].strip()
            if not bearer_token:
                return jsonify({'error': 'Bearer token cannot be empty'}), 400
            current_settings['bearerToken'] = bearer_token
            
        if 'enableSync' in data:
            current_settings['enableSync'] = bool(data['enableSync'])
            
        if 'lastSyncTimestamp' in data:
            # Validate timestamp format
            try:
                if data['lastSyncTimestamp']:
                    datetime.fromisoformat(data['lastSyncTimestamp'])
                current_settings['lastSyncTimestamp'] = data['lastSyncTimestamp']
            except ValueError:
                return jsonify({'error': 'Invalid timestamp format'}), 400
        
        # Update user record with Pydantic model
        from shared_quickscribe_py.cosmos import PlaudSettings
        user.plaudSettings = PlaudSettings(**current_settings)

        user_handler = create_user_handler()
        updated_user = user_handler.save_user(user)
        
        if not updated_user:
            return jsonify({'error': 'Failed to update user settings'}), 500
            
        return jsonify({'message': 'Plaud settings updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating Plaud settings: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Plaud Sync Operations
# ============================================================================

@plaud_bp.route('/sync/start', methods=['POST'])
def start_plaud_sync():
    """Trigger a Plaud sync operation"""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'User not authenticated or not found'}), 401
            
        if not user.plaudSettings:
            return jsonify({'error': 'Plaud settings not configured'}), 400
            
        plaud_settings = user.plaudSettings
        if not plaud_settings.bearerToken:
            return jsonify({'error': 'Plaud bearer token not configured'}), 400
            
        if not plaud_settings.enableSync:
            return jsonify({'error': 'Plaud sync is disabled'}), 400
        
        # Check if sync is already active
        if plaud_settings.activeSyncToken and plaud_settings.activeSyncStarted:
            # Check if sync hasn't expired
            elapsed = datetime.now(UTC) - plaud_settings.activeSyncStarted
            if elapsed.total_seconds() <= 3600:  # 1 hour timeout
                return jsonify({
                    'error': 'Sync already in progress',
                    'active_sync_token': plaud_settings.activeSyncToken,
                    'sync_started': plaud_settings.activeSyncStarted.isoformat() if plaud_settings.activeSyncStarted else None
                }), 409
            else:
                # Clear expired sync token
                logger.info(f"Clearing expired sync token for user {user.id}")
                plaud_settings.activeSyncToken = None
                plaud_settings.activeSyncStarted = None
            
        # Get request parameters
        request_data = request.get_json() or {}
        dry_run = request_data.get('dry_run', False)
        
        # Generate sync token for this operation
        sync_token = str(uuid.uuid4())
        
        # Prepare callback URLs
        backend_base_url = os.getenv('BACKEND_BASE_URL')
        if backend_base_url:
            callback_url = f"{backend_base_url.rstrip('/')}/plaud/plaud_callback"
        else:
            callback_url = url_for('plaud.plaud_callback', _external=True)
        
        callbacks = [{
            'url': callback_url,
            'token': sync_token
        }]
        
        # Get list of previously processed Plaud IDs
        recording_handler = get_recording_handler()
        processed_ids = recording_handler.get_user_plaud_ids(user.id)
        logger.info(f"Found {len(processed_ids)} previously synced Plaud recordings for user {user.id}")
        
        # Prepare sync message for queue
        # Ensure lastSyncTimestamp is JSON serializable (handle both datetime and string)
        last_sync_timestamp = plaud_settings.lastSyncTimestamp
        if last_sync_timestamp is not None:
            if isinstance(last_sync_timestamp, datetime):
                last_sync_timestamp = last_sync_timestamp.isoformat()
            elif isinstance(last_sync_timestamp, str):
                # Already a string, keep as-is
                pass
        
        sync_message = {
            'action': 'plaud_sync',
            'user_id': user.id,
            'bearerToken': plaud_settings.bearerToken, 
            #what happens to recordings that didn't sync the last time and are before lastSyncTimestamp?
            'lastSyncTimestamp': last_sync_timestamp, 
            'processedPlaudIds': processed_ids,
            'callbacks': callbacks,
            'callback_token': sync_token,
            'dry_run': dry_run
        }
        
        # Send message to transcoding queue
        try:
            queue_client = QueueClient.from_connection_string(
                config.AZURE_STORAGE_CONNECTION_STRING, 
                queue_name=config.TRANSCODING_QUEUE_NAME
            )
            queue_client.send_message(json.dumps(sync_message))
            logger.info(f"Sent Plaud sync message to queue {config.TRANSCODING_QUEUE_NAME} for user {user.id}")
            
        except Exception as queue_error:
            logger.error(f"Failed to send Plaud sync message to queue: {queue_error}")
            return jsonify({'error': 'Failed to queue sync operation'}), 500
        
        # Update user's sync status with active sync token
        user_handler = create_user_handler()
        # Use clean model API - set fields directly on the datetime object
        user.plaudSettings.activeSyncToken = sync_token
        user.plaudSettings.activeSyncStarted = datetime.now(UTC)
        user_handler.save_user(user)
        logger.info(f"Stored sync token for user {user.id}")
        
        # Create initial sync progress record
        try:
            sync_progress_handler = get_sync_progress_handler()
            sync_progress_handler.create_progress(
                sync_token=sync_token,
                user_id=user.id,
                status='queued',
                current_step='Sync request queued, waiting for processing...'
            )
            logger.info(f"Created sync progress record for token {sync_token}")
        except Exception as progress_error:
            logger.error(f"Failed to create sync progress record: {progress_error}")
            # Don't fail the whole operation if progress tracking fails
        
        return jsonify({
            'message': 'Plaud sync operation started',
            'sync_token': sync_token,
            'dry_run': dry_run
        }), 200
        
    except Exception as e:
        logger.error(f"Error starting Plaud sync: {e}")
        return jsonify({'error': str(e)}), 500

@plaud_bp.route('/sync/progress/<sync_token>', methods=['GET'])
def get_sync_progress(sync_token):
    """Get detailed sync progress for a specific sync token"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get sync progress
        sync_progress_handler = get_sync_progress_handler()
        progress = sync_progress_handler.get_progress(sync_token, current_user.id)
        
        if not progress:
            return jsonify({'error': 'Sync progress not found'}), 404
        
        # Convert to dict for JSON response
        progress_dict = progress.model_dump()
        
        # Calculate progress percentage if total is known
        if progress.totalRecordings and progress.totalRecordings > 0:
            completed = progress.processedRecordings + progress.failedRecordings
            progress_dict['progressPercentage'] = min(100, (completed / progress.totalRecordings) * 100)
        else:
            progress_dict['progressPercentage'] = None
        
        return jsonify(progress_dict), 200
        
    except Exception as e:
        logger.error(f"Error getting sync progress: {e}")
        return jsonify({'error': str(e)}), 500

@plaud_bp.route('/plaud_sync/status/<user_id>', methods=['GET'])
def get_plaud_sync_status(user_id):
    """Get Plaud sync status for a user"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not authenticated'}), 401
            
        # Only allow users to check their own status
        if current_user.id != user_id:
            return jsonify({'error': 'Access denied'}), 403
                   
        if not current_user.plaudSettings:
            return jsonify({'error': 'Plaud settings not configured'}), 400
        
        # Check if sync is currently active
        sync_active = False
        active_sync_token = None
        if current_user.plaudSettings.activeSyncToken and current_user.plaudSettings.activeSyncStarted:
            # Check if sync hasn't expired
            elapsed = datetime.now(UTC) - current_user.plaudSettings.activeSyncStarted
            sync_active = elapsed.total_seconds() <= 3600  # 1 hour timeout
            if sync_active:
                active_sync_token = current_user.plaudSettings.activeSyncToken
        
        status = {
            'hasSettings': bool(current_user.plaudSettings.bearerToken),
            'syncEnabled': current_user.plaudSettings.enableSync,
            'lastSyncTimestamp': current_user.plaudSettings.lastSyncTimestamp,
            'currentSyncActive': sync_active,
            'activeSyncToken': active_sync_token
        }
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Error getting Plaud sync status: {e}")
        return jsonify({'error': str(e)}), 500

@plaud_bp.route('/sync/check_active', methods=['GET'])
def check_active_sync():
    """Check if current user has an active sync and return its status"""
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Check if user has an active sync token
        if (current_user.plaudSettings and 
            current_user.plaudSettings.activeSyncToken):
            
            sync_token = current_user.plaudSettings.activeSyncToken
            
            # Try to get the progress for this sync
            sync_progress_handler = get_sync_progress_handler()
            progress = sync_progress_handler.get_progress(sync_token, current_user.id)
            
            if progress:
                # Check if sync is still active (not completed or failed)
                if progress.status in ['queued', 'processing']:
                    return jsonify({
                        'has_active_sync': True,
                        'sync_token': sync_token,
                        'progress': progress.model_dump()
                    }), 200
                else:
                    # Sync is completed/failed, clear the token
                    current_user.plaudSettings.activeSyncToken = None
                    current_user.plaudSettings.activeSyncStarted = None
                    user_handler = get_user_handler()
                    user_handler.save_user(current_user)
                    logger.info(f"Cleared completed sync token for user {current_user.id}")
            else:
                # Progress record not found, clear orphaned token
                current_user.plaudSettings.activeSyncToken = None
                current_user.plaudSettings.activeSyncStarted = None
                user_handler = get_user_handler()
                user_handler.save_user(current_user)
                logger.info(f"Cleared orphaned sync token for user {current_user.id}")
        
        return jsonify({'has_active_sync': False}), 200
        
    except Exception as e:
        logger.error(f"Error checking active sync: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Plaud Callback Handler
# ============================================================================

@plaud_bp.route('/plaud_callback', methods=['POST'])
def plaud_callback():
    """Handle callbacks from the transcoding container for Plaud operations"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        action = data.get('action')
        callback_token = data.get('callback_token')
        user_id = data.get('user_id')
        
        logger.info(f"Received Plaud callback: action={action}, user_id={user_id}")
        
        if not callback_token:
            return jsonify({'error': 'Missing callback token'}), 400
            
        # Validate callback token against stored token
        user_handler = create_user_handler()
        user = user_handler.get_user(user_id)
        
        if not user or not user.plaudSettings:
            logger.error(f"User not found or no Plaud settings for user {user_id}")
            return jsonify({'error': 'Invalid user'}), 401
            
        stored_token = user.plaudSettings.activeSyncToken
        sync_started = user.plaudSettings.activeSyncStarted
        
        # Check if token exists and matches
        if not stored_token or stored_token != callback_token:
            logger.error(f"Invalid callback token for user {user_id}")
            return jsonify({'error': 'Invalid callback token'}), 401
            
        # Check if token has expired (1 hour timeout)
        if sync_started:
            elapsed = datetime.now(UTC) - sync_started
            if elapsed.total_seconds() > 3600:  # 1 hour timeout
                logger.error(f"Sync token expired for user {user_id} (started {elapsed.total_seconds():.0f}s ago)")
                # Clear the expired token
                user.plaudSettings.activeSyncToken = None
                user.plaudSettings.activeSyncStarted = None
                user_handler.save_user(user)
                return jsonify({'error': 'Sync token expired'}), 401
        
        # Handle different callback actions
        if action == 'register_plaud_recording':
            return handle_plaud_recording_registration(data)
        elif action == 'plaud_sync':
            return handle_plaud_sync_status(data)
        else:
            logger.error(f"Unknown Plaud callback action: {action}")
            return jsonify({'error': f'Unknown action: {action}'}), 400
            
    except Exception as e:
        logger.error(f"Error processing Plaud callback: {e}")
        return jsonify({'error': str(e)}), 500

def handle_plaud_recording_registration(data):
    """Handle registration of a new Plaud recording"""
    try:
        user_id = data.get('user_id')
        plaud_id = data.get('plaud_id')
        original_filename = data.get('original_filename')
        original_timestamp = data.get('original_timestamp')
        duration = data.get('duration')
        filesize = data.get('filesize')
        filetype = data.get('filetype')
        dry_run = data.get('dry_run', False)
        
        # Validate required fields
        if not all([user_id, plaud_id, original_filename]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
            
        if dry_run:
            # For dry run, just return success without creating records
            return jsonify({
                'success': True,
                'recording_id': f'dry-run-{plaud_id}',
                'sas_url': 'https://example.com/dry-run-sas-url',
                'message': 'Dry run - no actual recording created'
            }), 200
        
        # Check if recording with this plaud_id already exists to prevent duplicates
        recording_handler = get_recording_handler()
        existing_recordings = recording_handler.get_user_recordings(user_id)
        
        for existing in existing_recordings:
            if (existing.plaudMetadata and 
                existing.plaudMetadata.plaudId == plaud_id):
                return jsonify({
                    'success': False,
                    'error': f'Recording with Plaud ID {plaud_id} already exists'
                }), 409
        
        # Generate unique filename for the recording
        unique_filename = f"{uuid.uuid4().hex}.mp3"
        
        # Create plaud metadata
        plaud_metadata = {
            'plaudId': plaud_id,
            'originalTimestamp': original_timestamp,
            'plaudFilename': original_filename,
            'plaudFileSize': filesize or 0,
            'plaudDuration': int((duration or 0) * 1000),  # Convert to milliseconds
            'plaudFileType': filetype or 'mp3',
            'syncedAt': datetime.now(UTC).isoformat()
        }
        
        # Create recording record
        from shared_quickscribe_py.cosmos import Source
        recording = recording_handler.create_recording(
            user_id=user_id,
            original_filename=original_filename,
            unique_filename=unique_filename,
            source=Source.plaud,
            title=original_filename,  # Default title to filename
            recorded_timestamp=original_timestamp  # Use the actual recording timestamp from Plaud
        )
        
        # Update recording with Plaud metadata and duration
        from shared_quickscribe_py.cosmos import PlaudMetadata
        recording.plaudMetadata = PlaudMetadata(**plaud_metadata)
        recording.duration = duration
        recording.upload_timestamp = datetime.now(UTC).isoformat()
        recording_handler.update_recording(recording)
        
        # Generate SAS URL for upload
        sas_url = generate_recording_sas_url(unique_filename, read=True, write=True)
        
        logger.info(f"Registered Plaud recording {recording.id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'recording_id': recording.id,
            'sas_url': sas_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error registering Plaud recording: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def handle_plaud_sync_status(data):
    """Handle Plaud sync status updates"""
    try:
        user_id = data.get('user_id')
        status = data.get('status')
        callback_token = data.get('callback_token')
        
        logger.info(f"Plaud sync status update for user {user_id}: {status}")
        
        # Get sync progress handler for updating progress
        sync_progress_handler = get_sync_progress_handler()
        
        if status == 'in_progress':
            # Sync operation started
            message = data.get('message', 'Sync in progress')
            total_recordings = data.get('total_recordings_found')
            logger.info(f"Plaud sync started for user {user_id}: {message}")
            
            # Update progress to processing status
            update_data = {
                'status': 'processing',
                'currentStep': message
            }
            if total_recordings is not None:
                update_data['totalRecordings'] = total_recordings
                
            sync_progress_handler.update_progress(callback_token, user_id, **update_data)
            
        elif status == 'recording_processed':
            # Individual recording was processed successfully
            plaud_id = data.get('plaud_id')
            recording_id = data.get('recording_id')
            filename = data.get('filename', plaud_id)
            logger.info(f"Plaud recording {plaud_id} processed as {recording_id}")
            
            # Update progress with successful recording
            current_progress = sync_progress_handler.get_progress(callback_token, user_id)
            if current_progress:
                processed_count = current_progress.processedRecordings + 1
                total = current_progress.totalRecordings or 0
                
                step_message = f"Processing recordings ({processed_count}"
                if total > 0:
                    step_message += f"/{total}"
                step_message += ")"
                
                sync_progress_handler.update_progress(
                    callback_token, 
                    user_id,
                    processedRecordings=processed_count,
                    currentStep=step_message
                )
            
        elif status == 'recording_failed':
            # Individual recording failed
            plaud_id = data.get('plaud_id')
            filename = data.get('filename', plaud_id)
            error_message = data.get('error_message')
            logger.error(f"Plaud recording {plaud_id} failed: {error_message}")
            
            # Add error to progress tracking
            error_detail = f"{filename}: {error_message}"
            sync_progress_handler.add_error(callback_token, user_id, error_detail)
            
        elif status == 'completed':
            # Sync operation completed
            total_found = data.get('total_recordings_found', 0)
            processed = data.get('new_recordings_processed', 0)
            error_count = data.get('error_count', 0)
            processing_time = data.get('processing_time', 0)
            
            logger.info(f"Plaud sync completed for user {user_id}: "
                       f"{processed}/{total_found} processed, "
                       f"{error_count} errors, "
                       f"{processing_time:.1f}s")
            
            # Mark progress as completed
            final_message = f"Sync completed: {processed} recordings processed"
            if error_count > 0:
                final_message += f", {error_count} errors"
            
            sync_progress_handler.update_progress(
                callback_token,
                user_id,
                status='completed',
                currentStep=final_message
            )
            
            # Update user's last sync timestamp
            user_handler = create_user_handler()
            user = user_handler.get_user(user_id)
            if user and user.plaudSettings:
                user.plaudSettings.lastSyncTimestamp = datetime.now(UTC)
                user.plaudSettings.activeSyncToken = None  # Clear active sync
                user.plaudSettings.activeSyncStarted = None
                user_handler.save_user(user)
                
        elif status == 'failed':
            # Sync operation failed
            error_message = data.get('error_message')
            logger.error(f"Plaud sync failed for user {user_id}: {error_message}")
            
            # Mark progress as failed
            sync_progress_handler.mark_failed(callback_token, user_id, error_message)
            
            # Clear active sync from user
            user_handler = create_user_handler()
            user = user_handler.get_user(user_id)
            if user and user.plaudSettings:
                user.plaudSettings.activeSyncToken = None
                user.plaudSettings.activeSyncStarted = None
                user_handler.save_user(user)
            
        else:
            logger.warning(f"Unknown Plaud sync status: {status}")
        
        return jsonify({'message': 'Status update received'}), 200
        
    except Exception as e:
        logger.error(f"Error handling Plaud sync status: {e}")
        return jsonify({'error': str(e)}), 500

@plaud_bp.route('/admin/cleanup_stale_syncs', methods=['POST'])
def cleanup_stale_syncs():
    """Admin endpoint to clean up stale sync operations (2+ hours in queue)"""
    try:
        # Get sync progress handler
        sync_progress_handler = get_sync_progress_handler()
        
        # Find stale syncs before marking them failed
        cutoff_time = datetime.now(UTC) - timedelta(hours=2)
        query = "SELECT * FROM c WHERE c.status = 'queued' AND c.startTime < @cutoff_time"
        parameters = [{"name": "@cutoff_time", "value": cutoff_time.isoformat()}]
        
        stale_syncs = list(sync_progress_handler.container.query_items(
            query=query,
            parameters=parameters
        ))
        
        # Clear user active sync tokens for stale syncs
        user_handler = get_user_handler()
        cleared_tokens = 0
        
        for item in stale_syncs:
            try:
                user_id = item.get('userId')
                sync_token = item.get('syncToken')
                
                if user_id and sync_token:
                    user = user_handler.get_user(user_id)
                    if (user and user.plaudSettings and 
                        user.plaudSettings.activeSyncToken == sync_token):
                        user.plaudSettings.activeSyncToken = None
                        user.plaudSettings.activeSyncStarted = None
                        user_handler.save_user(user)
                        cleared_tokens += 1
                        logger.info(f"Cleared stale active sync token for user {user_id}")
                        
            except Exception as e:
                logger.warning(f"Failed to clear user token for stale sync: {str(e)}")
        
        # Now mark the syncs as failed
        cleaned_count = sync_progress_handler.check_stale_syncs()
        
        logger.info(f"Cleanup complete: {cleaned_count} stale syncs marked failed, {cleared_tokens} user tokens cleared")
        
        return jsonify({
            'message': f'Cleaned up {cleaned_count} stale sync operations',
            'stale_syncs_failed': cleaned_count,
            'user_tokens_cleared': cleared_tokens
        }), 200
        
    except Exception as e:
        logger.error(f"Error during stale sync cleanup: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Helper Functions
# ============================================================================

def send_plaud_sync_to_queue(user_id: str, plaud_settings: dict, dry_run: bool = False):
    """Send a Plaud sync message to the transcoding queue"""
    sync_token = str(uuid.uuid4())
    
    backend_base_url = os.getenv('BACKEND_BASE_URL')
    if backend_base_url:
        callback_url = f"{backend_base_url.rstrip('/')}/plaud/plaud_callback"
    else:
        callback_url = url_for('plaud.plaud_callback', _external=True)
    
    callbacks = [{
        'url': callback_url,
        'token': sync_token
    }]
    
    # Get list of previously processed Plaud IDs
    recording_handler = get_recording_handler()
    processed_ids = recording_handler.get_user_plaud_ids(user_id)
    logger.info(f"Found {len(processed_ids)} previously synced Plaud recordings for user {user_id}")
    
    sync_message = {
        'action': 'plaud_sync',
        'user_id': user_id,
        'bearerToken': plaud_settings['bearerToken'],
        'lastSyncTimestamp': plaud_settings.get('lastSyncTimestamp'),
        'processedPlaudIds': processed_ids,
        'callbacks': callbacks,
        'callback_token': sync_token,
        'dry_run': dry_run
    }
    
    queue_client = QueueClient.from_connection_string(
        config.AZURE_STORAGE_CONNECTION_STRING,
        queue_name=config.TRANSCODING_QUEUE_NAME
    )
    queue_client.send_message(json.dumps(sync_message))
    
    return sync_token