#!/bin/bash

# Exit on error
set -e

echo "Starting Spins Management service..."

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Start the spins management system
echo "Starting spins manager..."
exec python -u spins_manager.py
