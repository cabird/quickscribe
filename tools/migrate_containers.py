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
Migration script to consolidate participants and analysis_types containers into QuickScribeContainer.

This script:
1. Copies all records from 'participants' container to 'QuickScribeContainer'
2. Copies all records from 'analysis_types' container to 'QuickScribeContainer'
3. Ensures each record has the 'type' field set correctly

Usage:
    # Preview changes (dry run)
    uv run tools/migrate_containers.py --dry-run

    # Execute migration
    uv run tools/migrate_containers.py

    # With explicit .env file
    uv run tools/migrate_containers.py -e backend/src/.env --dry-run
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


def load_env(env_file: Optional[Path] = None):
    """Load environment variables from .env file."""
    from dotenv import load_dotenv

    if env_file and env_file.exists():
        load_dotenv(env_file)
        console.print(f"[dim]Loaded env from {env_file}[/dim]")
    else:
        # Try common locations
        for path in [Path(".env"), Path("tools/.env"), Path("backend/src/.env"), Path("../backend/src/.env")]:
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


def migrate_container(
    source_container,
    target_container,
    entity_type: str,
    dry_run: bool,
    verbose: bool
) -> dict:
    """
    Migrate all records from source container to target container.

    Args:
        source_container: Source Cosmos container client
        target_container: Target Cosmos container client
        entity_type: The type value to set (e.g., 'participant', 'analysis_type')
        dry_run: If True, don't actually write records
        verbose: If True, show detailed output

    Returns:
        Dictionary with migration statistics
    """
    stats = {
        "found": 0,
        "migrated": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Query all records from source
    query = "SELECT * FROM c"
    items = list(source_container.query_items(query=query, enable_cross_partition_query=True))
    stats["found"] = len(items)

    for item in items:
        record_id = item.get("id", "unknown")
        partition_key = item.get("partitionKey", "unknown")

        # Ensure type field is set
        if "type" not in item or item["type"] != entity_type:
            item["type"] = entity_type

        if dry_run:
            if verbose:
                console.print(f"  [dim]Would migrate {entity_type}: {record_id} (pk: {partition_key})[/dim]")
            stats["migrated"] += 1
        else:
            try:
                # Use upsert to handle both new and existing records
                target_container.upsert_item(body=item)
                stats["migrated"] += 1
                if verbose:
                    console.print(f"  [green]Migrated {entity_type}: {record_id}[/green]")
            except Exception as e:
                stats["errors"] += 1
                console.print(f"  [red]Error migrating {record_id}: {e}[/red]")

    return stats


@app.command()
def migrate(
    env_file: Optional[Path] = typer.Option(None, "-e", "--env-file", help="Path to .env file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without executing"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed output"),
):
    """Migrate participants and analysis_types to QuickScribeContainer."""

    load_env(env_file)
    client = get_cosmos_client()

    database_name = os.environ.get("AZURE_COSMOS_DATABASE_NAME", "QuickScribeDatabase")
    target_container_name = os.environ.get("AZURE_COSMOS_CONTAINER_NAME", "QuickScribeContainer")

    database = client.get_database_client(database_name)

    # Get container clients
    participants_container = database.get_container_client("participants")
    analysis_types_container = database.get_container_client("analysis_types")
    target_container = database.get_container_client(target_container_name)

    console.print(f"\n[bold]Container Consolidation Migration[/bold]")
    console.print(f"Database: {database_name}")
    console.print(f"Target container: {target_container_name}")
    console.print(f"Mode: {'[yellow]DRY RUN[/yellow]' if dry_run else '[red]LIVE[/red]'}\n")

    # Create results table
    table = Table(title="Migration Results")
    table.add_column("Source Container", style="cyan")
    table.add_column("Entity Type", style="magenta")
    table.add_column("Found", justify="right")
    table.add_column("Migrated", justify="right", style="green")
    table.add_column("Errors", justify="right", style="red")

    total_stats = {"found": 0, "migrated": 0, "skipped": 0, "errors": 0}

    # Migrate participants
    console.print("[bold]Migrating participants...[/bold]")
    try:
        participant_stats = migrate_container(
            participants_container,
            target_container,
            "participant",
            dry_run,
            verbose
        )
        table.add_row(
            "participants",
            "participant",
            str(participant_stats["found"]),
            str(participant_stats["migrated"]),
            str(participant_stats["errors"])
        )
        for key in total_stats:
            total_stats[key] += participant_stats[key]
    except Exception as e:
        console.print(f"[red]Error accessing participants container: {e}[/red]")
        table.add_row("participants", "participant", "ERROR", "-", "-")

    # Migrate analysis_types
    console.print("[bold]Migrating analysis_types...[/bold]")
    try:
        analysis_stats = migrate_container(
            analysis_types_container,
            target_container,
            "analysis_type",
            dry_run,
            verbose
        )
        table.add_row(
            "analysis_types",
            "analysis_type",
            str(analysis_stats["found"]),
            str(analysis_stats["migrated"]),
            str(analysis_stats["errors"])
        )
        for key in total_stats:
            total_stats[key] += analysis_stats[key]
    except Exception as e:
        console.print(f"[red]Error accessing analysis_types container: {e}[/red]")
        table.add_row("analysis_types", "analysis_type", "ERROR", "-", "-")

    # Show results
    console.print()
    console.print(table)

    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total records found: {total_stats['found']}")
    console.print(f"  {'Would migrate' if dry_run else 'Migrated'}: [green]{total_stats['migrated']}[/green]")
    if total_stats["errors"] > 0:
        console.print(f"  Errors: [red]{total_stats['errors']}[/red]")

    if dry_run and total_stats["migrated"] > 0:
        console.print(f"\n[yellow]Run without --dry-run to apply changes[/yellow]")
    elif not dry_run and total_stats["migrated"] > 0:
        console.print(f"\n[green]Migration complete![/green]")
        console.print(f"[dim]Note: Old containers (participants, analysis_types) still exist.[/dim]")
        console.print(f"[dim]Verify the data before deleting them.[/dim]")


@app.command()
def verify(
    env_file: Optional[Path] = typer.Option(None, "-e", "--env-file", help="Path to .env file"),
):
    """Verify that migrated data exists in QuickScribeContainer."""

    load_env(env_file)
    client = get_cosmos_client()

    database_name = os.environ.get("AZURE_COSMOS_DATABASE_NAME", "QuickScribeDatabase")
    target_container_name = os.environ.get("AZURE_COSMOS_CONTAINER_NAME", "QuickScribeContainer")

    database = client.get_database_client(database_name)
    target_container = database.get_container_client(target_container_name)

    console.print(f"\n[bold]Verifying Migration[/bold]")
    console.print(f"Container: {target_container_name}\n")

    # Count participants
    participant_query = "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'participant'"
    participant_count = list(target_container.query_items(
        query=participant_query,
        enable_cross_partition_query=True
    ))[0]

    # Count analysis_types
    analysis_query = "SELECT VALUE COUNT(1) FROM c WHERE c.type = 'analysis_type'"
    analysis_count = list(target_container.query_items(
        query=analysis_query,
        enable_cross_partition_query=True
    ))[0]

    # Create table
    table = Table(title=f"Records in {target_container_name}")
    table.add_column("Entity Type", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("participant", str(participant_count))
    table.add_row("analysis_type", str(analysis_count))

    console.print(table)

    # Compare with source containers
    console.print(f"\n[bold]Comparing with source containers:[/bold]")

    try:
        participants_container = database.get_container_client("participants")
        source_participants = list(participants_container.query_items(
            query="SELECT VALUE COUNT(1) FROM c",
            enable_cross_partition_query=True
        ))[0]

        match = "[green]MATCH[/green]" if source_participants == participant_count else f"[red]MISMATCH (source: {source_participants})[/red]"
        console.print(f"  participants: {match}")
    except Exception as e:
        console.print(f"  participants: [yellow]Container not found or empty[/yellow]")

    try:
        analysis_types_container = database.get_container_client("analysis_types")
        source_analysis = list(analysis_types_container.query_items(
            query="SELECT VALUE COUNT(1) FROM c",
            enable_cross_partition_query=True
        ))[0]

        match = "[green]MATCH[/green]" if source_analysis == analysis_count else f"[red]MISMATCH (source: {source_analysis})[/red]"
        console.print(f"  analysis_types: {match}")
    except Exception as e:
        console.print(f"  analysis_types: [yellow]Container not found or empty[/yellow]")


@app.command()
def delete_old_containers(
    env_file: Optional[Path] = typer.Option(None, "-e", "--env-file", help="Path to .env file"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
):
    """Delete the old participants and analysis_types containers."""

    load_env(env_file)
    client = get_cosmos_client()

    database_name = os.environ.get("AZURE_COSMOS_DATABASE_NAME", "QuickScribeDatabase")
    database = client.get_database_client(database_name)

    console.print(f"\n[bold red]WARNING: This will permanently delete containers![/bold red]")
    console.print(f"Database: {database_name}")
    console.print(f"Containers to delete: participants, analysis_types\n")

    if not force:
        confirm = typer.confirm("Are you sure you want to delete these containers?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    # Delete participants container
    try:
        database.delete_container("participants")
        console.print("[green]Deleted container: participants[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting participants: {e}[/red]")

    # Delete analysis_types container
    try:
        database.delete_container("analysis_types")
        console.print("[green]Deleted container: analysis_types[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting analysis_types: {e}[/red]")

    console.print(f"\n[green]Done![/green]")


if __name__ == "__main__":
    app()
