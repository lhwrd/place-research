#!/bin/bash
# Development script with additional checks

set -e

echo "🚀 Starting Place Research API..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys!"
    exit 1
fi

# Start the server
echo "🎯 Starting FastAPI server..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
