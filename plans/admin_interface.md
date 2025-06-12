# Transcription Database Admin Interface Specification

## Overview
Build a web-based admin interface for managing a transcription application database stored in Azure Cosmos DB. The interface should provide intuitive navigation through related data using a macOS Finder-style column navigation system.

## Data Model
The system manages six main entity types stored across separate Cosmos DB containers:

### Entity Types
- **Users**: Application users who own recordings
- **Recordings**: Audio/video files uploaded for transcription
- **Transcriptions**: Processed transcription results from recordings
- **AI Analyses**: AI-generated insights from transcriptions (summaries, action items, etc.)
- **Participants**: People who appear in recordings/meetings
- **Tags**: User-defined labels for organizing transcriptions and recordings

### Relationships
- **User → Recordings**: One-to-many (user owns multiple recordings)
- **User → Participants**: One-to-many (user defines participants in their scope)
- **User → Tags**: One-to-many (user creates their own tags)
- **Recording → Transcription**: One-to-one (recording may have one transcription)
- **Recording → Participants**: Many-to-many (recording can have multiple participants)
- **Transcription → AI Analyses**: One-to-many (transcription can have multiple analyses)
- **Transcription → Tags**: Many-to-many (transcription can have multiple tags)

*Note: All data is scoped by user - no cross-user relationships exist*

## Core Features

### 1. Column-Based Navigation (Primary Feature)
Implement macOS Finder-style navigation where each interaction opens a new column to the right:

**Navigation Flow:**
1. **Overview Column**: Database summary with entity counts and quick access
2. **List Column**: Shows all items of selected entity type
3. **Detail Column**: Shows specific item details and related items
4. **Relation Column**: Shows filtered list of related items
5. Continue drilling down indefinitely

**Column Behavior:**
- Horizontal scrolling to view navigation history
- Click breadcrumb to jump back to any previous level
- Adjustable column widths via drag handles
- Persist column state between sessions
- Each column width: 320px default, min 280px, max 500px

### 2. Data Integrity Checks
Implement comprehensive consistency validation accessible via "Find Orphaned Records" button:

**Check Types:**
- **Broken References**: Find IDs that reference non-existent records
- **Missing Required Relationships**: Records that should have relationships but don't
- **Circular References**: Detect unexpected relationship loops
- **Duplicate Detection**: Same names/identifiers within user scope
- **Schema Validation**: Records missing required fields or with wrong types
- **Usage Analysis**: Unused tags, participants with zero recordings

**Results Display:**
- Show issues in a dedicated column with severity levels
- Group by issue type with counts
- Click to navigate to problematic records
- Export issues list for external analysis

### 3. Overview Dashboard
**Entity Cards:**
- Show count for each entity type (Users: 23, Recordings: 156, etc.)
- Click card to open entity list
- Visual indicators for entities with issues

**Global Search:**
- Search across all entity types
- Results grouped by entity type
- Click result to navigate directly to item

**Quick Actions Panel:**
- Find orphaned records
- Export all data
- Bulk operations launcher

### 4. List Views
**Features for each entity list:**
- Sortable columns (name, date, status, etc.)
- Virtual scrolling for large lists
- Bulk selection with checkboxes
- Hover actions: Edit, Delete buttons
- Filter/search within entity type
- Add new item button

**List Item Display:**
- Primary identifier (name, filename, etc.)
- Secondary info (date, status, count)
- Visual indicators for relationships
- Quick action buttons on hover

### 5. Detail Views
**Item Details Section:**
- All field values in organized grid
- Edit and Delete buttons in header
- Field labels formatted (camelCase → Proper Case)

**Related Items Section:**
- Cards for each relationship type
- Show count and relationship type
- Click to open related items in new column
- Icons for each entity type

### 6. Bulk Operations
**Selection Interface:**
- Multi-select checkboxes in list views
- "Select All" option with filters
- Selected item counter
- Clear selection button

**Available Operations:**
- Bulk delete with cascade preview
- Bulk tag operations (add/remove tags)
- Bulk relationship updates (reassign to different user/parent)
- Export selected items

### 7. Safety Features
**Delete Confirmations:**
- Show exactly what will be deleted in cascading deletes
- Item counts by type
- "This will delete: 1 recording, 1 transcription, 3 analyses"
- Require typing "DELETE" for major operations

**Data Export:**
- Export entire database or selected items
- JSON format with relationship preservation
- Triggered manually or before major operations

### 8. Navigation Enhancements
**Breadcrumb Trail:**
- Show current navigation path
- Click any breadcrumb to jump back
- Visual separation between levels

**Recent Activity:**
- Panel showing last 10 viewed/edited items
- Quick navigation back to recent items
- Persist across sessions

**Favorites/Bookmarks:**
- Star button on detail views
- Quick access panel in overview
- Persist user's bookmarked items

### 9. Keyboard Shortcuts
- **Arrow Keys**: Navigate between columns and items
- **Enter**: Open selected item
- **Delete**: Delete selected item(s) with confirmation
- **Escape**: Close current column
- **Ctrl+F**: Focus global search
- **Ctrl+A**: Select all in current list

## Technical Requirements

### Frontend Framework
- **React** with TypeScript
- **Tailwind CSS** for styling
- **Lucide React** for icons

### State Management
- React useState/useReducer for local state
- No external state management library required
- Persist navigation state and preferences in localStorage

### Data Loading
- Fetch data from REST API endpoints
- Load data progressively as columns are opened
- Cache loaded data to avoid redundant requests
- Handle loading states with skeletons

### Performance Considerations
- Virtual scrolling for lists with 100+ items
- Debounced search input
- Lazy load relationship data
- Optimized re-renders with React.memo where appropriate

### Responsive Design
- Minimum viewport width: 1024px (desktop-focused admin tool)
- Horizontal scrolling for column navigation
- Collapsible sidebar for narrow screens

## API Requirements

### Endpoints Needed
```
GET /api/admin/overview - Entity counts and summary
GET /api/admin/{entityType} - List all entities of type
GET /api/admin/{entityType}/{id} - Get specific entity with relationships
GET /api/admin/{entityType}/{id}/related/{relationType} - Get related entities
POST /api/admin/integrity-check - Run data consistency checks
DELETE /api/admin/{entityType}/{id} - Delete entity with cascading
PUT /api/admin/{entityType}/{id} - Update entity
POST /api/admin/bulk-operations - Perform bulk operations
GET /api/admin/export - Export data
GET /api/admin/search?q={query} - Global search
```

### Error Handling
- Display user-friendly error messages
- Handle network failures gracefully
- Show loading states during operations
- Validate user input before submission

## User Experience Goals
- **Intuitive Navigation**: Users should easily understand how to drill down through relationships
- **Fast Operations**: Common tasks should require minimal clicks
- **Safe Operations**: Destructive actions should be clearly confirmed
- **Discoverable Features**: Important features should be easily found
- **Consistent Interface**: Similar operations should work the same way across entity types

## Development Priority
1. Core column navigation system
2. Basic CRUD operations
3. Data integrity checks
4. Bulk operations
5. Enhanced navigation features
6. Keyboard shortcuts
7. Export functionality

This specification should provide a comprehensive foundation for building a powerful, user-friendly admin interface for the transcription database.
