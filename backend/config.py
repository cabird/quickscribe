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
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
    # this is a workaround to determine if we're running in a container
    # https://stackoverflow.com/questions/71411665/how-to-determine-if-a-python-flask-application-is-running-in-a-container
    RUNNING_IN_CONTAINER = "WEBSITE_INSTANCE_ID" in os.environ
    

config = Config()
