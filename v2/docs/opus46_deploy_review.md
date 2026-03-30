# QuickScribe v2 Deployment Infrastructure Review

**Reviewer**: Claude Opus 4.6
**Date**: 2026-03-24
**Files reviewed**: All files in `v2/deploy/` (Dockerfile, entrypoint.sh, litestream.yml, .dockerignore, bicep/main.bicep, scripts/*)
**Reference**: `~/repos/guides/deploying-sqlite-to-azure.md`, `v2/docs/REWRITE_SPEC.md`

---

## Summary

The deployment infrastructure is well-structured and closely follows the proven Litestream deployment guide. The scripts are clean, have proper error handling, and support WSL. There are a handful of issues ranging from a build-breaking Dockerfile problem to minor robustness improvements.

**Severity levels**: CRITICAL (will break), HIGH (will cause problems in production), MEDIUM (should fix before deploying), LOW (nice-to-have).

---

## 1. Dockerfile

**File**: `v2/deploy/Dockerfile`

### CRITICAL: PyTorch/SpeechBrain not installed

The spec (line 109, 628-648) explicitly requires ECAPA-TDNN speaker identification via PyTorch and SpeechBrain, running in the same container. The Dockerfile installs `ffmpeg` and `libsndfile1` (good), but there is no PyTorch CPU-only install step.

PyTorch CPU-only is ~800MB and requires a custom index URL. The builder stage (lines 9-15) just runs `uv sync` from `pyproject.toml`, which would need PyTorch listed there with the CPU-only index. If `pyproject.toml` has PyTorch with the default (CUDA) index, the image will be ~3GB larger than necessary and include unused CUDA libraries.

**Fix**: Either ensure `pyproject.toml` uses `--index-url https://download.pytorch.org/whl/cpu` for torch (via uv's index configuration), or add an explicit install step:

```dockerfile
RUN uv pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Verify by checking `v2/backend/pyproject.toml` for torch/speechbrain/torchaudio entries and their index configuration.

### HIGH: `uv sync` may not produce a portable venv

Line 10-11: `uv sync --frozen --no-dev --no-install-project` installs dependencies, then line 15 installs the project. However, the `COPY --from=builder /app/.venv /app/.venv` on line 49 copies the venv to the runtime stage. The venv's Python paths are baked in as `/app/.venv`, which matches the runtime layout, so this should work. But `uv sync` creates a venv with the builder stage's Python, so the builder and runtime stages **must** use the same Python base image (`python:3.12-slim`). Currently they do (lines 2 and 39) -- this is correct but fragile. Consider adding a comment.

### MEDIUM: Missing `uv.lock` will silently fall back to unlocked install

Lines 10-11 use a fallback pattern:
```dockerfile
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || \
    uv sync --no-dev --no-install-project
```

The `2>/dev/null` suppresses the error from `--frozen` failing (no lock file), then falls back to an unlocked sync. This means builds are **not reproducible** when the lock file is missing -- different builds could get different dependency versions. The fallback should at minimum print a warning.

### MEDIUM: Frontend COPY path assumes `package-lock.json` exists

Line 22: `COPY frontend/package-lock.json* ./` uses a glob so it won't fail if the lockfile is missing. But `npm install` without a lockfile is non-deterministic. The frontend directory does have a `package-lock.json`, so this works today, but the glob weakens the guarantee.

### LOW: Health check endpoint path

Line 79: `http://localhost:8000/api/health`. The Bicep template (line 93) uses `healthCheckPath: '/api/health'`. These match, which is good. Just ensure the FastAPI app actually exposes this exact path.

### LOW: No `.dockerignore` coverage for `config.local.sh`

The `.dockerignore` excludes `deploy/scripts/` and `deploy/bicep/` (good), but `config.local.sh` could contain secrets. Since it lives in `deploy/scripts/`, it's already excluded. This is fine.

### LOW: Consider pinning uv version

Line 4: `COPY --from=ghcr.io/astral-sh/uv:latest` uses `latest`. For reproducible builds, pin to a specific version (e.g., `ghcr.io/astral-sh/uv:0.6.x`).

---

## 2. Litestream Configuration

**File**: `v2/deploy/litestream.yml`

### Status: Correct

The config exactly matches the guide's template (guide lines 139-149):
- `type: abs` for Azure Blob Storage
- Environment variable substitution for credentials (`${AZURE_STORAGE_ACCOUNT}`, etc.)
- `sync-interval: 1s` (guide default)
- `snapshot-interval: 24h` (guide default)
- `path: app.db` matches `DB_BLOB_NAME` in config.sh

No issues found.

---

## 3. Entrypoint Script

**File**: `v2/deploy/entrypoint.sh`

### Status: Correct, follows guide closely

The script correctly implements the guide's three-step pattern (guide lines 154-163):
1. Check for Azure credentials, skip Litestream if missing (line 8-11)
2. `litestream restore -if-replica-exists` (line 14) -- handles first deploy with no backup
3. `exec litestream replicate ... -exec "uvicorn ..."` (line 17)

### MEDIUM: App module path may be wrong

Lines 10 and 17: `uvicorn app.main:app`. This assumes the FastAPI app object is at `backend/src/app/main.py` and the working directory is `/app` with `src/` containing an `app/` package. The Dockerfile copies `backend/src/` to `/app/src/` (line 58), so the actual module path would be `src.app.main:app` or the working directory needs to be `/app/src`.

Verify: what is the actual module structure inside `backend/src/`? If it's `backend/src/app/main.py`, then `WORKDIR /app` + `PYTHONPATH` would need `/app/src` or the uvicorn command should be `src.app.main:app`. This could prevent the container from starting.

### LOW: No `--workers` flag for uvicorn

The spec mentions lazy-loading PyTorch (spec line 648) and running embedding extraction in a thread pool (spec line 649). A single uvicorn worker is fine for a personal app, but worth noting that `--workers 1` is implicit.

---

## 4. Bicep Template

**File**: `v2/deploy/bicep/main.bicep`

### Status: Mostly correct, follows guide well

The template deploys all four resources (App Service Plan, ACR, Storage Account, Web App) with correct configuration.

### Correct items:
- `reserved: true` on App Service Plan (line 40) -- required for Linux, per guide gotcha #4
- `adminUserEnabled: true` on ACR (line 55) -- per guide gotcha #5
- `allowBlobPublicAccess: false` on Storage Account (line 68) -- security best practice
- `minimumTlsVersion: 'TLS1_2'` (line 69)
- `WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'` (line 99) -- per guide gotcha #2
- `linuxFxVersion`, `alwaysOn`, `healthCheckPath` correctly placed in `siteConfig` (not in `appSettings`)
- All credential wiring via `acr.listCredentials()` and `storageAccount.listKeys()`
- Blob container resource created with correct parent chain

### MEDIUM: B3 SKU is expensive for a personal app

Line 27: `param appSku string = 'B3'`. B3 is ~$52/month. The guide recommends B2 (~$26) as default and B1 (~$13) for low-traffic. The spec mentions PyTorch/SpeechBrain which needs more RAM, justifying B3 (7GB RAM vs B2's 3.5GB). However:

- PyTorch CPU-only + SpeechBrain + ECAPA-TDNN model loading peaks at ~1.5-2GB RAM
- The spec says "lazy-load PyTorch on first speaker ID request" (line 648), so the baseline is lower
- B2 (3.5GB) would likely work. B3 gives headroom.

**Recommendation**: Keep B3 as default but add a comment explaining why (PyTorch memory requirement). Consider B2 if cost is a concern and test whether speaker ID fits in 3.5GB.

### LOW: Missing `DOCKER_ENABLE_CI` app setting

For automatic image pull on ACR push (continuous deployment), add:
```bicep
{ name: 'DOCKER_ENABLE_CI', value: 'true' }
```
Without this, you must manually restart the app after pushing a new image (which `03-deploy-app.sh` does, so it works -- but CI/CD would be smoother with this setting).

### LOW: No instance count constraint

The guide warns (line 17) that Litestream is single-instance only. The Bicep doesn't set `numberOfWorkers: 1` or disable autoscaling. App Service defaults to 1 instance, but an accidental scale-out would corrupt the database. Consider:
```bicep
properties: {
  reserved: true
  numberOfWorkers: 1
}
```

---

## 5. Deployment Scripts

### config.sh

**File**: `v2/deploy/scripts/config.sh`

**Status: Excellent.** Clean implementation with all helper functions from the guide (`print_config`, `check_azure_login`, `is_wsl`, `az_path`). Local override support via `config.local.sh`. All variables use proper bash parameter expansion defaults.

### 01-create-resources.sh

**File**: `v2/deploy/scripts/01-create-resources.sh`

**Status: Correct.** Uses `az_path` for WSL compatibility (line 23). Passes all parameters to Bicep.

### 02-build-push.sh

**File**: `v2/deploy/scripts/02-build-push.sh`

**Status: Correct.** Tags with both `latest` and git SHA (good for rollback). Uses `PROJECT_ROOT` as Docker context.

### MEDIUM: Docker build context is `v2/` directory

Line 27: `"$PROJECT_ROOT"` which resolves to the `v2/` directory. The Dockerfile `COPY` commands reference `backend/`, `frontend/`, `deploy/` -- all relative to `v2/`. This is correct given the project structure. The `.dockerignore` is in `deploy/` but Docker expects it in the context root (`v2/`).

**Bug**: The `.dockerignore` file is at `v2/deploy/.dockerignore`, but Docker reads `.dockerignore` from the **build context root** (`v2/`), not from the Dockerfile's directory. The `-f` flag only sets the Dockerfile location, not the `.dockerignore` location. So the `.dockerignore` is **not being applied**.

**Fix**: Move `.dockerignore` from `v2/deploy/` to `v2/` (the project root / build context root). Or use Docker BuildKit's `--build-context` feature.

### 03-deploy-app.sh

**File**: `v2/deploy/scripts/03-deploy-app.sh`

**Status: Correct.** Health polling with 30 attempts at 10s intervals (5 minutes total). Uses curl with proper error suppression.

### set-secrets.sh

**File**: `v2/deploy/scripts/set-secrets.sh`

**Status: Correct and well-designed.** Only sets non-empty variables, loads from `.env`, uses `set -a` / `set +a` for export.

### MEDIUM: `AZURE_STORAGE_CONNECTION_STRING` may conflict

Line 34 sets `AZURE_STORAGE_CONNECTION_STRING` as an app secret. This is for audio blob storage (different from the Litestream storage account, which uses `AZURE_STORAGE_ACCOUNT` + `AZURE_STORAGE_KEY` set by Bicep). The spec says "storage account shared with Litestream" (spec line 107), so the audio blob storage and Litestream storage may share an account. If so, the connection string in `set-secrets.sh` is redundant with the key already set by Bicep. If not, it's correct. Clarify which storage account serves which purpose.

### upload-db.sh and download-db.sh

**Files**: `v2/deploy/scripts/upload-db.sh`, `v2/deploy/scripts/download-db.sh`

**Status: Good.** Auto-install Litestream pattern matches the guide. Temp config with `trap` cleanup. Upload uses background replicate with 15s timeout.

### LOW: Duplicated `install_litestream` function

The function is copy-pasted between `upload-db.sh` (lines 19-47) and `download-db.sh` (lines 13-34). Consider extracting to a shared function in `config.sh`.

### LOW: `download-db.sh` restore command has redundant path

Line 69: `litestream restore -config "$TEMP_CONFIG" -o "$OUTPUT_PATH" "$OUTPUT_PATH"`. The `-o` flag sets the output path, and the positional argument is the DB path from the config to restore. Since the temp config's `path` is already `$OUTPUT_PATH`, the positional arg should match. This works but is confusing -- the positional arg identifies which DB in the config to restore, and `-o` overrides the output location.

### teardown.sh

**File**: `v2/deploy/scripts/teardown.sh`

**Status: Correct.** Confirmation by typing resource group name. Uses `--no-wait` for async deletion.

---

## 6. Security

### Good:
- Non-root user `appuser` in Dockerfile (lines 66-70)
- `allowBlobPublicAccess: false` on storage account
- `httpsOnly: true` on web app
- TLS 1.2 minimum
- `.dockerignore` excludes `.env` (though see the .dockerignore bug above)
- Secrets set separately via `set-secrets.sh`, not baked into Bicep parameters
- Storage keys and ACR credentials wired via Bicep resource references (not hardcoded)

### MEDIUM: ACR admin credentials in app settings

Bicep lines 97-98 inject ACR admin username and password as app settings. These are visible in the Azure Portal and in `az webapp config appsettings list` output. This is the standard approach (guide line 121 notes this), but managed identity would be more secure. Fine for a personal app.

### LOW: Storage account key in app settings

Same pattern -- `AZURE_STORAGE_KEY` is visible in app settings. Again, standard for this architecture.

---

## 7. Comparison to Guide

| Guide requirement | Implementation | Status |
|---|---|---|
| 3-stage Dockerfile (builder, litestream, runtime) | 4-stage (added frontend builder) | Correct adaptation |
| Litestream binary from GitHub releases | Yes, pinned to 0.3.13 | Correct |
| Non-root `appuser` | Yes | Correct |
| `/app/data/` owned by appuser | Yes (`chown -R appuser:appuser /app`) | Correct |
| Health check via Python urllib | Yes | Correct |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false` | Yes | Correct |
| `reserved: true` on App Service Plan | Yes | Correct |
| `adminUserEnabled: true` on ACR | Yes | Correct |
| `alwaysOn: true` | Yes | Correct |
| `-if-replica-exists` on restore | Yes | Correct |
| Skip Litestream without credentials | Yes | Correct |
| `exec` for both direct run and Litestream | Yes | Correct |
| WSL path conversion | Yes (`az_path` helper) | Correct |
| Git SHA tagging | Yes | Correct |
| Health polling in deploy script | Yes, 30x10s | Correct |
| Temp config + trap cleanup in upload/download | Yes | Correct |
| Litestream auto-install in scripts | Yes | Correct |
| `.dockerignore` placement | Wrong directory | **Bug** |

---

## 8. Priority Summary

| # | Severity | Issue | File | Lines |
|---|----------|-------|------|-------|
| 1 | CRITICAL | PyTorch/SpeechBrain not installed in Dockerfile | Dockerfile | 9-15 |
| 2 | HIGH | `.dockerignore` in wrong directory (not applied) | deploy/.dockerignore | all |
| 3 | MEDIUM | `uv sync` fallback hides missing lock file | Dockerfile | 10-11 |
| 4 | MEDIUM | Uvicorn module path may not match source layout | entrypoint.sh | 10, 17 |
| 5 | MEDIUM | B3 SKU expensive; needs justification comment | bicep/main.bicep | 27 |
| 6 | MEDIUM | Storage account overlap between audio and Litestream unclear | scripts/set-secrets.sh | 34 |
| 7 | LOW | `uv` version not pinned | Dockerfile | 4 |
| 8 | LOW | No `numberOfWorkers: 1` in Bicep to prevent scale-out | bicep/main.bicep | 35-45 |
| 9 | LOW | Duplicated `install_litestream` function | upload-db.sh, download-db.sh | 19-47, 13-34 |
| 10 | LOW | No `DOCKER_ENABLE_CI` for auto-deploy on push | bicep/main.bicep | 94-104 |

---

## 9. Overall Assessment

The deployment infrastructure is **solid and well-implemented**. It follows the Litestream guide faithfully, with appropriate adaptations for QuickScribe's needs (4-stage build for frontend, PyTorch system deps). The scripts are clean, handle WSL correctly, and have proper error handling.

The two items that need immediate attention before deployment:
1. **PyTorch installation** -- the container won't perform speaker identification without it
2. **`.dockerignore` location** -- the file isn't being applied, meaning `.git`, `tests/`, `docs/`, etc. are all being sent to the Docker daemon (slow builds, larger layer cache)

Everything else is either a robustness improvement or a minor optimization.
