# Speaker Identification Experiment

> **Status: archived (July 2026).** This experiment produced the similarity
> thresholds used in production — `speaker_id_auto_threshold = 0.78` and
> `speaker_id_suggest_threshold = 0.68` in `v2/backend/src/app/config.py` come
> from `sensitivity_report.md`. It is kept for that provenance.
>
> **It no longer runs as-is.** It reads QuickScribe v1's CosmosDB via
> `shared_quickscribe_py`; both were decommissioned and deleted in July 2026
> (v2 uses SQLite). The 12 GB `audio_cache/` was also deleted. Re-running it
> would require porting `data_loader.py` to the v2 SQLite schema and re-pulling
> audio from Blob Storage.
>
> The committed `embeddings/` and `speaker_profiles.json` are the surviving
> computed outputs and cannot be regenerated from what remains in this repo.

This experiment uses ECAPA-TDNN speaker embeddings to automatically identify speakers across meetings based on previously labeled recordings.

## Overview

The system works in two phases:

1. **Profile Building**: Extract voice embeddings from meetings where speakers have been labeled (mapped to participant profiles). These embeddings are aggregated to create a "voice fingerprint" for each known speaker.

2. **Speaker Identification**: For new/unlabeled meetings, extract embeddings for each diarized speaker and match against known profiles using cosine similarity.

## How It Works

### ECAPA-TDNN Embeddings

ECAPA-TDNN (Enhanced Channel Attention, Propagation and Aggregation Time-Delay Neural Network) is a state-of-the-art speaker recognition model that produces 192-dimensional embeddings from audio segments.

Key properties:
- Robust to background noise and channel variations
- Works well with 2-8 second audio segments
- Trained on VoxCeleb dataset (millions of utterances from thousands of speakers)

### Matching Strategy

For each speaker in an unlabeled meeting:
1. Extract embeddings from their speech segments (merged for better quality)
2. Compute a centroid (average) embedding for that speaker in this meeting
3. Compare against all known speaker profiles using cosine similarity
4. Classify based on thresholds:
   - **Auto** (>= 0.78): High confidence, auto-assign
   - **Suggest** (>= 0.68): Medium confidence, suggest to user
   - **Unknown** (< 0.68): No confident match

## Installation

```bash
cd diarization_experiment

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install shared library
pip install -e ../shared_quickscribe_py
```

## Environment Setup

The experiment connects to QuickScribe's CosmosDB and Azure Blob Storage. Ensure these environment variables are set:

```bash
# CosmosDB
export AZURE_COSMOS_ENDPOINT="https://your-account.documents.azure.com:443/"
export AZURE_COSMOS_KEY="your-key"
export COSMOS_DATABASE_NAME="quickscribe"

# Blob Storage (for audio files)
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
```

Or create a `.env` file with these values.

## Usage

### Quick Start

```bash
# Run full experiment (build profiles + identify)
python run_experiment.py --user-id YOUR_USER_ID
```

### Step-by-Step

#### 1. Check Your Data

First, see what labeled data you have:

```bash
python data_loader.py --user-id YOUR_USER_ID --stats
```

This shows:
- Which participants have labeled speech
- How many meetings each appears in
- Total speaking duration per participant

#### 2. Build Speaker Profiles

Build voice profiles from labeled meetings:

```bash
python profile_builder.py --user-id YOUR_USER_ID --output speaker_profiles.json
```

Options:
- `--max-meetings N`: Limit meetings processed (for testing)
- `--require-verified`: Only use manually verified speaker mappings
- `--audio-cache DIR`: Directory to cache downloaded audio

#### 3. Identify Speakers

Use profiles to identify speakers in unlabeled meetings:

```bash
python speaker_identifier.py --user-id YOUR_USER_ID --profiles speaker_profiles.json
```

Options:
- `--max-meetings N`: Limit meetings processed
- `--high-threshold 0.78`: Threshold for auto-identification
- `--low-threshold 0.68`: Threshold for suggestions

### Cross-Validation

To get a realistic estimate of accuracy:

```bash
python run_experiment.py --user-id YOUR_USER_ID --cross-validate --folds 5
```

This splits labeled meetings into folds, trains on N-1 folds, tests on the held-out fold, and reports overall accuracy.

## Output

### Speaker Profiles (speaker_profiles.json)

