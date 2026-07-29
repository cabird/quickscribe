# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0",
#     "typer>=0.9.0",
# ]
# ///
"""
Migration script to remove deprecated fields from speaker_mapping in transcriptions.

Removes: name, displayName, reasoning
Keeps: participantId, confidence, manuallyVerified

Usage:
    # Preview changes (dry run)
    uv run tools/migrate_speaker_mapping.py --dry-run

    # Execute migration
    uv run tools/migrate_speaker_mapping.py

    # With explicit .env file
    uv run tools/migrate_speaker_mapping.py -e backend/src/.env --dry-run
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from azure.cosmos import CosmosClient
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

# Fields to keep in speaker_mapping
KEEP_FIELDS = {"participantId", "confidence", "manuallyVerified"}

# Fields to remove (deprecated)
REMOVE_FIELDS = {"name", "displayName", "reasoning"}


def load_env(env_file: Optional[Path] = None):
    """Load environment variables from .env file."""
    from dotenv import load_dotenv

    if env_file and env_file.exists():
        load_dotenv(env_file)
        console.print(f"[dim]Loaded env from {env_file}[/dim]")
    else:
        # Try common locations
        for path in [Path(".env"), Path("backend/src/.env"), Path("../backend/src/.env")]:
            if path.exists():
                load_dotenv(path)
                console.print(f"[dim]Loaded env from {path}[/dim]")
                break


def get_cosmos_client():
    """Create CosmosDB client from environment variables."""
    endpoint = os.environ.get("AZURE_COSMOS_ENDPOINT")
    key = os.environ.get("AZURE_COSMOS_KEY")

    if not endpoint or not key:
        console.print("[red]Error: AZURE_COSMOS_ENDPOINT and AZURE_COSMOS_KEY must be set[/red]")
        raise typer.Exit(1)

    return CosmosClient(endpoint, credential=key)


def clean_speaker_mapping(speaker_mapping: dict) -> tuple[dict, bool]:
    """
    Clean speaker_mapping by removing deprecated fields.

    Returns:
        Tuple of (cleaned_mapping, was_modified)
    """
    if not speaker_mapping:
        return speaker_mapping, False

    cleaned = {}
    was_modified = False

    for speaker_label, mapping in speaker_mapping.items():
        if not isinstance(mapping, dict):
            cleaned[speaker_label] = mapping
            continue

        # Keep only the normalized fields
        cleaned_mapping = {}
        for key, value in mapping.items():
            if key in KEEP_FIELDS:
                cleaned_mapping[key] = value
            elif key in REMOVE_FIELDS:
                was_modified = True  # We're removing a field

        cleaned[speaker_label] = cleaned_mapping

    return cleaned, was_modified


@app.command()
def migrate(
    env_file: Optional[Path] = typer.Option(None, "-e", "--env-file", help="Path to .env file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without executing"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of records to process"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed changes"),
):
    """Remove deprecated fields from speaker_mapping in all transcriptions."""

    load_env(env_file)
    client = get_cosmos_client()

    database_name = os.environ.get("AZURE_COSMOS_DATABASE_NAME", "QuickScribeDatabase")
    container_name = os.environ.get("AZURE_COSMOS_CONTAINER_NAME", "QuickScribeContainer")

    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    console.print(f"\n[bold]Speaker Mapping Migration[/bold]")
    console.print(f"Database: {database_name}, Container: {container_name}")
    console.print(f"Mode: {'[yellow]DRY RUN[/yellow]' if dry_run else '[red]LIVE[/red]'}\n")

    # Query transcriptions with speaker_mapping
    query = """
        SELECT c.id, c.partitionKey, c.speaker_mapping, c.recording_id
        FROM c
        WHERE c.type = 'transcription'
        AND IS_DEFINED(c.speaker_mapping)
        AND c.speaker_mapping != null
    """

    transcriptions = list(container.query_items(query=query, enable_cross_partition_query=True))

    console.print(f"Found [bold]{len(transcriptions)}[/bold] transcriptions with speaker_mapping\n")

    if limit:
        transcriptions = transcriptions[:limit]
        console.print(f"[dim]Processing first {limit} records[/dim]\n")

    # Track statistics
    stats = {
        "processed": 0,
        "modified": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Create results table
    table = Table(title="Migration Results")
    table.add_column("Transcription ID", style="cyan", max_width=40)
    table.add_column("Speakers", justify="right")
    table.add_column("Fields Removed", style="yellow")
    table.add_column("Status", style="green")

    for t in transcriptions:
        transcription_id = t["id"]
        partition_key = t.get("partitionKey", "transcription")
        speaker_mapping = t.get("speaker_mapping", {})

        stats["processed"] += 1

        # Clean the speaker mapping
        cleaned_mapping, was_modified = clean_speaker_mapping(speaker_mapping)

        if not was_modified:
            stats["skipped"] += 1
            if verbose:
                table.add_row(transcription_id[:36] + "...", str(len(speaker_mapping)), "-", "No changes needed")
            continue

        # Calculate what was removed
        removed_fields = set()
        for label, mapping in speaker_mapping.items():
            if isinstance(mapping, dict):
                for key in mapping.keys():
                    if key in REMOVE_FIELDS:
                        removed_fields.add(key)

        if verbose or dry_run:
            table.add_row(
                transcription_id[:36] + "...",
                str(len(speaker_mapping)),
                ", ".join(sorted(removed_fields)),
                "Would update" if dry_run else "Updated"
            )

        if not dry_run:
            try:
                # Fetch full document and update
                full_doc = container.read_item(item=transcription_id, partition_key=partition_key)
                full_doc["speaker_mapping"] = cleaned_mapping
                container.replace_item(item=transcription_id, body=full_doc)
                stats["modified"] += 1
            except Exception as e:
                stats["errors"] += 1
                console.print(f"[red]Error updating {transcription_id}: {e}[/red]")
        else:
            stats["modified"] += 1

    # Show table if there were changes
    if stats["modified"] > 0 or verbose:
        console.print(table)

    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Processed: {stats['processed']}")
    console.print(f"  {'Would modify' if dry_run else 'Modified'}: [yellow]{stats['modified']}[/yellow]")
    console.print(f"  Skipped (already clean): {stats['skipped']}")
    if stats["errors"] > 0:
        console.print(f"  Errors: [red]{stats['errors']}[/red]")

    if dry_run and stats["modified"] > 0:
        console.print(f"\n[yellow]Run without --dry-run to apply changes[/yellow]")


if __name__ == "__main__":
    app()
