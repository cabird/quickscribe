from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
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
from db_handlers.transcription_handler import TranscriptionHandler
from db_handlers.models import TranscriptionStatus
import uuid
from datetime import datetime, timedelta, UTC
from routes.az_transcription_routes import az_transcription_bp, check_in_progress_transcription
from routes.api import api_bp
from blob_util import store_recording, generate_recording_sas_url
from api_version import API_VERSION
import logging
from user_util import get_user
from config import config
import auth
from llms import get_speaker_mapping
import jinja2
from util import jinja2_escapejs_filter, get_recording_duration_in_seconds, format_duration, ellide, convert_to_mp3
from db_handlers.handler_factory import get_recording_handler, get_transcription_handler, get_user_handler
import time
import logging

load_dotenv()

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['PREFERRED_URL_SCHEME'] = 'https'

app.jinja_env.filters['escapejs'] = jinja2_escapejs_filter
app.jinja_env.filters['ellide'] = ellide

# Create a context processor to make API_VERSION available globally
@app.context_processor
def inject_api_version():
    return dict(api_version=API_VERSION)

logging.basicConfig(level=logging.INFO)
# Set logging level for Azure SDK components to suppress headers
# TODO - could move this to an environment variable
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.info("Starting QuickScribe Web App")

TRANSCRIPTION_IN_PROGRESS_TIMEOUT_SECONDS = 24 * 60 * 60 * 30 # 30 days

app.register_blueprint(az_transcription_bp, url_prefix='/az_transcription')
app.register_blueprint(api_bp, url_prefix='/api')

# Initialize the BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)

# Initialize Cosmos DB client
cosmos_client = CosmosClient(config.COSMOS_URL, credential=config.COSMOS_KEY)
cosmos_database = cosmos_client.get_database_client(config.COSMOS_DB_NAME)
cosmos_container = cosmos_database.get_container_client(config.COSMOS_CONTAINER_NAME)


# Landing page route
@app.route('/')
def index():
    if config.RUNNING_IN_CONTAINER:
        user = auth.get_user()
        return render_template('index.html', api_version=API_VERSION, user=user)
    else:
        user = get_user(request)
        return render_template('index.html', api_version=API_VERSION)

@app.route('/login')
def login():
    return auth.login()

@app.route('/auth/callback')
def callback():
    return auth.handle_auth_callback()


@app.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html')

# File upload form route
@app.route('/upload', methods=['POST'])
def upload():
    logging.info("upload endpoint called")
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file: # and (file.filename.endswith('.mp3') or file.filename.endswith('.m4a')):
        logging.info("file found")
        try:
            original_filename = secure_filename(file.filename)
            #get the file extension
            file_extension = file.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            logging.info(f"unique_filename: {unique_filename}")
            file_path = os.path.join('/tmp', unique_filename)
            file.save(file_path)
            logging.info(f"file saved to {file_path}")
            #if the file is an m4a, convert it to mp3
            mp3_file_path = file_path
            if file_extension.lower() == "m4a":
                logging.info("converting m4a to mp3")
                start_time = time.time()
                try:
                    mp3_file_path = convert_to_mp3(file_path)
                except Exception as e:
                    logging.error(f"error converting m4a to mp3: {e}")
                    return jsonify({'error': str(e)}), 500
                end_time = time.time()
                logging.info(f"converted m4a to mp3 and saved to {mp3_file_path} in {end_time - start_time} seconds")
                # change the extension on unique_filename
                unique_filename = unique_filename.replace(".m4a", ".mp3")

            store_recording(mp3_file_path, unique_filename)
            recording_handler = get_recording_handler()
            user = get_user(request)

            recording = recording_handler.create_recording(user.id, original_filename, unique_filename)
            recording.upload_timestamp = datetime.now(UTC).isoformat()
            # determine the duration of the recording
            recording.duration = get_recording_duration_in_seconds(mp3_file_path)
            recording_handler.update_recording(recording)

            #remove the file(s) from the tmp directory
            os.remove(file_path)
            if mp3_file_path != file_path:
                os.remove(mp3_file_path)

            return jsonify({'message': 'File uploaded successfully!', 'filename': original_filename, 'recording_id': recording.id}), 200

        except Exception as e:
            logging.error(f"error uploading file: {e}")
            #print the stack trace
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Only .mp3 and .m4a files are allowed'}), 400


