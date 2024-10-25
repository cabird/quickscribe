#!/bin/bash

echo "Installing dependencies"

# Install ffmpeg
apt-get update && apt-get install -y ffmpeg

# Install Python dependencies
pip install -r requirements.txt

if [ -d "local_packages" ] && ls local_packages/*.whl 1> /dev/null 2>&1; then
    pip install local_packages/*.whl
else
    echo "No .whl files found in local_packages"
fi

echo "Starting the Flask app"
gunicorn --bind=0.0.0.0 --timeout 600 app:app
