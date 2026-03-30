"""Storage service — dual mode: local filesystem or Azure Blob Storage.

When LOCAL_BLOB_PATH is set (e.g. "./blobs"), files are stored on disk.
When AZURE_STORAGE_CONNECTION_STRING is set, files go to Azure Blob Storage.
Local mode is for development; Azure mode is for production.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API — all functions check config to decide local vs Azure
# ---------------------------------------------------------------------------


async def upload_file(file_path: str | Path, blob_name: str) -> str:
    """Upload a local file to storage.

    Args:
        file_path: Path to the local file.
        blob_name: Destination name (e.g. "user-xxx/recording-yyy.mp3").

    Returns:
        The blob/file name that was stored.
    """
    settings = get_settings()
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Local file not found: {file_path}")

    if settings.use_local_storage:
        return _local_upload(file_path, blob_name, settings)
    else:
        return await _azure_upload(file_path, blob_name, settings)


async def download_file(blob_name: str, local_path: str | Path) -> Path:
    """Download a file from storage to a local path.

    Args:
        blob_name: Source file name.
        local_path: Destination local path.

    Returns:
        The local path where the file was saved.
    """
    settings = get_settings()
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.use_local_storage:
        return _local_download(blob_name, local_path, settings)
    else:
        return await _azure_download(blob_name, local_path, settings)


def generate_sas_url(blob_name: str, hours: int = 24) -> str:
    """Generate a URL for accessing a file.

    Local mode: returns a relative URL path that FastAPI serves.
    Azure mode: returns a SAS URL for direct browser access.
    """
    settings = get_settings()

    if settings.use_local_storage:
        return _local_url(blob_name)
    else:
        return _azure_sas_url(blob_name, hours, settings)


async def delete_blob(blob_name: str) -> None:
    """Delete a file from storage."""
    settings = get_settings()

    if settings.use_local_storage:
        _local_delete(blob_name, settings)
    else:
        await _azure_delete(blob_name, settings)


async def copy_blob(source_url: str, dest_blob_name: str) -> str:
    """Copy a blob (Azure-only, used for migration)."""
    settings = get_settings()

    if settings.use_local_storage:
        raise NotImplementedError("copy_blob is only supported with Azure Blob Storage")

    return await _azure_copy(source_url, dest_blob_name, settings)


def file_exists(blob_name: str) -> bool:
    """Check if a file exists in storage."""
    settings = get_settings()

    if settings.use_local_storage:
        return (settings.local_blob_dir / blob_name).exists()
    else:
        # For Azure, we'd need a head_blob call — skip for now
        return True


# ---------------------------------------------------------------------------
# Local filesystem implementation
# ---------------------------------------------------------------------------


def _local_upload(file_path: Path, blob_name: str, settings) -> str:
    dest = settings.local_blob_dir / blob_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest)
    logger.info("Local storage: copied %s -> %s", file_path.name, dest)
    return blob_name


def _local_download(blob_name: str, local_path: Path, settings) -> Path:
    source = settings.local_blob_dir / blob_name
    if not source.exists():
        raise FileNotFoundError(f"Local blob not found: {source}")
    shutil.copy2(source, local_path)
    logger.info("Local storage: copied %s -> %s", source, local_path)
    return local_path


def _local_url(blob_name: str) -> str:
    """Return a URL path that the FastAPI static file server will handle."""
    return f"/api/blobs/{blob_name}"


def _local_delete(blob_name: str, settings) -> None:
    path = settings.local_blob_dir / blob_name
    if path.exists():
        path.unlink()
        logger.info("Local storage: deleted %s", path)
    else:
        logger.warning("Local storage: file not found for deletion: %s", path)


# ---------------------------------------------------------------------------
# Azure Blob Storage implementation
# ---------------------------------------------------------------------------


async def _azure_upload(file_path: Path, blob_name: str, settings) -> str:
    from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient

    async with AsyncBlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as client:
        container = client.get_container_client(settings.azure_storage_container)
        blob = container.get_blob_client(blob_name)
        with open(file_path, "rb") as f:
            await blob.upload_blob(f, overwrite=True)

    logger.info("Azure Blob: uploaded %s -> %s", file_path.name, blob_name)
    return blob_name


async def _azure_download(blob_name: str, local_path: Path, settings) -> Path:
    from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient

    async with AsyncBlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as client:
        container = client.get_container_client(settings.azure_storage_container)
        blob = container.get_blob_client(blob_name)
        with open(local_path, "wb") as f:
            stream = await blob.download_blob()
            data = await stream.readall()
            f.write(data)

    logger.info("Azure Blob: downloaded %s -> %s", blob_name, local_path)
    return local_path


def _azure_sas_url(blob_name: str, hours: int, settings) -> str:
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

    client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    account_name = client.account_name

    parts = dict(
        part.split("=", 1)
        for part in settings.azure_storage_connection_string.split(";")
        if "=" in part
    )
    account_key = parts.get("AccountKey", "")

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=settings.azure_storage_container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=hours),
    )

    return f"https://{account_name}.blob.core.windows.net/{settings.azure_storage_container}/{blob_name}?{sas_token}"


async def _azure_delete(blob_name: str, settings) -> None:
    from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient

    async with AsyncBlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as client:
        container = client.get_container_client(settings.azure_storage_container)
        blob = container.get_blob_client(blob_name)
        try:
            await blob.delete_blob()
            logger.info("Azure Blob: deleted %s", blob_name)
        except Exception:
            logger.warning("Azure Blob: not found for deletion: %s", blob_name)


async def _azure_copy(source_url: str, dest_blob_name: str, settings) -> str:
    from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient

    async with AsyncBlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as client:
        container = client.get_container_client(settings.azure_storage_container)
        blob = container.get_blob_client(dest_blob_name)
        await blob.start_copy_from_url(source_url)

    logger.info("Azure Blob: copied to %s", dest_blob_name)
    return dest_blob_name
