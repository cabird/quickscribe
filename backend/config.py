import os
from dotenv import load_dotenv

# Load appropriate .env file based on environment
if os.getenv('WEBSITE_INSTANCE_ID'):  # Running in Azure
    if os.path.exists('.env.production'):
        load_dotenv('.env.production')
        print("Loaded environment from .env.production (Azure)")
    else:
        print("WARNING: .env.production not found in Azure environment")
else:  # Local development
    if os.path.exists('.env.local'):
        load_dotenv('.env.local')
        print("Loaded environment from .env.local (Local)")
    elif os.path.exists('.env'):
        load_dotenv('.env')
        print("Loaded environment from .env (Local fallback)")
    else:
        print("WARNING: No .env file found for local development")

class Config:
    # Environment detection - single source of truth
    RUNNING_IN_AZURE = bool(os.getenv('WEBSITE_INSTANCE_ID'))
    IS_LOCAL_DEVELOPMENT = not RUNNING_IN_AZURE
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_RECORDING_BLOB_CONTAINER = os.getenv("AZURE_RECORDING_BLOB_CONTAINER")
    COSMOS_URL = os.getenv('COSMOS_URL')
    COSMOS_KEY = os.getenv('COSMOS_KEY')
    COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME")
    COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")
    KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME")
    AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

    TRANSCODING_QUEUE_NAME = os.getenv("TRANSCODING_QUEUE_NAME")
    
    #Azure Authentication
    AZ_AUTH_CLIENT_ID = os.getenv("AZ_AUTH_CLIENT_ID")
    AZ_AUTH_CLIENT_SECRET = os.getenv("AZ_AUTH_CLIENT_SECRET")
    AZ_AUTH_TENANT_ID = os.getenv("AZ_AUTH_TENANT_ID")

    #Azure OpenAI
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_ENDPOINT = os.getenv("AZURE_OPENAI_API_ENDPOINT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    #AssemblyAI
    ASSEMBLYAI_SPEECH_MODEL = os.getenv("ASSEMBLYAI_SPEECH_MODEL")
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

    #Azure Speech Services
    AZURE_SPEECH_SERVICES_ENDPOINT = os.getenv("AZURE_SPEECH_SERVICES_ENDPOINT")
    AZURE_SPEECH_SERVICES_REGION = os.getenv("AZURE_SPEECH_SERVICES_REGION")
    AZURE_SPEECH_SERVICES_KEY = os.getenv("AZURE_SPEECH_SERVICES_KEY")

config = Config()
