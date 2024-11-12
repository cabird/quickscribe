from flask import Blueprint, request, redirect, jsonify, flash, url_for
from db_handlers.transcription_handler import TranscriptionHandler
from db_handlers.recording_handler import RecordingHandler
from db_handlers.models import TranscriptionStatus, Recording
from user_util import get_user
from blob_util import generate_recording_sas_url
from azure.storage.blob import BlobServiceClient
import assemblyai as aai
import logging
import uuid
import json
from config import config
from datetime import datetime, UTC
import swagger_client
import requests
from pprint import pprint

# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)

az_transcription_bp = Blueprint('az_transcription_bp', __name__)

# Initialize your handlers
recording_handler = RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
transcription_handler = TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

@az_transcription_bp.route("/start_transcription/<recording_id>", methods=["POST", "GET"])
def start_transcription(recording_id):
    logging.info(f"Starting transcription: {recording_id}")
    user = get_user(request)
    # Get the recording details
    # TODO - check that the recording exists and belongs to the user
    recording = recording_handler.get_recording(recording_id)

    if not recording or recording.user_id != user.id:
        logging.error(f"Recording not found or does not belong to the user: {recording_id}")
        return jsonify({'error': 'Recording not found or does not belong to the user'}), 404

    logging.info(f"found recording: {recording.original_filename}")

    #see if there is already a transcription for this recording
    transcription = transcription_handler.get_transcription_by_recording(recording_id)
    logging.info(f"Transcription: {transcription}")
    if recording and recording.transcription_status in [TranscriptionStatus.in_progress, TranscriptionStatus.completed]:
        logging.warning(f"Transcription already exists or in progress for this recording: {recording.id}")
        return jsonify({'error': 'Transcription already exists or in progress for this recording'}), 400
    
    if not transcription:
        logging.info(f"No transcription found, creating new transcription")
        transcription = transcription_handler.create_transcription(user.id, recording_id)
    else:
        logging.info(f"Transcription found: {transcription.id}")
    
    try:
        blob_sas_url = generate_recording_sas_url(recording.unique_filename)
        logging.info(f"SAS URL generated: {blob_sas_url}")        
        # Call the long-running Azure Speech Services transcription function asynchronously
        logging.info(f"Calling Azure Speech Services transcription function: {transcription.id}")
            
        logging.info(f"Submitting transcription to Azure Speech Services: {blob_sas_url}")
        az_transcription_id = az_transcribe(blob_sas_url, recording.original_filename)

        recording.transcription_status = TranscriptionStatus.in_progress
        recording.az_transcription_id = az_transcription_id
        recording_handler.update_recording(recording)
        return jsonify({'message': 'Transcription started'}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        #print the stack trace
        import traceback
        traceback.print_exc()
        logging.error(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@az_transcription_bp.route("/transcription_hello_world", methods=["GET"])
def transcription_hello_world():
    return "<html><body><h1>Hello World</h1></body></html>", 200

@az_transcription_bp.route("/check_transcription_status/<recording_id>", methods=["GET"])
def check_transcription_status(recording_id):
    logging.info(f"Checking transcription status: {recording_id}")
    recording = recording_handler.get_recording(recording_id)
    status, error = check_in_progress_transcription(recording)
    return jsonify({'status': status, 'error': error}), 200

def check_in_progress_transcription(recording: Recording) -> tuple[str, str]:
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)
    az_transcription_id = recording.az_transcription_id
    if not az_transcription_id:
        return TranscriptionStatus.not_started.value, ""
    az_transcription = api.transcriptions_get(az_transcription_id)
    logging.info(f" got transcription for {az_transcription_id}")

    # valid statuses are "NotStarted", "Running", "Succeeded", "Failed" - these are different than the TranscriptionStatus enum
    az_status_map = {
        "NotStarted": TranscriptionStatus.not_started.value,
        "Running": TranscriptionStatus.in_progress.value,
        "Succeeded": TranscriptionStatus.completed.value,
        "Failed": TranscriptionStatus.failed.value
    }
    status = az_status_map[az_transcription.status]
    logging.info(f"AZ Transcription status: {status}")
    error_message = ""
    if status == TranscriptionStatus.completed.value:
        logging.info(f"Transcription succeeded: {az_transcription_id}")
        transcription = transcription_handler.get_transcription_by_recording(recording.id)
        if not transcription:
            logging.info(f"No transcription found, creating new transcription")
            transcription = transcription_handler.create_transcription(recording.user_id, recording.id)
        transcription.az_transcription_id = az_transcription_id
        transcription.az_raw_transcription = str(az_transcription)
        
        logging.info(f"Getting transcript: {az_transcription_id}")
        transcription.transcript_json = az_get_transcript(az_transcription_id)
        json_data = json.loads(transcription.transcript_json)        
        
        transcription.diarized_transcript = az_get_diarized_transcript(json_data)

        logging.info(f"Updating transcription: {transcription.id}")
        transcription_handler.update_transcription(transcription)

        recording.transcription_status = TranscriptionStatus.completed
        recording.transcription_id = transcription.id
        recording_handler.update_recording(recording)

    elif status == TranscriptionStatus.failed.value and az_transcription.properties.error:
        logging.info(f"Transcription failed: {az_transcription.properties.error}")
        error_message = str(az_transcription.properties.error.code) + ": " + str(az_transcription.properties.error.message)
    elif status == TranscriptionStatus.in_progress.value:
        logging.info(f"Transcription is still running: {az_transcription_id}")
    return status, error_message

  
def az_paginate(api, paginated_object):
    """
    The autogenerated client does not support pagination. This function returns a generator over
    all items of the array that the paginated object `paginated_object` is part of.
    """
    yield from paginated_object.values
    typename = type(paginated_object).__name__
    auth_settings = ["api_key"]
    while paginated_object.next_link:
        link = paginated_object.next_link[len(api.api_client.configuration.host):]
        paginated_object, status, headers = api.api_client.call_api(link, "GET",
            response_type=typename, auth_settings=auth_settings)

        if status == 200:
            yield from paginated_object.values
        else:
            raise Exception(f"could not receive paginated data: status {status}")

def get_speech_api_client():
    configuration = swagger_client.Configuration()
    configuration.api_key["Ocp-Apim-Subscription-Key"] = config.AZURE_SPEECH_SERVICES_KEY
    configuration.host = f"https://{config.AZURE_SPEECH_SERVICES_REGION}.api.cognitive.microsoft.com/speechtotext/v3.2"

    client = swagger_client.ApiClient(configuration)
    return client

def az_transcribe(blob_sas_url, original_filename):
    """
    Transcribe a single audio file located at `blob_sas_url` using the settings specified in `properties`
    using the base model for the specified locale.

    returns the transcription id
    """

    logging.info("Starting transcription client...")
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)

    properties = swagger_client.TranscriptionProperties()
    properties.punctuation_mode = "DictatedAndAutomatic"
    properties.diarization_enabled = True
    #TODO - make this dynamic
    properties.diarization = swagger_client.DiarizationProperties(
        swagger_client.DiarizationSpeakersProperties(min_count=1, max_count=5))
    
    name = "Transcription of " + original_filename
    description = f"Transcription of {original_filename} using the Azure Speech Services, started at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"

    transcription_definition = swagger_client.Transcription(
        display_name=name,
        description=description,
        locale="en-US",
        content_urls=[blob_sas_url],
        properties=properties
    )

    created_transcription, status, headers = api.transcriptions_create_with_http_info(transcription=transcription_definition)
    logging.info(f"Transcription created: {created_transcription}")
    logging.info(f"Status: {status}")
    logging.info(f"Headers: {headers}")

    transcription_id = headers["location"].split("/")[-1]
    return transcription_id

