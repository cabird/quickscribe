"""
Azure Blob Storage operations for QuickScribe
"""
from typing import Dict, List
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.storage.queue import QueueClient
from datetime import datetime, timedelta, UTC
import json
import logging

logger = logging.getLogger(__name__)


class BlobStorageClient:
    """Client for Azure Blob Storage operations"""

    def __init__(self, connection_string: str, container_name: str):
        """
        Initialize the Blob Storage client.

        Args:
            connection_string: Azure Storage connection string
            container_name: Name of the blob container
        """
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    def upload_file(self, file_path: str, blob_filename: str) -> None:
        """
        Upload a file to blob storage.

        Args:
            file_path: Local path to the file to upload
            blob_filename: Name to use for the blob
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=blob_filename
        )
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        logger.info(f"Uploaded file {file_path} to blob {blob_filename}")

    def download_file(self, blob_filename: str, local_file_path: str) -> None:
        """
        Download a file from blob storage using streaming to minimize memory usage.

        Args:
            blob_filename: Name of the blob to download
            local_file_path: Local path where the file should be saved
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=blob_filename
        )
        with open(local_file_path, "wb") as data:
            stream = blob_client.download_blob()
            stream.readinto(data)
        logger.info(f"Downloaded blob {blob_filename} to {local_file_path}")

    def generate_sas_url(
        self, filename: str, read: bool = True, write: bool = False, hours: int = 24
    ) -> str:
        """
        Generate a SAS URL for a blob with specified permissions.

        Args:
            filename: Name of the blob file
            read: Whether to allow read access
            write: Whether to allow write access
            hours: Number of hours until the SAS token expires

        Returns:
            SAS URL with the specified permissions
        """
        # Set permissions based on the parameters
        blob_permissions = BlobSasPermissions(read=read, write=write, create=write)

        sas_token = generate_blob_sas(
            account_name=self.blob_service_client.account_name,
            container_name=self.container_name,
            blob_name=filename,
            account_key=self.blob_service_client.credential.account_key,
            permission=blob_permissions,
            expiry=datetime.now(UTC) + timedelta(hours=hours),
        )

        blob_sas_url = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{filename}?{sas_token}"
        return blob_sas_url

    def delete_blob(self, filename: str) -> None:
        """
        Delete a blob file from Azure Storage.

        Args:
            filename: Name of the blob to delete
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=filename
        )
        blob_client.delete_blob(delete_snapshots="include")
        logger.info(f"Deleted blob {filename}")

    def blob_exists(self, filename: str) -> bool:
        """
        Check if a blob exists in storage.

        Args:
            filename: Name of the blob to check

        Returns:
            True if blob exists, False otherwise
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=filename
        )
        return blob_client.exists()

    def delete_file(self, filename: str) -> None:
        """
        Alias for delete_blob for convenience.

        Args:
            filename: Name of the blob to delete
        """
        self.delete_blob(filename)


class QueueStorageClient:
    """Client for Azure Storage Queue operations"""

    def __init__(self, connection_string: str, queue_name: str):
        """
        Initialize the Queue Storage client.

        Args:
            connection_string: Azure Storage connection string
            queue_name: Name of the storage queue
        """
        self.connection_string = connection_string
        self.queue_name = queue_name
        self.queue_client = QueueClient.from_connection_string(
            connection_string, queue_name=queue_name
        )

    def send_message(self, message: Dict) -> None:
        """
        Send a message to the queue.

        Args:
            message: Message dictionary to send (will be JSON-encoded)
        """
        message_json = json.dumps(message)
        self.queue_client.send_message(message_json)
        logger.info(f"Sent message to queue {self.queue_name}: {message.get('action', 'unknown')}")


def send_transcoding_job(
    connection_string: str,
    queue_name: str,
    container_name: str,
    recording_id: str,
    source_blob_filename: str,
    target_blob_filename: str,
    original_filename: str,
    user_id: str,
    callbacks: List[Dict[str, str]],
) -> None:
    """
    Send a transcoding job to the Azure Storage Queue.

    Args:
        connection_string: Azure Storage connection string
        queue_name: Name of the transcoding queue
        container_name: Name of the blob container
        recording_id: ID of the recording being transcoded
        source_blob_filename: Source blob filename
        target_blob_filename: Target blob filename
        original_filename: Original filename
        user_id: ID of the user
        callbacks: List of callback URLs
    """
    logger.info(f"Sending transcoding request for recording ID: {recording_id} to queue: {queue_name}")

    # Create blob storage client to generate SAS URLs
    blob_client = BlobStorageClient(connection_string, container_name)
    source_sas_url = blob_client.generate_sas_url(source_blob_filename, read=True, write=False)
    target_sas_url = blob_client.generate_sas_url(target_blob_filename, read=True, write=True)

    # Create queue message
    message = {
        "action": "transcode",
        "recording_id": recording_id,
        "original_filename": original_filename,
        "user_id": user_id,
        "source_sas_url": source_sas_url,
        "target_sas_url": target_sas_url,
        "callbacks": callbacks,
    }

    # Send to queue
    queue_client = QueueStorageClient(connection_string, queue_name)
    queue_client.send_message(message)
