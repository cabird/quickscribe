
from config import config
from db_handlers.handler_factory import create_recording_handler, create_transcription_handler, create_user_handler
from db_handlers.transcription_handler import TranscribingStatus
from datetime import datetime, UTC
from azure.storage.blob import BlobServiceClient
from util import get_recording_duration_in_seconds
import os
import logging

# setup logging
logging.basicConfig(level=logging.INFO)

# Suppress INFO logs from azure.core.pipeline.policies.http_logging_policy
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)


def fixup_recording(recording):
    changed = False
    if not 'transcription_status' in recording:
        logging.info(f"fixup_recording: setting transcription_status to {TranscribingStatus.NOT_STARTED.value} for recording {recording['id']}")
        recording['transcription_status'] = TranscribingStatus.NOT_STARTED.value
        changed = True
    
    if not 'transcription_status_updated_at' in recording:
        logging.info(f"fixup_recording: setting transcription_status_updated_at to {datetime.now(UTC).timestamp()} for recording {recording['id']}")
        recording['transcription_status_updated_at'] = datetime.now(UTC).timestamp()
        changed = True

    original_extension = recording['original_filename'].split(".")[-1]
    unique_extension = recording['unique_filename'].split(".")[-1]
    if original_extension != unique_extension:
        first_unique_filename = recording['unique_filename']
        logging.info(f"fixup_recording: original_extension {original_extension} != unique_extension {unique_extension} for recording {recording['id']}")
        recording['unique_filename'] = recording['unique_filename'].split(".")[0] + "." + original_extension
        
        logging.info(f"fixup_recording: copying {first_unique_filename} to {recording['unique_filename']} for recording {recording['id']}")
        #rename the blob in azure blob storage
        blob_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING).get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=first_unique_filename)
        new_blob_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING).get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=recording['unique_filename'])
        new_blob_client.start_copy_from_url(blob_client.url)
        blob_client.delete_blob()

        changed = True

    #calculate the duration of the recording
    if not 'duration' in recording:
        logging.info(f"fixup_recording: calculating duration for recording {recording['id']}")
        # get the blob from azure blob storage
        blob_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING).get_blob_client(container=config.AZURE_RECORDING_BLOB_CONTAINER, blob=recording['unique_filename'])

        # write the blob to a file
        filename = recording['unique_filename']
        with open(filename, "wb") as f:
            f.write(blob_client.download_blob().readall())
        recording['duration'] = get_recording_duration_in_seconds(filename)
        os.remove(filename)
        changed = True

    return changed

def main():
    recording_handler = create_recording_handler()
    recordings = recording_handler.get_all_recordings()
    for recording in recordings:
        logging.info(f"fixup_cosmos_data: processing recording {recording['id']}")
        changed = fixup_recording(recording)
        if changed:
            recording_handler.update_recording(recording)
            logging.info(f"fixup_cosmos_data: updated recording {recording['id']}")
if __name__ == "__main__":
    main()