
from config import config
from db_handlers.handler_factory import create_recording_handler, create_transcription_handler, create_user_handler
from db_handlers.models import TranscriptionStatus
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
        logging.info(f"fixup_recording: setting transcription_status to {TranscriptionStatus.not_started} for recording {recording['id']}")
        recording['transcription_status'] = TranscriptionStatus.not_started
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

def fixup_2():
    recording_handler = create_recording_handler()
    container = recording_handler.container
    query = "SELECT * FROM c"
    for item in container.query_items(query=query, partition_key="recording"):
        logging.info(f"fixup_cosmos_data: processing item {item['id']}")
        if "transcription_status_updated_at" in item:
            value = item["transcription_status_updated_at"]
            if isinstance(value, float):
                item["transcription_status_updated_at"] = datetime.fromtimestamp(value, UTC).isoformat()
                container.upsert_item(item)
                logging.info(f"fixup_cosmos_data: updated item {item['id']}")

def fixup_remove_diarization_and_speaker_mapping():
    transcription_handler = create_transcription_handler()
    container = transcription_handler.container
    query = "SELECT * FROM c"
    for item in container.query_items(query=query, partition_key="transcription"):
        changed = False 
        if "callback_secret" in item:
            del item["callback_secret"]
            changed = True
        if "aai_transcript_id" in item:
            del item["aai_transcript_id"]
            changed = True
        if "diarized_transcript" in item:
            del item["diarized_transcript"]
            changed = True
        if changed:
            container.upsert_item(item)
            logging.info(f"fixup_cosmos_data: updated item {item['id']}")


def fixup_transcriptions():
    transcription_handler = create_transcription_handler()
    container = transcription_handler.container
    query = "SELECT * FROM c"
    for item in container.query_items(query=query, partition_key="transcription"):
        changed = False
        if "transcription_status" in item:
            del item["transcription_status"]
            changed = True
        if "transcription_progress" in item:
            del item["transcription_progress"]
            changed = True
        if changed:
            container.upsert_item(item)
            logging.info(f"fixup_cosmos_data: updated item {item['id']}")
        if item["id"].startswith("f798c"):
            item["transcription_status"] = "in_progress"
            container.upsert_item(item)
            logging.info(f"fixup_cosmos_data: updated item {item['id']}")

def fixup_item():
    transcription_handler = create_transcription_handler()
    container = transcription_handler.container
    query = "SELECT * FROM c"
    items = container.query_items(
        query=query, 
        partition_key="recording", 
    )
    for item in items:
        logging.info(f"fixup_cosmos_data: examining item {item['id']}")
        if item["id"].startswith("f798c"):
            item["transcription_status"] = "in_progress"
            container.upsert_item(item)
            logging.info(f"fixup_cosmos_data: updated item {item['id']}")

def main():
    fixup_item()
if __name__ == "__main__":
    main()