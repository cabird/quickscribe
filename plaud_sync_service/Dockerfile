# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.11-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy shared library first
COPY shared_quickscribe_py /tmp/shared_quickscribe_py

# Install shared_quickscribe_py library
RUN pip install -e /tmp/shared_quickscribe_py

# Copy and install Azure Speech Services swagger client
COPY backend/azure_speech/python-client /tmp/azure_speech_client
RUN pip install -e /tmp/azure_speech_client

# Copy function app files
COPY plaud_sync_service /home/site/wwwroot

# Install Python dependencies
WORKDIR /home/site/wwwroot
RUN pip install --no-cache-dir -r requirements.txt