# Route to list all uploaded files
@app.route('/recordings')
def recordings():
    try:
        user = get_user(request)
        # Get all file metadata from Cosmos DB
        recording_handler = get_recording_handler()
        recordings = recording_handler.get_user_recordings(user.id)
        transcription_handler = get_transcription_handler()

        recording_data = []
        for recording in recordings:
            error_message = ""
            unique_filename = recording.unique_filename

            if not recording.transcription_status:
                recording.transcription_status = TranscriptionStatus.not_started
                recording_handler.update_recording(recording)

            # if the transcription status is in progress, then check how long it has been in progress
            if recording.transcription_status == TranscriptionStatus.in_progress:
                logging.info(f"transcription status is in progress for recording {recording.id}")
                # if the transcription status updated at is not in the recording, then set it to the current timestamp
                # and eventually the transcription status will be updated to either failed or completed
                if not recording.transcription_status_updated_at:
                    recording.transcription_status_updated_at = datetime.now(UTC).isoformat()
                
                # if the recording is in progress, then it better have an az_transcription_id
                if recording.az_transcription_id:
                    status, az_error_message = check_in_progress_transcription(recording)
                    if status == "Succeeded":
                        recording.transcription_status = TranscriptionStatus.completed
                        recording.transcription_error_message = ""   
                        recording_handler.update_recording(recording)
                    if status == "Failed":
                        recording.transcription_status = TranscriptionStatus.failed
                        recording.transcription_error_message = az_error_message
                        error_message = f"Transcription failed: {az_error_message}"
                        logging.error(error_message)
                        recording_handler.update_recording(recording)
                    

                else:
                    logging.warning(f"recording {recording.id} is in progress but does not have an az_transcription_id")
                

                transcription_time = datetime.fromisoformat(recording.transcription_status_updated_at)
                # check if transcription time is offset-aware and fix it if it is not
                if transcription_time.tzinfo is None:
                    transcription_time = transcription_time.replace(tzinfo=UTC)
                duration_in_progress = datetime.now(UTC) - transcription_time
                if duration_in_progress.total_seconds() > TRANSCRIPTION_IN_PROGRESS_TIMEOUT_SECONDS:
                    logging.info(f"duration in progress is greater than {TRANSCRIPTION_IN_PROGRESS_TIMEOUT_SECONDS} seconds, setting transcription status to failed")
                    recording.transcription_status = TranscriptionStatus.failed
                    recording_handler.update_recording(recording)


            if recording.duration:
                duration_str = format_duration(recording.duration)
            else:
                duration_str = "unknown"

            # Get blob properties (size) from Azure Blob Storage
            blob_client = blob_service_client.get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=unique_filename)
            blob_properties = blob_client.get_blob_properties()

            transcription = transcription_handler.get_transcription_by_recording(recording.id)
            
            text = transcription.diarized_transcript if transcription and transcription.diarized_transcript else transcription.text if transcription else ""
            # Prepare the data for rendering
            recording_info = {
                'transcription_status': recording.transcription_status.value,
                'original_filename': recording.original_filename,
                'unique_filename': unique_filename,
                'file_size': blob_properties.size,  # Get file size in bytes
                'download_url': generate_recording_sas_url(unique_filename),
                'recording_id': recording.id,
                'transcription_id': transcription.id if transcription else -1,
                'speaker_names_inferred':True if transcription and transcription.speaker_mapping else False,
                'duration': duration_str,
                'transcription_text': text,
                'transcription_error_message': recording.transcription_error_message if recording.transcription_error_message else ""
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


@app.route("/infer_speaker_names/<transcription_id>")
def infer_speaker_names(transcription_id):
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    if transcription and transcription.diarized_transcript:
        if True: # TODO - uncomment this when we don't want to allow inferring multiple times... not transcription.speaker_mapping:
            speaker_mapping, diarized_text = get_speaker_mapping(transcription.diarized_transcript)
            transcription.speaker_mapping = speaker_mapping
            transcription.diarized_transcript = diarized_text
            transcription_handler.update_transcription(transcription)
            flash("Speaker names successfully inferred", "success")
        else:
            # redirect to recordings page, but flash the message that we already inferred the speaker names
            flash("Speaker names already inferred", "info")
    else:
        flash("Transcription not found", "error")
    return redirect(url_for('recordings'))

@app.route("/view_transcription/<transcription_id>")
def view_transcription(transcription_id):
    """View the transcription for a given transcription ID."""
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription(transcription_id)
    recording_handler = get_recording_handler()
    recording = recording_handler.get_recording(transcription.recording_id)
    
    if transcription:
        # Render a template to display the transcription text
        return render_template('view_transcription.html', transcription=transcription, recording=recording)
    else:
        return "Transcription not found", 404
        
@app.route("/delete_recording/<recording_id>")
def delete_recording(recording_id):
    recording_handler = get_recording_handler()
    recording = recording_handler.get_recording(recording_id)
    #check if there is a transcription for this recording
    transcription_handler = get_transcription_handler()
    transcription = transcription_handler.get_transcription_by_recording(recording_id)
    if transcription:
        #delete the transcription
        transcription_handler.delete_transcription(transcription.id)
        flash("Transcription deleted successfully", "success")
        if recording:
            recording.transcription_status = TranscriptionStatus.not_started
            recording_handler.update_recording(recording)
    elif recording:
        recording_handler.delete_recording(recording_id)
        flash("Recording deleted successfully", "success")
    else:
        flash("Recording not found", "error")
    return redirect(url_for('recordings'))


if __name__ == '__main__':
    app.run(debug=True)
