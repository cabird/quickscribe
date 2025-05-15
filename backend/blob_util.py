from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.storage.queue import QueueClient
from datetime import datetime, timedelta
from config import config
import json

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

def send_to_transcoding_queue(source_blob_filename, target_blob_filename, original_filename, user_id):
    queue_client = QueueClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING, config.TRANSCODING_QUEUE_NAME)
    # the assumption is that these are in the recordings container of the storage account, found in config.AZURE_RECORDING_BLOB_CONTAINER
    obj = {
        "source_blob_filename": source_blob_filename,
        "target_blob_filename": target_blob_filename,
        "original_filename": original_filename,
        "user_id": user_id
    }
    queue_client.send_message(json.dumps(obj))
    