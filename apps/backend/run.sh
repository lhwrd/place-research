#!/bin/bash
# Run the FastAPI backend with uv

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run with uv
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
