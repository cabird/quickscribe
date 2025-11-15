"""
Wrapper module for blob storage operations using shared_quickscribe_py library.
This maintains backward compatibility with existing route code.
"""
from typing import Dict, List
from config import config
from shared_quickscribe_py.azure_services import BlobStorageClient, send_transcoding_job

import logging
logging.basicConfig(level=logging.INFO)

# Create a singleton blob storage client for the recordings container
_blob_client = None

def _get_blob_client() -> BlobStorageClient:
    """Get or create the blob storage client singleton."""
    global _blob_client
    if _blob_client is None:
        _blob_client = BlobStorageClient(
            config.AZURE_STORAGE_CONNECTION_STRING,
            config.AZURE_RECORDING_BLOB_CONTAINER
        )
    return _blob_client


def store_recording_as_blob(file_path, blob_filename):
    """Upload a file to blob storage."""
    client = _get_blob_client()
    client.upload_file(file_path, blob_filename)


def save_blob_to_local_file(blob_filename, local_file_path):
    """Download a blob to a local file."""
    client = _get_blob_client()
    client.download_file(blob_filename, local_file_path)


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
    client = _get_blob_client()
    return client.generate_sas_url(filename, read=read, write=write, hours=24)


def send_to_transcoding_queue(recording_id: str, source_blob_filename: str, target_blob_filename: str, original_filename: str, user_id: str, callbacks: List[Dict[str, str]]):
    """Send a transcoding job to the queue."""
    send_transcoding_job(
        connection_string=config.AZURE_STORAGE_CONNECTION_STRING,
        queue_name=config.TRANSCODING_QUEUE_NAME,
        container_name=config.AZURE_RECORDING_BLOB_CONTAINER,
        recording_id=recording_id,
        source_blob_filename=source_blob_filename,
        target_blob_filename=target_blob_filename,
        original_filename=original_filename,
        user_id=user_id,
        callbacks=callbacks
    )


def delete_recording_blob(filename):
    """Delete a blob file from Azure Storage"""
    client = _get_blob_client()
    client.delete_blob(filename)
    