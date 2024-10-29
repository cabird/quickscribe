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
    logging.info(f"found recording: {recording['original_filename']}")
    if not recording or recording['user_id'] != user['id']:
        logging.error(f"Recording not found or does not belong to the user: {recording_id}")
        return jsonify({'error': 'Recording not found or does not belong to the user'}), 404

    #see if there is already a transcription for this recording
    transcription = transcription_handler.get_transcription_by_recording(recording_id)
    logging.info(f"Transcription: {transcription}")
    if recording and recording['transcription_status'] in [TranscribingStatus.IN_PROGRESS.value, TranscribingStatus.COMPLETED.value]:
        logging.warning(f"Transcription already exists or in progress for this recording: {recording['id']}")
        return jsonify({'error': 'Transcription already exists or in progress for this recording'}), 400
    
    if not transcription:
        logging.info(f"No transcription found, creating new transcription")
        transcription = transcription_handler.create_transcription(user['id'], recording_id)
    else:
        logging.info(f"Transcription found: {transcription['id']}")
    

    try:
        blob_sas_url = generate_recording_sas_url(recording['unique_filename'])
        logging.info(f"SAS URL generated: {blob_sas_url}")        
        # Call the long-running Azure Speech Services transcription function asynchronously
        logging.info(f"Calling Azure Speech Services transcription function: {transcription['id']}")
        

        if config.RUNNING_IN_CONTAINER:
            logging.info(f"Running in container, setting webhook")
            # get the url of the transcription_webhook route
            transcription_webhook_url = request.host_url.replace("http://", "https://") + "az_transcription/transcription_webhook"
            #logging.info(f"Webhook URL: {transcription_webhook_url}")
            #set_webhook(transcription_webhook_url)

            logging.info(f"Submitting transcription to Azure Speech Services: {blob_sas_url}")
            az_transcription_id = az_transcribe(blob_sas_url, recording['original_filename'])

            recording['transcription_status'] = TranscribingStatus.IN_PROGRESS.value
            recording['transcription_status_updated_at'] = datetime.now(UTC).timestamp()
            recording['az_transcription_id'] = az_transcription_id
            recording_handler.update_recording(recording)
            return "<html><body><h1>Transcription started</h1></body></html>", 200

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

def check_in_progress_transcription(recording):
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)
    az_transcription_id = recording['az_transcription_id']
    az_transcription = api.transcriptions_get(az_transcription_id)
    logging.info(f"AZ Transcription: {az_transcription}")
    # valid statuses are "NotStarted", "Running", "Succeeded", "Failed"
    status = az_transcription.status
    if status == "Succeeded":
        transcription = transcription_handler.get_transcription_by_recording(recording['id'])
        if not transcription:
            transcription = transcription_handler.create_transcription(recording['user_id'], recording['id'])
            transcription['az_transcription_id'] = az_transcription_id
            transcription['az_transcription'] = str(az_transcription)
            transcription['text'] = "dummy_text"
            transcription['diarized_transcript'] = "dummy_text"
            transcription_handler.update_transcription(transcription)

    return status

@az_transcription_bp.route("/transcription_webhook", methods=["POST"])
def transcription_webhook():
    logging.info(f"Transcription webhook received")
    logging.info(f"Request body: {request.json}")
    logging.info(f"Headers: {request.headers}")
    json_data = request.json
    headers = request.headers
    # get the event type from the headers
    event_type = headers.get('X-MicrosoftSpeechServices-Event', "")
    logging.info(f"Event type: {event_type}")

    if event_type == "challenge":
        logging.info(f"Challenge event received. returning validation token {json_data.get('validationToken')}")
        return jsonify({"validationToken": json_data.get('validationToken')}), 200

    if event_type == "ping":
        logging.info(f"Ping event received. returning pong")
        return jsonify({"message": "pong"}), 200

    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)

    if event_type in ["transcription_creation", "transcription_processing", "transcription_completion", "transcription_deletion"]:
        logging.info(f"Transcription event received: {event_type}")
        entity_url = json_data.get('_self')
        logging.info(f"Entity URL: {entity_url}")
        az_transcription_id = entity_url.split("/")[-1]
        logging.info(f"Transcription ID: {az_transcription_id}")
        transcription = transcription_handler.get_transcription_by_az_id(az_transcription_id)
        if not transcription:
            logging.error(f"Transcription with azure transcription id not found: {az_transcription_id}")
            return jsonify({'error': 'Transcription not found'}), 404

        az_transcription = api.transcriptions_get(az_transcription_id)
        transcription['az_transcription'] = az_transcription
        logging.info(f"Transcription: {az_transcription}")

    if event_type == "transcription_creation":
        transcription['az_log'] = transcription.get("az_log", "") + "\n" + "transcription_creation"
        transcription_handler.update_transcription(transcription)
        return "", 200

    if event_type == "transcription_processing":
        logging.info(f"Transcription processing event received")
        transcription['az_log'] = transcription.get("az_log", "") + "\n" + "transcription_processing"
        transcription_handler.update_transcription(transcription)
        return "", 200
    
    if event_type == "transcription_completion":
        logging.info(f"Transcription completion event received")
        transcription['az_log'] = transcription.get("az_log", "") + "\n" + "transcription_completion"
        transcription_handler.update_transcription(transcription)
        return "", 200
    
    logging.error(f"Unhandled event type: {event_type}")
    return jsonify({'error': f"Unhandled event type: {event_type}"}), 400

