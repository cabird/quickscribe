# Azure Explorer

A CLI tool for exploring and modifying Azure CosmosDB and Blob Storage. Designed for both humans and LLMs.

## Quick Start

```bash
# Run with uv (recommended - no setup needed)
# Automatically loads .env from current directory or script directory
uv run tools/azure_explorer.py cosmos discover
uv run tools/azure_explorer.py blob list

# Or specify a .env file explicitly
uv run tools/azure_explorer.py -e backend/.env cosmos discover

# Run from backend directory (auto-loads backend/.env)
cd backend && uv run ../tools/azure_explorer.py cosmos discover
```

## .env Auto-Loading

The tool automatically loads environment variables from `.env` files in this order:

1. **Existing environment variables** - never overwritten
2. **`--env-file` / `-e` path** - if specified on command line
3. **`.env` in current working directory**
4. **`.env` in script directory** (`tools/`)

Use `-v` / `--verbose` to see which .env files were loaded.

## Resources

| Resource | Description |
|----------|-------------|
| `cosmos` | CosmosDB database operations |
| `blob` | Azure Blob Storage operations |

## Cosmos Commands

| Command | Description |
|---------|-------------|
| `discover` | List all entity types with counts |
| `containers` | List containers and partition keys |
| `schema <type>` | Infer schema from sample records |
| `sample <type>` | Get sample records as JSON |
| `query "<sql>"` | Execute SQL query |
| `get --id X -p Y` | Get single record by ID |
| `update --id X -p Y --set '{...}'` | Update fields on a record |
| `insert --data '{...}'` | Insert new record |
| `delete --id X -p Y` | Delete a record |
| `bulk-update --where "..." --set '{...}'` | Update multiple records |

## Blob Commands

| Command | Description |
|---------|-------------|
| `list [--prefix X]` | List blobs in container |
| `info <path>` | Get blob details (size, modified, etc.) |
| `url <path> [--hours N]` | Generate SAS URL |
| `download <path> <local>` | Download blob to local file |
| `upload <local> <path>` | Upload local file to blob |
| `delete <path>` | Delete a blob |
| `orphans` | Find blobs not referenced in Cosmos |
| `missing` | Find Cosmos records with missing blobs |

## Safety Features

All write operations support:

- `--dry-run` - Preview changes without executing
- `--backup` - Save records to file before modifying
- `--force` - Skip confirmation prompts (for scripting)
- `--json` - Output as JSON for programmatic use

## Environment Variables

```
AZURE_COSMOS_ENDPOINT              CosmosDB endpoint URL (required)
AZURE_COSMOS_KEY                   CosmosDB master key (required)
AZURE_COSMOS_DATABASE_NAME         Database name (default: quickscribe)
AZURE_COSMOS_CONTAINER_NAME        Container name (default: recordings)
AZURE_STORAGE_CONNECTION_STRING    Blob storage connection string (required)
AZURE_STORAGE_AUDIO_CONTAINER_NAME Blob container (default: recordings)
```

## Examples

```bash
# Discover what's in the database
uv run tools/azure_explorer.py cosmos discover

# Understand a data type
uv run tools/azure_explorer.py cosmos schema recording

# Query for specific records
uv run tools/azure_explorer.py cosmos query "SELECT c.id, c.title FROM c WHERE c.type = 'recording'" --limit 10

# Update a record (with preview)
uv run tools/azure_explorer.py cosmos update --id abc123 -p recording --set '{"title": "New Title"}' --dry-run

# List blobs for a user
uv run tools/azure_explorer.py blob list --prefix "user-xyz/"

# Generate a temporary download URL
uv run tools/azure_explorer.py blob url "user-xyz/recording.mp3" --hours 24

# Find orphaned blobs (cleanup candidates)
uv run tools/azure_explorer.py blob orphans --limit 100
```

## LLM Workflow

1. Run `cosmos discover` to see available entity types
2. Run `cosmos schema <type>` to understand the data structure
3. Run `cosmos sample <type>` to see real examples
4. Use `query`, `get`, `update` etc. for specific operations
5. Use `blob orphans` / `blob missing` to audit storage consistency

## How It Works

This script uses [PEP 723](https://peps.python.org/pep-0723/) inline script metadata to declare its dependencies. When you run it with `uv run`, uv automatically:

1. Creates a cached virtual environment
2. Installs the required packages (typer, rich, azure-cosmos, azure-storage-blob)
3. Runs the script

No manual setup required!
