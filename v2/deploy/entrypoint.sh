#!/bin/bash
set -e

DB_PATH="${DATABASE_PATH:-/app/data/app.db}"

# If Azure storage credentials are not set, skip Litestream and run app directly.
# This allows local dev / Docker without Azure credentials.
if [ -z "$AZURE_STORAGE_ACCOUNT" ] || [ -z "$AZURE_STORAGE_KEY" ]; then
    echo "AZURE_STORAGE_ACCOUNT or AZURE_STORAGE_KEY not set — running without Litestream"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

echo "Restoring database from Azure Blob Storage..."
litestream restore -if-replica-exists -config /app/litestream.yml "$DB_PATH"

echo "Starting Litestream replication with app..."
exec litestream replicate -config /app/litestream.yml -exec "uvicorn app.main:app --host 0.0.0.0 --port 8000"
