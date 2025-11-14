# QuickScribe Frontend Implementation Plan

## Project Overview

Building a React + TypeScript frontend for QuickScribe audio transcription management system using Fluent UI v9, following Outlook-style three-panel layout.

**Location**: `/v3_frontend/`
**Tech Stack**: Vite + React + TypeScript + Fluent UI v9
**Data Models**: `/shared/Models.ts`
**API Spec**: `/docs/API_SPECIFICATION.md`

---

## Phase 1: Foundation & Transcripts View

### 1.1 Project Setup

#### Initialize Vite Project
```bash
cd v3_frontend
npm create vite@latest . -- --template react-ts
npm install
```

#### Install Dependencies
```bash
# Fluent UI
npm install @fluentui/react-components @fluentui/react-icons

# Toast notifications
npm install react-toastify
npm install -D @types/react-toastify

# API & Routing
npm install axios react-router-dom
npm install -D @types/react-router-dom

# Development Tools
npm install -D eslint prettier eslint-plugin-prettier eslint-config-prettier
```

#### Project Structure
```
v3_frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── NavigationRail.tsx
│   │   │   ├── TopActionBar.tsx
│   │   │   └── MainLayout.tsx
│   │   ├── transcripts/
│   │   │   ├── RecordingsList.tsx
│   │   │   ├── RecordingCard.tsx
│   │   │   ├── TranscriptViewer.tsx
│   │   │   └── TranscriptEntry.tsx
│   │   ├── logs/
│   │   │   └── LogsPlaceholder.tsx
│   │   └── search/
│   │       └── SearchPlaceholder.tsx
│   ├── services/
│   │   ├── api.ts
│   │   ├── recordingsService.ts
│   │   └── transcriptionsService.ts
│   ├── types/
│   │   ├── index.ts              # Copy from shared/Models.ts
│   │   └── api.ts                # API response types
│   ├── hooks/
│   │   ├── useRecordings.ts
│   │   ├── useTranscription.ts
│   │   └── useSearch.ts
│   ├── theme/
│   │   ├── customTheme.ts
│   │   └── colors.ts
│   ├── styles/
│   │   └── globals.css
│   ├── config/
│   │   ├── styles.ts
│   │   └── constants.ts
│   ├── utils/
│   │   ├── dateUtils.ts
│   │   ├── formatters.ts
│   │   ├── exportTranscript.ts
│   │   └── toast.ts
│   ├── App.tsx
│   └── main.tsx
├── .env.development
├── .env.production
├── vite.config.ts
└── tsconfig.json
```

### 1.2 Configuration Files

#### `vite.config.ts`
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
    },
  },
});
```

#### `.env.development`
```bash
VITE_API_URL=http://localhost:5050
VITE_AZURE_CLIENT_ID=<placeholder-for-future-auth>
```

#### `.env.production`
```bash
VITE_API_URL=https://your-production-api.azurewebsites.net
VITE_AZURE_CLIENT_ID=<azure-client-id>
```

### 1.3 Theme Setup

#### `src/theme/customTheme.ts`
```typescript
import { createLightTheme, BrandVariants } from '@fluentui/react-components';

const quickScribeBrand: BrandVariants = {
  10: "#020305",
  20: "#111723",
  30: "#16263D",
  40: "#193253",
  50: "#1B3F6A",
  60: "#1B4C82",
  70: "#18599B",
  80: "#1267B4",
  90: "#3174C2",
  100: "#4F82C8",
  110: "#6790CF",
  120: "#7D9ED5",
  130: "#92ACDC",
  140: "#A6BAE2",
  150: "#BAC9E9",
  160: "#CDD8EF"
};

export const lightTheme = createLightTheme(quickScribeBrand);
```

#### `src/styles/globals.css`
```css
:root {
  /* Semantic colors */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-danger: #EF4444;
  --color-info: #3B82F6;

  /* Spacing system */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;

  /* App-specific */
  --nav-rail-width: 68px;
  --list-panel-width: 35%;
  --transcript-speaker-color: #2563EB;
  --transcript-time-color: #6B7280;
  --selection-border-color: #4CAF50;
}
```

#### `src/config/styles.ts`
```typescript
import { tokens } from '@fluentui/react-components';

export const APP_COLORS = {
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  info: '#3B82F6',
  transcriptSpeaker: '#2563EB',
  selectionBorder: '#4CAF50',
  navRailBg: '#2c3e50',
} as const;

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const LAYOUT = {
  navRailWidth: 68,
  listPanelWidthPercent: 35,
} as const;
```

### 1.4 Type Definitions

#### `src/types/index.ts`
**Action**: Re-export from auto-generated models and add API-specific types

```typescript
// Re-export all models from auto-generated file
export * from './models';

