from flask import Blueprint, jsonify, request
from db_handlers.handler_factory import get_transcription_handler
from llms import get_speaker_summaries_via_llm, get_speaker_mapping
from logging_config import get_logger
from api_version import API_VERSION

# Initialize logger
logger = get_logger('ai_routes', API_VERSION)

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "up"})

@ai_bp.route('/get_speaker_summaries/<transcription_id>', methods=['GET'])
def get_speaker_summaries(transcription_id):
    logger.info(f"get_speaker_summaries: transcription_id {transcription_id}")
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        logger.info(f"get_speaker_summaries: found diarized transcript")
        summaries = get_speaker_summaries_via_llm(transcription.diarized_transcript)
        logger.info(f"get_speaker_summaries: summaries {summaries}")
        return jsonify(summaries), 200
    return jsonify({'error': 'Transcription not found or does not have a diarized transcript'}), 404

@ai_bp.route('/infer_speaker_names/<transcription_id>')
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