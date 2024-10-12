from flask import Blueprint, request, redirect, jsonify
from db_handlers.transcription_handler import TranscriptionHandler, TranscribingStatus
from db_handlers.recording_handler import RecordingHandler
from db_handlers.user_handler import UserHandler
from util.blob_util import generate_recording_sas_url
from azure.storage.blob import BlobServiceClient
import assemblyai as aai

from dotenv import load_dotenv
import os

load_dotenv()

# Initialize your handlers (you can replace these with actual configurations)
# Azure Blob Storage configurations
AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("AZURE_RECORDING_BLOB_CONTAINER")

# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# Initialize Cosmos DB client
COSMOS_URL = os.environ.get('COSMOS_URL')  # Your Cosmos DB URI
COSMOS_KEY = os.environ.get('COSMOS_KEY')  # Your Cosmos DB primary key
DATABASE_NAME = os.getenv("COSMOS_DB_NAME")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Set up a Flask blueprint for transcription routes
transcription_bp = Blueprint('transcription_bp', __name__)

# Initialize your handlers
recording_handler = RecordingHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, "RecordingContainer")
transcription_handler = TranscriptionHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)

@transcription_bp.route("/start_transcription/<recording_id>", methods=["POST"])
def start_transcription(recording_id):
    user = get_user(request)
    recording_handler = RecordingHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)
    # Get the recording details
    # TODO - check that the recording exists and belongs to the user
    recording = recording_handler.get_recording(recording_id)
    if not recording or recording['user_id'] != user['id']:
        return jsonify({'error': 'Recording not found or does not belong to the user'}), 404

    transcription_handler = TranscriptionHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)
    #see if there is already a transcription for this recording
    transcription = transcription_handler.get_transcription_by_recording(recording_id)
    if transcription and transcription['status'] in [TranscribingStatus.IN_PROGRESS.value, TranscribingStatus.COMPLETED.value]:
        return jsonify({'error': 'Transcription already exists for this recording'}), 400
    
    if not transcription:
        logging.info(f"No transcription found, creating new transcription")
        transcription = transcription_handler.create_transcription(user['id'], recording_id)
    else:
        logging.info(f"Transcription found: {transcription['id']}")
    
    try:
        blob_sas_url = generate_recording_sas_url(recording['unique_filename'])
        logging.info(f"SAS URL generated: {blob_sas_url}")
        
        # Call the long-running AssemblyAI transcription function asynchronously
        logging.info(f"Calling AssemblyAI transcription function: {transcription['id']}")
        
        callback_url = f"{request.host}/transcription/transcription_callback/{transcription['id']}"
        transcription['callback_secret'] = uuid.uuid4()
        transcription['status'] = TranscribingStatus.IN_PROGRESS.value
        transcription_handler.update_transcription(transcription)

        aai.settings.api_key = ASSEMBLYAI_API_KEY
        config = aai.TranscriptionConfig().set_webhook(callback_url, "X-Callback-Secret", transcription['callback_secret'])
        aai.Transcriber().submit(blob_sas_url, config)
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        #print the stack trace
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@transcription_bp.route("/transcription_callback/<transcription_id>", methods=["POST"])
def transcription_callback(transcription_id):
    logging.info(f"Transcription callback received: {transcription_id}")
    #log the request body
    logging.info(request.json)
    transcription_handler = TranscriptionHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)
    transcription = transcription_handler.get_transcription(transcription_id)
    if not transcription:
        return jsonify({'error': 'Transcription not found'}), 404

    transcript_id = request.json['transcript_id']
    status = request.json['status']

    if status == 'completed':
        transcription['status'] = TranscribingStatus.COMPLETED.value
        transcription['aai_transcript_id'] = transcript_id
    else:
        logging.error(f"AssemblyAI transcription failed: {transcription_id}")
        transcription['status'] = TranscribingStatus.FAILED.value
        return jsonify({'error': 'Transcription failed'}), 500
    

    # get the transcript from AssemblyAI
    aai.settings.api_key = ASSEMBLYAI_API_KEY
    transcript = aai.Transcript.get_by_id(transcript_id)
    if not transcript:
        logging.error(f"Transcript not found: {transcript_id}")
        return jsonify({'error': 'Transcript not found'}), 404
    
    print(transcript)
    transcription['text'] = transcript.text
    # save the transcript to Cosmos DB
    transcription_handler.update_transcription(transcription)
    

    
