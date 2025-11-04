"""
QuickScribe Shared Configuration Module

Provides Pydantic-based configuration with validation and feature flags.
"""

from .settings import (
    QuickScribeSettings,
    AzureOpenAISettings,
    CosmosDBSettings,
    BlobStorageSettings,
    SpeechServicesSettings,
    PlaudAPISettings,
    get_settings,
)

__all__ = [
    "QuickScribeSettings",
    "AzureOpenAISettings",
    "CosmosDBSettings",
    "BlobStorageSettings",
    "SpeechServicesSettings",
    "PlaudAPISettings",
    "get_settings",
]
