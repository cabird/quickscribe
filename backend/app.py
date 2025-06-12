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
from routes.plaud import plaud_bp
from routes.ai_routes import ai_bp
from routes.local_routes import local_bp
from routes.admin import admin_bp
from routes.participant_routes import participant_bp
from api_version import API_VERSION
from user_util import get_current_user
from config import config
import auth
import logging

import time
# Import our custom logging configuration
from logging_config import get_logger

load_dotenv()

# Module-level variables for shared resources
blob_service_client = None
cosmos_client = None
cosmos_database = None
cosmos_container = None
app_logger = None

TRANSCRIPTION_IN_PROGRESS_TIMEOUT_SECONDS = 24 * 60 * 60 * 30  # 30 days

def create_app(test_config=None):
    """Application factory function for Flask app."""
    global blob_service_client, cosmos_client, cosmos_database, cosmos_container, app_logger
    
    app = Flask(__name__, static_folder='frontend-dist', static_url_path=None)
    
    # Load configuration
    if test_config is None:
        # Load production/development config
        app.secret_key = config.SECRET_KEY
        app.config['PREFERRED_URL_SCHEME'] = 'https'
    else:
        # Load test configuration
        app.config.update(test_config)
    
    # Create a context processor to make API_VERSION available globally
    @app.context_processor
    def inject_api_version():
        return dict(api_version=API_VERSION)
    
    # Configure basic logging for compatibility
    logging.basicConfig(level=logging.INFO)
    # Set logging level for Azure SDK components to suppress headers
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    
    # Initialize our application logger with Azure Application Insights
    app_logger = get_logger('app', API_VERSION)
    app_logger.info(f"Starting QuickScribe backend ({API_VERSION})")
    
    # Register blueprints
    app.register_blueprint(az_transcription_bp, url_prefix='/az_transcription')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(plaud_bp, url_prefix='/plaud')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(local_bp, url_prefix='/api/local')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(participant_bp, url_prefix='/api/participants')
    
    # Initialize Azure services only if not in testing mode
    if not app.config.get('TESTING'):
        try:
            # Initialize the BlobServiceClient
            blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
            
            # Initialize Cosmos DB client
            cosmos_client = CosmosClient(config.COSMOS_URL, credential=config.COSMOS_KEY)
            cosmos_database = cosmos_client.get_database_client(config.COSMOS_DB_NAME)
            cosmos_container = cosmos_database.get_container_client(config.COSMOS_CONTAINER_NAME)
        except Exception as e:
            app_logger.error(f"Failed to initialize Azure services: {e}")
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app):
    """Register all Flask routes."""

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
        if path.startswith( ("auth/", "api/", "az_transcription/", "plaud/") ):
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

# Create the application instance
app = create_app()

# Add this right before `if __name__ == '__main__':`
if not app.config.get('TESTING'):
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(rule)

if __name__ == '__main__':
    app.run(debug=True)
