#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.9.0",
#     "rich>=13.0.0",
#     "azure-cosmos>=4.7.0",
#     "azure-storage-blob>=12.23.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Azure Explorer - A CLI tool for exploring and modifying Azure CosmosDB and Blob Storage.

This tool provides LLM-friendly discovery of database structure and blob storage,
with full CRUD operations and safety features.

Usage:
    uv run tools/azure_explorer.py <resource> <command> [options]

Resources:
    cosmos  - CosmosDB database operations
    blob    - Azure Blob Storage operations

Examples:
    # CosmosDB operations
    uv run tools/azure_explorer.py cosmos discover
    uv run tools/azure_explorer.py cosmos schema recording
    uv run tools/azure_explorer.py cosmos query "SELECT * FROM c WHERE c.type = 'recording'"

    # Blob Storage operations
    uv run tools/azure_explorer.py blob list
    uv run tools/azure_explorer.py blob info "user-123/recording.mp3"
    uv run tools/azure_explorer.py blob url "user-123/recording.mp3" --hours 24

Environment Variables (loaded from .env automatically):
    AZURE_COSMOS_ENDPOINT              CosmosDB endpoint URL
    AZURE_COSMOS_KEY                   CosmosDB master key
    AZURE_COSMOS_DATABASE_NAME         Database name (default: quickscribe)
    AZURE_COSMOS_CONTAINER_NAME        Container name (default: recordings)
    AZURE_STORAGE_CONNECTION_STRING    Blob storage connection string
    AZURE_STORAGE_AUDIO_CONTAINER_NAME Blob container (default: recordings)

.env Loading Order:
    1. Existing environment variables (not overwritten)
    2. --env-file path if specified
    3. .env in current working directory
    4. .env in script directory (tools/)
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax


# =============================================================================
# Environment Loading
# =============================================================================

def load_env_files(env_file: Optional[Path] = None, verbose: bool = False) -> None:
    """
    Load environment variables from .env files.

    Loading order (later files don't override existing vars):
    1. Existing environment variables (preserved)
    2. --env-file path if specified
    3. .env in current working directory
    4. .env in script directory
    """
    loaded_from = []

    # Script directory .env (lowest priority, load first so others override)
    script_dir = Path(__file__).parent
    script_env = script_dir / ".env"
    if script_env.exists():
        load_dotenv(script_env, override=False)
        loaded_from.append(f"script dir: {script_env}")

    # Current working directory .env
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists() and cwd_env != script_env:
        load_dotenv(cwd_env, override=False)
        loaded_from.append(f"cwd: {cwd_env}")

    # Explicit --env-file (highest priority for files)
    if env_file:
        if env_file.exists():
            load_dotenv(env_file, override=False)
            loaded_from.append(f"--env-file: {env_file}")
        else:
            rprint(f"[yellow]Warning: Specified env file not found: {env_file}[/yellow]")

    if verbose and loaded_from:
        rprint(f"[dim]Loaded .env from: {', '.join(reversed(loaded_from))}[/dim]")

# =============================================================================
# App Setup
# =============================================================================

def app_callback(
    ctx: typer.Context,
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file", "-e",
        help="Path to .env file to load",
        exists=False,  # We handle existence check ourselves for better error message
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show verbose output (e.g., which .env files were loaded)",
    ),
):
    """Load environment variables before running commands."""
    load_env_files(env_file, verbose)
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


app = typer.Typer(
    name="azure_explorer",
    help="""
Azure Explorer - Swiss army knife for Azure CosmosDB and Blob Storage.

A CLI tool for discovering, querying, and modifying data in Azure services.
Designed for both humans and LLMs.

[bold]Resources:[/bold]
  cosmos  - CosmosDB database operations (discover, query, CRUD)
  blob    - Azure Blob Storage operations (list, upload, download, SAS URLs)

[bold]Quick Start:[/bold]
  uv run tools/azure_explorer.py cosmos discover          # See all entity types
  uv run tools/azure_explorer.py cosmos schema recording  # Understand data structure
  uv run tools/azure_explorer.py blob list                # List all blobs

[bold]Environment Variables (auto-loaded from .env):[/bold]
  AZURE_COSMOS_ENDPOINT              CosmosDB endpoint URL
  AZURE_COSMOS_KEY                   CosmosDB master key
  AZURE_COSMOS_DATABASE_NAME         Database name (default: quickscribe)
  AZURE_COSMOS_CONTAINER_NAME        Default container (default: recordings)
  AZURE_STORAGE_CONNECTION_STRING    Blob storage connection string
  AZURE_STORAGE_AUDIO_CONTAINER_NAME Blob container name (default: recordings)

[bold].env Loading Order:[/bold]
  1. Existing environment variables (preserved)
  2. --env-file <path> if specified
  3. .env in current working directory
  4. .env in script directory (tools/)
""",
    rich_markup_mode="rich",
    no_args_is_help=True,
    callback=app_callback,
)

cosmos_app = typer.Typer(
    name="cosmos",
    help="CosmosDB database operations - discover, query, and modify data.",
    no_args_is_help=True,
)

