# Dockerfile for QuickScribe Processing Service
# Plaud sync + Speaker identification (ECAPA-TDNN)
FROM mwader/static-ffmpeg:7.1 AS ffmpeg

# Main Python image
FROM python:3.11-slim

# Install system deps for torchaudio/soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy static ffmpeg binaries
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

WORKDIR /app

# Copy shared library first
COPY shared_quickscribe_py /tmp/shared_quickscribe_py
RUN pip install --no-cache-dir -e /tmp/shared_quickscribe_py

# Copy and install Azure Speech Services swagger client
COPY plaud_sync_service/azure_speech/python-client /tmp/azure_speech_client
RUN pip install --no-cache-dir -e /tmp/azure_speech_client

# Install CPU-only torch + torchaudio first (big layer, cache separately)
RUN pip install --no-cache-dir \
    torch torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Install speechbrain
RUN pip install --no-cache-dir speechbrain>=1.0.0

# Copy requirements and install remaining deps
COPY plaud_sync_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ECAPA-TDNN model during build (bake into image)
RUN python -c "\
from speechbrain.inference.speaker import EncoderClassifier; \
EncoderClassifier.from_hparams( \
    source='speechbrain/spkrec-ecapa-voxceleb', \
    savedir='/app/pretrained_models/spkrec-ecapa-voxceleb', \
    run_opts={'device': 'cpu'} \
)"

# Copy application source files
COPY plaud_sync_service/src/ /app/

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
