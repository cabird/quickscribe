# QuickScribe Configuration System

Pydantic-based configuration with validation and feature flags for all QuickScribe services.

## Features

- **Fail Fast**: Validates all configuration at startup, not during runtime
- **Type Safety**: Full type checking with Pydantic models
- **Feature Flags**: Enable/disable services conditionally
- **Self-Documenting**: Configuration model serves as documentation
- **Testable**: Easy to mock configurations for testing
- **Conditional Requirements**: Settings only required when features are enabled

## Quick Start

### 1. Install Dependencies

The shared package includes `pydantic-settings` as a dependency. Install the shared package:

```bash
cd shared_quickscribe_py
pip install -e .
```

### 2. Configure Environment Variables

Copy the template and fill in your values:

```bash
cp .env.template .env
# Edit .env with your configuration
```

### 3. Use in Your Service

```python
from shared_quickscribe_py.config import get_settings

# At application startup
try:
    settings = get_settings()
except SystemExit:
    # Configuration validation failed - error logged to stderr
    pass

# Check feature flags
if settings.ai_enabled:
    # AI post-processing is available
    client = AzureOpenAIClient(
        endpoint=settings.azure_openai.api_endpoint,
        api_key=settings.azure_openai.api_key,
        deployment_name=settings.azure_openai.deployment_name
    )

if settings.cosmos_enabled:
    # CosmosDB is available
    cosmos_client = CosmosClient(
        url=settings.cosmos.endpoint,
        credential=settings.cosmos.key
    )
```

## Configuration Structure

### Feature Flags

Control which services are enabled:

```python
ai_enabled: bool                    # Azure OpenAI for AI post-processing
cosmos_enabled: bool                # CosmosDB for database
blob_storage_enabled: bool          # Azure Blob Storage
speech_services_enabled: bool       # Azure Speech Services
plaud_enabled: bool                 # Plaud device integration
```

### Conditional Settings

Settings are only required when their feature flag is `True`:

| Feature Flag | Required Settings |
|-------------|------------------|
| `ai_enabled=True` | `AzureOpenAISettings` |
| `cosmos_enabled=True` | `CosmosDBSettings` |
| `blob_storage_enabled=True` | `BlobStorageSettings` |
| `speech_services_enabled=True` | `SpeechServicesSettings` |
| `plaud_enabled=True` | `PlaudAPISettings` |

## Environment Variables

### Core Settings

```bash
SERVICE_NAME=quickscribe          # Optional, default: "quickscribe"
ENVIRONMENT=development           # Optional, default: "development"
LOG_LEVEL=INFO                    # Optional, default: "INFO"
```

### Feature Flags

```bash
AI_ENABLED=false
COSMOS_ENABLED=true
BLOB_STORAGE_ENABLED=true
SPEECH_SERVICES_ENABLED=true
PLAUD_ENABLED=false
```

### Azure OpenAI (required if `AI_ENABLED=true`)

```bash
AZURE_OPENAI_API_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_MINI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview  # Optional
```

### CosmosDB (required if `COSMOS_ENABLED=true`)

```bash
AZURE_COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
AZURE_COSMOS_KEY=your-primary-key
AZURE_COSMOS_DATABASE_NAME=quickscribe  # Optional
```

### Blob Storage (required if `BLOB_STORAGE_ENABLED=true`)

```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_AUDIO_CONTAINER_NAME=audio-files  # Optional
AZURE_STORAGE_QUEUE_NAME=audio-processing-queue  # Optional
```

### Speech Services (required if `SPEECH_SERVICES_ENABLED=true`)

```bash
AZURE_SPEECH_SUBSCRIPTION_KEY=your-speech-key
AZURE_SPEECH_REGION=eastus
```

### Plaud API (required if `PLAUD_ENABLED=true`)

```bash
PLAUD_API_BASE_URL=https://webapp.plaud.ai  # Optional
```

## Usage Examples

### Minimal Configuration (Testing)

```bash
# Disable all optional features for testing
AI_ENABLED=false
COSMOS_ENABLED=false
BLOB_STORAGE_ENABLED=false
SPEECH_SERVICES_ENABLED=false
PLAUD_ENABLED=false
```

```python
settings = get_settings()
# All feature flags will be False
# No Azure service credentials required
```

### Production Configuration

