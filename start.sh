#!/bin/bash

# Exit on error
set -e

echo "Starting Billionaires Bot deployment..."

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start gunicorn in background
echo "Starting Django API server..."
gunicorn billionaires_backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - &

# Wait a bit for gunicorn to start
sleep 5

# Start the Telegram bot in foreground
echo "Starting Telegram bot..."
python bot.py
