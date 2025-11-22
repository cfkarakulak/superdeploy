#!/bin/bash
# Dashboard backend startup script with proper PYTHONPATH

cd "$(dirname "$0")"
export PYTHONPATH="/Users/cfkarakulak/Desktop/cheapa.io/hero/superdeploy:$PYTHONPATH"
exec python -m uvicorn main:app --host 0.0.0.0 --port 8401 --reload
