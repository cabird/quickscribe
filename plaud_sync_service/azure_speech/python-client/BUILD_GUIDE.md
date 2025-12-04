# Build and Installation Guide

## Package Naming

- **Package name** (for pip install): `azure-speech-client`
- **Module name** (for Python import): `azure_speech_client`

Example:
```bash
pip install azure-speech-client  # Install the package
```
```python
import azure_speech_client  # Import in Python code
```

---

## Quick Start - Use Pre-built Package

The package is already built! Just install the wheel:

```bash
pip install dist/azure_speech_client-3.2.0-py3-none-any.whl
```

---

## Building from Source

### Prerequisites
```bash
# Make sure you have build tools installed
pip install build
```

### Build the Package
```bash
# From the python-client directory
python -m build
```

This creates two files in `dist/`:
- `azure_speech_client-3.2.0-py3-none-any.whl` - **Wheel package** (recommended)
- `azure_speech_client-3.2.0.tar.gz` - Source distribution

---

## Installation Methods

### Method 1: Install Pre-built Wheel (Recommended)
```bash
pip install dist/azure_speech_client-3.2.0-py3-none-any.whl
```

### Method 2: Install from Source Distribution
```bash
pip install dist/azure_speech_client-3.2.0.tar.gz
```

### Method 3: Editable Install (for Development)
```bash
# From the python-client directory
pip install -e .
```

This installs the package in "editable" mode - changes to the code are immediately available without reinstalling.

### Method 4: Install from Parent Project
The package is already configured in the parent `plaud_sync_service/requirements.txt`:
```bash
# From plaud_sync_service directory
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Verification

After installation, verify it works:

```bash
# Check package info
pip show azure-speech-client

# Test import
python -c "import swagger_client; print('Success!')"
```

---

## Distribution

### Share the Wheel File
The `.whl` file is standalone and can be:
- Copied to other systems
- Stored in a private package repository
- Installed directly: `pip install /path/to/azure_speech_client-3.2.0-py3-none-any.whl`

### Upload to Private PyPI (Optional)
If you have a private PyPI server:
```bash
pip install twine
twine upload --repository-url https://your-pypi-server.com dist/*
```

### Upload to Public PyPI (Not Recommended)
Only if you want to make this public:
```bash
pip install twine
twine upload dist/*
```

---

## Rebuilding After Changes

If you modify the code or metadata:

1. **Clean old builds** (optional but recommended):
   ```bash
   rm -rf dist/ build/ *.egg-info/
   ```

2. **Update version** in `pyproject.toml` if needed:
   ```toml
   version = "3.2.1"  # Increment as needed
   ```

3. **Rebuild**:
   ```bash
   python -m build
   ```

4. **Reinstall**:
   ```bash
   pip install --force-reinstall dist/azure_speech_client-*.whl
   ```

---

## Using in Other Projects

### requirements.txt
```txt
# Option 1: From local path
/path/to/quickscribe/plaud_sync_service/azure_speech/python-client/dist/azure_speech_client-3.2.0-py3-none-any.whl

# Option 2: Editable install
-e /path/to/quickscribe/plaud_sync_service/azure_speech/python-client

# Option 3: If uploaded to PyPI
azure-speech-client==3.2.0
```

### setup.py or pyproject.toml
```toml
dependencies = [
    "azure-speech-client==3.2.0",
]
```

---

## Package Contents

The wheel includes:
- `swagger_client/` - Main module with API client code
- `swagger_client/api/` - API endpoint classes
- `swagger_client/models/` - Data models
- `docs/` - API documentation markdown files
- `LICENSE` - MIT license
- `README.md` - Package documentation

---

## Troubleshooting

### "No module named build"
```bash
pip install build
```

### "externally-managed-environment" error
Use a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install build
```

### Import fails but package installed
Remember: package name is `azure-speech-client`, and import name is `azure_speech_client`:
```python
import azure_speech_client  # ✓ Correct
import azure_speech_client as asc  # ✓ Also fine
```
