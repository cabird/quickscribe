# QuickScribe New Frontend

A modern React frontend for the QuickScribe audio transcription application, built with Vite, TypeScript, and Mantine v7.

## Features

✅ **Complete Layout Implementation**
- Modern tabbed sidebar with Upload, Browse, and Settings tabs
- Responsive main content area with grid/list view toggle
- Beautiful gradient backgrounds following Mantine design principles

✅ **Recording Management**
- Enhanced recording cards with status indicators
- Tag management with color-coded badges
- Real-time transcription status updates
- Optimistic UI updates for smooth user experience

✅ **Tag System**
- Full CRUD operations for tags
- Color-coded tag system
- Tag filtering and search functionality
- Automatic tag count displays

✅ **AI Workspace (Visual)**
- Modal interface for AI analysis tools
- Visual simulation of AI processing
- Results display with copy/export functionality
- Recording details and transcript preview

✅ **State Management**
- Zustand for global state management
- Optimistic updates for tags and recordings
- Real-time status polling
- Preserved existing event system for compatibility

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Mantine v7** for UI components and theming
- **Zustand** for state management
- **Axios** for API communication
- **React Router** for navigation

## Getting Started

### Prerequisites
- Node.js 18+
- Backend running on localhost:5000 (via Docker Compose)

### Installation

```bash
cd frontend_new
npm install
```

### Development

```bash
npm run dev
```

The frontend will start on http://localhost:5173 with proxy configuration to route API calls to the backend.

### Building

```bash
npm run build
```

### Type Checking

```bash
npm run typecheck
```

## Architecture

### Directory Structure

```
src/
├── api/           # API client functions
├── components/    # React components
│   ├── Layout/    # App layout and sidebar tabs
│   ├── RecordingCard/  # Recording display components
│   ├── AIWorkspace/    # AI analysis modal
│   └── Tags/      # Tag management components
├── stores/        # Zustand state stores
├── types/         # TypeScript type definitions
└── utils/         # Utility functions
```

### State Management

- **Recording Store**: Manages recordings list, loading states, and CRUD operations
- **Tag Store**: Handles tag management and filtering
- **UI Store**: Controls UI state (sidebar tabs, filters, modals, view modes)

### API Integration

All existing API endpoints are supported:
- `/api/recordings/*` - Recording management
- `/api/tags/*` - Tag CRUD operations
- `/az_transcription/*` - Transcription services

## Key Features Preserved

✅ **Recording Updates**: Maintains the existing `recordingUpdated` CustomEvent system  
✅ **Optimistic Updates**: Tag changes update UI immediately with proper error handling  
✅ **Status Polling**: Real-time transcription status updates  
✅ **Error Handling**: Comprehensive error handling with user notifications  
✅ **Responsive Design**: Works on desktop, tablet, and mobile  

## Visual Design

The new frontend follows Mantine's design principles instead of exactly matching the original mockup colors. This provides:

- Better accessibility and contrast
- Consistent component styling
- Built-in dark mode support (ready to implement)
- Professional, modern appearance

## Future Enhancements

- Connect AI Workspace to real backend endpoints
- Add authentication integration
- Implement dark mode toggle
- Add keyboard shortcuts
- Performance optimizations with React.memo and useMemo

## Deployment

The build output can be deployed anywhere or copied to the backend's static directory:

```bash
npm run build
cp -r dist/* ../backend/frontend-dist/
```
