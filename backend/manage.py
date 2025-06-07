import click
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient, PartitionKey
from db_handlers.handler_factory import create_user_handler, create_recording_handler, create_analysis_type_handler
import os
import json
from dotenv import load_dotenv
import swagger_client
from pprint import pprint
import requests


load_dotenv()

# Azure configurations
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
RECORDINGS_BLOB_CONTAINER = os.getenv("AZURE_RECORDING_BLOB_CONTAINER")

COSMOS_URL = os.getenv("COSMOS_URL")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DB_NAME  = os.getenv("COSMOS_DB_NAME")
COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")

AZURE_SPEECH_SERVICES_KEY = os.getenv("AZURE_SPEECH_SERVICES_KEY")
AZURE_SPEECH_SERVICES_ENDPOINT = os.getenv("AZURE_SPEECH_SERVICES_ENDPOINT")
AZURE_SPEECH_SERVICES_REGION = os.getenv("AZURE_SPEECH_SERVICES_REGION")

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
def show_item(partial_id):
    """Show the full JSON of a particular entry in Cosmos DB by partial ID."""
    entry = find_entry_by_partial_id(partial_id)
    
    if entry:
        click.echo(json.dumps(entry, indent=4))


@cli.command()
def list_recordings():
    recording_handler = create_recording_handler()
    recordings = recording_handler.get_all_recordings()
    for recording in recordings:
        click.echo(f"- {recording.id}: {recording.original_filename} {recording.unique_filename}")

@cli.command()
@click.argument('recording_id')
def show_recording(recording_id):
    recording_handler = create_recording_handler()
    recordings = recording_handler.get_all_recordings()
    for curRecording in recordings:
        if curRecording.id.startswith(recording_id):
            click.echo(json.dumps(curRecording.model_dump(exclude_unset=False), indent=4))


# Command to delete a Cosmos DB entry and its associated blob
@cli.command()
@click.argument('entry_id')
def delete_cosmos_entry(entry_id):
    """Delete an entry in Cosmos DB and the associated file in Blob Storage."""
    entry = find_entry_by_partial_id(entry_id)
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

# Command to create a new user
@cli.command()
@click.argument('email')
@click.argument('name')
@click.option('--role', default="user", help="Role of the user (default is 'user')")
def create_user(email, name, role):
    # Create the user handler
    user_handler = create_user_handler()
    """Create a new user with the provided email, name, and optional role."""
    user_id = user_handler.create_user(email, name, role)
    click.echo(f"User created with ID: {user_id}")

# Command to list users
@cli.command()
def list_users():
    user_handler = create_user_handler()
    users = user_handler.get_all_users()
    for user in users:
        click.echo(f"- {user['id']}: {user['name']} ({user['email']})")

# command to list transcription jobs
@cli.command()
def list_transcriptions():
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)
    
    paginated_transcriptions = api.transcriptions_list()
    for transcription in az_paginate(api, paginated_transcriptions):
        link = transcription._self
        created_datetime = transcription.created_date_time
        #format the datetime
        created_datetime = created_datetime.strftime("%Y-%m-%d %H:%M:%S")   
        id = link.split('/')[-1]
        click.echo(f"{id}: {transcription.status} : {transcription.display_name} : {created_datetime}")


@cli.command()
@click.argument('id')
def show_transcription(id):
    client = get_speech_api_client()
    api = swagger_client.CustomSpeechTranscriptionsApi(api_client=client)
    
    paginated_transcriptions = api.transcriptions_list()
    for transcription in az_paginate(api, paginated_transcriptions):
        link = transcription._self
        link_id = link.split('/')[-1]
        if link_id.startswith(id):
            id = link_id
            click.echo(f"{link}: {transcription.status} : {transcription.display_name}")
            click.echo(f"    {transcription}")

            paginated_files = api.transcriptions_list_files(id)
            for file in az_paginate(api, paginated_files):
                click.echo(f"FILE    {file}")
                link = file.links.content_url
                click.echo(f" LINK       {link}")
                #get the contents of the link using requests
                response = requests.get(link)
                click.echo(f"RESPONSE    {response.content}")
                # convert the content which is json to a python object and then pretty print it
                content = json.loads(response.content)
                pprint(content)

            
            #pprint(response)

def az_paginate(api, paginated_object):
    """
    The autogenerated client does not support pagination. This function returns a generator over
    all items of the array that the paginated object `paginated_object` is part of.
    """
    yield from paginated_object.values
    typename = type(paginated_object).__name__
    auth_settings = ["api_key"]
    while paginated_object.next_link:
        link = paginated_object.next_link[len(api.api_client.configuration.host):]
        paginated_object, status, headers = api.api_client.call_api(link, "GET",
            response_type=typename, auth_settings=auth_settings)

        if status == 200:
            yield from paginated_object.values
        else:
            raise Exception(f"could not receive paginated data: status {status}")

