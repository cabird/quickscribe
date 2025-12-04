# QuickScribe - Deleted Recording Solution

## Problem Statement

When a user deletes a recording in the UI:
1. Recording document is removed from CosmosDB
2. Blob is deleted from Azure Storage
3. Transcription is removed

On the next Plaud sync:
- Deduplication only checks existing recordings by `plaudId`
- Deleted recording's `plaudId` is no longer in the database
- Sync service sees it as "new" and re-downloads it
- **Result**: Deleted recordings reappear after every sync

## Solution: Deleted Items Collection

Create a separate, lightweight collection to track deleted Plaud recordings permanently.

### Design Principles

1. **Permanent Deletion**: Once deleted, stays deleted unless explicitly unblocked
2. **No TTL**: Deleted records remain indefinitely (no automatic expiration)
3. **Separation of Concerns**: Don't pollute main recordings collection with deleted items
4. **Storage Efficiency**: Small records (just IDs and timestamps)
5. **Explicit Unblock**: User must intentionally remove from deleted list to re-sync

---

## Data Model

### New Collection: `deleted_plaud_recordings`

**Partition Key**: `userId`

**Document Structure**:
```typescript
{
  id: string;                    // Format: "deleted-{plaudId}"
  partitionKey: string;          // userId (for efficient queries)
  userId: string;                // User who deleted this recording
  plaudId: string;               // Original Plaud recording ID
  originalRecordingId: string;   // Reference to deleted recording (optional)
  deletedAt: string;             // ISO timestamp of deletion
  deletedBy: string;             // "user" | "admin" | "system"
  reason?: string;               // Optional reason for deletion
  type: "deleted_plaud_recording" // Document type discriminator
}
```

**Example Document**:
```json
{
  "id": "deleted-plaud_rec_20250104_123456",
  "partitionKey": "user-abc-123",
  "userId": "user-abc-123",
  "plaudId": "plaud_rec_20250104_123456",
  "originalRecordingId": "rec-xyz-789",
  "deletedAt": "2025-11-04T12:34:56.789Z",
  "deletedBy": "user",
  "type": "deleted_plaud_recording"
}
```

---

## Implementation Details

### 1. Recording Deletion Flow (Backend)

When user deletes a recording from UI:

```python
def delete_recording(recording_id: str, user_id: str):
    # 1. Fetch the recording
    recording = recording_handler.get_recording(recording_id)

    # 2. If it has a plaudId, create deleted item
    if recording.plaudId:
        deleted_item = {
            "id": f"deleted-{recording.plaudId}",
            "partitionKey": user_id,
            "userId": user_id,
            "plaudId": recording.plaudId,
            "originalRecordingId": recording.id,
            "deletedAt": datetime.now(UTC).isoformat(),
            "deletedBy": "user",
            "type": "deleted_plaud_recording"
        }
        deleted_plaud_handler.create_deleted_item(deleted_item)

    # 3. Delete the blob
    if recording.audio_file_url:
        blob_client.delete_blob(recording.audio_file_url)

    # 4. Delete transcription
    transcription_handler.delete_transcription(recording.transcription_id)

    # 5. Delete recording
    recording_handler.delete_recording(recording_id)
```

### 2. Deduplication in Plaud Sync Service

**Current Code** (`job_executor.py`):
```python
# Fetch existing Plaud IDs from recordings
existing_plaud_ids = self.recording_handler.get_user_plaud_ids(user.id)
```

**New Code**:
```python
# Fetch existing Plaud IDs from recordings
existing_plaud_ids = self.recording_handler.get_user_plaud_ids(user.id)

# Fetch deleted Plaud IDs
deleted_plaud_ids = self.deleted_plaud_handler.get_user_deleted_plaud_ids(user.id)

# Combine both for deduplication
all_blocked_ids = existing_plaud_ids + deleted_plaud_ids

# Pass to processor for filtering
processor.set_existing_plaud_ids(all_blocked_ids)
```

**Effect**:
- Deleted recordings are filtered out during deduplication
- Never get re-downloaded or processed
- User never sees them again

### 3. Database Handler

