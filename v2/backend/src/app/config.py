"""Application configuration loaded from environment variables."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


def _read_version() -> str:
    """Read version from pyproject.toml, checking multiple possible locations."""
    for candidate in [
        Path(__file__).resolve().parent.parent.parent / "pyproject.toml",  # src/app/../../
        Path("/app/pyproject.toml"),
    ]:
        if candidate.exists():
            with open(candidate, "rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version", "0.0.0")
    return "0.0.0-unknown"


class Settings(BaseSettings):
    """QuickScribe v2 configuration."""

    # --- Database ---
    database_path: str = "./data/app.db"

    # --- Auth ---
    auth_disabled: bool = False
    azure_tenant_id: str = "common"
    azure_client_id: str = ""

    # --- Storage ---
    # When local_blob_path is set, files are stored on local filesystem instead of Azure Blob.
    # Set to "" to use Azure Blob Storage (production).
    local_blob_path: str = ""  # e.g. "./blobs" for local dev
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "audio-files"

    # --- Azure OpenAI ---
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_mini_deployment: str = ""
    azure_openai_chat_deployment: str = ""
    azure_openai_api_version: str = "2024-06-01"

    # --- Azure Speech Services ---
    speech_services_key: str = ""
    speech_services_region: str = ""

    # --- Speaker ID ---
    speaker_id_enabled: bool = True
    speaker_id_auto_threshold: float = 0.78
    speaker_id_suggest_threshold: float = 0.68
    speaker_id_model_path: str = "/app/pretrained_models/spkrec-ecapa-voxceleb"

    # --- Plaud ---
    plaud_enabled: bool = True

    # --- Sync ---
    sync_interval_minutes: int = 15
    max_recordings_per_sync: int | None = None
    max_speaker_id_per_user: int = 10

    # --- Deep Search ---
    deep_search_batch_token_limit: int = 50_000
    deep_search_max_candidates: int = 10

    # --- Server ---
    app_port: int = 8000
    api_version: str = ""
    log_level: str = "INFO"

    # --- Litestream (informational, used by entrypoint.sh not Python) ---
    azure_storage_account: str = ""
    azure_storage_key: str = ""
    litestream_bucket: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def db_path(self) -> Path:
        return Path(self.database_path)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

    @property
    def speech_enabled(self) -> bool:
        return bool(self.speech_services_key and self.speech_services_region)

    @property
    def use_local_storage(self) -> bool:
        return bool(self.local_blob_path)

    @property
    def blob_enabled(self) -> bool:
        return bool(self.azure_storage_connection_string) or self.use_local_storage

    @property
    def local_blob_dir(self) -> Path:
        return Path(self.local_blob_path)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.api_version:
            self.api_version = _read_version()


@lru_cache
def get_settings() -> Settings:
    return Settings()
