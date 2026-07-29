# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "azure-cosmos>=4.5.0",
#     "azure-storage-blob>=12.19.0",
#     "python-dotenv>=1.0.0",
#     "rich>=13.0.0",
#     "typer>=0.9.0",
# ]
# ///
"""
Fix unique_filename paths in recordings to match actual blob locations.

Some recordings have unique_filename = "guid.mp3" but the blob is stored at
"user-xxx/guid.mp3". This script finds and fixes those mismatches.

Usage:
    # Preview changes (dry run)
    uv run tools/fix_blob_paths.py --dry-run

    # Execute fix
    uv run tools/fix_blob_paths.py

    # With explicit .env file
    uv run tools/fix_blob_paths.py -e tools/.env --dry-run
"""

import os
from pathlib import Path
from typing import Optional

import typer
from azure.cosmos import CosmosClient
from azure.storage.blob import ContainerClient
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer()
console = Console()


def load_env(env_file: Optional[Path] = None):
    """Load environment variables from .env file."""
    from dotenv import load_dotenv

    if env_file and env_file.exists():
        load_dotenv(env_file)
        console.print(f"[dim]Loaded env from {env_file}[/dim]")
    else:
        for path in [Path(".env"), Path("tools/.env"), Path("backend/src/.env")]:
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


def get_blob_container_client() -> ContainerClient:
    """Create Blob Storage container client."""
    conn_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_AUDIO_CONTAINER_NAME", "recordings")

    if not conn_string:
        console.print("[red]Error: AZURE_STORAGE_CONNECTION_STRING must be set[/red]")
        raise typer.Exit(1)

    return ContainerClient.from_connection_string(conn_string, container_name)


def blob_exists(blob_client: ContainerClient, path: str) -> bool:
    """Check if a blob exists at the given path."""
    try:
        blob = blob_client.get_blob_client(path)
        blob.get_blob_properties()
        return True
    except Exception:
        return False


@app.command()
def fix(
    env_file: Optional[Path] = typer.Option(None, "-e", "--env-file", help="Path to .env file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without executing"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed output"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of recordings to process"),
):
    """Fix unique_filename paths to match actual blob locations."""

    load_env(env_file)
    cosmos_client = get_cosmos_client()
    blob_client = get_blob_container_client()

    database_name = os.environ.get("AZURE_COSMOS_DATABASE_NAME", "QuickScribeDatabase")
    container_name = os.environ.get("AZURE_COSMOS_CONTAINER_NAME", "QuickScribeContainer")

    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    console.print(f"\n[bold]Fix Blob Paths in Recordings[/bold]")
    console.print(f"Database: {database_name}, Container: {container_name}")
    console.print(f"Mode: {'[yellow]DRY RUN[/yellow]' if dry_run else '[red]LIVE[/red]'}\n")

    # Query all recordings that don't have a "/" in unique_filename
    query = """
        SELECT c.id, c.unique_filename, c.user_id, c.partitionKey
        FROM c
        WHERE c.type = 'recording'
        AND NOT CONTAINS(c.unique_filename, '/')
    """

    recordings = list(container.query_items(query=query, enable_cross_partition_query=True))
    console.print(f"Found [bold]{len(recordings)}[/bold] recordings without path prefix\n")

    if limit:
        recordings = recordings[:limit]
        console.print(f"[dim]Processing first {limit} records[/dim]\n")

    stats = {
        "checked": 0,
        "needs_fix": 0,
        "fixed": 0,
        "already_correct": 0,
        "missing_blob": 0,
        "errors": 0,
    }

    # Results table
    table = Table(title="Path Fixes")
    table.add_column("Recording ID", style="cyan", max_width=40)
    table.add_column("Old Path", style="dim")
    table.add_column("New Path", style="green")
    table.add_column("Status")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking recordings...", total=len(recordings))

        for rec in recordings:
            rec_id = rec["id"]
            unique_filename = rec["unique_filename"]
            user_id = rec["user_id"]
            partition_key = rec.get("partitionKey", "recording")

            stats["checked"] += 1
            progress.update(task, advance=1, description=f"Checking {rec_id[:8]}...")

            # Check if blob exists at current path
            if blob_exists(blob_client, unique_filename):
                stats["already_correct"] += 1
                if verbose:
                    table.add_row(rec_id[:36], unique_filename, "-", "[green]OK[/green]")
                continue

            # Check if blob exists at user-prefixed path
            user_prefixed_path = f"{user_id}/{unique_filename}"
            if blob_exists(blob_client, user_prefixed_path):
                stats["needs_fix"] += 1

                if dry_run:
                    table.add_row(rec_id[:36], unique_filename, user_prefixed_path, "[yellow]Would fix[/yellow]")
                    stats["fixed"] += 1
                else:
                    try:
                        # Fetch full document and update
                        full_doc = container.read_item(item=rec_id, partition_key=partition_key)
                        full_doc["unique_filename"] = user_prefixed_path
                        container.replace_item(item=rec_id, body=full_doc)
                        table.add_row(rec_id[:36], unique_filename, user_prefixed_path, "[green]Fixed[/green]")
                        stats["fixed"] += 1
                    except Exception as e:
                        table.add_row(rec_id[:36], unique_filename, user_prefixed_path, f"[red]Error: {e}[/red]")
                        stats["errors"] += 1
            else:
                # Blob doesn't exist at either location
                stats["missing_blob"] += 1
                if verbose:
                    table.add_row(rec_id[:36], unique_filename, "-", "[red]Missing blob[/red]")

    # Show results
    if stats["needs_fix"] > 0 or verbose:
        console.print(table)

    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Checked: {stats['checked']}")
    console.print(f"  Already correct: [green]{stats['already_correct']}[/green]")
    console.print(f"  {'Would fix' if dry_run else 'Fixed'}: [yellow]{stats['fixed']}[/yellow]")
    console.print(f"  Missing blobs: [red]{stats['missing_blob']}[/red]")
    if stats["errors"] > 0:
        console.print(f"  Errors: [red]{stats['errors']}[/red]")

    if dry_run and stats["needs_fix"] > 0:
        console.print(f"\n[yellow]Run without --dry-run to apply fixes[/yellow]")


