from typing import Dict, List
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.storage.queue import QueueClient
from datetime import datetime, timedelta
from config import config
import json

import logging
logging.basicConfig(level=logging.INFO)

def store_recording_as_blob(file_path, blob_filename):
    blob_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING).get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=blob_filename)
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data)


def save_blob_to_local_file(blob_filename, local_file_path):
    blob_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING).get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=blob_filename)
    with open(local_file_path, "wb") as data:
        data.write(blob_client.download_blob().readall())

def generate_recording_sas_url(filename):
    blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=config.AZURE_RECORDING_BLOB_CONTAINER,
        blob_name=filename,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    blob_sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{config.AZURE_RECORDING_BLOB_CONTAINER}/{filename}?{sas_token}"
    return blob_sas_url

def generate_recording_sas_url(filename, read=True, write=False):
    """
    Generate a SAS URL for a blob with specified permissions.
    
    Args:
        filename: Name of the blob file
        read: Whether to allow read access
        write: Whether to allow write access
    
    Returns:
        SAS URL with the specified permissions
    """
    blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
    
    # Set permissions based on the parameter
    blob_permissions = BlobSasPermissions(read=read, write=write, create=write)

    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=config.AZURE_RECORDING_BLOB_CONTAINER,
        blob_name=filename,
        account_key=blob_service_client.credential.account_key,
        permission=blob_permissions,
        expiry=datetime.utcnow() + timedelta(days=1)
    )
    
    blob_sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{config.AZURE_RECORDING_BLOB_CONTAINER}/{filename}?{sas_token}"
    return blob_sas_url

def send_to_transcoding_queue(recording_id: str, source_blob_filename: str, target_blob_filename: str, original_filename: str, user_id: str, callbacks: List[Dict[str, str]]):
    logging.info(f"Sending transcoding request for recording ID: {recording_id} to queue: {config.TRANSCODING_QUEUE_NAME}")
    queue_client = QueueClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING, queue_name=config.TRANSCODING_QUEUE_NAME)

    source_sas_url = generate_recording_sas_url(source_blob_filename, read=True, write=False)
    target_sas_url = generate_recording_sas_url(target_blob_filename, read=True, write=True)

    # the assumption is that these are in the recordings container of the storage account, found in config.AZURE_RECORDING_BLOB_CONTAINER
    obj = {
        "action": "transcode",
        "recording_id": recording_id,
        "original_filename": original_filename,
        "user_id": user_id,
        "source_sas_url": source_sas_url,
        "target_sas_url": target_sas_url,
        "callbacks": callbacks
    }
    queue_client.send_message(json.dumps(obj))

def delete_recording_blob(filename):
    """Delete a blob file from Azure Storage"""
    blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(
        container=config.AZURE_RECORDING_BLOB_CONTAINER, 
        blob=filename
    )
    blob_client.delete_blob(delete_snapshots="include")
    