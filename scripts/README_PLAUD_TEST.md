# Plaud Sync Integration Test

This script provides comprehensive testing of the Plaud sync functionality in the QuickScribe application.

## Prerequisites

1. **Docker Environment**: Make sure docker-compose is running with all services:
   ```bash
   cd /home/cbird/repos/quickscribe
   docker-compose up -d
   ```

2. **Python Dependencies**: Install required packages:
   ```bash
   cd scripts
   pip install -r requirements_test.txt
   ```

3. **Configuration**: Copy and configure the environment file:
   ```bash
   cp .env.test .env.test.local
   # Edit .env.test.local with your actual values
   ```

## Configuration

Edit `.env.test.local` with your actual values:

```bash
# Plaud Configuration (REQUIRED)
PLAUD_BEARER_TOKEN=your-actual-plaud-bearer-token

# Backend Configuration (adjust if needed)
BACKEND_URL=http://localhost:5000

# Test Configuration (optional)
TEST_USER_PREFIX=test-plaud
TEST_USER_ID=test-plaud-1749019682-0bdf  # Optional: Use specific user ID instead of creating new one
MAX_RECORDINGS_TO_SYNC=3
MONITOR_TIMEOUT=180

# Azure Configuration (copy from backend/.env.local)
AZURE_STORAGE_CONNECTION_STRING=your-storage-connection-string
COSMOS_URL=your-cosmos-endpoint
COSMOS_KEY=your-cosmos-key
COSMOS_DB_NAME=quickscribe
AZURE_RECORDING_BLOB_CONTAINER=recordings
```

## Usage

### Test Mode (Default)
Runs the complete test flow. Creates temporary user if no TEST_USER_ID is set, or uses existing user if TEST_USER_ID is configured:
```bash
python test_plaud_sync.py
# or explicitly:
python test_plaud_sync.py --mode test
```

### Monitor Existing Sync
Monitor an already running sync operation:
```bash
python test_plaud_sync.py --mode monitor --user-id your-user-id
# or if TEST_USER_ID is set in config:
python test_plaud_sync.py --mode monitor
```

### Cleanup Mode
Clean up all recordings and blobs for a user:
```bash
python test_plaud_sync.py --mode cleanup --user-id your-user-id
# or if TEST_USER_ID is set in config:
python test_plaud_sync.py --mode cleanup
```

## What the Test Does

1. **Health Check**: Verifies all services are running (backend, CosmosDB, Azure Storage, Docker containers)

2. **Smart Recording Limit**: Queries your Plaud account and sets a sync timestamp to only process the last 2-3 recordings

3. **Test User Creation**: Creates a test user with `is_test_user: true` to bypass authentication

4. **Sync Trigger**: Calls the `/plaud/sync/start` endpoint to initiate the sync

5. **Real-time Monitoring**: 
   - Monitors CosmosDB for new recording entries
   - Watches Docker logs from backend and transcoder containers
   - Shows progress updates in real-time

6. **Verification**: 
   - Checks that recordings were created in CosmosDB
   - Verifies blob files exist in Azure Storage
   - Validates metadata (status, duration, size)

7. **Cleanup (for temporary users only)**: 
   - If TEST_USER_ID is configured, cleanup is skipped
   - For temporary users: deletes user, recording entries, and blob files
   - Shows confirmation before cleanup

## Sample Output

```
🎯 Starting Plaud Sync Integration Test
============================================================

🔍 Checking prerequisites...
✅ Backend API is responsive
✅ CosmosDB connection works
✅ Azure Storage connection works
✅ Container quickscribe-backend-1 is running
✅ Container quickscribe-transcoder-1 is running

👤 Creating test user...
ℹ️  Found 45 recordings in Plaud account
ℹ️  Will sync last 3 recordings
ℹ️  Setting sync timestamp: 2024-01-13T10:30:00+00:00
✅ Created test user: test-plaud-1705311000-a3f2

🔐 Logging in as test user...
✅ Logged in successfully

🚀 Triggering Plaud sync...
✅ Sync triggered - Token: 5d3e-4f2a-9b1c-3d8e

📊 Monitoring sync progress...
Press Ctrl+C to stop monitoring

📥 New recording: meeting_2024-01-15.mp3
    ID: rec_123456
    Status: completed
    Duration: 245s

─── Recent Docker Logs ───
[backend] 10:30:09: Received Plaud sync request
[transcoder] 10:30:10: Processing plaud_sync message
[transcoder] 10:30:15: Downloading recording 1/3

📈 Progress: 3 recordings processed (75s elapsed)

🔍 Verifying results...
✅ Found 3 recordings

📁 Verifying recording: meeting_2024-01-15.mp3
  ✅ Blob exists (2,456,789 bytes)
  📊 Status: completed
  ⏱️  Duration: 245s
  ✅ Recording processed successfully

🎉 Test completed successfully!

🧹 Starting cleanup...
🗑️  Deleting 3 recording entries...
🗑️  Deleting 3 blob files...
🗑️  Deleting test user: test-plaud-1705311000-a3f2

📋 Cleanup Summary:
  Recordings deleted: 3
  Blobs deleted: 3
  User deleted: ✅

✅ Cleanup completed successfully
```

## Error Handling

- **Graceful Shutdown**: Press Ctrl+C to stop monitoring and run cleanup
- **Automatic Cleanup**: Failed tests automatically clean up test data
- **Service Checks**: Validates all required services before starting
- **Detailed Logging**: Shows Docker container logs for debugging

## Troubleshooting

1. **"Container not found"**: Ensure docker-compose is running
2. **"Backend API not responsive"**: Check if backend container is healthy
3. **"CosmosDB connection failed"**: Verify Azure credentials in config
4. **"Plaud API failed"**: Check your bearer token is valid
5. **"No recordings found"**: The sync may have completed too quickly, check Azure logs

## Safety Features

- All test resources are prefixed with `test-` to prevent accidental deletion of real data
- Confirmation prompt before cleanup
- Only test users with `is_test_user: true` can be cleaned up
- Smart timestamp limiting prevents syncing entire Plaud account
- Configured users (via TEST_USER_ID) are never automatically cleaned up