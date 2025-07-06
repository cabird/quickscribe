#!/bin/bash
# Run the sync recording participants script with proper environment

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/backend/venv" ]; then
    source "$PROJECT_ROOT/backend/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/scripts/.venv" ]; then
    source "$PROJECT_ROOT/scripts/.venv/bin/activate"
fi

# Set PYTHONPATH to include backend directory
export PYTHONPATH="$PROJECT_ROOT/backend:$PYTHONPATH"

# Load environment variables
if [ -f "$PROJECT_ROOT/backend/.env" ]; then
    export $(cat "$PROJECT_ROOT/backend/.env" | grep -v '^#' | xargs)
fi

# Run the script with all arguments
python "$SCRIPT_DIR/sync_recording_participants.py" "$@"