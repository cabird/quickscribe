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
from db_handlers.user_handler import UserHandler
from db_handlers.recording_handler import RecordingHandler
from db_handlers.transcription_handler import TranscriptionHandler, TranscribingStatus
import uuid
from datetime import datetime, timedelta
from routes.transcription_routes import transcription_bp
from blob_util import store_recording, generate_recording_sas_url
from api_version import API_VERSION
import logging
from user_util import get_user
from config import config

load_dotenv()

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
socketio = SocketIO(app)

logging.basicConfig(level=logging.INFO)
logging.info("Starting QuickScribe Web App")


app.register_blueprint(transcription_bp, url_prefix='/transcription')

# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)

# Initialize Cosmos DB client
cosmos_client = CosmosClient(config.COSMOS_URL, credential=config.COSMOS_KEY)
cosmos_database = cosmos_client.get_database_client(config.COSMOS_DB_NAME)
cosmos_container = cosmos_database.get_container_client(config.COSMOS_CONTAINER_NAME)

# Landing page route
@app.route('/')
def index():
    return render_template('index.html', api_version=API_VERSION)


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
            store_recording(file_path, unique_filename)

            socketio.emit('status', {'message': f'File uploaded to Azure Blob Storage complete...'})
            recording_handler = RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
            user = get_user(request)
            recording_handler.create_recording(user['id'], original_filename, unique_filename)

            return jsonify({'message': 'File uploaded successfully!', 'filename': original_filename}), 200

        except Exception as e:
            #print the stack trace
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Only .mp3 files are allowed'}), 400


# Route to list all uploaded files
@app.route('/recordings')
def list_recordings():
    try:
        user = get_user(request)
        # Get all file metadata from Cosmos DB
        recording_handler = RecordingHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
        recordings = recording_handler.get_user_recordings(user['id'])
        transcription_handler = TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)

        recording_data = []
        for recording in recordings:
            unique_filename = recording['unique_filename']

            # Get blob properties (size) from Azure Blob Storage
            blob_client = blob_service_client.get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=unique_filename)
            blob_properties = blob_client.get_blob_properties()

            transcription = transcription_handler.get_transcription_by_recording(recording['id'])
            if not transcription:
                status = '<a href="/transcription/start_transcription/{}">Start Transcription</a>'.format(recording['id'])
            elif transcription['transcription_status'] == TranscribingStatus.IN_PROGRESS.value:
                status = 'In Progress'
            elif transcription['transcription_status'] == TranscribingStatus.COMPLETED.value:
                status = '<a href="/view_transcription/{}">View Transcription</a>'.format(transcription['id'])
            elif transcription['transcription_status'] == TranscribingStatus.FAILED.value:
                status = 'Failed'
            elif transcription['transcription_status'] == TranscribingStatus.NOT_STARTED.value:
                status = '<a href="/transcription/start_transcription/{}">Start Transcription</a>'.format(recording['id'])
            else:
                status = f"Unknown status: {transcription['status']}"

            # Prepare the data for rendering
            recording_info = {
                'original_filename': recording['original_filename'],
                'unique_filename': unique_filename,
                'file_size': blob_properties.size,  # Get file size in bytes
                'download_url': generate_recording_sas_url(unique_filename),
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

@app.route("/view_transcription/<transcription_id>")
def view_transcription(transcription_id):
    """View the transcription for a given transcription ID."""
    transcription_handler = TranscriptionHandler(config.COSMOS_URL, config.COSMOS_KEY, config.COSMOS_DB_NAME, config.COSMOS_CONTAINER_NAME)
    transcription = transcription_handler.get_transcription(transcription_id)
    
    if transcription:
        # Render a template to display the transcription text
        return render_template('view_transcription.html', transcription=transcription)
    else:
        return "Transcription not found", 404



if __name__ == '__main__':
    app.run(debug=True)
