# api.py
from flask import Blueprint, request, jsonify, url_for
from db_handlers.handler_factory import get_user_handler, get_recording_handler, get_transcription_handler
from user_util import get_user
from db_handlers.models import User, Recording, Transcription, TranscodingStatus, TranscriptionStatus
from util import update_diarized_transcript, convert_to_mp3, get_recording_duration_in_seconds
import logging
from llms import get_speaker_summaries_via_llm, get_speaker_mapping
import uuid
import os
from werkzeug.utils import secure_filename
from datetime import datetime, UTC
import time
from blob_util import store_recording_as_blob, send_to_transcoding_queue
from api_version import API_VERSION

api_bp = Blueprint('api', __name__)

# Helper function to get current user
def get_current_user():
    return get_user(request)

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
    recordings = recording_handler.get_all_recordings()
    return jsonify([recording.model_dump() for recording in recordings]), 200

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

@api_bp.route('/get_speaker_summaries/<transcription_id>', methods=['GET'])
def get_speaker_summaries(transcription_id):
    logging.info(f"get_speaker_summaries: transcription_id {transcription_id}")
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        logging.info(f"get_speaker_summaries: found diarized transcript")
        summaries = get_speaker_summaries_via_llm(transcription.diarized_transcript)    
        logging.info(f"get_speaker_summaries: summaries {summaries}")
        return jsonify(summaries), 200
    return jsonify({'error': 'Transcription not found or does not have a diarized transcript'}), 404

@api_bp.route('/update_speaker_labels/<transcription_id>', methods=['POST'])
def update_speaker_labels(transcription_id):
    logging.info(f"update_speaker_labels: transcription_id {transcription_id}")
    #output the request json
    logging.info(f"update_speaker_labels: request json {request.json}")
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        speaker_labels = request.json
        # TODO - update the speaker labels... do we need them?
        updated_transcript = update_diarized_transcript(transcription.diarized_transcript, speaker_labels)
        transcription.diarized_transcript = updated_transcript

        #transcription.speaker_mapping = speaker_labels
        logging.info(f"update_speaker_labels: updated_transcript")
        transcription_handler.update_transcription(transcription)
        return jsonify({'message': 'Speaker labels updated successfully'}), 200
    return jsonify({'error': 'Transcription not found or does not have a diarized transcript'}), 404


