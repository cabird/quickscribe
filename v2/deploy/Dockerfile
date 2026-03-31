# Stage 1a: Install PyTorch/SpeechBrain (heavy, rarely changes)
# This layer is ~1.8GB but only rebuilds when speaker-id versions change.
FROM python:3.12-slim AS speaker-id-deps

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /usr/local/bin/uv

WORKDIR /app

# Install ONLY speaker-id deps into a separate venv.
# Pinned versions ensure this layer is cached across deploys.
RUN uv venv /app/.speaker-id-venv && \
    VIRTUAL_ENV=/app/.speaker-id-venv uv pip install \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1 torchaudio==2.4.1 && \
    VIRTUAL_ENV=/app/.speaker-id-venv uv pip install \
        speechbrain==1.0.3 huggingface_hub==0.24.7 soundfile==0.12.1


# Stage 1b: Install app dependencies (light, changes with pyproject.toml)
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /usr/local/bin/uv

WORKDIR /app

# Install app dependencies first (cache-friendly)
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || \
    uv sync --no-dev --no-install-project

# Copy backend source and install project
COPY backend/src/ ./src/
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Merge speaker-id packages into the app venv
COPY --from=speaker-id-deps /app/.speaker-id-venv/lib /app/.venv/lib


# Stage 2: Frontend builder
FROM node:22.14-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build


# Stage 3: Litestream binary
FROM debian:bookworm-slim AS litestream

ARG LITESTREAM_VERSION=0.3.13
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates && \
    wget -q "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-v${LITESTREAM_VERSION}-linux-amd64.tar.gz" -O /tmp/litestream.tar.gz && \
    tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin && \
    rm /tmp/litestream.tar.gz


# Stage 4: Runtime
FROM python:3.12-slim AS runtime

# System deps: ffmpeg for audio, libsndfile1 for speaker-id/soundfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy Litestream binary
COPY --from=litestream /usr/local/bin/litestream /usr/local/bin/litestream

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist /app/frontend-dist/

# Copy backend source
COPY backend/src/ /app/src/

# Copy pyproject.toml for version info at runtime
COPY backend/pyproject.toml /app/pyproject.toml

# Copy deploy config files
COPY deploy/litestream.yml /app/litestream.yml
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create non-root user and data directory
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser

# Environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV DATABASE_PATH=/app/data/app.db
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
