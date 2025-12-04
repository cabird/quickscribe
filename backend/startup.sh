#!/bin/bash
set -e

echo "Starting QuickScribe container..."

echo "Current working directory: $(pwd)"
echo "Contents of current directory:"
ls -la

# Install local packages if present
if [ -d "local_packages" ] && ls local_packages/*.whl 1> /dev/null 2>&1; then
    pip install local_packages/*.whl
else
    echo "No .whl files found in local_packages"
fi

# Select and copy the appropriate environment file to .env
if [ -z "$WEBSITE_INSTANCE_ID" ]; then
    echo "Running in LOCAL mode - copying .env.local to .env"
    cp .env.local src/.env
    PORT=${PORT:-8000}
    echo "Using port: $PORT"
    export FLASK_APP=app.py
    export FLASK_DEBUG=1
    export FLASK_ENV=development
    cd src && python -m flask run --host=0.0.0.0 --port=$PORT --debug --reload
else
    echo "Running in AZURE mode - copying .env.azure to .env"
    echo "WEBSITE_INSTANCE_ID: $WEBSITE_INSTANCE_ID"
    cp .env.azure src/.env
    PORT=${PORT:-8000}
    echo "Using port: $PORT"
    cd src && gunicorn --bind=0.0.0.0:$PORT --timeout 600 app:app
fi
