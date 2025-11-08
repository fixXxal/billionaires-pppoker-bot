"""
Test Script for Billionaires PPPoker Bot
Run this to verify basic functionality before deployment
"""

import os
import sys
from dotenv import load_dotenv

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing imports...")
    try:
        from telegram import Update
        from telegram.ext import Application
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        import pytz
        print("   ✅ All imports successful")
        return True
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        print("   Run: pip install -r requirements.txt")
        return False

def test_env_vars():
    """Test if required environment variables are set"""
    print("\n🔍 Testing environment variables...")
    load_dotenv()

    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'ADMIN_USER_ID',
        'GOOGLE_SHEETS_CREDENTIALS_FILE',
        'SPREADSHEET_NAME'
    ]

    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value and not value.startswith('your_'):
            print(f"   ✅ {var} is set")
        else:
            print(f"   ❌ {var} is NOT set")
            all_set = False

    return all_set

def test_credentials_file():
    """Test if credentials file exists and is valid JSON"""
    print("\n🔍 Testing Google credentials...")

    creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')

    if not os.path.exists(creds_file):
        print(f"   ❌ Credentials file not found: {creds_file}")
        return False

    try:
        import json
        with open(creds_file, 'r') as f:
            creds = json.load(f)

        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in creds:
                print(f"   ❌ Missing field in credentials: {field}")
                return False

        print(f"   ✅ Credentials file is valid")
        print(f"   📧 Service account: {creds['client_email']}")
        return True
    except json.JSONDecodeError:
        print(f"   ❌ Invalid JSON in credentials file")
        return False
    except Exception as e:
        print(f"   ❌ Error reading credentials: {e}")
        return False

def test_telegram_connection():
    """Test if bot token is valid"""
    print("\n🔍 Testing Telegram bot connection...")

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token or token.startswith('your_'):
        print("   ⚠️  Bot token not configured, skipping test")
        return True

    try:
        import asyncio
        from telegram import Bot

        async def check_bot():
            bot = Bot(token)
            me = await bot.get_me()
            return me

        bot_info = asyncio.run(check_bot())
        print(f"   ✅ Connected to bot: @{bot_info.username}")
        print(f"   🤖 Bot name: {bot_info.first_name}")
        return True
    except Exception as e:
        print(f"   ❌ Failed to connect to Telegram: {e}")
        return False

def test_google_sheets_connection():
    """Test if Google Sheets connection works"""
    print("\n🔍 Testing Google Sheets connection...")

    creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')

    if not os.path.exists(creds_file):
        print("   ⚠️  Credentials file not found, skipping test")
        return True

    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)

        print(f"   ✅ Successfully connected to Google Sheets API")
        print(f"   📊 Can access spreadsheets")
        return True
    except Exception as e:
        print(f"   ❌ Failed to connect to Google Sheets: {e}")
        return False

def test_module_structure():
    """Test if all bot modules can be imported"""
    print("\n🔍 Testing bot modules...")

    modules_to_test = [
        ('bot', 'bot.py'),
        ('admin_panel', 'admin_panel.py'),
        ('sheets_manager', 'sheets_manager.py')
    ]

    all_ok = True
    for module_name, file_name in modules_to_test:
        if not os.path.exists(file_name):
            print(f"   ❌ File not found: {file_name}")
            all_ok = False
            continue

        try:
            __import__(module_name)
            print(f"   ✅ {file_name} is valid")
        except Exception as e:
            print(f"   ❌ Error importing {file_name}: {e}")
            all_ok = False

    return all_ok

def main():
    """Run all tests"""
    print("=" * 60)
    print("Billionaires PPPoker Bot - Test Suite")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Environment Variables", test_env_vars),
        ("Credentials File", test_credentials_file),
        ("Module Structure", test_module_structure),
        ("Telegram Connection", test_telegram_connection),
        ("Google Sheets Connection", test_google_sheets_connection),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} test failed with error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All tests passed! Your bot is ready to run.")
        print("\n📝 Next steps:")
        print("   1. Run: python bot.py")
        print("   2. Test in Telegram")
        print("   3. Deploy to Railway")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\n📖 Check these resources:")
        print("   - README.md for setup instructions")
        print("   - QUICKSTART.md for quick setup")
        print("   - setup_helper.py for configuration check")
        return 1

if __name__ == '__main__':
    sys.exit(main())
