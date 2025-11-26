"""
Periodic Sync Runner
Runs Django to Google Sheets sync every 30 seconds
Keep this running in the background to maintain sync
"""

import time
import schedule
from sheets_sync import DjangoToSheetsSync


def run_sync_job():
    """Execute sync and handle any errors"""
    try:
        syncer = DjangoToSheetsSync()
        syncer.run_full_sync()
    except Exception as e:
        print(f"❌ Sync failed with error: {str(e)}")


def main():
    print("🔄 Periodic Sync Service Started")
    print("Running sync every 30 seconds...")
    print("Press Ctrl+C to stop\n")

    # Run immediately on startup
    run_sync_job()

    # Schedule to run every 30 seconds
    schedule.every(30).seconds.do(run_sync_job)

    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Sync service stopped by user")
