"""
Test script for notification queue system
"""

import os
from dotenv import load_dotenv
from sheets_manager import SheetsManager

load_dotenv()

SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))

print("=" * 60)
print("🧪 Testing Notification Queue System")
print("=" * 60)

# Initialize sheets manager
print("\n1️⃣ Initializing SheetsManager...")
sheets = SheetsManager(CREDENTIALS_FILE, SPREADSHEET_NAME, TIMEZONE)
print("✅ SheetsManager initialized")

# Test 1: Add a test notification
print("\n2️⃣ Adding test notification to queue...")
test_message = (
    "🧪 <b>TEST NOTIFICATION</b>\n\n"
    "This is a test message from the notification queue system.\n"
    "If you see this, the queue is working! ✅"
)

notification_id = sheets.add_notification(
    user_id=ADMIN_USER_ID,
    message=test_message,
    notification_type='test',
    priority=1  # High priority
)

if notification_id:
    print(f"✅ Notification added with ID: {notification_id}")
else:
    print("❌ Failed to add notification")
    exit(1)

# Test 2: Get pending notifications
print("\n3️⃣ Getting pending notifications...")
pending = sheets.get_pending_notifications(limit=10)
print(f"✅ Found {len(pending)} pending notification(s)")

if pending:
    print("\n📋 Pending notifications:")
    for notif in pending:
        print(f"  - ID: {notif['id']}")
        print(f"    User: {notif['user_id']}")
        print(f"    Type: {notif['type']}")
        print(f"    Priority: {notif['priority']}")
        print(f"    Status: {notif['status']}")
        print()

# Test 3: Check if Notification_Queue sheet exists
print("\n4️⃣ Verifying Notification_Queue sheet...")
try:
    sheet = sheets.notification_queue_sheet
    if sheet:
        row_count = len(sheet.get_all_values())
        print(f"✅ Notification_Queue sheet exists with {row_count} rows")
    else:
        print("❌ Notification_Queue sheet is None")
except Exception as e:
    print(f"❌ Error accessing sheet: {e}")

print("\n" + "=" * 60)
print("✅ Test completed!")
print("=" * 60)
print("\n📌 Next steps:")
print("1. Start the notification worker:")
print("   python notification_worker.py")
print("\n2. The worker will process the test notification")
print("   and you should receive it on Telegram")
print("\n3. Check the Notification_Queue sheet in Google Sheets")
print("   to see the status change from 'pending' to 'sent'")
