"""
Backward-compatible config module that wraps shared_quickscribe_py.config.

This module provides the old config.X interface while using the new shared settings
system under the hood. This allows gradual migration of code to use shared settings.
"""
from dotenv import load_dotenv
import os
import sys

# Load environment from .env file (startup.sh copies the appropriate file to .env)
if os.path.exists('.env'):
    load_dotenv('.env')
    print("Loaded environment from .env")
else:
    print("ERROR: .env file not found - startup.sh should have created it")
    sys.exit(1)

# Import shared settings
from shared_quickscribe_py.config import get_settings

# Load settings
_settings = get_settings()


class Config:
    """
    Backward-compatible configuration class that wraps shared settings.

    This provides the old config.X interface while using shared_quickscribe_py.config
    under the hood. Allows gradual migration to the new settings system.
    """

    # Environment detection - single source of truth
    RUNNING_IN_AZURE = _settings.running_in_azure
    IS_LOCAL_DEVELOPMENT = _settings.is_local_development

    # Flask settings
    SECRET_KEY = _settings.flask.secret_key if _settings.flask else os.getenv('SECRET_KEY', 'supersecretkey')

    # CosmosDB settings
    @property
    def COSMOS_URL(self):
        return _settings.cosmos.endpoint if _settings.cosmos else None

    @property
    def COSMOS_KEY(self):
        return _settings.cosmos.key if _settings.cosmos else None

    @property
    def COSMOS_DB_NAME(self):
        return _settings.cosmos.database_name if _settings.cosmos else None

    @property
    def COSMOS_CONTAINER_NAME(self):
        return _settings.cosmos.container_name if _settings.cosmos else None

    # Blob Storage settings
    @property
    def AZURE_STORAGE_CONNECTION_STRING(self):
        return _settings.blob_storage.connection_string if _settings.blob_storage else None

    @property
    def AZURE_RECORDING_BLOB_CONTAINER(self):
        return _settings.blob_storage.audio_container_name if _settings.blob_storage else None

    @property
    def TRANSCODING_QUEUE_NAME(self):
        return _settings.blob_storage.queue_name if _settings.blob_storage else None

    # Azure OpenAI settings
    @property
    def AZURE_OPENAI_API_KEY(self):
        return _settings.azure_openai.api_key if _settings.azure_openai else None

    @property
    def AZURE_OPENAI_API_ENDPOINT(self):
        return _settings.azure_openai.api_endpoint if _settings.azure_openai else None

    @property
    def AZURE_OPENAI_API_VERSION(self):
        return _settings.azure_openai.api_version if _settings.azure_openai else None

    @property
    def AZURE_OPENAI_DEPLOYMENT_NAME(self):
        return _settings.azure_openai.deployment_name if _settings.azure_openai else None

    # Azure Speech Services settings
    @property
    def AZURE_SPEECH_SERVICES_KEY(self):
        return _settings.speech_services.subscription_key if _settings.speech_services else None

    @property
    def AZURE_SPEECH_SERVICES_REGION(self):
        return _settings.speech_services.region if _settings.speech_services else None

    @property
    def AZURE_SPEECH_SERVICES_ENDPOINT(self):
        """Construct endpoint from region."""
        if _settings.speech_services:
            return f"https://{_settings.speech_services.region}.api.cognitive.microsoft.com"
        return None

    # Azure AD Auth settings
    @property
    def AZ_AUTH_CLIENT_ID(self):
        return _settings.azure_ad_auth.client_id if _settings.azure_ad_auth else None

    @property
    def AZ_AUTH_CLIENT_SECRET(self):
        return _settings.azure_ad_auth.client_secret if _settings.azure_ad_auth else None

    @property
    def AZ_AUTH_TENANT_ID(self):
        return _settings.azure_ad_auth.tenant_id if _settings.azure_ad_auth else None

    # AssemblyAI settings (optional)
    @property
    def ASSEMBLYAI_API_KEY(self):
        return _settings.assemblyai.api_key if _settings.assemblyai else None

    @property
    def ASSEMBLYAI_SPEECH_MODEL(self):
        return _settings.assemblyai.speech_model if _settings.assemblyai else None

    # Legacy/optional settings (not in shared config)
    KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME")
    AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")


# Create singleton instance
config = Config()