```json
{
  "profiles": {
    "participant-uuid-1": {
      "participant_id": "participant-uuid-1",
      "display_name": "John Smith",
      "centroid": [0.123, -0.456, ...],  // 192-dim vector
      "n_samples": 47,
      "recording_ids": ["recording-1", "recording-2"],
      "embedding_std": 0.082
    }
  }
}
```

### Experiment Results (experiment_results.json)

```json
{
  "build_stats": {
    "meetings_processed": 10,
    "participants_found": 5,
    "total_audio_minutes": 45.2
  },
  "identification_stats": {
    "meetings_processed": 15,
    "total_speakers": 28,
    "auto_identified": 22,
    "suggested": 3,
    "unknown": 3,
    "identification_rate": 78.6
  },
  "meeting_results": [...]
}
```

## Module Reference

### speaker_embedder.py

Core embedding functionality:
- `EcapaEmbedder`: Extracts ECAPA-TDNN embeddings from audio
- `SpeakerProfile`: Represents a speaker's voice profile
- `SpeakerProfileDB`: Database of speaker profiles

### data_loader.py

Database connectivity:
- `DataLoader`: Connects to QuickScribe's CosmosDB
- `LabeledMeeting`: Meeting with labeled speakers
- `UnlabeledMeeting`: Meeting needing identification

### profile_builder.py

Profile construction:
- `ProfileBuilder`: Builds profiles from labeled meetings

### speaker_identifier.py

Speaker matching:
- `SpeakerIdentifier`: Identifies speakers using profiles

### run_experiment.py

Complete experiment runner with cross-validation support.

## Tuning

### Thresholds

The default thresholds (0.78/0.68) are a starting point. To tune:

1. Run cross-validation with different thresholds
2. Balance false positives (wrong identification) vs false negatives (unknown)
3. For higher precision: increase thresholds
4. For higher recall: decrease thresholds

### Segment Duration

- **Minimum (2.0s)**: Shorter segments produce noisy embeddings
- **Maximum (8.0s)**: Longer segments are windowed to center

Adjust if your meetings have very short or very long turns.

### Merging

Adjacent segments from the same speaker are merged (gap <= 0.35s) to create longer, more reliable embedding windows.

## Limitations

1. **New Speakers**: Cannot identify speakers not in any labeled meeting
2. **Short Audio**: Speakers with little audio have less reliable profiles
3. **Similar Voices**: Same gender, similar accent can be confused
4. **Cross-Device**: Different microphones may affect accuracy

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    QuickScribe Database                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐      │
│  │  Recordings │  │ Transcripts  │  │ Participants  │      │
│  │  (audio)    │  │ (diarization)│  │ (labels)      │      │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘      │
└─────────┼────────────────┼──────────────────┼───────────────┘
          │                │                  │
          ▼                ▼                  ▼
    ┌─────────────────────────────────────────────────────┐
    │                   DataLoader                         │
    │  - Fetches labeled/unlabeled meetings               │
    │  - Parses Azure transcript JSON for timing          │
    │  - Downloads audio files                            │
    └──────────────────────┬──────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
    ┌──────────────┐                 ┌──────────────┐
    │ProfileBuilder│                 │  Identifier  │
    │              │                 │              │
    │ For each     │                 │ For each     │
    │ labeled      │                 │ unlabeled    │
    │ meeting:     │                 │ meeting:     │
    │              │                 │              │
    │ 1. Download  │                 │ 1. Download  │
    │ 2. Extract   │                 │ 2. Extract   │
    │    ECAPA     │                 │    ECAPA     │
    │ 3. Update    │                 │ 3. Match vs  │
    │    profile   │                 │    profiles  │
    └──────┬───────┘                 └──────┬───────┘
           │                                │
           ▼                                ▼
    ┌──────────────┐                 ┌──────────────┐
    │SpeakerProfile│                 │   Results    │
    │     DB       │ ───────────────▶│  (matches)   │
    └──────────────┘                 └──────────────┘
```

## Future Improvements

1. **Incremental Learning**: Update profiles as users confirm identifications
2. **Active Learning**: Prioritize uncertain matches for user review
3. **Vector Search**: Use FAISS for faster matching with many speakers
4. **On-Device**: Run embeddings locally for privacy
5. **Confidence Calibration**: Per-speaker thresholds based on profile quality
