#!/bin/bash

# VeriMinutes Startup Script

echo "Starting VeriMinutes..."

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker container"
    python -m uvicorn src.app.api:app --host 0.0.0.0 --port 8787
else
    echo "Running locally"

    # Check for Python
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed"
        exit 1
    fi

    # Check for ffmpeg
    if ! command -v ffmpeg &> /dev/null; then
        echo "Warning: ffmpeg not found. Audio recording will not work."
        echo "Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
    fi

    # Start the application
    python3 start.py
fi