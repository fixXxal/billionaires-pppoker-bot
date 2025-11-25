"""
Notification Worker - Processes notification queue and sends Telegram messages
Runs continuously in background, checking queue every 5 seconds
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from sheets_manager import SheetsManager
from datetime import datetime
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')

# Worker settings
POLL_INTERVAL = 5  # Check queue every 5 seconds
BATCH_SIZE = 10  # Process up to 10 notifications per cycle
MESSAGE_DELAY = 0.1  # 100ms delay between messages (10 messages/second max)
MAX_RETRIES = 3
RETRY_AFTER_MINUTES = 1

# Initialize
sheets = None
bot = None


def init_managers():
    """Initialize sheets manager and bot"""
    global sheets, bot
    try:
        sheets = SheetsManager(CREDENTIALS_FILE, SPREADSHEET_NAME, TIMEZONE)
        bot = Bot(token=BOT_TOKEN)
        logger.info("✅ Managers initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize managers: {e}")
        return False


async def send_notification(notification: dict) -> tuple:
    """
    Send a single notification via Telegram

    Returns:
        (success: bool, error_message: str or None)
    """
    try:
        user_id = notification['user_id']
        message = notification['message']

        # Send message with HTML parse mode
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='HTML'
        )

        logger.info(f"✅ Notification sent to user {user_id}")
        return (True, None)

    except TelegramError as e:
        error_msg = str(e)
        logger.warning(f"⚠️ Telegram error for user {user_id}: {error_msg}")
        return (False, error_msg)

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ Error sending notification: {error_msg}")
        return (False, error_msg)


async def process_notifications():
    """Process pending notifications from queue"""
    try:
        # Get pending notifications
        pending = sheets.get_pending_notifications(limit=BATCH_SIZE)

        if not pending:
            return 0

        logger.info(f"📬 Processing {len(pending)} pending notifications")
        sent_count = 0

        for notification in pending:
            notification_id = notification['id']

            # Send notification
            success, error_message = await send_notification(notification)

            if success:
                # Mark as sent
                sheets.update_notification_status(
                    notification_id,
                    status='sent',
                    sent_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                sent_count += 1
            else:
                # Mark as failed
                sheets.update_notification_status(
                    notification_id,
                    status='failed',
                    error_message=error_message
                )

            # Rate limiting - wait between messages
            await asyncio.sleep(MESSAGE_DELAY)

        logger.info(f"✅ Processed {sent_count}/{len(pending)} notifications successfully")
        return sent_count

    except Exception as e:
        logger.error(f"❌ Error processing notifications: {e}")
        return 0


async def retry_failed_notifications():
    """Retry failed notifications that are eligible for retry"""
    try:
        # Get failed notifications ready for retry
        failed = sheets.get_failed_notifications_for_retry(
            max_retries=MAX_RETRIES,
            retry_after_minutes=RETRY_AFTER_MINUTES
        )

        if not failed:
            return 0

        logger.info(f"🔄 Retrying {len(failed)} failed notifications")
        retry_count = 0

        for notification in failed:
            notification_id = notification['id']

            # Reset to pending so it gets processed in next cycle
            sheets.reset_notification_to_pending(notification_id)
            retry_count += 1

        logger.info(f"✅ Reset {retry_count} notifications to pending for retry")
        return retry_count

    except Exception as e:
        logger.error(f"❌ Error retrying failed notifications: {e}")
        return 0


async def worker_loop():
    """Main worker loop - runs continuously"""
    logger.info("🚀 Notification worker started")
    logger.info(f"⚙️ Settings: Poll interval={POLL_INTERVAL}s, Batch size={BATCH_SIZE}, Message delay={MESSAGE_DELAY}s")

    cycle_count = 0

    while True:
        try:
            cycle_count += 1

            # Process pending notifications
            sent = await process_notifications()

            # Every 12 cycles (1 minute), retry failed notifications
            if cycle_count % 12 == 0:
                await retry_failed_notifications()

            # Wait before next cycle
            await asyncio.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("⏹️ Worker stopped by user")
            break

        except Exception as e:
            logger.error(f"❌ Unexpected error in worker loop: {e}")
            # Wait a bit longer on error to avoid spam
            await asyncio.sleep(POLL_INTERVAL * 2)


def main():
    """Entry point"""
    logger.info("=" * 60)
    logger.info("🔔 NOTIFICATION WORKER - Starting...")
    logger.info("=" * 60)

    # Initialize managers
    if not init_managers():
        logger.error("❌ Failed to initialize - exiting")
        return

    # Start worker loop
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("\n👋 Notification worker stopped")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")


if __name__ == '__main__':
    main()