def handle_transcription_callback(transcription):
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)

    logging.info(f"Getting transcription: {transcription['az_transcription_id']}")
    az_transcription = api.transcriptions_get(transcription['az_transcription_id'])
    logging.info(f"Transcription: {az_transcription}")

    recording = recording_handler.get_recording(transcription['recording_id'])
    if not recording:
        logging.error(f"Recording not found: {transcription['recording_id']}")
        return jsonify({'error': 'Recording not found'}), 404

    if status == 'completed':
        logging.info(f"AssemblyAI transcription completed: {transcription_id}")
        recording['transcription_status'] = TranscribingStatus.COMPLETED.value
        recording['transcription_status_updated_at'] = datetime.now(UTC).timestamp()
        transcription['aai_transcript_id'] = transcript_id

    else:
        logging.error(f"AssemblyAI transcription failed: {transcription_id}")
        recording['transcription_status'] = TranscribingStatus.FAILED.value
        recording['transcription_status_updated_at'] = datetime.now(UTC).timestamp()
        return jsonify({'error': 'Transcription failed'}), 500
    

    # get the transcript from AssemblyAI
    aai.settings.api_key = config.ASSEMBLYAI_API_KEY
    transcript = aai.Transcript.get_by_id(transcript_id)
    if not transcript:
        logging.error(f"Transcript not found: {transcript_id}")
        return jsonify({'error': 'Transcript not found'}), 404

    logging.info(f"Transcript: {transcript}")
    
    transcription['text'] = transcript.text
    transcription['diarized_transcript'] = az_get_diarized_transcript(transcript)
    # save the transcript to Cosmos DB
    transcription_handler.update_transcription(transcription)
    recording_handler.update_recording(recording)
    


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

"""
If the property secret in the configuration is present and contains a non-empty string, it will be used to create a SHA256 hash of the payload with  
the secret as HMAC key. This hash will be set as X-MicrosoftSpeechServices-Signature header when calling back into the registered URL.                
When calling back into the registered URL, the request will contain a X-MicrosoftSpeechServices-Event header containing one of the registered event  
types. There will be one request per registered event type.                After successfully registering the web hook, it will not be usable until a 
challenge/response is completed. To do this, a request with the event type  challenge will be made with a query parameter called validationToken. 
Respond to the challenge with a 200 OK containing the value of the validationToken  query parameter as the response body. When the challenge/response 
is successfully completed, the web hook will begin receiving events.  # noqa: E501
"""

def set_webhook(url):
    logging.info(f"Setting webhook: {url}")
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechWebHooksApi(client)
    
    #first get the list of webhooks
    webhooks = api.web_hooks_list()
    logging.info(f"Webhooks: {webhooks}")

    for webhook in az_paginate(api, webhooks):
        if webhook.web_url == url:
            logging.info(f"Webhook already exists: {webhook.web_url}")
            return
    
    #create the webhook
    webhook = swagger_client.WebHook(
        web_url=url,
        display_name="Quickscribe webhook",
        description="Quickscribe transcription callback webhook",
        events = swagger_client.WebHookEvents(
            transcription_completion=True, 
            transcription_creation=True, 
            transcription_processing=True, 
            transcription_deletion=True,
        )
    )

    logging.info(f"Creating webhook: {webhook}")
    api_response = api.web_hooks_create(webhook)
    logging.info(f"Webhook created: {api_response}")


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

#DEFUNT - only here as a reference...  Why would there be multiple transcriptions with the same id?
def az_get_transcript(transcription_id): 
    logging.info(f"Getting transcript: {transcription_id}")
    configuration = swagger_client.Configuration()
    configuration.api_key["Ocp-Apim-Subscription-Key"] = config.AZURE_SPEECH_SERVICES_KEY
    configuration.host = f"https://{config.AZURE_SPEECH_SERVICES_REGION}.api.cognitive.microsoft.com/speechtotext/v3.2"

    client = swagger_client.ApiClient(configuration)
    api = swagger_client.CustomSpeechTranscriptionApi(api_client=client)

    transcription = api.transcriptions_get(transcription_id)
    logging.info(f"Transcript: {transcription}")
    if transcription.status == "Succeeded":
        pag_files = api.transcriptions_list_files(transcription_id)
        for file_data in az_paginate(api, pag_files):
            if file_data.kind != "Transcription":
                continue
            logging.info(f"File data: {file_data}")
            results_url = file_data.links.content_urls[0]
            logging.info(f"Results URL: {results_url}")
            results = requests.get(results_url)
            logging.info(f"Results for {transcription_id}:\n{results.content.decode('utf-8')}")
            return results.content.decode('utf-8')


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

    # Print the formatted transcript
    for line in transcript:
        print(line)
