#!/bin/bash
# Upload a local SQLite database to Azure Blob Storage via Litestream.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

LOCAL_DB="${1:-$PROJECT_ROOT/data/app.db}"

if [ ! -f "$LOCAL_DB" ]; then
    echo "ERROR: Database file not found: $LOCAL_DB"
    echo "Usage: $0 [path-to-local-db]"
    exit 1
fi

check_azure_login

# --- Auto-install Litestream if needed ---
install_litestream() {
    local VERSION="0.3.13"
    local OS ARCH
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    case "$ARCH" in
        x86_64)  ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
    esac

    # macOS = darwin, Linux = linux
    case "$OS" in
        darwin) ;;
        linux)  ;;
        *)      echo "ERROR: Unsupported OS: $OS"; exit 1 ;;
    esac

    local URL="https://github.com/benbjohnson/litestream/releases/download/v${VERSION}/litestream-v${VERSION}-${OS}-${ARCH}.tar.gz"
    local INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"

    echo "Installing Litestream v${VERSION} to $INSTALL_DIR..."
    wget -q "$URL" -O /tmp/litestream.tar.gz
    tar -xzf /tmp/litestream.tar.gz -C "$INSTALL_DIR"
    rm /tmp/litestream.tar.gz
    export PATH="$INSTALL_DIR:$PATH"
    echo "Litestream installed."
}

if ! command -v litestream &>/dev/null; then
    install_litestream
fi

# --- Get storage key ---
STORAGE_KEY=$(az storage account keys list \
    --account-name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[0].value" -o tsv)

# --- Create temp Litestream config ---
TEMP_CONFIG=$(mktemp /tmp/litestream-upload-XXXXXX.yml)
trap "rm -f $TEMP_CONFIG" EXIT

cat > "$TEMP_CONFIG" <<EOF
dbs:
  - path: $LOCAL_DB
    replicas:
      - type: abs
        account-name: $STORAGE_ACCOUNT
        account-key: $STORAGE_KEY
        bucket: $BLOB_CONTAINER
        path: $DB_BLOB_NAME
        sync-interval: 1s
        snapshot-interval: 1h
EOF

echo "Uploading database: $LOCAL_DB"
echo "  -> $STORAGE_ACCOUNT/$BLOB_CONTAINER/$DB_BLOB_NAME"
echo ""

# Run Litestream replicate in background with timeout
litestream replicate -config "$TEMP_CONFIG" &
LITESTREAM_PID=$!

# Wait for initial sync (15 seconds is enough for snapshot + WAL)
echo "Waiting 15s for initial replication..."
sleep 15
kill $LITESTREAM_PID 2>/dev/null || true
wait $LITESTREAM_PID 2>/dev/null || true

# Verify blobs exist
echo ""
echo "Verifying blobs in storage..."
BLOB_COUNT=$(az storage blob list \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --container-name "$BLOB_CONTAINER" \
    --query "length(@)" -o tsv)

if [ "$BLOB_COUNT" -gt 0 ]; then
    echo "Upload successful — $BLOB_COUNT blob(s) in container."
    az storage blob list \
        --account-name "$STORAGE_ACCOUNT" \
        --account-key "$STORAGE_KEY" \
        --container-name "$BLOB_CONTAINER" \
        -o table
else
    echo "WARNING: No blobs found. Upload may have failed."
    exit 1
fi

echo ""
read -p "Restart the web app to pick up the new database? [y/N] " RESTART
if [[ "$RESTART" =~ ^[Yy]$ ]]; then
    az webapp restart --name "$APP_NAME" --resource-group "$RESOURCE_GROUP"
    echo "Web app restarted."
fi
