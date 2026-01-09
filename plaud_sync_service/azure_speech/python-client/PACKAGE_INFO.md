# Azure Speech Client Package Information

## Summary

This directory contains a modernized Python client for Azure Speech Services API v3.2, packaged as `azure-speech-client`. The package has been updated from the original Swagger-generated code with modern Python packaging standards.

## Changes Made

### 1. Modern Package Configuration (`pyproject.toml`)
- Replaced legacy `setup.py` with modern `pyproject.toml`
- Package name: `azure-speech-client` (was: `swagger-client`)
- Version: 3.2.0 (aligned with API version)
- Python requirement: >=3.8 (dropped Python 2.7 support)
- Updated dependencies to current secure versions:
  - `certifi>=2023.7.22` (was: >=2017.4.17)
  - `python-dateutil>=2.8.2` (was: >=2.1)
  - `six>=1.16.0` (was: >=1.10)
  - `urllib3>=2.0.0,<3.0.0` (was: >=1.23)

### 2. Package Metadata
- Added MIT license
- Added development dependencies (pytest, black, ruff)
- Added project URLs and classifiers
- Added proper author information

### 3. Build Configuration
- Created `MANIFEST.in` for including documentation and metadata
- Configured setuptools to properly package all modules
- Added support for editable installs

### 4. Documentation
- Updated `README.md` with modern installation instructions
- Added `LICENSE` file (MIT)
- Created this `PACKAGE_INFO.md`

### 5. Testing Configuration
- Added pytest configuration in `pyproject.toml`
- Configured code quality tools (black, ruff)

## Installation

### From the parent project (plaud_sync_service)

The package is now included in the parent `requirements.txt` as an editable install:

```bash
# Activate virtual environment
source .venv/bin/activate

# Install all requirements including azure-speech-client
pip install -r requirements.txt
```

### Standalone installation

```bash
# Editable/development install
pip install -e .

# Build and install
python -m build
pip install dist/azure_speech_client-3.2.0-py3-none-any.whl
```

## Usage

Import the module using `azure_speech_client`:

```python
import azure_speech_client
from azure_speech_client.rest import ApiException
from azure_speech_client.api import CustomSpeechTranscriptionsApi

# Configure API client
configuration = azure_speech_client.Configuration()
configuration.api_key['Ocp-Apim-Subscription-Key'] = 'YOUR_API_KEY'
configuration.host = 'https://YOUR_REGION.api.cognitive.microsoft.com/speechtotext/v3.2'

# Use the API
api_client = azure_speech_client.ApiClient(configuration)
transcriptions_api = CustomSpeechTranscriptionsApi(api_client)
```

## Package vs Module Naming

- **Package name** (for pip): `azure-speech-client`
- **Module name** (for import): `azure_speech_client`

The package and module names now align for clarity.

## Build Artifacts

After building, the following files are created in `dist/`:
- `azure_speech_client-3.2.0-py3-none-any.whl` - Wheel distribution
- `azure_speech_client-3.2.0.tar.gz` - Source distribution

## Development

### Code Quality Tools

```bash
# Format code
black swagger_client/

# Lint code
ruff swagger_client/
```

### Testing

```bash
# Run tests with coverage
pytest

# Run specific test
pytest test/test_transcription.py
```

## Notes

- The module has been renamed from `swagger_client` to `azure_speech_client` for clarity
- All generated API code remains intact
- All imports have been updated throughout the codebase
- The old `swagger_client-1.0.0` wheel can be removed from `dist/`

## Compatibility

- **Python**: 3.8+
- **Azure Speech Services API**: v3.2
- **Dependencies**: See `pyproject.toml` for full list

## Future Improvements

Consider:
1. Adding type hints (py.typed marker is configured)
2. Adding async support for API calls
3. Creating higher-level wrapper classes for common operations
4. Adding comprehensive test coverage
5. Publishing to PyPI if this becomes a shared package