def az_get_transcript(az_transcription_id): 
    logging.info(f"Getting transcript: {az_transcription_id}")
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)

    transcription = api.transcriptions_get(az_transcription_id)
    logging.info(f"Transcript: {transcription}")
    if transcription.status == "Succeeded":
        pag_files = api.transcriptions_list_files(az_transcription_id)
        for file_data in az_paginate(api, pag_files):
            if file_data.kind != "Transcription":
                continue
            logging.info(f"File data: {file_data}")
            results_url = file_data.links.content_url
            logging.info(f"Results URL: {results_url}")
            results = requests.get(results_url)
            #logging.info(f"Results for {az_transcription_id}:\n{results.content.decode('utf-8')}")
            return results.content.decode('utf-8')
    return None


# Function to generate the transcript
def az_get_diarized_transcript(json_data):
    transcript = []
    last_speaker = None
    last_text = []

    for phrase in json_data["recognizedPhrases"]:
        current_speaker = phrase["speaker"]
        current_text = phrase["nBest"][0]["display"]

        # Combine consecutive text if same speaker
        if current_speaker == last_speaker:
            last_text.append(current_text)
        else:
            if last_text:  # Add the previous speaker's combined text
                transcript.append(f"Speaker {last_speaker}: " + " ".join(last_text) + "\n")
            # Reset for new speaker
            last_speaker = current_speaker
            last_text = [current_text]

    # Append the last speaker's text after the loop
    if last_text:
        transcript.append(f"Speaker {last_speaker}: " + " ".join(last_text) + "\n")
    
    return "\n".join(transcript)