```bash
# Enable required services
COSMOS_ENABLED=true
BLOB_STORAGE_ENABLED=true
SPEECH_SERVICES_ENABLED=true
AI_ENABLED=true
PLAUD_ENABLED=false

# Provide required credentials
AZURE_COSMOS_ENDPOINT=...
AZURE_COSMOS_KEY=...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_SPEECH_SUBSCRIPTION_KEY=...
AZURE_SPEECH_REGION=eastus
AZURE_OPENAI_API_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_MINI_DEPLOYMENT_NAME=gpt-4o-mini
```

### Testing Configuration

For unit tests, you can disable `fail_fast` and provide mock settings:

```python
import os

# Set test environment variables
os.environ['AI_ENABLED'] = 'false'
os.environ['COSMOS_ENABLED'] = 'false'
os.environ['BLOB_STORAGE_ENABLED'] = 'false'
os.environ['SPEECH_SERVICES_ENABLED'] = 'false'

# Load config without exiting on error
settings = get_settings(fail_fast=False)

if settings is None:
    # Handle missing config for test
    pytest.skip("Configuration not available")
```

## Migration Guide

### Before (Old Approach)

```python
# Scattered environment variable access
cosmos_endpoint = os.environ.get('AZURE_COSMOS_ENDPOINT')
if not cosmos_endpoint:
    logger.error("Missing AZURE_COSMOS_ENDPOINT")
    # Continue anyway, fail later...

# Manual validation in each component
def _check_ai_postprocessing_config(self) -> bool:
    required_vars = [
        "AZURE_OPENAI_API_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_MINI_DEPLOYMENT_NAME"
    ]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        self.logger.warning(f"Missing: {', '.join(missing_vars)}")
        return False
    return True
```

### After (New Approach)

```python
# main.py - Validate once at startup
from shared_quickscribe_py.config import get_settings

try:
    settings = get_settings()
except SystemExit:
    # Configuration validation failed - already logged
    pass

# Use throughout application
if settings.ai_enabled:
    # Safe to access - validation ensures it exists
    client = AzureOpenAIClient(
        endpoint=settings.azure_openai.api_endpoint,
        api_key=settings.azure_openai.api_key,
        deployment_name=settings.azure_openai.deployment_name
    )
```

## Advantages Over Previous Approach

1. **Fail Fast**: Errors at startup, not during processing
2. **No Manual Validation**: Remove all `_check_*_config()` methods
3. **Type Safety**: IDE autocomplete and type checking work
4. **Single Source of Truth**: One model defines all configuration
5. **Self-Documenting**: Field descriptions serve as documentation
6. **Testability**: Easy to mock entire configuration
7. **Feature Flags**: Clear control over optional features

## Testing

Run the test suite:

```bash
cd shared_quickscribe_py
python test_config.py
```

Expected output:
```
✓ PASS: Minimal config
✓ PASS: Missing Azure OpenAI
✓ PASS: Complete AI config
```

## Architecture

The configuration system uses Pydantic's `BaseSettings` with custom validators:

1. **Feature Flags** determine which settings are required
2. **Field Validators** conditionally instantiate nested settings
3. **ValidationError** raised at startup if required settings missing
4. **Environment Variables** automatically mapped to Pydantic fields

```
QuickScribeSettings
├── Feature Flags (ai_enabled, cosmos_enabled, etc.)
├── Core Settings (service_name, environment, log_level)
└── Conditional Nested Settings
    ├── AzureOpenAISettings (if ai_enabled)
    ├── CosmosDBSettings (if cosmos_enabled)
    ├── BlobStorageSettings (if blob_storage_enabled)
    ├── SpeechServicesSettings (if speech_services_enabled)
    └── PlaudAPISettings (if plaud_enabled)
```

## Best Practices

1. **Load Once**: Instantiate `QuickScribeSettings` once at application startup
2. **Dependency Injection**: Pass the settings object to components that need it
3. **Check Feature Flags**: Always check `settings.{feature}_enabled` before accessing nested settings
4. **Avoid Global State**: Pass settings explicitly rather than using a global singleton
5. **Test Configuration**: Use `get_settings(fail_fast=False)` in tests

## Troubleshooting

### Configuration Validation Failed

If you see validation errors at startup:

1. Check that all required environment variables are set
2. Verify feature flags match your intended configuration
3. Review `.env.template` for expected variable names
4. Check for typos in environment variable names

### Missing Module: pydantic_settings

```bash
pip install pydantic-settings
```

Or reinstall the shared package:

```bash
cd shared_quickscribe_py
pip install -e .
```

## Related Files

- `settings.py` - Main configuration models
- `__init__.py` - Exports configuration classes
- `../.env.template` - Template for environment variables
- `../test_config.py` - Configuration test suite
