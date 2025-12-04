"""
QuickScribe Shared Configuration

Provides Pydantic-based configuration with validation for all services.
Validates environment variables at startup and provides feature flags.
"""
from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import sys
import os


# =============================================================================
# Service-Specific Settings
# =============================================================================

class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration for AI post-processing."""

    api_endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    api_key: str = Field(..., description="Azure OpenAI API key")
    deployment_name: str = Field(
        ...,
        description="Standard model deployment (e.g., gpt-4o)"
    )
    mini_deployment_name: str = Field(
        ...,
        description="Mini model deployment (e.g., gpt-4o-mini)"
    )
    api_version: str = Field(
        default="2024-02-15-preview",
        description="API version"
    )

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_",
        case_sensitive=False
    )


class CosmosDBSettings(BaseSettings):
    """CosmosDB configuration for database operations."""

    endpoint: str = Field(..., description="CosmosDB endpoint URL")
    key: str = Field(..., description="CosmosDB master key")
    database_name: str = Field(
        default="quickscribe",
        description="Database name"
    )
    container_name: str = Field(
        default="recordings",
        description="Default container name"
    )

    model_config = SettingsConfigDict(
        env_prefix="AZURE_COSMOS_",
        case_sensitive=False
    )


class BlobStorageSettings(BaseSettings):
    """Azure Blob Storage configuration."""

    connection_string: str = Field(
        ...,
        description="Azure Storage connection string"
    )
    audio_container_name: str = Field(
        default="audio-files",
        description="Container for audio files"
    )
    queue_name: str = Field(
        default="audio-processing-queue",
        description="Queue for audio processing jobs"
    )

    model_config = SettingsConfigDict(
        env_prefix="AZURE_STORAGE_",
        case_sensitive=False
    )


class SpeechServicesSettings(BaseSettings):
    """Azure Speech Services configuration for transcription."""

    subscription_key: str = Field(..., description="Speech Services key")
    region: str = Field(..., description="Speech Services region")

    model_config = SettingsConfigDict(
        env_prefix="AZURE_SPEECH_",
        case_sensitive=False
    )


class PlaudAPISettings(BaseSettings):
    """Plaud API configuration for device integration."""

    base_url: str = Field(
        default="https://webapp.plaud.ai",
        description="Plaud API base URL"
    )

    model_config = SettingsConfigDict(
        env_prefix="PLAUD_API_",
        case_sensitive=False
    )


class AzureADAuthSettings(BaseSettings):
    """Azure AD authentication configuration for backend API."""

    client_id: str = Field(..., description="Azure AD application client ID")
    client_secret: str = Field(..., description="Azure AD client secret")
    tenant_id: str = Field(..., description="Azure AD tenant ID")

    model_config = SettingsConfigDict(
        env_prefix="AZ_AUTH_",
        case_sensitive=False
    )


class AssemblyAISettings(BaseSettings):
    """AssemblyAI transcription service configuration (optional alternative)."""

    api_key: str = Field(..., description="AssemblyAI API key")
    speech_model: str = Field(
        default="best",
        description="Speech model to use"
    )

    model_config = SettingsConfigDict(
        env_prefix="ASSEMBLYAI_",
        case_sensitive=False
    )


class FlaskSettings(BaseSettings):
    """Flask application-specific settings."""

    secret_key: str = Field(
        default="supersecretkey",
        description="Flask secret key for sessions"
    )

    model_config = SettingsConfigDict(
        env_prefix="FLASK_",
        case_sensitive=False
    )


class PlaudSyncTriggerSettings(BaseSettings):
    """
    Service principal configuration for triggering Plaud Sync Container Apps Job.

    Uses a dedicated service principal with limited scope to start the sync job.
    """

    client_id: str = Field(..., description="Service principal client ID (appId)")
    client_secret: str = Field(..., description="Service principal client secret")
    tenant_id: str = Field(..., description="Azure AD tenant ID")
    subscription_id: str = Field(..., description="Azure subscription ID")
    resource_group: str = Field(
        default="QuickScribeResourceGroup",
        description="Resource group containing the Container Apps Job"
    )
    job_name: str = Field(
        default="quickscribe-plaud-sync-job",
        description="Name of the Container Apps Job to trigger"
    )

    model_config = SettingsConfigDict(
        env_prefix="PLAUD_SYNC_TRIGGER_",
        case_sensitive=False
    )


# =============================================================================
# Main Application Settings
# =============================================================================

class QuickScribeSettings(BaseSettings):
    """
    Main configuration for QuickScribe services.

    Validates all required environment variables at startup and provides
    feature flags for optional integrations.

    Usage:
        # At application startup
        try:
            settings = QuickScribeSettings()
        except ValidationError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)

        # Check feature flags
        if settings.ai_enabled:
            # Use settings.azure_openai.*
            pass
    """

    # =========================================================================
    # Core Application Settings
    # =========================================================================

    service_name: str = Field(
        default="quickscribe",
        description="Service name for logging"
    )
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )

    # =========================================================================
    # Feature Flags
    # =========================================================================

    ai_enabled: bool = Field(
        default=False,
        description="Enable AI post-processing (requires Azure OpenAI)"
    )
    cosmos_enabled: bool = Field(
        default=True,
        description="Enable CosmosDB (required for most operations)"
    )
    blob_storage_enabled: bool = Field(
        default=True,
        description="Enable Blob Storage (required for most operations)"
    )
    speech_services_enabled: bool = Field(
        default=True,
        description="Enable Speech Services for transcription"
    )
    plaud_enabled: bool = Field(
        default=False,
        description="Enable Plaud device integration"
    )
    azure_ad_auth_enabled: bool = Field(
        default=False,
        description="Enable Azure AD authentication for backend"
    )
    assemblyai_enabled: bool = Field(
        default=False,
        description="Enable AssemblyAI as alternative transcription service"
    )
    plaud_sync_trigger_enabled: bool = Field(
        default=False,
        description="Enable manual triggering of Plaud Sync Container Apps Job"
    )

    # =========================================================================
    # Service-Specific Settings (Conditionally Required)
    # =========================================================================

    azure_openai: Optional[AzureOpenAISettings] = None
    cosmos: Optional[CosmosDBSettings] = None
    blob_storage: Optional[BlobStorageSettings] = None
    speech_services: Optional[SpeechServicesSettings] = None
    plaud_api: Optional[PlaudAPISettings] = None
    azure_ad_auth: Optional[AzureADAuthSettings] = None
    assemblyai: Optional[AssemblyAISettings] = None
    flask: Optional[FlaskSettings] = None
    plaud_sync_trigger: Optional[PlaudSyncTriggerSettings] = None

    # =========================================================================
    # Pydantic Configuration
    # =========================================================================

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"  # Ignore extra env vars
    )

    # =========================================================================
    # Validators: Conditional Requirements Based on Feature Flags
    # =========================================================================

    @field_validator('azure_openai', mode='before')
    @classmethod
    def validate_azure_openai(cls, v, info):
        """Require Azure OpenAI settings if ai_enabled is True."""
        if info.data.get('ai_enabled'):
            try:
                return AzureOpenAISettings()
            except ValidationError as e:
                raise ValueError(
                    f"Azure OpenAI configuration required (ai_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('cosmos', mode='before')
    @classmethod
    def validate_cosmos(cls, v, info):
        """Require CosmosDB settings if cosmos_enabled is True."""
        if info.data.get('cosmos_enabled'):
            try:
                return CosmosDBSettings()
            except ValidationError as e:
                raise ValueError(
                    f"CosmosDB configuration required (cosmos_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('blob_storage', mode='before')
    @classmethod
    def validate_blob_storage(cls, v, info):
        """Require Blob Storage settings if blob_storage_enabled is True."""
        if info.data.get('blob_storage_enabled'):
            try:
                return BlobStorageSettings()
            except ValidationError as e:
                raise ValueError(
                    f"Blob Storage configuration required (blob_storage_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('speech_services', mode='before')
    @classmethod
    def validate_speech_services(cls, v, info):
        """Require Speech Services settings if speech_services_enabled is True."""
        if info.data.get('speech_services_enabled'):
            try:
                return SpeechServicesSettings()
            except ValidationError as e:
                raise ValueError(
                    f"Speech Services configuration required (speech_services_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('plaud_api', mode='before')
    @classmethod
    def validate_plaud_api(cls, v, info):
        """Require Plaud API settings if plaud_enabled is True."""
        if info.data.get('plaud_enabled'):
            try:
                return PlaudAPISettings()
            except ValidationError as e:
                raise ValueError(
                    f"Plaud API configuration required (plaud_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('azure_ad_auth', mode='before')
    @classmethod
    def validate_azure_ad_auth(cls, v, info):
        """Require Azure AD auth settings if azure_ad_auth_enabled is True."""
        if info.data.get('azure_ad_auth_enabled'):
            try:
                return AzureADAuthSettings()
            except ValidationError as e:
                raise ValueError(
                    f"Azure AD auth configuration required (azure_ad_auth_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('assemblyai', mode='before')
    @classmethod
    def validate_assemblyai(cls, v, info):
        """Require AssemblyAI settings if assemblyai_enabled is True."""
        if info.data.get('assemblyai_enabled'):
            try:
                return AssemblyAISettings()
            except ValidationError as e:
                raise ValueError(
                    f"AssemblyAI configuration required (assemblyai_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('plaud_sync_trigger', mode='before')
    @classmethod
    def validate_plaud_sync_trigger(cls, v, info):
        """Require Plaud Sync Trigger settings if plaud_sync_trigger_enabled is True."""
        if info.data.get('plaud_sync_trigger_enabled'):
            try:
                return PlaudSyncTriggerSettings()
            except ValidationError as e:
                raise ValueError(
                    f"Plaud Sync Trigger configuration required (plaud_sync_trigger_enabled=True) "
                    f"but validation failed: {e}"
                )
        return None

    @field_validator('flask', mode='before')
    @classmethod
    def validate_flask(cls, v, info):
        """Always load Flask settings with defaults."""
        try:
            return FlaskSettings()
        except ValidationError as e:
            raise ValueError(f"Flask configuration validation failed: {e}")

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def running_in_azure(self) -> bool:
        """Detect if running in Azure App Service."""
        return bool(os.getenv('WEBSITE_INSTANCE_ID'))

    @property
    def is_local_development(self) -> bool:
        """Detect if running in local development environment."""
        return not self.running_in_azure


# =============================================================================
# Helper Functions
# =============================================================================

def get_settings(fail_fast: bool = True) -> Optional[QuickScribeSettings]:
    """
    Load and validate application settings.

    Args:
        fail_fast: If True, exit the application on validation error.
                   If False, return None on error (useful for testing).

    Returns:
        Validated settings or None if validation fails and fail_fast=False

    Example:
        # In your main.py
        settings = get_settings()

        # In tests
        settings = get_settings(fail_fast=False)
        if settings is None:
            # Handle missing config for test
    """
    try:
        return QuickScribeSettings()
    except ValidationError as e:
        if fail_fast:
            print(f"Configuration validation error: {e}", file=sys.stderr)
            sys.exit(1)
        return None
