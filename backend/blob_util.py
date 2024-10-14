from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from config import config



def store_recording(file_path, blob_filename):
    blob_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING).get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=blob_filename)
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data)

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
    