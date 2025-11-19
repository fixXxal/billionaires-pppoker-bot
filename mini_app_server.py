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


async def notify_admin(user_id: int, username: str, prize: str, chips: int, pppoker_id: str):
    """Send notification to admin when user wins chips"""
    try:
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
            f"⏳ <b>Pending Approval</b>\n"
            f"Use /pendingspins to review"
        )
        await bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode='HTML')
        logger.info(f"✅ Admin notified: {username} won {prize}")
    except TelegramError as e:
        logger.error(f"❌ Failed to notify admin: {e}")
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
    """Get user's available spins"""
    try:
        data = request.json
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

        sheets, _ = get_managers()
        user_data = sheets.get_spin_user(user_id)

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
    """Process spin - CLEAN VERSION"""
    try:
        data = request.json
        user_id = data.get('user_id')
        spin_count = data.get('spin_count', 1)

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

        sheets, _ = get_managers()
        user_data = sheets.get_spin_user(user_id)

        if not user_data:
            return jsonify({'success': False, 'message': "No spins available!"}), 400

        available_spins = user_data.get('available_spins', 0)
        username = user_data.get('username', 'Unknown')
        pppoker_id = user_data.get('pppoker_id', '')

        if available_spins < spin_count:
            return jsonify({
                'success': False,
                'message': f"You only have {available_spins} spin(s)!"
            }), 400

        # WHEEL PRIZES - MUST match frontend exactly!
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
                'segment_index': segment_index
            })

            # Log to Google Sheets
            sheets.log_spin_history(user_id, username, prize_display, chips, pppoker_id)

            # Notify admin for chip wins
            if chips > 0:
                logger.info(f"💰 Chip win detected! Notifying admin about {chips} chips for user {username}")
                try:
                    asyncio.run(notify_admin(user_id, username, prize_display, chips, pppoker_id))
                except Exception as e:
                    logger.error(f"❌ Failed to notify admin: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logger.info(f"🔄 Try Again - no admin notification needed")

        # Update user spins
        new_available = available_spins - spin_count
        total_used = user_data.get('total_spins_used', 0) + spin_count

        sheets.update_spin_user(
            user_id=user_id,
            available_spins=new_available,
            total_spins_used=total_used
        )

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