New handler: `DeletedPlaudRecordingHandler`

```python
class DeletedPlaudRecordingHandler:
    """Handles deleted Plaud recording tracking."""

    def __init__(self, cosmos_url, cosmos_key, database_name, container_name):
        self.client = CosmosClient(cosmos_url, cosmos_key)
        self.database = self.client.get_database_client(database_name)
        self.container = self.database.get_container_client(container_name)

    def create_deleted_item(self, deleted_item: dict):
        """Create a new deleted item record."""
        return self.container.create_item(deleted_item)

    def get_user_deleted_plaud_ids(self, user_id: str) -> List[str]:
        """Get all deleted Plaud IDs for a user."""
        query = """
            SELECT c.plaudId FROM c
            WHERE c.type = 'deleted_plaud_recording'
            AND c.userId = @user_id
        """
        parameters = [{"name": "@user_id", "value": user_id}]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            partition_key=user_id
        ))

        return [item['plaudId'] for item in items]

    def get_all_deleted_items(self, user_id: str) -> List[dict]:
        """Get all deleted items for a user (for UI display)."""
        query = """
            SELECT * FROM c
            WHERE c.type = 'deleted_plaud_recording'
            AND c.userId = @user_id
            ORDER BY c.deletedAt DESC
        """
        parameters = [{"name": "@user_id", "value": user_id}]

        return list(self.container.query_items(
            query=query,
            parameters=parameters,
            partition_key=user_id
        ))

    def unblock_recording(self, user_id: str, plaud_id: str):
        """Remove from deleted list (allows re-sync)."""
        deleted_id = f"deleted-{plaud_id}"
        self.container.delete_item(
            item=deleted_id,
            partition_key=user_id
        )
```

---

## UI Features

### 1. Recording Deletion
- Delete button → shows confirmation
- On confirm: Backend creates deleted item + removes recording
- Toast: "Recording deleted. It will not sync from Plaud again."

### 2. Deleted Items Management (Admin/Settings)

New section in user settings: **Blocked Plaud Recordings**

Shows table:
| Plaud ID | Original Filename | Deleted Date | Action |
|----------|-------------------|--------------|--------|
| plaud_rec_... | Meeting 2025-11-04 | Nov 4, 2025 | [Unblock] |

**Unblock Action**:
- Removes from deleted collection
- Next sync will re-download from Plaud
- Toast: "Recording unblocked. It will sync on next Plaud sync."

---

## Database Queries

### Create Index
For efficient deleted ID lookups:
```sql
{
  "indexingMode": "consistent",
  "includedPaths": [
    {
      "path": "/userId/?"
    },
    {
      "path": "/plaudId/?"
    },
    {
      "path": "/deletedAt/?"
    }
  ]
}
```

### Common Queries

**Get all deleted IDs for user** (for deduplication):
```sql
SELECT c.plaudId FROM c
WHERE c.type = 'deleted_plaud_recording'
AND c.userId = @user_id
```

**Get deleted items for UI**:
```sql
SELECT * FROM c
WHERE c.type = 'deleted_plaud_recording'
AND c.userId = @user_id
ORDER BY c.deletedAt DESC
```

**Check if specific recording is deleted**:
```sql
SELECT * FROM c
WHERE c.type = 'deleted_plaud_recording'
AND c.userId = @user_id
AND c.plaudId = @plaud_id
```

---

## Migration Plan

### Phase 1: Backend Setup
1. Add `DeletedPlaudRecordingHandler` to `shared_quickscribe_py/cosmos/`
2. Update recording deletion endpoint to create deleted items
3. Deploy backend changes

### Phase 2: Plaud Sync Service
1. Update `job_executor.py` deduplication logic
2. Fetch deleted IDs alongside existing IDs
3. Pass combined list to processor
4. Test with known deleted recordings
5. Deploy Plaud sync service

### Phase 3: UI (Optional - Can do later)
1. Add "Blocked Recordings" section to settings
2. Display deleted items table
3. Add "Unblock" functionality
4. Test unblock → sync flow

