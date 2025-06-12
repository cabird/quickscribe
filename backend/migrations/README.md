# Database Migrations

This directory contains database migration scripts for QuickScribe.

## Migration Naming Convention

Migrations should be named with a sequential number prefix:
- `001_normalize_diarized_transcripts.py`
- `002_add_user_preferences.py`
- etc.

## Running Migrations

Each migration script supports the following arguments:

```bash
# Dry run to preview changes
python migrations/001_migration_name.py --dry-run

# Execute the migration
python migrations/001_migration_name.py --execute

# Get help
python migrations/001_migration_name.py --help
```

## Migration Structure

Each migration should:
1. Include a clear description of what it does
2. Support dry-run mode for testing
3. Log progress and any issues
4. Validate data integrity
5. Include rollback instructions in comments

## Safety Guidelines

- Always test migrations on staging/dev environment first
- Run with `--dry-run` to preview changes
- Backup critical data before running migrations
- Monitor logs during execution
- Have a rollback plan ready

## Current Migrations

- `001_normalize_diarized_transcripts.py`: Converts existing diarized transcripts from speaker names to "Speaker X" format with proper speaker mapping
- `002_create_participant_profiles.py`: Migrates legacy participant data to new participant entity system - creates Participant profiles for all speakers and updates recordings/transcriptions to reference them