#!/bin/bash
# Download (restore) the database from Azure Blob Storage via Litestream.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

OUTPUT_PATH="${1:-$PROJECT_ROOT/data/app-downloaded.db}"

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
TEMP_CONFIG=$(mktemp /tmp/litestream-download-XXXXXX.yml)
trap "rm -f $TEMP_CONFIG" EXIT

cat > "$TEMP_CONFIG" <<EOF
dbs:
  - path: $OUTPUT_PATH
    replicas:
      - type: abs
        account-name: $STORAGE_ACCOUNT
        account-key: $STORAGE_KEY
        bucket: $BLOB_CONTAINER
        path: $DB_BLOB_NAME
EOF

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_PATH")"

echo "Restoring database from Azure Blob Storage..."
echo "  Source: $STORAGE_ACCOUNT/$BLOB_CONTAINER/$DB_BLOB_NAME"
echo "  Output: $OUTPUT_PATH"
echo ""

litestream restore -config "$TEMP_CONFIG" -o "$OUTPUT_PATH" "$OUTPUT_PATH"

if [ -f "$OUTPUT_PATH" ]; then
    SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
    echo "Download complete: $OUTPUT_PATH ($SIZE)"
else
    echo "ERROR: Restore failed — no file at $OUTPUT_PATH"
    exit 1
fi
