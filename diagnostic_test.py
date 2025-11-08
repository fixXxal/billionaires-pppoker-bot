#!/usr/bin/env python3
"""
Quick Diagnostic Test for Bot Issues
Run this to quickly identify problems with notifications and approvals
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("🔍 BILLIONAIRES BOT DIAGNOSTIC TEST")
print("=" * 60)
print()

# Test 1: Check .env file
print("1️⃣ Checking .env configuration...")
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
admin_id = os.getenv('ADMIN_USER_ID')

if not bot_token:
    print("   ❌ TELEGRAM_BOT_TOKEN is missing!")
    sys.exit(1)
else:
    print(f"   ✅ Bot Token: {bot_token[:20]}...{bot_token[-10:]}")

if not admin_id:
    print("   ❌ ADMIN_USER_ID is missing!")
    sys.exit(1)
else:
    print(f"   ✅ Admin User ID: {admin_id}")

print()

# Test 2: Check Python version
print("2️⃣ Checking Python version...")
python_version = sys.version_info
if python_version.major == 3 and python_version.minor in [11, 12]:
    print(f"   ✅ Python {python_version.major}.{python_version.minor}.{python_version.micro} (Good!)")
elif python_version.major == 3 and python_version.minor == 13:
    print(f"   ⚠️  Python {python_version.major}.{python_version.minor}.{python_version.micro} (May have compatibility issues)")
    print("   💡 Consider using Python 3.11 or 3.12")
else:
    print(f"   ⚠️  Python {python_version.major}.{python_version.minor}.{python_version.micro} (Unexpected version)")

print()

# Test 3: Check required packages
print("3️⃣ Checking required packages...")
try:
    import telegram
    print(f"   ✅ python-telegram-bot: {telegram.__version__}")
except ImportError:
    print("   ❌ python-telegram-bot is not installed!")
    print("   💡 Run: pip install python-telegram-bot")

try:
    import gspread
    print(f"   ✅ gspread installed")
except ImportError:
    print("   ❌ gspread is not installed!")
    print("   💡 Run: pip install gspread")

try:
    import oauth2client
    print(f"   ✅ oauth2client installed")
except ImportError:
    print("   ❌ oauth2client is not installed!")
    print("   💡 Run: pip install oauth2client")

print()

# Test 4: Check Google credentials
print("4️⃣ Checking Google Sheets credentials...")
creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
if os.path.exists(creds_file):
    print(f"   ✅ {creds_file} exists")

    # Try to load it
    try:
        import json
        with open(creds_file, 'r') as f:
            creds = json.load(f)
            if 'client_email' in creds:
                print(f"   ✅ Service account: {creds['client_email']}")
            else:
                print("   ⚠️  credentials.json doesn't have client_email")
    except Exception as e:
        print(f"   ⚠️  Could not parse credentials.json: {e}")
else:
    print(f"   ❌ {creds_file} not found!")

print()

# Test 5: Test bot connection
print("5️⃣ Testing bot connection...")
try:
    from telegram import Bot
    import asyncio

    async def test_bot():
        bot = Bot(token=bot_token)
        me = await bot.get_me()
        print(f"   ✅ Bot connected: @{me.username}")

        # Try to send a test message to admin
        print(f"   📤 Attempting to send test message to admin ({admin_id})...")
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="🧪 *Diagnostic Test Message*\n\nIf you see this, notifications are working!\n\nThis test was run from diagnostic test script."
            )
            print(f"   ✅ TEST MESSAGE SENT SUCCESSFULLY!")
            print(f"   💡 Check your Telegram to see if you received it.")
        except Exception as e:
            print(f"   ❌ FAILED to send message to admin!")
            print(f"   Error: {e}")
            print()
            print("   🔍 Common causes:")
            print("   - Admin ID is incorrect (verify with @userinfobot)")
            print("   - You haven't started the bot yet (send /start to your bot)")
            print("   - You blocked the bot")
            print("   - Bot token is invalid")

    asyncio.run(test_bot())

except Exception as e:
    print(f"   ❌ Bot connection failed: {e}")
    print("   💡 Check your bot token is correct")

print()

# Test 6: Test Google Sheets connection
print("6️⃣ Testing Google Sheets connection...")
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
    client = gspread.authorize(creds)

    spreadsheet_name = os.getenv('SPREADSHEET_NAME', 'Billionaires_Bot_Data')
    sheet = client.open(spreadsheet_name)
    print(f"   ✅ Connected to: {sheet.title}")
    print(f"   ✅ Worksheets: {[ws.title for ws in sheet.worksheets()]}")

except Exception as e:
    print(f"   ❌ Google Sheets connection failed!")
    print(f"   Error: {e}")
    print("   💡 Common causes:")
    print("   - Spreadsheet name is incorrect")
    print("   - Service account doesn't have access to spreadsheet")
    print("   - Google Sheets API or Drive API not enabled")

print()
print("=" * 60)
print("✅ DIAGNOSTIC TEST COMPLETE")
print("=" * 60)
print()
print("📋 NEXT STEPS:")
print()
print("1. Check if you received the test message in Telegram")
print("2. If YES: Notifications work! The issue is elsewhere.")
print("3. If NO: Follow the troubleshooting steps shown above")
print()
print("4. To test the bot fully:")
print("   - Run: python bot.py")
print("   - Send /test command to your bot")
print("   - Make a test deposit from another account")
print()
print("💡 If you saw any ❌ errors above, fix those first!")
print()
