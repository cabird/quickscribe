from flask import Blueprint, request, redirect, jsonify
from db_handlers.transcription_handler import TranscriptionHandler, TranscribingStatus
from db_handlers.recording_handler import RecordingHandler
from user_util import get_user
from blob_util import generate_recording_sas_url
from azure.storage.blob import BlobServiceClient
import assemblyai as aai
import logging
import uuid
import json
from config import config


# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)

transcription_bp = Blueprint('transcription_bp', __name__)

# Initialize your handlers
recording_handler = RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
transcription_handler = TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

@transcription_bp.route("/start_transcription/<recording_id>", methods=["POST", "GET"])
def start_transcription(recording_id):
    user = get_user(request)
    # Get the recording details
    # TODO - check that the recording exists and belongs to the user
    recording = recording_handler.get_recording(recording_id)
    if not recording or recording['user_id'] != user['id']:
        logging.error(f"Recording not found or does not belong to the user: {recording_id}")
        return jsonify({'error': 'Recording not found or does not belong to the user'}), 404

    #see if there is already a transcription for this recording
    transcription = transcription_handler.get_transcription_by_recording(recording_id)
    logging.info(f"Transcription: {transcription}")
    if transcription and transcription['transcription_status'] in [TranscribingStatus.IN_PROGRESS.value, TranscribingStatus.COMPLETED.value]:
        logging.error(f"Transcription already exists for this recording: {transcription['id']}")
        return jsonify({'error': 'Transcription already exists for this recording'}), 400
    
    if not transcription:
        logging.info(f"No transcription found, creating new transcription")
        transcription = transcription_handler.create_transcription(user['id'], recording_id)
    else:
        logging.info(f"Transcription found: {transcription['id']}")
    

    callback_secret = str(uuid.uuid4())
    aai_transcript_id = None
    try:
        blob_sas_url = generate_recording_sas_url(recording['unique_filename'])
        logging.info(f"SAS URL generated: {blob_sas_url}")
        
        # Call the long-running AssemblyAI transcription function asynchronously
        logging.info(f"Calling AssemblyAI transcription function: {transcription['id']}")
        

        transcription['callback_secret'] = callback_secret

        aai.settings.api_key = config.ASSEMBLYAI_API_KEY
        aai_config = aai.TranscriptionConfig(speaker_labels=True, speech_model=aai.SpeechModel.nano)

        if config.RUNNING_IN_CONTAINER:
            logging.info(f"Running in container, setting webhook")
            callback_url = f"https://{request.host}/transcription/transcription_callback/{transcription['id']}"
            logging.info(f"Callback URL: {callback_url}")
            aai_config.set_webhook(callback_url, "X-Callback-Secret", callback_secret)
            logging.info(f"Submitting transcription to AssemblyAI: {blob_sas_url}")
            aai.Transcriber().submit(blob_sas_url, aai_config)
            transcription['transcription_status'] = TranscribingStatus.IN_PROGRESS.value
            transcription_handler.update_transcription(transcription)
            return "<html><body><h1>Transcription started</h1></body></html>", 200
        else:
            logging.info(f"Running locally, calling and waiting for transcription to complete")
            transcript = aai.Transcriber().transcribe(blob_sas_url, aai_config)
            transcription['transcription_status'] = TranscribingStatus.COMPLETED.value
            aai_transcript_id = transcript.id
            transcription_handler.update_transcription(transcription)
            # return a simple html page saying that the transcription has completed
            headers = {"X-Callback-Secret": callback_secret}
            json_payload = {"status": "completed", "transcript_id": aai_transcript_id}
            logging.info("Calling handle_transcription_callback since we're running locally")
            handle_transcription_callback(transcription['id'], json_payload, headers)
            return "<html><body><h1>Transcription completed</h1></body></html>", 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        #print the stack trace
        import traceback
        traceback.print_exc()
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@transcription_bp.route("/transcription_callback/<transcription_id>", methods=["POST"])
def transcription_callback(transcription_id):
    json_data = request.json
    headers = request.headers
    handle_transcription_callback(transcription_id, json_data, headers)
    return "", 200


def handle_transcription_callback(transcription_id, json_data, headers):
    logging.info(f"Transcription callback received: {transcription_id}")
    logging.info(f"Request body: {json_data}")
    logging.info(f"Headers: {headers}")
    transcription = transcription_handler.get_transcription(transcription_id)
    if not transcription:
        logging.error(f"Transcription not found: {transcription_id}")
        return jsonify({'error': 'Transcription not found'}), 404

    if transcription['callback_secret'] != headers.get('X-Callback-Secret', ""):
        logging.error(f"Invalid callback secret: {headers.get('X-Callback-Secret')}")
        return jsonify({'error': 'Invalid callback secret'}), 401

    transcript_id = json_data['transcript_id']
    status = json_data['status']

    if status == 'completed':
        logging.info(f"AssemblyAI transcription completed: {transcription_id}")
        transcription['transcription_status'] = TranscribingStatus.COMPLETED.value
        transcription['aai_transcript_id'] = transcript_id
    else:
        logging.error(f"AssemblyAI transcription failed: {transcription_id}")
        transcription['transcription_status'] = TranscribingStatus.FAILED.value
        return jsonify({'error': 'Transcription failed'}), 500
    

    # get the transcript from AssemblyAI
    aai.settings.api_key = config.ASSEMBLYAI_API_KEY
    transcript = aai.Transcript.get_by_id(transcript_id)
    if not transcript:
        logging.error(f"Transcript not found: {transcript_id}")
        return jsonify({'error': 'Transcript not found'}), 404

    logging.info(f"Transcript: {transcript}")
    
    transcription['text'] = transcript.text
    transcription['diarized_transcript'] = get_diarized_transcript(transcript)
    # save the transcript to Cosmos DB
    transcription_handler.update_transcription(transcription)
    

def get_json_from_transcript(transcript):
    json_transcript = {}
    json_transcript['text'] = transcript.text
    json_transcript['words'] = []
    for word in transcript.words:
        json_transcript['words'].append({
            'word': word.text,
            'start': word.start,
            'end': word.end,
            'confidence': word.confidence,
            'speaker': word.speaker if hasattr(word, 'speaker') else "not specified"
        })
    json_transcript['utterances'] = []
    for utterance in transcript.utterances:
        words = []
        for word in utterance.words:
            words.append({
                'word': word.text,
                'start': word.start,
                'end': word.end,
                'confidence': word.confidence,
                'speaker': word.speaker if hasattr(word, 'speaker') else "not specified"
            })
        json_transcript['utterances'].append({
            'words': words,
        })
    
    return json.dumps(json_transcript, indent=4)

def get_diarized_transcript(transcript):
    # Process the transcript
    utterances_list = []
    for utterance in transcript.utterances:
        utterance_dict = {
            "confidence": utterance.confidence,
            "end": utterance.end,
            "speaker": utterance.speaker,
            "start": utterance.start,
            "text": utterance.text,
            "words": [
                {
                    "text": word.text,
                    "start": word.start,
                    "end": word.end,
                    "confidence": word.confidence,
                    "speaker": word.speaker
                } for word in utterance.words
            ]
        }
        utterances_list.append(utterance_dict)

    # Additional processing and saving to files
    speaker_mapping = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E'}

    # Add the speaker_name to each utterance
    for utterance in utterances_list:
        utterance['speaker_name'] = speaker_mapping[utterance['speaker']]

    lines = []
    for utterance in utterances_list:
        lines.append(f"Speaker {speaker_mapping[utterance['speaker']]}: {utterance['text']}")

    #combine lines into a single string
    transcript_text = "\n\n".join(lines)
    return transcript_text