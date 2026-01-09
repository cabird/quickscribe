"""
QuickScribe Shared Python Library
Shared functionality for backend, transcoder, and sync services
"""
from setuptools import setup, find_packages

setup(
    name="quickscribe-shared",
    version="0.1.1",
    description="Shared Python library for QuickScribe services",
    packages=find_packages(),
    install_requires=[
        # Azure services
        "azure-cosmos>=4.7.0",
        "azure-storage-blob>=12.23.0",
        "azure-storage-queue>=12.12.0",
        "azure-identity>=1.19.0",

        # Data validation and models
        "pydantic>=2.9.0",
        "pydantic-settings>=2.0.0",

        # HTTP client for Plaud API
        "httpx>=0.27.0",
        "requests>=2.32.0",

        # Utilities
        "python-dotenv>=1.0.0",
        "mutagen>=1.47.0",  # For audio file metadata
        "tiktoken>=0.5.0",  # For accurate token counting
    ],
    python_requires=">=3.11",
)
