# Collections — Implementation Plan

**Date**: 2026-03-25
**Status**: Building

## Overview

Collections are curated sets of recordings that users build collaboratively before running deep search. They bridge automatic discovery with manual refinement.

## Schema

```sql
CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL DEFAULT 'Untitled collection',
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE collection_items (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    added_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, recording_id)
);

CREATE TABLE collection_searches (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT,
    item_count INTEGER,
    item_set_hash TEXT,
    search_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

## API Endpoints

### Collections CRUD
- `GET /api/collections` — list user's collections with item counts
- `POST /api/collections` — create (name, description optional)
- `GET /api/collections/{id}` — get collection with items
- `PUT /api/collections/{id}` — update name/description
- `DELETE /api/collections/{id}` — delete collection

### Collection Items
- `POST /api/collections/{id}/items` — add recordings (body: {recording_ids: [...]})
- `DELETE /api/collections/{id}/items/{recording_id}` — remove one
- `POST /api/collections/{id}/items/search` — search recordings to add (FTS + date + speaker filters)

### Collection Search
- `POST /api/collections/{id}/search` — run deep search (Tier 2→3 only) on collection's recordings
- `GET /api/collections/{id}/searches` — query history for this collection

### From Search All
- `POST /api/collections/from-candidates` — create collection from deep search candidate IDs

## Frontend

### New nav item: "Collections" (between Search and Settings)

### Collections page — split view
- **Left sidebar** (300px):
  - Saved collections list (name, item count, last updated)
  - "New Collection" button
  - Active collection: name (editable), description, item count, date range
  - Collection items list (compact: title, date, remove button)
  - Sticky bottom: question textarea + "Search Collection" button
- **Right main pane**:
  - Search bar (FTS query)
  - Filters: date range, speaker dropdown
  - Results list with add/remove toggles (checkbox or +/- button)
  - Shows: title, date, speakers, search_summary snippet
  - Items already in collection are visually marked

### Search All integration
- After deep search results, show "Refine as Collection" button
- Creates a new collection pre-populated with Tier 1 candidates
- Navigates to Collections page with that collection active

### Collection search results
- Same answer display as Search All (markdown + citations + trace)
- Plus: query history section showing past questions on this collection
- "Collection changed" badge if items differ from last search

## Deep Search Changes

### New function: `search_collection(question, collection_id, user_id)`
- Load recording IDs from collection_items
- Skip Tier 1 entirely
- Run Tier 2 (extract) on each recording in parallel
- Run Tier 3 (synthesize)
- Save to collection_searches with item_set_hash
- Stream via SSE same as regular deep search

## Implementation Order
1. Database schema + migration
2. Backend: collection CRUD + items + search-to-add
3. Backend: collection deep search (Tier 2→3)
4. Backend: collection search history
5. Frontend: Collections page with split view
6. Frontend: Search All "Refine as Collection" integration
7. Frontend: collection search results + history
