# Transcoding Callback Implementation Guide

This document explains how the transcoding callback mechanism works in the updated architecture and how to test it.

## Architecture Overview

1. When a file is uploaded through the `/upload` endpoint:
   - The file is stored in Azure Blob Storage
   - A record is created in the database with `transcoding_status=queued`
   - A message is sent to the Azure Storage Queue with the necessary info and callback URLs
   - A unique token is stored with the recording for callback authentication

2. The Azure Container App:
   - Polls the queue for new messages
   - Processes the transcoding job (converts audio to MP3)
   - Sends callbacks to notify of progress changes:
     - `in_progress` when it starts
     - `completed` when successful (with metadata)
     - `failed` if errors occur (with error details)

3. The backend's `/api/transcoding_callback` endpoint:
   - Receives the callbacks from the container
   - Updates the recording status in the database
   - Stores metadata like duration, error messages, etc.

## Testing the Callback Implementation

We've provided a test script to simulate callbacks from the container. Here's how to use it:

### 1. First, create a test recording:

```
curl -X POST -F "file=@sample.mp3" http://localhost:5000/api/upload
```

Note the `recording_id` and `transcoding_token` in the response.

### 2. Run the test script with various parameters:

```bash
# Test with in_progress status:
python3 test_callback.py --recording-id <ID> --token <TOKEN> --status in_progress

# Test with completed status:
python3 test_callback.py --recording-id <ID> --token <TOKEN> --status completed --duration 175.5

# Test with failed status:
python3 test_callback.py --recording-id <ID> --token <TOKEN> --status failed --error "Invalid audio format"

# Test the test message:
python3 test_callback.py --action test
```

### 3. Check the recording status:

```
curl http://localhost:5000/api/transcoding_status/<RECORDING_ID>
```

## Common Issues

- **Authentication Failure**: Ensure the token matches the one stored with the recording
- **Missing Fields**: The callback must include `action`, `recording_id`, and `status`
- **Invalid Status**: Status must be one of: `in_progress`, `completed`, or `failed`

## Next Steps

- Add monitoring to track failed transcoding jobs
- Implement automatic retries for failed jobs
- Add notification when transcoding is complete
