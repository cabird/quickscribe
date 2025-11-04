# TypeScript-to-Python Type Sharing Pattern

This document describes a pattern for maintaining type consistency across a full-stack application by defining types once in TypeScript and automatically generating both Python Pydantic models and TypeScript types.

## Overview

**Single Source of Truth**: All data models are defined in TypeScript interfaces in a `shared/` directory.

**Automatic Generation**:
- Python Pydantic v2 models for backend validation and type safety
- TypeScript types for frontend type checking

**Benefits**:
- Define types once, use everywhere
- Compile-time type safety across the stack
- Automatic validation with Pydantic
- Reduced maintenance and sync issues

## Project Structure

```
my-project/
├── shared/
│   ├── Models.ts              # Source of truth for all types
│   ├── models.schema.json     # Generated JSON Schema (gitignore this)
│   └── README.md             # Optional: document your models
├── backend/
│   ├── Makefile              # Build automation
│   ├── requirements.txt      # Python dependencies
│   ├── venv/                 # Python virtual environment
│   └── db_handlers/
│       └── models.py         # Generated Pydantic models (gitignore this)
└── frontend/
    ├── package.json          # Includes sync-models script
    └── src/
        └── types/
            └── index.ts      # Generated TypeScript types (gitignore this)
```

## Prerequisites

### Backend Requirements

1. **Python 3.9+** with virtual environment
2. **Node.js and npm** (for TypeScript tooling)

### Required npm Packages (Global or Dev Dependencies)

```bash
# Install globally
npm install -g typescript-json-schema datamodel-code-generator

# OR add to backend dev dependencies
npm install --save-dev typescript-json-schema datamodel-code-generator
```

### Required Python Packages

Add to `backend/requirements.txt`:
```txt
pydantic>=2.0.0
```

## Setup Instructions

### Step 1: Create the Shared Models Directory

Create `shared/Models.ts` with your type definitions:

```typescript
// shared/Models.ts

// Basic example types
export interface User {
    id: string;
    email: string;
    name?: string;
    createdAt: string;  // ISO date string
    updatedAt: string;
}

export interface Recording {
    id: string;
    userId: string;
    title: string;
    description?: string;
    status: "pending" | "processing" | "completed" | "failed";
    createdAt: string;
    metadata?: RecordingMetadata;
}

export interface RecordingMetadata {
    duration?: number;
    fileSize?: number;
    format?: string;
}

// API Response types
export interface ApiResponse<T = any> {
    status: 'success' | 'error';
    data?: T;
    message?: string;
    error?: string;
}

export interface CreateRecordingRequest {
    title: string;
    description?: string;
}

export interface UpdateRecordingRequest {
    title?: string;
    description?: string;
    status?: "pending" | "processing" | "completed" | "failed";
}
```

**Important Notes for Models.ts**:
- Use `string` for dates (ISO 8601 format recommended)
- Use `number` for numeric types (can add `type integer = number;` for integers)
- Optional fields use `?` syntax: `fieldName?: type`
- Union types work: `status: "pending" | "processing"`
- Nested interfaces are supported
- Generics work for API responses

### Step 2: Backend Setup

#### Create `backend/Makefile`

```makefile
# backend/Makefile

SHARED_DIR = ../shared

# Default target
.PHONY: build
default: build

# Build Python models from TypeScript definitions
build: db_handlers/models.py

db_handlers/models.py: $(SHARED_DIR)/Models.ts
	@echo "Generating JSON Schema from TypeScript..."
	typescript-json-schema $(SHARED_DIR)/Models.ts "*" \
		--propOrder \
		--required \
		--out $(SHARED_DIR)/models.schema.json
	@echo "Generating Pydantic models from JSON Schema..."
	datamodel-codegen \
		--input $(SHARED_DIR)/models.schema.json \
		--input-file-type jsonschema \
		--output-model-type pydantic_v2.BaseModel \
		--use-subclass-enum \
		--output db_handlers/models.py
	@echo "✓ Python models generated successfully"

# Clean generated files
.PHONY: clean
clean:
	rm -f $(SHARED_DIR)/models.schema.json
	rm -f db_handlers/models.py
	@echo "✓ Cleaned generated files"

# Verify models are up to date
.PHONY: check
check:
	@if [ $(SHARED_DIR)/Models.ts -nt db_handlers/models.py ]; then \
		echo "ERROR: Models.ts has been modified. Run 'make build' to regenerate."; \
		exit 1; \
	fi
	@echo "✓ Models are up to date"
```

