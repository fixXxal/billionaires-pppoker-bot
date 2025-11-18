#!/bin/bash

# Automated Mini App Setup and Run Script
# This script helps you set up everything automatically

set -e  # Exit on error

echo "🎰 Mini App Setup Script 🎰"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from correct directory
if [ ! -f "bot.py" ]; then
    echo -e "${RED}❌ Error: bot.py not found!${NC}"
    echo "Please run this script from /mnt/c/billionaires directory"
    exit 1
fi

echo "✅ Directory check passed"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Error: Virtual environment not found!${NC}"
    echo "Please create venv first: python -m venv venv"
    exit 1
fi

echo "✅ Virtual environment found"
echo ""

# Activate venv
source venv/bin/activate

# Check if Flask is installed
if ! python -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask dependencies..."
    pip install -r mini_app_requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo "✅ Flask already installed"
fi
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${YELLOW}⚠️  ngrok not found!${NC}"
    echo ""
    echo "Please install ngrok:"
    echo "1. Visit: https://ngrok.com/download"
    echo "2. Download and install ngrok"
    echo "3. Sign up for free account"
    echo "4. Run: ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    echo "After installing ngrok, run this script again."
    exit 1
fi

echo "✅ ngrok is installed"
echo ""

# Check if bot.py has been updated with Mini App URL
CURRENT_URL=$(grep -n "mini_app_url = " bot.py | grep "YOUR_MINI_APP_URL_HERE")
if [ ! -z "$CURRENT_URL" ]; then
    echo -e "${YELLOW}⚠️  Mini App URL not configured yet!${NC}"
    echo ""
    echo "You need to:"
    echo "1. Start ngrok: ngrok http 5000"
    echo "2. Copy the HTTPS URL"
    echo "3. Update bot.py line 120 with that URL"
    echo ""
    read -p "Do you want to start the Mini App server now and see instructions? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "================================"
        echo "🚀 Starting Mini App Server..."
        echo "================================"
        echo ""
        echo "Next steps:"
        echo "1. Open a NEW terminal"
        echo "2. Run: ngrok http 5000"
        echo "3. Copy the HTTPS URL (e.g., https://abc123.ngrok-free.app)"
        echo "4. Edit bot.py line 120 with that URL"
        echo "5. Open ANOTHER terminal and run: python bot.py"
        echo ""
        echo "Press Ctrl+C to stop this server"
        echo ""
        python mini_app_server.py
    else
        echo "Setup cancelled. Run the script again when ready!"
        exit 0
    fi
else
    echo "✅ Mini App URL configured"
    echo ""
    echo "================================"
    echo "🚀 Starting Mini App Server..."
    echo "================================"
    echo ""
    echo "Server is running on http://localhost:5000"
    echo ""
    echo "If ngrok is not running yet, open another terminal and run:"
    echo "  ngrok http 5000"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""
    python mini_app_server.py
fi