### Phase 4: Backfill (If Needed)
If users have already deleted Plaud recordings that keep re-syncing:
- Create admin script to identify and mark them
- Query recordings with `plaudId` that user has deleted multiple times
- Create deleted items retroactively

---

## Edge Cases

### What if user deletes, then unblocks, then deletes again?
- First delete: Creates deleted item
- Unblock: Removes deleted item
- Next sync: Re-downloads from Plaud
- Second delete: Creates new deleted item again
- **Works as expected**

### What if Plaud API changes recording IDs?
- Deleted items tied to old Plaud ID
- New Plaud ID would not be blocked
- Recording would re-sync with new ID
- **Mitigation**: Also store original filename/timestamp for fuzzy matching (future enhancement)

### What if user wants to "clear" all blocks?
- Admin endpoint: Delete all deleted items for user
- Next sync: Re-downloads everything from Plaud
- **Use case**: User wants fresh start

### What if deleted item exists but no recording?
- Harmless - just filters during deduplication
- Deleted item prevents re-download
- **Works as expected**

---

## Storage Considerations

### Size Estimate
- Each deleted item: ~200 bytes
- 1000 deleted items: ~200 KB
- 10,000 deleted items: ~2 MB
- **Conclusion**: Negligible storage cost

### Partition Strategy
- Partition by `userId` for efficient user-scoped queries
- Matches recordings collection partition strategy
- Enables point reads with partition key

### No TTL Rationale
- TTL would auto-expire deleted items
- Recordings would re-sync unexpectedly
- User expects permanent deletion
- If user wants to unblock, they do it explicitly

---

## API Endpoints

### Backend (`/api/recordings`)

**DELETE /api/recordings/:id**
```typescript
// Deletes recording and creates deleted item
Response: {
  success: true,
  message: "Recording deleted permanently"
}
```

**GET /api/deleted-plaud-recordings**
```typescript
// Returns list of deleted items for current user
Response: {
  items: [
    {
      plaudId: "plaud_rec_...",
      deletedAt: "2025-11-04T12:34:56Z",
      originalRecordingId: "rec-xyz"
    }
  ]
}
```

**POST /api/deleted-plaud-recordings/:plaudId/unblock**
```typescript
// Removes from deleted list (allows re-sync)
Response: {
  success: true,
  message: "Recording unblocked. Will sync on next Plaud sync."
}
```

---

## Testing Strategy

### Unit Tests
1. `DeletedPlaudRecordingHandler` CRUD operations
2. Deduplication with deleted IDs
3. Unblock flow

### Integration Tests
1. Delete recording → creates deleted item
2. Sync service skips deleted IDs
3. Unblock → next sync re-downloads

### E2E Test Flow
1. User syncs Plaud → recording appears
2. User deletes recording → recording removed
3. Run sync again → recording does NOT reappear ✓
4. User unblocks recording
5. Run sync again → recording reappears ✓

---

## Future Enhancements

### 1. Fuzzy Matching
If Plaud changes IDs, match by:
- Original filename
- Recording duration
- Upload timestamp
- Audio file hash

### 2. Bulk Operations
- Delete multiple recordings at once
- Unblock multiple at once
- "Clear all blocks" option

### 3. Audit Trail
- Track who deleted (user vs admin vs system)
- Track reason for deletion
- Export deleted items history

### 4. Smart Suggestions
- "You've deleted this 3 times. Block permanently?"
- Suggest blocking recurring unwanted recordings

---

## Summary

**Solution**: Deleted Items Collection (No TTL)

**Benefits**:
✅ Deleted recordings never re-sync
✅ Clean separation from main recordings
✅ Explicit unblock if user changes mind
✅ Minimal storage footprint
✅ Simple deduplication logic
✅ No automatic expiration surprises

**Implementation**:
1. New `deleted_plaud_recordings` collection
2. Update deletion endpoint to create deleted items
3. Update deduplication to check deleted IDs
4. Optional UI for managing blocks

**Next Steps**:
1. Create `DeletedPlaudRecordingHandler` in shared package
2. Update backend delete endpoint
3. Update Plaud sync deduplication
4. Test end-to-end
5. Add UI (optional, can be later)