// Note: models.ts is auto-generated from /shared/Models.ts via sync-models script
// Key types available:
// - Recording
// - Transcription
// - User
// - Participant
// - Tag
// - AnalysisType
// - AnalysisResult
// - TranscriptionSegment
```

#### `src/types/api.ts`
```typescript
// API response wrappers
export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: string;
  message?: string;
}

// Pagination (for future)
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

// Search/Filter params
export interface RecordingFilters {
  searchQuery?: string;
  searchType?: 'basic' | 'fulltext';
  dateRange?: 'all' | 'week' | 'month' | 'quarter';
  tagIds?: string[];
}
```

### 1.5 API Service Layer

#### `src/services/api.ts`
```typescript
import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5050';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth (placeholder)
    this.client.interceptors.request.use(
      (config) => {
        // TODO: Add Azure AD token when auth is implemented
        // const token = getAuthToken();
        // if (token) {
        //   config.headers.Authorization = `Bearer ${token}`;
        // }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error);
        // Don't show toast here - let individual services handle error display
        return Promise.reject(error);
      }
    );
  }

  getInstance() {
    return this.client;
  }
}

export const apiClient = new ApiClient().getInstance();
```

#### `src/services/recordingsService.ts`
```typescript
import { apiClient } from './api';
import type { Recording } from '../types';

export const recordingsService = {
  // GET /api/recordings
  getAllRecordings: async (): Promise<Recording[]> => {
    const response = await apiClient.get<Recording[]>('/api/recordings');
    return response.data;
  },

  // GET /api/recording/<recording_id>
  getRecordingById: async (recordingId: string): Promise<Recording> => {
    const response = await apiClient.get<Recording>(`/api/recording/${recordingId}`);
    return response.data;
  },

  // GET /api/recording/<recording_id>/audio-url
  getRecordingAudioUrl: async (recordingId: string): Promise<{ audio_url: string; expires_in: number }> => {
    const response = await apiClient.get(`/api/recording/${recordingId}/audio-url`);
    return response.data;
  },

  // PUT /api/recording/<recording_id>
  updateRecording: async (recordingId: string, updates: Partial<Recording>): Promise<Recording> => {
    const response = await apiClient.put(`/api/recording/${recordingId}`, updates);
    return response.data;
  },

  // DELETE /api/delete_recording/<recording_id>
  deleteRecording: async (recordingId: string): Promise<void> => {
    await apiClient.get(`/api/delete_recording/${recordingId}`);
  },
};
```

#### `src/services/transcriptionsService.ts`
```typescript
import { apiClient } from './api';
import type { Transcription } from '../types';

export const transcriptionsService = {
  // GET /api/transcription/<transcription_id>
  getTranscriptionById: async (transcriptionId: string): Promise<Transcription> => {
    const response = await apiClient.get<Transcription>(`/api/transcription/${transcriptionId}`);
    return response.data;
  },

  // POST /api/transcription/<transcription_id>/speaker
  updateSpeaker: async (
    transcriptionId: string,
    speakerLabel: string,
    participantId: string,
    manuallyVerified: boolean = true
  ): Promise<void> => {
    await apiClient.post(`/api/transcription/${transcriptionId}/speaker`, {
      speaker_label: speakerLabel,
      participant_id: participantId,
      manually_verified: manuallyVerified,
    });
  },
};
```

### 1.6 Custom Hooks

#### `src/hooks/useRecordings.ts`
```typescript
import { useState, useEffect } from 'react';
import { recordingsService } from '../services/recordingsService';
import type { Recording } from '../types';

interface UseRecordingsResult {
  recordings: Recording[];
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useRecordings(): UseRecordingsResult {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchRecordings = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await recordingsService.getAllRecordings();
      setRecordings(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecordings();
  }, []);

  return {
    recordings,
    loading,
    error,
    refetch: fetchRecordings,
  };
}
```

#### `src/hooks/useTranscription.ts`
```typescript
import { useState, useEffect } from 'react';
import { transcriptionsService } from '../services/transcriptionsService';
import type { Transcription } from '../types';

