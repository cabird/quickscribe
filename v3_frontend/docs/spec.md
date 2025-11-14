# Meeting Recordings Management System - Frontend Specification

## Overview
Build a web application frontend for managing, viewing, and searching meeting recordings and transcripts. The backend already exists and stores recordings/transcripts in Cosmos DB with metadata. This frontend should provide an Outlook-style interface for users to interact with their meeting data.

## Architecture Context
- **Backend**: Already built - handles recording processing, transcript generation, stores in Cosmos DB
- **Frontend**: React application (to be built)
- **Data Source**: Cosmos DB with meeting metadata (title, description, date, time, speakers, location, duration, transcript)

## UI Layout Requirements

### Main Layout Structure
Three-panel Outlook-style layout:
1. **Navigation Rail** (far left, 68px wide)
   - Dark themed vertical bar with icon buttons
   - Visual indicator for active view
   - Tooltip on hover

2. **Context Panel** (middle, ~35% width)
   - Changes based on selected navigation mode
   - In transcript mode: scrollable list of recordings

3. **Main Content Area** (right, remaining width)
   - Changes based on selected navigation mode
   - In transcript mode: full transcript viewer

## Core Features

### 1. Transcripts View (Primary View)
**List Panel:**
- Display all recordings as cards showing:
  - Title
  - Date & Time
  - Duration  
  - Speaker names (truncated if many)
  - Brief description
- Clickable items with hover state
- Visual selection indicator (green left border when selected)
- Scrollable list
- Real-time search filtering

**Transcript Viewer:**
- Header with full meeting details
- Timestamped transcript entries
- Speaker names clearly distinguished
- Clean, readable typography
- Scrollable content

**Top Action Bar:**
- Search input with dropdown for search mode (Basic/Full-text)
- Date range filter (All Time/This Week/This Month/Quarter)
- Export button (downloads selected transcript as .txt)
- Refresh button (re-fetches from backend)

### 2. Service Logs View
**Purpose:** Monitor backend service health and processing status

**Display:**
- Dark terminal-style background
- Color-coded log entries by level (Error=red, Warning=orange, Info=green, Debug=blue)
- Each log shows: timestamp, level badge, message
- Filterable by log level
- Clear and refresh actions

### 3. RAG Search View
**Purpose:** Semantic search across entire transcript corpus

**Interface:**
- Large textarea for natural language queries
- Examples placeholder text showing sample queries
- Search button triggers RAG search
- Results displayed as cards with:
  - Meeting title
  - Relevant snippet with search context
  - Relevance score
  - Date and speakers
  - Link to full transcript

## Functional Requirements

### Search Capabilities
1. **Basic Search**: Search by title, description, speaker names
2. **Full-text Search**: Search within transcript content
3. **RAG Search**: Semantic search using natural language queries across all transcripts

### Data Operations
- Fetch recordings list from backend API
- Fetch individual transcript details
- Export transcript to text file
- Refresh to get latest data

### State Management
- Track selected recording
- Track active navigation view
- Manage search/filter states
- Handle loading and error states

## Technical Requirements

### Technology Stack
- **Framework**: React
- **UI Library**: Fluent UI React v9 (@fluentui/react-components)
- **Icons**: Fluent UI Icons (@fluentui/react-icons)
- **Styling**: Fluent UI's makeStyles with design tokens

### API Integration
Backend endpoints needed:
- `GET /recordings` - List all recordings with metadata
- `GET /recordings/{id}` - Get specific recording with full transcript
- `GET /logs` - Get service logs
- `POST /search/rag` - Perform semantic search

### Browser Support
- Modern browsers (Chrome, Firefox, Safari, Edge)
- Responsive design (with mobile considerations for future)

## Data Models

### Recording Object
```javascript
{
  id: string,
  title: string,
  date: string,
  time: string,
  duration: string,
  speakers: string[],
  description: string,
  location?: string,
  transcript: TranscriptEntry[]
}
```

### Transcript Entry
```javascript
{
  time: string,  // "MM:SS" format
  speaker: string,
  text: string
}
```

### Log Entry
```javascript
{
  level: 'error' | 'warning' | 'info' | 'debug',
  time: string,
  message: string
}
```

### RAG Search Result
```javascript
{
  id: string,
  title: string,
  snippet: string,
  relevance: number,  // 0-100
  speakers: string,
  date: string
}
```

## User Experience Goals
- **Fast**: Instant search and filtering
- **Intuitive**: Outlook-familiar interface
- **Efficient**: Minimize clicks to access information
- **Professional**: Clean, business-appropriate design
- **Accessible**: Keyboard navigation and screen reader support

## Future Considerations
- Audio playback synchronized with transcript
- Edit/correct transcripts
- Add comments/annotations
- Bulk operations on multiple recordings
- Advanced analytics dashboard
- Mobile responsive design
- Dark mode theme

## Reference Implementation
See provided Fluent UI React example code for visual design patterns and component structure.

---

*Note: The provided example code demonstrates the complete UI implementation with mock data. The production version should replace mock data with actual API calls to the backend service.*
