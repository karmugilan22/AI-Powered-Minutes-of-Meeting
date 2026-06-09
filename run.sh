#!/bin/bash
echo "Starting AI-Powered MoM Assistant Backend..."

# If .venv directory exists, use it
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
    UVICORN_BIN=".venv/bin/uvicorn"
else
    echo "Warning: .venv not found. Using system python/uvicorn..."
    UVICORN_BIN="uvicorn"
fi

# Detect if we're on a Pi or Debian-based system
if [ -f /etc/debian_version ]; then
    echo "System is Debian-based. Checking PortAudio dependency for microphone recording..."
    if ! dpkg -s libportaudio2 >/dev/null 2>&1; then
        echo "--------------------------------------------------------"
        echo "WARNING: libportaudio2 is not installed."
        echo "Physical microphone recording on this host might fail."
        echo "Install it via: sudo apt-get update && sudo apt-get install libportaudio2"
        echo "--------------------------------------------------------"
    fi
fi

# Run FastAPI
$UVICORN_BIN backend.main:app --host 0.0.0.0 --port 8000 --reload
