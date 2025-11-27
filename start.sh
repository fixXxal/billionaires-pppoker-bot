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

# Start the Telegram bot in background with unbuffered output
echo "Starting Telegram bot..."
python -u bot.py 2>&1 &

# Store bot PID
BOT_PID=$!
echo "Bot started with PID: $BOT_PID"

# Start gunicorn in foreground (this keeps the container running)
echo "Starting Django API server..."
exec gunicorn billionaires_backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
