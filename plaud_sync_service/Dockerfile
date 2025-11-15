# Dockerfile for Azure Container Apps Jobs
# Use static ffmpeg binaries (no external dependencies)
FROM mwader/static-ffmpeg:7.1 AS ffmpeg

# Main Python image
FROM python:3.11-slim

# Copy static ffmpeg binaries (completely self-contained, no libs needed)
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

# Create app directory
WORKDIR /app

# Copy shared library first
COPY shared_quickscribe_py /tmp/shared_quickscribe_py

# Install shared_quickscribe_py library
RUN pip install --no-cache-dir -e /tmp/shared_quickscribe_py

# Copy and install Azure Speech Services swagger client
COPY plaud_sync_service/azure_speech/python-client /tmp/azure_speech_client
RUN pip install --no-cache-dir -e /tmp/azure_speech_client

# Copy requirements first for better layer caching
COPY plaud_sync_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source files
COPY plaud_sync_service/src/ /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the sync service
CMD ["python", "main.py"]