#### Create `backend/db_handlers/` directory

```bash
mkdir -p backend/db_handlers
touch backend/db_handlers/__init__.py
```

#### Add to `backend/.gitignore`

```gitignore
# Generated files - do not commit
db_handlers/models.py
../shared/models.schema.json
```

### Step 3: Frontend Setup

#### Update `frontend/package.json`

Add the sync script:

```json
{
  "name": "frontend",
  "scripts": {
    "sync-models": "cp ../shared/Models.ts src/types/index.ts 2>/dev/null || cp /shared/Models.ts src/types/index.ts",
    "dev": "npm run sync-models && vite",
    "build": "npm run sync-models && tsc && vite build",
    "typecheck": "tsc --noEmit",
    "lint": "eslint ."
  },
  "dependencies": {
    "react": "^18.0.0",
    // ... other dependencies
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vite": "^5.0.0",
    // ... other dev dependencies
  }
}
```

#### Create `frontend/src/types/` directory

```bash
mkdir -p frontend/src/types
```

#### Add to `frontend/.gitignore`

```gitignore
# Generated files - do not commit
src/types/index.ts
```

### Step 4: Initialize Everything

```bash
# 1. Set up backend virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Generate Python models
make build

# 3. Set up frontend
cd ../frontend
npm install

# 4. Sync TypeScript models
npm run sync-models

# Done!
```

## Usage Workflow

### When You Modify Models

1. **Edit** `shared/Models.ts` with your changes
2. **Regenerate backend models**:
   ```bash
   cd backend
   source venv/bin/activate
   make build
   ```
3. **Sync frontend models** (happens automatically):
   ```bash
   cd frontend
   npm run dev  # or npm run build
   ```

### Pre-commit Hook (Recommended)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Check if Models.ts has been modified
if git diff --cached --name-only | grep -q "shared/Models.ts"; then
    echo "Models.ts modified - regenerating Python models..."

    cd backend
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    make build

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to generate Python models"
        exit 1
    fi

    # Add generated models to commit
    git add db_handlers/models.py

    cd ..
    echo "✓ Models regenerated successfully"
fi

exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Generated Output Examples

### Input: TypeScript (shared/Models.ts)

```typescript
export interface User {
    id: string;
    email: string;
    name?: string;
    role: "admin" | "user";
    createdAt: string;
}
```

### Output: Python (backend/db_handlers/models.py)

```python
# generated by datamodel-codegen
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class Role(str, Enum):
    admin = 'admin'
    user = 'user'

class User(BaseModel):
    id: str
    email: str
    role: Role
    createdAt: str
    name: Optional[str] = None
```

### Output: TypeScript (frontend/src/types/index.ts)

```typescript
// Identical to source - just copied
export interface User {
    id: string;
    email: string;
    name?: string;
    role: "admin" | "user";
    createdAt: string;
}
```

## Using the Generated Models

### Backend Example (Python/Flask)

```python
from db_handlers.models import User, Recording, CreateRecordingRequest
from pydantic import ValidationError

@app.route('/api/recordings', methods=['POST'])
def create_recording():
    try:
        # Automatic validation with Pydantic
        request_data = CreateRecordingRequest(**request.json)

        # Use validated data
        recording = Recording(
            id=str(uuid.uuid4()),
            userId=current_user.id,
            title=request_data.title,
            description=request_data.description,
            status="pending",
            createdAt=datetime.now(UTC).isoformat()
        )

        # Save to database
        db.save_recording(recording.model_dump())

        return jsonify(recording.model_dump()), 201

    except ValidationError as e:
        return jsonify({"error": "Invalid request", "details": e.errors()}), 400
```

### Frontend Example (TypeScript/React)

```typescript
import { Recording, ApiResponse, CreateRecordingRequest } from '@/types';

async function createRecording(data: CreateRecordingRequest): Promise<Recording> {
    const response = await fetch('/api/recordings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });

    const result: ApiResponse<Recording> = await response.json();

    if (result.status === 'error') {
        throw new Error(result.error || 'Failed to create recording');
    }

    return result.data!;
}

// Usage in component
const handleSubmit = async (formData: CreateRecordingRequest) => {
    try {
        const newRecording = await createRecording(formData);
        console.log('Created:', newRecording.id);
    } catch (error) {
        console.error('Failed:', error);
    }
};
```

