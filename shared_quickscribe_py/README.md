# QuickScribe Shared Python Library

Shared Python functionality for QuickScribe microservices.

## Overview

This package contains common code shared between:
- Backend API server (`/backend/`)
- Transcoder container (`/transcoder_container/`)
- Plaud sync service (`/plaud_sync_service/`)

## Structure

```
shared_quickscribe_py/
├── cosmos/              # Cosmos DB models and handlers
│   ├── models.py        # Pydantic models
│   ├── recording_handler.py
│   ├── transcription_handler.py
│   ├── user_handler.py
│   └── ...
├── azure_services/      # Azure service clients
│   ├── blob_storage.py  # Blob storage operations
│   ├── speech_service.py # Azure Speech Services
│   └── queue_service.py # Queue operations
├── plaud/              # Plaud API client
│   └── client.py
├── logging/            # Shared logging configuration
│   └── config.py
└── config/             # Shared configuration
    └── settings.py
```

## Installation

From any service directory, install in development mode:

```bash
pip install -e /path/to/shared_quickscribe_py
```

Or in Dockerfile:

```dockerfile
COPY shared_quickscribe_py/ /app/shared_quickscribe_py/
RUN pip install -e /app/shared_quickscribe_py/
```

## Usage

```python
from shared_quickscribe_py.cosmos import RecordingHandler, Recording
from shared_quickscribe_py.azure_services import BlobStorageClient
from shared_quickscribe_py.plaud import PlaudClient

# Use shared handlers
handler = RecordingHandler(cosmos_client, database_name)
recording = handler.get_recording_by_id(recording_id)

# Use shared Azure services
blob_client = BlobStorageClient(connection_string)
blob_client.upload_file(file_path, blob_name)
```

## Development

When making changes to shared_quickscribe_py:
1. Edit files in `/shared_quickscribe_py/`
2. Changes are immediately available to services using `-e` install
3. Test across all services that use the library
4. Commit shared_quickscribe_py changes separately for clarity
