# Dockerfile for Speaker Identification Service
# Uses ECAPA-TDNN model for voice embedding extraction

FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Copy shared library first
COPY shared_quickscribe_py /tmp/shared_quickscribe_py

# Install shared_quickscribe_py library
RUN pip install --no-cache-dir -e /tmp/shared_quickscribe_py

# Copy requirements first for better layer caching
COPY speaker_id_service/requirements.txt /app/requirements.txt
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
COPY speaker_id_service/src/ /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the speaker identification service
CMD ["python", "main.py"]
