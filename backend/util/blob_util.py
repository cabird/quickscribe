from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import os

def generate_recording_sas_url(filename):
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_RECORDING_BLOB_CONTAINER = os.getenv("AZURE_RECORDING_BLOB_CONTAINER")
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_RECORDING_BLOB_CONTAINER:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING or AZURE_RECORDING_BLOB_CONTAINER not set in environment variables")

    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=AZURE_RECORDING_BLOB_CONTAINER,
        blob_name=filename,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    blob_sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{AZURE_RECORDING_BLOB_CONTAINER}/{filename}?{sas_token}"
    return blob_sas_url
    