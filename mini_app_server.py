"""
Flask server for Telegram Mini App - Spin Wheel
Handles API requests from the Mini App
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv
from sheets_manager import SheetsManager
from spin_bot import SpinBot
import pytz
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for Telegram Mini App

# Initialize managers
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Don't initialize sheets on startup to avoid rate limits
# Will be initialized on first request
sheets = None
spin_bot = None
bot = None

def get_sheets_manager():
    """Lazy load sheets manager"""
    global sheets, spin_bot, bot
    if sheets is None:
        sheets = SheetsManager(CREDENTIALS_FILE, SPREADSHEET_NAME, TIMEZONE)
        spin_bot = SpinBot(sheets, ADMIN_USER_ID, pytz.timezone(TIMEZONE))
        bot = Bot(token=BOT_TOKEN)
    return sheets, spin_bot


async def send_admin_notification(user_id: int, username: str, prize_name: str, chips: int, pppoker_id: str = ""):
    """Send notification to admin when user wins chips"""
    try:
        message = (
            f"🎰 <b>SPIN WHEEL WIN!</b> 🎰\n\n"
            f"👤 User: {username} (ID: {user_id})\n"
            f"🎁 Prize: {prize_name}\n"
            f"💰 Chips: {chips}\n"
            f"🎮 PPPoker ID: {pppoker_id or 'Not set'}\n\n"
            f"⏳ <b>Pending Approval</b>\n"
            f"Use /pendingspins to review and approve"
        )

        await bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Admin notification sent for user {user_id} winning {prize_name}")

    except TelegramError as e:
        logger.error(f"Failed to send admin notification: {e}")


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

        # Lazy load sheets manager
        sheets, _ = get_sheets_manager()

        # Get user data from Google Sheets
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
    """Process a spin request - NEW CLEAN VERSION FOR MINI APP"""
    try:
        data = request.json
        user_id = data.get('user_id')
        spin_count = data.get('spin_count', 1)

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

        # Lazy load sheets manager
        sheets, _ = get_sheets_manager()

        # Get user data
        user_data = sheets.get_spin_user(user_id)

        if not user_data:
            return jsonify({
                'success': False,
                'message': "You don't have any spins available!"
            }), 400

        available_spins = user_data.get('available_spins', 0)
        username = user_data.get('username', 'Unknown')
        pppoker_id = user_data.get('pppoker_id', '')

        if available_spins < spin_count:
            return jsonify({
                'success': False,
                'message': f"You only have {available_spins} spin(s) available!"
            }), 400

        # NEW CLEAN SPIN LOGIC
        import random

        # Define wheel prizes matching frontend EXACTLY (must be same order as frontend prizes array!)
        # Frontend: 500, Try Again!, 50, iPhone, 20, Try Again!, 100, MacBook, 10, Try Again!, 250, AirPods, 20, Try Again!, 50, Watch
        wheel_prizes = [
            "500",         # 0
            "Try Again!",  # 1
            "50",          # 2
            "iPhone",      # 3
            "20",          # 4
            "Try Again!",  # 5
            "100",         # 6
            "MacBook",     # 7
            "10",          # 8
            "Try Again!",  # 9
            "250",         # 10
            "AirPods",     # 11
            "20",          # 12
            "Try Again!",  # 13
            "50",          # 14
            "Watch"        # 15
        ]

        # Prize pool with weights (only chips and Try Again! - no Apple products)
        prize_pool = {
            "Try Again!": 60,  # 60% chance
            "10": 15,          # 15%
            "20": 12,          # 12%
            "50": 8,           # 8%
            "100": 3,          # 3%
            "250": 1.5,        # 1.5%
            "500": 0.5         # 0.5%
        }

        results = []

        for i in range(spin_count):
            # Pick prize based on weights
            choices = list(prize_pool.keys())
            weights = list(prize_pool.values())
            won_prize = random.choices(choices, weights=weights, k=1)[0]

            prize_display = won_prize if won_prize == "Try Again!" else f"{won_prize} Chips"
            chips_amount = 0 if won_prize == "Try Again!" else int(won_prize)

            results.append({
                'prize': prize_display,
                'segment_index': get_segment_for_prize(won_prize, wheel_prizes)
            })

            # Log each spin to Google Sheets history
            sheets.log_spin_history(
                user_id=user_id,
                username=username,
                prize=prize_display,
                chips=chips_amount,
                pppoker_id=pppoker_id
            )

            # Send admin notification for chip wins (not "Try Again")
            if chips_amount > 0:
                try:
                    asyncio.run(send_admin_notification(
                        user_id=user_id,
                        username=username,
                        prize_name=prize_display,
                        chips=chips_amount,
                        pppoker_id=pppoker_id
                    ))
                except Exception as e:
                    logger.error(f"Failed to send admin notification: {e}")

        # Update user spins
        new_available = available_spins - spin_count
        total_spins_used = user_data.get('total_spins_used', 0) + spin_count

        sheets.update_spin_user(
            user_id=user_id,
            available_spins=new_available,
            total_spins_used=total_spins_used
        )

        # Build response
        response = {
            'success': True,
            'available_spins': new_available,
            'total_spins_used': total_spins_used,
            'total_chips_earned': user_data.get('total_chips_earned', 0),
            'results': results
        }

        # For single spin, return display_prize
        if spin_count == 1:
            response['display_prize'] = results[0]['prize']
            response['segment_index'] = results[0]['segment_index']

        logger.info(f"Spin successful for user {user_id}: {response}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in spin: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


def get_segment_for_prize(prize, wheel_prizes):
    """Get random segment index for a prize (handles duplicates)"""
    import random
    matching_indices = [i for i, p in enumerate(wheel_prizes) if p == prize]
    return random.choice(matching_indices) if matching_indices else 0


if __name__ == '__main__':
    # Run on port from environment variable (Railway/Heroku) or default to 5000
    # For production, use a proper WSGI server like gunicorn
    # and host it on a service with HTTPS (required for Telegram Mini Apps)
    port = int(os.getenv('PORT', os.getenv('MINI_APP_PORT', 5000)))
    app.run(host='0.0.0.0', port=port, debug=False)
