#!/bin/bash
set -e

echo "Starting QuickScribe container..."

echo "Current working directory: $(pwd)"
echo "Contents of current directory:"
ls -la
# Python dependencies are already installed in the Dockerfile
# This is just in case we're running in a development environment
echo "Ensuring Python dependencies are installed..."

if [ -d "local_packages" ] && ls local_packages/*.whl 1> /dev/null 2>&1; then
    pip install local_packages/*.whl
else
    echo "No .whl files found in local_packages"
fi

if [ "$ENVIRONMENT" = "local" ]; then
    echo "Starting the Flask app on port"
    cp -r /app/.env.local /app/.env
    PORT=${PORT:-8000}
    echo "Using port: $PORT"
    export FLASK_APP=app.py
    export FLASK_DEBUG=1
    export FLASK_ENV=development
    python -m flask run --host=0.0.0.0 --port=$PORT --debug --reload
else
    echo "Starting the Flask app"
    # Use the PORT environment variable if set (for Azure), otherwise default to 8000
    PORT=${PORT:-8000}
    echo "Using port: $PORT"
    gunicorn --bind=0.0.0.0:$PORT --timeout 600 app:app
fi
