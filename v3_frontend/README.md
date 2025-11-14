# QuickScribe v3 Frontend

Modern React + TypeScript frontend for QuickScribe audio transcription management system.

## Tech Stack

- **Vite** - Fast build tool and dev server
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Fluent UI v9** - Microsoft's design system
- **Axios** - HTTP client
- **React Toastify** - Toast notifications

## Project Structure

```
v3_frontend/
├── src/
│   ├── components/
│   │   ├── layout/          # NavigationRail, TopActionBar, MainLayout
│   │   ├── transcripts/     # Recording cards, transcript viewer
│   │   ├── logs/            # Placeholder for Phase 2
│   │   └── search/          # Placeholder for Phase 2
│   ├── services/            # API client and service layers
│   ├── hooks/               # Custom React hooks
│   ├── utils/               # Utility functions
│   ├── types/               # TypeScript type definitions (auto-synced)
│   ├── theme/               # Fluent UI theme customization
│   ├── config/              # App configuration
│   └── styles/              # Global CSS
├── scripts/                 # Build scripts (model sync)
└── public/                  # Static assets
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on port 5050

### Installation

```bash
npm install
```

### Development

Start the development server:

```bash
npm run dev
```

The app will be available at http://localhost:3000

### Building for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Available Scripts

- `npm run dev` - Start development server (syncs models first)
- `npm run build` - Build for production (syncs models, type checks, builds)
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run format` - Format code with Prettier
- `npm run sync-models` - Manually sync type definitions from `/shared/Models.ts`

## Key Features

### Phase 1 (Current)

✅ **Recordings List**
- View all recordings with metadata
- Search by title/description
- Filter by date range
- Responsive recording cards with status

✅ **Transcript Viewer**
- Full transcript display with speaker diarization
- Rich metadata display
- Export transcript to .txt file

✅ **Navigation**
- Three-panel Outlook-style layout
- Navigation rail with view switching
- Logs and Search views (placeholders)

✅ **Type Safety**
- Auto-synced type definitions from backend
- Full TypeScript coverage
- Shared models between frontend and backend

## Model Synchronization

Type definitions are automatically synced from `/shared/Models.ts` before every `dev` and `build` command.

The sync creates `src/types/models.ts` with all shared types including:
- `Recording`
- `Transcription`
- `User`
- `Participant`
- `Tag`
- And more...

To manually sync models:
```bash
npm run sync-models
```

## API Integration

The frontend communicates with the backend API at `http://localhost:5050` (configurable via `.env.development`).

### Key Endpoints Used

- `GET /api/recordings` - List all recordings
- `GET /api/recording/<id>` - Get recording details
- `GET /api/transcription/<id>` - Get transcription with segments
- `GET /api/recording/<id>/audio-url` - Get audio URL (Phase 4)

## Environment Variables

### Development (`.env.development`)
```
VITE_API_URL=http://localhost:5050
VITE_AZURE_CLIENT_ID=<placeholder-for-future-auth>
```

### Production (`.env.production`)
```
VITE_API_URL=https://your-production-api.azurewebsites.net
VITE_AZURE_CLIENT_ID=<azure-client-id>
```

## Upcoming Features

### Phase 2
- Tag management and filtering
- Advanced search with full-text
- Service logs view
- RAG semantic search

### Phase 3
- Speaker identification UI
- Participant management
- Speaker assignment workflow

### Phase 4
- Audio playback with sync
- Click-to-seek timestamps
- Playback controls

## Development Notes

- Hot module reloading enabled
- TypeScript strict mode enabled
- Component library: Fluent UI v9 (makeStyles API)
- State management: React hooks (no external state library in Phase 1)
- Authentication: Deferred to Phase 2+

## Troubleshooting

### Models not syncing
```bash
npm run sync-models
```

### Backend connection errors
Ensure backend is running on port 5050:
```bash
cd ../backend
source venv/bin/activate
python app.py
```

### TypeScript errors
Check that models are synced and dependencies are installed:
```bash
npm run sync-models
npm install
```

## Contributing

When adding new features:
1. Update type definitions in `/shared/Models.ts` (not in frontend)
2. Run `npm run sync-models` to update frontend types
3. Follow existing component patterns (Fluent UI makeStyles)
4. Add proper TypeScript types for all functions/components
5. Test with backend integration

## License

Part of the QuickScribe project.
