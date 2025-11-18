#!/bin/bash

# Start Mini App Server for Spin Wheel
# This script helps you quickly start the Mini App server

echo "🎰 Starting Spin Wheel Mini App Server..."
echo ""

# Check if Flask is installed
if ! python -c "import flask" 2>/dev/null; then
    echo "❌ Flask not found. Installing dependencies..."
    pip install -r mini_app_requirements.txt
    echo "✅ Dependencies installed!"
    echo ""
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "   Make sure your environment variables are configured."
    echo ""
fi

# Start the Flask server
echo "✅ Starting Flask server on port 5000..."
echo ""
echo "📝 Next steps:"
echo "   1. If using ngrok, run: ngrok http 5000"
echo "   2. Copy the HTTPS URL from ngrok"
echo "   3. Update bot.py line ~120 with your URL"
echo "   4. Start your bot: python bot.py"
echo ""
echo "🌐 Server starting..."
echo ""

python mini_app_server.py