@app.command()
def check_missing(
    env_file: Optional[Path] = typer.Option(None, "-e", "--env-file", help="Path to .env file"),
    limit: Optional[int] = typer.Option(50, "--limit", help="Limit number of recordings to check"),
):
    """Check for recordings with missing blobs (neither path works)."""

    load_env(env_file)
    cosmos_client = get_cosmos_client()
    blob_client = get_blob_container_client()

    database_name = os.environ.get("AZURE_COSMOS_DATABASE_NAME", "QuickScribeDatabase")
    container_name = os.environ.get("AZURE_COSMOS_CONTAINER_NAME", "QuickScribeContainer")

    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    console.print(f"\n[bold]Check for Missing Blobs[/bold]\n")

    # Query all recordings
    query = """
        SELECT c.id, c.unique_filename, c.user_id, c.title
        FROM c
        WHERE c.type = 'recording'
    """

    recordings = list(container.query_items(query=query, enable_cross_partition_query=True))

    if limit:
        recordings = recordings[:limit]

    missing = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking blobs...", total=len(recordings))

        for rec in recordings:
            rec_id = rec["id"]
            unique_filename = rec["unique_filename"]
            user_id = rec["user_id"]
            title = rec.get("title", "Unknown")

            progress.update(task, advance=1)

            # Check both paths
            path1 = unique_filename
            path2 = f"{user_id}/{unique_filename}" if "/" not in unique_filename else None

            exists_at_path1 = blob_exists(blob_client, path1)
            exists_at_path2 = path2 and blob_exists(blob_client, path2)

            if not exists_at_path1 and not exists_at_path2:
                missing.append({
                    "id": rec_id,
                    "title": title,
                    "unique_filename": unique_filename,
                    "user_id": user_id,
                })

    if missing:
        table = Table(title=f"Missing Blobs ({len(missing)} found)")
        table.add_column("Recording ID", style="cyan")
        table.add_column("Title", max_width=40)
        table.add_column("Filename")

        for rec in missing[:20]:  # Show first 20
            table.add_row(rec["id"][:36], rec["title"][:40], rec["unique_filename"])

        console.print(table)
        if len(missing) > 20:
            console.print(f"[dim]... and {len(missing) - 20} more[/dim]")
    else:
        console.print("[green]No missing blobs found![/green]")


if __name__ == "__main__":
    app()
