import azure.functions as func
import json
import os
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import hashlib
from dotenv import load_dotenv
from api_version import API_VERSION
from shared.transcription_handler import TranscriptionHandler, TranscribingStatus
from shared.recording_handler import RecordingHandler
from datetime import datetime, timedelta
import assemblyai as aai
import asyncio

load_dotenv()
app = func.FunctionApp()

# add a logging handler that write to a file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('function_app.log')
logging.getLogger().addHandler(file_handler)

# Function to get secret from Key Vault
def get_secret(secret_name):
    #key_vault_name = os.environ["KEY_VAULT_NAME"]
    key_vault_name = "QuickScribeKeyVault"
    key_vault_uri = f"https://{key_vault_name}.vault.azure.net"
    
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=key_vault_uri, credential=credential)
    
    retrieved_secret = client.get_secret(secret_name)
    return retrieved_secret.value

# get the api version
@app.route(route="api_version", auth_level=func.AuthLevel.ANONYMOUS)
def api_version(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(API_VERSION, status_code=200)

COSMOS_URL = os.environ["COSMOS_URL"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
COSMOS_DB_NAME = os.environ["COSMOS_DB_NAME"]
COSMOS_CONTAINER_NAME = os.environ["COSMOS_CONTAINER_NAME"]

AZURE_RECORDING_BLOB_CONTAINER = os.environ["AZURE_RECORDING_BLOB_CONTAINER"]
AZURE_STORAGE_CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]


# Async function to handle the transcription process in the background
async def transcribe_recording_async(recording_id, user_id):
    logging.info('Transcribing recording asynchronously')

    recording_handler = RecordingHandler(COSMOS_URL, COSMOS_KEY, COSMOS_DB_NAME, COSMOS_CONTAINER_NAME)
    transcription_handler = TranscriptionHandler(COSMOS_URL, COSMOS_KEY, COSMOS_DB_NAME, COSMOS_CONTAINER_NAME)

    logging.info(f"Getting recording details: {recording_id}")
    # Get the recording details and ensure it exists and belongs to the user
    recording = recording_handler.get_recording(recording_id)
    if not recording or recording['user_id'] != user_id:
        #TODO - log this... how do we handle this in the frontend?
        logging.error(f"Recording not found or does not belong to the user: {recording_id} {user_id}")
        return func.HttpResponse("Recording not found or does not belong to the user", status_code=404)
    
    logging.info(f"Recording found: {recording}")
    
    
    transcription = transcription_handler.get_transcription_by_recording(recording_id)
    if transcription and transcription['status'] in [TranscribingStatus.IN_PROGRESS.value, TranscribingStatus.COMPLETED.value]:
        #TODO - log this... how do we handle this in the frontend?
        logging.error(f"Transcription already exists or in progress for this recording: {recording_id}")
        return func.HttpResponse("Transcription already exists or in progress for this recording", status_code=400)

    if not transcription:
        logging.info(f"No transcription found, creating new transcription")
        transcription = transcription_handler.create_transcription(user_id, recording_id)
    else:
        logging.info(f"Transcription found: {transcription}")

    logging.info(f"Updating transcription status to IN_PROGRESS: {transcription['id']}")
    transcription['status'] = TranscribingStatus.IN_PROGRESS.value
    transcription_handler.update_transcription(transcription)

    try:
        # Generate a SAS URL for the blob (the recording file)
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        sas_token = generate_blob_sas(
            account_name=blob_service_client.account_name,
            container_name=AZURE_RECORDING_BLOB_CONTAINER,
            blob_name=recording['unique_filename'],
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        blob_sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_RECORDING_BLOB_CONTAINER}/{recording['unique_filename']}?{sas_token}"
        logging.info(f"SAS URL generated: {blob_sas_url}")
        
        # Call the long-running AssemblyAI transcription function asynchronously
        logging.info(f"Calling AssemblyAI transcription function: {transcription['id']}")
        transcription_id = transcription['id']
        await do_assemblyai_transcription(blob_sas_url, transcription_id)
        
    except Exception as e:
        logging.error(f"Failed to generate SAS URL: {e}")
        transcription['status'] = TranscribingStatus.FAILED.value
        transcription['error'] = str(e)
        transcription_handler.update_transcription(transcription)

# Update the main route to trigger the async transcription
@app.route(route="transcribe_recording", auth_level=func.AuthLevel.FUNCTION)
async def transcribe_recording(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Received request to transcribe recording')

    #output the request body
    logging.info(f"Request body: {req.get_body()}")

    recording_id = None
    user_id = None

    try:
        req_body = req.get_json()
        recording_id = req_body.get('recording_id')
        user_id = req_body.get('user_id')
    except ValueError:
        pass


    if not recording_id or not user_id:
        return func.HttpResponse("Recording ID and user ID are required", status_code=400)

    # Fire off the transcription task asynchronously and return immediately
    asyncio.create_task(transcribe_recording_async(recording_id, user_id))

    return func.HttpResponse("Transcription started", status_code=202)

# Async transcription function (AssemblyAI call)
async def do_assemblyai_transcription(blob_sas_url, transcription_id):
    logging.info(f"Starting AssemblyAI transcription: {transcription_id}")
    ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")
    if not ASSEMBLYAI_API_KEY:
        logging.error("ASSEMBLYAI_API_KEY not set")
        return

    aai.settings.api_key = ASSEMBLYAI_API_KEY
    logging.info(f"AssemblyAI API key set: {ASSEMBLYAI_API_KEY}")
    transcriber = aai.Transcriber()
    logging.info(f"Transcriber created")
    config = aai.TranscriptionConfig(
        
        speaker_labels=True,
        language_code="en"
    )

    transcription_handler = TranscriptionHandler(COSMOS_URL, COSMOS_KEY, COSMOS_DB_NAME, COSMOS_CONTAINER_NAME)
    transcription = transcription_handler.get_transcription(transcription_id)

    try:
        # Call the transcription service asynchronously
        logging.info(f"Calling AssemblyAI transcription service: with url {blob_sas_url}")
        transcript = transcriber.transcribe(blob_sas_url, config=config)

        if transcript.error:
            transcription['status'] = TranscribingStatus.FAILED.value
            transcription['error'] = str(transcript.error)
            transcription_handler.update_transcription(transcription)
            logging.error(f"Error transcribing recording: {transcript.error}")
        else:
            transcription['status'] = TranscribingStatus.COMPLETED.value
            transcription['transcript'] = transcript.text
            transcription_handler.update_transcription(transcription)
            logging.info(f"Transcription completed for {transcription_id}")

    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        transcription['status'] = TranscribingStatus.FAILED.value
        transcription['error'] = str(e)
        transcription_handler.update_transcription(transcription)

@app.route(route="test_key_vault", auth_level=func.AuthLevel.FUNCTION)
def test_key_vault(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to retrieve secret from Key Vault.')

    # Retrieve secret name from query parameters or request body
    secret_name = req.params.get('secret_name')
    if not secret_name:
        try:
            req_body = req.get_json()
            secret_name = req_body.get('secret_name')
        except (ValueError, KeyError):
            pass

    if not secret_name:
        return func.HttpResponse(
            "Please pass a secret name in the query string or request body",
            status_code=400
        )

    try:
        # Retrieve the secret from Key Vault using the helper function
        secret_value = get_secret(secret_name)
        # share the md5sum of the secret value, but not the secret value itself
        md5sum = hashlib.md5(secret_value.encode()).hexdigest()
        return func.HttpResponse(f"md5sum of secret value: {md5sum}", status_code=200)
    except Exception as e:
        logging.error(f"Failed to retrieve secret: {e}")
        return func.HttpResponse(f"Failed to retrieve secret: {str(e)}", status_code=500)

@app.route(route="test", auth_level=func.AuthLevel.ANONYMOUS)
def test(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
            
@app.route(route="test_with_auth", auth_level=func.AuthLevel.FUNCTION)
def test_with_auth(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )