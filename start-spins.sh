#!/bin/bash

# Exit on error
set -e

echo "Starting Mini App Server (Spin Wheel)..."

# Start the Flask mini app server
echo "Starting Flask server..."
exec python -u mini_app_server.py
