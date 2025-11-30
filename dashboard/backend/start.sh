#!/bin/bash
# Dashboard backend startup script with proper PYTHONPATH

# Get the superdeploy root (2 levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUPERDEPLOY_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$(dirname "$0")"
export PYTHONPATH="$SUPERDEPLOY_ROOT:$PYTHONPATH"
exec python -m uvicorn main:app --host 0.0.0.0 --port 8401 --reload
