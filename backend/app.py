from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
import os
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from azure.cosmos import CosmosClient, PartitionKey
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from shared.user_handler import UserHandler
from shared.recording_handler import RecordingHandler
from shared.transcription_handler import TranscriptionHandler, TranscribingStatus
import uuid
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
# todo - make this a random key and store it somewhere like in a keyvault
app.secret_key = 'supersecretkey'
socketio = SocketIO(app)

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

cosmos_client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
cosmos_database = cosmos_client.get_database_client(DATABASE_NAME)
cosmos_container = cosmos_database.get_container_client(CONTAINER_NAME)


def get_user(request):
    # Try to get the user_id from cookies
    user_id = request.cookies.get('user_id')

    user_handler = UserHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)

    if user_id:
        # Fetch user by ID if the user_id exists in the cookie
        user = user_handler.get_user(user_id)
    else:
        # If no user_id in cookie, fetch user by name 'cbird'
        users = user_handler.get_user_by_name('cbird')
        user = users[0] if users else None  # Assuming 'cbird' is unique, take the first result

    return user

# Helper function to get secret from Azure Key Vault
def get_secret(secret_name):
    key_vault_name = os.environ["KEY_VAULT_NAME"]
    key_vault_uri = f"https://{key_vault_name}.vault.azure.net"

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=key_vault_uri, credential=credential)
    
    secret = client.get_secret(secret_name)
    return secret.value

# Landing page route
@app.route('/')
def index():
    return render_template('index.html')

# Route to call the Azure Functions app's test function
@app.route('/call-function')
def call_function():
    try:
        # Call the Azure Functions app's test function
        function_url = "https://quickscribefunctionapp.azurewebsites.net/api/test"
        response = requests.get(function_url, params={"name": "Chris"})
        
        if response.status_code == 200:
            return f"Function call successful! Response: {response.text}"
        else:
            return f"Failed to call function. Status code: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

# Route to call the Azure Functions app's test function
@app.route('/call-function-with-auth')
def call_function_with_auth():
    try:
        # Get the function key from Key Vault
        function_key = get_secret("AzureFunctionKey")
        
        # Call the Azure Functions app's test function
        function_url = "https://quickscribefunctionapp.azurewebsites.net/api/test_with_auth"
        headers = {"x-functions-key": function_key}
        params = {"name": "Chris"}
        response = requests.get(function_url, params=params, headers=headers)
        
        if response.status_code == 200:
            return f"Function call with auth successful! Response: {response.text}"
        else:
            return f"Failed to call function with auth. Status code: {response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"
@app.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html')

# File upload form route
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and file.filename.endswith('.mp3'):
        try:
            original_filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}.mp3"
            print(f"unique_filename: {unique_filename}")

            # TODO - figure out where this should really be saved...
            file_path = os.path.join('/tmp', unique_filename)
            file.save(file_path)
            print(f"file saved to {file_path}")
            socketio.emit('status', {'message': f'File downloaded to server...'})
            print("emitting status message: Uploading to Azure Blob Storage...")
            socketio.emit('status', {'message': f'Uploading to Azure Blob Storage...'})

            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER, blob=unique_filename)

            with open(file_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    content_settings=ContentSettings(
                        content_type='audio/mpeg',
                        content_disposition=f'attachment; filename={original_filename}'
                    )
                )

            socketio.emit('status', {'message': f'File uploaded to Azure Blob Storage complete...'})
            recording_handler = RecordingHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)
            user = get_user(request)
            recording_handler.create_recording(user['id'], original_filename, unique_filename)

            return jsonify({'message': 'File uploaded successfully!', 'filename': original_filename}), 200

        except Exception as e:
            #print the stack trace
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Only .mp3 files are allowed'}), 400




# Generate a SAS URL for downloading a file
def generate_download_url(blob_name):
    # Get the account key from environment variable
    account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_key:
        raise ValueError("Account key not set in environment variables")

    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=BLOB_CONTAINER,
        blob_name=blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1),  # 1-hour expiry
        account_key=account_key
    )

    # Construct the full URL with SAS token
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER}/{blob_name}?{sas_token}"
    return blob_url

# Route to list all uploaded files
@app.route('/recordings')
def list_recordings():
    try:
        user = get_user(request)
        # Get all file metadata from Cosmos DB
        recording_handler = RecordingHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)
        recordings = recording_handler.get_user_recordings(user['id'])
        transcription_handler = TranscriptionHandler(COSMOS_URL, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME)

        recording_data = []
        for recording in recordings:
            unique_filename = recording['unique_filename']

            # Get blob properties (size) from Azure Blob Storage
            blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER, blob=unique_filename)
            blob_properties = blob_client.get_blob_properties()

            transcription = transcription_handler.get_transcription_by_recording(recording['id'])
            if not transcription:
                status = '<a href="/start_transcription/{}">Start Transcription</a>'.format(recording['id'])
            elif transcription['transcription_status'] == 'in_progress':
                status = 'In Progress'
            elif transcription['transcription_status'] == 'completed':
                status = '<a href="/view_transcription/{}">View Transcription</a>'.format(transcription['id'])
            else:
                status = f"Unknown status: {transcription['transcription_status']}"

            # Prepare the data for rendering
            recording_info = {
                'original_filename': recording['original_filename'],
                'unique_filename': unique_filename,
                'file_size': blob_properties.size,  # Get file size in bytes
                'download_url': generate_download_url(unique_filename),
                'transcription_status': status  
            }
            recording_data.append(recording_info)

        return render_template('recordings.html', recordings=recording_data)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        #print the stack trace
        import traceback
        traceback.print_exc()
        #return the error message and the stack trace
        error_message = str(e)
        stack_trace = traceback.format_exc()
        return f"<pre>Error: {error_message}\n\nStack Trace:\n{stack_trace}</pre>"


@app.route("/start_transcription/<recording_id>", methods=["POST"])
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
    
    payload = {
        'user_id': user['id'],
        'recording_id': recording_id
    }
    function_url = "https://quickscribefunctionapp.azurewebsites.net/api/transcribe_recording"
    try:
        FUNCTIONS_KEY = os.environ.get("FUNCTIONS_KEY")
        if not FUNCTIONS_KEY:
            return jsonify({'error': 'FUNCTIONS_KEY not set in environment variables'}), 500
        headers = {"x-functions-key": FUNCTIONS_KEY}
        response = requests.post(function_url, json=payload, headers=headers)
        if response.status_code != 200:
            return jsonify({'error': 'Failed to start transcription'}), response.status_code
        else:
            return jsonify({'message': 'Transcription started successfully'}), 200
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        #print the stack trace
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

