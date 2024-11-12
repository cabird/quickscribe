from flask import Flask, render_template, request, jsonify, g, send_from_directory    
import os
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from db_handlers.user_handler import UserHandler
from db_handlers.recording_handler import RecordingHandler
from db_handlers.transcription_handler import TranscriptionHandler
from datetime import datetime, UTC
from routes.az_transcription_routes import az_transcription_bp, check_in_progress_transcription
from routes.api import api_bp
from api_version import API_VERSION
import logging
from user_util import get_user
from config import config
import auth

from util import jinja2_escapejs_filter, get_recording_duration_in_seconds, format_duration, ellide, convert_to_mp3
from db_handlers.handler_factory import get_recording_handler, get_transcription_handler, get_user_handler
import time
import logging

load_dotenv()

app = Flask(__name__, static_folder='frontend-dist', static_url_path=None)
app.secret_key = config.SECRET_KEY
app.config['PREFERRED_URL_SCHEME'] = 'https'

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

@app.route('/auth/login')
def login():
    return auth.login()

@app.route('/auth/callback')
def callback():
    return auth.handle_auth_callback()

#@app.route("/", defaults={'path': ''})
#@app.route("/<path:path>")
@app.route("/<path:path>", endpoint='catch_all')
def serve_static(path):
    logging.info(f"received request for: {path}")
    if path.startswith( ("auth/", "api/", "az_transcription/") ):
        logging.info(f"API route detected, returning 404")
        return jsonify({"error": "Not found"}), 404  # Optional: Provide a custom error or redirect

    # Check for static assets
    static_file_path = os.path.join(app.static_folder, path)
    logging.info(f"static_file_path: {static_file_path}")
    if path != "" and os.path.exists(static_file_path):
        logging.info(f"Serving static file from: {static_file_path}")
        return send_from_directory(app.static_folder, path)
    else:
        logging.info(f"Not serving static file from: {static_file_path}")

    # For all other routes, including /view_transcription/*, return index.html
    logging.info(f"Serving index.html for client-side routing at path: {path}")
    return send_from_directory(app.static_folder, "index.html")
        
#Add a separate root route
@app.route("/")
def serve_root():
    logging.info(f"serving root route")
    return send_from_directory(app.static_folder, "index.html")

# Add this right before `if __name__ == '__main__':`
print("Registered routes:")
for rule in app.url_map.iter_rules():
    print(rule)

if __name__ == '__main__':
    app.run(debug=True)
