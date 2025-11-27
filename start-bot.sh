#!/bin/bash

# Exit on error
set -e

echo "Starting Telegram Bot service..."

# Run migrations (only bot needs this for its database access)
echo "Running database migrations..."
python manage.py migrate --noinput

# Start the Telegram bot with unbuffered output
echo "Starting Telegram bot..."
exec python -u bot.py