@api_bp.route("/infer_speaker_names/<transcription_id>")
def infer_speaker_names(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        if True: # TODO - uncomment this when we don't want to allow inferring multiple times... not transcription.speaker_mapping:
            speaker_mapping, diarized_text = get_speaker_mapping(transcription.diarized_transcript)
            transcription.speaker_mapping = speaker_mapping
            transcription.diarized_transcript = diarized_text
            transcription_handler.update_transcription(transcription)
            return jsonify({'message': 'Speaker names successfully inferred'}), 200
        else:
            return jsonify({'message': 'Speaker names already inferred'}), 200
    else:
        return jsonify({'error': 'Transcription not found'}), 404

#support upload from iphone share context menu
@api_bp.route("/upload_from_ios_share", methods=['POST'])
def upload_from_ios_share():
    logging.info("upload_from_ios_share endpoint called")

    # log file details
    filenames = [request.files[key].filename for key in request.files.keys()]
    #output the list of files in the request
    for file in request.files.values():
        #output all the fields in the file:
        logging.info(f"upload_from_ios_share: file {file}")
        logging.info(f"upload_from_ios_share: file.filename {file.filename}")
        logging.info(f"upload_from_ios_share: file.content_type {file.content_type}")
        logging.info(f"upload_from_ios_share: file.mimetype {file.mimetype}")
        logging.info(f"upload_from_ios_share: file.content_length {file.content_length}")
        logging.info(f"upload_from_ios_share: file.headers {file.headers}")
        
    logging.info(f"upload_from_ios_share: request files {filenames}")

    if 'audio_file' not in request.files:
        return jsonify({'error': 'No audio file part'}), 400

    audio_file = request.files['audio_file']
    if audio_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if audio_file:
        logging.info(f"handling upload of audio file: {audio_file}")

        try:
            logging.info(f"handling upload of file: {audio_file}")
            original_filename = secure_filename(audio_file.filename)

            #get the file extension
            file_extension = os.path.splitext(audio_file.filename)[1]
            unique_original_filename = uuid.uuid4().hex + file_extension
            unique_transcoded_filename = uuid.uuid4().hex + ".mp3"

            temp_path = os.path.join('/tmp', unique_original_filename)
            audio_file.save(temp_path)
            logging.info(f"file saved to {temp_path}")

            #store the original file in blob storage
            store_recording_as_blob(temp_path, unique_original_filename)
            logging.info(f"stored original file in blob storage as {unique_original_filename}")

            recording_handler = get_recording_handler()
            user = get_user(request)

            recording = recording_handler.create_recording(user.id, original_filename, unique_original_filename,
                                                           transcoding_status=TranscodingStatus.queued)
            recording.upload_timestamp = datetime.now(UTC).isoformat()
            recording.duration = get_recording_duration_in_seconds(temp_path)
            recording_handler.update_recording(recording)

            send_to_transcoding_queue(recording.id,
                                      unique_original_filename,
                                      unique_transcoded_filename,
                                      original_filename,
                                      user.id)

            logging.info(f"sent to transcoding queue: {recording.id}, {unique_original_filename}, {unique_transcoded_filename}, {original_filename}, {user.id}")

            os.remove(temp_path)

            return jsonify({'success': 'File uploaded successfully!', 
                            'filename': original_filename, 
                            'recording_id': recording.id, 
                            'transcoding_status': 'queued'}), 200



        except Exception as e:
            logging.error(f"error uploading file: {e}")
            #print the stack trace
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        
    return jsonify({'error': 'No valid audio file provided'}), 400


def generate_callbacks(request, callback_token):
    callbacks = []
    # Generate callback URL
    callbacks.append( { "url": url_for('api.transcoding_callback', _external=True), "token": callback_token })
    # TODO - move this to config or something
    callbacks.append( { "url": "https://eo6nc88rnfy4hyx.m.pipedream.net/", "token": callback_token })
    return callbacks
   

# File upload form route
@api_bp.route('/upload', methods=['POST'])
def upload():
    logging.info("upload endpoint called")
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            logging.info(f"handling upload of file: {file}")
            original_filename = secure_filename(file.filename)
            
            # Generate unique filename for the original upload
            file_extension = os.path.splitext(original_filename)[1]
            unique_original_filename = str(uuid.uuid4()) + file_extension
            
            # Generate target filename for transcoded version (always .mp3)
            unique_transcoded_filename = str(uuid.uuid4()) + ".mp3"
            
            # Save original file to temporary location
            temp_path = os.path.join('/tmp', unique_original_filename)
            file.save(temp_path)
            logging.info(f"file saved to {temp_path}")
            
            # Store original file in blob storage
            store_recording_as_blob(temp_path, unique_original_filename)
            logging.info(f"stored original file in blob storage as {unique_original_filename}")
            
            # Create recording in database with transcoding status "queued"
            recording_handler = get_recording_handler()
            user = get_user(request)
            
            recording = recording_handler.create_recording(
                user.id, 
                original_filename, 
                unique_original_filename,  # This will be the final transcoded filename
                transcoding_status=TranscodingStatus.queued
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
            logging.info(f"queued transcoding job for recording {recording.id}")
            
            # Clean up temporary file
            os.remove(temp_path)
            
            return jsonify({
                'message': 'File uploaded successfully and queued for transcoding!', 
                'filename': original_filename, 
                'recording_id': recording.id,
                'transcoding_status': 'queued'
            }), 200

        except Exception as e:
            logging.error(f"error uploading file: {e}")
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

# File upload form route
@api_bp.route('/transcoding_callback', methods=['POST'])
# this should be a POST request in json format with the following fields:
# user_id, original_filename, blob_filename, duration_in_seconds
def transcoding_callback():
    logging.info("transcoding_callback endpoint called")
    logging.info(f"transcoding_callback: request json {request.json}")

    data = request.json()
    if "test" in data:
        logging.info("transcoding_callback: test mode")
        return jsonify({'message': 'Transcoding callback received'}), 200
    
    #get the user_id from the request
    user_id = data.get('user_id')
    original_filename = data.get('original_filename')
    blob_filename = data.get('blob_filename')
    duration_in_seconds = data.get('duration_in_seconds')

    recording_handler = get_recording_handler()
    recording = recording_handler.create_recording(user_id, original_filename, blob_filename)
    recording.upload_timestamp = datetime.now(UTC).isoformat()
    # determine the duration of the recording
    recording.duration = duration_in_seconds
    recording_handler.update_recording(recording)

    return jsonify({'message': 'Transcoding callback received'}), 200
