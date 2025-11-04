# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.11-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy function app files
COPY . /home/site/wwwroot

# Install shared_quickscribe_py library
WORKDIR /home/site/wwwroot
RUN if [ -d "../shared_quickscribe_py" ]; then \
        pip install -e ../shared_quickscribe_py; \
    else \
        echo "Warning: shared_quickscribe_py not found, will need to be installed separately"; \
    fi

# Install Python dependencies
RUN pip install --no-cache-dir -r /home/site/wwwroot/requirements.txt

WORKDIR /home/site/wwwroot
