#!/bin/bash

# Start the LiveKit agent in the background
# The 'dev' command is typically used for local/livekit cloud integration
python agent.py dev &

# Start the FastAPI server
# Render provides the PORT environment variable
echo "Starting FastAPI server on port $PORT"
uvicorn app:app --host 0.0.0.0 --port $PORT
