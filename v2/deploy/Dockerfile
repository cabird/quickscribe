# Stage 1: Python dependencies (cached unless uv.lock changes)
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /usr/local/bin/uv

WORKDIR /app

# Copy ONLY dependency files — this layer rebuilds only when deps change
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# Stage 2: App source (thin layer, changes every deploy)
FROM deps AS builder

COPY backend/src/ ./src/
RUN uv sync --frozen --no-dev


# Stage 3: Frontend builder
FROM node:22.14-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build


# Stage 4: Litestream binary
FROM debian:bookworm-slim AS litestream

ARG LITESTREAM_VERSION=0.3.13
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates && \
    wget -q "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-v${LITESTREAM_VERSION}-linux-amd64.tar.gz" -O /tmp/litestream.tar.gz && \
    tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin && \
    rm /tmp/litestream.tar.gz


# Stage 5: Runtime
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

# Copy VERSION file (small, changes on version bump without busting deps cache)
COPY backend/VERSION /app/VERSION

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
