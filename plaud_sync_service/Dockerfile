# Dockerfile for QuickScribe Processing Service
# Plaud sync + Speaker identification (ECAPA-TDNN)
FROM mwader/static-ffmpeg:7.1 AS ffmpeg

FROM python:3.11-slim

# --- Layer 1: System deps (rarely changes) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

WORKDIR /app

# --- Layer 2: CPU-only torch + torchaudio (~800MB, never changes) ---
RUN pip install --no-cache-dir \
    torch==2.4.1+cpu torchaudio==2.4.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# --- Layer 3: speechbrain + deps (~200MB, rarely changes) ---
RUN pip install --no-cache-dir soundfile huggingface_hub==0.24.7 speechbrain==1.0.3

# --- Layer 4: ECAPA-TDNN model weights (~100MB, never changes) ---
RUN python -c "\
from speechbrain.inference.speaker import EncoderClassifier; \
EncoderClassifier.from_hparams( \
    source='speechbrain/spkrec-ecapa-voxceleb', \
    savedir='/app/pretrained_models/spkrec-ecapa-voxceleb', \
    run_opts={'device': 'cpu'} \
)"

# --- Layer 5: App requirements (changes occasionally) ---
COPY plaud_sync_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- Layer 6: Shared library (changes occasionally) ---
COPY shared_quickscribe_py /tmp/shared_quickscribe_py
RUN pip install --no-cache-dir -e /tmp/shared_quickscribe_py

# --- Layer 7: Azure Speech client (rarely changes) ---
COPY plaud_sync_service/azure_speech/python-client /tmp/azure_speech_client
RUN pip install --no-cache-dir -e /tmp/azure_speech_client

# --- Layer 8: Application source (changes most often) ---
COPY plaud_sync_service/src/ /app/

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
