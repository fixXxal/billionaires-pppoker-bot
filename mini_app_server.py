"""
Flask server for Telegram Mini App - Spin Wheel
CLEAN VERSION - No old code, just what's needed
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv
# DJANGO MIGRATION: Using Django API only (No Google Sheets)
from django_api import DjangoAPI
import pytz
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import random
import time
from collections import defaultdict
from datetime import datetime

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
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')

# Verify critical config
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set! Admin notifications will fail!")
if not ADMIN_USER_ID:
    logger.error("❌ ADMIN_USER_ID not set! Admin notifications will fail!")
else:
    logger.info(f"✅ Admin notifications will be sent to user ID: {ADMIN_USER_ID}")

# Lazy load managers
api = None
bot = None

def get_managers():
    """Lazy load api and bot"""
    global api, bot
    if api is None:
        django_api_url = os.getenv('DJANGO_API_URL', 'http://localhost:8000/api')
        api = DjangoAPI(django_api_url)
        bot = Bot(token=BOT_TOKEN)
    return api, bot


# Rate limiting - max 1 spin per second per user
user_last_spin = defaultdict(float)
SPIN_COOLDOWN = 1.0  # seconds

# Simple cache for user data (5 minute TTL for better performance during high load)
user_data_cache = {}
cache_timestamps = {}
CACHE_TTL = 300  # seconds (5 minutes - increased for launch to reduce Sheets API calls)

# Notification aggregator - collect wins over short time period for batch notifications
pending_notifications = defaultdict(lambda: {'chips': 0, 'wins': [], 'timer': None, 'username': '', 'pppoker_id': ''})
NOTIFICATION_DELAY = 3.0  # seconds - wait 3s to collect all wins before sending notification


def get_cached_user_data(user_id):
    """Get user data from cache or fetch fresh"""
    current_time = time.time()

    # Check if cache is valid
    if user_id in user_data_cache:
        if current_time - cache_timestamps.get(user_id, 0) < CACHE_TTL:
            logger.info(f"📦 Cache hit for user {user_id}")
            return user_data_cache[user_id]

    # Fetch fresh data
    logger.info(f"🔄 Cache miss for user {user_id}, fetching from api")
    api, _ = get_managers()
    # FIXED: Use get_or_create_spin_user which accepts telegram_id
    user_data = api.get_or_create_spin_user(user_id)

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
    """Send notification to user when they win chips - DISABLED, using batched notifications instead"""
    # DISABLED: Instant notifications replaced by batched notifications (bot.py line 8596)
    # The bot now sends notifications every 30 seconds in batches to avoid spam
    logger.info(f"✅ Spin recorded: {username} won {prize} (notification will be sent in batch)")


async def notify_admin(user_id: int, username: str, prize: str, chips: int, pppoker_id: str):
    """Send notification to ALL admins when user wins chips - DISABLED, using batched notifications instead"""
    # DISABLED: Instant admin notifications replaced by batched notifications (bot.py line 8618)
    # The bot now sends admin notifications every 30 seconds in batches with approve buttons
    logger.info(f"✅ Admin notification will be sent in batch for {username} winning {prize}")


def send_aggregated_notifications(user_id: int):
    """Send combined notification for all wins accumulated in the time window"""
    import threading

    notification_data = pending_notifications[user_id]
    total_chips = notification_data['chips']
    username = notification_data['username']
    pppoker_id = notification_data['pppoker_id']

    if total_chips > 0:
        logger.info(f"📬 Sending aggregated notification: {username} won {total_chips} chips total")

        # Send notifications with proper async handling
        try:
            # Create a fresh event loop for each notification batch
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def send_all():
                """Send all notifications together"""
                try:
                    await notify_user_win(user_id, username, f"{total_chips} Chips Total", total_chips)
                    await notify_admin(user_id, username, f"{total_chips} Chips Total", total_chips, pppoker_id)
                except Exception as e:
                    logger.error(f"❌ Error in send_all: {e}")
                    raise

            try:
                loop.run_until_complete(send_all())
                logger.info(f"✅ Aggregated notifications sent successfully")
            finally:
                # Clean up all pending tasks before closing loop
                pending_tasks = asyncio.all_tasks(loop)
                for task in pending_tasks:
                    task.cancel()

                # Run loop one more time to allow cancellations to complete
                loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))

                # Close the loop
                loop.close()

        except Exception as e:
            logger.error(f"❌ Failed to send aggregated notifications: {e}")
            import traceback
            traceback.print_exc()

    # Clear pending notifications for this user
    if user_id in pending_notifications:
        del pending_notifications[user_id]


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

        api, _ = get_managers()
        # Use cached data for faster response
        user_data = get_cached_user_data(user_id)

        if not user_data:
            return jsonify({'success': False, 'message': "No spins available!"}), 400

        available_spins = user_data.get('available_spins', 0)

        # Get username from request (latest from Telegram) or fallback to cached data
        username = data.get('username')  # Get from request first (most up-to-date)
        if not username:
            # Fallback to cached user data
            user_details = user_data.get('user_details', {})
            username = user_details.get('username', 'Unknown')

        # Get PPPoker ID from user_details
        user_details = user_data.get('user_details', {})
        pppoker_id = user_details.get('pppoker_id', '')

        # Try to get from deposits only if empty (fast lookup, no updates)
        if not pppoker_id:
            try:
                pppoker_id = api.get_pppoker_id_from_deposits(user_id)
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

        # PRIZE WEIGHTS - Optimized for 65% club profit margin
        # Try Again: 82.489%, Win chips: 17.511%
        # Average payout: 3.53 chips per spin
        prize_weights = {
            "Try Again!": 82489,  # 82.489% - Most spins lose
            "10": 10000,          # 10.000% - Common small win
            "20": 5000,           # 5.000% - Uncommon small win
            "50": 2000,           # 2.000% - Rare medium win
            "100": 500,           # 0.500% - Very rare good win
            "250": 10,            # 0.010% - Extremely rare big win
            "500": 1              # 0.001% - Legendary jackpot (1 in 100k)
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

        # Log ALL spins to Django API using process_spin endpoint
        # This handles: creating spin history records, deducting spins, updating totals
        import threading

        def log_all_spins():
            try:
                # Prepare results for Django API
                spin_results = []
                for result in results:
                    spin_results.append({
                        'prize': result['prize'],
                        'chips': result['chips'],
                        'segment_index': result['segment_index']
                    })

                # Send to Django API - handles everything in one call
                # Pass username to preserve it in database
                response = api.process_spin(user_id, spin_results, username=username)
                logger.info(f"✅ Processed {len(spin_results)} spins via Django API for user {username}")

            except Exception as e:
                logger.error(f"❌ Failed to process spins: {e}")
                import traceback
                traceback.print_exc()

        # Start logging thread (non-daemon so it completes)
        log_thread = threading.Thread(target=log_all_spins)
        log_thread.start()

        # Wait for logging to complete (max 10 seconds)
        log_thread.join(timeout=10.0)

        # Calculate new values (Django API already updated these, but we need them for response)
        new_available = available_spins - spin_count
        total_used = user_data.get('total_spins_used', 0) + spin_count

        # Invalidate cache so next request gets fresh data from Django
        invalidate_user_cache(user_id)

        # Aggregate notifications - collect wins over short time period for batch notifications
        total_chips_won = sum(r.get('chips', 0) for r in results if isinstance(r, dict) and r.get('chips', 0) > 0)

        if total_chips_won > 0:
            logger.info(f"💰 Chips won this spin: {total_chips_won} - Adding to pending notifications")

            # Add to pending notifications
            import threading
            notification_data = pending_notifications[user_id]
            notification_data['chips'] += total_chips_won
            notification_data['username'] = username
            notification_data['pppoker_id'] = pppoker_id

            # Cancel existing timer if any
            if notification_data['timer'] is not None:
                notification_data['timer'].cancel()

            # Start new timer - will send notification after delay if no more wins
            timer = threading.Timer(NOTIFICATION_DELAY, send_aggregated_notifications, args=[user_id])
            timer.start()
            notification_data['timer'] = timer

            logger.info(f"⏰ Notification timer set for {NOTIFICATION_DELAY}s (Total pending: {notification_data['chips']} chips)")

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
