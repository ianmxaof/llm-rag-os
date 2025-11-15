#!/usr/bin/env bash

# Initialize database
python -m backend.models

# Start FastAPI backend
echo "Starting FastAPI backend on http://127.0.0.1:8000"
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000 &

sleep 2

echo "Backend started. Open http://127.0.0.1:8000/docs for API documentation"