blob_app = typer.Typer(
    name="blob",
    help="Azure Blob Storage operations - list, upload, download, and manage blobs.",
    no_args_is_help=True,
)

app.add_typer(cosmos_app, name="cosmos")
app.add_typer(blob_app, name="blob")

console = Console()


# =============================================================================
# Configuration Helpers
# =============================================================================

def get_cosmos_client():
    """Create CosmosDB client from environment variables."""
    from azure.cosmos import CosmosClient

    endpoint = os.environ.get('AZURE_COSMOS_ENDPOINT')
    key = os.environ.get('AZURE_COSMOS_KEY')
    database = os.environ.get('AZURE_COSMOS_DATABASE_NAME', 'quickscribe')
    container = os.environ.get('AZURE_COSMOS_CONTAINER_NAME', 'recordings')

    if not endpoint or not key:
        rprint("[red]Error: Missing required environment variables.[/red]")
        rprint("\n[bold]Required:[/bold]")
        rprint("  AZURE_COSMOS_ENDPOINT - CosmosDB endpoint URL")
        rprint("  AZURE_COSMOS_KEY      - CosmosDB master key")
        rprint("\n[bold]Optional:[/bold]")
        rprint("  AZURE_COSMOS_DATABASE_NAME  - Database name (default: quickscribe)")
        rprint("  AZURE_COSMOS_CONTAINER_NAME - Container name (default: recordings)")
        raise typer.Exit(1)

    client = CosmosClient(endpoint, credential=key)
    return client, database, container


def get_blob_client():
    """Create Blob Storage client from environment variables."""
    from azure.storage.blob import BlobServiceClient

    connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    # Check both possible env var names for container
    container = (
        os.environ.get('AZURE_STORAGE_AUDIO_CONTAINER_NAME') or
        os.environ.get('AZURE_RECORDING_BLOB_CONTAINER') or
        'recordings'
    )

    if not connection_string:
        rprint("[red]Error: Missing required environment variables.[/red]")
        rprint("\n[bold]Required:[/bold]")
        rprint("  AZURE_STORAGE_CONNECTION_STRING - Azure Storage connection string")
        rprint("\n[bold]Optional:[/bold]")
        rprint("  AZURE_STORAGE_AUDIO_CONTAINER_NAME - Container name (default: recordings)")
        raise typer.Exit(1)

    service_client = BlobServiceClient.from_connection_string(connection_string)
    return service_client, container


def get_container(client, database_name: str, container_name: str):
    """Get a CosmosDB container client."""
    database = client.get_database_client(database_name)
    return database.get_container_client(container_name)


# =============================================================================
# Utility Functions
# =============================================================================

