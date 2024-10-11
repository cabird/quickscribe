import click
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient, PartitionKey
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Azure configurations
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
RECORDINGS_BLOB_CONTAINER = os.getenv("AZURE_RECORDING_BLOB_CONTAINER")

COSMOS_URL = os.getenv("COSMOS_URL")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DB_NAME  = os.getenv("COSMOS_DB_NAME")
COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")

# Initialize clients
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
cosmos_client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
database = cosmos_client.get_database_client(COSMOS_DB_NAME)
container = database.get_container_client(COSMOS_CONTAINER_NAME)

def find_entry_by_partial_id(partial_id):
    """
    Search for an entry in Cosmos DB whose ID starts with the given partial ID.
    Returns the entry if exactly one match is found, otherwise returns None and prints a message.
    """
    # Fetch all entries from Cosmos DB
    entries = list(container.read_all_items())

    # Search for entries whose ID starts with the given partial ID
    matching_entries = [entry for entry in entries if entry['id'].startswith(partial_id)]

    if len(matching_entries) == 0:
        click.echo(f"No entries found with an ID starting with '{partial_id}'")
        return None
    elif len(matching_entries) > 1:
        click.echo(f"Multiple entries found with an ID starting with '{partial_id}':")
        for entry in matching_entries:
            click.echo(f"- {entry['id']}")
        return None

    # If exactly one match is found, return the matched entry
    return matching_entries[0]


@click.group()
def cli():
    """A command-line tool to manage Azure Blob Storage and Cosmos DB."""
    pass

# Command to list all files in the mp3uploads container
@cli.command()
def list_blobs():
    """List all files in the mp3uploads container."""
    blob_list = blob_service_client.get_container_client(RECORDINGS_BLOB_CONTAINER).list_blobs()
    click.echo("Files in the 'mp3uploads' container:")
    for blob in blob_list:
        click.echo(f"- {blob.name}")

# Command to list all entries in the Cosmos DB
@cli.command()
def list_cosmos_entries():
    """List all entries in Cosmos DB."""
    entries = list(container.read_all_items())
    click.echo("Entries in the Cosmos DB:")
    for entry in entries:
        click.echo(f"- {entry['id']}: {entry['original_filename']}")

@cli.command()
@click.argument('partial_id')
def show_cosmos_entry(partial_id):
    """Show the full JSON of a particular entry in Cosmos DB by partial ID."""
    entry = find_entry_by_partial_id(partial_id)
    
    if entry:
        click.echo(json.dumps(entry, indent=4))

    except Exception as e:
        click.echo(f"Error: {str(e)}")

# Command to delete a Cosmos DB entry and its associated blob
@cli.command()
@click.argument('entry_id')
def delete_cosmos_entry(entry_id):
    """Delete an entry in Cosmos DB and the associated file in Blob Storage."""
    entry = find_entry_by_partial_id(partial_id)
    if not entry:
        return
    try:
        unique_filename = entry['unique_filename']

        # Delete the file from Blob Storage
        blob_client = blob_service_client.get_blob_client(container=RECORDINGS_BLOB_CONTAINER, blob=unique_filename)
        blob_client.delete_blob()
        click.echo(f"Deleted file: {unique_filename} from Blob Storage")

        # Delete the entry from Cosmos DB
        container.delete_item(item=entry_id, partition_key="file")
        click.echo(f"Deleted entry: {entry_id} from Cosmos DB")

    except Exception as e:
        click.echo(f"Error: {str(e)}")

# Command to check consistency between Cosmos DB and Blob Storage
@cli.command()
def check_consistency():
    """Check that every entry in Cosmos DB has an associated file in Blob Storage and vice versa."""
    click.echo("Checking consistency between Cosmos DB and Blob Storage...\n")

    # Step 1: Check if every entry in Cosmos DB has a corresponding blob
    cosmos_entries = list(container.read_all_items())
    blob_names = {blob.name for blob in blob_service_client.get_container_client(RECORDINGS_BLOB_CONTAINER).list_blobs()}

    missing_files = []
    for entry in cosmos_entries:
        if entry['unique_filename'] not in blob_names:
            missing_files.append(entry['unique_filename'])
            click.echo(f"Warning: Missing blob for Cosmos DB entry: {entry['id']} (file: {entry['unique_filename']})")

    if not missing_files:
        click.echo("All Cosmos DB entries have corresponding files in Blob Storage.\n")

    # Step 2: Check if every blob in Blob Storage has a corresponding entry in Cosmos DB
    cosmos_filenames = {entry['unique_filename'] for entry in cosmos_entries}
    missing_entries = []
    for blob_name in blob_names:
        if blob_name not in cosmos_filenames:
            missing_entries.append(blob_name)
            click.echo(f"Warning: Missing Cosmos DB entry for blob: {blob_name}")

    if not missing_entries:
        click.echo("All files in Blob Storage have corresponding entries in Cosmos DB.\n")

    # Final Summary
    if not missing_files and not missing_entries:
        click.echo("Consistency check passed. Everything is in sync!")
    else:
        click.echo(f"\nSummary: {len(missing_files)} missing blobs, {len(missing_entries)} missing Cosmos DB entries.")

if __name__ == '__main__':
    cli()
