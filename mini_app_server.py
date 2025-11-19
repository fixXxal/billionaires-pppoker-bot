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
    """Send notification to admin when user wins a milestone prize"""
    try:
        message = (
            f"🎊 <b>MILESTONE PRIZE WON!</b> 🎊\n\n"
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
    """Process a spin request"""
    try:
        data = request.json
        user_id = data.get('user_id')
        spin_count = data.get('spin_count', 1)

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

        # Lazy load sheets manager
        sheets, spin_bot = get_sheets_manager()

        # Validate Telegram Web App data (optional but recommended)
        init_data = data.get('init_data')
        # TODO: Validate init_data using Telegram's validation method

        # Get username from Telegram (fallback to Unknown)
        username = "Unknown"
        try:
            # In a real implementation, extract from init_data
            user_data = sheets.get_spin_user(user_id)
            if user_data:
                username = user_data.get('username', 'Unknown')
        except:
            pass

        # Process the spin using existing spin_bot logic
        import asyncio
        result = asyncio.run(spin_bot.process_spin(user_id, username, spin_count))

        if not result['success']:
            return jsonify(result), 400

        # Format response for Mini App
        response = {
            'success': True,
            'available_spins': result['available_spins'],
            'total_spins_used': result['total_spins_used'],
            'total_chips_earned': result['total_chips_earned']
        }

        # Add display prize (for animation)
        if result.get('results') and len(result['results']) > 0:
            response['display_prize'] = result['results'][0]['prize']

        # Add milestone prize if won
        if result.get('milestone_prize'):
            response['milestone_prize'] = result['milestone_prize']

            # Send instant notification to admin
            try:
                user_data = sheets.get_spin_user(user_id)
                pppoker_id = user_data.get('pppoker_id', '') if user_data else ''

                asyncio.run(send_admin_notification(
                    user_id=user_id,
                    username=username,
                    prize_name=result['milestone_prize']['name'],
                    chips=result['milestone_prize']['chips'],
                    pppoker_id=pppoker_id
                ))
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")

        # Add surprise chips if won
        if result.get('got_surprise'):
            response['surprise_chips'] = result['surprise_chips']

            # Send notification for surprise reward too
            try:
                user_data = sheets.get_spin_user(user_id)
                pppoker_id = user_data.get('pppoker_id', '') if user_data else ''

                asyncio.run(send_admin_notification(
                    user_id=user_id,
                    username=username,
                    prize_name="Surprise Reward",
                    chips=result['surprise_chips'],
                    pppoker_id=pppoker_id
                ))
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")

        logger.info(f"Spin successful for user {user_id}: {response}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in spin: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


if __name__ == '__main__':
    # Run on port from environment variable (Railway/Heroku) or default to 5000
    # For production, use a proper WSGI server like gunicorn
    # and host it on a service with HTTPS (required for Telegram Mini Apps)
    port = int(os.getenv('PORT', os.getenv('MINI_APP_PORT', 5000)))
    app.run(host='0.0.0.0', port=port, debug=False)
