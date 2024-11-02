# api.py
from flask import Blueprint, request, jsonify
from db_handlers.handler_factory import get_user_handler, get_recording_handler, get_transcription_handler
from user_util import get_user
from db_handlers.models import User, Recording, Transcription
from util import update_diarized_transcript
import logging
from llms import get_speaker_summaries_via_llm


api_bp = Blueprint('api', __name__)

# Helper function to get current user
def get_current_user():
    return get_user(request)

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

@api_bp.route('/deleterecording/<recording_id>', methods=['GET'])
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