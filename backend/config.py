import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_RECORDING_BLOB_CONTAINER = os.getenv("AZURE_RECORDING_BLOB_CONTAINER")
    COSMOS_URL = os.getenv('COSMOS_URL')
    COSMOS_KEY = os.getenv('COSMOS_KEY')
    COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME")
    COSMOS_CONTAINER_NAME = os.getenv("COSMOS_CONTAINER_NAME")
    KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME")
    AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    
    # this is a workaround to determine if we're running in a container
    # https://stackoverflow.com/questions/71411665/how-to-determine-if-a-python-flask-application-is-running-in-a-container
    RUNNING_IN_CONTAINER = "WEBSITE_INSTANCE_ID" in os.environ
    
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
