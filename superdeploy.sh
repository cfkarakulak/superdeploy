#!/bin/bash
# SuperDeploy CLI wrapper - automatically activates venv

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at: $VENV_PATH"
    echo "Please run: cd $SCRIPT_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && pip install -e ."
    exit 1
fi

# Activate venv and run superdeploy
source "$VENV_PATH/bin/activate"
"$VENV_PATH/bin/superdeploy" "$@"