def infer_type(value: Any) -> str:
    """Infer a human-readable type from a Python value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "bool"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        if len(value) > 10 and ('T' in value or '-' in value[:10]):
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return "datetime"
            except:
                pass
        return "str"
    elif isinstance(value, list):
        if value:
            inner_type = infer_type(value[0])
            return f"list[{inner_type}]"
        return "list"
    elif isinstance(value, dict):
        return "dict"
    else:
        return type(value).__name__


def truncate_example(value: Any, max_len: int = 60) -> str:
    """Truncate an example value for display."""
    if value is None:
        return "null"
    if isinstance(value, str):
        if len(value) > max_len:
            return f'"{value[:max_len]}..."'
        return f'"{value}"'
    elif isinstance(value, (list, dict)):
        s = json.dumps(value, default=str)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    else:
        s = str(value)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# =============================================================================
# CosmosDB Commands
# =============================================================================

@cosmos_app.command("discover")
def cosmos_discover(
    output_json: bool = typer.Option(False, "--json", help="Output results as JSON"),
):
    """
    Discover all entity types in the database.

    Scans all containers and identifies unique entity types by examining
    the 'type' and 'partitionKey' fields. Reports counts for each type.

    This is the first command to run when exploring an unfamiliar database.
    """
    client, db_name, default_container = get_cosmos_client()
    database = client.get_database_client(db_name)

    rprint(f"[bold]Discovering entities in database:[/bold] {db_name}")

    containers = list(database.list_containers())
    if not containers:
        rprint("[yellow]No containers found in database.[/yellow]")
        return

    all_types = []

    for container_props in containers:
        container_name = container_props['id']
        container = database.get_container_client(container_name)
        rprint(f"  Scanning container: [cyan]{container_name}[/cyan]...")

        query = "SELECT c.type, c.partitionKey FROM c"
        try:
            results = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            type_counts = defaultdict(int)
            for item in results:
                entity_type = item.get('type') or item.get('partitionKey') or 'unknown'
                partition_key = item.get('partitionKey', 'N/A')
                key = (entity_type, partition_key)
                type_counts[key] += 1

            for (entity_type, partition_key), count in type_counts.items():
                all_types.append({
                    'type': entity_type,
                    'partition_key': partition_key,
                    'count': count,
                    'container': container_name
                })
        except Exception as e:
            rprint(f"    [yellow]Warning: Could not query container '{container_name}': {e}[/yellow]")

    if not all_types:
        rprint("\n[yellow]No entity types found.[/yellow]")
        return

    all_types.sort(key=lambda x: x['count'], reverse=True)

    table = Table(title=f"\nEntity Types ({len(all_types)} found)")
    table.add_column("Entity Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Partition Key", style="yellow")
    table.add_column("Container", style="blue")

    for item in all_types:
        table.add_row(
            item['type'],
            str(item['count']),
            item['partition_key'],
            item['container']
        )

    console.print(table)

    if output_json:
        rprint("\n[bold]JSON Output:[/bold]")
        print(json.dumps(all_types, indent=2))


@cosmos_app.command("containers")
def cosmos_containers(
    output_json: bool = typer.Option(False, "--json", help="Output results as JSON"),
):
    """
    List all containers in the database with their partition keys.

    Partition keys are essential for efficient queries - knowing the
    partition key helps write faster queries and is required for point reads.
    """
    client, db_name, _ = get_cosmos_client()
    database = client.get_database_client(db_name)

    rprint(f"[bold]Containers in database:[/bold] {db_name}\n")

    containers = list(database.list_containers())
    if not containers:
        rprint("[yellow]No containers found.[/yellow]")
        return

    results = []
    table = Table()
    table.add_column("Container", style="cyan")
    table.add_column("Partition Key", style="yellow")

    for container in containers:
        info = {
            'name': container['id'],
            'partition_key': container.get('partitionKey', {}).get('paths', ['N/A'])[0]
        }
        results.append(info)
        table.add_row(info['name'], info['partition_key'])

    console.print(table)

    if output_json:
        rprint("\n[bold]JSON Output:[/bold]")
        print(json.dumps(results, indent=2))


@cosmos_app.command("schema")
def cosmos_schema(
    entity_type: str = typer.Argument(..., help="Entity type to get schema for (e.g., recording, user)"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container to query"),
    samples: int = typer.Option(5, "--samples", "-n", help="Number of samples to analyze"),
    output_json: bool = typer.Option(False, "--json", help="Output schema as JSON"),
):
    """
    Infer and display schema for an entity type.

    Samples multiple records and builds a merged schema showing field names,
    inferred types, and example values. Designed for LLM consumption.
    """
    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    query = f"SELECT * FROM c WHERE c.type = @type OR c.partitionKey = @type OFFSET 0 LIMIT {samples}"
    parameters = [{"name": "@type", "value": entity_type}]

    try:
        sample_records = list(container_client.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
    except Exception as e:
        rprint(f"[red]Error querying for entity type '{entity_type}': {e}[/red]")
        raise typer.Exit(1)

    if not sample_records:
        rprint(f"[yellow]No records found for entity type: {entity_type}[/yellow]")
        rprint("\n[dim]Hint: Use 'azure_explorer.py cosmos discover' to see available entity types.[/dim]")
        return

    schema = {}
    field_occurrences = defaultdict(int)

    for sample in sample_records:
        for key, value in sample.items():
            if key.startswith('_'):
                continue
            field_occurrences[key] += 1
            if key not in schema:
                schema[key] = {'types': set(), 'examples': [], 'nullable': False}
            inferred = infer_type(value)
            schema[key]['types'].add(inferred)
            if len(schema[key]['examples']) < 3 and value is not None:
                example = truncate_example(value)
                if example not in schema[key]['examples']:
                    schema[key]['examples'].append(example)
            if value is None:
                schema[key]['nullable'] = True

    for key in schema:
        schema[key]['required'] = field_occurrences[key] == len(sample_records)

    rprint(f"\n[bold]Schema for '{entity_type}'[/bold] (from {len(sample_records)} sample(s))")
    rprint(f"[dim]Container: {container_name}[/dim]\n")

    sorted_fields = sorted(schema.keys(), key=lambda k: (not schema[k]['required'], k))

    for field in sorted_fields:
        info = schema[field]
        types_str = " | ".join(sorted(info['types']))
        nullable_marker = "?" if info['nullable'] or not info['required'] else ""
        rprint(f"  [cyan]{field}[/cyan]: [yellow]{types_str}{nullable_marker}[/yellow]")
        for example in info['examples'][:2]:
            rprint(f"    [dim]e.g., {example}[/dim]")

    if output_json:
        json_schema = {}
        for key, value in schema.items():
            json_schema[key] = {
                'types': list(value['types']),
                'examples': value['examples'],
                'nullable': value['nullable'],
                'required': value['required']
            }
        rprint("\n[bold]JSON Output:[/bold]")
        print(json.dumps(json_schema, indent=2))


@cosmos_app.command("sample")
def cosmos_sample(
    entity_type: str = typer.Argument(..., help="Entity type to sample (e.g., recording, user)"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container to query"),
    count: int = typer.Option(3, "--count", "-n", help="Number of samples"),
    include_internal: bool = typer.Option(False, "--include-internal", help="Include Cosmos internal fields"),
):
    """
    Get sample records of an entity type as JSON.

    Returns full records, useful for understanding data structure,
    getting IDs for further operations, and debugging.
    """
    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    query = f"SELECT * FROM c WHERE c.type = @type OR c.partitionKey = @type OFFSET 0 LIMIT {count}"
    parameters = [{"name": "@type", "value": entity_type}]

    try:
        samples = list(container_client.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not samples:
        rprint(f"[yellow]No records found for entity type: {entity_type}[/yellow]")
        return

    if not include_internal:
        samples = [{k: v for k, v in s.items() if not k.startswith('_')} for s in samples]

    print(json.dumps(samples, indent=2, default=str))


@cosmos_app.command("query")
def cosmos_query(
    sql: str = typer.Argument(..., help="SQL query to execute"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container to query"),
    params: Optional[str] = typer.Option(None, "--params", "-p", help='Query parameters as JSON, e.g., \'{"uid": "abc123"}\''),
    limit: int = typer.Option(100, "--limit", "-l", help="Max results"),
    include_internal: bool = typer.Option(False, "--include-internal", help="Include Cosmos internal fields"),
):
    """
    Execute a SQL query against CosmosDB.

    Supports full CosmosDB SQL syntax. Use --params for parameterized queries.
    Cross-partition queries are enabled by default.
    """
    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    parameters = []
    if params:
        try:
            params_dict = json.loads(params)
            parameters = [{"name": f"@{k}", "value": v} for k, v in params_dict.items()]
        except json.JSONDecodeError as e:
            rprint(f"[red]Error parsing parameters JSON: {e}[/red]")
            raise typer.Exit(1)

    try:
        results = list(container_client.query_items(
            query=sql,
            parameters=parameters if parameters else None,
            enable_cross_partition_query=True,
            max_item_count=limit
        ))
    except Exception as e:
        rprint(f"[red]Query error: {e}[/red]")
        raise typer.Exit(1)

    if not results:
        rprint("[yellow]No results found.[/yellow]")
        return

    if not include_internal:
        results = [{k: v for k, v in r.items() if not k.startswith('_')} for r in results]

    rprint(f"[green]Found {len(results)} result(s)[/green]")
    print(json.dumps(results, indent=2, default=str))


@cosmos_app.command("get")
def cosmos_get(
    id: str = typer.Option(..., "--id", help="Record ID"),
    partition: str = typer.Option(..., "--partition", "-p", help="Partition key value"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container name"),
    include_internal: bool = typer.Option(False, "--include-internal", help="Include Cosmos internal fields"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON (default behavior, flag for consistency)"),
):
    """
    Get a single record by ID.

    Requires both ID and partition key for efficient point read.
    This is the fastest way to retrieve a specific record.
    """
    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    try:
        item = container_client.read_item(item=id, partition_key=partition)
    except CosmosResourceNotFoundError:
        rprint(f"[red]Record not found: id={id}, partition={partition}[/red]")
        raise typer.Exit(1)

    if not include_internal:
        item = {k: v for k, v in item.items() if not k.startswith('_')}

    print(json.dumps(item, indent=2, default=str))


@cosmos_app.command("update")
def cosmos_update(
    id: str = typer.Option(..., "--id", help="Record ID to update"),
    partition: str = typer.Option(..., "--partition", "-p", help="Partition key value"),
    set_fields: str = typer.Option(..., "--set", "-s", help='Fields to update as JSON, e.g., \'{"title": "New Title"}\''),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    backup: bool = typer.Option(False, "--backup", help="Save original record to file before modifying"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    output_json: bool = typer.Option(False, "--json", help="Output updated record as JSON"),
):
    """
    Update specific fields on a record.

    Performs a read-modify-write operation - only specified fields change.
    Use --dry-run to preview changes before applying.
    """
    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    try:
        updates = json.loads(set_fields)
    except json.JSONDecodeError as e:
        rprint(f"[red]Error parsing --set JSON: {e}[/red]")
        raise typer.Exit(1)

    try:
        current = container_client.read_item(item=id, partition_key=partition)
    except CosmosResourceNotFoundError:
        rprint(f"[red]Record not found: id={id}, partition={partition}[/red]")
        raise typer.Exit(1)

    if backup:
        backup_file = f"backup_{id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(current, f, indent=2, default=str)
        rprint(f"[green]Backup saved to: {backup_file}[/green]")

    updated = current.copy()
    for key, value in updates.items():
        updated[key] = value

    rprint("\n[bold]Changes to be applied:[/bold]")
    for key, new_value in updates.items():
        old_value = current.get(key, '<not set>')
        rprint(f"  [cyan]{key}[/cyan]:")
        rprint(f"    OLD: [red]{truncate_example(old_value)}[/red]")
        rprint(f"    NEW: [green]{truncate_example(new_value)}[/green]")

    if dry_run:
        rprint("\n[yellow][DRY RUN] No changes made.[/yellow]")
        return

    if not force:
        confirm = typer.confirm("\nApply these changes?", default=False)
        if not confirm:
            rprint("[yellow]Cancelled.[/yellow]")
            return

    try:
        result = container_client.replace_item(item=id, body=updated)
        rprint("\n[green]Update successful![/green]")
        if output_json:
            filtered = {k: v for k, v in result.items() if not k.startswith('_')}
            print(json.dumps(filtered, indent=2, default=str))
    except Exception as e:
        rprint(f"[red]Update failed: {e}[/red]")
        raise typer.Exit(1)


@cosmos_app.command("insert")
def cosmos_insert(
    data: str = typer.Option(..., "--data", "-d", help="Record data as JSON"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without inserting"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    output_json: bool = typer.Option(False, "--json", help="Output created record as JSON"),
):
    """
    Insert a new record.

    If 'id' is not provided in the data, one will be auto-generated.
    Use 'azure_explorer.py cosmos schema <type>' to see required fields.
    """
    import uuid

    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    try:
        record = json.loads(data)
    except json.JSONDecodeError as e:
        rprint(f"[red]Error parsing --data JSON: {e}[/red]")
        raise typer.Exit(1)

    if 'id' not in record:
        record['id'] = str(uuid.uuid4())
        rprint(f"[dim]Auto-generated ID: {record['id']}[/dim]")

    rprint("\n[bold]Record to insert:[/bold]")
    console.print(Syntax(json.dumps(record, indent=2), "json"))

    if dry_run:
        rprint("\n[yellow][DRY RUN] No changes made.[/yellow]")
        return

    if not force:
        confirm = typer.confirm("\nInsert this record?", default=False)
        if not confirm:
            rprint("[yellow]Cancelled.[/yellow]")
            return

    try:
        result = container_client.create_item(body=record)
        rprint("\n[green]Insert successful![/green]")
        if output_json:
            filtered = {k: v for k, v in result.items() if not k.startswith('_')}
            print(json.dumps(filtered, indent=2, default=str))
    except Exception as e:
        rprint(f"[red]Insert failed: {e}[/red]")
        raise typer.Exit(1)


@cosmos_app.command("delete")
def cosmos_delete(
    id: str = typer.Option(..., "--id", help="Record ID to delete"),
    partition: str = typer.Option(..., "--partition", "-p", help="Partition key value"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Verify record exists without deleting"),
    backup: bool = typer.Option(False, "--backup", help="Save record to file before deleting"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """
    Delete a record by ID.

    WARNING: This is PERMANENT. Use --backup to save the record first.
    """
    from azure.cosmos.exceptions import CosmosResourceNotFoundError

    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    try:
        current = container_client.read_item(item=id, partition_key=partition)
    except CosmosResourceNotFoundError:
        rprint(f"[red]Record not found: id={id}, partition={partition}[/red]")
        raise typer.Exit(1)

    if backup:
        backup_file = f"backup_{id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(current, f, indent=2, default=str)
        rprint(f"[green]Backup saved to: {backup_file}[/green]")

    rprint("\n[bold]Record to delete:[/bold]")
    filtered = {k: v for k, v in current.items() if not k.startswith('_')}
    console.print(Syntax(json.dumps(filtered, indent=2, default=str), "json"))

    if dry_run:
        rprint("\n[yellow][DRY RUN] No changes made.[/yellow]")
        return

    if not force:
        confirm = typer.confirm("\nPERMANENTLY DELETE this record?", default=False)
        if not confirm:
            rprint("[yellow]Cancelled.[/yellow]")
            return

    try:
        container_client.delete_item(item=id, partition_key=partition)
        rprint("\n[green]Delete successful![/green]")
    except Exception as e:
        rprint(f"[red]Delete failed: {e}[/red]")
        raise typer.Exit(1)


@cosmos_app.command("bulk-update")
def cosmos_bulk_update(
    where: str = typer.Option(..., "--where", "-w", help="WHERE clause (SQL syntax, without WHERE keyword)"),
    set_fields: str = typer.Option(..., "--set", "-s", help="Fields to update as JSON"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container name"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max records to update"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview matching records without modifying"),
    backup: bool = typer.Option(False, "--backup", help="Save all affected records to file"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """
    Update multiple records matching a query.

    DANGEROUS: This can modify many records at once.
    ALWAYS use --dry-run first to preview affected records.
    """
    client, db_name, default_container = get_cosmos_client()
    container_name = container or default_container
    container_client = get_container(client, db_name, container_name)

    try:
        updates = json.loads(set_fields)
    except json.JSONDecodeError as e:
        rprint(f"[red]Error parsing --set JSON: {e}[/red]")
        raise typer.Exit(1)

    query = f"SELECT * FROM c WHERE {where}"
    if limit:
        query += f" OFFSET 0 LIMIT {limit}"

    try:
        records = list(container_client.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
    except Exception as e:
        rprint(f"[red]Query error: {e}[/red]")
        raise typer.Exit(1)

    if not records:
        rprint("[yellow]No records match the query.[/yellow]")
        return

    rprint(f"[bold]Found {len(records)} record(s) matching:[/bold]")
    rprint(f"  [dim]WHERE {where}[/dim]")
    rprint(f"\n[bold]Fields to update:[/bold]")
    for key, value in updates.items():
        rprint(f"  [cyan]{key}[/cyan] = [green]{truncate_example(value)}[/green]")

    if backup:
        backup_file = f"bulk_backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(records, f, indent=2, default=str)
        rprint(f"\n[green]Backup saved to: {backup_file}[/green]")

    if dry_run:
        rprint(f"\n[yellow][DRY RUN] Would update {len(records)} record(s):[/yellow]")
        for record in records[:5]:
            rprint(f"  - {record.get('id', 'unknown')}")
        if len(records) > 5:
            rprint(f"  [dim]... and {len(records) - 5} more[/dim]")
        return

    if not force:
        confirm = typer.confirm(f"\nUpdate {len(records)} record(s)?", default=False)
        if not confirm:
            rprint("[yellow]Cancelled.[/yellow]")
            return

    success_count = 0
    error_count = 0

    for record in records:
        try:
            for key, value in updates.items():
                record[key] = value
            container_client.replace_item(item=record['id'], body=record)
            success_count += 1
        except Exception as e:
            rprint(f"  [red]Error updating {record.get('id')}: {e}[/red]")
            error_count += 1

    rprint(f"\n[bold]Bulk update complete:[/bold] {success_count} succeeded, {error_count} failed")


# =============================================================================
# Blob Storage Commands
# =============================================================================

@blob_app.command("list")
def blob_list(
    prefix: Optional[str] = typer.Option(None, "--prefix", "-p", help="Filter by blob name prefix (e.g., 'user-123/')"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max blobs to list"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    List blobs in the container.

    Use --prefix to filter by path prefix (e.g., user ID folder).
    """
    service_client, container_name = get_blob_client()
    container_client = service_client.get_container_client(container_name)

    rprint(f"[bold]Listing blobs in container:[/bold] {container_name}")
    if prefix:
        rprint(f"[dim]Prefix filter: {prefix}[/dim]")

    blobs = []
    count = 0

    for blob in container_client.list_blobs(name_starts_with=prefix):
        if count >= limit:
            break
        blobs.append({
            'name': blob.name,
            'size': blob.size,
            'size_formatted': format_size(blob.size),
            'last_modified': blob.last_modified.isoformat() if blob.last_modified else None,
            'content_type': blob.content_settings.content_type if blob.content_settings else None,
        })
        count += 1

    if not blobs:
        rprint("[yellow]No blobs found.[/yellow]")
        return

    if output_json:
        print(json.dumps(blobs, indent=2))
    else:
        table = Table(title=f"\nBlobs ({len(blobs)} shown, limit={limit})")
        table.add_column("Name", style="cyan", max_width=60)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Last Modified", style="yellow")

        for blob in blobs:
            table.add_row(
                blob['name'],
                blob['size_formatted'],
                blob['last_modified'][:19] if blob['last_modified'] else 'N/A'
            )

        console.print(table)


