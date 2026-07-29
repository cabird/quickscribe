# Speaker Identification Validation UI

A fast, keyboard-driven web interface for validating speaker identification suggestions from the diarization experiment system.

## Overview

This tool helps you quickly validate speaker identification suggestions by:
- Grouping validations by suggested participant (focus on one voice at a time)
- Playing audio snippets with a single keystroke
- Providing reference audio from known recordings
- Auto-saving decisions to JSON files for batch processing
- Tracking progress and reminding you to take breaks

## Features

### The "Voice-Focused Gauntlet" Workflow
- **Grouped by Participant**: Validate all suggestions for "John Doe" before moving to "Jane Smith"
- **Reference Audio**: Hear confirmed samples of the participant before validating
- **Keyboard-Driven**: Complete validations without touching the mouse
- **Undo Support**: Made a mistake? Press Ctrl+Z to undo
- **Session Management**: Auto-save after 30 items, with break reminders
- **Progress Tracking**: See your progress both per-participant and overall

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Space** | Play/Pause audio |
| **Y** or **→** | Yes (confirm this is the correct person) |
| **N** or **←** | No (this is not the correct person) |
| **S** or **↓** | Skip (uncertain, review later) |
| **R** | Play reference audio |
| **Ctrl+Z** | Undo last decision |

## Setup

### Prerequisites

1. Python 3.11+ with `uv` installed
2. Diarization experiment dependencies (parent directory)
3. Environment variables configured:
   ```bash
   export QUICKSCRIBE_USER_ID='your_user_id'
   export SPEAKER_PROFILES_PATH='../speaker_profiles.json'  # optional
   ```

### Installation

**Option 1: Use parent directory's environment (recommended)**
```bash
cd /home/cbird/repos/quickscribe/diarization_experiment
uv sync  # Install parent dependencies if not already done
```

**Option 2: Standalone installation**
```bash
cd validation_ui
uv sync  # Creates its own environment with all dependencies
```

### File Structure

```
validation_ui/
├── app.py                          # Flask server
├── apply_validations.py            # Batch-apply script
├── index.html                      # Main page
├── primereact-standalone-bundle.umd.js
├── components/
│   ├── Icon.jsx
│   ├── AudioPlayer.jsx
│   ├── ReferenceAudioPlayer.jsx
│   ├── ProgressHeader.jsx
│   ├── ValidationCard.jsx
│   └── App.jsx
└── validations/                    # Output directory for JSON files
```

## Usage

### Step 1: Start the Server

**Option 1: Using parent environment (recommended)**
```bash
cd /home/cbird/repos/quickscribe/diarization_experiment

# Set environment variables
export QUICKSCRIBE_USER_ID='your_user_id'

# Start the Flask server
uv run validation_ui/app.py
```

**Option 2: From validation_ui directory**
```bash
cd validation_ui

# Set environment variables
export QUICKSCRIBE_USER_ID='your_user_id'

# Start the Flask server
uv run app.py
```

The server will start at http://localhost:5001

### Step 2: Validate Speakers

1. Open http://localhost:5001 in your browser
2. The queue will load automatically, grouped by suggested participant
3. For each suggestion:
   - Listen to the audio snippet (press **Space**)
   - Listen to reference audio if needed (press **R**)
   - Decide:
     - Press **Y** if this is the correct person
     - Press **N** if this is not the correct person
     - Press **S** if you're uncertain
4. The UI will automatically advance to the next item
5. After 30 validations, you'll get a break reminder
6. When you're done, your decisions are automatically saved to `validations/validation-{user}-{timestamp}.json`

### Step 3: Apply Validations to Database

After completing a validation session, apply the decisions:

**From parent directory:**
```bash
cd /home/cbird/repos/quickscribe/diarization_experiment

# Preview changes (dry run)
uv run validation_ui/apply_validations.py --latest --dry-run

# Apply the latest session
uv run validation_ui/apply_validations.py --latest

# Apply a specific session
uv run validation_ui/apply_validations.py --session validation-user-20240112-154530.json

# Apply all sessions
uv run validation_ui/apply_validations.py --all
```

**From validation_ui directory:**
```bash
cd validation_ui

# Preview changes (dry run)
uv run apply_validations.py --latest --dry-run

# Apply the latest session
uv run apply_validations.py --latest
```

## API Endpoints

The Flask server provides these endpoints:

- `GET /api/validation-queue` - Get the validation queue
- `POST /api/save-session` - Save validation decisions
- `GET /api/reference-audio/<participant_id>` - Get reference audio samples
- `GET /audio/<filename>` - Serve cached audio files

## Validation Session Format

Sessions are saved as JSON files in `validations/`:

```json
{
  "validator_id": "user_123",
  "validated_at": "2024-01-12T15:45:30Z",
  "session_metadata": {
    "started_at": "2024-01-12T15:30:00Z",
    "completed_at": "2024-01-12T15:45:30Z",
    "items_validated": 30
  },
  "decisions": [
    {
      "item_id": "recording_abc::Speaker 1",
      "decision": "confirmed",
      "participant_id": "participant_xyz",
      "similarity": 0.82,
      "timestamp": "2024-01-12T15:31:15Z"
    }
  ]
}
```

## Workflow Design

### Why Group by Participant?

The most significant UX decision is grouping by participant. This:
- **Reduces cognitive load**: You become an expert on one voice
- **Improves accuracy**: Familiarity with the target voice leads to better decisions
- **Increases speed**: Less context-switching means faster validation

### Reference Audio Strategy

Reference samples are:
- From **different recordings** than the one being validated (prevents circular validation)
- The **highest confidence** matches from the profile
- **2-3 samples** to show voice consistency across contexts

### Session Management

To prevent fatigue and maintain quality:
- Break reminders every 30 validations
- Save progress automatically
- Show progress bars for motivation
- Support undo for quick error correction

## Troubleshooting

### "No items to validate"

This means there are no "suggest" level suggestions. Check:
- Are there speaker identification results?
- Are all items already at "auto" or "unknown" confidence?
- Try running `run_experiment.py` to generate new suggestions

### Audio not playing

Check:
- Audio files are cached in `../audio_cache/`
- Flask server is running and serving `/audio/` route
- Browser console for errors

### Server won't start

Check:
- `QUICKSCRIBE_USER_ID` environment variable is set
- Python environment is activated
- Required packages are installed: `flask`, `flask-cors`

## Technical Details

### In-Browser React Architecture

This UI uses:
- **React 18** (via UMD bundle, no build step)
- **PrimeReact** (via standalone bundle)
- **Lucide Icons**
- **Babel Standalone** (for JSX transpilation)

All components use the namespace pattern: `window.ValidationApp = {}`

### Audio Handling

Audio is served as:
1. Full audio file downloaded to cache
2. Frontend plays specific time ranges (start/end seconds)
3. In production, would use Azure Blob SAS URLs with time ranges

## Future Enhancements

### Phase 2: Identify Unknown Clusters
- List unknown speaker clusters (e.g., "appears in 8 recordings, 25 min total")
- Play samples from different recordings
- Assign a name to the entire cluster

### Phase 3: QA Workflows
- Spot-check high-confidence "auto" assignments
- Review and fix outliers (potentially mislabeled data)
- More detailed "forensic" view with spectrograms

## Credits

UX design collaboration with Gemini 2.5 Pro, focusing on:
- Minimizing cognitive load
- Keyboard-driven efficiency
- The "Voice-Focused Gauntlet" workflow pattern

## License

Part of the QuickScribe diarization experiment system.
