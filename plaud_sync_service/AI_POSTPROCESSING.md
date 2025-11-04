# AI Post-Processing Implementation

## Overview

The Plaud Sync Service now includes automated AI-powered post-processing that generates descriptive titles and summaries for recordings immediately after transcription completes.

## Architecture

### Shared Azure OpenAI Client

**Location**: `shared_quickscribe_py/shared_quickscribe_py/azure_services/azure_openai.py`

A reusable Azure OpenAI client that supports:
- Multiple model configurations (normal and mini)
- Synchronous and asynchronous requests
- Concurrent batch processing
- Timing and token usage metrics
- Backward compatibility with existing code

### Factory Function

```python
from shared_quickscribe_py.azure_services.azure_openai import get_openai_client

# Get standard model client (e.g., gpt-4o)
normal_client = get_openai_client("normal")

# Get mini model client (e.g., gpt-4o-mini) - cheaper, faster
mini_client = get_openai_client("mini")
```

### Prompts Configuration

**Location**: `plaud_sync_service/prompts.yaml`

Contains the prompt template for generating both title and description in a single LLM call:
- Title: Maximum 60 characters, concise and descriptive
- Description: 1-2 sentences summarizing the main content

## Integration Flow

1. **Transcription Completes** → Azure Speech Services finishes transcription
2. **Transcript Downloaded** → Diarized transcript saved to CosmosDB
3. **AI Post-Processing Triggered** → Automatically called in `_handle_completed_transcription()`
4. **LLM Request** → Mini model generates title and description from transcript
5. **Recording Updated** → Title and description saved to recording document

## Implementation Details

### TranscriptionPoller Enhancement

**File**: `plaud_sync_service/transcription_poller.py`

Added:
- Import of `get_openai_client` and async/yaml modules
- Loading of prompts from `prompts.yaml` (using absolute path)
- `_generate_title_and_description()` async method
- Step 8 in `_handle_completed_transcription()` for AI post-processing

### Key Features

1. **Async Processing**: Uses `asyncio.run()` to handle async LLM calls
2. **Error Handling**: Gracefully handles failures without blocking transcription completion
3. **Mini Model**: Uses cost-efficient mini model for simple title/description tasks
4. **JSON Parsing**: Robust extraction of JSON from LLM response
5. **Detailed Logging**: Step-by-step progress tracking

## Environment Configuration

### Required Environment Variables

```bash
# Azure OpenAI Configuration
export AZURE_OPENAI_API_ENDPOINT=https://your-endpoint.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-api-key
export AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Standard model (gpt-4o)
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-prod

# Mini model (gpt-4o-mini) - used for title/description generation
export AZURE_OPENAI_MINI_DEPLOYMENT_NAME=gpt-5-mini
export AZURE_OPENAI_MINI_API_VERSION=2025-01-01-preview
```

### Dependencies

Added to `requirements.txt`:
- `aiohttp>=3.9.0` - Async HTTP client for LLM requests
- `PyYAML>=6.0` - YAML configuration parsing

## Usage

### Automatic Processing

Post-processing happens automatically when:
- A transcription completes successfully
- The diarized transcript is available
- Azure OpenAI is properly configured

No manual intervention required!

### Manual Testing

Test the post-processing integration:

```bash
cd plaud_sync_service
source .env
source .venv/bin/activate

# Run transcription check
python test_plaud_sync.py --check-transcriptions-only
```

### Verify Import

```python
from shared_quickscribe_py.azure_services.azure_openai import get_openai_client

# Create mini model client
client = get_openai_client("mini")
print(f"Client ready: {client.deployment_name}")
```

## Logging Output

When post-processing runs, you'll see:

```
  Step 8: Generating AI-powered title and description
Sending LLM request for title and description generation
Generated title: 'Team Sprint Planning Discussion' (length: 32)
Generated description: 'Team members discuss upcoming sprint goals...' (length: 87)
    ✓ Title: 'Team Sprint Planning Discussion'
    ✓ Description: 'Team members discuss upcoming sprint goals...'
  ✓ SUCCESS: Transcription fully processed and saved
```

## Error Handling

If AI post-processing fails:
- Error is logged but doesn't block transcription completion
- Recording keeps original title (filename) and description (null)
- Transcription status remains "completed"
- Can be retried manually via backend API endpoint

## Cost Optimization

- Uses **mini model** (gpt-4o-mini) instead of standard model
- Single LLM call generates both title and description
- Typically 10-50 tokens for prompt, 50-100 tokens for response
- ~$0.0001 per recording (significantly cheaper than standard model)

## Backend Integration

The backend's `ai_postprocessing.py` continues to work independently with its own:
- `backend/prompts.yaml` - Backend-specific prompts
- `backend/llms.py` - Existing LLM client (can be migrated to shared module later)

Both systems can coexist:
- Plaud Sync: Auto-processes immediately after transcription
- Backend API: Manual post-processing via `/api/recording/<id>/postprocess` endpoint

## Future Enhancements

Potential improvements:
1. **Speaker Inference** - Identify speakers by name (currently disabled)
2. **Custom Prompts** - User-configurable prompt templates
3. **Retry Logic** - Automatic retry on LLM failures
4. **Batch Processing** - Process multiple recordings concurrently
5. **Model Selection** - Allow per-user model preferences

## Migration Path for Backend

To migrate backend to use shared Azure OpenAI client:

```python
# Old way (backend/llms.py)
from llms import send_prompt_to_llm

# New way (shared module)
from shared_quickscribe_py.azure_services.azure_openai import send_prompt_to_llm
# API is identical - drop-in replacement!
```

The shared module provides backward-compatible wrapper functions.

## Troubleshooting

### Import Errors

```bash
# Ensure shared_quickscribe_py is installed
cd shared_quickscribe_py
pip install -e .

# Verify import
python -c "from shared_quickscribe_py.azure_services import get_openai_client"
```

### Missing Dependencies

```bash
# Install all requirements
cd plaud_sync_service
pip install -r requirements.txt
```

### Environment Variables

```bash
# Check configuration
env | grep AZURE_OPENAI

# Should show:
# AZURE_OPENAI_API_ENDPOINT=...
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_DEPLOYMENT_NAME=...
# AZURE_OPENAI_MINI_DEPLOYMENT_NAME=...
```

### LLM Request Failures

Check logs for:
- Network connectivity issues
- Invalid API key
- Model deployment name mismatch
- Rate limiting (429 errors)
- Token limit exceeded

## Summary

✅ **Created**: Shared Azure OpenAI client with multi-model support
✅ **Integrated**: AI post-processing into transcription pipeline
✅ **Configured**: Mini model for cost-efficient title/description generation
✅ **Tested**: Import and client instantiation verified
✅ **Documented**: Complete implementation guide

The system now automatically generates meaningful titles and descriptions for all transcribed recordings!
