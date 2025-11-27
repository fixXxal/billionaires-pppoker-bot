#!/bin/bash

# Exit on error
set -e

echo "Starting Django API service..."

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start gunicorn for Django API
echo "Starting Django API server on port $PORT..."
exec gunicorn billionaires_backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
