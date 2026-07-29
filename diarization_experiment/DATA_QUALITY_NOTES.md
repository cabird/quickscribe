# Data Quality Notes for Speaker Embeddings

## Known Issues Discovered During Sensitivity Analysis

### 1. Maximum Audio Duration: 90 Minutes

Recordings over 90 minutes get split into chunks for transcription, and the timing gets misaligned.

**Action:** Never use audio segments past the first 90 minutes (5400 seconds).

This affects the extraction script - should add a `max_audio_offset_s = 5400` parameter.

### 2. Recordings to Exclude (Bad Diarization)

These recordings have diarization issues and should be excluded from analysis:

| Recording ID | Title | Issue |
|--------------|-------|-------|
| fbc9d31e-6308-4330-b6d4-9768d01670d0 | Team AI Usage and Recruitment Strategy Discussion | Diarization messed up |

### 3. Label Corrections Made

These labels were corrected after the initial extraction (2026-01-11):

| Recording ID | Speaker | Was | Should Be |
|--------------|---------|-----|-----------|
| (Part 2 #1) | Speaker X | Person A | Person B |
| 6f938659-1adf-45db-8487-8320b45eccda | Multiple | Chris/Carmen | Swapped - fixed |
| 17ef022d-476b-4886-b78d-0fc85c3e0a24 | Multiple | Chris/Carmen | Swapped - fixed |

### 4. Suspected Remaining Issues

**Bryan Tower / Chris Bird swap** in recording `188345d5-68a8-4889-8913-33d75d3703ef`:
- "Bryan Tower" (Speaker 2, 1240s) has 0.929 similarity to Chris Bird
- "Chris Bird" (Speaker 3, 205s) has only 0.148 similarity to other Chris Bird recordings
- **Likely swapped** - needs verification

Also check `6467bf72-c865-4e42-88b0-e705b70ed60b` (same date, both Bryan Tower and Chris Bird labeled).

---

## Re-extraction Required

After fixing labels in the database, re-run extraction to update embeddings:

```bash
# Delete old embeddings
rm -rf embeddings/

# Re-extract with fixes
uv run python extract_embeddings.py \
    --user-id "user-bd639cf9-a105-44f5-80e0-478a8ec2e5c2"

# Re-run sensitivity analysis
uv run python sensitivity_analysis.py --embeddings-dir embeddings/
```

## Future Improvements

1. Add `--exclude-recordings` flag to extraction script
2. Add `--max-audio-offset` parameter (default 5400s = 90 min)
3. Add a "confidence" score for each speaker based on similarity to their other appearances
