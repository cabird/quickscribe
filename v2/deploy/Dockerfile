# App image. Builds FROM the deps base image (Dockerfile.deps), which holds the
# OS packages and the full Python venv including PyTorch. 02-build-push.sh
# computes DEPS_IMAGE from a hash of Dockerfile.deps + pyproject.toml + uv.lock
# and builds it first only if that tag is missing, so a normal deploy only
# builds and ships the thin layers below.
ARG DEPS_IMAGE


# Stage 1: Frontend builder
FROM node:22.14-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
# MSAL settings are baked into the bundle at build time. Pass them as build
# args (see 02-build-push.sh) rather than relying on an untracked .env file.
ARG VITE_AUTH_ENABLED
ARG VITE_AZURE_CLIENT_ID
ARG VITE_AZURE_TENANT_ID
# Stamped into the bundle so a stale window can tell it's out of date
ARG VITE_APP_VERSION
ENV VITE_AUTH_ENABLED=$VITE_AUTH_ENABLED \
    VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID \
    VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID \
    VITE_APP_VERSION=$VITE_APP_VERSION
# Without it the bundle reports "dev" and the update banner never shows
RUN test -n "$VITE_APP_VERSION" || (echo "VITE_APP_VERSION build arg is required" && exit 1)
RUN npm run build


# Stage 2: Runtime
FROM ${DEPS_IMAGE} AS runtime

WORKDIR /app

# Copy frontend build
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist /app/frontend-dist/

# Copy backend source
COPY --chown=appuser:appuser backend/src/ /app/src/

# Copy deploy config files
COPY --chown=appuser:appuser deploy/litestream.yml /app/litestream.yml
# entrypoint.sh is committed with mode 755 (classic builder has no --chmod)
COPY --chown=appuser:appuser deploy/entrypoint.sh /app/entrypoint.sh

# Copy VERSION file last (changes on every deploy)
COPY --chown=appuser:appuser backend/VERSION /app/VERSION

USER appuser

# Environment (PATH to the venv is set in the deps image)
ENV PYTHONPATH="/app/src"
ENV DATABASE_PATH=/app/data/app.db
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