@blob_app.command("info")
def blob_info(
    path: str = typer.Argument(..., help="Blob path (e.g., 'user-123/recording.mp3')"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Get detailed information about a blob.

    Shows size, content type, last modified, and metadata.
    """
    service_client, container_name = get_blob_client()
    blob_client = service_client.get_blob_client(container=container_name, blob=path)

    if not blob_client.exists():
        rprint(f"[red]Blob not found: {path}[/red]")
        raise typer.Exit(1)

    props = blob_client.get_blob_properties()

    info = {
        'name': path,
        'size': props.size,
        'size_formatted': format_size(props.size),
        'content_type': props.content_settings.content_type if props.content_settings else None,
        'last_modified': props.last_modified.isoformat() if props.last_modified else None,
        'created': props.creation_time.isoformat() if props.creation_time else None,
        'etag': props.etag,
        'metadata': dict(props.metadata) if props.metadata else {},
    }

    if output_json:
        print(json.dumps(info, indent=2))
    else:
        rprint(f"\n[bold]Blob Information:[/bold] {path}\n")
        rprint(f"  [cyan]Size:[/cyan]         {info['size_formatted']} ({info['size']} bytes)")
        rprint(f"  [cyan]Content Type:[/cyan] {info['content_type'] or 'N/A'}")
        rprint(f"  [cyan]Last Modified:[/cyan] {info['last_modified'] or 'N/A'}")
        rprint(f"  [cyan]Created:[/cyan]      {info['created'] or 'N/A'}")
        rprint(f"  [cyan]ETag:[/cyan]         {info['etag']}")
        if info['metadata']:
            rprint(f"  [cyan]Metadata:[/cyan]     {json.dumps(info['metadata'])}")


@blob_app.command("url")
def blob_url(
    path: str = typer.Argument(..., help="Blob path (e.g., 'user-123/recording.mp3')"),
    hours: int = typer.Option(24, "--hours", "-h", help="Hours until URL expires"),
    write: bool = typer.Option(False, "--write", "-w", help="Include write permission"),
):
    """
    Generate a SAS URL for a blob.

    Creates a time-limited URL that can be used to access the blob
    without Azure credentials. Default is read-only for 24 hours.
    """
    from azure.storage.blob import generate_blob_sas, BlobSasPermissions
    from datetime import timedelta

    service_client, container_name = get_blob_client()
    blob_client = service_client.get_blob_client(container=container_name, blob=path)

    if not blob_client.exists():
        rprint(f"[red]Blob not found: {path}[/red]")
        raise typer.Exit(1)

    permissions = BlobSasPermissions(read=True, write=write, create=write)

    sas_token = generate_blob_sas(
        account_name=service_client.account_name,
        container_name=container_name,
        blob_name=path,
        account_key=service_client.credential.account_key,
        permission=permissions,
        expiry=datetime.now(UTC) + timedelta(hours=hours),
    )

    url = f"https://{service_client.account_name}.blob.core.windows.net/{container_name}/{path}?{sas_token}"

    rprint(f"\n[bold]SAS URL for:[/bold] {path}")
    rprint(f"[dim]Expires in {hours} hours | Permissions: {'read+write' if write else 'read-only'}[/dim]\n")
    print(url)


@blob_app.command("download")
def blob_download(
    path: str = typer.Argument(..., help="Blob path to download"),
    local: str = typer.Argument(..., help="Local file path to save to"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing file"),
):
    """
    Download a blob to a local file.

    Uses streaming download to handle large files efficiently.
    """
    service_client, container_name = get_blob_client()
    blob_client = service_client.get_blob_client(container=container_name, blob=path)

    if not blob_client.exists():
        rprint(f"[red]Blob not found: {path}[/red]")
        raise typer.Exit(1)

    local_path = Path(local)
    if local_path.exists() and not force:
        rprint(f"[red]File already exists: {local}[/red]")
        rprint("[dim]Use --force to overwrite[/dim]")
        raise typer.Exit(1)

    props = blob_client.get_blob_properties()
    rprint(f"[bold]Downloading:[/bold] {path}")
    rprint(f"[dim]Size: {format_size(props.size)}[/dim]")

    with open(local_path, "wb") as f:
        stream = blob_client.download_blob()
        stream.readinto(f)

    rprint(f"\n[green]Downloaded to: {local}[/green]")


@blob_app.command("upload")
def blob_upload(
    local: str = typer.Argument(..., help="Local file path to upload"),
    path: str = typer.Argument(..., help="Blob path to upload to"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without uploading"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation for overwrite"),
):
    """
    Upload a local file to blob storage.

    Will prompt for confirmation if the blob already exists.
    """
    service_client, container_name = get_blob_client()
    blob_client = service_client.get_blob_client(container=container_name, blob=path)

    local_path = Path(local)
    if not local_path.exists():
        rprint(f"[red]Local file not found: {local}[/red]")
        raise typer.Exit(1)

    file_size = local_path.stat().st_size
    exists = blob_client.exists()

    rprint(f"[bold]Upload:[/bold] {local} -> {path}")
    rprint(f"[dim]Size: {format_size(file_size)}[/dim]")
    if exists:
        rprint("[yellow]Warning: Blob already exists and will be overwritten[/yellow]")

    if dry_run:
        rprint("\n[yellow][DRY RUN] No changes made.[/yellow]")
        return

    if exists and not force:
        confirm = typer.confirm("\nOverwrite existing blob?", default=False)
        if not confirm:
            rprint("[yellow]Cancelled.[/yellow]")
            return

    with open(local_path, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)

    rprint(f"\n[green]Upload successful![/green]")


@blob_app.command("delete")
def blob_delete(
    path: str = typer.Argument(..., help="Blob path to delete"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Verify blob exists without deleting"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """
    Delete a blob.

    WARNING: This is PERMANENT. The blob cannot be recovered.
    """
    service_client, container_name = get_blob_client()
    blob_client = service_client.get_blob_client(container=container_name, blob=path)

    if not blob_client.exists():
        rprint(f"[red]Blob not found: {path}[/red]")
        raise typer.Exit(1)

    props = blob_client.get_blob_properties()
    rprint(f"[bold]Blob to delete:[/bold] {path}")
    rprint(f"[dim]Size: {format_size(props.size)}[/dim]")

    if dry_run:
        rprint("\n[yellow][DRY RUN] No changes made.[/yellow]")
        return

    if not force:
        confirm = typer.confirm("\nPERMANENTLY DELETE this blob?", default=False)
        if not confirm:
            rprint("[yellow]Cancelled.[/yellow]")
            return

    blob_client.delete_blob(delete_snapshots="include")
    rprint("\n[green]Delete successful![/green]")


@blob_app.command("orphans")
def blob_orphans(
    prefix: Optional[str] = typer.Option(None, "--prefix", "-p", help="Filter by blob prefix"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs execute deletion"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max blobs to check"),
):
    """
    Find orphaned blobs (in blob storage but not referenced in CosmosDB).

    Cross-references blob storage with CosmosDB recordings to find
    blobs that are no longer associated with any recording.

    Use --execute to delete orphans (default is dry-run preview).
    """
    # Get both clients
    cosmos_client, db_name, cosmos_container = get_cosmos_client()
    service_client, blob_container = get_blob_client()

    container_client = service_client.get_container_client(blob_container)
    cosmos_container_client = get_container(cosmos_client, db_name, cosmos_container)

    rprint("[bold]Finding orphaned blobs...[/bold]")
    rprint(f"[dim]Checking blobs in: {blob_container}[/dim]")
    rprint(f"[dim]Against recordings in: {cosmos_container}[/dim]\n")

    # Get all unique_filenames from CosmosDB
    query = "SELECT c.unique_filename, c.user_id FROM c WHERE c.type = 'recording' OR c.partitionKey = 'recording'"
    recordings = list(cosmos_container_client.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    # Build set of valid blob names (both with and without user prefix)
    valid_blobs = set()
    for rec in recordings:
        uf = rec.get('unique_filename')
        user_id = rec.get('user_id')
        if uf:
            valid_blobs.add(uf)
            if user_id:
                valid_blobs.add(f"{user_id}/{uf}")

    rprint(f"[dim]Found {len(recordings)} recordings with {len(valid_blobs)} valid blob references[/dim]\n")

    # Check blobs
    orphans = []
    count = 0

    for blob in container_client.list_blobs(name_starts_with=prefix):
        if count >= limit:
            break
        count += 1

        # Check if blob is referenced
        if blob.name not in valid_blobs:
            # Also check just the filename part
            filename_only = blob.name.split('/')[-1] if '/' in blob.name else blob.name
            if filename_only not in valid_blobs:
                orphans.append({
                    'name': blob.name,
                    'size': blob.size,
                    'size_formatted': format_size(blob.size),
                    'last_modified': blob.last_modified.isoformat() if blob.last_modified else None,
                })

    if not orphans:
        rprint("[green]No orphaned blobs found![/green]")
        return

    total_size = sum(o['size'] for o in orphans)
    rprint(f"[yellow]Found {len(orphans)} orphaned blob(s)[/yellow]")
    rprint(f"[dim]Total size: {format_size(total_size)}[/dim]\n")

    table = Table(title="Orphaned Blobs")
    table.add_column("Name", style="cyan", max_width=60)
    table.add_column("Size", justify="right", style="green")
    table.add_column("Last Modified", style="yellow")

    for orphan in orphans[:20]:
        table.add_row(
            orphan['name'],
            orphan['size_formatted'],
            orphan['last_modified'][:19] if orphan['last_modified'] else 'N/A'
        )

    if len(orphans) > 20:
        table.add_row("[dim]...[/dim]", f"[dim]+{len(orphans)-20} more[/dim]", "")

    console.print(table)

    if dry_run:
        rprint("\n[yellow][DRY RUN] No blobs deleted. Use --execute to delete.[/yellow]")
    else:
        confirm = typer.confirm(f"\nDelete {len(orphans)} orphaned blob(s)?", default=False)
        if confirm:
            deleted = 0
            for orphan in orphans:
                try:
                    blob_client = service_client.get_blob_client(container=blob_container, blob=orphan['name'])
                    blob_client.delete_blob(delete_snapshots="include")
                    deleted += 1
                except Exception as e:
                    rprint(f"[red]Failed to delete {orphan['name']}: {e}[/red]")
            rprint(f"\n[green]Deleted {deleted} blob(s)[/green]")
        else:
            rprint("[yellow]Cancelled.[/yellow]")


@blob_app.command("missing")
def blob_missing(
    limit: int = typer.Option(100, "--limit", "-l", help="Max recordings to check"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Find recordings with missing blobs (in CosmosDB but not in blob storage).

    Cross-references CosmosDB recordings with blob storage to find
    recordings whose audio files are missing.
    """
    cosmos_client, db_name, cosmos_container = get_cosmos_client()
    service_client, blob_container = get_blob_client()

    container_client = service_client.get_container_client(blob_container)
    cosmos_container_client = get_container(cosmos_client, db_name, cosmos_container)

    rprint("[bold]Finding recordings with missing blobs...[/bold]\n")

    query = f"SELECT c.id, c.unique_filename, c.user_id, c.title FROM c WHERE c.type = 'recording' OR c.partitionKey = 'recording' OFFSET 0 LIMIT {limit}"
    recordings = list(cosmos_container_client.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    missing = []
    for rec in recordings:
        uf = rec.get('unique_filename')
        user_id = rec.get('user_id')
        if not uf:
            continue

        # Check both possible paths
        paths_to_check = [uf]
        if user_id:
            paths_to_check.append(f"{user_id}/{uf}")

        found = False
        for path in paths_to_check:
            blob_client = service_client.get_blob_client(container=blob_container, blob=path)
            if blob_client.exists():
                found = True
                break

        if not found:
            missing.append({
                'id': rec.get('id'),
                'unique_filename': uf,
                'user_id': user_id,
                'title': rec.get('title', 'N/A'),
            })

    if not missing:
        rprint("[green]All recordings have their blobs![/green]")
        return

    rprint(f"[red]Found {len(missing)} recording(s) with missing blobs[/red]\n")

    if output_json:
        print(json.dumps(missing, indent=2))
    else:
        table = Table(title="Recordings with Missing Blobs")
        table.add_column("ID", style="cyan", max_width=40)
        table.add_column("Title", style="yellow", max_width=40)
        table.add_column("Filename", style="red")

        for rec in missing[:20]:
            table.add_row(
                rec['id'][:36] + "..." if len(rec['id']) > 36 else rec['id'],
                (rec['title'][:37] + "...") if len(rec['title']) > 40 else rec['title'],
                rec['unique_filename']
            )

        if len(missing) > 20:
            table.add_row("[dim]...[/dim]", f"[dim]+{len(missing)-20} more[/dim]", "")

        console.print(table)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    app()


if __name__ == "__main__":
    main()
