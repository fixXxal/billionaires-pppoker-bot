"""
Setup Helper Script for Billionaires PPPoker Bot
Run this to verify your configuration before deployment
"""

import os
import sys
from dotenv import load_dotenv

def check_file_exists(filename, description):
    """Check if a file exists"""
    if os.path.exists(filename):
        print(f"✅ {description} found: {filename}")
        return True
    else:
        print(f"❌ {description} NOT found: {filename}")
        return False

def check_env_variable(var_name, description):
    """Check if environment variable is set"""
    value = os.getenv(var_name)
    if value and value != f"your_{var_name.lower()}_here":
        print(f"✅ {description} is set")
        return True
    else:
        print(f"❌ {description} is NOT set or still has default value")
        return False

def main():
    print("=" * 60)
    print("Billionaires PPPoker Bot - Configuration Checker")
    print("=" * 60)
    print()

    # Load environment variables
    if not check_file_exists('.env', '.env file'):
        print("\n⚠️  Create a .env file based on .env.example")
        print("   Copy .env.example to .env and fill in your values")
        return False

    load_dotenv()

    all_checks_passed = True

    print("\n📋 Checking Configuration Files...")
    print("-" * 60)

    # Check credentials.json
    if not check_file_exists('credentials.json', 'Google Sheets credentials'):
        print("   Download credentials from Google Cloud Console")
        all_checks_passed = False

    # Check Python files
    required_files = [
        ('bot.py', 'Main bot file'),
        ('admin_panel.py', 'Admin panel module'),
        ('sheets_manager.py', 'Google Sheets manager'),
        ('requirements.txt', 'Requirements file')
    ]

    for filename, description in required_files:
        if not check_file_exists(filename, description):
            all_checks_passed = False

    print("\n🔧 Checking Environment Variables...")
    print("-" * 60)

    # Check required environment variables
    env_vars = [
        ('TELEGRAM_BOT_TOKEN', 'Telegram Bot Token'),
        ('ADMIN_USER_ID', 'Admin User ID'),
        ('GOOGLE_SHEETS_CREDENTIALS_FILE', 'Credentials file path'),
        ('SPREADSHEET_NAME', 'Spreadsheet name'),
    ]

    for var_name, description in env_vars:
        if not check_env_variable(var_name, description):
            all_checks_passed = False

    # Check payment accounts (optional)
    print("\n💳 Checking Payment Account Configuration...")
    print("-" * 60)

    payment_accounts = [
        ('BML_ACCOUNT', 'BML Account'),
        ('MIB_ACCOUNT', 'MIB Account'),
        ('USDT_WALLET', 'USDT Wallet'),
    ]

    for var_name, description in payment_accounts:
        check_env_variable(var_name, description)
        # Don't fail if payment accounts aren't set yet

    print("\n📊 Configuration Summary")
    print("=" * 60)

    if all_checks_passed:
        print("✅ All required configuration checks passed!")
        print("\n🚀 Next Steps:")
        print("   1. Test locally: python bot.py")
        print("   2. Update payment accounts via bot commands")
        print("   3. Deploy to Railway")
        print("\n💡 Pro Tips:")
        print("   - Test all features locally before deploying")
        print("   - Keep your .env and credentials.json files secure")
        print("   - Never commit these files to GitHub")
        return True
    else:
        print("❌ Some configuration issues need to be resolved")
        print("\n📖 Please check:")
        print("   1. README.md for setup instructions")
        print("   2. QUICKSTART.md for quick setup guide")
        print("   3. .env.example for required variables")
        return False

if __name__ == '__main__':
    print()
    success = main()
    print()
    sys.exit(0 if success else 1)
