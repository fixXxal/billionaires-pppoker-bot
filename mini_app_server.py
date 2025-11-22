"""
Flask server for Telegram Mini App - Spin Wheel
CLEAN VERSION - No old code, just what's needed
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv
from sheets_manager import SheetsManager
import pytz
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import random
import time
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')

# Verify critical config
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set! Admin notifications will fail!")
if not ADMIN_USER_ID:
    logger.error("❌ ADMIN_USER_ID not set! Admin notifications will fail!")
else:
    logger.info(f"✅ Admin notifications will be sent to user ID: {ADMIN_USER_ID}")

# Lazy load managers
sheets = None
bot = None

def get_managers():
    """Lazy load sheets and bot"""
    global sheets, bot
    if sheets is None:
        sheets = SheetsManager(CREDENTIALS_FILE, SPREADSHEET_NAME, TIMEZONE)
        bot = Bot(token=BOT_TOKEN)
    return sheets, bot


# Rate limiting - max 1 spin per second per user
user_last_spin = defaultdict(float)
SPIN_COOLDOWN = 1.0  # seconds

# Simple cache for user data (1 minute TTL)
user_data_cache = {}
cache_timestamps = {}
CACHE_TTL = 60  # seconds


def get_cached_user_data(user_id):
    """Get user data from cache or fetch fresh"""
    current_time = time.time()

    # Check if cache is valid
    if user_id in user_data_cache:
        if current_time - cache_timestamps.get(user_id, 0) < CACHE_TTL:
            logger.info(f"📦 Cache hit for user {user_id}")
            return user_data_cache[user_id]

    # Fetch fresh data
    logger.info(f"🔄 Cache miss for user {user_id}, fetching from sheets")
    sheets, _ = get_managers()
    user_data = sheets.get_spin_user(user_id)

    # Update cache
    user_data_cache[user_id] = user_data
    cache_timestamps[user_id] = current_time

    return user_data


def invalidate_user_cache(user_id):
    """Invalidate cache for a user after their data changes"""
    if user_id in user_data_cache:
        del user_data_cache[user_id]
    if user_id in cache_timestamps:
        del cache_timestamps[user_id]


async def notify_user_win(user_id: int, username: str, prize: str, chips: int):
    """Send notification to user when they win chips"""
    try:
        # Make sure bot is initialized
        global bot
        if bot is None:
            bot = Bot(token=BOT_TOKEN)

        message = (
            f"🎊 <b>CONGRATULATIONS!</b> 🎊\n\n"
            f"🎰 <b>You won:</b> {prize}\n"
            f"💰 <b>Chips:</b> {chips}\n\n"
            f"⏳ <b>Your reward is pending approval</b>\n\n"
            f"✅ Our admin team will review and approve your chips shortly.\n"
            f"📬 You'll receive a notification once approved!\n\n"
            f"🎮 Your chips will be added to your PPPoker account.\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Thank you for playing! 🎲"
        )
        await bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
        logger.info(f"✅ User notified: {username} won {prize}")
    except TelegramError as e:
        logger.error(f"❌ Failed to notify user: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error in notify_user_win: {e}")


async def notify_admin(user_id: int, username: str, prize: str, chips: int, pppoker_id: str):
    """Send notification to ALL admins when user wins chips - with instant approve button"""
    try:
        # Import InlineKeyboardButton and InlineKeyboardMarkup
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        # Make sure bot is initialized
        global bot
        if bot is None:
            bot = Bot(token=BOT_TOKEN)

        message = (
            f"🎰 <b>SPIN WHEEL WIN!</b> 🎰\n\n"
            f"👤 User: {username} (ID: {user_id})\n"
            f"🎁 Prize: {prize}\n"
            f"💰 Chips: {chips}\n"
            f"🎮 PPPoker ID: {pppoker_id or 'Not set'}\n\n"
            f"⏳ <b>Pending Approval</b>"
        )

        # Create instant approve button
        keyboard = [
            [InlineKeyboardButton("✅ Approve Now", callback_data=f"approve_instant_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send to super admin
        try:
            await bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            logger.info(f"✅ Super admin notified: {username} won {prize}")
        except Exception as e:
            logger.error(f"❌ Failed to notify super admin: {e}")

        # Send to all regular admins
        try:
            admins = sheets.get_all_admins()
            for admin in admins:
                try:
                    await bot.send_message(
                        chat_id=admin['admin_id'],
                        text=message,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    logger.info(f"✅ Admin {admin['admin_id']} notified: {username} won {prize}")
                except Exception as e:
                    logger.error(f"❌ Failed to notify admin {admin['admin_id']}: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to get admin list: {e}")

    except TelegramError as e:
        logger.error(f"❌ Failed to notify admins: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error in notify_admin: {e}")


@app.route('/')
def serve_mini_app():
    """Serve the Mini App HTML"""
    return send_from_directory('.', 'spin_wheel.html')


@app.route('/spinnsimgss/<path:filename>')
def serve_images(filename):
    """Serve product images"""
    return send_from_directory('spinnsimgss', filename)


@app.route('/api/get_spins', methods=['POST'])
def get_spins():
    """Get user's available spins - FAST with caching"""
    try:
        data = request.json
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

        # Use cached data for fast response
        user_data = get_cached_user_data(user_id)

        if not user_data:
            return jsonify({
                'available_spins': 0,
                'total_spins_used': 0,
                'total_chips_earned': 0
            })

        return jsonify({
            'available_spins': user_data.get('available_spins', 0),
            'total_spins_used': user_data.get('total_spins_used', 0),
            'total_chips_earned': user_data.get('total_chips_earned', 0)
        })

    except Exception as e:
        logger.error(f"Error in get_spins: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/spin', methods=['POST'])
def spin():
    """Process spin - OPTIMIZED with rate limiting and caching"""
    try:
        data = request.json
        user_id = data.get('user_id')
        spin_count = data.get('spin_count', 1)

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

        # Rate limiting - prevent spam
        current_time = time.time()
        last_spin = user_last_spin.get(user_id, 0)

        if current_time - last_spin < SPIN_COOLDOWN:
            remaining = SPIN_COOLDOWN - (current_time - last_spin)
            return jsonify({
                'success': False,
                'message': f'Please wait {remaining:.1f}s before spinning again'
            }), 429

        # Update last spin time
        user_last_spin[user_id] = current_time

        sheets, _ = get_managers()
        # Use cached data for faster response
        user_data = get_cached_user_data(user_id)

        if not user_data:
            return jsonify({'success': False, 'message': "No spins available!"}), 400

        available_spins = user_data.get('available_spins', 0)
        username = user_data.get('username', 'Unknown')

        # Get PPPoker ID quickly without blocking
        # Don't sync during spin - it's too slow and not critical for the spin itself
        pppoker_id = user_data.get('pppoker_id', '')

        # Try to get from deposits only if empty (fast lookup, no updates)
        if not pppoker_id:
            try:
                pppoker_id = sheets.get_pppoker_id_from_deposits(user_id)
            except:
                pppoker_id = ''

        logger.info(f"📋 User {username} spinning with PPPoker ID: {pppoker_id or 'Not set'}")

        if available_spins < spin_count:
            return jsonify({
                'success': False,
                'message': f"You only have {available_spins} spin(s)!"
            }), 400

        # WHEEL PRIZES - MUST match frontend exactly! (16 segments)
        # NOTE: iPhone, MacBook, AirPods, Watch are DISPLAY ONLY - backend never selects them!
        wheel_prizes = [
            "500", "Try Again!", "50", "iPhone", "20", "Try Again!",
            "100", "MacBook", "10", "Try Again!", "250", "AirPods",
            "20", "Try Again!", "50", "Watch"
        ]

        # DEBUG: Log prize order
        logger.info("📋 PRIZE ORDER (Backend):")
        for idx, p in enumerate(wheel_prizes):
            logger.info(f"  {idx}: {p}")

        # PRIZE WEIGHTS - Only chips and Try Again can be won
        prize_weights = {
            "Try Again!": 60,
            "10": 15,
            "20": 12,
            "50": 8,
            "100": 3,
            "250": 1.5,
            "500": 0.5
        }

        results = []

        for i in range(spin_count):
            # Pick prize based on weights
            prize = random.choices(
                list(prize_weights.keys()),
                weights=list(prize_weights.values()),
                k=1
            )[0]

            # Find matching segment index
            matching_indices = [i for i, p in enumerate(wheel_prizes) if p == prize]
            segment_index = random.choice(matching_indices)

            # Format prize display
            if prize == "Try Again!":
                prize_display = "Try Again!"
                chips = 0
            else:
                prize_display = f"{prize} Chips"
                chips = int(prize)

            logger.info(f"🎲 Spin {i+1}: prize={prize}, matching_indices={matching_indices}, chosen_segment={segment_index}")
            logger.info(f"   wheel_prizes[{segment_index}] = {wheel_prizes[segment_index]}")

            results.append({
                'prize': prize_display,
                'segment_index': segment_index,
                'chips': chips  # Store chips for notification later
            })

            # Log to Google Sheets (in background to not block response)
            import threading
            threading.Thread(
                target=sheets.log_spin_history,
                args=(user_id, username, prize_display, chips, pppoker_id),
                daemon=True
            ).start()

        # Update user spins
        new_available = available_spins - spin_count
        total_used = user_data.get('total_spins_used', 0) + spin_count

        # Update in background thread (Google Sheets is slow)
        def update_user_data():
            sheets.update_spin_user(
                user_id=user_id,
                available_spins=new_available,
                total_spins_used=total_used
            )
            # Invalidate cache after update completes
            invalidate_user_cache(user_id)

        threading.Thread(target=update_user_data, daemon=True).start()

        # Send notifications AFTER all spins are processed (in background - non-blocking)
        total_chips_won = sum(r.get('chips', 0) for r in results if isinstance(r, dict) and r.get('chips', 0) > 0)

        if total_chips_won > 0:
            logger.info(f"💰 Total chips won: {total_chips_won} - Queuing notifications")

            # Calculate delay based on number of spins
            # Single spin: 4 seconds animation
            # Multi-spin: 2.5 seconds per spin
            notification_delay = 4.5 if spin_count == 1 else (spin_count * 2.5) + 0.5

            # Run notifications in background thread to not block the response
            import threading
            def send_notifications():
                try:
                    # Wait for animation to complete before sending notifications
                    import time
                    time.sleep(notification_delay)

                    asyncio.run(notify_user_win(user_id, username, f"{total_chips_won} Chips", total_chips_won))
                    asyncio.run(notify_admin(user_id, username, f"{total_chips_won} Chips Total", total_chips_won, pppoker_id))
                    logger.info(f"✅ Notifications sent after {notification_delay}s delay")
                except Exception as e:
                    logger.error(f"❌ Failed to send notifications: {e}")

            threading.Thread(target=send_notifications, daemon=True).start()
            logger.info(f"✅ Notifications queued with {notification_delay}s delay")

        # Build response
        response = {
            'success': True,
            'available_spins': new_available,
            'total_spins_used': total_used,
            'total_chips_earned': user_data.get('total_chips_earned', 0),
            'results': results
        }

        # For single spin, add display fields
        if spin_count == 1:
            response['display_prize'] = results[0]['prize']
            response['segment_index'] = results[0]['segment_index']

        logger.info(f"Spin successful: User {user_id} - {results}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in spin: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', os.getenv('MINI_APP_PORT', 5000)))
    app.run(host='0.0.0.0', port=port, debug=False)