interface UseTranscriptionResult {
  transcription: Transcription | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useTranscription(transcriptionId: string | null): UseTranscriptionResult {
  const [transcription, setTranscription] = useState<Transcription | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchTranscription = async () => {
    if (!transcriptionId) {
      setTranscription(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await transcriptionsService.getTranscriptionById(transcriptionId);
      setTranscription(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTranscription();
  }, [transcriptionId]);

  return {
    transcription,
    loading,
    error,
    refetch: fetchTranscription,
  };
}
```

### 1.7 Utility Functions

#### `src/utils/dateUtils.ts`
```typescript
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function formatDuration(seconds?: number): string {
  if (!seconds) return 'Unknown';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes} min`;
}
```

#### `src/utils/formatters.ts`
```typescript
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

export function formatSpeakersList(speakers?: string[] | any[]): string {
  if (!speakers || speakers.length === 0) return 'No speakers';

  // Handle both string[] and Participant[] formats
  const speakerNames = speakers.map(s =>
    typeof s === 'string' ? s : s.displayName || s.name || 'Unknown'
  );

  if (speakerNames.length <= 3) {
    return speakerNames.join(', ');
  }

  return `${speakerNames.slice(0, 2).join(', ')}, +${speakerNames.length - 2} more`;
}
```

#### `src/utils/exportTranscript.ts`
```typescript
import type { Recording, Transcription } from '../types';

export function exportTranscriptToFile(
  recording: Recording,
  transcription: Transcription
): void {
  if (!transcription.diarized_transcript) {
    throw new Error('No transcript available to export');
  }

  // Build formatted transcript with metadata header
  let content = '';

  // Add header
  content += `${recording.title || 'Untitled Recording'}\n`;
  content += '='.repeat(60) + '\n\n';

  // Add metadata
  if (recording.recorded_timestamp) {
    const date = new Date(recording.recorded_timestamp);
    content += `Date: ${date.toLocaleDateString()} ${date.toLocaleTimeString()}\n`;
  }
  if (recording.duration) {
    const hours = Math.floor(recording.duration / 3600);
    const minutes = Math.floor((recording.duration % 3600) / 60);
    content += `Duration: ${hours > 0 ? `${hours}h ` : ''}${minutes}m\n`;
  }
  if (recording.participants && recording.participants.length > 0) {
    const speakerNames = recording.participants.map((p: any) =>
      typeof p === 'string' ? p : p.displayName || p.name
    );
    content += `Participants: ${speakerNames.join(', ')}\n`;
  }
  if (recording.description) {
    content += `\nDescription: ${recording.description}\n`;
  }

  content += '\n' + '='.repeat(60) + '\n\n';

  // Add transcript with speaker names
  content += 'TRANSCRIPT\n\n';
  content += transcription.diarized_transcript;

  // Create blob and download
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;

  // Create filename from title and date
  const filename = `${recording.title || 'transcript'}_${new Date().toISOString().split('T')[0]}.txt`;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
```

#### `src/utils/toast.ts`
```typescript
import { toast } from 'react-toastify';

export const showToast = {
  success: (message: string) => {
    toast.success(message);
  },

  error: (message: string) => {
    toast.error(message);
  },

  info: (message: string) => {
    toast.info(message);
  },

  warning: (message: string) => {
    toast.warning(message);
  },

  // Convenience methods for common scenarios
  apiError: (error: any) => {
    const message = error.response?.data?.error || error.message || 'An error occurred';
    toast.error(message);
  },

  recordingDeleted: () => {
    toast.success('Recording deleted successfully');
  },

  recordingUpdated: () => {
    toast.success('Recording updated successfully');
  },

  exportSuccess: () => {
    toast.success('Transcript exported successfully');
  },
};
```

---

## Component Implementation Details

### 2.1 Layout Components

#### `src/components/layout/NavigationRail.tsx`

**Props**:
```typescript
interface NavigationRailProps {
  activeView: 'transcripts' | 'logs' | 'search';
  onViewChange: (view: 'transcripts' | 'logs' | 'search') => void;
}
```

**Features**:
- Dark themed vertical bar (68px wide)
- Icon buttons for each view
- Active state indicator (green left border)
- Tooltips on hover
- Icons: DocumentText (transcripts), ChartMultiple (logs), Search (search)

**Styling**:
```typescript
const useStyles = makeStyles({
  navRail: {
    width: '68px',
    backgroundColor: APP_COLORS.navRailBg,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: '12px',
    gap: '8px',
    boxShadow: tokens.shadow16,
  },
  navButton: {
    width: '48px',
    height: '48px',
    minWidth: '48px',
    color: 'white',
  },
  navButtonActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    // Add green left border
  },
});
```

#### `src/components/layout/TopActionBar.tsx`

**Props**:
```typescript
interface TopActionBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchType: 'basic' | 'fulltext';
  onSearchTypeChange: (type: 'basic' | 'fulltext') => void;
  dateRange: 'all' | 'week' | 'month' | 'quarter';
  onDateRangeChange: (range: 'all' | 'week' | 'month' | 'quarter') => void;
  onExport: () => void;
  onRefresh: () => void;
}
```

**Features**:
- Search input with icon
- Search type dropdown
- Date range filter dropdown
- Export button
- Refresh button

**Layout**: Horizontal flex with gap, padding, border-bottom

#### `src/components/layout/MainLayout.tsx`

**State Management**:
```typescript
const [activeView, setActiveView] = useState<'transcripts' | 'logs' | 'search'>('transcripts');
```

**Structure**:
```tsx
<div className={styles.container}>
  <NavigationRail activeView={activeView} onViewChange={setActiveView} />
  <div className={styles.mainContent}>
    {activeView === 'transcripts' && <TranscriptsView />}
    {activeView === 'logs' && <LogsPlaceholder />}
    {activeView === 'search' && <SearchPlaceholder />}
  </div>
</div>
```

### 2.2 Transcripts View Components

#### `src/components/transcripts/RecordingCard.tsx`

**Props**:
```typescript
interface RecordingCardProps {
  recording: Recording;
  isSelected: boolean;
  onClick: () => void;
}
```

**Display**:
- Title (bold, 15px)
- Date & time with icons
- Duration
- Description (truncated, 1 line)
- Speakers list (truncated if many)
- Selected state: green left border + background tint

**Styling**: Use makeStyles for hover states, selection indicator

#### `src/components/transcripts/RecordingsList.tsx`

**Props**:
```typescript
interface RecordingsListProps {
  recordings: Recording[];
  selectedRecordingId: string | null;
  onRecordingSelect: (recordingId: string) => void;
  loading: boolean;
}
```

**Features**:
- Scrollable list container (35% width)
- Maps recordings to RecordingCard components
- Loading spinner when fetching
- Empty state message

#### `src/components/transcripts/TranscriptEntry.tsx`

**Props**:
```typescript
interface TranscriptEntryProps {
  segment: TranscriptionSegment;
  speakerMapping?: Record<string, any>;
}
```

**Display**:
- Time (left column, 50px, gray)
- Speaker name (bold, blue)
- Transcript text (readable font, 1.6 line-height)

**Layout**: Flex row with gap

#### `src/components/transcripts/TranscriptViewer.tsx`

**Props**:
```typescript
interface TranscriptViewerProps {
  transcription: Transcription | null;
  recording: Recording | null;
  loading: boolean;
}
```

**Structure**:
```tsx
{transcription ? (
  <>
    <Header>
      <Title>{recording?.title}</Title>
      <Meta>Date • Time • Duration • Speakers</Meta>
    </Header>
    <Divider />
    <TranscriptEntries>
      {/* Map segments to TranscriptEntry */}
    </TranscriptEntries>
  </>
) : (
  <EmptyState>Select a recording to view transcript</EmptyState>
)}
```

**Features**:
- Header with full metadata
- Scrollable transcript area
- Proper speaker name resolution from mapping
- Loading state

#### `src/components/transcripts/TranscriptsView.tsx`

**State**:
```typescript
const [selectedRecordingId, setSelectedRecordingId] = useState<string | null>(null);
const [searchQuery, setSearchQuery] = useState('');
const [searchType, setSearchType] = useState<'basic' | 'fulltext'>('basic');
const [dateRange, setDateRange] = useState<'all' | 'week' | 'month' | 'quarter'>('all');

const { recordings, loading: recordingsLoading, refetch } = useRecordings();
const selectedRecording = recordings.find(r => r.id === selectedRecordingId);
const { transcription, loading: transcriptionLoading } = useTranscription(
  selectedRecording?.transcription_id || null
);
```

**Layout**:
```tsx
<>
  <TopActionBar {...actionBarProps} />
  <div className={styles.viewContainer}>
    <RecordingsList
      recordings={filteredRecordings}
      selectedRecordingId={selectedRecordingId}
      onRecordingSelect={setSelectedRecordingId}
      loading={recordingsLoading}
    />
    <TranscriptViewer
      transcription={transcription}
      recording={selectedRecording}
      loading={transcriptionLoading}
    />
  </div>
</>
```

**Search/Filter Logic**:
```typescript
const filteredRecordings = useMemo(() => {
  let filtered = recordings;

  // Search filter
  if (searchQuery) {
    filtered = filtered.filter(r => {
      if (searchType === 'basic') {
        return (
          r.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.description?.toLowerCase().includes(searchQuery.toLowerCase())
        );
      }
      // Full-text search requires transcription - defer to backend in Phase 2
      return true;
    });
  }

  // Date range filter
  if (dateRange !== 'all') {
    const now = new Date();
    const cutoff = new Date();

    switch (dateRange) {
      case 'week':
        cutoff.setDate(now.getDate() - 7);
        break;
      case 'month':
        cutoff.setMonth(now.getMonth() - 1);
        break;
      case 'quarter':
        cutoff.setMonth(now.getMonth() - 3);
        break;
    }

    filtered = filtered.filter(r =>
      new Date(r.upload_timestamp || '') >= cutoff
    );
  }

  return filtered;
}, [recordings, searchQuery, searchType, dateRange]);
```

### 2.3 Placeholder Components

#### `src/components/logs/LogsPlaceholder.tsx`
```tsx
export function LogsPlaceholder() {
  return (
    <div className={styles.placeholder}>
      <Text size={500}>Service Logs View</Text>
      <Text size={300}>Coming in Phase 2</Text>
    </div>
  );
}
```

#### `src/components/search/SearchPlaceholder.tsx`
```tsx
export function SearchPlaceholder() {
  return (
    <div className={styles.placeholder}>
      <Text size={500}>RAG Search View</Text>
      <Text size={300}>Coming in Phase 2</Text>
    </div>
  );
}
```

---

## App Entry Points

### `src/App.tsx`
```tsx
import { FluentProvider } from '@fluentui/react-components';
import { ToastContainer } from 'react-toastify';
import { lightTheme } from './theme/customTheme';
import { MainLayout } from './components/layout/MainLayout';
import './styles/globals.css';
import 'react-toastify/dist/ReactToastify.css';

function App() {
  return (
    <FluentProvider theme={lightTheme}>
      <MainLayout />
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="light"
      />
    </FluentProvider>
  );
}

export default App;
```

### `src/main.tsx`
```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

---

## Development Workflow

### Scripts in `package.json`
```json
{
  "scripts": {
    "dev": "npm run sync-models && vite",
    "build": "npm run sync-models && tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .ts,.tsx",
    "format": "prettier --write 'src/**/*.{ts,tsx,css}'",
    "sync-models": "node scripts/sync-models.js"
  }
}
```

### Model Sync Build Step

**Create `scripts/sync-models.js`**:
```javascript
const fs = require('fs');
const path = require('path');

const sharedModelsPath = path.join(__dirname, '../../shared/Models.ts');
const frontendTypesPath = path.join(__dirname, '../src/types/models.ts');

console.log('Syncing models from shared/Models.ts...');

if (!fs.existsSync(sharedModelsPath)) {
  console.error('Error: shared/Models.ts not found at', sharedModelsPath);
  process.exit(1);
}

// Read shared models
const sharedModels = fs.readFileSync(sharedModelsPath, 'utf8');

// Add header comment
const output = `// AUTO-GENERATED from /shared/Models.ts
// Do not edit this file directly - changes will be overwritten
// Last synced: ${new Date().toISOString()}

${sharedModels}
`;

// Ensure types directory exists
const typesDir = path.dirname(frontendTypesPath);
if (!fs.existsSync(typesDir)) {
  fs.mkdirSync(typesDir, { recursive: true });
}

// Write to frontend types
fs.writeFileSync(frontendTypesPath, output, 'utf8');

console.log('✓ Models synced successfully to src/types/models.ts');
```

This script:
- Copies `shared/Models.ts` to `src/types/models.ts`
- Adds auto-generated header
- Runs before `dev` and `build` commands
- Ensures models stay in sync

### Running Locally
```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
python app.py

# Terminal 2: Frontend
cd v3_frontend
npm run dev
```

Frontend will be at `http://localhost:3000`, proxying API calls to backend at `http://localhost:5050`.

---

## API Endpoints Used in Phase 1

### Available & Used
- ✅ `GET /api/recordings` - List all recordings
- ✅ `GET /api/recording/<id>` - Get specific recording
- ✅ `GET /api/transcription/<id>` - Get transcription with segments
- ✅ `GET /api/recording/<id>/audio-url` - Get audio URL (for Phase 4)

### Not Yet Implemented (Note for Future)
- ⚠️ Full-text search within transcripts (need backend endpoint)
- ⚠️ RAG semantic search (need backend endpoint)
- ⚠️ Service logs endpoint (need backend endpoint)

### Authentication Endpoints (Phase 2+)
- 🔒 MSAL integration (deferred)
- 🔒 `/api/user/<user_id>` (deferred)

---

## Testing Strategy

### Manual Testing Checklist
- [ ] Recordings list loads and displays
- [ ] Click recording shows transcript
- [ ] Search filters recordings by title
- [ ] Date range filter works
- [ ] Selected recording highlights with green border
- [ ] Loading states display properly
- [ ] Empty states show when no data
- [ ] Refresh button re-fetches data
- [ ] Export downloads transcript (Phase 1: basic implementation)

### Future Automated Testing
- Unit tests with Vitest
- Component tests with React Testing Library
- E2E tests with Playwright (Phase 3+)

---

## Phase 2 Preview: Tags & Filtering

**New Features**:
- Tag chips on recording cards
- Tag filter dropdown in TopActionBar
- Tag management UI (create/edit/delete tags)
- Multi-tag filtering

**API Endpoints**:
- `GET /api/tags/get`
- `POST /api/tags/create`
- `GET /api/recordings/<id>/add_tag/<tag_id>`
- `GET /api/recordings/<id>/remove_tag/<tag_id>`

**New Components**:
- `TagChip.tsx`
- `TagFilter.tsx`
- `TagManager.tsx`

---

## Phase 3 Preview: Speaker Identification & Participants

**New Features**:
- Speaker identification inline in transcript
- Participant management panel
- Assign participants to speakers
- Edit speaker mappings

**API Endpoints**:
- `GET /api/participants`
- `POST /api/participants`
- `POST /api/transcription/<id>/speaker`
- `POST /api/recording/<id>/update_speakers`

**New Components**:
- `SpeakerIdentifier.tsx`
- `ParticipantPanel.tsx`
- `ParticipantSelector.tsx`

---

## Phase 4 Preview: Audio Playback

**New Features**:
- Audio player component
- Sync playback with transcript highlighting
- Click timestamp to seek
- Playback controls

**API Endpoints**:
- `GET /api/recording/<id>/audio-url` (already available)

**New Components**:
- `AudioPlayer.tsx`
- `PlaybackControls.tsx`

**Libraries**:
- Consider `react-h5-audio-player` or custom implementation

---

## Known Limitations & Notes

1. **Authentication**: Skipped in Phase 1, all requests unauthenticated
2. **Full-text Search**: Currently client-side only, need backend implementation
3. **RAG Search**: Backend endpoint doesn't exist yet
4. **Logs View**: Backend endpoint not defined
5. **Export**: Phase 1 will do simple client-side .txt export
6. **Pagination**: Not implemented (assuming reasonable dataset size)
7. **Real-time Updates**: No WebSocket/polling for live updates

---

## Success Criteria for Phase 1

- [ ] Project initializes and runs on `localhost:3000`
- [ ] Navigation rail switches between views
- [ ] Recordings list fetches and displays from backend
- [ ] Clicking recording loads and displays transcript
- [ ] Basic search filters by title/description
- [ ] Date range filter works
- [ ] UI matches Fluent UI design system
- [ ] Responsive layout (desktop-first)
- [ ] Code is TypeScript-strict compliant
- [ ] No console errors or warnings

---

## Next Steps After Plan Approval

1. Initialize Vite project
2. Install dependencies
3. Set up theme and global styles
4. Create type definitions from shared models
5. Build API service layer
6. Implement layout components
7. Implement transcripts view components
8. Add placeholder views
9. Test with local backend
10. Document any API discrepancies

**Estimated Time**: Phase 1 implementation ~2-3 days of focused development

---

## Configuration Summary

Based on your answers:

1. ✅ **Backend Port**: `5050` (configured in .env and vite.config.ts)
2. ✅ **Model Sync**: Build step via `scripts/sync-models.js` (runs before dev/build)
3. ✅ **Export Format**: Formatted transcript with speaker names, metadata header
4. ✅ **Error Handling**: Toast notifications via `react-toastify`

## Pre-Implementation Checklist

Before starting implementation, ensure:

- [ ] Backend is running on port 5050
- [ ] Backend has test data (recordings with transcriptions)
- [ ] `/shared/Models.ts` exists and is up to date
- [ ] You've reviewed and approved this plan

Ready to proceed with implementation! 🚀
