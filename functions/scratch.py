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

load_dotenv()

COSMOS_URL = os.environ["COSMOS_URL"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
COSMOS_DB_NAME = os.environ["COSMOS_DB_NAME"]
COSMOS_CONTAINER_NAME = os.environ["COSMOS_CONTAINER_NAME"]

AZURE_RECORDING_BLOB_CONTAINER = os.environ["AZURE_RECORDING_BLOB_CONTAINER"]
AZURE_STORAGE_CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]

unique_filename = "040a2218-6431-4324-9d28-b620a3ff67de.mp3"

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
# Generate a SAS token for the blob
sas_token = generate_blob_sas(
    account_name=blob_service_client.account_name,
    container_name=AZURE_RECORDING_BLOB_CONTAINER,
    blob_name=unique_filename,
    account_key=blob_service_client.credential.account_key,
    permission=BlobSasPermissions(read=True),
    expiry=datetime.utcnow() + timedelta(hours=1)  # Expiry time for the SAS token
)

# Construct the full SAS URL
blob_sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_RECORDING_BLOB_CONTAINER}/{unique_filename}?{sas_token}"

print(f"SAS URL: {blob_sas_url}")

