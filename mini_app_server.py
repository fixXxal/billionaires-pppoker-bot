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

sheets = SheetsManager()
spin_bot = SpinBot(sheets, ADMIN_USER_ID, pytz.timezone(TIMEZONE))


@app.route('/')
def serve_mini_app():
    """Serve the Mini App HTML"""
    return send_from_directory('.', 'spin_wheel.html')


@app.route('/api/get_spins', methods=['POST'])
def get_spins():
    """Get user's available spins"""
    try:
        data = request.json
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400

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

        # Add surprise chips if won
        if result.get('got_surprise'):
            response['surprise_chips'] = result['surprise_chips']

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