@cli.command()
def delete_builtin_analysis_types():
    """Delete all built-in analysis types from the database."""
    analysis_type_handler = create_analysis_type_handler()
    
    try:
        # Get all built-in analysis types
        builtin_types = analysis_type_handler.get_builtin_analysis_types()
        
        if not builtin_types:
            click.echo("No built-in analysis types found to delete.")
            return
            
        click.echo(f"Found {len(builtin_types)} built-in analysis types to delete:")
        for analysis_type in builtin_types:
            click.echo(f"  - {analysis_type.name}: {analysis_type.title}")
        
        # Confirm deletion
        if click.confirm(f"Are you sure you want to delete all {len(builtin_types)} built-in analysis types?"):
            deleted_count = 0
            
            for analysis_type in builtin_types:
                try:
                    # Delete using the container directly since we need to delete built-in types
                    container = analysis_type_handler.container
                    container.delete_item(item=analysis_type.id, partition_key="global")
                    click.echo(f"✓ Deleted: {analysis_type.name}")
                    deleted_count += 1
                except Exception as e:
                    click.echo(f"✗ Failed to delete {analysis_type.name}: {e}")
            
            click.echo(f"\nDeleted {deleted_count} out of {len(builtin_types)} built-in analysis types.")
        else:
            click.echo("Deletion cancelled.")
            
    except Exception as e:
        click.echo(f"Error deleting built-in analysis types: {e}")


@cli.command()
def seed_analysis_types():
    """Seed the database with built-in analysis types."""
    analysis_type_handler = create_analysis_type_handler()
    
    # Define the 6 built-in analysis types with shortTitle field
    builtin_types = [
        {
            "name": "summary",
            "title": "Generate Summary",
            "shortTitle": "Summary",
            "description": "Create a concise overview of the main topics and key points",
            "icon": "file-text",
            "prompt": "Please provide a concise summary of the following transcript, highlighting the main topics and key points discussed:\n\n{transcript}"
        },
        {
            "name": "keywords",
            "title": "Extract Keywords",
            "shortTitle": "Keywords",
            "description": "Identify important keywords, topics, and themes",
            "icon": "tag",
            "prompt": "Extract the most important keywords, topics, and themes from the following transcript. Present them in a structured format with primary keywords and key themes:\n\n{transcript}"
        },
        {
            "name": "sentiment",
            "title": "Analyze Sentiment",
            "shortTitle": "Sentiment",
            "description": "Analyze emotional tone and sentiment patterns",
            "icon": "smile",
            "prompt": "Analyze the emotional tone and sentiment patterns in the following transcript. Provide an overall sentiment assessment and identify key emotional shifts:\n\n{transcript}"
        },
        {
            "name": "qa",
            "title": "Generate Q&A",
            "shortTitle": "Q&A",
            "description": "Create relevant questions and answers for study material",
            "icon": "circle-help",
            "prompt": "Generate relevant questions and answers based on the following transcript. Create study material that captures the key information and concepts discussed:\n\n{transcript}"
        },
        {
            "name": "action-items",
            "title": "Find Action Items",
            "shortTitle": "Actions",
            "description": "Extract actionable tasks and follow-up items",
            "icon": "list-todo",
            "prompt": "Extract all action items, tasks, decisions, and follow-up items from the following transcript. List any responsible parties and deadlines where mentioned:\n\n{transcript}"
        },
        {
            "name": "topic-detection",
            "title": "Detect Topics",
            "shortTitle": "Topics",
            "description": "Automatically identify and categorize discussion topics",
            "icon": "search",
            "prompt": "Identify and categorize the main topics discussed in the following transcript. Provide a structured breakdown of topics and their relative importance:\n\n{transcript}"
        }
    ]
    
    # Check existing built-in types
    existing_types = analysis_type_handler.get_builtin_analysis_types()
    existing_names = {t.name for t in existing_types}
    
    created_count = 0
    updated_count = 0
    
    for type_data in builtin_types:
        if type_data["name"] in existing_names:
            click.echo(f"Built-in analysis type '{type_data['name']}' already exists, skipping...")
            continue
            
        try:
            created_type = analysis_type_handler.create_builtin_analysis_type(
                name=type_data["name"],
                title=type_data["title"],
                short_title=type_data["shortTitle"],
                description=type_data["description"],
                icon=type_data["icon"],
                prompt=type_data["prompt"]
            )
            
            if created_type:
                click.echo(f"✓ Created built-in analysis type: {type_data['title']}")
                created_count += 1
            else:
                click.echo(f"✗ Failed to create analysis type: {type_data['title']}")
                
        except Exception as e:
            click.echo(f"✗ Error creating analysis type '{type_data['title']}': {e}")
    
    click.echo(f"\nSeeding complete! Created {created_count} new built-in analysis types.")
    if created_count == 0 and len(existing_names) == len(builtin_types):
        click.echo("All built-in analysis types already exist in the database.")

def get_speech_api_client():
    configuration = swagger_client.Configuration()
    configuration.api_key["Ocp-Apim-Subscription-Key"] = os.getenv("AZURE_SPEECH_SERVICES_KEY")
    configuration.host = f"https://{os.getenv('AZURE_SPEECH_SERVICES_REGION')}.api.cognitive.microsoft.com/speechtotext/v3.2"

    client = swagger_client.ApiClient(configuration)
    return client
    

if __name__ == '__main__':
    cli()