## Advanced Configuration

### Custom Type Transformations

If you need special handling for certain fields (e.g., datetime objects instead of strings), extend the generated models:

```python
# backend/db_handlers/user_handler.py
from datetime import datetime
from typing import Optional
from pydantic import field_validator, field_serializer
from . import models

class User(models.User):
    """Extended User model with datetime handling"""

    @field_validator('createdAt', 'updatedAt', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    @field_serializer('createdAt', 'updatedAt')
    def serialize_datetime(self, value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return value
```

### Excluding Certain Types from Generation

If you want some types only in TypeScript:

```typescript
// shared/Models.ts

// This will be generated for Python
export interface User {
    id: string;
    email: string;
}

// This won't be exported to Python (no export keyword for Python-only exclusion)
// But it will still be in frontend types
type FrontendOnlyType = {
    componentState: any;
};
```

### Alternative: Per-Model Generation

If you want more control, generate specific models:

```makefile
# Generate only User and Recording models
db_handlers/models.py: $(SHARED_DIR)/Models.ts
	typescript-json-schema $(SHARED_DIR)/Models.ts User Recording \
		--propOrder --required --out $(SHARED_DIR)/models.schema.json
	datamodel-codegen \
		--input $(SHARED_DIR)/models.schema.json \
		--input-file-type jsonschema \
		--output-model-type pydantic_v2.BaseModel \
		--use-subclass-enum \
		--output db_handlers/models.py
```

## Troubleshooting

### Models Not Updating

```bash
# Force regeneration
cd backend
make clean
make build
```

### TypeScript Schema Generation Fails

Ensure you have valid TypeScript:
```bash
# Check for syntax errors
cd shared
npx tsc --noEmit Models.ts
```

### Pydantic Import Errors

Make sure you're using Pydantic v2:
```bash
pip install --upgrade "pydantic>=2.0.0"
```

### Python Types Don't Match TypeScript

Check the JSON Schema intermediate:
```bash
cat shared/models.schema.json
```

Common issues:
- Union types require all options to be explicitly defined
- Enums should use string literals: `"value1" | "value2"`
- Optional fields need `?` in TypeScript
- Dates should be strings (ISO 8601 format)

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/validate-models.yml
name: Validate Models

on:
  pull_request:
    paths:
      - 'shared/Models.ts'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install schema tools
        run: npm install -g typescript-json-schema datamodel-code-generator

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Python dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Generate and validate models
        run: |
          cd backend
          make build
          python -c "import db_handlers.models; print('✓ Models are valid')"

      - name: Check for uncommitted changes
        run: |
          if git diff --exit-code backend/db_handlers/models.py; then
            echo "✓ Generated models match committed version"
          else
            echo "ERROR: Generated models differ from committed version"
            echo "Run 'cd backend && make build' and commit the changes"
            exit 1
          fi
```

## Best Practices

1. **Always define dates as strings** (ISO 8601 format) - convert to Python `datetime` objects in extended models if needed

2. **Use explicit string unions for enums**: `status: "active" | "inactive"` instead of referencing enum types

3. **Document your models** with JSDoc comments:
   ```typescript
   /**
    * Represents a user in the system
    */
   export interface User {
       /** Unique identifier (UUID) */
       id: string;
       /** User's email address (unique) */
       email: string;
   }
   ```

4. **Version your API types** by including them in Models.ts:
   ```typescript
   export interface CreateUserRequest { /* ... */ }
   export interface UpdateUserRequest { /* ... */ }
   export interface UserResponse { /* ... */ }
   ```

5. **Commit generated Python models** or exclude them (your choice):
   - **Commit**: Easier to review changes, no build step needed
   - **Exclude**: Cleaner git history, ensures regeneration

6. **Run `make build` before testing** backend changes to ensure models are current

7. **Use TypeScript strict mode** to catch type issues early:
   ```json
   // tsconfig.json
   {
     "compilerOptions": {
       "strict": true,
       "noUncheckedIndexedAccess": true
     }
   }
   ```

## Summary

This pattern provides:
- ✅ Single source of truth for data models
- ✅ Type safety across frontend and backend
- ✅ Automatic validation with Pydantic
- ✅ Reduced maintenance burden
- ✅ Fewer sync issues between layers
- ✅ Better developer experience

By maintaining types in one place and generating them automatically, you eliminate a major source of bugs and inconsistencies in full-stack applications.
