"""
Billionaires PPPoker Club Telegram Bot
Main bot file with all handlers and logic
Version: 2.0 - Django API Migration Complete
"""

import os
import logging
import asyncio
from typing import Dict
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
# Using Django API with backward compatibility layer (migrated from Google Sheets)
from sheets_compat import SheetsCompatAPI
import admin_panel
import vision_api
from spin_bot import SpinBot
import spin_bot as spin_bot_module

# Load environment variables
load_dotenv()

# Configure logging with explicit stdout handler for Railway
import sys
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))

# Helper function to escape markdown special characters
def escape_markdown(text: str) -> str:
    """Escape special markdown characters in user-provided text"""
    if not text:
        return text
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def clean_pppoker_id(raw_input: str) -> str:
    """
    Clean PPPoker ID by removing all non-numeric characters.
    Keeps only digits 0-9.

    Examples:
        '123 456 789' -> '123456789'
        'ID: 123456' -> '123456'
        '123-456-789' -> '123456789'
        'abc123xyz' -> '123'
    """
    if not raw_input:
        return ''
    # Keep only digits
    cleaned = ''.join(char for char in raw_input if char.isdigit())
    return cleaned

def is_counter_closed() -> bool:
    """Check if counter is currently closed"""
    return not api.is_counter_open()

async def send_counter_closed_message(update: Update) -> bool:
    """
    Send counter closed message to user.
    Returns True if counter is closed, False if open.
    """
    if is_counter_closed():
        await update.message.reply_text(
            "🔴 <b>COUNTER IS CLOSED</b>\n\n"
            "We are currently not accepting requests.\n"
            "Please try again later when we reopen!",
            parse_mode='HTML'
        )
        return True
    return False
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')
DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://localhost:8000/api')

# Log the Django API URL for debugging
logger.info(f"🔗 Django API URL: {DJANGO_API_URL}")
logger.info(f"🌍 Timezone: {TIMEZONE}")

# Initialize Django API with backward compatibility (migrated from Google Sheets)
api = SheetsCompatAPI(DJANGO_API_URL)

# Initialize Spin Bot with Django API
spin_bot = SpinBot(api, ADMIN_USER_ID, pytz.timezone(TIMEZONE))
logger.info(f"✅ SpinBot initialized successfully - Minimum deposit for spins: 200 MVR")

# Conversation states
(DEPOSIT_METHOD, DEPOSIT_AMOUNT, DEPOSIT_PPPOKER_ID, DEPOSIT_ACCOUNT_NAME,
 DEPOSIT_PROOF, DEPOSIT_USDT_AMOUNT, WITHDRAWAL_METHOD, WITHDRAWAL_AMOUNT, WITHDRAWAL_PPPOKER_ID,
 WITHDRAWAL_ACCOUNT_NAME, WITHDRAWAL_ACCOUNT_NUMBER, JOIN_PPPOKER_ID,
 ADMIN_APPROVAL_NOTES, SUPPORT_CHAT, ADMIN_REPLY_MESSAGE, UPDATE_ACCOUNT_METHOD, UPDATE_ACCOUNT_NUMBER, BROADCAST_MESSAGE,
 PROMO_PERCENTAGE, PROMO_START_DATE, PROMO_END_DATE, SEAT_AMOUNT, SEAT_SLIP_UPLOAD,
 CASHBACK_PROMO_PERCENTAGE, CASHBACK_PROMO_START_DATE, CASHBACK_PROMO_END_DATE,
 COUNTER_CLOSE_POSTER, COUNTER_OPEN_POSTER,
 INVESTMENT_PPPOKER_ID, INVESTMENT_NOTE, INVESTMENT_AMOUNT,
 RETURN_SELECT_ID, RETURN_AMOUNT,
 BALANCE_SETUP_CHIPS, BALANCE_SETUP_COST, BALANCE_SETUP_MVR, BALANCE_SETUP_USD, BALANCE_SETUP_USDT,
 BALANCE_BUY_CHIPS, BALANCE_BUY_COST,
 BALANCE_ADD_CURRENCY, BALANCE_ADD_AMOUNT, BALANCE_ADD_NOTE,
 ACCOUNT_ADD_METHOD, ACCOUNT_ADD_NUMBER, ACCOUNT_ADD_HOLDER,
 ACCOUNT_EDIT_NUMBER, ACCOUNT_EDIT_HOLDER) = range(48)

# Store for live support sessions
live_support_sessions: Dict[int, int] = {}  # user_id: admin_user_id (which admin is handling this user)
support_mode_users: set = set()  # Users currently in support mode
admin_reply_context: Dict[int, int] = {}  # admin_id: user_id (for reply context)
notification_messages: Dict[str, list] = {}  # request_id: [(admin_id, message_id), ...] (for editing notification buttons)
active_support_handlers: Dict[int, int] = {}  # user_id: admin_id (tracks which admin is handling which support session)
processing_requests: Dict[str, int] = {}  # request_id: admin_id (tracks which admin is processing which request)
support_message_ids: Dict[int, list] = {}  # user_id: [(chat_id, message_id), ...] (tracks support messages with buttons to remove later)
user_support_message_ids: Dict[int, list] = {}  # user_id: [message_id, ...] (tracks user messages with End Support button)
support_timeout_jobs: Dict[int, object] = {}  # user_id: job (tracks scheduled auto-close jobs)
seat_request_data: Dict[int, dict] = {}  # user_id: {amount, pppoker_id, request_id} (tracks seat request data)
seat_reminder_jobs: Dict[int, object] = {}  # user_id: job (tracks seat reminder jobs)


# Helper Functions
def is_admin(user_id: int) -> bool:
    """Check if user is admin (super admin or regular admin)"""
    return api.is_admin(user_id)


# Spin Bot Wrapper Functions
async def freespins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open Mini App for spinning wheel"""
    user = update.effective_user

    try:
        # Check if counter is open
        counter_status = api.get_counter_status()
        if not counter_status.get('is_open', True):
            await update.message.reply_text(
                "🔒 *COUNTER IS CLOSED*\n\n"
                "The spin wheel is currently unavailable\\.\n"
                "Please try again when the counter reopens\\!\n\n"
                "Thank you for your patience\\! 🙏",
                parse_mode='MarkdownV2'
            )
            return

        # Get user's spin data (creates user if doesn't exist)
        user_data = spin_bot.api.get_or_create_spin_user(user.id)

        if not user_data or user_data.get('available_spins', 0) == 0:
            # Create deposit button
            keyboard = [[InlineKeyboardButton("💰 Make Deposit", callback_data="deposit_start")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "━━━━━━━━━━━━━━━━━━\n"
                "🎰 *FREE SPINS* 🎰\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "💫 *No spins available right now\\!*\n\n"
                "💰 Make a deposit to unlock free spins\\!\n"
                "🔥 More deposit → More spins → More prizes\\!\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👉 Click button below to get started\\!\n"
                "━━━━━━━━━━━━━━━━━━",
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )
            return

        available = user_data.get('available_spins', 0)

        # MINI APP URL - Railway deployment
        mini_app_url = "https://billionaires-spins.up.railway.app"

        # Create button to open Mini App
        keyboard = [[
            InlineKeyboardButton(
                "🎰 Open Spin Wheel 🎰",
                web_app=WebAppInfo(url=mini_app_url)
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎰 *FREE SPINS* 🎰\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 You have *{available}* spins available\\!\n\n"
            f"Click the button below to open the spinning wheel\\!\n\n"
            f"━━━━━━━━━━━━━━━━━━",
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in freespins command: {e}")
        await update.message.reply_text("❌ Error loading spin wheel\\. Please try again\\.", parse_mode='MarkdownV2')

# DISABLED: Spinning is now done in Mini App only
# async def spin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Wrapper for spin bot callback"""
#     await spin_bot_module.spin_callback(update, context, spin_bot, ADMIN_USER_ID)

# async def spin_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Wrapper for spin again callback"""
#     await spin_bot_module.spin_again_callback(update, context, spin_bot)

async def addspins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for add spins command"""
    await spin_bot_module.addspins_command(update, context, spin_bot, is_admin)

async def spinsstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for spin stats command"""
    await spin_bot_module.spinsstats_command(update, context, spin_bot, is_admin)

async def pendingspins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for pending spins command"""
    await spin_bot_module.pendingspins_command(update, context, spin_bot, is_admin)

async def approvespin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for approve spin command"""
    await spin_bot_module.approvespin_command(update, context, spin_bot, is_admin)


async def handle_mini_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data sent from the Mini App after spinning"""
    try:
        import json
        web_app_data = update.message.web_app_data.data
        result = json.loads(web_app_data)

        logger.info(f"Received Mini App data: {result}")

        # The result already contains all the spin information
        # Just acknowledge receipt to the user
        await update.message.reply_text(
            "✅ Spin completed! Check your results in the Mini App.",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error handling Mini App data: {e}")


async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send notification to all admins"""
    # Send to super admin
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send notification to super admin: {e}")

    # Send to all regular admins
    try:
        admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(admins_response, dict) and 'results' in admins_response:
            admins = admins_response['results']
        else:
            admins = admins_response

        for admin in admins:
            try:
                await context.bot.send_message(chat_id=admin['telegram_id'], text=message, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Failed to send notification to admin {admin['telegram_id']}: {e}")
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")


# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    # Create or update user in database
    try:
        logger.info(f"Creating/updating user: {user.id} ({user.username})")
        api.create_or_update_user(
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )
        logger.info(f"Successfully created/updated user: {user.id}")
    except Exception as e:
        logger.error(f"❌ Failed to create/update user {user.id}: {e}")
        await update.message.reply_text(
            "⚠️ <b>Service Temporarily Unavailable</b>\n\n"
            "We're experiencing technical difficulties. Please try again in a few moments.\n\n"
            f"Error: {str(e)[:100]}",
            parse_mode='HTML'
        )
        return

    # Check if user is admin - show admin menu
    if is_admin(user.id):
        keyboard = [
            [KeyboardButton("📋 Admin Panel"), KeyboardButton("🎰 Spin Management")],
            [KeyboardButton("📊 View Deposits"), KeyboardButton("💸 View Withdrawals")],
            [KeyboardButton("🎮 View Join Requests"), KeyboardButton("💳 Payment Accounts")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        welcome_message = f"""
🔐 <b>ADMIN PANEL</b>

Welcome back, Admin {user.first_name}! 👨‍💼

<b>Quick Access:</b>
📋 <b>Admin Panel</b> - Full admin dashboard
🎰 <b>Spin Management</b> - Manage spin rewards
📊 <b>View Deposits</b> - Manage deposit requests
💸 <b>View Withdrawals</b> - Manage withdrawal requests
🎮 <b>View Join Requests</b> - Approve/reject club joins
💳 <b>Payment Accounts</b> - Update payment details

Select an option to get started:
"""
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Regular user menu
        keyboard = [
            [KeyboardButton("💰 Deposit"), KeyboardButton("💸 Withdrawal")],
            [KeyboardButton("🪑 Seat"), KeyboardButton("🎮 Join Club")],
            [KeyboardButton("🎲 Free Spins"), KeyboardButton("💸 Cashback")],
            [KeyboardButton("💬 Live Support"), KeyboardButton("📊 My Info")],
            [KeyboardButton("❓ Help")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        welcome_message = f"""
🎰 <b>Welcome to Billionaires PPPoker Club!</b> 🎰

Hello {user.first_name}! 👋

I'm here to help you with:
💰 <b>Deposits</b> - Add funds to your account
💸 <b>Withdrawals</b> - Cash out your winnings
🎲 <b>Free Spins</b> - Win chips by spinning!
🎮 <b>Club Access</b> - Join our exclusive club
💬 <b>Live Support</b> - Chat with our admin

Please select an option from the menu below:
"""
        # Add channel link button
        channel_keyboard = [[InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/Billionairesmv")]]
        channel_markup = InlineKeyboardMarkup(channel_keyboard)

        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')
        await update.message.reply_text(
            "📢 <b>Stay Updated!</b>\n\n"
            "Join our official Telegram channel for latest news, promotions, and exclusive offers! 🎁",
            reply_markup=channel_markup,
            parse_mode='HTML'
        )


# Help Command
async def test_admin_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test admin notification - Admin only"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only command.")
        return

    try:
        keyboard = [
            [
                InlineKeyboardButton("✅ Test Approve", callback_data="test_approve"),
                InlineKeyboardButton("❌ Test Reject", callback_data="test_reject")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"🧪 *TEST NOTIFICATION*\n\nAdmin ID: `{ADMIN_USER_ID}`\n\nThis is a test notification with buttons. Click them to verify they work!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await update.message.reply_text(f"✅ Test notification sent to admin ID: {ADMIN_USER_ID}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send test: {e}")


async def test_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle test button clicks"""
    query = update.callback_query
    await query.answer("Test button clicked!")

    if query.data == "test_approve":
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ **Test Approve button works!**",
            parse_mode='Markdown'
        )
    elif query.data == "test_reject":
        await query.edit_message_text(
            f"{query.message.text}\n\n❌ **Test Reject button works!**",
            parse_mode='Markdown'
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command and Help button"""

    # Basic help for regular users
    help_text = """
📖 **How to Use Billionaires Bot**

**💰 Deposit**

• Tap 💰 Deposit
• Choose your payment method — BML, MIB, USD, or USDT
• Upload your payment slip
• Enter your PPPoker ID
• Wait for approval
• Receive an instant confirmation once approved

**💸 Withdrawal**

• Tap 💸 Withdrawal
• Select your preferred payment method — BML, MIB, USD, or USDT
• Enter the amount you wish to withdraw
• Provide your PPPoker ID
• Enter your bank account number
• Wait while your request is processed
• Get an instant notification when completed

**🎮 Join Club**

• Tap 🎮 Join Club
• Enter your PPPoker ID
• Wait for approval
• You'll receive an instant notification once you're in!

**💬 Live Support**

• Tap 💬 Live Support to chat directly with an admin
• Type /endsupport anytime to end the conversation
"""

    # Add admin commands only if user is admin
    if is_admin(update.effective_user.id):
        admin_help = """
━━━━━━━━━━━━━━━━━━

🔐 **ADMIN COMMANDS**

**💼 Admin Panel:**
• `/admin` - Open admin panel

**💳 Payment Account Management:**
• `/update_bml` - Update BML account
• `/update_mib` - Update MIB account
• `/update_usd` - Update USD account
• `/update_usdt` - Update USDT wallet
• `/clear_bml` - Remove BML account
• `/clear_mib` - Remove MIB account
• `/clear_usd` - Remove USD account
• `/clear_usdt` - Remove USDT wallet

**💱 Exchange Rate Management:**
• `/set_usd_rate <rate>` - Set USD to MVR rate
  Example: `/set_usd_rate 17.50`
• `/set_usdt_rate <rate>` - Set USDT to MVR rate
  Example: `/set_usdt_rate 18.50`

**📊 Reports & Broadcasting:**
• `/stats` - View profit/loss statistics
• `/broadcast` - Send message to all users

**📋 Admin Panel Features:**
• Approve/reject deposits instantly
• Approve/reject withdrawals
• Manage join requests
• Manage promotions (create, view, deactivate)
• View payment accounts
• Live support (reply via buttons)
"""
        # Super admin only commands
        if update.effective_user.id == ADMIN_USER_ID:
            admin_help += """
━━━━━━━━━━━━━━━━━━

🔱 **SUPER ADMIN ONLY**

**👥 Admin Management:**
• `/addadmin <user_id>` - Add new admin
  Example: `/addadmin 123456789`
• `/removeadmin <user_id>` - Remove admin
  Example: `/removeadmin 123456789`
• `/listadmins` - View all admins
"""
        help_text += admin_help

    await update.message.reply_text(help_text, parse_mode='Markdown')


# Deposit Flow
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start deposit process"""
    # Check if counter is closed
    if await send_counter_closed_message(update):
        return ConversationHandler.END

    user_data = api.get_user(update.effective_user.id)

    # Get all configured payment accounts
    payment_accounts = api.get_all_payment_accounts()
    logger.info(f"Payment accounts for deposit: {payment_accounts}")

    # Build keyboard with only configured payment methods
    keyboard = []
    if 'BML' in payment_accounts and payment_accounts['BML'].get('account_number'):
        logger.info(f"Adding BML button: {payment_accounts['BML']}")
        keyboard.append([InlineKeyboardButton("🏦 BML", callback_data="deposit_bml")])
    if 'MIB' in payment_accounts and payment_accounts['MIB'].get('account_number'):
        logger.info(f"Adding MIB button: {payment_accounts['MIB']}")
        keyboard.append([InlineKeyboardButton("🏦 MIB", callback_data="deposit_mib")])
    if 'USD' in payment_accounts and payment_accounts['USD'].get('account_number'):
        logger.info(f"Adding USD button: {payment_accounts['USD']}")
        keyboard.append([InlineKeyboardButton("💵 USD", callback_data="deposit_usd")])
    if 'USDT' in payment_accounts and payment_accounts['USDT'].get('account_number'):
        logger.info(f"Adding USDT button: {payment_accounts['USDT']}")
        keyboard.append([InlineKeyboardButton("💎 USDT (BEP20)", callback_data="deposit_usdt")])

    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    # Check if any payment methods are configured
    if len(keyboard) == 1:  # Only cancel button
        await update.message.reply_text(
            "⚠️ No payment methods are currently available.\n\n"
            "Please contact admin for assistance.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💰 **Deposit to Billionaires Club**\n\n"
        "Please select your payment method:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return DEPOSIT_METHOD


async def deposit_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit method selection"""
    query = update.callback_query
    await query.answer()

    method = query.data.replace('deposit_', '').upper()
    context.user_data['deposit_method'] = method

    # Get payment account details
    account = api.get_payment_account_details(method)
    account_holder = api.get_payment_account_holder(method)

    if not account:
        await query.edit_message_text(
            "❌ Payment account not configured. Please contact admin."
        )
        return ConversationHandler.END

    method_names = {'BML': 'Bank of Maldives', 'MIB': 'Maldives Islamic Bank', 'USD': 'USD Bank Transfer', 'USDT': 'USDT (BEP20)'}

    # Ask for receipt/slip directly after showing account details
    if method == 'USDT':
        message = f"💰 <b>Deposit via {method_names[method]}</b>\n\n"

        # Show exchange rate for USDT
        usdt_rate = api.get_exchange_rate('USDT', 'MVR')
        if usdt_rate:
            message += f"💱 <b>Current Rate:</b> 1 USDT = {float(usdt_rate):.2f} MVR\n\n"

        message += f"<b>Wallet Address:</b> <a href='#'>(tap to copy)</a>\n"
        message += f"<code>{account}</code>\n\n"
        message += f"📝 Please send your <b>Transaction ID (TXID)</b> from the blockchain:"

        await query.edit_message_text(message, parse_mode='HTML')
    elif method == 'USD':
        # Build message with exchange rate and account details
        message = f"💰 <b>Deposit via {method_names[method]}</b>\n\n"

        # Show exchange rate for USD
        usd_rate = api.get_exchange_rate('USD', 'MVR')
        if usd_rate:
            message += f"💱 <b>Current Rate:</b> 1 USD = {float(usd_rate):.2f} MVR\n\n"

        message += f"<b>Account Number:</b> <a href='#'>(tap to copy)</a>\n<code>{account}</code>\n\n"

        if account_holder and account_holder.strip():
            message += f"<b>Account Holder:</b>\n{account_holder}\n\n"

        message += f"━━━━━━━━━━━━━━━━━━\n"
        message += f"📸 Please upload your <b>payment slip/receipt</b> (screenshot or photo):"

        await query.edit_message_text(message, parse_mode='HTML')
    else:
        # Build message with account holder name if available (BML/MIB)
        message = f"💰 <b>Deposit via {method_names[method]}</b>\n\n"
        message += f"<b>Account Number:</b> <a href='#'>(tap to copy)</a>\n<code>{account}</code>\n\n"

        if account_holder and account_holder.strip():
            message += f"<b>Account Holder:</b>\n{account_holder}\n\n"

        message += f"━━━━━━━━━━━━━━━━━━\n"
        message += f"📸 Please upload your <b>payment slip/receipt</b> (screenshot or photo):"

        await query.edit_message_text(message, parse_mode='HTML')

    return DEPOSIT_PROOF


async def deposit_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit amount input"""
    try:
        amount = float(update.message.text.replace(',', ''))
        if amount <= 0:
            raise ValueError("Amount must be positive")

        context.user_data['deposit_amount'] = amount

        await update.message.reply_text(
            "🎮 Please enter your **PPPoker ID**:",
            parse_mode='Markdown'
        )

        return DEPOSIT_PPPOKER_ID

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number (e.g., 1000 or 1000.50):"
        )
        return DEPOSIT_AMOUNT


async def deposit_pppoker_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PPPoker ID input - final step, creates deposit request and sends to admin"""
    user = update.effective_user
    raw_input = update.message.text.strip()

    # Clean PPPoker ID (remove spaces, letters, special characters)
    pppoker_id = clean_pppoker_id(raw_input)

    # Validate that we have a valid number
    if not pppoker_id or len(pppoker_id) < 3:
        await update.message.reply_text(
            "❌ Invalid PPPoker ID. Please enter only numbers (at least 3 digits):",
            parse_mode='HTML'
        )
        return DEPOSIT_PPPOKER_ID

    # Update user's PPPoker ID
    api.update_user_pppoker_id(user.id, pppoker_id)

    # Get stored data from context
    method = context.user_data['deposit_method']
    transaction_ref = context.user_data['transaction_ref']
    extracted_details = context.user_data.get('extracted_details')

    # Get USDT specific data if available
    usdt_amount = context.user_data.get('usdt_amount')
    usdt_rate = context.user_data.get('usdt_exchange_rate')

    # Get amount and account name from extracted details (or use defaults)
    if method == 'USDT' and usdt_amount:
        # For USDT, use the MVR equivalent amount
        amount = context.user_data.get('deposit_amount', 0)  # This is MVR amount
        account_name = "USDT Deposit"
    elif method == 'USD':
        # For USD, convert to MVR
        usd_amount = extracted_details['amount'] if extracted_details and extracted_details['amount'] else 0
        usd_rate = api.get_exchange_rate('USD', 'MVR') or 15.42
        usd_rate = float(usd_rate)
        amount = usd_amount * usd_rate  # Convert to MVR
        account_name = extracted_details['sender_name'] if extracted_details and extracted_details['sender_name'] else "Not extracted"
    else:
        amount = extracted_details['amount'] if extracted_details and extracted_details['amount'] else 0
        account_name = extracted_details['sender_name'] if extracted_details and extracted_details['sender_name'] else "Not extracted"

    # Update user's account name if we extracted it
    if extracted_details and extracted_details['sender_name']:
        api.update_user_account_name(user.id, extracted_details['sender_name'])

    # Create deposit request
    deposit_response = api.create_deposit_request(
        telegram_id=user.id,
        amount=amount,
        method=method,
        account_name=account_name,
        proof_image_path=transaction_ref,
        pppoker_id=pppoker_id
    )
    request_id = deposit_response.get('id') if isinstance(deposit_response, dict) else deposit_response

    # Send confirmation to user
    confirmation_msg = f"✅ <b>Deposit sent!</b>\n\n"

    if method == 'USDT' and usdt_amount:
        # Show both USDT and MVR amounts
        confirmation_msg += f"💎 {usdt_amount} USDT (≈{amount:,.2f} MVR)\n"
        confirmation_msg += f"🔗 TXID: <code>{transaction_ref[:25]}...</code>\n"
        if usdt_rate:
            confirmation_msg += f"💱 Rate: 1 USDT = {float(usdt_rate):.2f} MVR\n"
    elif method == 'USD':
        # Show both USD and MVR amounts
        usd_amount = extracted_details['amount'] if extracted_details and extracted_details['amount'] else 0
        confirmation_msg += f"💵 {usd_amount} USD (≈{amount:,.2f} MVR)\n"
        confirmation_msg += f"💱 Rate: 1 USD = {float(usd_rate):.2f} MVR\n"
    else:
        confirmation_msg += f"💰 {amount} MVR via {method}\n"

    confirmation_msg += f"🎮 ID: {pppoker_id}\n\n"
    confirmation_msg += f"Awaiting admin approval."

    await update.message.reply_text(confirmation_msg, parse_mode='HTML')

    # Send notification to admin with approval buttons
    username_display = f"@{user.username}" if user.username else "No username"

    # Build clean admin message
    # Use extracted reference if available, otherwise show transaction ref
    ref_number = "N/A"
    verified_amount = amount
    verified_bank = method
    sender_name = account_name
    receiver_name = "Billionaires Club"

    if extracted_details and extracted_details['reference_number']:
        ref_number = extracted_details['reference_number']

    # Override with extracted values if available and valid
    # BUT: Don't overwrite for USD/USDT since amount is already converted to MVR
    if extracted_details:
        if extracted_details['amount'] and extracted_details['amount'] > 0 and method not in ['USD', 'USDT']:
            verified_amount = extracted_details['amount']
        # NOTE: Don't overwrite verified_bank with OCR bank!
        # User-selected method is the RECEIVER's bank (where money goes TO)
        # OCR 'bank' field can show either sender's or receiver's bank depending on slip format
        # We must validate against user-selected method to ensure correct account matching
        if extracted_details['sender_name']:
            sender_name = extracted_details['sender_name']
        if extracted_details['receiver_name']:
            receiver_name = extracted_details['receiver_name']

    # Validate receiver name against stored account holder name
    name_validation_warning = ""
    if extracted_details and extracted_details['receiver_name']:
        # Get stored account holder name for this payment method
        stored_holder_name = api.get_payment_account_holder(verified_bank)

        if stored_holder_name:
            # Normalize names for comparison (case-insensitive, remove extra spaces)
            extracted_receiver = extracted_details['receiver_name'].upper().strip()
            stored_holder = stored_holder_name.upper().strip()

            # Check if names match (allow partial match for flexibility)
            if stored_holder not in extracted_receiver and extracted_receiver not in stored_holder:
                name_validation_warning = f"\n\n⚠️ <b>NAME MISMATCH WARNING</b>\n" \
                                         f"Slip receiver: {extracted_details['receiver_name']}\n" \
                                         f"Expected: {stored_holder_name}"

    # Validate receiver account number against stored account number
    account_validation_warning = ""
    if extracted_details and extracted_details.get('receiver_account_number'):
        # Get stored account number for this payment method
        stored_account_number = api.get_payment_account_details(verified_bank)

        if stored_account_number:
            # Normalize account numbers (remove spaces, dashes)
            extracted_account = extracted_details['receiver_account_number'].replace(' ', '').replace('-', '').strip()
            stored_account = stored_account_number.replace(' ', '').replace('-', '').strip()

            # Check if account numbers match (exact match required)
            if extracted_account != stored_account:
                account_validation_warning = f"\n\n⚠️ <b>ACCOUNT NUMBER MISMATCH WARNING</b>\n" \
                                            f"Slip receiver account: {extracted_details['receiver_account_number']}\n" \
                                            f"Expected: {stored_account_number}"

    # Combine warnings
    validation_warnings = name_validation_warning + account_validation_warning

    # Currency and USDT/USD display
    if method == 'USDT' and usdt_amount:
        # USDT deposit - show both currencies
        amount_display = f"<b>{usdt_amount} USDT</b> (≈ {verified_amount:,.2f} MVR)"
        if usdt_rate:
            amount_display += f"\n💱 Exchange Rate: 1 USDT = {float(usdt_rate):.2f} MVR"
        currency = 'MVR'  # Use MVR for bonus calculations
        ref_number = transaction_ref  # TXID
    elif method == 'USD':
        # USD deposit - show both currencies
        usd_amount = extracted_details['amount'] if extracted_details and extracted_details['amount'] else 0
        amount_display = f"<b>{usd_amount} USD</b> (≈ {verified_amount:,.2f} MVR)"
        # Get the USD rate that was used for conversion
        display_usd_rate = api.get_exchange_rate('USD', 'MVR') or 15.42
        amount_display += f"\n💱 Exchange Rate: 1 USD = {float(display_usd_rate):.2f} MVR"
        currency = 'MVR'  # Use MVR for bonus calculations
    else:
        # Regular MVR deposit
        currency = 'MVR'
        amount_display = f"<b>{currency} {verified_amount:,.2f}</b>"

    # Check for active promotion and user eligibility
    promotion_info = ""
    promotion_bonus = 0
    active_promotion = api.get_active_promotion()

    if active_promotion and verified_amount > 0:
        # Check if user is eligible (first deposit during promotion period)
        # Use 'id' and 'percentage' fields from PromoCode serializer
        promo_id = active_promotion.get('id')
        promo_percentage = active_promotion.get('percentage', 0)

        is_eligible = api.check_user_promotion_eligibility(
            user.id,
            pppoker_id,
            promo_id
        )

        if is_eligible:
            # Calculate bonus
            promotion_bonus = verified_amount * (float(promo_percentage) / 100)
            total_with_bonus = verified_amount + promotion_bonus

            promotion_info = f"\n\n🎁 <b>PROMOTION BONUS</b>\n" \
                           f"Bonus: {promo_percentage}% = <b>{currency} {promotion_bonus:,.2f}</b>\n" \
                           f"Total with bonus: <b>{currency} {total_with_bonus:,.2f}</b>\n" \
                           f"<i>User's first deposit during promotion period</i>"

            # Store promotion info in context for approval handler
            context.bot_data[f'promo_{request_id}'] = {
                'promotion_id': promo_id,
                'bonus_amount': promotion_bonus,
                'deposit_amount': verified_amount,
                'pppoker_id': pppoker_id,
                'user_id': user.id,
                'currency': currency
            }

    # Build clean, organized notification
    if method == 'USDT':
        # Special format for USDT with TXID
        admin_message = f"""💰 <b>NEW {method} DEPOSIT</b> — {request_id}

👤 <b>USER DETAILS</b>
Name: {user.first_name} {user.last_name or ''}
Username: {username_display}
User ID: <code>{user.id}</code>

🏦 <b>TRANSACTION DETAILS</b>
🔗 TXID: <code>{ref_number}</code>
Amount: {amount_display}
Method: {verified_bank} (BEP20)

🎮 <b>PPPOKER INFO</b>
Player ID: <code>{pppoker_id}</code>

💡 <i>Verify TXID on BscScan.com</i>{validation_warnings}{promotion_info}"""
    else:
        # Regular deposit format
        admin_message = f"""💰 <b>NEW {method} DEPOSIT</b> — {request_id}

👤 <b>USER DETAILS</b>
Name: {user.first_name} {user.last_name or ''}
Username: {username_display}
User ID: <code>{user.id}</code>

🏦 <b>TRANSACTION DETAILS</b>
Reference: <code>{ref_number}</code>
Amount: {amount_display}
Bank: {verified_bank}
From: {sender_name}
To: {receiver_name}

🎮 <b>PPPOKER INFO</b>
Player ID: <code>{pppoker_id}</code>

📸 <i>Payment slip attached below</i>{validation_warnings}{promotion_info}"""

    # Create approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_deposit_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quick_reject_deposit_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send notification to all admins
    photo_file_id = context.user_data.get('photo_file_id')
    document_file_id = context.user_data.get('document_file_id')

    # Get all admin IDs (avoid duplicates)
    all_admin_ids = [ADMIN_USER_ID]
    try:
        regular_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(regular_admins_response, dict) and 'results' in regular_admins_response:
            regular_admins = regular_admins_response['results']
        else:
            regular_admins = regular_admins_response

        logger.info(f"Found {len(regular_admins)} regular admins in database")

        # Add admins from database, but skip if already in list (avoid duplicate super admin)
        for admin in regular_admins:
            admin_telegram_id = admin['telegram_id']
            if admin_telegram_id not in all_admin_ids:
                all_admin_ids.append(admin_telegram_id)

        logger.info(f"Total admin IDs to notify: {all_admin_ids}")
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Initialize list to store all notification message IDs
    notification_messages[request_id] = []

    # Send to each admin
    for admin_id in all_admin_ids:
        try:
            # Send notification message with HTML for better formatting
            notification_msg = await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            # Store notification message_id for ALL admins (for editing when any admin approves/rejects)
            notification_messages[request_id].append((admin_id, notification_msg.message_id))
            logger.info(f"Deposit notification sent to admin {admin_id} for {request_id}")

            # Forward proof to admin if it's a photo/document
            if photo_file_id:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_file_id,
                    caption=f"📸 Deposit Proof for {request_id}"
                )
                logger.info(f"Deposit photo sent to admin {admin_id} for {request_id}")
            elif document_file_id:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=document_file_id,
                    caption=f"📎 Deposit Proof for {request_id}"
                )
                logger.info(f"Deposit document sent to admin {admin_id} for {request_id}")
        except Exception as e:
            logger.error(f"Failed to send deposit notification to admin {admin_id}: {e}")

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


async def deposit_account_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle account name input for deposit"""
    account_name = update.message.text.strip()
    context.user_data['deposit_account_name'] = account_name

    # Update user's account name
    api.update_user_account_name(update.effective_user.id, account_name)

    method = context.user_data['deposit_method']

    if method == 'USDT':
        await update.message.reply_text(
            "📝 Please send your **Transaction ID (TXID)** from the blockchain:"
        )
    else:
        await update.message.reply_text(
            "📸 Please upload your **payment slip** (screenshot or photo):"
        )

    return DEPOSIT_PROOF


async def deposit_proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit proof upload with Vision API OCR - extracts details and asks for PPPoker ID"""
    user = update.effective_user
    method = context.user_data['deposit_method']

    # Variables for extracted details
    extracted_details = None
    transaction_ref = None

    # Get transaction reference and process image if uploaded
    if update.message.photo:
        # Photo uploaded - get file ID and download for processing
        photo = update.message.photo[-1]  # Get highest resolution
        photo_file_id = photo.file_id
        transaction_ref = f"Photo: {photo_file_id}"  # Default to file ID

        # Send processing message
        processing_msg = await update.message.reply_text("🔍 Processing receipt... Please wait...")

        try:
            # Download photo
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()

            # Process with Vision API
            extracted_details = await vision_api.process_receipt_image(bytes(file_bytes))

            # Delete processing message
            await processing_msg.delete()

            # Show extracted details to user
            details_msg = vision_api.format_extracted_details(extracted_details)

            # Check if any details were actually extracted
            has_details = any([
                extracted_details['reference_number'],
                extracted_details['amount'],
                extracted_details['bank'],
                extracted_details['sender_name'],
                extracted_details['receiver_name'],
                extracted_details.get('receiver_account_number')
            ])

            if has_details:
                await update.message.reply_text(
                    details_msg + "\n✅ _Details extracted successfully!_",
                    parse_mode='Markdown'
                )
                logger.info(f"Vision API extracted details for user {user.id}")

                # Use extracted reference number as transaction_ref if available
                if extracted_details['reference_number']:
                    transaction_ref = extracted_details['reference_number']
                    logger.info(f"Using extracted reference: {transaction_ref}")
            else:
                await update.message.reply_text(
                    details_msg + "\n⚠️ _Your receipt will be reviewed manually._",
                    parse_mode='Markdown'
                )
                logger.warning(f"Vision API could not parse details for user {user.id}")

        except Exception as e:
            logger.error(f"Vision API processing failed: {e}")
            await processing_msg.edit_text(
                "⚠️ Could not extract receipt details automatically.\n"
                "Your receipt has been saved and will be reviewed manually."
            )
            extracted_details = None

        # Store photo file ID separately for forwarding to admin
        context.user_data['photo_file_id'] = photo_file_id

    elif update.message.document:
        # Document uploaded
        document = update.message.document
        document_file_id = document.file_id
        transaction_ref = f"Document: {document_file_id}"  # Default to file ID

        # Check if it's an image document
        if document.mime_type and document.mime_type.startswith('image/'):
            processing_msg = await update.message.reply_text("🔍 Processing receipt... Please wait...")

            try:
                # Download document
                file = await context.bot.get_file(document.file_id)
                file_bytes = await file.download_as_bytearray()

                # Process with Vision API
                extracted_details = await vision_api.process_receipt_image(bytes(file_bytes))

                # Delete processing message
                await processing_msg.delete()

                # Show extracted details to user
                details_msg = vision_api.format_extracted_details(extracted_details)

                # Check if any details were actually extracted
                has_details = any([
                    extracted_details['reference_number'],
                    extracted_details['amount'],
                    extracted_details['bank'],
                    extracted_details['sender_name'],
                    extracted_details['receiver_name'],
                    extracted_details.get('receiver_account_number')
                ])

                if has_details:
                    await update.message.reply_text(
                        details_msg + "\n✅ _Details extracted successfully!_",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Vision API extracted details for user {user.id}")

                    # Use extracted reference number as transaction_ref if available
                    if extracted_details['reference_number']:
                        transaction_ref = extracted_details['reference_number']
                        logger.info(f"Using extracted reference: {transaction_ref}")
                else:
                    await update.message.reply_text(
                        details_msg + "\n⚠️ _Your receipt will be reviewed manually._",
                        parse_mode='Markdown'
                    )
                    logger.warning(f"Vision API could not parse details for user {user.id}")

            except Exception as e:
                logger.error(f"Vision API processing failed: {e}")
                await processing_msg.edit_text(
                    "⚠️ Could not extract receipt details automatically.\n"
                    "Your receipt has been saved and will be reviewed manually."
                )
                extracted_details = None

        # Store document file ID separately for forwarding to admin
        context.user_data['document_file_id'] = document_file_id

    elif update.message.text:
        # Text is only allowed for USDT (TXID)
        if method == 'USDT':
            transaction_ref = update.message.text.strip()
            # Store TXID
            context.user_data['transaction_ref'] = transaction_ref

            # Ask for amount next
            usdt_rate = api.get_exchange_rate('USDT', 'MVR') or 15.42  # Fallback to standard MVR rate
            rate_msg = f"\n\n💱 Current Rate: 1 USDT = {float(usdt_rate):.2f} MVR"

            await update.message.reply_text(
                f"✅ Transaction ID received!\n{rate_msg}\n\n"
                f"💎 Please enter the **amount you sent** (in USDT):\n\n"
                f"Example: 100 or 100.5",
                parse_mode='Markdown'
            )
            return DEPOSIT_USDT_AMOUNT
        else:
            # For BML/MIB, reject text and require image
            await update.message.reply_text(
                "❌ Please upload an **image** of your payment slip/receipt.\n\n"
                "📸 Send a photo or screenshot of your bank transfer slip.",
                parse_mode='Markdown'
            )
            return DEPOSIT_PROOF
    else:
        await update.message.reply_text("❌ Please send a valid payment proof (image).")
        return DEPOSIT_PROOF

    # Store transaction reference and extracted details in context
    context.user_data['transaction_ref'] = transaction_ref
    context.user_data['extracted_details'] = extracted_details

    # Now ask for PPPoker ID
    await update.message.reply_text(
        "🎮 Please enter your **PPPoker ID**:",
        parse_mode='Markdown'
    )

    return DEPOSIT_PPPOKER_ID


async def deposit_usdt_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle USDT amount input"""
    try:
        usdt_amount = float(update.message.text.replace(',', '').strip())
        if usdt_amount <= 0:
            raise ValueError("Amount must be positive")

        # Store USDT amount
        context.user_data['usdt_amount'] = usdt_amount

        # Get exchange rate and convert to MVR
        usdt_rate = api.get_exchange_rate('USDT', 'MVR') or 15.42  # Fallback to standard MVR rate
        usdt_rate = float(usdt_rate)  # Convert to float for calculations
        mvr_amount = usdt_amount * usdt_rate
        context.user_data['deposit_amount'] = mvr_amount  # Store MVR amount for deposit creation
        context.user_data['usdt_exchange_rate'] = usdt_rate

        await update.message.reply_text(
            f"✅ Amount received!\n\n"
            f"💎 {usdt_amount} USDT\n"
            f"💱 Rate: 1 USDT = {float(usdt_rate):.2f} MVR\n"
            f"💰 Equivalent: **{mvr_amount:,.2f} MVR**\n\n"
            f"🎮 Please enter your **PPPoker ID**:",
            parse_mode='Markdown'
        )

        return DEPOSIT_PPPOKER_ID

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number.\n\n"
            "Example: 100 or 100.5"
        )
        return DEPOSIT_USDT_AMOUNT


# Withdrawal Flow
async def withdrawal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal process"""
    # Check if counter is closed
    if await send_counter_closed_message(update):
        return ConversationHandler.END

    user_id = update.effective_user.id

    # Check if user has outstanding credit
    user_credit = api.get_user_credit(user_id)
    if user_credit and float(user_credit.get('amount', 0)) > 0:
        await update.message.reply_text(
            f"❌ <b>Cannot Withdraw - Outstanding Credit</b>\n\n"
            f"You have an unpaid credit:\n"
            f"💳 <b>Amount Owed:</b> {user_credit['amount']:,.2f} MVR\n"
            f"📅 <b>Since:</b> {user_credit['created_at']}\n\n"
            f"Please pay your credit before requesting withdrawal.\n"
            f"Contact admin for payment details.",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    user_data = api.get_user(user_id)

    # Check if user has balance to withdraw
    if not user_data or float(user_data.get('balance', 0)) <= 0:
        await update.message.reply_text(
            "⚠️ You don't have any balance to withdraw.\n"
            "Please make a deposit first."
        )
        return ConversationHandler.END

    # Get all configured payment accounts
    payment_accounts = api.get_all_payment_accounts()

    # Build keyboard with only configured payment methods
    keyboard = []
    if 'BML' in payment_accounts and payment_accounts['BML']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 BML", callback_data="withdrawal_bml")])
    if 'MIB' in payment_accounts and payment_accounts['MIB']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 MIB", callback_data="withdrawal_mib")])
    if 'USD' in payment_accounts and payment_accounts['USD']['account_number']:
        keyboard.append([InlineKeyboardButton("💵 USD", callback_data="withdrawal_usd")])
    if 'USDT' in payment_accounts and payment_accounts['USDT']['account_number']:
        keyboard.append([InlineKeyboardButton("💎 USDT (BEP20)", callback_data="withdrawal_usdt")])

    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    # Check if any payment methods are configured
    if len(keyboard) == 1:  # Only cancel button
        await update.message.reply_text(
            "⚠️ No payment methods are currently available.\n\n"
            "Please contact admin for assistance.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Show account name if available (from regular deposits)
    account_name_text = ""
    if user_data.get('account_name'):
        account_name_text = f"**Registered Account Name:** {user_data['account_name']}\n\n⚠️ Withdrawals will only be sent to accounts with this name.\n\n"

    await update.message.reply_text(
        f"💸 **Withdrawal from Billionaires Club**\n\n"
        f"{account_name_text}"
        f"Please select your payment method:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return WITHDRAWAL_METHOD


async def withdrawal_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal method selection"""
    query = update.callback_query
    await query.answer()

    method = query.data.replace('withdrawal_', '').upper()
    context.user_data['withdrawal_method'] = method

    method_names = {'BML': 'Bank of Maldives', 'MIB': 'Maldives Islamic Bank', 'USD': 'USD Bank Transfer', 'USDT': 'USDT (BEP20)'}

    message = f"💸 <b>Withdrawal via {method_names[method]}</b>\n\n"

    # Show exchange rate for USD/USDT
    if method == 'USD':
        usd_rate = api.get_exchange_rate('USD', 'MVR')
        if usd_rate:
            message += f"💱 <b>Current Rate:</b> 1 USD = {float(usd_rate):.2f} MVR\n\n"
    elif method == 'USDT':
        usdt_rate = api.get_exchange_rate('USDT', 'MVR')
        if usdt_rate:
            message += f"💱 <b>Current Rate:</b> 1 USDT = {float(usdt_rate):.2f} MVR\n\n"

    message += f"Please enter the amount you want to withdraw (in {'USD' if method in ['USD', 'USDT'] else 'MVR'}):"

    await query.edit_message_text(message, parse_mode='HTML')

    return WITHDRAWAL_AMOUNT


async def withdrawal_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal amount input"""
    try:
        amount = float(update.message.text.replace(',', ''))
        if amount <= 0:
            raise ValueError("Amount must be positive")

        context.user_data['withdrawal_amount'] = amount

        await update.message.reply_text(
            "🎮 Please enter your **PPPoker ID**:",
            parse_mode='Markdown'
        )

        return WITHDRAWAL_PPPOKER_ID

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number (e.g., 1000 or 1000.50):"
        )
        return WITHDRAWAL_AMOUNT


async def withdrawal_pppoker_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PPPoker ID input for withdrawal"""
    raw_input = update.message.text.strip()

    # Clean PPPoker ID (remove spaces, letters, special characters)
    pppoker_id = clean_pppoker_id(raw_input)

    # Validate that we have a valid number
    if not pppoker_id or len(pppoker_id) < 3:
        await update.message.reply_text(
            "❌ Invalid PPPoker ID. Please enter only numbers (at least 3 digits):",
            parse_mode='HTML'
        )
        return WITHDRAWAL_PPPOKER_ID

    context.user_data['withdrawal_pppoker_id'] = pppoker_id

    method = context.user_data['withdrawal_method']

    if method == 'USDT':
        await update.message.reply_text(
            "💎 Please enter your **USDT wallet address** (BEP20):\n\n"
            "⚠️ Make sure the address is correct! Transactions cannot be reversed.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"🏦 Please enter your **{method} account number**:\n\n"
            "⚠️ Make sure the account number is correct!",
            parse_mode='Markdown'
        )

    return WITHDRAWAL_ACCOUNT_NUMBER


async def withdrawal_account_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal account number input"""
    user = update.effective_user
    user_data = api.get_user(user.id)

    account_number = update.message.text.strip()
    method = context.user_data['withdrawal_method']
    amount = context.user_data['withdrawal_amount']
    pppoker_id = context.user_data['withdrawal_pppoker_id']

    # Get account name from most recent deposit (including seat deposits now)
    try:
        deposits = api.get_user_deposits(user.id)
        # Get deposits with valid account names (seat deposits now have extracted sender names)
        valid_deposits = [d for d in deposits if d.get('account_name') and d.get('account_name') not in ['Seat Payment', '']]
        if valid_deposits:
            # Use the most recent deposit's account name
            account_name = valid_deposits[0].get('account_name')
        else:
            # Fallback to User profile account_name
            account_name = user_data.get('account_name') or user_data.get('username', 'User')
    except Exception as e:
        logger.error(f"Error getting account name from deposits: {e}")
        # Fallback to User profile
        account_name = user_data.get('account_name') or user_data.get('username', 'User')

    # Create withdrawal request
    withdrawal_response = api.create_withdrawal_request(
        telegram_id=user.id,
        amount=amount,
        method=method,
        account_name=account_name,
        account_number=account_number,
        pppoker_id=pppoker_id
    )
    request_id = withdrawal_response.get('id') if isinstance(withdrawal_response, dict) else withdrawal_response

    # Send confirmation to user
    currency = 'MVR' if method != 'USDT' else 'USD'
    await update.message.reply_text(
        f"✅ <b>Withdrawal sent!</b>\n\n"
        f"💸 {amount} {currency} to {method}\n"
        f"👤 Account Name: {account_name}\n"
        f"🏦 Account Number: {account_number}\n\n"
        f"Processing now.",
        parse_mode='HTML'
    )

    # Send notification to admin with approval buttons
    username_display = f"@{user.username}" if user.username else "No username"

    admin_message = f"""🔔 <b>NEW WITHDRAWAL REQUEST</b>

<b>Request ID:</b> {request_id}
<b>User:</b> {user.first_name} {user.last_name or ''}
<b>Username:</b> {username_display}
<b>User ID:</b> {user.id}
<b>Amount:</b> {amount} {'MVR' if method != 'USDT' else 'USD'}
<b>Method:</b> {method}
<b>PPPoker ID:</b> <a href='#'>(tap to copy)</a>
<code>{pppoker_id}</code>
<b>Account Name:</b> {account_name}
<b>Account Number:</b> <a href='#'>(tap to copy)</a>
<code>{account_number}</code>
"""

    # Create approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_withdrawal_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quick_reject_withdrawal_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send notification to all admins
    all_admin_ids = [ADMIN_USER_ID]
    try:
        regular_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(regular_admins_response, dict) and 'results' in regular_admins_response:
            regular_admins = regular_admins_response['results']
        else:
            regular_admins = regular_admins_response

        logger.info(f"Found {len(regular_admins)} regular admins in database")

        # Add admins from database, but skip if already in list (avoid duplicate super admin)
        for admin in regular_admins:
            admin_telegram_id = admin['telegram_id']
            if admin_telegram_id not in all_admin_ids:
                all_admin_ids.append(admin_telegram_id)

        logger.info(f"Total admin IDs to notify: {all_admin_ids}")
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Initialize list to store all notification message IDs
    notification_messages[request_id] = []

    for admin_id in all_admin_ids:
        try:
            notification_msg = await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            # Store notification message_id for ALL admins
            notification_messages[request_id].append((admin_id, notification_msg.message_id))
            logger.info(f"Withdrawal notification sent to admin {admin_id} for {request_id}")
        except Exception as e:
            logger.error(f"Failed to send withdrawal notification to admin {admin_id}: {e}")

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


# Join Club Flow
async def join_club_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start join club process - show club info with button"""
    # Check if counter is closed
    if await send_counter_closed_message(update):
        return ConversationHandler.END

    club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"

    # Create button to open club directly
    keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = """🎰 <b>JOIN BILLIONAIRES CLUB</b> 🎰

<b>Club ID:</b> <a href='#'>(tap to copy)</a>
<code>370625</code>

<b>Club Name:</b> βILLIONAIRES

━━━━━━━━━━━━━━━━━━

<b>📋 How to Join:</b>

1️⃣ Tap the button below to open the club
2️⃣ Or manually search club ID: <code>370625</code>
3️⃣ Request to join the club
4️⃣ Enter your PPPoker ID here

━━━━━━━━━━━━━━━━━━

Please enter your <b>PPPoker ID</b> to complete your join request:"""

    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return JOIN_PPPOKER_ID


async def join_pppoker_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PPPoker ID input for join request"""
    user = update.effective_user
    raw_input = update.message.text.strip()

    # Clean PPPoker ID (remove spaces, letters, special characters)
    pppoker_id = clean_pppoker_id(raw_input)

    # Validate that we have a valid number
    if not pppoker_id or len(pppoker_id) < 3:
        await update.message.reply_text(
            "❌ Invalid PPPoker ID. Please enter only numbers (at least 3 digits):",
            parse_mode='HTML'
        )
        return JOIN_PPPOKER_ID

    # Get or create user in database to get their database ID
    user_data = api.get_or_create_user(user.id, user.username or user.first_name or str(user.id))
    db_user_id = user_data.get('id')

    # Create join request
    join_response = api.create_join_request(
        user_id=db_user_id,
        pppoker_id=pppoker_id
    )
    request_id = join_response.get('id') if isinstance(join_response, dict) else join_response

    # Update user's PPPoker ID
    api.update_user_pppoker_id(user.id, pppoker_id)

    # Send confirmation to user
    await update.message.reply_text(
        f"✅ <b>Join request sent!</b>\n\n"
        f"🎮 ID: {pppoker_id}\n\n"
        f"Admin will review shortly.",
        parse_mode='HTML'
    )

    # Send notification to admin with approval buttons
    username_display = f"@{user.username}" if user.username else "No username"

    admin_message = f"""🔔 <b>NEW CLUB JOIN REQUEST</b>

<b>Request ID:</b> {request_id}
<b>User:</b> {user.first_name} {user.last_name or ''}
<b>Username:</b> {username_display}
<b>User ID:</b> {user.id}
<b>PPPoker ID:</b> <a href='#'>(tap to copy)</a>
<code>{pppoker_id}</code>
"""

    # Create approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_join_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quick_reject_join_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send notification to all admins
    all_admin_ids = [ADMIN_USER_ID]
    try:
        regular_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(regular_admins_response, dict) and 'results' in regular_admins_response:
            regular_admins = regular_admins_response['results']
        else:
            regular_admins = regular_admins_response

        logger.info(f"Found {len(regular_admins)} regular admins in database")

        # Add admins from database, but skip if already in list (avoid duplicate super admin)
        for admin in regular_admins:
            admin_telegram_id = admin['telegram_id']
            if admin_telegram_id not in all_admin_ids:
                all_admin_ids.append(admin_telegram_id)

        logger.info(f"Total admin IDs to notify: {all_admin_ids}")
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Initialize list to store all notification message IDs
    notification_messages[request_id] = []

    for admin_id in all_admin_ids:
        try:
            notification_msg = await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            # Store notification message_id for ALL admins
            notification_messages[request_id].append((admin_id, notification_msg.message_id))
            logger.info(f"Join request notification sent to admin {admin_id} for {request_id}")
        except Exception as e:
            logger.error(f"Failed to send join notification to admin {admin_id}: {e}")

    return ConversationHandler.END


# ========== CASHBACK FLOW ==========
CASHBACK_PPPOKER_ID = 100

async def cashback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start cashback request flow"""
    # Check if counter is closed
    if await send_counter_closed_message(update):
        return ConversationHandler.END

    user = update.effective_user
    logger.info(f"Cashback button clicked by user {user.id} ({user.username or user.first_name})")

    # Check if user has outstanding credit
    try:
        user_credit = api.get_user_credit(user.id)
        if user_credit and float(user_credit.get('amount', 0)) > 0:
            credit_amount = float(user_credit['amount'])
            await update.message.reply_text(
                f"❌ <b>Cannot Request Cashback - Outstanding Credit</b>\n\n"
                f"You have an unpaid credit:\n"
                f"💳 <b>Amount Owed:</b> {credit_amount:,.2f} MVR\n"
                f"📅 <b>Since:</b> {user_credit['created_at']}\n\n"
                f"Please pay your credit before requesting cashback.\n"
                f"Contact admin for payment details.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking user credit: {e}")

    try:
        # Check if there's an active CASHBACK promotion (separate from bonus)
        cashback_promo = api.get_active_cashback_promotion()
    except Exception as e:
        logger.error(f"Error getting active cashback promotion: {e}")
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Sorry, there was an error checking for active promotions.\n"
            "Please try again later or contact support.",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    if not cashback_promo:
        await update.message.reply_text(
            "❌ <b>Cashback Not Available</b>\n\n"
            "Sorry, there is no active cashback promotion at the moment.\n"
            "Please check back later!",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    cashback_percentage = float(cashback_promo.get('percentage', 0))
    promotion_id = cashback_promo.get('id')

    try:
        # Check if user already has a pending cashback request for this promotion
        pending_requests = api.get_user_pending_cashback(user.id)
        pending_for_promo = [r for r in pending_requests if r.get('promotion_id') == promotion_id]
    except Exception as e:
        logger.error(f"Error getting pending cashback requests: {e}")
        await update.message.reply_text(
            "❌ <b>Error</b>\n\n"
            "Sorry, there was an error checking your pending requests.\n"
            "Please try again later or contact support.",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    if pending_for_promo:
        await update.message.reply_text(
            f"❌ <b>Pending Cashback Request Exists</b>\n\n"
            f"You already have a pending cashback request for this promotion.\n\n"
            f"🎫 Request ID: <code>{pending_for_promo[0]['request_id']}</code>\n"
            f"💰 Amount: <b>{pending_for_promo[0]['cashback_amount']:.2f} MVR</b>\n\n"
            f"⏳ Please wait for admin approval before submitting another request.\n\n"
            f"💡 <i>You can only have one pending request per promotion period.</i>",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    try:
        # Check eligibility (both loss requirement and if already claimed)
        eligibility = api.check_cashback_eligibility(user.id, promotion_id, min_deposit=500)
    except Exception as e:
        import traceback
        logger.error(f"Error checking cashback eligibility: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n"
            f"Sorry, there was an error checking your eligibility.\n"
            f"Error: {str(e)}\n\n"
            f"Please contact admin.",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    if not eligibility['eligible']:
        current_deposits = eligibility['current_deposits']
        current_withdrawals = eligibility['current_withdrawals']
        total_spin_rewards = eligibility.get('total_spin_rewards', 0)
        total_bonuses = eligibility.get('total_bonuses', 0)
        total_cashback = eligibility.get('total_cashback', 0)
        club_profit = eligibility.get('club_profit', 0)
        user_loss = eligibility.get('user_loss', 0)
        effective_new_deposits = eligibility['effective_new_deposits']
        last_claim_deposits = eligibility['last_claim_deposits']
        baseline = eligibility['baseline']
        min_required = eligibility['min_required']
        deposits_exceed_withdrawals = eligibility['deposits_exceed_withdrawals']
        already_claimed = eligibility.get('already_claimed', False)

        # Check if user is in profit (considering all chip sources)
        if not deposits_exceed_withdrawals:
            message = f"❌ <b>Not Eligible for Cashback</b>\n\n"
            message += f"You are currently in profit, not at a loss.\n\n"
            message += f"💰 Your Balance:\n"
            message += f"   Deposits: {current_deposits:.2f} MVR\n"
            message += f"   Withdrawals: {current_withdrawals:.2f} MVR\n"
            if total_spin_rewards > 0:
                message += f"   Spin Wins: {total_spin_rewards:.2f} MVR\n"
            if total_bonuses > 0:
                message += f"   Bonuses: {total_bonuses:.2f} MVR\n"
            if total_cashback > 0:
                message += f"   Cashback: {total_cashback:.2f} MVR\n"

            message += f"\n💡 <i>Cashback is only available for users at a net loss.</i>"

            await update.message.reply_text(message, parse_mode='HTML')
            return ConversationHandler.END

        # User is at a loss but doesn't have enough effective new deposits
        needed = min_required - effective_new_deposits

        message = f"❌ <b>Insufficient New Deposits</b>\n\n"
        message += f"New deposits required: <b>{min_required:.2f} MVR</b>\n"
        message += f"Your new deposits: <b>{effective_new_deposits:.2f} MVR</b>\n"
        message += f"Deposit <b>{needed:.2f} MVR</b> more to qualify.\n\n"
        message += f"💡 <i>Minimum {min_required:.2f} MVR in new deposits required.</i>"

        await update.message.reply_text(message, parse_mode='HTML')
        return ConversationHandler.END

    # User is eligible - calculate cashback on effective new deposits
    effective_new_deposits = float(eligibility['effective_new_deposits'])
    cashback_amount = (effective_new_deposits * cashback_percentage) / 100

    message = f"✅ <b>Cashback Eligible!</b>\n\n"
    message += f"💎 Cashback Rate: <b>{cashback_percentage}%</b>\n"
    message += f"💰 Cashback Amount: <b>{cashback_amount:.2f} MVR</b>\n"
    message += f"   (on {effective_new_deposits:.2f} MVR deposits)\n\n"
    message += f"📝 Enter your <b>PPPoker ID</b> to submit:"

    await update.message.reply_text(
        message,
        parse_mode='HTML'
    )

    # Store deposit amount and cashback details in context
    context.user_data['cashback_loss'] = effective_new_deposits
    context.user_data['cashback_percentage'] = cashback_percentage
    context.user_data['cashback_amount'] = cashback_amount
    context.user_data['cashback_promotion_id'] = promotion_id

    return CASHBACK_PPPOKER_ID


async def cashback_pppoker_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive PPPoker ID and submit cashback request"""
    user = update.effective_user
    raw_input = update.message.text.strip()

    # Clean PPPoker ID (remove spaces, letters, special characters)
    pppoker_id = clean_pppoker_id(raw_input)

    # Validate PPPoker ID (basic validation)
    if not pppoker_id or len(pppoker_id) < 3:
        await update.message.reply_text(
            "❌ Invalid PPPoker ID. Please enter only numbers (at least 3 digits):",
            parse_mode='HTML'
        )
        return CASHBACK_PPPOKER_ID

    # Get cashback details from context
    loss_amount = context.user_data.get('cashback_loss')
    cashback_percentage = context.user_data.get('cashback_percentage')
    cashback_amount = context.user_data.get('cashback_amount')
    promotion_id = context.user_data.get('cashback_promotion_id')

    # Create cashback request
    request_data = api.create_cashback_request(
        user_id=user.id,
        username=user.username or user.first_name,
        pppoker_id=pppoker_id,
        loss_amount=loss_amount,
        cashback_amount=cashback_amount,
        cashback_percentage=cashback_percentage,
        promotion_id=promotion_id
    )

    if request_data:
        request_id = request_data.get('id')
        # Notify user
        await update.message.reply_text(
            f"✅ <b>Cashback request sent!</b>\n\n"
            f"💎 {cashback_amount:.2f} MVR ({cashback_percentage}%)\n"
            f"📉 Loss: {loss_amount:.2f} MVR\n\n"
            f"Awaiting approval.",
            parse_mode='HTML'
        )

        # Notify all admins
        asyncio.create_task(notify_admins_cashback_request(
            context=context,
            user_id=user.id,
            username=user.username or user.first_name,
            request_id=request_id,
            loss_amount=loss_amount,
            cashback_percentage=cashback_percentage,
            cashback_amount=cashback_amount,
            pppoker_id=pppoker_id
        ))

    else:
        await update.message.reply_text(
            "❌ <b>Error</b>\n\nFailed to submit cashback request. Please try again later.",
            parse_mode='HTML'
        )

    # Clear context data
    context.user_data.clear()
    return ConversationHandler.END


async def notify_admins_cashback_request(context, user_id: int, username: str, request_id: int,
                                        loss_amount: float, cashback_percentage: float,
                                        cashback_amount: float, pppoker_id: str):
    """Notify all admins about new cashback request"""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        message = (
            f"💸 <b>CASHBACK REQUEST</b> 💸\n\n"
            f"👤 User: {username} (ID: {user_id})\n"
            f"🎫 Request ID: <code>{request_id}</code>\n\n"
            f"📊 Loss Amount: <b>{loss_amount:.2f} MVR</b>\n"
            f"💰 Cashback Rate: <b>{cashback_percentage}%</b>\n"
            f"💎 Cashback Amount: <b>{cashback_amount:.2f} MVR</b>\n"
            f"🎮 PPPoker ID: <b>{pppoker_id}</b>"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"cashback_approve_{request_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"cashback_reject_{request_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Initialize notification messages list for this request
        notification_messages[request_id] = []

        # Send to super admin
        try:
            msg = await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            # Store message ID
            notification_messages[request_id].append((ADMIN_USER_ID, msg.message_id))
            logger.info(f"✅ Super admin notified about cashback request {request_id}")
        except Exception as e:
            logger.error(f"❌ Failed to notify super admin: {e}")

        # Send to all regular admins
        try:
            admins_response = api.get_all_admins()

            # Handle paginated response from Django API
            if isinstance(admins_response, dict) and 'results' in admins_response:
                admins = admins_response['results']
            else:
                admins = admins_response

            for admin in admins:
                try:
                    msg = await context.bot.send_message(
                        chat_id=admin['telegram_id'],
                        text=message,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    # Store message ID
                    notification_messages[request_id].append((admin['telegram_id'], msg.message_id))
                    logger.info(f"✅ Admin {admin['telegram_id']} notified about cashback request {request_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to notify admin {admin['telegram_id']}: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to get admin list: {e}")

    except Exception as e:
        logger.error(f"❌ Failed to notify admins about cashback: {e}")


# My Info Command
async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user information"""
    user = update.effective_user
    user_data = api.get_user(user.id)

    if not user_data:
        await update.message.reply_text("❌ No user data found. Please use /start first.")
        return

    info_text = f"""
📊 **Your Information**

**Name:** {user.first_name} {user.last_name or ''}
**Username:** @{user.username or 'Not set'}
**User ID:** `{user.id}`
**PPPoker ID:** {user_data.get('pppoker_id') or 'Not set'}
**Account Name:** {user_data.get('account_name') or 'Not set'}
**Status:** {user_data.get('status', 'Active')}
**Registered:** {user_data.get('registered_at', 'N/A')}
"""

    await update.message.reply_text(info_text, parse_mode='Markdown')


# Seat Request Flow
async def seat_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start seat request process"""
    # Check if counter is closed
    if await send_counter_closed_message(update):
        return ConversationHandler.END

    user = update.effective_user

    # Check if user has active credit
    existing_credit = api.get_user_credit(user.id)
    if existing_credit:
        await update.message.reply_text(
            f"⚠️ **You already have an active credit!**\n\n"
            f"💰 Credit Amount: {existing_credit['amount']} chips/MVR\n"
            f"📅 Created: {existing_credit['created_at']}\n\n"
            f"Please settle your existing credit before requesting a new seat.\n"
            f"Contact Live Support.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # Get user's PPPoker ID from last deposit
    pppoker_id = None
    try:
        deposits = api.get_all_deposits()
        if isinstance(deposits, dict) and 'results' in deposits:
            deposits = deposits['results']

        # Filter approved deposits for this user
        user_deposits = [d for d in deposits if d.get('user_details', {}).get('telegram_id') == user.id and d.get('status') == 'Approved']

        if user_deposits:
            # Get PPPoker ID from most recent deposit
            pppoker_id = user_deposits[0].get('pppoker_id')
    except Exception as e:
        logger.error(f"Error fetching deposits for PPPoker ID: {e}")

    if not pppoker_id:
        await update.message.reply_text(
            "❌ **No PPPoker ID found!**\n\n"
            "Please make a deposit first to register your PPPoker ID.\n"
            "Use /start and select 💰 Deposit.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # Store PPPoker ID in context for later use
    context.user_data['seat_pppoker_id'] = pppoker_id

    await update.message.reply_text(
        "🪑 **Seat Request**\n\n"
        "Please enter the amount of chips you want:",
        parse_mode='Markdown'
    )

    return SEAT_AMOUNT


async def seat_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle seat amount input"""
    user = update.effective_user

    try:
        amount = float(update.message.text.strip())

        if amount <= 0:
            await update.message.reply_text(
                "❌ Please enter a valid amount greater than 0.",
                parse_mode='Markdown'
            )
            return SEAT_AMOUNT

        # Get PPPoker ID from context (already fetched from last deposit)
        pppoker_id = context.user_data.get('seat_pppoker_id', '')

        # Get database user ID
        user_data = api.get_user_by_telegram_id(user.id)
        if not user_data:
            await update.message.reply_text(
                "❌ User not found. Please use /start first.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        db_user_id = user_data.get('id')

        # Create seat request
        seat_response = api.create_seat_request(
            user_id=db_user_id,
            amount=amount,
            slip_image_path='',  # Seat requests don't have slip initially
            pppoker_id=pppoker_id
        )
        request_id = seat_response.get('id') if isinstance(seat_response, dict) else seat_response

        # Store in context for later use
        context.user_data['seat_request_id'] = request_id
        context.user_data['seat_amount'] = amount
        context.user_data['seat_pppoker_id'] = pppoker_id

        # Send confirmation to user
        await update.message.reply_text(
            f"✅ <b>Seat request sent!</b>\n\n"
            f"🪑 {amount} chips\n"
            f"🎮 ID: {pppoker_id}\n\n"
            f"Admin will review shortly.",
            parse_mode='HTML'
        )

        # Send notification to all admins
        username_display = f"@{user.username}" if user.username else "No username"

        admin_message = f"""🪑 <b>NEW SEAT REQUEST</b>

<b>Request ID:</b> {request_id}
<b>User:</b> {user.first_name} {user.last_name or ''}
<b>Username:</b> {username_display}
<b>User ID:</b> <code>{user.id}</code>
<b>PPPoker ID:</b> <code>{pppoker_id}</code>
<b>Amount:</b> <b>{amount} chips/MVR</b>
"""

        # Create approval buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_seat_{request_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_seat_{request_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send to all admins (avoid duplicates)
        all_admin_ids = [ADMIN_USER_ID]
        try:
            regular_admins_response = api.get_all_admins()

            # Handle paginated response from Django API
            if isinstance(regular_admins_response, dict) and 'results' in regular_admins_response:
                regular_admins = regular_admins_response['results']
            else:
                regular_admins = regular_admins_response

            # Add admins from database, but skip if already in list (avoid duplicate super admin)
            for admin in regular_admins:
                admin_telegram_id = admin['telegram_id']
                if admin_telegram_id not in all_admin_ids:
                    all_admin_ids.append(admin_telegram_id)
        except Exception as e:
            logger.error(f"Failed to get admin list: {e}")

        # Store notification messages for button removal
        notification_messages[request_id] = []

        for admin_id in all_admin_ids:
            try:
                msg = await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                notification_messages[request_id].append((admin_id, msg.message_id))
            except Exception as e:
                logger.error(f"Failed to send seat request to admin {admin_id}: {e}")

        # Schedule auto-reject after 2 minutes if not processed
        job = context.job_queue.run_once(
            auto_reject_seat_request,
            when=120,  # 2 minutes
            data={'request_id': request_id, 'user_id': user.id, 'amount': amount, 'pppoker_id': pppoker_id},
            name=f"auto_reject_seat_{request_id}"
        )
        logger.info(f"Scheduled auto-reject for seat request {request_id} in 2 minutes")

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a number.",
            parse_mode='Markdown'
        )
        return SEAT_AMOUNT


# Live Support
async def live_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start live support session"""
    user = update.effective_user

    # Check if counter is open
    counter_status = api.get_counter_status()
    if not counter_status.get('is_open', True):
        await update.message.reply_text(
            "🔒 *COUNTER IS CLOSED*\n\n"
            "Live support is currently unavailable\\.\n"
            "Please try again when the counter reopens\\!\n\n"
            "Thank you for your patience\\! 🙏",
            parse_mode='MarkdownV2'
        )
        return ConversationHandler.END

    if user.id in support_mode_users:
        # Show End Support button
        keyboard = [[InlineKeyboardButton("❌ End Support", callback_data="user_end_support")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = await update.message.reply_text(
            "💬 You're already in a support session!\n\n"
            "Type your message and it will be sent to our admin.\n"
            "Click the button below to end the session.",
            reply_markup=reply_markup
        )

        # Track this message to remove button later
        if user.id not in user_support_message_ids:
            user_support_message_ids[user.id] = []
        user_support_message_ids[user.id].append(msg.message_id)

        return SUPPORT_CHAT

    support_mode_users.add(user.id)
    live_support_sessions[user.id] = ADMIN_USER_ID

    # Show End Support button
    keyboard = [[InlineKeyboardButton("❌ End Support", callback_data="user_end_support")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        "💬 **Live Support Session Started**\n\n"
        "You're now connected to our admin. Type your message below.\n\n"
        "Click the button below when you're done.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # Initialize tracking and store this message
    user_support_message_ids[user.id] = [msg.message_id]

    # Notify ALL admins
    all_admins_response = api.get_all_admins()

    # Handle paginated response from Django API
    if isinstance(all_admins_response, dict) and 'results' in all_admins_response:
        all_admins = all_admins_response['results']
    else:
        all_admins = all_admins_response

    admin_ids = [ADMIN_USER_ID]  # Start with super admin
    for admin in all_admins:
        if admin['telegram_id'] != ADMIN_USER_ID:
            admin_ids.append(admin['telegram_id'])

    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"💬 **New Support Session Started**\n\n"
                     f"User: {user.first_name} {user.last_name or ''} (@{user.username or 'No username'})\n"
                     f"User ID: `{user.id}`\n\n"
                     f"Waiting for user's message...",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    return SUPPORT_CHAT


async def live_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle live support messages"""
    user = update.effective_user

    if user.id not in support_mode_users:
        return ConversationHandler.END

    # Cancel timeout job if user responds
    if user.id in support_timeout_jobs:
        support_timeout_jobs[user.id].schedule_removal()
        del support_timeout_jobs[user.id]

    # Check if there's a handling admin (admin who clicked Reply)
    if user.id in active_support_handlers:
        # Only send to the handling admin
        handling_admin_id = active_support_handlers[user.id]
        message_text = f"💬 **Message from {user.first_name}** (@{user.username or 'No username'})\n\n_{update.message.text}_"

        # Create buttons for handling admin
        keyboard = [
            [
                InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user.id}"),
                InlineKeyboardButton("❌ End Chat", callback_data=f"support_end_{user.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Initialize tracking list if not exists
        if user.id not in support_message_ids:
            support_message_ids[user.id] = []

        try:
            msg = await context.bot.send_message(
                chat_id=handling_admin_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            # Track this message to remove buttons later
            support_message_ids[user.id].append((handling_admin_id, msg.message_id))
        except Exception as e:
            logger.error(f"Failed to send support message to handling admin {handling_admin_id}: {e}")
    else:
        # No handling admin yet, send to ALL admins
        message_text = f"💬 **Message from {user.first_name}** (@{user.username or 'No username'})\n\n_{update.message.text}_"

        # Create buttons for admin
        keyboard = [
            [
                InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user.id}"),
                InlineKeyboardButton("❌ End Chat", callback_data=f"support_end_{user.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send to all admins and track message IDs
        all_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(all_admins_response, dict) and 'results' in all_admins_response:
            all_admins = all_admins_response['results']
        else:
            all_admins = all_admins_response

        admin_ids = [ADMIN_USER_ID]  # Start with super admin
        for admin in all_admins:
            if admin['telegram_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['telegram_id'])

        # Initialize tracking list if not exists
        if user.id not in support_message_ids:
            support_message_ids[user.id] = []

        for admin_id in admin_ids:
            try:
                msg = await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                # Track this message to remove buttons later
                support_message_ids[user.id].append((admin_id, msg.message_id))
            except Exception as e:
                logger.error(f"Failed to send support message to admin {admin_id}: {e}")

    await update.message.reply_text("✅ Message sent to admins.")

    return SUPPORT_CHAT


async def end_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End live support session"""
    user = update.effective_user

    if user.id in support_mode_users:
        support_mode_users.remove(user.id)
        if user.id in live_support_sessions:
            del live_support_sessions[user.id]
        if user.id in active_support_handlers:
            del active_support_handlers[user.id]

        await update.message.reply_text("✅ Support session ended. Thank you!")

        # Notify ALL admins
        all_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(all_admins_response, dict) and 'results' in all_admins_response:
            all_admins = all_admins_response['results']
        else:
            all_admins = all_admins_response

        admin_ids = [ADMIN_USER_ID]  # Start with super admin
        for admin in all_admins:
            if admin['telegram_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['telegram_id'])

        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 Support session ended with {user.first_name} (@{user.username or 'No username'})"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    else:
        await update.message.reply_text("You're not in a support session.")

    return ConversationHandler.END


async def admin_reply_button_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin clicking Reply button - ANY admin can reply, first one locks the session"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    # Extract user_id from callback data
    user_id = int(query.data.split('_')[-1])

    # Check if another admin is already handling this session
    if user_id in active_support_handlers:
        handling_admin = active_support_handlers[user_id]
        if handling_admin != query.from_user.id:
            # Get admin info for better messaging
            handling_admin_info_response = api.get_all_admins()

            # Handle paginated response from Django API
            if isinstance(handling_admin_info_response, dict) and 'results' in handling_admin_info_response:
                handling_admin_info = handling_admin_info_response['results']
            else:
                handling_admin_info = handling_admin_info_response

            handler_name = "Another admin"
            for admin in handling_admin_info:
                if admin['telegram_id'] == handling_admin:
                    handler_name = admin.get('name', 'Another admin')
                    break

            await query.answer(
                f"⛔ {handler_name} is currently handling this chat. They must end it first.",
                show_alert=True
            )
            return

    await query.answer()

    # Check if user still in support session
    if user_id not in support_mode_users:
        await query.edit_message_text(
            f"{query.message.text}\n\n⚠️ _User has ended the support session._",
            parse_mode='Markdown'
        )
        return

    # Lock this session to this admin (first admin to reply gets the lock)
    active_support_handlers[user_id] = query.from_user.id
    logger.info(f"Admin {query.from_user.id} ({query.from_user.first_name}) locked support session with user {user_id}")

    # Notify other admins that this session is now locked
    all_admins_response = api.get_all_admins()

    # Handle paginated response from Django API
    if isinstance(all_admins_response, dict) and 'results' in all_admins_response:
        all_admins = all_admins_response['results']
    else:
        all_admins = all_admins_response

    admin_ids = [ADMIN_USER_ID]  # Start with super admin
    for admin in all_admins:
        if admin['telegram_id'] != ADMIN_USER_ID:
            admin_ids.append(admin['telegram_id'])

    admin_name = query.from_user.first_name
    for admin_id in admin_ids:
        if admin_id != query.from_user.id:  # Don't notify the admin who took it
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔒 {admin_name} is now handling support chat with user {user_id}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    # Store user_id for next message from admin
    admin_reply_context[query.from_user.id] = user_id

    await query.edit_message_text(
        f"{query.message.text}\n\n✏️ **Type your reply below:**\n_You are now handling this chat._",
        parse_mode='Markdown'
    )

    return ADMIN_REPLY_MESSAGE


async def admin_reply_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin's reply message"""
    if not is_admin(update.effective_user.id):
        return

    admin_id = update.effective_user.id

    if admin_id not in admin_reply_context:
        return

    user_id = admin_reply_context[admin_id]
    message = update.message.text

    # Check if user still in support
    if user_id not in support_mode_users:
        await update.message.reply_text("⚠️ User has ended the support session.")
        del admin_reply_context[admin_id]
        return

    try:
        # Show End Support button to user with the reply
        keyboard = [[InlineKeyboardButton("❌ End Support", callback_data="user_end_support")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send message to user
        msg = await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 **Admin:**\n\n{escape_markdown(message)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        # Track this user message to remove button later
        if user_id not in user_support_message_ids:
            user_support_message_ids[user_id] = []
        user_support_message_ids[user_id].append(msg.message_id)

        # Cancel existing timeout job if any
        if user_id in support_timeout_jobs:
            support_timeout_jobs[user_id].schedule_removal()
            del support_timeout_jobs[user_id]

        # Schedule auto-close after 2 minutes of user inactivity
        job = context.job_queue.run_once(
            auto_close_support,
            when=120,  # 2 minutes in seconds
            data=user_id,
            name=f"support_timeout_{user_id}"
        )
        support_timeout_jobs[user_id] = job

        await update.message.reply_text("✅ Message sent! Session will auto-close in 2 minutes if user doesn't respond.")

        # Clear context
        del admin_reply_context[admin_id]

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send: {e}")
        if admin_id in admin_reply_context:
            del admin_reply_context[admin_id]


async def admin_end_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin clicking End Chat button - ANY admin can end if not locked, or handling admin can end"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    user_id = int(query.data.split('_')[-1])

    # Check if another admin is actively handling this session
    if user_id in active_support_handlers:
        handling_admin = active_support_handlers[user_id]
        if handling_admin != query.from_user.id:
            # Get admin info for better messaging
            handling_admin_info_response = api.get_all_admins()

            # Handle paginated response from Django API
            if isinstance(handling_admin_info_response, dict) and 'results' in handling_admin_info_response:
                handling_admin_info = handling_admin_info_response['results']
            else:
                handling_admin_info = handling_admin_info_response

            handler_name = "Another admin"
            for admin in handling_admin_info:
                if admin['telegram_id'] == handling_admin:
                    handler_name = admin.get('name', 'Another admin')
                    break

            await query.answer(
                f"⛔ {handler_name} is actively chatting with this user. They must end it first.",
                show_alert=True
            )
            return

    await query.answer()
    logger.info(f"Admin {query.from_user.id} ({query.from_user.first_name}) ending support session with user {user_id}")

    if user_id in support_mode_users:
        support_mode_users.remove(user_id)
        if user_id in live_support_sessions:
            del live_support_sessions[user_id]
        if user_id in active_support_handlers:
            del active_support_handlers[user_id]

        # Cancel timeout job if exists
        if user_id in support_timeout_jobs:
            support_timeout_jobs[user_id].schedule_removal()
            del support_timeout_jobs[user_id]

        # Remove all End Chat buttons from admin messages
        if user_id in support_message_ids:
            for admin_id, message_id in support_message_ids[user_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
            # Clean up tracked messages
            del support_message_ids[user_id]

        # Remove all End Support buttons from user messages
        if user_id in user_support_message_ids:
            for message_id in user_support_message_ids[user_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=user_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove End Support button from user message {message_id}: {e}")
            # Clean up tracked user messages
            del user_support_message_ids[user_id]

        # Notify user (without button since session is ended)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="💬 **Support session ended by admin.**\n\nThank you for contacting us!",
                parse_mode='Markdown'
            )
        except:
            pass

        # Edit admin's message to remove button
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ _Chat ended by admin._",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            f"{query.message.text}\n\n⚠️ _User already ended the session._",
            parse_mode='Markdown'
        )


async def user_end_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user clicking End Support button"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if user.id in support_mode_users:
        support_mode_users.remove(user.id)
        if user.id in live_support_sessions:
            del live_support_sessions[user.id]
        if user.id in active_support_handlers:
            del active_support_handlers[user.id]

        # Cancel timeout job if exists
        if user.id in support_timeout_jobs:
            support_timeout_jobs[user.id].schedule_removal()
            del support_timeout_jobs[user.id]

        # Remove all End Chat buttons from admin messages
        if user.id in support_message_ids:
            for admin_id, message_id in support_message_ids[user.id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
            # Clean up tracked messages
            del support_message_ids[user.id]

        # Remove all End Support buttons from ALL user messages
        if user.id in user_support_message_ids:
            for message_id in user_support_message_ids[user.id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=user.id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove End Support button from user message {message_id}: {e}")
            # Clean up tracked messages
            del user_support_message_ids[user.id]

        # Edit the clicked message to show session ended
        await query.edit_message_text(
            "✅ **Support session ended.**\n\nThank you! Feel free to start a new session anytime.",
            parse_mode='Markdown'
        )

        # Notify ALL admins
        all_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(all_admins_response, dict) and 'results' in all_admins_response:
            all_admins = all_admins_response['results']
        else:
            all_admins = all_admins_response

        admin_ids = [ADMIN_USER_ID]  # Start with super admin
        for admin in all_admins:
            if admin['telegram_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['telegram_id'])

        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 **Support session ended**\n\n"
                         f"User: {user.first_name} (@{user.username or 'No username'}) ended the chat.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    else:
        await query.edit_message_text("You're not in a support session.")

    return ConversationHandler.END


async def auto_close_support(context: ContextTypes.DEFAULT_TYPE):
    """Auto-close support session after 2 minutes of user inactivity"""
    user_id = context.job.data

    if user_id not in support_mode_users:
        # Already closed
        return

    # Get handling admin
    handling_admin_id = active_support_handlers.get(user_id)

    # Close the session
    support_mode_users.remove(user_id)
    if user_id in live_support_sessions:
        del live_support_sessions[user_id]
    if user_id in active_support_handlers:
        del active_support_handlers[user_id]
    if user_id in support_timeout_jobs:
        del support_timeout_jobs[user_id]

    # Remove all buttons from admin messages
    if user_id in support_message_ids:
        for admin_id, message_id in support_message_ids[user_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
        del support_message_ids[user_id]

    # Remove all End Support buttons from user messages
    if user_id in user_support_message_ids:
        for message_id in user_support_message_ids[user_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=user_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                logger.error(f"Failed to remove End Support button from user message {message_id}: {e}")
        del user_support_message_ids[user_id]

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="💬 **Support session closed due to inactivity.**\n\nFeel free to start a new session anytime!",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

    # Notify handling admin
    if handling_admin_id:
        try:
            await context.bot.send_message(
                chat_id=handling_admin_id,
                text=f"💬 **Support session auto-closed**\n\nUser {user_id} did not respond within 2 minutes.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {handling_admin_id}: {e}")


async def admin_end_inactive_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manually end any support session: /endsupport_user <user_id>"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin access required.")
        return

    # Parse user_id from command
    try:
        if len(context.args) == 0:
            # Show active support sessions
            if not support_mode_users:
                await update.message.reply_text("📭 No active support sessions.")
                return

            message = "💬 **Active Support Sessions:**\n\n"
            for user_id in support_mode_users:
                handler = "Not yet handled"
                if user_id in active_support_handlers:
                    handler_id = active_support_handlers[user_id]
                    handler = f"Admin {handler_id}"
                message += f"• User ID: `{user_id}` - {handler}\n"

            message += f"\n📝 Use `/endsupport_user <user_id>` to end a session"
            await update.message.reply_text(message, parse_mode='Markdown')
            return

        user_id = int(context.args[0])

        if user_id not in support_mode_users:
            await update.message.reply_text(f"❌ User {user_id} does not have an active support session.")
            return

        # End the session
        support_mode_users.remove(user_id)
        if user_id in live_support_sessions:
            del live_support_sessions[user_id]
        if user_id in active_support_handlers:
            del active_support_handlers[user_id]

        # Remove all End Chat buttons from admin messages
        if user_id in support_message_ids:
            for admin_id, message_id in support_message_ids[user_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
            del support_message_ids[user_id]

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="💬 **Support session ended by admin due to inactivity.**\n\n"
                     "Thank you for contacting us! Feel free to start a new session anytime.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

        # Notify all admins
        all_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(all_admins_response, dict) and 'results' in all_admins_response:
            all_admins = all_admins_response['results']
        else:
            all_admins = all_admins_response

        admin_ids = [ADMIN_USER_ID]
        for admin in all_admins:
            if admin['telegram_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['telegram_id'])

        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 Support session with user {user_id} ended by {update.effective_user.first_name}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

        await update.message.reply_text(
            f"✅ Support session with user {user_id} has been ended.",
            parse_mode='Markdown'
        )

        logger.info(f"Admin {update.effective_user.id} manually ended support session with user {user_id}")

    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ Invalid usage.\n\n"
            "**Usage:** `/endsupport_user <user_id>`\n"
            "**Example:** `/endsupport_user 123456789`\n\n"
            "Or use `/endsupport_user` without arguments to see active sessions.",
            parse_mode='Markdown'
        )


# Statistics and Reports
def generate_daily_stats_report(timezone_str='Indian/Maldives'):
    """Generate daily and monthly profit/loss statistics report for automatic notifications"""
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)

    # Define date ranges - ONLY TODAY and THIS MONTH
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get data from sheets - ONLY TODAY and THIS MONTH
    periods = {
        'TODAY': (today_start, today_end),
        'THIS MONTH': (month_start, today_end)
    }

    # Get exchange rates
    usd_rate = api.get_exchange_rate('USD', 'MVR') or 15.40
    usdt_rate = api.get_exchange_rate('USDT', 'MVR') or 15.40

    report = "📊 <b>PROFIT/LOSS REPORT</b>\n\n"
    report += f"💱 <b>Current Exchange Rates:</b>\n"
    report += f"1 USD = {float(usd_rate):.2f} MVR\n"
    report += f"1 USDT = {float(usdt_rate):.2f} MVR\n\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"

    # Store data for saving to Google Sheets
    report_data = {}

    for period_name, (start, end) in periods.items():
        deposits = api.get_deposits_by_date_range(start, end)
        withdrawals = api.get_withdrawals_by_date_range(start, end)
        spins = api.get_spins_by_date_range(start, end)
        bonuses = api.get_bonuses_by_date_range(start, end)
        cashback = api.get_cashback_by_date_range(start, end)

        # Get 50/50 investment stats for this period
        start_date_str = start.strftime('%Y-%m-%d')
        end_date_str = end.strftime('%Y-%m-%d')
        investment_stats = api.get_investment_stats(start_date_str, end_date_str)

        # Calculate chip costs (money given to users as chips)
        total_spin_rewards = sum([s['amount'] for s in spins])
        total_bonuses = sum([b['amount'] for b in bonuses])
        total_cashback = sum([c['amount'] for c in cashback])

        # Separate deposits by currency
        mvr_deposits = sum([d['amount'] for d in deposits if d['method'] in ['BML', 'MIB']])
        usd_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USD'])
        usdt_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USDT'])

        # Separate withdrawals by currency
        mvr_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] in ['BML', 'MIB']])
        usd_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USD'])
        usdt_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USDT'])

        # Calculate 50/50 investment impact
        investment_net = investment_stats['total_club_share'] - investment_stats['lost_amount']

        # Calculate COMPREHENSIVE profits per currency
        # Real Profit = Deposits - (Withdrawals + Spins + Bonuses + Cashback) + 50/50 Net
        # Note: Spins, bonuses, cashback are in MVR equivalent
        mvr_profit = mvr_deposits - (mvr_withdrawals + total_spin_rewards + total_bonuses + total_cashback) + investment_net
        usd_profit = usd_deposits - usd_withdrawals
        usdt_profit = usdt_deposits - usdt_withdrawals

        # Calculate MVR equivalents
        usd_mvr_equiv = usd_profit * usd_rate
        usdt_mvr_equiv = usdt_profit * usdt_rate
        total_mvr_profit = mvr_profit + usd_mvr_equiv + usdt_mvr_equiv

        # Save data for Google Sheets
        prefix = 'today_' if period_name == 'TODAY' else 'month_'
        report_data[f'{prefix}mvr_deposits'] = mvr_deposits
        report_data[f'{prefix}mvr_withdrawals'] = mvr_withdrawals
        report_data[f'{prefix}spin_rewards'] = total_spin_rewards
        report_data[f'{prefix}bonuses'] = total_bonuses
        report_data[f'{prefix}cashback'] = total_cashback
        report_data[f'{prefix}investment_profit'] = investment_stats['total_club_share']
        report_data[f'{prefix}investment_loss'] = investment_stats['lost_amount']
        report_data[f'{prefix}investment_net'] = investment_net
        report_data[f'{prefix}mvr_profit'] = mvr_profit
        report_data[f'{prefix}usd_deposits'] = usd_deposits
        report_data[f'{prefix}usd_withdrawals'] = usd_withdrawals
        report_data[f'{prefix}usd_profit'] = usd_profit
        report_data[f'{prefix}usdt_deposits'] = usdt_deposits
        report_data[f'{prefix}usdt_withdrawals'] = usdt_withdrawals
        report_data[f'{prefix}usdt_profit'] = usdt_profit
        report_data[f'{prefix}total_profit'] = total_mvr_profit

        report += f"<b>{period_name}</b>\n"

        # MVR Section
        if mvr_deposits > 0 or mvr_withdrawals > 0 or total_spin_rewards > 0 or total_bonuses > 0 or total_cashback > 0:
            mvr_emoji = "📈" if mvr_profit > 0 else "📉" if mvr_profit < 0 else "➖"
            report += f"💰 MVR Deposits: {mvr_deposits:,.2f}\n"
            report += f"💸 MVR Withdrawals: {mvr_withdrawals:,.2f}\n"

            if total_spin_rewards > 0:
                report += f"🎰 Spin Rewards: {total_spin_rewards:,.2f}\n"
            if total_bonuses > 0:
                report += f"🎁 Bonuses Given: {total_bonuses:,.2f}\n"
            if total_cashback > 0:
                report += f"💵 Cashback Given: {total_cashback:,.2f}\n"

            report += f"{mvr_emoji} <b>MVR Real Profit: {mvr_profit:,.2f}</b>\n"
            report += f"   (Deposits - Withdrawals - Spins - Bonuses - Cashback)\n\n"

        # USD Section
        if usd_deposits > 0 or usd_withdrawals > 0:
            usd_emoji = "📈" if usd_profit > 0 else "📉" if usd_profit < 0 else "➖"
            report += f"💵 USD Deposits: {usd_deposits:,.2f}\n"
            report += f"💵 USD Withdrawals: {usd_withdrawals:,.2f}\n"
            report += f"{usd_emoji} USD Profit: {usd_profit:,.2f}\n"
            report += f"   ≈ {usd_mvr_equiv:,.2f} MVR\n\n"

        # USDT Section
        if usdt_deposits > 0 or usdt_withdrawals > 0:
            usdt_emoji = "📈" if usdt_profit > 0 else "📉" if usdt_profit < 0 else "➖"
            report += f"💎 USDT Deposits: {usdt_deposits:,.2f}\n"
            report += f"💎 USDT Withdrawals: {usdt_withdrawals:,.2f}\n"
            report += f"{usdt_emoji} USDT Profit: {usdt_profit:,.2f}\n"
            report += f"   ≈ {usdt_mvr_equiv:,.2f} MVR\n\n"

        # 50/50 Investment Section
        if (investment_stats['completed_count'] > 0 or investment_stats['lost_count'] > 0 or
            investment_stats['active_count'] > 0):
            report += f"💎 <b>50/50 Investments:</b>\n"

            if investment_stats['active_count'] > 0:
                report += f"🔄 Active: {investment_stats['active_count']} ({investment_stats['active_amount']:,.2f} MVR)\n"

            if investment_stats['completed_count'] > 0:
                report += f"✅ Completed: {investment_stats['completed_count']}\n"
                report += f"   Club Share: +{investment_stats['total_club_share']:,.2f} MVR\n"

            if investment_stats['lost_count'] > 0:
                report += f"❌ Lost: {investment_stats['lost_count']}\n"
                report += f"   Lost Amount: -{investment_stats['lost_amount']:,.2f} MVR\n"

            investment_emoji = "📈" if investment_net > 0 else "📉" if investment_net < 0 else "➖"
            report += f"{investment_emoji} <b>50/50 Net:</b> {investment_net:,.2f} MVR\n\n"

        # Total in MVR
        if (mvr_deposits > 0 or mvr_withdrawals > 0 or
            usd_deposits > 0 or usd_withdrawals > 0 or
            usdt_deposits > 0 or usdt_withdrawals > 0 or
            investment_stats['completed_count'] > 0 or investment_stats['lost_count'] > 0):
            total_emoji = "📈" if total_mvr_profit > 0 else "📉" if total_mvr_profit < 0 else "➖"
            report += f"<b>{total_emoji} Total Profit (MVR):</b> {total_mvr_profit:,.2f}\n\n"

        report += f"━━━━━━━━━━━━━━━━━━\n\n"

    return report, report_data


def generate_stats_report(timezone_str='Indian/Maldives'):
    """Generate full profit/loss statistics report with all periods (for /stats command)"""
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)

    # Define date ranges - ALL PERIODS
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now

    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    six_months_start = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)

    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get data from sheets - ALL PERIODS
    periods = {
        'TODAY': (today_start, today_end),
        'THIS WEEK': (week_start, today_end),
        'THIS MONTH': (month_start, today_end),
        '6 MONTHS': (six_months_start, today_end),
        'THIS YEAR': (year_start, today_end)
    }

    # Get exchange rates (for display only)
    usd_rate = api.get_exchange_rate('USD', 'MVR') or 15.40
    usdt_rate = api.get_exchange_rate('USDT', 'MVR') or 15.40

    report = "📊 <b>PROFIT/LOSS REPORT</b>\n\n"
    report += f"💱 <b>Current Exchange Rates:</b>\n"
    report += f"1 USD = {float(usd_rate):.2f} MVR\n"
    report += f"1 USDT = {float(usdt_rate):.2f} MVR\n\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"

    for period_name, (start, end) in periods.items():
        deposits = api.get_deposits_by_date_range(start, end)
        withdrawals = api.get_withdrawals_by_date_range(start, end)
        spins = api.get_spins_by_date_range(start, end)
        bonuses = api.get_bonuses_by_date_range(start, end)
        cashback = api.get_cashback_by_date_range(start, end)
        investments = api.get_investments_by_date_range(start, end)
        credits = api.get_credits_by_date_range(start, end)

        # Handle paginated responses from Django API
        if isinstance(deposits, dict) and 'results' in deposits:
            deposits = deposits['results']
        if isinstance(withdrawals, dict) and 'results' in withdrawals:
            withdrawals = withdrawals['results']
        if isinstance(spins, dict) and 'results' in spins:
            spins = spins['results']
        if isinstance(bonuses, dict) and 'results' in bonuses:
            bonuses = bonuses['results']
        if isinstance(cashback, dict) and 'results' in cashback:
            cashback = cashback['results']
        if isinstance(investments, dict) and 'results' in investments:
            investments = investments['results']
        if isinstance(credits, dict) and 'results' in credits:
            credits = credits['results']

        # Calculate chip costs (money given to users as chips)
        total_spin_rewards = sum([float(s.get('chips', 0)) for s in spins if s.get('chips')])
        total_bonuses = sum([float(b.get('bonus_amount', 0)) for b in bonuses])
        total_cashback = sum([float(c.get('cashback_amount', 0)) for c in cashback])

        # Calculate 50/50 profit/loss
        # Completed = profit_share - investment (club got money back)
        # Lost = -investment (club lost the investment)
        # Active/Cancelled = ignore for now
        fiftyfifty_completed = [inv for inv in investments if inv.get('status') == 'Completed']
        fiftyfifty_lost = [inv for inv in investments if inv.get('status') == 'Lost']

        fiftyfifty_profit = sum([
            float(inv.get('profit_share', 0)) - float(inv.get('investment_amount', 0))
            for inv in fiftyfifty_completed
        ])
        fiftyfifty_loss = sum([
            float(inv.get('investment_amount', 0))
            for inv in fiftyfifty_lost
        ])
        fiftyfifty_net = fiftyfifty_profit - fiftyfifty_loss

        # Calculate outstanding credits (money users owe to club)
        # All credits in DB are outstanding (unpaid debts)
        total_credits = sum([float(c.get('amount', 0)) for c in credits])
        credits_count = len(credits)

        # All deposits/withdrawals are stored in MVR (USD/USDT are converted at deposit time)
        # So we just sum everything - no need to separate by currency or convert
        total_deposits = sum([float(d.get('amount', 0)) for d in deposits])
        total_withdrawals = sum([float(w.get('amount', 0)) for w in withdrawals])

        # Separate by method for display purposes only
        mvr_deposits = sum([float(d.get('amount', 0)) for d in deposits if d.get('method') in ['BML', 'MIB']])
        usd_deposits_mvr = sum([float(d.get('amount', 0)) for d in deposits if d.get('method') == 'USD'])
        usdt_deposits_mvr = sum([float(d.get('amount', 0)) for d in deposits if d.get('method') == 'USDT'])

        mvr_withdrawals = sum([float(w.get('amount', 0)) for w in withdrawals if w.get('payment_method', w.get('method')) in ['BML', 'MIB']])
        usd_withdrawals_mvr = sum([float(w.get('amount', 0)) for w in withdrawals if w.get('payment_method', w.get('method')) == 'USD'])
        usdt_withdrawals_mvr = sum([float(w.get('amount', 0)) for w in withdrawals if w.get('payment_method', w.get('method')) == 'USDT'])

        # Calculate total profit (everything is already in MVR)
        # Profit = Deposits + 50/50 Wins - Withdrawals - Spin Rewards - Bonuses - Cashback - 50/50 Losses
        total_mvr_profit = total_deposits + fiftyfifty_net - (total_withdrawals + total_spin_rewards + total_bonuses + total_cashback)

        report += f"<b>{period_name}</b>\n"

        # Show deposits by payment method (all amounts already in MVR)
        if mvr_deposits > 0:
            report += f"💰 BML/MIB Deposits: {mvr_deposits:,.2f} MVR\n"
        if usd_deposits_mvr > 0:
            report += f"💵 USD Deposits: {usd_deposits_mvr:,.2f} MVR\n"
        if usdt_deposits_mvr > 0:
            report += f"💎 USDT Deposits: {usdt_deposits_mvr:,.2f} MVR\n"

        # Show total deposits
        if total_deposits > 0:
            report += f"<b>📥 Total Deposits: {total_deposits:,.2f} MVR</b>\n\n"

        # Show withdrawals by payment method (all amounts already in MVR)
        if mvr_withdrawals > 0:
            report += f"💸 BML/MIB Withdrawals: {mvr_withdrawals:,.2f} MVR\n"
        if usd_withdrawals_mvr > 0:
            report += f"💵 USD Withdrawals: {usd_withdrawals_mvr:,.2f} MVR\n"
        if usdt_withdrawals_mvr > 0:
            report += f"💎 USDT Withdrawals: {usdt_withdrawals_mvr:,.2f} MVR\n"

        # Show total withdrawals
        if total_withdrawals > 0:
            report += f"<b>📤 Total Withdrawals: {total_withdrawals:,.2f} MVR</b>\n\n"

        # Show costs (spins, bonuses, cashback)
        if total_spin_rewards > 0:
            report += f"🎰 Spin Rewards: {total_spin_rewards:,.2f} MVR\n"
        if total_bonuses > 0:
            report += f"🎁 Bonuses Given: {total_bonuses:,.2f} MVR\n"
        if total_cashback > 0:
            report += f"💵 Cashback Given: {total_cashback:,.2f} MVR\n"

        # Show total costs
        total_costs = total_withdrawals + total_spin_rewards + total_bonuses + total_cashback
        if total_costs > 0:
            report += f"<b>💸 Total Costs: {total_costs:,.2f} MVR</b>\n\n"

        # Show 50/50 Investment profit/loss
        if len(fiftyfifty_completed) > 0 or len(fiftyfifty_lost) > 0:
            report += f"🎲 <b>50/50 Investments:</b>\n"
            if len(fiftyfifty_completed) > 0:
                report += f"  ✅ Completed: {len(fiftyfifty_completed)} (Profit: +{fiftyfifty_profit:,.2f} MVR)\n"
            if len(fiftyfifty_lost) > 0:
                report += f"  ❌ Lost: {len(fiftyfifty_lost)} (Loss: -{fiftyfifty_loss:,.2f} MVR)\n"
            fiftyfifty_emoji = "📈" if fiftyfifty_net > 0 else "📉" if fiftyfifty_net < 0 else "➖"
            report += f"  {fiftyfifty_emoji} Net 50/50: {fiftyfifty_net:+,.2f} MVR\n\n"

        # Show outstanding credits (money users owe)
        if credits_count > 0:
            report += f"💳 <b>Outstanding Credits:</b>\n"
            report += f"  {credits_count} user(s) owe {total_credits:,.2f} MVR\n"
            report += f"  <i>(Unpaid debts - not included in profit)</i>\n\n"

        # Show final profit/loss
        if total_deposits > 0 or total_costs > 0 or fiftyfifty_net != 0:
            total_emoji = "📈" if total_mvr_profit > 0 else "📉" if total_mvr_profit < 0 else "➖"
            report += f"<b>{total_emoji} Net Profit:</b> {total_mvr_profit:,.2f} MVR\n"
            report += f"<i>(Deposits + 50/50 Wins - Withdrawals - Rewards - Bonuses - Cashback - 50/50 Losses)</i>\n"
            if credits_count > 0:
                potential_profit = total_mvr_profit + total_credits
                report += f"\n💡 <i>Potential Profit (if all credits paid): {potential_profit:,.2f} MVR</i>\n"
            report += "\n"

        report += f"━━━━━━━━━━━━━━━━━━\n\n"

    return report


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show profit/loss report"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    await update.message.reply_text("📊 Generating statistics report...")

    try:
        report = generate_stats_report()
        await update.message.reply_text(report, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error generating stats: {e}")
        await update.message.reply_text(f"❌ Error generating report: {e}")


async def clear_bml_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_bml command - Remove BML account"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    success = api.clear_payment_account('BML')
    if success:
        await update.message.reply_text(
            "✅ BML account has been removed.\n\n"
            "Users will no longer see BML as a payment option.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed to clear BML account.")


async def clear_mib_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_mib command - Remove MIB account"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    success = api.clear_payment_account('MIB')
    if success:
        await update.message.reply_text(
            "✅ MIB account has been removed.\n\n"
            "Users will no longer see MIB as a payment option.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed to clear MIB account.")


async def clear_usd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_usd command - Remove USD account"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    success = api.clear_payment_account('USD')
    if success:
        await update.message.reply_text(
            "✅ USD account has been removed.\n\n"
            "Users will no longer see USD as a payment option.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed to clear USD account.")


async def clear_usdt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_usdt command - Remove USDT wallet"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    success = api.clear_payment_account('USDT')
    if success:
        await update.message.reply_text(
            "✅ USDT wallet has been removed.\n\n"
            "Users will no longer see USDT as a payment option.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed to clear USDT wallet.")


async def set_usd_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_usd_rate command - Set USD to MVR exchange rate"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    # Check if rate was provided
    if len(context.args) == 0:
        # Show current rate
        current_rate = api.get_exchange_rate('USD', 'MVR')
        if current_rate:
            await update.message.reply_text(
                f"💵 <b>Current USD Rate</b>\n\n"
                f"1 USD = {current_rate:.2f} MVR\n\n"
                f"To update: /set_usd_rate <rate>\n"
                f"Example: /set_usd_rate 17.50",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ USD rate not found.\n\n"
                "To set: /set_usd_rate <rate>\n"
                "Example: /set_usd_rate 17.50"
            )
        return

    try:
        rate = float(context.args[0])
        if rate <= 0:
            await update.message.reply_text("❌ Rate must be a positive number.")
            return

        success = api.set_exchange_rate('USD', 'MVR', rate)
        if success:
            await update.message.reply_text(
                f"✅ USD exchange rate updated!\n\n"
                f"💵 1 USD = {rate:.2f} MVR\n\n"
                f"This rate will be displayed to users during deposits and withdrawals.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Failed to update USD rate.")
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid rate format.\n\n"
            "Usage: /set_usd_rate <rate>\n"
            "Example: /set_usd_rate 17.50"
        )


async def set_usdt_rate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_usdt_rate command - Set USDT to MVR exchange rate"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    # Check if rate was provided
    if len(context.args) == 0:
        # Show current rate
        current_rate = api.get_exchange_rate('USDT', 'MVR')
        if current_rate:
            await update.message.reply_text(
                f"💎 <b>Current USDT Rate</b>\n\n"
                f"1 USDT = {current_rate:.2f} MVR\n\n"
                f"To update: /set_usdt_rate <rate>\n"
                f"Example: /set_usdt_rate 18.50",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ USDT rate not found.\n\n"
                "To set: /set_usdt_rate <rate>\n"
                "Example: /set_usdt_rate 18.50"
            )
        return

    try:
        rate = float(context.args[0])
        if rate <= 0:
            await update.message.reply_text("❌ Rate must be a positive number.")
            return

        success = api.set_exchange_rate('USDT', 'MVR', rate)
        if success:
            await update.message.reply_text(
                f"✅ USDT exchange rate updated!\n\n"
                f"💎 1 USDT = {rate:.2f} MVR\n\n"
                f"This rate will be displayed to users during deposits and withdrawals.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Failed to update USDT rate.")
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid rate format.\n\n"
            "Usage: /set_usdt_rate <rate>\n"
            "Example: /set_usdt_rate 18.50"
        )


async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addadmin command - Super admin only"""
    user_id = update.effective_user.id

    # Only super admin can add admins
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Only the super admin can add new admins.")
        return

    # Check if admin ID was provided
    if len(context.args) == 0:
        await update.message.reply_text(
            "❌ Please provide the admin's Telegram user ID.\n\n"
            "Usage: /addadmin <user_id>\n"
            "Example: /addadmin 123456789"
        )
        return

    try:
        new_admin_id = int(context.args[0])

        # Check if user is already super admin
        if new_admin_id == ADMIN_USER_ID:
            await update.message.reply_text("❌ This user is already the super admin.")
            return

        # Get user info from the new admin (if they've interacted with the bot)
        new_admin_user = api.get_user(new_admin_id)
        username = new_admin_user.get('username', '') if new_admin_user else ''
        name = ''
        if new_admin_user:
            first_name = new_admin_user.get('first_name', '')
            last_name = new_admin_user.get('last_name', '')
            name = f"{first_name} {last_name}".strip()

        # Add admin
        success = api.add_admin(new_admin_id, username, name, user_id)

        if success:
            await update.message.reply_text(
                f"✅ Admin added successfully!\n\n"
                f"<b>Admin ID:</b> <code>{new_admin_id}</code>\n"
                f"<b>Username:</b> @{username if username else 'N/A'}\n"
                f"<b>Name:</b> {name if name else 'N/A'}\n\n"
                f"They now have full access to the admin panel.",
                parse_mode='HTML'
            )

            # Try to notify the new admin
            try:
                await context.bot.send_message(
                    chat_id=new_admin_id,
                    text=(
                        "🎉 <b>Congratulations!</b>\n\n"
                        "You have been granted admin access to the Billionaires PPPoker Bot.\n\n"
                        "Use /start to access the admin panel."
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify new admin: {e}")
                await update.message.reply_text(
                    "⚠️ Note: Could not send notification to the new admin. "
                    "They may need to start the bot first."
                )
        else:
            await update.message.reply_text("❌ Admin already exists or could not be added.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric Telegram user ID.")
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        await update.message.reply_text(f"❌ Error adding admin: {e}")


async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /removeadmin command - Super admin only"""
    user_id = update.effective_user.id

    # Only super admin can remove admins
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Only the super admin can remove admins.")
        return

    # Check if admin ID was provided
    if len(context.args) == 0:
        await update.message.reply_text(
            "❌ Please provide the admin's Telegram user ID.\n\n"
            "Usage: /removeadmin <user_id>\n"
            "Example: /removeadmin 123456789"
        )
        return

    try:
        admin_id_to_remove = int(context.args[0])

        # Can't remove super admin
        if admin_id_to_remove == ADMIN_USER_ID:
            await update.message.reply_text("❌ Cannot remove the super admin.")
            return

        # Remove admin
        success = api.remove_admin(admin_id_to_remove)

        if success:
            await update.message.reply_text(
                f"✅ Admin removed successfully!\n\n"
                f"<b>Admin ID:</b> <code>{admin_id_to_remove}</code>\n\n"
                f"They no longer have access to the admin panel.",
                parse_mode='HTML'
            )

            # Try to notify the removed admin
            try:
                await context.bot.send_message(
                    chat_id=admin_id_to_remove,
                    text=(
                        "⚠️ <b>Admin Access Revoked</b>\n\n"
                        "Your admin access to the Billionaires PPPoker Bot has been removed.\n\n"
                        "You now have regular user access."
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Could not notify removed admin: {e}")
        else:
            await update.message.reply_text("❌ Admin not found or could not be removed.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric Telegram user ID.")
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        await update.message.reply_text(f"❌ Error removing admin: {e}")


async def listadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /listadmins command - Super admin only"""
    user_id = update.effective_user.id

    # Only super admin can view admin list
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Only the super admin can view the admin list.")
        return

    try:
        # Get all admins
        admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(admins_response, dict) and 'results' in admins_response:
            admins = admins_response['results']
        else:
            admins = admins_response

        message = "👥 <b>ADMIN LIST</b>\n\n"
        message += f"🔱 <b>Super Admin:</b>\n"
        message += f"ID: <code>{ADMIN_USER_ID}</code>\n\n"

        if admins:
            message += f"👤 <b>Regular Admins ({len(admins)}):</b>\n\n"
            for admin in admins:
                message += f"━━━━━━━━━━━━━━━━━━\n"
                message += f"<b>ID:</b> <code>{admin['telegram_id']}</code>\n"
                if admin.get('username'):
                    message += f"<b>Username:</b> @{admin['username']}\n"
                if admin.get('name'):
                    message += f"<b>Name:</b> {admin['name']}\n"
                message += f"<b>Added:</b> {admin.get('added_at', 'N/A')}\n"
        else:
            message += "No regular admins added yet.\n"

        message += "\n━━━━━━━━━━━━━━━━━━\n"
        message += f"<b>Total Admins:</b> {len(admins) + 1}"

        await update.message.reply_text(message, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error listing admins: {e}")
        await update.message.reply_text(f"❌ Error listing admins: {e}")


async def user_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /user_credit command - Show all users with active credits"""
    user_id = update.effective_user.id

    # Only admins can view credits
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return

    try:
        # Get all active credits
        credits = api.get_all_active_credits()

        if not credits:
            await update.message.reply_text(
                "✅ **No Active Credits**\n\n"
                "All users have settled their seat requests.",
                parse_mode='Markdown'
            )
            return

        message = "💳 <b>USERS WITH ACTIVE CREDITS</b>\n\n"
        message += f"<i>Total: {len(credits)} user(s)</i>\n\n"

        # Create inline buttons for each user
        keyboard = []

        for credit in credits:
            # Extract user details
            user_details = credit.get('user_details', {})
            username = user_details.get('username', credit.get('username'))
            user_id = credit.get('user') or credit.get('user_id')
            pppoker_id = user_details.get('pppoker_id', 'N/A')

            user_display = f"User {user_id}"
            if username:
                user_display = f"@{username}"

            message += "━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>User:</b> {user_display}\n"
            message += f"<b>User ID:</b> <code>{user_id}</code>\n"
            # Only wrap in <code> if pppoker_id has a value
            pppoker_display = f"<code>{pppoker_id}</code>" if pppoker_id and pppoker_id != 'N/A' else pppoker_id or 'N/A'
            message += f"<b>PPPoker ID:</b> {pppoker_display}\n"
            message += f"<b>Credit Amount:</b> <b>{credit['amount']} chips/MVR</b>\n"

            # Extract request ID from description (format: "Seat request {id} for PPPoker ID {pppoker}")
            request_id = 'N/A'
            description = credit.get('description', '')
            if 'Seat request' in description:
                try:
                    request_id = description.split('Seat request ')[1].split(' ')[0]
                except:
                    request_id = 'N/A'

            message += f"<b>Request ID:</b> {request_id}\n"
            message += f"<b>Created:</b> {credit['created_at']}\n"
            message += f"<b>Reminders Sent:</b> {credit.get('reminder_count', 0)}\n\n"

            # Add button for this user
            button_text = f"✅ Clear Credit - {user_display} ({credit['amount']} MVR)"
            # Use telegram_id for callback
            user_telegram_id = user_details.get('telegram_id') or credit.get('user_id')
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"clear_credit_{user_telegram_id}"
            )])

        message += "━━━━━━━━━━━━━━━━━━\n\n"
        message += "📝 <i>Click a button below to clear a user's credit after they've settled payment.</i>"

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error listing credits: {e}")
        await update.message.reply_text(f"❌ Error listing credits: {e}")


async def clear_user_credit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clear credit button click"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    user_id = int(query.data.split('_')[-1])
    await query.answer()

    # Get credit info before clearing
    credit = api.get_user_credit(user_id)
    if not credit:
        await query.edit_message_text(
            "❌ **Credit not found**\n\n"
            "This credit may have already been cleared.",
            parse_mode='Markdown'
        )
        return

    # Create deposit record for accounting/tracking purposes
    # (Balance was already given when seat was approved, this is just for reports)
    try:
        user_details = credit.get('user_details', {})
        pppoker_id = user_details.get('pppoker_id', 'N/A')

        deposit_data = api.create_deposit(
            user_id=credit.get('user'),
            amount=float(credit['amount']),
            method='Credit Payment',
            account_name='Credit Settlement',
            pppoker_id=pppoker_id,
            proof_image_path=''  # Empty string instead of None
        )

        # Auto-approve the deposit (just for tracking, no balance added)
        if deposit_data:
            deposit_id = deposit_data.get('id')
            api.approve_deposit(deposit_id, query.from_user.id, add_balance=False)
            logger.info(f"Created deposit record {deposit_id} for credit payment tracking")
    except Exception as e:
        logger.error(f"Failed to create deposit record for credit payment: {e}")

    # Clear the credit
    success = api.clear_user_credit(user_id)

    if success:
        # Clean up tracking
        if user_id in seat_request_data:
            del seat_request_data[user_id]
        if user_id in seat_reminder_jobs:
            try:
                seat_reminder_jobs[user_id].schedule_removal()
                del seat_reminder_jobs[user_id]
            except:
                pass

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ **Credit Cleared**\n\n"
                     f"Your credit of **{credit['amount']} chips/MVR** has been cleared.\n\n"
                     f"Thank you for settling your payment!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        # Extract username safely
        user_details = credit.get('user_details', {})
        username = user_details.get('username', 'N/A')

        await query.edit_message_text(
            f"✅ <b>Credit Cleared Successfully</b>\n\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Username:</b> @{username if username != 'N/A' else 'N/A'}\n"
            f"<b>Amount:</b> {credit['amount']} chips/MVR\n\n"
            f"User has been notified.\n\n"
            f"<i>Use /user_credit to view remaining credits.</i>",
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            "❌ **Failed to clear credit**\n\n"
            "Please try again or contact support.",
            parse_mode='Markdown'
        )


def calculate_all_periods_data(timezone_str='Indian/Maldives'):
    """Calculate data for all periods (TODAY, WEEK, MONTH, 6 MONTHS, YEAR) for saving to Google Sheets"""
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)

    # Define all date ranges
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now

    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    six_months_start = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)

    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    periods = {
        'today': (today_start, today_end),
        'week': (week_start, today_end),
        'month': (month_start, today_end),
        'six_months': (six_months_start, today_end),
        'year': (year_start, today_end)
    }

    # Get exchange rates
    usd_rate = api.get_exchange_rate('USD', 'MVR') or 15.40
    usdt_rate = api.get_exchange_rate('USDT', 'MVR') or 15.40

    all_data = {}

    for period_name, (start, end) in periods.items():
        deposits = api.get_deposits_by_date_range(start, end)
        withdrawals = api.get_withdrawals_by_date_range(start, end)
        spins = api.get_spins_by_date_range(start, end)
        bonuses = api.get_bonuses_by_date_range(start, end)
        cashback = api.get_cashback_by_date_range(start, end)

        # Calculate chip costs
        total_spin_rewards = sum([s['amount'] for s in spins])
        total_bonuses = sum([b['amount'] for b in bonuses])
        total_cashback = sum([c['amount'] for c in cashback])

        # Separate by currency
        mvr_deposits = sum([d['amount'] for d in deposits if d['method'] in ['BML', 'MIB']])
        usd_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USD'])
        usdt_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USDT'])

        mvr_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] in ['BML', 'MIB']])
        usd_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USD'])
        usdt_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USDT'])

        # Calculate COMPREHENSIVE profits
        mvr_profit = mvr_deposits - (mvr_withdrawals + total_spin_rewards + total_bonuses + total_cashback)
        usd_profit = usd_deposits - usd_withdrawals
        usdt_profit = usdt_deposits - usdt_withdrawals

        # Calculate total profit in MVR
        usd_mvr_equiv = usd_profit * usd_rate
        usdt_mvr_equiv = usdt_profit * usdt_rate
        total_mvr_profit = mvr_profit + usd_mvr_equiv + usdt_mvr_equiv

        # Store data
        all_data[f'{period_name}_mvr_deposits'] = mvr_deposits
        all_data[f'{period_name}_mvr_withdrawals'] = mvr_withdrawals
        all_data[f'{period_name}_spin_rewards'] = total_spin_rewards
        all_data[f'{period_name}_bonuses'] = total_bonuses
        all_data[f'{period_name}_cashback'] = total_cashback
        all_data[f'{period_name}_mvr_profit'] = mvr_profit
        all_data[f'{period_name}_usd_deposits'] = usd_deposits
        all_data[f'{period_name}_usd_withdrawals'] = usd_withdrawals
        all_data[f'{period_name}_usd_profit'] = usd_profit
        all_data[f'{period_name}_usdt_deposits'] = usdt_deposits
        all_data[f'{period_name}_usdt_withdrawals'] = usdt_withdrawals
        all_data[f'{period_name}_usdt_profit'] = usdt_profit
        all_data[f'{period_name}_total_profit'] = total_mvr_profit

    return all_data


async def send_daily_report(application):
    """Send daily profit/loss report to all admins"""
    try:
        report_header = "🌅 <b>DAILY PROFIT/LOSS REPORT</b>\n"
        report_header += f"<i>{datetime.now(pytz.timezone('Indian/Maldives')).strftime('%B %d, %Y')}</i>\n\n"

        stats_report, report_data = generate_daily_stats_report()
        report = report_header + stats_report

        # Add credit summary section
        credit_summary = api.get_daily_credit_summary()
        if credit_summary['count'] > 0:
            report += "\n\n💳 <b>ACTIVE CREDITS SUMMARY</b>\n"
            report += f"━━━━━━━━━━━━━━━━━━\n\n"
            report += f"<b>Total Outstanding Credits:</b> {credit_summary['count']}\n"
            report += f"<b>Total Credit Amount:</b> {credit_summary['total_amount']:,.2f} MVR\n\n"

            if credit_summary['details']:
                report += "<b>Details:</b>\n"
                for detail in credit_summary['details']:
                    username_display = f"@{detail['username']}" if detail['username'] else "No username"
                    report += f"• {username_display}\n"
                    report += f"  Amount: {detail['amount']:,.2f} MVR\n"
                    report += f"  PPPoker ID: {detail['pppoker_id']}\n"
                    report += f"  Since: {detail['created_at']}\n\n"
        else:
            report += "\n\n✅ <b>No active credits - All payments received!</b>\n"

        # Calculate ALL period reports for saving to Google Sheets
        all_reports_data = calculate_all_periods_data()

        # Add credit data
        all_reports_data['credits_count'] = credit_summary['count']
        all_reports_data['credits_amount'] = credit_summary['total_amount']

        # Save all reports to Google Sheets
        try:
            api.save_all_reports(all_reports_data)
            logger.info("All period reports saved to Google Sheets successfully")
        except Exception as e:
            logger.error(f"Failed to save reports to Google Sheets: {e}")

        # Send to super admin
        try:
            await application.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=report,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to send daily report to super admin: {e}")

        # Send to all regular admins
        try:
            admins_response = api.get_all_admins()

            # Handle paginated response from Django API
            if isinstance(admins_response, dict) and 'results' in admins_response:
                admins = admins_response['results']
            else:
                admins = admins_response

            for admin in admins:
                try:
                    await application.bot.send_message(
                        chat_id=admin['telegram_id'],
                        text=report,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to send daily report to admin {admin['telegram_id']}: {e}")
        except Exception as e:
            logger.error(f"Failed to get admin list for daily report: {e}")

        logger.info("Daily report sent successfully to all admins")
    except Exception as e:
        logger.error(f"Error sending daily report: {e}")


# Admin Update Payment Account Handlers
async def update_payment_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start updating payment account"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return ConversationHandler.END

    # Determine which account to update from command
    command = update.message.text.split()[0].lower()

    if 'bml' in command:
        context.user_data['update_method'] = 'BML'
        method_name = 'BML'
    elif 'mib' in command:
        context.user_data['update_method'] = 'MIB'
        method_name = 'MIB'
    elif 'usd' in command and 'usdt' not in command:
        context.user_data['update_method'] = 'USD'
        method_name = 'USD'
    elif 'usdt' in command:
        context.user_data['update_method'] = 'USDT'
        method_name = 'USDT'
    else:
        await update.message.reply_text("❌ Unknown payment method.")
        return ConversationHandler.END

    # Get current details
    current_details = api.get_payment_account(context.user_data['update_method'])

    if current_details and current_details.get('account_number'):
        current_text = f"📋 **Current {method_name} Account:**\n"
        current_text += f"Account Number: `{current_details['account_number']}`\n"
        if current_details.get('account_name'):
            current_text += f"Account Holder: {current_details['account_name']}\n"
        current_text += f"\n"
    else:
        current_text = f"📋 **No {method_name} account configured yet.**\n\n"

    if method_name == 'USDT':
        prompt = current_text + f"Please enter the new {method_name} wallet address:"
    else:
        prompt = current_text + f"Please enter the new {method_name} account number:"

    # Add cancel button
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="update_account_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(prompt, parse_mode='Markdown', reply_markup=reply_markup)

    return UPDATE_ACCOUNT_NUMBER


async def update_account_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive account number and ask for holder name"""
    account_number = update.message.text.strip()
    context.user_data['update_account_number'] = account_number

    method = context.user_data['update_method']

    if method == 'USDT':
        # USDT doesn't need holder name, save directly
        try:
            api.update_payment_account(method, account_number, None)

            await update.message.reply_text(
                f"✅ **{method} wallet updated successfully!**\n\n"
                f"Wallet Address: `{account_number}`",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error updating USDT wallet: {e}")
            await update.message.reply_text(
                f"❌ **Error saving wallet details.**\n\n"
                f"Please try again or contact support.\n"
                f"Error: {str(e)}",
                parse_mode='Markdown'
            )

        # Clear user data
        context.user_data.clear()
        return ConversationHandler.END
    else:
        # Ask for account holder name for BML/MIB
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="update_account_cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📝 Account number: `{account_number}`\n\n"
            f"Now, please enter the account holder name (as it appears on the bank account):",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        return UPDATE_ACCOUNT_METHOD


async def update_account_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the update account conversation"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ **Update cancelled.**\n\n"
        "No changes were made to the payment accounts.",
        parse_mode='Markdown'
    )

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


async def update_account_holder_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive account holder name and save"""
    account_holder = update.message.text.strip()
    account_number = context.user_data.get('update_account_number')
    method = context.user_data.get('update_method')

    if not account_number or not method:
        await update.message.reply_text(
            "❌ **Error:** Session data lost. Please start again with the update command.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        # Save to sheets
        api.update_payment_account(method, account_number, account_holder)

        await update.message.reply_text(
            f"✅ **{method} account updated successfully!**\n\n"
            f"Account Number: `{account_number}`\n"
            f"Account Holder: {account_holder}\n\n"
            f"ℹ️ This holder name will be used to validate deposit slips.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error updating payment account: {e}")
        await update.message.reply_text(
            f"❌ **Error saving account details.**\n\n"
            f"Please try again or contact support.\n"
            f"Error: {str(e)}",
            parse_mode='Markdown'
        )

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


# Admin Broadcast System
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast - admin sends message to all users"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return ConversationHandler.END

    # Add cancel button
    keyboard = [[InlineKeyboardButton("❌ Cancel Broadcast", callback_data="broadcast_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📢 **Broadcast System**\n\n"
        "Please send the message or image you want to broadcast to all users.\n\n"
        "You can send:\n"
        "• Text message\n"
        "• Image with caption\n"
        "• Image only\n\n"
        "Click the button below or type /cancel to cancel.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    return BROADCAST_MESSAGE


async def broadcast_start_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast from admin panel callback"""
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ This feature is only for admins.")
        return ConversationHandler.END

    # Add cancel button
    keyboard = [[InlineKeyboardButton("❌ Cancel Broadcast", callback_data="broadcast_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📢 **Broadcast System**\n\n"
        "Please send the message or image you want to broadcast to all users.\n\n"
        "You can send:\n"
        "• Text message\n"
        "• Image with caption\n"
        "• Image only\n\n"
        "Click the button below or type /cancel to cancel.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    return BROADCAST_MESSAGE


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the broadcast"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ **Broadcast cancelled.**\n\n"
        "No messages were sent to users.",
        parse_mode='Markdown'
    )

    return ConversationHandler.END


async def broadcast_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive broadcast message and send to all users"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    # Get the message to broadcast
    broadcast_msg = update.message

    # Get all users from Django API
    users = api.get_all_users()

    # Handle paginated response
    if isinstance(users, dict) and 'results' in users:
        users = users['results']

    # Extract telegram IDs
    user_ids = [user['telegram_id'] for user in users if 'telegram_id' in user]

    if not user_ids:
        await update.message.reply_text("❌ No users found in database.")
        return ConversationHandler.END

    # Confirm before sending
    await update.message.reply_text(
        f"📊 Found {len(user_ids)} users in database.\n\n"
        f"🚀 Starting broadcast...",
        parse_mode='Markdown'
    )

    # Send to all users with delay
    success_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            # Send based on message type
            if broadcast_msg.photo:
                # Image with or without caption
                photo = broadcast_msg.photo[-1]  # Get highest quality
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo.file_id,
                    caption=broadcast_msg.caption,
                    parse_mode='Markdown' if broadcast_msg.caption else None
                )
            elif broadcast_msg.text:
                # Text message
                await context.bot.send_message(
                    chat_id=user_id,
                    text=broadcast_msg.text,
                    parse_mode='Markdown'
                )
            else:
                # Unsupported message type for this user
                failed_count += 1
                continue

            success_count += 1

            # 1-second delay to avoid rate limits
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user_id}: {e}")
            failed_count += 1
            # Continue with next user even if one fails
            await asyncio.sleep(1)

    # Report results to admin
    result_msg = f"✅ **Broadcast completed!**\n\n"
    result_msg += f"📤 Successfully sent: {success_count} users\n"

    if failed_count > 0:
        result_msg += f"❌ Failed: {failed_count} users\n"

    result_msg += f"\n📊 Total users in database: {len(user_ids)}"

    await update.message.reply_text(result_msg, parse_mode='Markdown')

    return ConversationHandler.END


# ========== 50/50 INVESTMENT HANDLERS ==========

async def investment_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new 50/50 investment"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💎 <b>Add 50/50 Investment</b>\n\n"
        "Enter the player's PPPoker ID:",
        parse_mode='HTML'
    )

    return INVESTMENT_PPPOKER_ID


async def investment_pppoker_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive PPPoker ID and ask for optional note"""
    pppoker_id = update.message.text.strip()

    # Clean PPPoker ID (remove spaces, letters, special characters)
    pppoker_id = ''.join(filter(str.isdigit, pppoker_id))

    if not pppoker_id:
        await update.message.reply_text(
            "❌ Invalid PPPoker ID. Please enter a valid ID:",
            parse_mode='HTML'
        )
        return INVESTMENT_PPPOKER_ID

    context.user_data['investment_pppoker_id'] = pppoker_id

    await update.message.reply_text(
        "💎 <b>Add Note (Optional)</b>\n\n"
        "Enter player name or note (e.g., 'Ahmed', 'Friend 1')\n"
        "Or send /skip to skip:",
        parse_mode='HTML'
    )

    return INVESTMENT_NOTE


async def investment_note_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive optional note and ask for amount"""
    if update.message.text.strip() == '/skip':
        context.user_data['investment_note'] = ''
    else:
        context.user_data['investment_note'] = update.message.text.strip()

    await update.message.reply_text(
        "💎 <b>Investment Amount</b>\n\n"
        "Enter the amount you gave to the player (MVR):",
        parse_mode='HTML'
    )

    return INVESTMENT_AMOUNT


async def investment_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive amount and add investment"""
    try:
        amount = float(update.message.text.strip())

        if amount <= 0:
            await update.message.reply_text(
                "❌ Amount must be greater than 0. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return INVESTMENT_AMOUNT

        pppoker_id = context.user_data['investment_pppoker_id']
        note = context.user_data.get('investment_note', '')
        telegram_id = update.effective_user.id
        start_date = datetime.now().strftime('%Y-%m-%d')

        # Add investment to Google Sheets
        success = api.add_investment(telegram_id, amount, start_date, note, pppoker_id)

        if success:
            player_display = pppoker_id
            if note:
                player_display += f" ({note})"

            await update.message.reply_text(
                f"✅ <b>Investment Added!</b>\n\n"
                f"🎮 Player: {player_display}\n"
                f"💰 Amount: {amount:.2f} MVR\n"
                f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"⚠️ Will count as loss after 24 hours if not returned.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ Failed to add investment. Please try again later.",
                parse_mode='HTML'
            )

        # Clean up
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a number:",
            parse_mode='HTML'
        )
        return INVESTMENT_AMOUNT


async def investment_return_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start recording a return - show active investments"""
    query = update.callback_query
    await query.answer()

    # Get all active investments from last 24 hours
    active_investments = api.get_all_active_investments_summary()

    if not active_investments:
        await query.edit_message_text(
            "💎 <b>No Active Investments</b>\n\n"
            "There are no active investments from the last 24 hours.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )
        return ConversationHandler.END

    # Show list of active investments
    message = "💎 <b>Active Investments (Last 24 Hours)</b>\n\n"
    message += "Select a PPPoker ID by sending the ID number:\n\n"

    for inv in active_investments:
        pppoker_id = inv['pppoker_id']
        note = inv['player_note']
        amount = inv['total_amount']
        date = inv['first_date']

        player_display = pppoker_id
        if note:
            player_display += f" ({note})"

        message += f"🎮 <b>{player_display}</b>\n"
        message += f"💰 Total Investment: {amount:.2f} MVR\n"
        message += f"📅 Since: {date}\n\n"

    message += "Send the PPPoker ID or /cancel to cancel:"

    await query.edit_message_text(message, parse_mode='HTML')

    return RETURN_SELECT_ID


async def return_id_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive PPPoker ID selection"""
    if update.message.text.strip() == '/cancel':
        await update.message.reply_text(
            "❌ Cancelled.",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    pppoker_id = update.message.text.strip()

    # Clean PPPoker ID
    pppoker_id = ''.join(filter(str.isdigit, pppoker_id))

    # Check if this PPPoker ID has active investments
    investments_data = api.get_active_investments_by_pppoker_id(pppoker_id)

    if investments_data['count'] == 0:
        await update.message.reply_text(
            "❌ No active investments found for this PPPoker ID.\n"
            "Please send a valid PPPoker ID or /cancel:",
            parse_mode='HTML'
        )
        return RETURN_SELECT_ID

    context.user_data['return_pppoker_id'] = pppoker_id
    context.user_data['return_investment_data'] = investments_data

    # Show investment details and ask for return amount
    total_investment = investments_data['total_amount']
    player_note = ''
    if investments_data['investments']:
        player_note = investments_data['investments'][0].get('player_note', '')

    player_display = pppoker_id
    if player_note:
        player_display += f" ({player_note})"

    await update.message.reply_text(
        f"💎 <b>Investment Details</b>\n\n"
        f"🎮 Player: {player_display}\n"
        f"💰 Total Investment: {total_investment:.2f} MVR\n"
        f"📊 Number of investments: {investments_data['count']}\n\n"
        f"Enter the total return amount (what player has now):",
        parse_mode='HTML'
    )

    return RETURN_AMOUNT


async def return_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive return amount and process the return"""
    try:
        return_amount = float(update.message.text.strip())

        if return_amount < 0:
            await update.message.reply_text(
                "❌ Amount cannot be negative. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return RETURN_AMOUNT

        pppoker_id = context.user_data['return_pppoker_id']
        investment_data = context.user_data['return_investment_data']
        total_investment = investment_data['total_amount']

        # Record the return
        result = api.record_investment_return(pppoker_id, return_amount)

        if result['success']:
            net_profit = result['net_profit']
            player_share = result['player_share']
            club_share = result['club_share']

            player_note = ''
            if investment_data['investments']:
                player_note = investment_data['investments'][0].get('player_note', '')

            player_display = pppoker_id
            if player_note:
                player_display += f" ({player_note})"

            message = "✅ <b>50/50 Return Recorded!</b>\n\n"
            message += f"📊 <b>Calculation:</b>\n"
            message += f"💰 Investment: {total_investment:.2f} MVR\n"
            message += f"💵 Return Total: {return_amount:.2f} MVR\n"
            message += f"📈 Net Profit: {net_profit:.2f} MVR\n\n"
            message += f"💎 <b>Split (50/50):</b>\n"
            message += f"👤 Player Share: {player_share:.2f} MVR\n"
            message += f"🏛️ Club Share: {club_share:.2f} MVR\n\n"
            message += f"📊 <b>Financial Impact:</b>\n"
            message += f"✅ +{club_share:.2f} MVR added to Club Profit\n\n"
            message += f"🎮 {player_display}\n"
            message += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(
                f"❌ Failed to record return: {result.get('error', 'Unknown error')}",
                parse_mode='HTML'
            )

        # Clean up
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a number:",
            parse_mode='HTML'
        )
        return RETURN_AMOUNT


# ========== CLUB BALANCE MANAGEMENT HANDLERS ==========

async def balance_setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start setting up club balances (one-time)"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "⚙️ <b>Set Starting Balances</b>\n\n"
        "Let's set up your club's starting inventory and cash balances.\n\n"
        "Enter your starting chip inventory:",
        parse_mode='HTML'
    )

    return BALANCE_SETUP_CHIPS


async def balance_setup_chips_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive starting chip inventory"""
    try:
        chips = float(update.message.text.strip())

        if chips < 0:
            await update.message.reply_text(
                "❌ Chips cannot be negative. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return BALANCE_SETUP_CHIPS

        context.user_data['setup_chips'] = chips

        await update.message.reply_text(
            f"✅ Starting chip inventory: {chips:,.0f}\n\n"
            f"How much did these {chips:,.0f} chips cost you? (MVR)",
            parse_mode='HTML'
        )

        return BALANCE_SETUP_COST

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter chip inventory:",
            parse_mode='HTML'
        )
        return BALANCE_SETUP_CHIPS


async def balance_setup_cost_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive chip cost basis"""
    try:
        cost = float(update.message.text.strip())

        if cost < 0:
            await update.message.reply_text(
                "❌ Cost cannot be negative. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return BALANCE_SETUP_COST

        chips = context.user_data['setup_chips']
        rate = cost / chips if chips > 0 else 0

        context.user_data['setup_cost'] = cost

        await update.message.reply_text(
            f"✅ Chip cost: {cost:,.2f} MVR\n"
            f"📊 Average rate: {rate:.4f} MVR/chip\n\n"
            f"Enter your starting MVR cash balance:",
            parse_mode='HTML'
        )

        return BALANCE_SETUP_MVR

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter cost in MVR:",
            parse_mode='HTML'
        )
        return BALANCE_SETUP_COST


async def balance_setup_mvr_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive MVR balance"""
    try:
        mvr = float(update.message.text.strip())

        if mvr < 0:
            await update.message.reply_text(
                "❌ Balance cannot be negative. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return BALANCE_SETUP_MVR

        context.user_data['setup_mvr'] = mvr

        await update.message.reply_text(
            f"✅ MVR balance: {mvr:,.2f}\n\n"
            f"Enter your starting USD balance (or 0 if none):",
            parse_mode='HTML'
        )

        return BALANCE_SETUP_USD

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter MVR balance:",
            parse_mode='HTML'
        )
        return BALANCE_SETUP_MVR


async def balance_setup_usd_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive USD balance"""
    try:
        usd = float(update.message.text.strip())

        if usd < 0:
            await update.message.reply_text(
                "❌ Balance cannot be negative. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return BALANCE_SETUP_USD

        context.user_data['setup_usd'] = usd

        await update.message.reply_text(
            f"✅ USD balance: {usd:,.2f}\n\n"
            f"Enter your starting USDT balance (or 0 if none):",
            parse_mode='HTML'
        )

        return BALANCE_SETUP_USDT

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter USD balance:",
            parse_mode='HTML'
        )
        return BALANCE_SETUP_USD


async def balance_setup_usdt_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive USDT balance and complete setup"""
    try:
        usdt = float(update.message.text.strip())

        if usdt < 0:
            await update.message.reply_text(
                "❌ Balance cannot be negative. Please enter a valid amount:",
                parse_mode='HTML'
            )
            return BALANCE_SETUP_USDT

        # Get all saved data
        chips = context.user_data['setup_chips']
        cost = context.user_data['setup_cost']
        mvr = context.user_data['setup_mvr']
        usd = context.user_data['setup_usd']

        rate = cost / chips if chips > 0 else 0

        # Save to sheets
        success = api.set_starting_balances(chips, cost, mvr, usd, usdt)

        if success:
            await update.message.reply_text(
                f"✅ <b>Starting Balances Set!</b>\n\n"
                f"🎲 Chip Inventory: {chips:,.0f}\n"
                f"💰 Chip Cost: {cost:,.2f} MVR\n"
                f"📊 Avg Rate: {rate:.4f} MVR/chip\n\n"
                f"💰 MVR Balance: {mvr:,.2f}\n"
                f"💵 USD Balance: {usd:,.2f}\n"
                f"💎 USDT Balance: {usdt:,.2f}\n\n"
                f"Balance tracking is now active!",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ Failed to set balances. Please try again.",
                parse_mode='HTML'
            )

        # Clean up
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter USDT balance:",
            parse_mode='HTML'
        )
        return BALANCE_SETUP_USDT


async def balance_buy_chips_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buying chips for club"""
    query = update.callback_query
    await query.answer()

    balances = api.get_club_balances()

    await query.edit_message_text(
        f"🎲 <b>Buy Chips for Club</b>\n\n"
        f"Current MVR Balance: {balances['mvr_balance']:,.2f}\n"
        f"Current Chip Inventory: {balances['chip_inventory']:,.0f}\n"
        f"Current Avg Rate: {balances['avg_chip_rate']:.4f} MVR/chip\n\n"
        f"How many chips are you buying?",
        parse_mode='HTML'
    )

    return BALANCE_BUY_CHIPS


async def balance_buy_chips_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive chips amount"""
    try:
        chips = float(update.message.text.strip())

        if chips <= 0:
            await update.message.reply_text(
                "❌ Amount must be greater than 0. Please enter chips amount:",
                parse_mode='HTML'
            )
            return BALANCE_BUY_CHIPS

        context.user_data['buy_chips'] = chips

        await update.message.reply_text(
            f"✅ Buying: {chips:,.0f} chips\n\n"
            f"What's the total cost? (MVR)",
            parse_mode='HTML'
        )

        return BALANCE_BUY_COST

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter chips amount:",
            parse_mode='HTML'
        )
        return BALANCE_BUY_CHIPS


async def balance_buy_cost_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive cost and process chip purchase"""
    try:
        cost = float(update.message.text.strip())

        if cost <= 0:
            await update.message.reply_text(
                "❌ Cost must be greater than 0. Please enter cost:",
                parse_mode='HTML'
            )
            return BALANCE_BUY_COST

        chips = context.user_data['buy_chips']
        rate = cost / chips

        # Get current balances
        current = api.get_club_balances()

        # Check if enough MVR
        if current['mvr_balance'] < cost:
            await update.message.reply_text(
                f"❌ <b>Not Enough MVR!</b>\n\n"
                f"You need: {cost:,.2f} MVR\n"
                f"You have: {current['mvr_balance']:,.2f} MVR\n"
                f"Short by: {cost - current['mvr_balance']:,.2f} MVR\n\n"
                f"Please add MVR cash first from Club Balances menu.",
                parse_mode='HTML'
            )
            context.user_data.clear()
            return ConversationHandler.END

        # Buy chips
        admin_name = update.effective_user.username or update.effective_user.first_name or 'Admin'
        result = api.buy_chips_for_club(chips, cost, admin_name)

        if result['success']:
            rate_change = ""
            if result['rate'] > current['avg_chip_rate']:
                rate_change = f"⚠️ Higher than avg ({current['avg_chip_rate']:.4f})"
            elif result['rate'] < current['avg_chip_rate']:
                rate_change = f"✅ Lower than avg ({current['avg_chip_rate']:.4f})"

            await update.message.reply_text(
                f"✅ <b>Chips Purchased!</b>\n\n"
                f"🎲 Bought: {chips:,.0f} chips\n"
                f"💰 Cost: {cost:,.2f} MVR\n"
                f"📊 Rate: {rate:.4f} MVR/chip {rate_change}\n\n"
                f"<b>Updated Balances:</b>\n"
                f"🎲 Chip Inventory: {result['new_chip_inventory']:,.0f}\n"
                f"💰 MVR Balance: {result['new_mvr_balance']:,.2f}\n\n"
                f"📊 New Avg Rate: {result['new_avg_rate']:.4f} MVR/chip\n"
                f"💎 Total Invested in Chips: {result['total_chip_cost']:,.2f} MVR",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ Failed to buy chips: {result.get('error', 'Unknown error')}",
                parse_mode='HTML'
            )

        # Clean up
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter cost in MVR:",
            parse_mode='HTML'
        )
        return BALANCE_BUY_COST


async def balance_add_cash_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding cash"""
    query = update.callback_query
    await query.answer()

    balances = api.get_club_balances()

    keyboard = [
        [InlineKeyboardButton("💰 MVR", callback_data="add_cash_mvr")],
        [InlineKeyboardButton("💵 USD", callback_data="add_cash_usd")],
        [InlineKeyboardButton("💎 USDT", callback_data="add_cash_usdt")],
        [InlineKeyboardButton("« Cancel", callback_data="admin_club_balances")]
    ]

    await query.edit_message_text(
        f"💵 <b>Add Cash to Club</b>\n\n"
        f"Current Balances:\n"
        f"💰 MVR: {balances['mvr_balance']:,.2f}\n"
        f"💵 USD: {balances['usd_balance']:,.2f}\n"
        f"💎 USDT: {balances['usdt_balance']:,.2f}\n\n"
        f"Select currency:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return BALANCE_ADD_CURRENCY


async def balance_add_currency_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Currency selected"""
    query = update.callback_query
    await query.answer()

    currency = query.data.split('_')[2].upper()  # Extract MVR/USD/USDT
    context.user_data['add_currency'] = currency

    await query.edit_message_text(
        f"💵 <b>Add {currency}</b>\n\n"
        f"How much {currency} are you adding?",
        parse_mode='HTML'
    )

    return BALANCE_ADD_AMOUNT


async def balance_add_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive amount"""
    try:
        amount = float(update.message.text.strip())

        if amount <= 0:
            await update.message.reply_text(
                "❌ Amount must be greater than 0. Please enter amount:",
                parse_mode='HTML'
            )
            return BALANCE_ADD_AMOUNT

        context.user_data['add_amount'] = amount
        currency = context.user_data['add_currency']

        await update.message.reply_text(
            f"✅ Adding: {amount:,.2f} {currency}\n\n"
            f"Add a note? (optional)\n"
            f"Or send /skip to skip:",
            parse_mode='HTML'
        )

        return BALANCE_ADD_NOTE

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter amount:",
            parse_mode='HTML'
        )
        return BALANCE_ADD_AMOUNT


async def balance_add_note_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive note and complete cash addition"""
    note = ''
    if update.message.text.strip() != '/skip':
        note = update.message.text.strip()

    currency = context.user_data['add_currency']
    amount = context.user_data['add_amount']

    # Add cash
    admin_name = update.effective_user.username or update.effective_user.first_name or 'Admin'
    result = api.add_cash_to_club(currency, amount, note, admin_name)

    if result['success']:
        await update.message.reply_text(
            f"✅ <b>Cash Added!</b>\n\n"
            f"💵 Added: {amount:,.2f} {currency}\n"
            f"📝 Note: {note if note else 'None'}\n\n"
            f"<b>Updated Balances:</b>\n"
            f"💰 MVR: {result['new_mvr_balance']:,.2f}\n"
            f"💵 USD: {result['new_usd_balance']:,.2f}\n"
            f"💎 USDT: {result['new_usdt_balance']:,.2f}",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"❌ Failed to add cash: {result.get('error', 'Unknown error')}",
            parse_mode='HTML'
        )

    # Clean up
    context.user_data.clear()
    return ConversationHandler.END


# ========== COUNTER CONTROL HANDLERS ==========

async def counter_close_with_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask admin to upload closing poster"""
    query = update.callback_query
    await query.answer()

    # Check if there's a saved poster
    saved_poster = api.get_saved_poster('closing')

    if saved_poster:
        keyboard = [
            [InlineKeyboardButton("📤 Upload New Poster", callback_data="counter_close_new_poster")],
            [InlineKeyboardButton("♻️ Use Saved Poster", callback_data="counter_close_saved_poster")],
            [InlineKeyboardButton("« Cancel", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            "📸 <b>CLOSING POSTER</b>\n\n"
            "You have a saved closing poster. Use it or upload a new one?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(
            "📸 <b>Upload Closing Poster</b>\n\n"
            "Please send the poster image for the closing announcement:",
            parse_mode='HTML'
        )
        return COUNTER_CLOSE_POSTER


async def counter_close_new_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for new poster upload"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📸 <b>Upload New Closing Poster</b>\n\n"
        "Please send the poster image:",
        parse_mode='HTML'
    )
    return COUNTER_CLOSE_POSTER


async def counter_close_saved_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use saved poster for closing"""
    query = update.callback_query
    await query.answer()

    saved_poster = api.get_saved_poster('closing')
    if not saved_poster:
        await query.edit_message_text(
            "❌ Saved poster not found. Please upload a new one.",
            parse_mode='HTML'
        )
        return COUNTER_CLOSE_POSTER

    # Broadcast to all users
    await query.edit_message_text(
        "📤 <b>Broadcasting closing announcement...</b>",
        parse_mode='HTML'
    )

    user_ids = api.get_all_user_ids()
    success_count = 0
    failed_count = 0

    admin_name = query.from_user.username or query.from_user.first_name

    for user_id in user_ids:
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=saved_poster,
                caption="🔴 <b>COUNTER CLOSED</b>\n\nWe'll notify you when we open again!",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send closing announcement to {user_id}: {e}")

    # Update counter status
    api.set_counter_status('CLOSED', query.from_user.id, announcement_sent=True)

    await query.edit_message_text(
        f"✅ <b>Counter CLOSED</b>\n\n"
        f"📤 Announcement sent to {success_count} users\n"
        f"❌ Failed: {failed_count}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]])
    )
    return ConversationHandler.END


async def counter_close_poster_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive closing poster and broadcast"""
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send an image file.",
            parse_mode='HTML'
        )
        return COUNTER_CLOSE_POSTER

    photo = update.message.photo[-1]  # Highest quality
    file_id = photo.file_id

    # Save poster for future use
    api.set_counter_status('CLOSED', update.effective_user.id, announcement_sent=True)
    api.save_counter_poster('closing', file_id)

    # Broadcast to all users
    await update.message.reply_text(
        "📤 <b>Broadcasting closing announcement...</b>",
        parse_mode='HTML'
    )

    user_ids = api.get_all_user_ids()
    success_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=file_id,
                caption="🔴 <b>COUNTER CLOSED</b>\n\nWe'll notify you when we open again!",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send closing announcement to {user_id}: {e}")

    await update.message.reply_text(
        f"✅ <b>Counter CLOSED</b>\n\n"
        f"📤 Announcement sent to {success_count} users\n"
        f"❌ Failed: {failed_count}\n\n"
        f"Poster saved for future use.",
        parse_mode='HTML'
    )
    return ConversationHandler.END


async def counter_close_text_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close counter with text-only announcement"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📤 <b>Broadcasting closing announcement...</b>",
        parse_mode='HTML'
    )

    user_ids = api.get_all_user_ids()
    success_count = 0
    failed_count = 0

    admin_name = query.from_user.username or query.from_user.first_name

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔴 <b>COUNTER CLOSED</b>\n\nWe'll notify you when we open again!",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send closing announcement to {user_id}: {e}")

    # Update counter status
    api.set_counter_status('CLOSED', query.from_user.id, announcement_sent=True)

    await query.edit_message_text(
        f"✅ <b>Counter CLOSED</b>\n\n"
        f"📤 Announcement sent to {success_count} users\n"
        f"❌ Failed: {failed_count}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]])
    )


async def counter_close_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close counter without announcement"""
    query = update.callback_query
    await query.answer()

    api.set_counter_status('CLOSED', query.from_user.id, announcement_sent=False)

    await query.edit_message_text(
        "✅ <b>Counter CLOSED</b>\n\n"
        "No announcement sent to users.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]])
    )


# ========== COUNTER OPEN HANDLERS ==========

async def counter_open_with_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask admin to upload opening poster"""
    query = update.callback_query
    await query.answer()

    # Check if there's a saved poster
    saved_poster = api.get_saved_poster('opening')

    if saved_poster:
        keyboard = [
            [InlineKeyboardButton("📤 Upload New Poster", callback_data="counter_open_new_poster")],
            [InlineKeyboardButton("♻️ Use Saved Poster", callback_data="counter_open_saved_poster")],
            [InlineKeyboardButton("« Cancel", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            "📸 <b>OPENING POSTER</b>\n\n"
            "You have a saved opening poster. Use it or upload a new one?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(
            "📸 <b>Upload Opening Poster</b>\n\n"
            "Please send the poster image for the opening announcement:",
            parse_mode='HTML'
        )
        return COUNTER_OPEN_POSTER


async def counter_open_new_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for new poster upload"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📸 <b>Upload New Opening Poster</b>\n\n"
        "Please send the poster image:",
        parse_mode='HTML'
    )
    return COUNTER_OPEN_POSTER


async def counter_open_saved_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use saved poster for opening"""
    query = update.callback_query
    await query.answer()

    saved_poster = api.get_saved_poster('opening')
    if not saved_poster:
        await query.edit_message_text(
            "❌ Saved poster not found. Please upload a new one.",
            parse_mode='HTML'
        )
        return COUNTER_OPEN_POSTER

    # Broadcast to all users
    await query.edit_message_text(
        "📤 <b>Broadcasting opening announcement...</b>",
        parse_mode='HTML'
    )

    user_ids = api.get_all_user_ids()
    success_count = 0
    failed_count = 0

    admin_name = query.from_user.username or query.from_user.first_name

    for user_id in user_ids:
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=saved_poster,
                caption="🟢 <b>COUNTER NOW OPEN!</b>\n\nYou can now make deposits, withdrawals, and all requests!",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send opening announcement to {user_id}: {e}")

    # Update counter status
    api.set_counter_status('OPEN', query.from_user.id, announcement_sent=True)

    await query.edit_message_text(
        f"✅ <b>Counter OPEN</b>\n\n"
        f"📤 Announcement sent to {success_count} users\n"
        f"❌ Failed: {failed_count}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]])
    )
    return ConversationHandler.END


async def counter_open_poster_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive opening poster and broadcast"""
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send an image file.",
            parse_mode='HTML'
        )
        return COUNTER_OPEN_POSTER

    photo = update.message.photo[-1]  # Highest quality
    file_id = photo.file_id

    # Save poster for future use
    api.set_counter_status('OPEN', update.effective_user.id, announcement_sent=True)
    api.save_counter_poster('opening', file_id)

    # Broadcast to all users
    await update.message.reply_text(
        "📤 <b>Broadcasting opening announcement...</b>",
        parse_mode='HTML'
    )

    user_ids = api.get_all_user_ids()
    success_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=file_id,
                caption="🟢 <b>COUNTER NOW OPEN!</b>\n\nYou can now make deposits, withdrawals, and all requests!",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send opening announcement to {user_id}: {e}")

    await update.message.reply_text(
        f"✅ <b>Counter OPEN</b>\n\n"
        f"📤 Announcement sent to {success_count} users\n"
        f"❌ Failed: {failed_count}\n\n"
        f"Poster saved for future use.",
        parse_mode='HTML'
    )
    return ConversationHandler.END


async def counter_open_text_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open counter with text-only announcement"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📤 <b>Broadcasting opening announcement...</b>",
        parse_mode='HTML'
    )

    user_ids = api.get_all_user_ids()
    success_count = 0
    failed_count = 0

    admin_name = query.from_user.username or query.from_user.first_name

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🟢 <b>COUNTER NOW OPEN!</b>\n\nYou can now make deposits, withdrawals, and all requests!",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limit
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send opening announcement to {user_id}: {e}")

    # Update counter status
    api.set_counter_status('OPEN', query.from_user.id, announcement_sent=True)

    await query.edit_message_text(
        f"✅ <b>Counter OPEN</b>\n\n"
        f"📤 Announcement sent to {success_count} users\n"
        f"❌ Failed: {failed_count}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]])
    )


async def counter_open_silent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open counter without announcement"""
    query = update.callback_query
    await query.answer()

    admin_name = query.from_user.username or query.from_user.first_name
    api.set_counter_status('OPEN', query.from_user.id, announcement_sent=False)

    await query.edit_message_text(
        "✅ <b>Counter OPEN</b>\n\n"
        "No announcement sent to users.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]])
    )


# Promotion Management Handlers
async def promo_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start promotion creation"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Admin access required.")
        return ConversationHandler.END

    await query.edit_message_text(
        "🎁 **Create New Promotion**\n\n"
        "Please enter the bonus percentage (e.g., 10 for 10%):",
        parse_mode='Markdown'
    )

    return PROMO_PERCENTAGE


async def promo_percentage_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive promotion bonus percentage"""
    try:
        percentage = float(update.message.text)
        if percentage <= 0 or percentage > 100:
            await update.message.reply_text(
                "❌ Invalid percentage. Please enter a number between 0 and 100:"
            )
            return PROMO_PERCENTAGE

        context.user_data['promo_percentage'] = percentage

        await update.message.reply_text(
            f"✅ Bonus: {percentage}%\n\n"
            f"📅 Enter start date (format: YYYY-MM-DD):",
            parse_mode='Markdown'
        )

        return PROMO_START_DATE

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid number (e.g., 10 for 10%):"
        )
        return PROMO_PERCENTAGE


async def promo_start_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive promotion start date"""
    from datetime import datetime as dt

    try:
        start_date_str = update.message.text.strip()
        # Validate date format
        start_date = dt.strptime(start_date_str, '%Y-%m-%d')

        context.user_data['promo_start_date'] = start_date_str

        await update.message.reply_text(
            f"✅ Start Date: {start_date_str}\n\n"
            f"📅 Enter end date (format: YYYY-MM-DD):",
            parse_mode='Markdown'
        )

        return PROMO_END_DATE

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-12-31):"
        )
        return PROMO_START_DATE


async def promo_end_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive promotion end date and create promotion"""
    from datetime import datetime as dt

    try:
        end_date_str = update.message.text.strip()
        # Validate date format
        end_date = dt.strptime(end_date_str, '%Y-%m-%d')
        start_date = dt.strptime(context.user_data['promo_start_date'], '%Y-%m-%d')

        # Validate end date is after start date
        if end_date < start_date:
            await update.message.reply_text(
                "❌ End date must be after start date. Please enter a valid end date:"
            )
            return PROMO_END_DATE

        # Create BONUS promotion
        promotion_id = api.create_promotion(
            bonus_percentage=context.user_data['promo_percentage'],
            start_date=context.user_data['promo_start_date'],
            end_date=end_date_str,
            admin_id=update.effective_user.id
        )

        if promotion_id:
            await update.message.reply_text(
                f"✅ **Bonus Promotion Created!**\n\n"
                f"🆔 ID: `{promotion_id}`\n"
                f"💰 Bonus: {context.user_data['promo_percentage']}%\n"
                f"📅 Period: {context.user_data['promo_start_date']} to {end_date_str}\n\n"
                f"The promotion is now active!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to create promotion. Please try again.")

        # Clear user data
        context.user_data.clear()

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-12-31):"
        )
        return PROMO_END_DATE


async def promo_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel promotion creation"""
    await update.message.reply_text("❌ Promotion creation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


# Cashback Promotion Handlers
async def cashback_promo_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start cashback promotion creation"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Admin access required.")
        return ConversationHandler.END

    await query.edit_message_text(
        "💸 **Create New Cashback Promotion**\n\n"
        "Please enter the cashback percentage (e.g., 10 for 10%):",
        parse_mode='Markdown'
    )

    return CASHBACK_PROMO_PERCENTAGE


async def cashback_promo_percentage_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive cashback promotion percentage"""
    try:
        percentage = float(update.message.text)
        if percentage <= 0 or percentage > 100:
            await update.message.reply_text(
                "❌ Invalid percentage. Please enter a number between 0 and 100:"
            )
            return CASHBACK_PROMO_PERCENTAGE

        context.user_data['cashback_promo_percentage'] = percentage

        await update.message.reply_text(
            f"✅ Cashback: {percentage}%\n\n"
            f"📅 Enter start date (format: YYYY-MM-DD):",
            parse_mode='Markdown'
        )

        return CASHBACK_PROMO_START_DATE

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid number (e.g., 10 for 10%):"
        )
        return CASHBACK_PROMO_PERCENTAGE


async def cashback_promo_start_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive cashback promotion start date"""
    from datetime import datetime as dt

    try:
        start_date_str = update.message.text.strip()
        # Validate date format
        start_date = dt.strptime(start_date_str, '%Y-%m-%d')

        context.user_data['cashback_promo_start_date'] = start_date_str

        await update.message.reply_text(
            f"✅ Start Date: {start_date_str}\n\n"
            f"📅 Enter end date (format: YYYY-MM-DD):",
            parse_mode='Markdown'
        )

        return CASHBACK_PROMO_END_DATE

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-12-31):"
        )
        return CASHBACK_PROMO_START_DATE


async def cashback_promo_end_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive cashback promotion end date and create promotion"""
    from datetime import datetime as dt

    try:
        end_date_str = update.message.text.strip()
        # Validate date format
        end_date = dt.strptime(end_date_str, '%Y-%m-%d')
        start_date = dt.strptime(context.user_data['cashback_promo_start_date'], '%Y-%m-%d')

        # Validate end date is after start date
        if end_date < start_date:
            await update.message.reply_text(
                "❌ End date must be after start date. Please enter a valid end date:"
            )
            return CASHBACK_PROMO_END_DATE

        # Create CASHBACK promotion
        promotion_id = api.create_cashback_promotion(
            cashback_percentage=context.user_data['cashback_promo_percentage'],
            start_date=context.user_data['cashback_promo_start_date'],
            end_date=end_date_str,
            admin_id=update.effective_user.id
        )

        if promotion_id:
            await update.message.reply_text(
                f"✅ **Cashback Promotion Created!**\n\n"
                f"🆔 ID: `{promotion_id}`\n"
                f"💸 Cashback: {context.user_data['cashback_promo_percentage']}%\n"
                f"📅 Period: {context.user_data['cashback_promo_start_date']} to {end_date_str}\n\n"
                f"The cashback promotion is now active!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to create cashback promotion. Please try again.")

        # Clear user data
        context.user_data.clear()

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-12-31):"
        )
        return CASHBACK_PROMO_END_DATE


async def cashback_promo_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel cashback promotion creation"""
    await update.message.reply_text("❌ Cashback promotion creation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


# Quick Approval/Rejection Handlers
async def quick_approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve deposit from notification"""
    query = update.callback_query

    try:
        logger.info(f"Admin {query.from_user.id} clicked approve button")

        if not is_admin(query.from_user.id):
            await query.answer("❌ Not authorized", show_alert=True)
            return

        request_id = int(query.data.split('_')[-1])

        # Check if another admin is already processing this request
        if request_id in processing_requests:
            await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
            return

        # Lock this request to this admin
        processing_requests[request_id] = query.from_user.id
        await query.answer("Processing approval...")

        logger.info(f"Approving deposit request: {request_id}")

        deposit = api.get_deposit_request(request_id)

        if not deposit:
            await query.edit_message_text(
                f"{query.message.text}\n\n❌ _Request not found in database._",
                parse_mode='Markdown'
            )
            logger.error(f"Deposit request {request_id} not found")
            # Clean up processing lock
            if request_id in processing_requests:
                del processing_requests[request_id]
            return

        # Check if already approved
        if deposit.get('status') != 'Pending':
            status = deposit.get('status', 'Unknown')
            await query.edit_message_text(
                f"{query.message.text}\n\n✅ <b>Already {status}</b>\n\nThis request was already processed by another admin.",
                parse_mode='HTML'
            )
            logger.info(f"Deposit {request_id} already {status}")
            # Clean up processing lock
            if request_id in processing_requests:
                del processing_requests[request_id]
            return

        # Extract user details once at the top
        user_details = deposit.get('user_details', {})
        user_telegram_id = user_details.get('telegram_id') or deposit.get('user')
        username = user_details.get('username', 'User')

        # Update status using Django API
        api.approve_deposit(request_id, query.from_user.id)
        logger.info(f"Deposit {request_id} status updated to Approved")

        # Add free spins based on deposit amount
        spins_message = ""
        spins_added = 0  # Initialize to 0

        try:
            # Amount is already stored in MVR (USDT/USD are converted at deposit time)
            amount_mvr = float(deposit['amount'])
            method = deposit.get('method', 'BML')

            logger.info(f"🎰 SPIN CALCULATION START - User: {user_telegram_id}, Amount: {amount_mvr} MVR, Method: {method}")

            logger.info(f"🎲 Calling add_spins_from_deposit with amount_mvr={amount_mvr}, user={user_telegram_id}")
            spins_added = await spin_bot.add_spins_from_deposit(
                user_id=user_telegram_id,
                username=username,
                amount_mvr=amount_mvr,
                pppoker_id=deposit.get('pppoker_id', '')
            )
            logger.info(f"✅ SPIN RESULT: {spins_added} spins added to user {user_telegram_id}")

            if spins_added > 0:
                spins_message = f"\n\n🎰 <b>FREE SPINS BONUS!</b>\n+{spins_added} free spins added!\nClick button below to play!"
                logger.info(f"🎉 User will receive spin message: {spins_added} spins")
            else:
                logger.info(f"ℹ️ No spins added (amount {amount_mvr} MVR below minimum threshold)")
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR adding spins for deposit: {e}")
            logger.error(f"   User ID: {user_telegram_id}, Username: {username}, Amount: {amount}, Method: {method}")
            import traceback
            traceback.print_exc()

        # Check for promotion bonus
        promo_data = context.bot_data.get(f'promo_{request_id}')
        bonus_message = ""

        if promo_data:
            # Record promotion bonus
            success = api.record_promotion_bonus(
                user_id=promo_data['user_id'],
                pppoker_id=promo_data['pppoker_id'],
                promotion_id=promo_data['promotion_id'],
                deposit_request_id=request_id,
                deposit_amount=promo_data['deposit_amount'],
                bonus_amount=promo_data['bonus_amount']
            )

            if success:
                total_with_bonus = promo_data['deposit_amount'] + promo_data['bonus_amount']
                bonus_message = f"\n\n🎁 <b>PROMOTION BONUS APPLIED!</b>\n" \
                              f"💰 Bonus: <b>+{promo_data['bonus_amount']:.2f} {promo_data['currency']}</b>\n" \
                              f"💎 Total credited: <b>{total_with_bonus:.2f} {promo_data['currency']}</b>"
                logger.info(f"Promotion bonus recorded for user {promo_data['user_id']}: {promo_data['bonus_amount']} {promo_data['currency']}")

            # Clean up promotion data
            del context.bot_data[f'promo_{request_id}']

        # Notify user with club link button and spins button if applicable
        club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"
        keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]

        # Add "Play Spins" button if spins were added
        if spins_added > 0:
            keyboard.append([InlineKeyboardButton("🎲 Play Free Spins", callback_data="play_freespins")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Format amount nicely
        amount = float(deposit['amount'])
        # All deposits are stored in MVR (USDT/USD are converted)
        currency = 'MVR'

        try:
            await context.bot.send_message(
                chat_id=user_telegram_id,
                text=f"🎉 <b>DEPOSIT APPROVED!</b> 🎉\n\n"
                     f"━━━━━━━━━━━━━━━━━━\n"
                     f"✅ Your deposit has been successfully approved!\n\n"
                     f"💰 <b>Amount:</b> {amount:.2f} {currency}\n"
                     f"🎮 <b>PPPoker ID:</b> <code>{deposit['pppoker_id']}</code>\n"
                     f"📋 <b>Request ID:</b> <code>{request_id}</code>\n"
                     f"{bonus_message}{spins_message}\n"
                     f"━━━━━━━━━━━━━━━━━━\n\n"
                     f"💎 Your chips have been added to your account!\n"
                     f"🎲 Ready to play? Click the button below!\n\n"
                     f"Good luck and happy gaming! 🍀",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            logger.info(f"User {user_telegram_id} notified of approval")
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        # Update message for ALL admins (remove buttons + add status)
        admin_name = query.from_user.first_name or query.from_user.username or "Admin"
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    # Get the original message text
                    original_text = query.message.text if admin_id == query.from_user.id else None

                    # Add approval status to the message
                    status_text = f"\n\n✅ <b>APPROVED by {admin_name}</b>"

                    # For the admin who approved, use their message
                    if admin_id == query.from_user.id:
                        await context.bot.edit_message_text(
                            chat_id=admin_id,
                            message_id=message_id,
                            text=f"{query.message.text}{status_text}",
                            parse_mode='HTML'
                        )
                    else:
                        # For other admins, remove buttons AND send notification
                        try:
                            # First, remove buttons from their notification
                            await context.bot.edit_message_reply_markup(
                                chat_id=admin_id,
                                message_id=message_id,
                                reply_markup=InlineKeyboardMarkup([])
                            )
                            # Then send them a notification about who approved
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"✅ <b>Deposit {request_id} APPROVED</b>\n\n"
                                     f"👤 Approved by: {admin_name}\n"
                                     f"💰 Amount: {deposit['amount']} MVR\n"
                                     f"User notified and chips credited.",
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin_id}: {e}")

                    logger.info(f"Updated notification for admin {admin_id} on deposit {request_id}")
                except Exception as e:
                    logger.error(f"Failed to update message for admin {admin_id}: {e}")
            # Clean up stored message IDs
            del notification_messages[request_id]

        # Clean up processing lock
        if request_id in processing_requests:
            del processing_requests[request_id]

    except Exception as e:
        logger.error(f"Error in quick_approve_deposit: {e}")
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)
        # Clean up processing lock on error
        if request_id in processing_requests:
            del processing_requests[request_id]


async def quick_reject_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick reject deposit - ask for reason"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    request_id = int(query.data.split('_')[-1])

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Check if deposit still pending
    deposit = api.get_deposit_request(request_id)
    if not deposit or deposit.get('status') != 'Pending':
        status = deposit.get('status', 'Not found') if deposit else 'Not found'
        await query.answer(f"⛔ Request already {status}", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_deposit_{request_id}"

    # Clean up promotion data if exists (rejection means no bonus)
    if f'promo_{request_id}' in context.bot_data:
        del context.bot_data[f'promo_{request_id}']
        logger.info(f"Promotion bonus cancelled for rejected deposit {request_id}")

    # Update message for ALL admins (remove buttons + add status)
    admin_name = query.from_user.first_name or query.from_user.username or "Admin"
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                # Add rejection status to the message
                status_text = f"\n\n❌ <b>REJECTED by {admin_name}</b> (adding reason...)"

                # For the admin who rejected, show prompt for reason
                if admin_id == query.from_user.id:
                    # This admin will get a different message via edit_message_text below
                    pass
                else:
                    # For other admins, just remove buttons
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )

                logger.info(f"Updated notification for admin {admin_id} - deposit {request_id} being rejected")
            except Exception as e:
                logger.error(f"Failed to update message for admin {admin_id}: {e}")
        # Clean up stored message IDs
        del notification_messages[request_id]

    await query.edit_message_text(
        f"❌ Rejecting Deposit Request {request_id}\n\n"
        f"✏️ Please type the rejection reason:",
        reply_markup=None
    )


async def quick_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve withdrawal from notification"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    request_id = int(query.data.split('_')[-1])

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    withdrawal = api.get_withdrawal_request(request_id)

    if not withdrawal:
        await query.edit_message_text(f"{query.message.text}\n\n❌ _Request not found._", parse_mode='Markdown')
        if request_id in processing_requests:
            del processing_requests[request_id]
        return

    # Check if already processed
    if withdrawal.get('status') != 'Pending':
        status = withdrawal.get('status', 'Unknown')
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ <b>Already {status}</b>\n\nThis request was already processed by another admin.",
            parse_mode='HTML'
        )
        if request_id in processing_requests:
            del processing_requests[request_id]
        return

    # Update status using Django API
    api.approve_withdrawal(request_id, query.from_user.id)

    # Notify user with club link button
    club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"
    keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Get user telegram_id from user_details
    user_details = withdrawal.get('user_details', {})
    user_telegram_id = user_details.get('telegram_id') or withdrawal.get('user')

    # Format amount nicely
    amount = float(withdrawal['amount'])
    currency = 'MVR' if withdrawal.get('method') != 'USDT' else 'USD'

    try:
        await context.bot.send_message(
            chat_id=user_telegram_id,
            text=f"✅ <b>WITHDRAWAL APPROVED!</b> ✅\n\n"
                 f"━━━━━━━━━━━━━━━━━━\n"
                 f"💸 Your withdrawal has been processed!\n\n"
                 f"💰 <b>Amount:</b> {amount:.2f} {currency}\n"
                 f"🏦 <b>Method:</b> {withdrawal.get('method')}\n"
                 f"📱 <b>Account:</b> <code>{withdrawal['account_number']}</code>\n"
                 f"📋 <b>Request ID:</b> <code>{request_id}</code>\n\n"
                 f"━━━━━━━━━━━━━━━━━━\n\n"
                 f"💵 Your funds have been transferred!\n"
                 f"⏰ Please allow a few minutes for the transaction to complete.\n\n"
                 f"Thank you for playing with us! 🎮",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

    # Remove buttons for ALL admins and notify them
    admin_name = query.from_user.first_name or query.from_user.username or "Admin"
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                # Remove buttons
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
                # Send notification to other admins (not the one who approved)
                if admin_id != query.from_user.id:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"✅ <b>Withdrawal {request_id} APPROVED</b>\n\n"
                             f"👤 Approved by: {admin_name}\n"
                             f"💰 Amount: {withdrawal['amount']} {'MVR' if withdrawal.get('payment_method') != 'USDT' else 'USD'}\n"
                             f"User notified and withdrawal processed.",
                        parse_mode='HTML'
                    )
                logger.info(f"Removed approval buttons for admin {admin_id} on withdrawal {request_id}")
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
        # Clean up stored message IDs
        del notification_messages[request_id]

    # Clean up processing lock
    if request_id in processing_requests:
        del processing_requests[request_id]


async def quick_reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick reject withdrawal - ask for reason"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    request_id = int(query.data.split('_')[-1])

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Check if withdrawal still pending
    withdrawal = api.get_withdrawal_request(request_id)
    if not withdrawal or withdrawal.get('status') != 'Pending':
        status = withdrawal.get('status', 'Not found') if withdrawal else 'Not found'
        await query.answer(f"⛔ Request already {status}", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_withdrawal_{request_id}"

    # Remove buttons for ALL admins when rejection starts
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
                logger.info(f"Removed buttons for admin {admin_id} - withdrawal {request_id} being rejected")
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
        # Clean up stored message IDs
        del notification_messages[request_id]

    await query.edit_message_text(
        f"❌ Rejecting Withdrawal Request {request_id}\n\n"
        f"✏️ Please type the rejection reason:",
        reply_markup=None
    )


async def quick_approve_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve join request from notification"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    request_id = int(query.data.split('_')[-1])

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    join_req = api.get_join_request(request_id)

    if not join_req:
        await query.edit_message_text(f"{query.message.text}\n\n❌ _Request not found._", parse_mode='Markdown')
        if request_id in processing_requests:
            del processing_requests[request_id]
        return

    # Update status
    api.update_join_request_status(request_id, 'Approved', query.from_user.id)

    # Notify user
    user_details = join_req.get('user_details', {})
    user_id = user_details.get('telegram_id') or join_req.get('user_id') or join_req.get('user')
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ <b>Welcome to βILLIONAIRES!</b>\n\n🎮 You're approved - start playing!",
            parse_mode='HTML'
        )
        logger.info(f"✅ User {user_id} notified about join request {request_id} approval")
    except Exception as e:
        logger.error(f"❌ Failed to notify user {user_id} about join approval: {e}")

    # Edit the approving admin's message to show confirmation
    try:
        pppoker_id = join_req.get('pppoker_id', 'N/A')
        await query.edit_message_text(
            f"✅ <b>JOIN REQUEST APPROVED</b>\n\n"
            f"👤 User: {user_id}\n"
            f"🎮 PPPoker ID: {pppoker_id}\n"
            f"🎫 Request ID: {request_id}\n\n"
            f"✨ User has been notified!",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to edit approval message: {e}")

    # Remove buttons for ALL other admins
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
                logger.info(f"Removed approval buttons for admin {admin_id} on join request {request_id}")
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
        # Clean up stored message IDs
        del notification_messages[request_id]

    # Clean up processing lock
    if request_id in processing_requests:
        del processing_requests[request_id]


async def quick_reject_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick reject join request - ask for reason"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    request_id = int(query.data.split('_')[-1])

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_join_{request_id}"

    # Remove buttons for ALL admins when rejection starts
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
                logger.info(f"Removed buttons for admin {admin_id} - join request {request_id} being rejected")
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
        # Clean up stored message IDs
        del notification_messages[request_id]

    await query.edit_message_text(
        f"❌ Rejecting Join Request {request_id}\n\n"
        f"✏️ Please type the rejection reason:",
        reply_markup=None
    )


# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Operation cancelled.")
    else:
        await update.message.reply_text("❌ Operation cancelled. Use /start to see the main menu.")

    context.user_data.clear()

    # If user was in support mode, end it
    user_id = update.effective_user.id
    if user_id in support_mode_users:
        support_mode_users.remove(user_id)
        if user_id in live_support_sessions:
            del live_support_sessions[user_id]

    return ConversationHandler.END


async def cancel_keyword_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel keywords like 'cancel', 'exit', 'stop'"""
    text = update.message.text.lower().strip()

    if text in ['cancel', 'exit', 'stop', 'quit', 'close']:
        await update.message.reply_text(
            "❌ Operation cancelled. Use /start to see the main menu."
        )

        context.user_data.clear()

        # If user was in support mode, end it
        user_id = update.effective_user.id
        if user_id in support_mode_users:
            support_mode_users.remove(user_id)
            if user_id in live_support_sessions:
                del live_support_sessions[user_id]

            # Notify admin
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"💬 Support session ended by user {update.effective_user.first_name}"
            )

        return ConversationHandler.END

    return None  # Not a cancel keyword, continue normal flow


async def handle_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rejection reason from admin"""
    admin_id = update.effective_user.id
    reason = update.message.text.strip()

    context_data = admin_reply_context[admin_id]
    parts = context_data.split('_')
    request_type = parts[1]  # deposit, withdrawal, join, or seat

    # For seat requests, the ID is "SEAT_XXXXX" so we need to rejoin the remaining parts
    if request_type == 'seat':
        request_id = int(''.join(parts[2:]))  # Convert to int for seat requests
    else:
        request_id = int(parts[2])  # Convert to int

    if request_type == 'deposit':
        deposit = api.get_deposit_request(request_id)
        if deposit:
            api.reject_deposit(request_id, admin_id, reason)

            # Get user telegram_id from user_details
            user_details = deposit.get('user_details', {})
            user_telegram_id = user_details.get('telegram_id') or deposit.get('user')

            # Format amount nicely
            amount = float(deposit['amount'])
            currency = 'MVR' if deposit.get('method') != 'USDT' else 'USD'

            try:
                await context.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"❌ <b>DEPOSIT REJECTED</b> ❌\n\n"
                         f"━━━━━━━━━━━━━━━━━━\n"
                         f"We're sorry, but your deposit request has been rejected.\n\n"
                         f"💰 <b>Amount:</b> {amount:.2f} {currency}\n"
                         f"📋 <b>Request ID:</b> <code>{request_id}</code>\n\n"
                         f"📝 <b>Reason:</b>\n{reason}\n\n"
                         f"━━━━━━━━━━━━━━━━━━\n\n"
                         f"💬 Need help? Contact our support team for assistance.\n"
                         f"📞 We're here to help you resolve this!",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")

            await update.message.reply_text(f"✅ Deposit {request_id} rejected. User notified.")

            # Notify other admins
            admin_name = update.effective_user.first_name or update.effective_user.username or "Admin"
            try:
                admins_response = api.get_all_admins()
                if isinstance(admins_response, dict) and 'results' in admins_response:
                    admins = admins_response['results']
                else:
                    admins = admins_response

                for admin in admins:
                    if admin['telegram_id'] != admin_id:
                        try:
                            await context.bot.send_message(
                                chat_id=admin['telegram_id'],
                                text=f"❌ <b>Deposit {request_id} REJECTED</b>\n\n"
                                     f"👤 Rejected by: {admin_name}\n"
                                     f"💰 Amount: {deposit['amount']} {'MVR' if deposit.get('method') != 'USDT' else 'USD'}\n"
                                     f"📝 Reason: {reason}",
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin['telegram_id']}: {e}")
            except Exception as e:
                logger.error(f"Failed to get admin list: {e}")

    elif request_type == 'withdrawal':
        withdrawal = api.get_withdrawal_request(request_id)
        if withdrawal:
            api.reject_withdrawal(request_id, admin_id, reason)

            # Get user telegram_id from user_details
            user_details = withdrawal.get('user_details', {})
            user_telegram_id = user_details.get('telegram_id') or withdrawal.get('user')

            # Format amount nicely
            amount = float(withdrawal['amount'])
            currency = 'MVR' if withdrawal.get('payment_method') != 'USDT' else 'USD'

            try:
                await context.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"❌ <b>WITHDRAWAL REJECTED</b> ❌\n\n"
                         f"━━━━━━━━━━━━━━━━━━\n"
                         f"We're sorry, but your withdrawal request has been rejected.\n\n"
                         f"💰 <b>Amount:</b> {amount:.2f} {currency}\n"
                         f"🏦 <b>Method:</b> {withdrawal.get('payment_method', withdrawal.get('method'))}\n"
                         f"📋 <b>Request ID:</b> <code>{request_id}</code>\n\n"
                         f"📝 <b>Reason:</b>\n{reason}\n\n"
                         f"━━━━━━━━━━━━━━━━━━\n\n"
                         f"💬 Need help? Contact our support team for assistance.\n"
                         f"📞 We're here to help you resolve this!",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")

            await update.message.reply_text(f"✅ Withdrawal {request_id} rejected. User notified.")

            # Notify other admins
            admin_name = update.effective_user.first_name or update.effective_user.username or "Admin"
            try:
                admins_response = api.get_all_admins()
                if isinstance(admins_response, dict) and 'results' in admins_response:
                    admins = admins_response['results']
                else:
                    admins = admins_response

                for admin in admins:
                    if admin['telegram_id'] != admin_id:
                        try:
                            await context.bot.send_message(
                                chat_id=admin['telegram_id'],
                                text=f"❌ <b>Withdrawal {request_id} REJECTED</b>\n\n"
                                     f"👤 Rejected by: {admin_name}\n"
                                     f"💰 Amount: {withdrawal['amount']} {'MVR' if withdrawal.get('payment_method') != 'USDT' else 'USD'}\n"
                                     f"📝 Reason: {reason}",
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin['telegram_id']}: {e}")
            except Exception as e:
                logger.error(f"Failed to get admin list: {e}")

    elif request_type == 'join':
        join_req = api.get_join_request(request_id)
        if join_req:
            api.update_join_request_status(request_id, 'Rejected', admin_id)

            try:
                await context.bot.send_message(
                    chat_id=join_req['user_id'],
                    text=f"❌ <b>Join request declined</b>\n\n"
                         f"Reason: {reason}",
                    parse_mode='HTML'
                )
            except:
                pass

            await update.message.reply_text(f"✅ Join request {request_id} rejected. User notified.")

    elif request_type == 'seat':
        seat_req = api.get_seat_request(request_id)
        if seat_req:
            api.reject_seat_request(request_id, admin_id, reason)

            # Extract user telegram ID from user_details
            user_telegram_id = seat_req.get('user_details', {}).get('telegram_id')
            if not user_telegram_id:
                user_telegram_id = seat_req.get('user_id')  # fallback

            try:
                await context.bot.send_message(
                    chat_id=user_telegram_id,
                    text=f"❌ <b>Seat request rejected</b>\n\n"
                         f"Reason: {reason}",
                    parse_mode='HTML'
                )
            except:
                pass

            await update.message.reply_text(f"✅ Seat request {request_id} rejected. User notified.")

    # Clear context
    del admin_reply_context[admin_id]


# Seat Request Admin Handlers
async def approve_seat_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approves seat request"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    # Extract request_id from callback data and convert to int
    request_id = int(query.data.replace('approve_seat_', ''))
    await query.answer()

    # Get seat request details
    try:
        seat_req = api.get_seat_request(request_id)
        logger.info(f"Seat request retrieved: {seat_req}")
    except Exception as e:
        logger.error(f"Error getting seat request {request_id}: {e}")
        seat_req = None

    if not seat_req:
        await query.edit_message_text(
            f"{query.message.text}\n\n❌ _Seat request not found._\nRequest ID: {request_id}",
            parse_mode='HTML'
        )
        return

    # Check if already processed
    if seat_req.get('status') != 'Pending':
        await query.edit_message_text(
            f"{query.message.text}\n\n⚠️ _This request was already {seat_req['status'].lower()}._",
            parse_mode='HTML'
        )
        return

    # Approve in database
    success = api.approve_seat_request(request_id, query.from_user.id)

    if success:
        # Remove buttons for ALL admins
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
            del notification_messages[request_id]

        # Get payment account details
        payment_accounts = api.get_all_payment_accounts()

        # Extract user telegram ID from user_details
        user_telegram_id = seat_req.get('user_details', {}).get('telegram_id')
        if not user_telegram_id:
            logger.error(f"No telegram_id found in seat request: {seat_req}")
            user_telegram_id = seat_req.get('user_id')  # fallback

        # Build payment account buttons
        keyboard = []
        if 'BML' in payment_accounts and payment_accounts['BML']['account_number']:
            keyboard.append([InlineKeyboardButton(
                "💳 BML",
                callback_data=f"show_account_bml_{request_id}"
            )])

        if 'MIB' in payment_accounts and payment_accounts['MIB']['account_number']:
            keyboard.append([InlineKeyboardButton(
                "💳 MIB",
                callback_data=f"show_account_mib_{request_id}"
            )])

        if 'USD' in payment_accounts and payment_accounts['USD']['account_number']:
            keyboard.append([InlineKeyboardButton(
                "💳 USD",
                callback_data=f"show_account_usd_{request_id}"
            )])

        if 'USDT' in payment_accounts and payment_accounts['USDT']['account_number']:
            keyboard.append([InlineKeyboardButton(
                "💳 USDT",
                callback_data=f"show_account_usdt_{request_id}"
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Notify user with payment details
        try:
            await context.bot.send_message(
                chat_id=user_telegram_id,
                text=f"✅ <b>Seat approved!</b>\n\n"
                     f"🪑 {seat_req['amount']} chips ready\n\n"
                     f"💳 <b>Choose payment method below:</b>\n"
                     f"Click on an account to see details, then upload your payment slip.",
                parse_mode='HTML',
                reply_markup=reply_markup
            )

            # Store data and add user to credit list
            seat_request_data[user_telegram_id] = {
                'request_id': request_id,
                'amount': seat_req['amount'],
                'pppoker_id': seat_req['pppoker_id']
            }

            # Add user to credit list
            api.add_user_credit(
                user_telegram_id,
                seat_req.get('user_details', {}).get('username', 'User'),
                seat_req['pppoker_id'],
                seat_req['amount'],
                request_id
            )

            # Schedule first reminder (1 minute)
            job = context.job_queue.run_once(
                first_slip_reminder,
                when=60,  # 1 minute
                data=user_telegram_id,
                name=f"seat_reminder1_{user_telegram_id}"
            )
            seat_reminder_jobs[user_telegram_id] = job

        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        await query.edit_message_text(
            f"{query.message.text}\n\n✅ <b>APPROVED by {query.from_user.first_name}</b>\n"
            f"User notified with payment details.",
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            f"{query.message.text}\n\n❌ _Failed to approve._",
            parse_mode='HTML'
        )


async def reject_seat_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects seat request - ask for reason"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    # Extract request_id from callback data and convert to int
    request_id = int(query.data.replace('reject_seat_', ''))
    await query.answer()

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_seat_{request_id}"

    # Remove buttons for ALL admins when rejection starts
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
        del notification_messages[request_id]

    await query.edit_message_text(
        f"{query.message.text}\n\n❌ **REJECTING**\n\n"
        f"Please type the reason for rejection:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([])
    )


async def auto_reject_seat_request(context: ContextTypes.DEFAULT_TYPE):
    """Auto-reject seat request if not processed within 2 minutes"""
    job_data = context.job.data
    request_id = job_data['request_id']
    user_id = job_data['user_id']
    amount = job_data['amount']
    pppoker_id = job_data['pppoker_id']

    # Check if seat request still pending
    seat_req = api.get_seat_request(request_id)
    if not seat_req or seat_req.get('status') != 'Pending':
        # Already processed, no need to auto-reject
        logger.info(f"Seat request {request_id} already processed, skipping auto-reject")
        return

    # Auto-reject the seat request
    try:
        api.reject_seat_request(request_id, 0, "Auto-rejected: Response timeout (2 minutes)")
        logger.info(f"Auto-rejected seat request {request_id} due to timeout")

        # Remove buttons for ALL admins
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_text(
                        chat_id=admin_id,
                        message_id=message_id,
                        text=f"🪑 <b>SEAT REQUEST - AUTO-REJECTED</b>\n\n"
                             f"<b>Request ID:</b> {request_id}\n"
                             f"<b>User ID:</b> <code>{user_id}</code>\n"
                             f"<b>PPPoker ID:</b> <code>{pppoker_id}</code>\n"
                             f"<b>Amount:</b> <b>{amount} chips/MVR</b>\n\n"
                             f"⏰ <b>Auto-rejected:</b> Response timeout (2 minutes)\n"
                             f"No admin action was taken within the time limit.",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to update message for admin {admin_id}: {e}")
            del notification_messages[request_id]

        # Notify user with a nice message
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏰ <b>Seat Request Timeout</b>\n\n"
                     f"Your seat request has been automatically closed.\n\n"
                     f"💰 Amount: {amount} chips/MVR\n"
                     f"📋 Request ID: <code>{request_id}</code>\n\n"
                     f"Sorry for the inconvenience. Please try again.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Failed to auto-reject seat request {request_id}: {e}")


# Seat Slip Upload and Reminder Handlers
async def first_slip_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send first reminder after 1 minute if slip not uploaded"""
    user_id = context.job.data

    # Check if user still has active credit
    credit = api.get_user_credit(user_id)
    if not credit:
        # Already settled, cancel
        if user_id in seat_reminder_jobs:
            del seat_reminder_jobs[user_id]
        return

    # Check reminder count
    if credit.get('reminder_count', 0) >= 2:
        # Already sent final reminder, don't send again
        return

    # Increment reminder count
    api.increment_credit_reminder(user_id)

    # Send reminder
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ **Payment Slip Reminder**\n\n"
                 f"You have a credit of **{credit['amount']} chips/MVR**.\n\n"
                 f"📸 Please upload your payment slip or contact Live Support.\n\n"
                 f"_You have 1 more minute before you must contact Live Support._",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to send first reminder to user {user_id}: {e}")

    # Schedule final reminder (1 minute later)
    job = context.job_queue.run_once(
        final_slip_reminder,
        when=60,  # 1 minute
        data=user_id,
        name=f"seat_reminder2_{user_id}"
    )
    seat_reminder_jobs[user_id] = job


async def final_slip_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send final reminder after 2 minutes total"""
    user_id = context.job.data

    # Check if user still has active credit
    credit = api.get_user_credit(user_id)
    if not credit:
        # Already settled
        if user_id in seat_reminder_jobs:
            del seat_reminder_jobs[user_id]
        return

    # Increment reminder count
    api.increment_credit_reminder(user_id)

    # Send final reminder
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🚨 **Final Reminder**\n\n"
                 f"You have a credit of **{credit['amount']} chips/MVR**.\n\n"
                 f"❗ Please upload your payment slip NOW or contact Live Support immediately.\n\n"
                 f"_Your credit must be settled to continue using the service._",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to send final reminder to user {user_id}: {e}")

    # Clean up job tracking
    if user_id in seat_reminder_jobs:
        del seat_reminder_jobs[user_id]


async def show_seat_account_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show payment account details when user clicks BML/MIB button"""
    query = update.callback_query
    await query.answer()

    # Extract account type and request_id from callback data
    # Format: show_account_bml_123 or show_account_mib_123 or show_account_usd_123 or show_account_usdt_123
    parts = query.data.split('_')
    account_type = parts[2].upper()  # BML, MIB, USD, or USDT
    request_id = '_'.join(parts[3:])  # Handle if request_id contains underscores

    # Get payment accounts
    payment_accounts = api.get_all_payment_accounts()

    if account_type in payment_accounts:
        account = payment_accounts[account_type]
        account_number = account.get('account_number', 'N/A')
        account_name = account.get('account_name', account_type)

        # Show account details
        await query.edit_message_text(
            f"✅ <b>Seat approved!</b>\n\n"
            f"💳 <b>{account_type} Account Details:</b>\n\n"
            f"<b>Account Number:</b>\n<code>{account_number}</code>\n"
            f"<i>(tap to copy)</i>\n\n"
            f"<b>Account Name:</b>\n{account_name}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📸 Please send your payment slip photo showing the transfer to this account.",
            parse_mode='HTML'
        )
    else:
        await query.answer("❌ Account not found", show_alert=True)


async def upload_seat_slip_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle upload slip button click"""
    query = update.callback_query
    await query.answer()

    # Check if user has active seat request
    if query.from_user.id not in seat_request_data:
        await query.edit_message_text(
            "❌ No active seat request found.\n\n"
            "Please request a seat first using /seat command.",
            parse_mode='HTML'
        )
        return

    # Prompt user to send photo
    await query.edit_message_text(
        f"{query.message.text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📸 <b>Please send your payment slip photo now.</b>\n\n"
        f"Make sure the slip clearly shows:\n"
        f"• Transaction amount\n"
        f"• Account name\n"
        f"• Date and time",
        parse_mode='HTML'
    )


async def handle_seat_slip_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment slip upload for seat request"""
    user = update.effective_user

    # Check if user has pending seat request
    if user.id not in seat_request_data:
        # Not a seat slip, ignore
        return

    # Cancel reminder jobs if any
    if user.id in seat_reminder_jobs:
        try:
            seat_reminder_jobs[user.id].schedule_removal()
            del seat_reminder_jobs[user.id]
        except Exception as e:
            logger.error(f"Error canceling reminder job: {e}")

    # Download the photo
    photo = update.message.photo[-1]  # Get highest resolution
    photo_file_id = photo.file_id

    # Send processing message
    processing_msg = await update.message.reply_text(
        "📸 **Processing your payment slip...**\n\nPlease wait while we verify the details.",
        parse_mode='Markdown'
    )

    # Get seat request data
    seat_data = seat_request_data[user.id]
    request_id = seat_data['request_id']

    # Try OCR extraction using the same method as deposits
    ocr_details = ""
    try:
        # Download photo as bytes
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        # Process with Vision API
        extracted_details = await vision_api.process_receipt_image(bytes(file_bytes))

        # Format extracted details
        details_msg = vision_api.format_extracted_details(extracted_details)

        # Check if any details were actually extracted
        has_details = any([
            extracted_details.get('reference_number'),
            extracted_details.get('amount'),
            extracted_details.get('bank'),
            extracted_details.get('sender_name'),
            extracted_details.get('receiver_name'),
            extracted_details.get('receiver_account_number')
        ])

        if has_details:
            ocr_details = details_msg
            logger.info(f"Vision API extracted slip details for user {user.id}")
            await processing_msg.edit_text(
                "✅ **Slip details extracted successfully!**\n\n"
                f"{details_msg}\n\n"
                "Sending to admin for verification...",
                parse_mode='Markdown'
            )
        else:
            ocr_details = "Could not extract details - Manual verification required"
            logger.warning(f"Vision API could not parse slip details for user {user.id}")
            await processing_msg.edit_text(
                "⚠️ **Could not extract details automatically.**\n\n"
                "Your slip will be reviewed manually by admin.",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Vision API processing failed: {e}")
        ocr_details = "OCR failed - Manual verification required"
        await processing_msg.edit_text(
            "⚠️ **Could not extract slip details automatically.**\n\n"
            "Your slip has been saved and will be reviewed manually.",
            parse_mode='Markdown'
        )

    # Validate receiver name and account number (same as deposit validation)
    validation_warnings = ""
    if extracted_details:
        # Validate receiver name
        name_validation_warning = ""
        if extracted_details.get('receiver_name'):
            # Check against all payment methods since we don't know which one user used
            for method in ['BML', 'MIB']:
                stored_holder_name = api.get_payment_account_holder(method)
                if stored_holder_name:
                    extracted_receiver = extracted_details['receiver_name'].upper().strip()
                    stored_holder = stored_holder_name.upper().strip()

                    # Check if names match (allow partial match for flexibility)
                    if stored_holder not in extracted_receiver and extracted_receiver not in stored_holder:
                        name_validation_warning = f"\n\n⚠️ <b>NAME MISMATCH WARNING</b>\n" \
                                                 f"Slip receiver: {extracted_details['receiver_name']}\n" \
                                                 f"Check against: {stored_holder_name} ({method})"
                    else:
                        # Found a match, clear warning
                        name_validation_warning = ""
                        break

        # Validate receiver account number
        account_validation_warning = ""
        if extracted_details.get('receiver_account_number'):
            # Check against all payment methods since we don't know which one user used
            for method in ['BML', 'MIB']:
                stored_account_number = api.get_payment_account_details(method)
                if stored_account_number:
                    extracted_account = extracted_details['receiver_account_number'].replace(' ', '').replace('-', '').strip()
                    stored_account = stored_account_number.replace(' ', '').replace('-', '').strip()

                    # Check if account numbers match (exact match required)
                    if extracted_account != stored_account:
                        account_validation_warning = f"\n\n⚠️ <b>ACCOUNT NUMBER MISMATCH WARNING</b>\n" \
                                                    f"Slip receiver account: {extracted_details['receiver_account_number']}\n" \
                                                    f"Check against: {stored_account_number} ({method})"
                    else:
                        # Found a match, clear warning
                        account_validation_warning = ""
                        break

        # Combine warnings
        validation_warnings = name_validation_warning + account_validation_warning

    # Save extracted sender name and payment method to seat request
    if extracted_details:
        sender_name = extracted_details.get('sender_name', '')
        payment_method = extracted_details.get('bank', '')
        if sender_name:
            try:
                api.update_seat_request_slip_details(request_id, sender_name, payment_method)
                logger.info(f"Updated seat request {request_id} with sender name: {sender_name}")
            except Exception as e:
                logger.error(f"Failed to update seat request slip details: {e}")

    # Send slip details to admin for verification
    username_display = f"@{user.username}" if user.username else "No username"

    admin_message = f"""💳 <b>SEAT PAYMENT SLIP RECEIVED</b>

<b>Request ID:</b> {request_id}
<b>User:</b> {user.first_name} {user.last_name or ''}
<b>Username:</b> {username_display}
<b>User ID:</b> <code>{user.id}</code>
<b>PPPoker ID:</b> <code>{seat_data['pppoker_id']}</code>
<b>Amount:</b> <b>{seat_data['amount']} chips/MVR</b>

<b>📄 Slip Details:</b>
{ocr_details}{validation_warnings}
"""

    # Create verification buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Verify & Settle", callback_data=f"settle_seat_{request_id}"),
            InlineKeyboardButton("❌ Reject Slip", callback_data=f"reject_slip_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send to all admins
    all_admin_ids = [ADMIN_USER_ID]
    try:
        regular_admins_response = api.get_all_admins()

        # Handle paginated response from Django API
        if isinstance(regular_admins_response, dict) and 'results' in regular_admins_response:
            regular_admins = regular_admins_response['results']
        else:
            regular_admins = regular_admins_response

        logger.info(f"Found {len(regular_admins)} regular admins in database")

        # Add admins from database, but skip if already in list (avoid duplicate super admin)
        for admin in regular_admins:
            admin_telegram_id = admin['telegram_id']
            if admin_telegram_id not in all_admin_ids:
                all_admin_ids.append(admin_telegram_id)

        logger.info(f"Total admin IDs to notify: {all_admin_ids}")
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Store for button removal
    notification_messages[f"slip_{request_id}"] = []

    for admin_id in all_admin_ids:
        try:
            # Send slip image with caption
            msg = await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=admin_message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            # Store message ID for later button removal
            notification_messages[f"slip_{request_id}"].append((admin_id, msg.message_id))
        except Exception as e:
            logger.error(f"Failed to send slip to admin {admin_id}: {e}")

    # Send final confirmation if processing message still exists
    try:
        await processing_msg.edit_text(
            "✅ **Slip uploaded successfully!**\n\n"
            "Your payment is being verified by the admin. You'll be notified soon.",
            parse_mode='Markdown'
        )
    except:
        # If processing message was already edited, send new message
        await update.message.reply_text(
            "✅ **Slip uploaded successfully!**\n\n"
            "Your payment is being verified by the admin. You'll be notified soon.",
            parse_mode='Markdown'
        )


async def settle_seat_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin verifies and settles seat slip"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    # Extract request_id from callback data and convert to int
    request_id = int(query.data.replace('settle_seat_', ''))
    await query.answer()

    # Get seat request
    seat_req = api.get_seat_request(request_id)
    if not seat_req:
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ _Request not found._",
            parse_mode='HTML'
        )
        return

    # Check if request is still approved (not already settled or rejected)
    if seat_req['status'] != 'Approved':
        await query.answer(f"❌ This slip has already been {seat_req['status'].lower()}", show_alert=True)
        return

    # Extract user telegram ID and username
    user_telegram_id = seat_req.get('user_details', {}).get('telegram_id')
    username = seat_req.get('user_details', {}).get('username', 'User')
    if not user_telegram_id:
        user_telegram_id = seat_req.get('user_id')  # fallback

    # Settle in database (mark as completed and create deposit)
    success = api.settle_seat_request(request_id, query.from_user.id)

    if success:
        # Clear user credit
        api.clear_user_credit(user_telegram_id)

        # Clean up tracking
        if user_telegram_id in seat_request_data:
            del seat_request_data[user_telegram_id]
        if user_telegram_id in seat_reminder_jobs:
            try:
                seat_reminder_jobs[user_telegram_id].schedule_removal()
                del seat_reminder_jobs[user_telegram_id]
            except:
                pass

        # Update message caption for ALL admins - remove buttons and show who settled
        if f"slip_{request_id}" in notification_messages:
            for admin_id, message_id in notification_messages[f"slip_{request_id}"]:
                try:
                    # Get the original message to preserve caption
                    await context.bot.edit_message_caption(
                        chat_id=admin_id,
                        message_id=message_id,
                        caption=f"📸 **Payment Slip Verification**\n\n"
                                f"**Request ID:** `{request_id}`\n"
                                f"**User:** @{username} (ID: {user_telegram_id})\n"
                                f"**PPPoker ID:** {seat_req['pppoker_id']}\n"
                                f"**Amount:** {seat_req['amount']} chips/MVR\n\n"
                                f"✅ <b>SETTLED by {query.from_user.first_name}</b>",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to update message for admin {admin_id}: {e}")
            del notification_messages[f"slip_{request_id}"]

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_telegram_id,
                text=f"✅ **Payment Verified!**\n\n"
                     f"**Request ID:** `{request_id}`\n"
                     f"**Amount:** {seat_req['amount']} chips/MVR\n\n"
                     f"Your seat request has been settled. Thank you!",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
    else:
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ _Failed to settle._",
            parse_mode='HTML'
        )


async def reject_seat_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects seat slip"""
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Not authorized", show_alert=True)
        return

    # Extract request_id from callback data and convert to int
    request_id = int(query.data.replace('reject_slip_', ''))
    await query.answer()

    # Get seat request
    seat_req = api.get_seat_request(request_id)
    if not seat_req:
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ _Request not found._",
            parse_mode='HTML'
        )
        return

    # Check if request is still approved (not already settled or rejected)
    if seat_req['status'] != 'Approved':
        await query.answer(f"❌ This slip has already been {seat_req['status'].lower()}", show_alert=True)
        return

    # Extract user info
    user_telegram_id = seat_req.get('user_details', {}).get('telegram_id')
    username = seat_req.get('user_details', {}).get('username', 'User')
    if not user_telegram_id:
        user_telegram_id = seat_req.get('user_id')  # fallback

    # Update message caption for ALL admins - remove buttons and show who rejected
    if f"slip_{request_id}" in notification_messages:
        for admin_id, message_id in notification_messages[f"slip_{request_id}"]:
            try:
                await context.bot.edit_message_caption(
                    chat_id=admin_id,
                    message_id=message_id,
                    caption=f"📸 Payment Slip Verification\n\n"
                            f"Request ID: {request_id}\n"
                            f"User: @{username} (ID: {user_telegram_id})\n"
                            f"PPPoker ID: {seat_req['pppoker_id']}\n"
                            f"Amount: {seat_req['amount']} chips / MVR\n\n"
                            f"❌ <b>REJECTED by {query.from_user.first_name}</b>\n"
                            f"This payment slip could not be verified. The user has been notified.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                logger.error(f"Failed to update message for admin {admin_id}: {e}")
        del notification_messages[f"slip_{request_id}"]

    # Notify user to reupload or contact support
    try:
        await context.bot.send_message(
            chat_id=user_telegram_id,
            text=f"**Request ID:** `{request_id}`\n\n"
                 f"We were unable to verify your payment slip.\n\n"
                 f"Please contact Live Support for assistance.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")


# Spin Management Panel for Admins
async def spin_management_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show spin management panel for admins"""
    keyboard = [
        [InlineKeyboardButton("📋 Pending Rewards", callback_data="spin_admin_pending")],
        [InlineKeyboardButton("📊 Spin Statistics", callback_data="spin_admin_stats")],
        [InlineKeyboardButton("➕ Add Spins to User", callback_data="spin_admin_add")],
        [InlineKeyboardButton("🎲 My Free Spins", callback_data="spin_admin_play")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━\n"
        "🎰 *SPIN MANAGEMENT* 🎰\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Select an option:\n\n"
        "📋 *Pending Rewards* \\- View and approve pending rewards\n"
        "📊 *Spin Statistics* \\- View global spin stats\n"
        "➕ *Add Spins to User* \\- Manually give spins\n"
        "🎲 *My Free Spins* \\- Play your own spins",
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )


# Spin admin callback handlers
async def spin_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle spin management callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin access required!")
        return

    data = query.data

    # Handle add spins amount selection
    if data.startswith("spin_admin_add_amount_"):
        amount = data.replace("spin_admin_add_amount_", "")
        # Store the amount in user context
        context.user_data['pending_spin_amount'] = amount

        await query.edit_message_text(
            f"➕ *ADD {amount} SPINS*\n\n"
            f"Please reply with the user's Telegram ID\n\n"
            f"Example: `123456789`\n\n"
            f"Or use command directly:\n"
            f"`/addspins <user_id> {amount}`",
            parse_mode='MarkdownV2'
        )
        # Set flag that admin is in "add spins mode"
        context.user_data['awaiting_user_id_for_spins'] = True
        return

    if data == "spin_admin_pending":
        await pendingspins_command(update, context)
    elif data == "spin_admin_stats":
        await spinsstats_command(update, context)
    elif data == "spin_admin_add":
        # Show common spin amounts as buttons
        keyboard = [
            [
                InlineKeyboardButton("➕ 10 Spins", callback_data="spin_admin_add_amount_10"),
                InlineKeyboardButton("➕ 25 Spins", callback_data="spin_admin_add_amount_25")
            ],
            [
                InlineKeyboardButton("➕ 50 Spins", callback_data="spin_admin_add_amount_50"),
                InlineKeyboardButton("➕ 100 Spins", callback_data="spin_admin_add_amount_100")
            ],
            [
                InlineKeyboardButton("➕ 250 Spins", callback_data="spin_admin_add_amount_250")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "➕ *ADD SPINS TO USER*\n\n"
            "Select amount, then I'll ask for user ID:\n\n"
            "Or use command:\n"
            "`/addspins <user_id> <amount>`",
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
    elif data == "spin_admin_play":
        # Replace message with freespins interface
        try:
            await query.delete_message()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        # Send freespins using the chat directly
        user = query.from_user

        try:
            # Get user's spin data
            user_data = spin_bot.api.get_spin_user(user.id)

            if not user_data or user_data.get('available_spins', 0) == 0:
                # Create deposit button
                keyboard = [[InlineKeyboardButton("💰 Make Deposit", callback_data="deposit_start")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="━━━━━━━━━━━━━━━━━━\n"
                        "🎰 *FREE SPINS* 🎰\n"
                        "━━━━━━━━━━━━━━━━━━\n\n"
                        "💫 *No spins available right now\\!*\n\n"
                        "💰 Make a deposit to unlock free spins\\!\n"
                        "🔥 More deposit → More spins → More prizes\\!\n\n"
                        "🎁 *Win Amazing Prizes:*\n"
                        "🏆 500 Chips\n"
                        "💰 250 Chips\n"
                        "💎 100 Chips\n"
                        "💵 50 Chips\n"
                        "🪙 20 Chips\n"
                        "🎯 10 Chips\n"
                        "📱 iPhone 17 Pro Max\n"
                        "💻 MacBook Pro\n"
                        "⌚ Apple Watch Ultra\n"
                        "🎧 AirPods Pro\n"
                        "✨ Plus Surprise Rewards\\!\n\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "👉 Click button below to get started\\!\n"
                        "━━━━━━━━━━━━━━━━━━",
                    parse_mode='MarkdownV2',
                    reply_markup=reply_markup
                )
                return

            available = user_data.get('available_spins', 0)
            total_used = user_data.get('total_spins_used', 0)
            total_chips = user_data.get('total_chips_earned', 0)

            # Create spin options keyboard
            keyboard = []

            # Single spin
            keyboard.append([InlineKeyboardButton("🎯 Spin 1x", callback_data="spin_1")])

            # Multi-spin options
            if available >= 10:
                keyboard.append([InlineKeyboardButton("🎰 Spin 10x", callback_data="spin_10")])

            if available >= 50:
                keyboard.append([InlineKeyboardButton("🔥 Spin 50x", callback_data="spin_50")])

            if available >= 100:
                keyboard.append([InlineKeyboardButton("💥 Spin 100x", callback_data="spin_100")])

            if available > 1:
                keyboard.append([InlineKeyboardButton(f"⚡ Spin ALL ({available}x)", callback_data=f"spin_all")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            # Escape username for MarkdownV2
            username_escaped = user.first_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎰 *FREE SPINS* 🎰\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 *{username_escaped}*\n\n"
                    f"🎯 Available Spins: *{available}*\n"
                    f"💎 Total Chips: *{total_chips}*\n\n"
                    f"🎁 *Prize Wheel:*\n"
                    f"🏆 500 Chips\n"
                    f"💰 250 Chips\n"
                    f"💎 100 Chips\n"
                    f"💵 50 Chips\n"
                    f"🪙 20 Chips\n"
                    f"🎯 10 Chips\n"
                    f"📱 iPhone 17 Pro Max\n"
                    f"💻 MacBook Pro\n"
                    f"⌚ Apple Watch Ultra\n"
                    f"🎧 AirPods Pro\n"
                    f"✨ Plus Surprise Rewards\\!\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ *Choose Your Spins:* ⚡\n"
                    f"━━━━━━━━━━━━━━━━━━",
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Error in spin_admin_play: {e}")
            import traceback
            traceback.print_exc()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Error loading spin data. Please try again."
            )


# Approve spin callback handler
async def approve_spin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve spin button clicks - approves ALL pending rewards for a user"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if not is_admin(user.id):
        await query.edit_message_text("❌ Admin access required!")
        return

    # Extract data from callback_data
    # Format: approve_user_<user_id>_<spin_id1>,<spin_id2>,<spin_id3>
    data_parts = query.data.replace("approve_user_", "").split("_", 1)
    target_user_id = int(data_parts[0])
    spin_ids = data_parts[1].split(",") if len(data_parts) > 1 else []

    # Approve all spin IDs for this user
    approved_count = 0
    total_chips = 0
    approver_name = user.username or user.first_name
    target_username = "Unknown"
    approved_rewards = []  # Store details of approved rewards

    for spin_id in spin_ids:
        try:
            # Get spin data before approval
            spin_data = spin_bot.api.get_spin_by_id(spin_id)

            if not spin_data:
                logger.warning(f"Spin ID {spin_id} not found")
                continue

            if spin_data.get('approved'):
                logger.info(f"Spin ID {spin_id} already approved, skipping")
                continue

            # Store username for later
            target_username = spin_data.get('username', 'Unknown')

            # Mark as approved
            spin_bot.api.approve_spin_reward(spin_id, user.id, approver_name)

            # Add to totals
            chips = int(spin_data.get('chips', 0))
            total_chips += chips
            approved_count += 1

            # Store reward details
            approved_rewards.append({
                'prize': spin_data['prize'],
                'chips': chips
            })

            # Update user's total approved chips
            user_data = spin_bot.api.get_spin_user(spin_data['user_id'])
            if user_data:
                current_chips = user_data.get('total_chips_earned', 0)
                new_total = current_chips + chips
                spin_bot.api.update_spin_user(
                    user_id=spin_data['user_id'],
                    username=target_username,
                    total_chips_earned=new_total
                )

        except Exception as e:
            logger.error(f"Error approving spin {spin_id}: {e}")
            import traceback
            traceback.print_exc()

    # Send ONE consolidated notification to user with all approved rewards
    if approved_count > 0 and target_user_id:
        try:
            # Build reward list
            rewards_text = ""
            for idx, reward in enumerate(approved_rewards, 1):
                # Escape prize name for MarkdownV2
                prize_escaped = reward['prize'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
                rewards_text += f"{idx}\\. {prize_escaped} \\- *{reward['chips']} chips*\n"

            user_message = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ *REWARDS APPROVED* ✅\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🎊 Congratulations\\!\n\n"
                f"🎁 *Your Rewards:*\n"
                f"{rewards_text}\n"
                f"💰 *TOTAL: {total_chips} chips*\n\n"
                f"✨ *Added to your balance\\!* ✨\n"
                f"Your chips have been credited to your PPPoker account\\!\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Thank you for playing\\! 🎰"
            )

            await context.bot.send_message(
                chat_id=target_user_id,
                text=user_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Successfully sent consolidated notification to user {target_user_id} for {approved_count} rewards")
        except Exception as e:
            logger.error(f"Error sending consolidated notification to user: {e}")
            import traceback
            traceback.print_exc()
            # Try sending without markdown as fallback
            try:
                rewards_simple = ""
                for idx, reward in enumerate(approved_rewards, 1):
                    rewards_simple += f"{idx}. {reward['prize']} - {reward['chips']} chips\n"

                simple_message = (
                    f"✅ REWARDS APPROVED ✅\n\n"
                    f"🎊 Congratulations!\n\n"
                    f"🎁 Your Rewards:\n"
                    f"{rewards_simple}\n"
                    f"💰 TOTAL: {total_chips} chips\n\n"
                    f"Your chips have been credited to your PPPoker account!\n\n"
                    f"Thank you for playing! 🎰"
                )
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=simple_message
                )
                logger.info(f"Sent simple consolidated notification to user {target_user_id} (fallback)")
            except Exception as e2:
                logger.error(f"Failed to send fallback notification: {e2}")

    # Remove approve buttons from ALL admin notification messages for this user
    notification_key = f"spin_reward_{target_user_id}"
    if hasattr(context.bot_data, 'spin_notification_messages') and notification_key in context.bot_data.get('spin_notification_messages', {}):
        logger.info(f"Removing approve buttons from {len(context.bot_data['spin_notification_messages'][notification_key])} admin messages")
        for admin_id, message_id in context.bot_data['spin_notification_messages'][notification_key]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
                logger.info(f"Removed approve button for admin {admin_id}, message {message_id}")
            except Exception as e:
                logger.error(f"Failed to remove button for admin {admin_id}: {e}")
        # Clean up stored message IDs
        del context.bot_data['spin_notification_messages'][notification_key]
        logger.info(f"Cleaned up notification storage for {notification_key}")

    # Notify ALL other admins about the batch approval
    if approved_count > 0:
        admin_notification = (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>REWARDS APPROVED</b> ✅\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User:</b> {target_username}\n"
            f"🎁 <b>Rewards:</b> {approved_count}\n"
            f"💎 <b>Total Chips:</b> {total_chips}\n\n"
            f"✅ <b>Approved by:</b> {approver_name}\n\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        try:
            # Send to super admin (if not the one who approved)
            if user.id != ADMIN_USER_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_USER_ID,
                        text=admin_notification,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify super admin: {e}")

            # Send to all other admins
            admins_response = spin_bot.api.get_all_admins()
            logger.info(f"📋 Got admin list response type: {type(admins_response)}")

            # Handle paginated response from Django API
            if isinstance(admins_response, dict) and 'results' in admins_response:
                admins = admins_response['results']
            else:
                admins = admins_response

            logger.info(f"📋 Found {len(admins)} admins to notify about approval")
            logger.info(f"📋 Approver ID: {user.id}, will skip this admin")

            for admin in admins:
                # Don't notify the admin who approved it
                logger.info(f"📋 Checking admin: {admin.get('telegram_id')} (name: {admin.get('name', 'N/A')})")
                if admin['telegram_id'] != user.id:
                    try:
                        logger.info(f"✅ Sending approval notification to admin {admin['telegram_id']}")
                        await context.bot.send_message(
                            chat_id=admin['telegram_id'],
                            text=admin_notification,
                            parse_mode='HTML'
                        )
                        logger.info(f"✅ Successfully sent approval notification to admin {admin['telegram_id']}")
                    except Exception as e:
                        logger.error(f"❌ Failed to notify admin {admin['telegram_id']}: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                else:
                    logger.info(f"⏭️ Skipping admin {admin['telegram_id']} (is the approver)")
        except Exception as e:
            logger.error(f"❌ Error notifying other admins: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # Edit the original message to show it was processed
    try:
        if approved_count > 0:
            await query.edit_message_text(
                f"✅ *APPROVED ALL REWARDS*\n\n"
                f"✅ Approved: {approved_count} rewards\n"
                f"💰 Total Chips: {total_chips}\n"
                f"👤 User: {target_username}\n\n"
                f"User has been notified\\!\n"
                f"💰 Manually add {total_chips} chips to PPPoker ID\\.",
                parse_mode='MarkdownV2'
            )
        else:
            await query.edit_message_text(
                f"⚠️ No rewards to approve\\.\n"
                f"All rewards may already be approved\\.",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        pass


# Deposit button callback handler (from no spins message)
async def approve_spinhistory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle NEW spin history approval - approves ALL pending rewards for a user"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if not is_admin(user.id):
        await query.edit_message_text("❌ Admin access required!")
        return

    try:
        # Extract user_id from callback_data
        # Format: approve_spinhistory_<user_id>
        target_user_id = int(query.data.replace("approve_spinhistory_", ""))

        # Get all pending spins for this user
        pending = spin_bot.api.get_pending_spin_rewards()

        # Handle paginated response
        if isinstance(pending, dict) and 'results' in pending:
            pending = pending['results']

        # Filter by telegram_id (from user_details, not user_id)
        user_pending = [p for p in pending if str(p.get('user_details', {}).get('telegram_id')) == str(target_user_id)]

        logger.info(f"🔍 [APPROVE CALLBACK] Found {len(user_pending)} pending spins for user {target_user_id}")

        if not user_pending:
            await query.edit_message_text(
                f"✅ All rewards already approved!\n\n"
                f"No pending spins found for this user.",
                parse_mode='Markdown'
            )
            return

        approver_name = user.username or user.first_name
        approved_count = 0
        total_chips = 0
        # Get username from user_details
        username = user_pending[0].get('user_details', {}).get('username', 'Unknown')

        # Get user data first
        user_data = spin_bot.api.get_spin_user(target_user_id)

        # Approve each pending spin
        for reward in user_pending:
            spin_id = reward.get('id')  # Use 'id' field from Django API, not 'row_number'
            chips = reward.get('chips', 0)

            # Skip if spin_id is None
            if not spin_id:
                logger.warning(f"Skipping reward with no id: {reward}")
                continue

            success = spin_bot.api.approve_spin_reward(spin_id, user.id)  # Pass admin user ID, not name
            if success:
                approved_count += 1
                total_chips += chips

        # Update user's total chips earned
        if user_data:
            current_chips = user_data.get('total_chips_earned', 0)
            new_total = current_chips + total_chips
            spin_bot.api.update_spin_user(
                telegram_id=target_user_id,
                total_chips_earned=new_total
            )

        # Escape HTML characters to prevent parsing errors
        from html import escape
        username_safe = escape(str(username))
        approver_name_safe = escape(str(approver_name))

        # Edit the message to show approval success
        await query.edit_message_text(
            f"✅ <b>APPROVED!</b> ✅\n\n"
            f"👤 User: {username_safe}\n"
            f"📦 Approved: {approved_count} rewards\n"
            f"💰 Total: {total_chips} chips\n\n"
            f"✨ User has been notified!\n"
            f"👤 Approved by: {approver_name_safe}",
            parse_mode='HTML'
        )

        # Remove approve buttons from ALL admin messages for this user
        # Need to remove from BOTH /pendingspins messages AND instant notification messages
        # Retrieve message IDs from Django database (persists across bot restarts)

        # Get /pendingspins messages
        pendingspins_key = f"pendingspins_{target_user_id}"
        try:
            pendingspins_messages = api.get_notification_messages(pendingspins_key)
            logger.info(f"🗑️ Retrieved {len(pendingspins_messages)} stored /pendingspins messages from database")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve /pendingspins messages from database: {e}")
            pendingspins_messages = []

        # Get instant notification messages
        instant_key = f"spin_reward_{target_user_id}"
        try:
            instant_messages = api.get_notification_messages(instant_key)
            logger.info(f"🗑️ Retrieved {len(instant_messages)} stored instant notification messages from database")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve instant messages from database: {e}")
            instant_messages = []

        # Combine all messages
        stored_messages = pendingspins_messages + instant_messages
        logger.info(f"🗑️ Total messages to process: {len(stored_messages)}")

        if stored_messages:
            logger.info(f"🗑️ Removing approve buttons from {len(stored_messages)} stored /pendingspins messages")

            # Track which admins we've already sent the approval notification to (avoid duplicates)
            notified_admins = set()

            for msg_record in stored_messages:
                admin_id = msg_record['admin_telegram_id']
                message_id = msg_record['message_id']
                try:
                    # If this is the approver's message, skip (already edited above)
                    if admin_id == user.id and message_id == query.message.message_id:
                        logger.info(f"✅ Approver's message already edited: admin {admin_id}, message {message_id}")
                    else:
                        # Remove button from this notification
                        try:
                            await context.bot.edit_message_reply_markup(
                                chat_id=admin_id,
                                message_id=message_id,
                                reply_markup=InlineKeyboardMarkup([])
                            )
                            logger.info(f"🔘 Removed button from admin {admin_id}, message {message_id}")
                        except Exception as e:
                            logger.error(f"❌ Failed to remove button: {e}")

                        # Send approval notification ONCE per admin (not per message)
                        if admin_id not in notified_admins:
                            try:
                                await context.bot.send_message(
                                    chat_id=admin_id,
                                    text=f"✅ <b>Spin Rewards APPROVED</b>\n\n"
                                         f"👤 User: {username_safe}\n"
                                         f"💰 Total: {total_chips} chips\n"
                                         f"📦 Rewards: {approved_count}\n\n"
                                         f"👤 Approved by: {approver_name_safe}\n"
                                         f"✨ User notified and chips credited.",
                                    parse_mode='HTML'
                                )
                                notified_admins.add(admin_id)
                                logger.info(f"📬 Sent approval notification to admin {admin_id}")
                            except Exception as e:
                                logger.error(f"❌ Failed to send notification to admin {admin_id}: {e}")
                except Exception as e:
                    logger.error(f"❌ Failed to process message for admin {admin_id}, message {message_id}: {e}")

            # Clean up stored message IDs from Django database (both types)
            try:
                deleted_pendingspins = api.delete_notification_messages(pendingspins_key)
                deleted_instant = api.delete_notification_messages(instant_key)
                logger.info(f"✅ Deleted {deleted_pendingspins} /pendingspins + {deleted_instant} instant notification messages from database")
            except Exception as e:
                logger.error(f"❌ Failed to delete notification messages from database: {e}")
        else:
            # No stored messages found
            logger.warning(f"⚠️ No stored message IDs found in database for user {target_user_id}")

        # Notify the user with detailed message
        try:
            # Get PPPoker ID for the message
            pppoker_id = spin_bot.api.get_pppoker_id_from_deposits(target_user_id)
            if pppoker_id:
                pppoker_msg = f"🎮 <b>PPPoker ID:</b> {pppoker_id}\n"
            else:
                pppoker_msg = ""

            notification_text = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>REWARDS APPROVED!</b> ✅\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🎊 <b>Congratulations!</b>\n\n"
                f"💰 <b>Total Chips:</b> {total_chips}\n"
                f"📦 <b>Rewards:</b> {approved_count}\n"
            )

            if pppoker_msg:
                notification_text += pppoker_msg

            notification_text += (
                f"\n✨ <b>Your chips have been added to your account!</b>\n\n"
                f"🎮 The chips are now available in your PPPoker account.\n"
                f"💎 You can use them to play poker right away!\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Thank you for playing! 🎰\n"
                f"Good luck at the tables! 🃏"
            )

            await context.bot.send_message(
                chat_id=target_user_id,
                text=notification_text,
                parse_mode='HTML'
            )
            logger.info(f"✅ User {target_user_id} notified of approval from pending rewards: {total_chips} chips")
        except Exception as e:
            logger.error(f"❌ Failed to notify user {target_user_id}: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        logger.error(f"Error in approve_spinhistory_callback: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(f"❌ Error approving rewards: {str(e)}")


async def approve_instant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle instant approve button from win notification - approves ALL pending rewards for a user"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if not is_admin(user.id):
        await query.answer("❌ Admin access required!", show_alert=True)
        return

    try:
        # Extract user_id from callback_data
        # Format: approve_instant_<user_id>
        target_user_id = int(query.data.replace("approve_instant_", ""))

        # Get all pending spins for this user
        pending = spin_bot.api.get_pending_spin_rewards()

        # Handle paginated response
        if isinstance(pending, dict) and 'results' in pending:
            pending = pending['results']

        # Filter by telegram_id (from user_details, not user_id)
        user_pending = [p for p in pending if str(p.get('user_details', {}).get('telegram_id')) == str(target_user_id)]

        logger.info(f"🔍 Found {len(user_pending)} pending spins for user {target_user_id}")

        if not user_pending:
            # Try to find who already approved by checking spin history via Django API
            try:
                # Query Django API for approved spins for this user
                response = api.get_all_spin_history()

                # Handle paginated response
                if isinstance(response, dict) and 'results' in response:
                    all_spins = response['results']
                else:
                    all_spins = response if isinstance(response, list) else []

                # Filter for approved spins from this user
                user_spins = [
                    s for s in all_spins
                    if s.get('user_details', {}).get('telegram_id') == target_user_id
                    and s.get('status') == 'Approved'
                ]

                if user_spins:
                    # Get LAST (most recent) approved spin details
                    last_spin = user_spins[-1]
                    approved_by = last_spin.get('approved_by', 'Unknown Admin')
                    total_chips = sum(s.get('chips_won', 0) for s in user_spins)
                    username = last_spin.get('user_details', {}).get('username', 'User')

                    # Escape HTML characters to prevent parsing errors
                    from html import escape
                    username_safe = escape(str(username))
                    approved_by_safe = escape(str(approved_by))

                    await query.edit_message_text(
                        f"✅ <b>Already Approved!</b> ✅\n\n"
                        f"👤 User: {username_safe}\n"
                        f"💰 Total: {total_chips} chips\n"
                        f"📦 Approved Spins: {len(user_spins)}\n\n"
                        f"✨ <b>Approved by:</b> {approved_by_safe}",
                        parse_mode='HTML',
                        reply_markup=None  # Remove button
                    )
                else:
                    await query.edit_message_text(
                        f"✅ All rewards already approved!\n\n"
                        f"No pending spins found for this user.",
                        parse_mode='Markdown',
                        reply_markup=None  # Remove button
                    )
            except Exception as e:
                logger.error(f"Error checking approval status: {e}")
                import traceback
                traceback.print_exc()
                await query.edit_message_text(
                    f"✅ All rewards already approved!\n\n"
                    f"No pending spins found for this user.",
                    parse_mode='Markdown',
                    reply_markup=None  # Remove button
                )
            return

        approver_name = user.username or user.first_name
        approved_count = 0
        total_chips = 0
        # Get username from user_details nested object (not directly from spin record)
        username = user_pending[0].get('user_details', {}).get('username', 'Unknown')

        # Get user data first
        user_data = spin_bot.api.get_spin_user(target_user_id)

        # Approve each pending spin
        for reward in user_pending:
            spin_id = reward.get('id')  # Use 'id' field from Django API, not 'row_number'
            chips = reward.get('chips', 0)

            # Skip if spin_id is None
            if not spin_id:
                logger.warning(f"Skipping reward with no id: {reward}")
                continue

            success = spin_bot.api.approve_spin_reward(spin_id, user.id)  # Pass admin user ID, not name
            if success:
                approved_count += 1
                total_chips += chips

        # Update user's total chips earned
        if user_data:
            current_chips = user_data.get('total_chips_earned', 0)
            new_total = current_chips + total_chips
            spin_bot.api.update_spin_user(
                telegram_id=target_user_id,
                total_chips_earned=new_total
            )

        # Escape HTML characters in names to prevent parsing errors
        from html import escape
        username_safe = escape(str(username))
        approver_name_safe = escape(str(approver_name))

        # Edit the notification message to show approval
        await query.edit_message_text(
            f"✅ <b>APPROVED!</b> ✅\n\n"
            f"👤 User: {username_safe}\n"
            f"💰 Total: {total_chips} chips\n"
            f"📦 Rewards: {approved_count}\n\n"
            f"✨ User has been notified!\n"
            f"👤 Approved by: {approver_name_safe}",
            parse_mode='HTML'
        )

        # Remove approve buttons from ALL admin notification messages for this user
        # Retrieve message IDs from Django database (persists across bot restarts)
        notification_key = f"spin_reward_{target_user_id}"

        # Get stored message IDs from Django database
        try:
            stored_messages = api.get_notification_messages(notification_key)
            logger.info(f"🗑️ Retrieved {len(stored_messages)} stored messages from database for {notification_key}")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve stored messages from database: {e}")
            stored_messages = []

        if stored_messages:
            logger.info(f"🗑️ Removing approve buttons from {len(stored_messages)} stored admin messages")

            # Track which admins we've already sent the approval notification to (avoid duplicates)
            notified_admins = set()

            for msg_record in stored_messages:
                admin_id = msg_record['admin_telegram_id']
                message_id = msg_record['message_id']
                try:
                    # If this is the approver's message, skip (already edited above)
                    if admin_id == user.id and message_id == query.message.message_id:
                        logger.info(f"✅ Approver's message already edited: admin {admin_id}, message {message_id}")
                    else:
                        # Remove button from this notification
                        try:
                            await context.bot.edit_message_reply_markup(
                                chat_id=admin_id,
                                message_id=message_id,
                                reply_markup=InlineKeyboardMarkup([])
                            )
                            logger.info(f"🔘 Removed button from admin {admin_id}, message {message_id}")
                        except Exception as e:
                            logger.error(f"❌ Failed to remove button: {e}")

                        # Send approval notification ONCE per admin (not per message)
                        if admin_id not in notified_admins:
                            try:
                                await context.bot.send_message(
                                    chat_id=admin_id,
                                    text=f"✅ <b>Spin Rewards APPROVED</b>\n\n"
                                         f"👤 User: {username_safe}\n"
                                         f"💰 Total: {total_chips} chips\n"
                                         f"📦 Rewards: {approved_count}\n\n"
                                         f"👤 Approved by: {approver_name_safe}\n"
                                         f"✨ User notified and chips credited.",
                                    parse_mode='HTML'
                                )
                                notified_admins.add(admin_id)
                                logger.info(f"📬 Sent approval notification to admin {admin_id}")
                            except Exception as e:
                                logger.error(f"❌ Failed to send notification to admin {admin_id}: {e}")
                except Exception as e:
                    logger.error(f"❌ Failed to process message for admin {admin_id}, message {message_id}: {e}")

            # Clean up stored message IDs from Django database
            try:
                deleted_count = api.delete_notification_messages(notification_key)
                logger.info(f"✅ Deleted {deleted_count} notification messages from database for {notification_key}")
            except Exception as e:
                logger.error(f"❌ Failed to delete notification messages from database: {e}")
        else:
            # No stored messages found
            logger.warning(f"⚠️ No stored message IDs found in database for {notification_key}")
            logger.warning(f"⚠️ Other admins will see 'Already Approved' when clicking their buttons.")

        # Notify the user
        try:
            pppoker_id = spin_bot.api.get_pppoker_id_from_deposits(target_user_id)
            if pppoker_id:
                pppoker_msg = f"🎮 <b>PPPoker ID:</b> {pppoker_id}\n"
            else:
                pppoker_msg = ""

            notification_text = (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ <b>REWARDS APPROVED!</b> ✅\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🎊 <b>Congratulations!</b>\n\n"
                f"💰 <b>Total Chips:</b> {total_chips}\n"
                f"📦 <b>Rewards:</b> {approved_count}\n"
            )

            if pppoker_msg:
                notification_text += pppoker_msg

            notification_text += (
                f"\n✨ <b>Your chips have been added to your account!</b>\n\n"
                f"🎮 The chips are now available in your PPPoker account.\n"
                f"💎 You can use them to play poker right away!\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Thank you for playing! 🎰\n"
                f"Good luck at the tables! 🃏"
            )

            await context.bot.send_message(
                chat_id=target_user_id,
                text=notification_text,
                parse_mode='HTML'
            )
            logger.info(f"✅ User {target_user_id} notified of instant approval: {total_chips} chips")
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        logger.error(f"Error in approve_instant_callback: {e}")
        import traceback
        traceback.print_exc()
        try:
            await query.edit_message_text(
                f"❌ Error approving rewards: {str(e)}",
                parse_mode=None  # No parse mode to avoid HTML errors
            )
        except:
            # If editing fails, just answer the query
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)


# ========== CASHBACK APPROVAL HANDLERS ==========

async def cashback_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cashback approval"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    approver_id = user.id
    approver_name = user.username or user.first_name

    try:
        # Extract request_id from callback data
        request_id = int(query.data.replace("cashback_approve_", ""))

        # Approve the cashback request
        result = api.approve_cashback_request(request_id, approver_id)

        if not result:
            await query.edit_message_text(
                "❌ <b>Error</b>\n\nFailed to approve cashback request.",
                parse_mode='HTML'
            )
            return

        # Extract details from result
        username = result['user_details']['username']
        target_user_id = result['user_details']['telegram_id']
        cashback_amount = float(result['cashback_amount'])
        pppoker_id = result['pppoker_id']

        # Edit the notification message
        await query.edit_message_text(
            f"✅ <b>CASHBACK APPROVED!</b> ✅\n\n"
            f"👤 User: {username}\n"
            f"💰 Cashback Amount: <b>{cashback_amount:.2f} MVR</b>\n"
            f"🎮 PPPoker ID: <b>{pppoker_id}</b>\n\n"
            f"✨ User has been notified!\n"
            f"👤 Approved by: {approver_name}",
            parse_mode='HTML'
        )

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"✅ <b>CASHBACK APPROVED!</b> ✅\n\n"
                    f"💰 Cashback Amount: <b>{cashback_amount:.2f} MVR</b>\n"
                    f"💎 Your balance has been updated!\n\n"
                    f"Thank you for playing with us! 🎰"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")

        # Remove buttons from ALL admin notifications
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
            del notification_messages[request_id]

    except Exception as e:
        logger.error(f"Error in cashback_approve_callback: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(f"❌ Error approving cashback: {str(e)}")


async def cashback_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cashback rejection"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    rejector_id = user.id
    rejector_name = user.username or user.first_name

    try:
        # Extract request_id from callback data
        request_id = int(query.data.replace("cashback_reject_", ""))

        # Reject the cashback request
        result = api.reject_cashback_request(request_id, rejector_id, "Rejected by admin")

        if not result:
            await query.edit_message_text(
                "❌ <b>Error</b>\n\nFailed to reject cashback request.",
                parse_mode='HTML'
            )
            return

        # Extract details from result
        username = result['user_details']['username']
        target_user_id = result['user_details']['telegram_id']
        cashback_amount = float(result['cashback_amount'])

        # Edit the notification message
        await query.edit_message_text(
            f"❌ <b>CASHBACK REJECTED</b> ❌\n\n"
            f"👤 User: {username}\n"
            f"💰 Rejected Amount: <b>{cashback_amount:.2f} MVR</b>\n\n"
            f"👤 Rejected by: {rejector_name}",
            parse_mode='HTML'
        )

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"❌ <b>CASHBACK REJECTED</b> ❌\n\n"
                    f"💰 Rejected Amount: <b>{cashback_amount:.2f} MVR</b>\n\n"
                    f"Your cashback request has been rejected.\n"
                    f"Please contact support if you have any questions.\n\n"
                    f"💬 Use /support to reach us!"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")

        # Remove buttons from ALL admin notifications
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
            del notification_messages[request_id]

    except Exception as e:
        logger.error(f"Error in cashback_reject_callback: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(f"❌ Error rejecting cashback: {str(e)}")


async def deposit_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit button click from free spins no-spins message"""
    query = update.callback_query
    await query.answer()

    # Delete the current message
    try:
        await query.delete_message()
    except:
        pass

    # Get user data
    user_data = api.get_user(update.effective_user.id)

    # Get all configured payment accounts
    payment_accounts = api.get_all_payment_accounts()

    # Build keyboard with only configured payment methods
    keyboard = []
    if 'BML' in payment_accounts and payment_accounts['BML']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 BML", callback_data="deposit_bml")])
    if 'MIB' in payment_accounts and payment_accounts['MIB']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 MIB", callback_data="deposit_mib")])
    if 'USD' in payment_accounts and payment_accounts['USD']['account_number']:
        keyboard.append([InlineKeyboardButton("💵 USD", callback_data="deposit_usd")])
    if 'USDT' in payment_accounts and payment_accounts['USDT']['account_number']:
        keyboard.append([InlineKeyboardButton("💎 USDT (BEP20)", callback_data="deposit_usdt")])

    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

    # Check if any payment methods are configured
    if len(keyboard) == 1:  # Only cancel button
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ No payment methods are currently available.\n\n"
                "Please contact admin for assistance.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="💰 **Deposit to Billionaires Club**\n\n"
            "Please select your payment method:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return DEPOSIT_METHOD


# Play freespins button callback handler
async def play_freespins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle play freespins button click - redirect to mini app"""
    try:
        query = update.callback_query
        await query.answer()

        logger.info(f"Play freespins button clicked by user {query.from_user.id}")

        # Delete the original message
        try:
            await query.delete_message()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        user = query.from_user

        try:
            # Get user's spin data
            user_data = spin_bot.api.get_spin_user(user.id)
            available = user_data.get('available_spins', 0) if user_data else 0
            total_chips = user_data.get('total_chips_earned', 0) if user_data else 0

            # Mini app URL
            mini_app_url = "https://billionaires-spins.up.railway.app"

            # Create mini app button
            keyboard = [[InlineKeyboardButton("🎰 OPEN SPIN WHEEL 🎰", web_app=WebAppInfo(url=mini_app_url))]]

            # Add deposit button if no spins
            if available == 0:
                keyboard.append([InlineKeyboardButton("💰 Make Deposit", callback_data="deposit_start")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            # Escape username for MarkdownV2
            username_escaped = user.first_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎰 *FREE SPINS WHEEL* 🎰\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 *{username_escaped}*\n\n"
                    f"🎯 Available Spins: *{available}*\n"
                    f"💎 Total Chips Earned: *{total_chips}*\n\n"
                    f"🎁 *Win Amazing Prizes:*\n"
                    f"🏆 500 Chips\n"
                    f"💰 250 Chips\n"
                    f"💎 100 Chips\n"
                    f"💵 50 Chips\n"
                    f"🪙 20 Chips\n"
                    f"🎯 10 Chips\n"
                    f"📱 iPhone 17 Pro Max\n"
                    f"💻 MacBook Pro\n"
                    f"⌚ Apple Watch Ultra\n"
                    f"🎧 AirPods Pro\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👇 Click button to spin the wheel\\!\n"
                    f"━━━━━━━━━━━━━━━━━━",
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Error loading spin data: {e}")
            import traceback
            traceback.print_exc()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Error loading spin data. Please try again."
            )

    except Exception as e:
        logger.error(f"Error in play_freespins_callback: {e}")
        import traceback
        traceback.print_exc()


# Message router
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route text messages to appropriate handlers"""
    user_id = update.effective_user.id
    text = update.message.text

    # Check if admin is in "add spins mode"
    if is_admin(user_id) and context.user_data.get('awaiting_user_id_for_spins'):
        # Admin sent a user ID
        target_user_id = text.strip()
        amount = context.user_data.get('pending_spin_amount')

        # Clear the flags
        context.user_data['awaiting_user_id_for_spins'] = False
        context.user_data['pending_spin_amount'] = None

        # Call addspins command
        context.args = [target_user_id, amount]
        await addspins_command(update, context)
        return

    # Check if admin is replying to a user or providing rejection reason
    if is_admin(user_id) and user_id in admin_reply_context:
        context_data = admin_reply_context[user_id]

        # Check if it's a rejection reason
        if isinstance(context_data, str) and context_data.startswith('reject_'):
            return await handle_rejection_reason(update, context)

        # Otherwise it's a support reply
        return await admin_reply_message_received(update, context)

    # Admin menu buttons
    if text == "📋 Admin Panel":
        return await admin_panel.admin_panel(update, context)
    elif text == "📊 View Deposits" and is_admin(user_id):
        return await admin_panel.admin_view_deposits(update, context)
    elif text == "💸 View Withdrawals" and is_admin(user_id):
        return await admin_panel.admin_view_withdrawals(update, context)
    elif text == "🎮 View Join Requests" and is_admin(user_id):
        return await admin_panel.admin_view_joins(update, context)
    elif text == "💳 Payment Accounts" and is_admin(user_id):
        return await admin_panel.admin_view_accounts(update, context)
    # Regular user menu buttons
    elif text == "💰 Deposit":
        return await deposit_start(update, context)
    elif text == "💸 Withdrawal":
        return await withdrawal_start(update, context)
    elif text == "🎮 Join Club":
        return await join_club_start(update, context)
    elif text == "🪑 Seat":
        return await seat_request_start(update, context)
    elif text == "📊 My Info":
        return await my_info(update, context)
    elif text == "💬 Live Support":
        return await live_support_start(update, context)
    elif text == "❓ Help":
        return await help_command(update, context)
    elif text == "🎲 Free Spins":
        return await freespins_command(update, context)
    elif text == "🎰 Spin Management":
        if is_admin(user_id):
            return await spin_management_panel(update, context)
        else:
            await update.message.reply_text("❌ Admin access required!")
    else:
        # Check if user is in support mode
        if user_id in support_mode_users:
            return await live_support_message(update, context)
        else:
            await update.message.reply_text(
                "Please use the menu buttons or /help for available commands."
            )


def main():
    """Start the bot"""
    # Generate unique instance ID to detect multiple running instances
    import uuid
    import socket
    instance_id = str(uuid.uuid4())[:8]
    hostname = socket.gethostname()
    logger.info(f"🚀 STARTING BOT INSTANCE: {instance_id} on {hostname}")
    logger.info(f"⚠️  WARNING: If you see multiple instance IDs, you have duplicate bots running!")

    # Create application
    # Note: Message IDs are now stored in Django database, no need for local persistence
    application = Application.builder().token(TOKEN).build()
    logger.info(f"💾 Message IDs stored in Django database (survives Railway redeploys)")

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_admin_notification))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("clear_bml", clear_bml_command))
    application.add_handler(CommandHandler("clear_mib", clear_mib_command))
    application.add_handler(CommandHandler("clear_usd", clear_usd_command))
    application.add_handler(CommandHandler("clear_usdt", clear_usdt_command))
    application.add_handler(CommandHandler("set_usd_rate", set_usd_rate_command))
    application.add_handler(CommandHandler("set_usdt_rate", set_usdt_rate_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("listadmins", listadmins_command))
    application.add_handler(CommandHandler("user_credit", user_credit_command))

    # Spin bot command handlers
    application.add_handler(CommandHandler("freespins", freespins_command))
    application.add_handler(CommandHandler("addspins", addspins_command))
    application.add_handler(CommandHandler("spinsstats", spinsstats_command))
    application.add_handler(CommandHandler("pendingspins", pendingspins_command))
    application.add_handler(CommandHandler("approvespin", approvespin_command))

    # Mini App data handler
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_mini_app_data))

    # Test button handlers
    application.add_handler(CallbackQueryHandler(test_button_handler, pattern="^test_"))

    # Spin bot callback handlers
    # IMPORTANT: Register more specific patterns FIRST before generic ones
    application.add_handler(CallbackQueryHandler(spin_admin_callback, pattern="^spin_admin_"))
    # DISABLED: Spinning is now done in Mini App only
    # application.add_handler(CallbackQueryHandler(spin_again_callback, pattern="^spin_again$"))
    application.add_handler(CallbackQueryHandler(approve_spin_callback, pattern="^approve_(spin_|user_)"))
    application.add_handler(CallbackQueryHandler(approve_spinhistory_callback, pattern="^approve_spinhistory_"))
    application.add_handler(CallbackQueryHandler(approve_instant_callback, pattern="^approve_instant_"))
    # application.add_handler(CallbackQueryHandler(spin_callback, pattern="^spin_"))
    # deposit_button_callback is now in deposit ConversationHandler entry_points (line 4740)
    application.add_handler(CallbackQueryHandler(play_freespins_callback, pattern="^play_freespins$"))

    # Button callback handlers for live support
    application.add_handler(CallbackQueryHandler(admin_reply_button_clicked, pattern="^support_reply_"))
    application.add_handler(CallbackQueryHandler(admin_end_support_button, pattern="^support_end_"))
    application.add_handler(CallbackQueryHandler(user_end_support_button, pattern="^user_end_support$"))

    # Quick approval/rejection handlers
    application.add_handler(CallbackQueryHandler(quick_approve_deposit, pattern="^quick_approve_deposit_"))
    application.add_handler(CallbackQueryHandler(quick_reject_deposit, pattern="^quick_reject_deposit_"))
    application.add_handler(CallbackQueryHandler(quick_approve_withdrawal, pattern="^quick_approve_withdrawal_"))
    application.add_handler(CallbackQueryHandler(quick_reject_withdrawal, pattern="^quick_reject_withdrawal_"))
    application.add_handler(CallbackQueryHandler(quick_approve_join, pattern="^quick_approve_join_"))
    application.add_handler(CallbackQueryHandler(quick_reject_join, pattern="^quick_reject_join_"))

    # Seat request handlers
    application.add_handler(CallbackQueryHandler(approve_seat_request, pattern="^approve_seat_"))
    application.add_handler(CallbackQueryHandler(reject_seat_request, pattern="^reject_seat_"))
    application.add_handler(CallbackQueryHandler(show_seat_account_details, pattern="^show_account_(bml|mib|usd|usdt)_"))
    application.add_handler(CallbackQueryHandler(upload_seat_slip_button, pattern="^upload_seat_slip_"))
    application.add_handler(CallbackQueryHandler(settle_seat_slip, pattern="^settle_seat_"))
    application.add_handler(CallbackQueryHandler(reject_seat_slip, pattern="^reject_slip_"))
    application.add_handler(CallbackQueryHandler(clear_user_credit_callback, pattern="^clear_credit_"))

    # Cashback approval handlers
    application.add_handler(CallbackQueryHandler(cashback_approve_callback, pattern="^cashback_approve_"))
    application.add_handler(CallbackQueryHandler(cashback_reject_callback, pattern="^cashback_reject_"))

    # Deposit conversation handler
    deposit_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💰 Deposit$"), deposit_start),
            CallbackQueryHandler(deposit_button_callback, pattern="^deposit_start$")
        ],
        states={
            DEPOSIT_METHOD: [CallbackQueryHandler(deposit_method_selected, pattern="^deposit_")],
            DEPOSIT_PROOF: [MessageHandler(
                (filters.PHOTO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
                deposit_proof_received
            )],
            DEPOSIT_USDT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_usdt_amount_received)],
            DEPOSIT_PPPOKER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_pppoker_id_received)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CommandHandler("cancel", cancel)
        ],
    )

    # Withdrawal conversation handler
    withdrawal_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 Withdrawal$"), withdrawal_start)
        ],
        states={
            WITHDRAWAL_METHOD: [CallbackQueryHandler(withdrawal_method_selected, pattern="^withdrawal_")],
            WITHDRAWAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_amount_received)],
            WITHDRAWAL_PPPOKER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_pppoker_id_received)],
            WITHDRAWAL_ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdrawal_account_number_received)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CommandHandler("cancel", cancel)
        ],
    )

    # Join club conversation handler
    join_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎮 Join Club$"), join_club_start)
        ],
        states={
            JOIN_PPPOKER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_pppoker_id_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Seat request conversation handler
    seat_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🪑 Seat$"), seat_request_start)
        ],
        states={
            SEAT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, seat_amount_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Cashback conversation handler
    cashback_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 Cashback$"), cashback_start)
        ],
        states={
            CASHBACK_PPPOKER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, cashback_pppoker_id_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Live support conversation handler
    support_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💬 Live Support$"), live_support_start)
        ],
        states={
            SUPPORT_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, live_support_message),
            ],
        },
        fallbacks=[CommandHandler("endsupport", end_support)],
    )

    # Admin update payment account conversation handler
    update_account_conv = ConversationHandler(
        entry_points=[
            CommandHandler("update_bml", update_payment_account_start),
            CommandHandler("update_mib", update_payment_account_start),
            CommandHandler("update_usd", update_payment_account_start),
            CommandHandler("update_usdt", update_payment_account_start),
        ],
        states={
            UPDATE_ACCOUNT_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_account_number_received),
                CallbackQueryHandler(update_account_cancel, pattern="^update_account_cancel$"),
            ],
            UPDATE_ACCOUNT_METHOD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_account_holder_received),
                CallbackQueryHandler(update_account_cancel, pattern="^update_account_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(update_account_cancel, pattern="^update_account_cancel$"),
        ],
    )

    # Admin broadcast conversation handler
    broadcast_conv = ConversationHandler(
        entry_points=[
            CommandHandler("broadcast", broadcast_start),
            CallbackQueryHandler(broadcast_start_from_callback, pattern="^admin_broadcast$"),
        ],
        states={
            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message_received),
                MessageHandler(filters.PHOTO, broadcast_message_received),
                CallbackQueryHandler(broadcast_cancel, pattern="^broadcast_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(broadcast_cancel, pattern="^broadcast_cancel$"),
        ],
        per_user=True,
        per_chat=True,
        name="broadcast_conv"
    )

    # Promotion creation conversation handler
    promo_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(promo_create_start, pattern="^promo_create$"),
        ],
        states={
            PROMO_PERCENTAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, promo_percentage_received),
            ],
            PROMO_START_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, promo_start_date_received),
            ],
            PROMO_END_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, promo_end_date_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", promo_cancel),
        ],
    )

    # Cashback promotion creation conversation handler
    cashback_promo_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cashback_promo_create_start, pattern="^cashback_promo_create$"),
        ],
        states={
            CASHBACK_PROMO_PERCENTAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cashback_promo_percentage_received),
            ],
            CASHBACK_PROMO_START_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cashback_promo_start_date_received),
            ],
            CASHBACK_PROMO_END_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cashback_promo_end_date_received),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cashback_promo_cancel),
        ],
    )

    # Add conversation handlers
    application.add_handler(deposit_conv)
    application.add_handler(withdrawal_conv)
    application.add_handler(join_conv)
    application.add_handler(seat_conv)
    application.add_handler(cashback_conv)
    application.add_handler(support_conv)
    application.add_handler(update_account_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(promo_conv)
    application.add_handler(cashback_promo_conv)

    # 50/50 Investment conversation handlers
    investment_add_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(investment_add_start, pattern="^investment_add$"),
        ],
        states={
            INVESTMENT_PPPOKER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, investment_pppoker_id_received),
            ],
            INVESTMENT_NOTE: [
                MessageHandler(filters.TEXT, investment_note_received),
            ],
            INVESTMENT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, investment_amount_received),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="investment_add_conv"
    )

    investment_return_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(investment_return_start, pattern="^investment_return$"),
        ],
        states={
            RETURN_SELECT_ID: [
                MessageHandler(filters.TEXT, return_id_selected),
            ],
            RETURN_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, return_amount_received),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="investment_return_conv"
    )

    application.add_handler(investment_add_conv)
    application.add_handler(investment_return_conv)

    # Club Balance conversation handlers
    balance_setup_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(balance_setup_start, pattern="^balances_setup$"),
        ],
        states={
            BALANCE_SETUP_CHIPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_setup_chips_received),
            ],
            BALANCE_SETUP_COST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_setup_cost_received),
            ],
            BALANCE_SETUP_MVR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_setup_mvr_received),
            ],
            BALANCE_SETUP_USD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_setup_usd_received),
            ],
            BALANCE_SETUP_USDT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_setup_usdt_received),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="balance_setup_conv"
    )

    balance_buy_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(balance_buy_chips_start, pattern="^balances_buy_chips$"),
        ],
        states={
            BALANCE_BUY_CHIPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_buy_chips_amount_received),
            ],
            BALANCE_BUY_COST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_buy_cost_received),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="balance_buy_conv"
    )

    balance_add_cash_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(balance_add_cash_start, pattern="^balances_add_cash$"),
        ],
        states={
            BALANCE_ADD_CURRENCY: [
                CallbackQueryHandler(balance_add_currency_selected, pattern="^add_cash_(mvr|usd|usdt)$"),
            ],
            BALANCE_ADD_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_add_amount_received),
            ],
            BALANCE_ADD_NOTE: [
                MessageHandler(filters.TEXT, balance_add_note_received),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="balance_add_cash_conv"
    )

    application.add_handler(balance_setup_conv)
    application.add_handler(balance_buy_conv)
    application.add_handler(balance_add_cash_conv)

    # Counter control conversation handlers
    counter_close_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(counter_close_with_poster, pattern="^counter_close_with_poster$"),
            CallbackQueryHandler(counter_close_new_poster, pattern="^counter_close_new_poster$"),
        ],
        states={
            COUNTER_CLOSE_POSTER: [
                MessageHandler(filters.PHOTO, counter_close_poster_received),
            ],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
        name="counter_close_conv"
    )

    counter_open_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(counter_open_with_poster, pattern="^counter_open_with_poster$"),
            CallbackQueryHandler(counter_open_new_poster, pattern="^counter_open_new_poster$"),
        ],
        states={
            COUNTER_OPEN_POSTER: [
                MessageHandler(filters.PHOTO, counter_open_poster_received),
            ],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
        name="counter_open_conv"
    )

    application.add_handler(counter_close_conv)
    application.add_handler(counter_open_conv)

    # Counter control callback handlers (non-conversation)
    application.add_handler(CallbackQueryHandler(counter_close_text_only, pattern="^counter_close_text_only$"))
    application.add_handler(CallbackQueryHandler(counter_close_silent, pattern="^counter_close_silent$"))
    application.add_handler(CallbackQueryHandler(counter_close_saved_poster, pattern="^counter_close_saved_poster$"))
    application.add_handler(CallbackQueryHandler(counter_open_text_only, pattern="^counter_open_text_only$"))
    application.add_handler(CallbackQueryHandler(counter_open_silent, pattern="^counter_open_silent$"))
    application.add_handler(CallbackQueryHandler(counter_open_saved_poster, pattern="^counter_open_saved_poster$"))

    # Photo handler for seat slip uploads
    application.add_handler(MessageHandler(filters.PHOTO, handle_seat_slip_upload))

    # Register admin handlers and share notification_messages dict and spin_bot instance
    logger.info(f"🔧 Registering admin handlers with spin_bot: {spin_bot is not None}")
    admin_panel.register_admin_handlers(application, notification_messages, spin_bot)

    # Add general text handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Set up scheduler for daily reports
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Indian/Maldives'))

    # Schedule daily report at midnight (00:00)
    scheduler.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=0, minute=0),
        args=[application],
        id='daily_report',
        name='Daily Profit/Loss Report'
    )

    # Schedule 50/50 investment expiry check every hour
    def check_expired_investments():
        """Mark investments older than 24 hours as Lost"""
        try:
            marked_count = api.mark_expired_investments_as_lost()
            if marked_count > 0:
                logger.info(f"Marked {marked_count} expired 50/50 investments as Lost")
        except Exception as e:
            logger.error(f"Error checking expired investments: {e}")

    scheduler.add_job(
        check_expired_investments,
        trigger=CronTrigger(minute=0),  # Run every hour at :00
        id='check_expired_investments',
        name='Check Expired 50/50 Investments'
    )

    # Schedule spin notification check every 3 seconds for near-instant notifications
    async def check_spin_notifications():
        """Check for new spin rewards and send notifications instantly"""
        try:
            from datetime import datetime, timedelta
            import requests

            # Get all pending spins that haven't been notified yet
            # Filter at database level to avoid fetching already-notified spins
            response = requests.get(
                f'{DJANGO_API_URL}/spin-history/?status=Pending&notified_at__isnull=true',
                headers={
                    'Authorization': f'Bearer {api.token}' if hasattr(api, 'token') and api.token else '',
                    'Content-Type': 'application/json'
                }
            )
            if response.status_code != 200:
                logger.error(f"Failed to get pending spins: HTTP {response.status_code} - {response.text}")
                return

            data = response.json()
            pending_spins = data.get('results', []) if isinstance(data, dict) else data

            if not pending_spins:
                # No unnotified spins - this is normal, just check again later
                return

            logger.info(f"📊 Check spin notifications: Found {len(pending_spins)} unnotified pending spins")

            # Group by user for batching spins from same session
            from collections import defaultdict
            user_all_spins = defaultdict(list)

            # Group all unnotified spins by user
            for spin in pending_spins:
                user_id = spin.get('user_details', {}).get('telegram_id')
                if user_id:
                    user_all_spins[user_id].append(spin)
                else:
                    logger.warning(f"⚠️ Spin {spin.get('id')} has no user telegram_id")

            # Smart batching: Wait 2 seconds only if user just spun (to catch multiple quick spins)
            # This allows batching 50x spins while keeping notifications near-instant
            user_spins = {}
            for user_id, spins in user_all_spins.items():
                # Find the most recent spin for this user
                most_recent_spin = max(spins, key=lambda s: s['created_at'])
                created_at_str = most_recent_spin['created_at'].replace('Z', '+00:00')
                created_at = datetime.fromisoformat(created_at_str)

                # Use UTC for both timestamps to avoid timezone issues
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                age_seconds = (now_utc - created_at).total_seconds()

                logger.info(f"📅 User {user_id}: {len(spins)} unnotified spins, most recent is {age_seconds:.1f}s old")

                # Smart logic: Send immediately if 2+ seconds old OR if user has 10+ spins (bulk spin)
                if age_seconds >= 2 or len(spins) >= 10:
                    logger.info(f"✅ Sending instant notification for user {user_id} ({len(spins)} spins)")
                    user_spins[user_id] = spins
                else:
                    logger.info(f"⏳ User {user_id} batch waiting {age_seconds:.1f}s (need 2s)")

            # Send notifications for each user
            if user_spins:
                logger.info(f"📨 Sending spin notifications for {len(user_spins)} user(s) (notifying users + all admins)")
                for user_id, spins in user_spins.items():
                    await send_spin_notification(application, user_id, spins)
            else:
                logger.info(f"⏳ All unnotified spins are too recent (waiting 2s for batching)")

        except Exception as e:
            logger.error(f"❌ Error checking spin notifications: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def send_spin_notification(app, user_id, spins):
        """Send notification to user and admins about new spin rewards"""
        try:
            total_chips = sum(s.get('chips', 0) for s in spins)
            spin_count = len(spins)

            # Get current user info from API (not from spin record which might be outdated)
            user_info = api.get_user_by_telegram_id(user_id)
            logger.info(f"📋 Retrieved user info from API: {user_info}")

            if isinstance(user_info, dict) and user_info:
                # API returns username with @ prefix, so remove it if present
                raw_username = user_info.get('username', 'User')
                username = raw_username.lstrip('@') if raw_username else 'User'
                pppoker_id = user_info.get('pppoker_id', 'N/A')
                logger.info(f"📝 Using API data - Username: {username}, PPPoker ID: {pppoker_id}")
            else:
                # Fallback to spin record if API call fails
                logger.warning(f"⚠️ API call failed, using spin record data")
                username = spins[0].get('user_details', {}).get('username', 'User')
                pppoker_id = spins[0].get('user_details', {}).get('pppoker_id', 'N/A')
                logger.info(f"📝 Using spin record - Username: {username}, PPPoker ID: {pppoker_id}")

            # Notify user
            user_message = (
                f"🎰 <b>SPIN REWARDS!</b> 🎰\n\n"
                f"🎁 You won <b>{total_chips} chips</b> from {spin_count} spin{'s' if spin_count > 1 else ''}!\n\n"
                f"⏳ Your rewards are pending admin approval.\n"
                f"You'll be notified once approved!"
            )

            try:
                await app.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
                logger.info(f"✅ Notified user {user_id} about {spin_count} spin rewards ({total_chips} chips)")
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")

            # Notify admins - show TOTAL pending rewards for this user
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import requests

            # Get ALL pending spins for this user to show total
            try:
                response = requests.get(
                    f'{DJANGO_API_URL}/spin-history/?status=Pending',
                    headers={
                        'Authorization': f'Bearer {api.token}' if hasattr(api, 'token') and api.token else '',
                        'Content-Type': 'application/json'
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    all_pending = data.get('results', []) if isinstance(data, dict) else data
                    # Filter for this specific user
                    user_pending = [s for s in all_pending if s.get('user_details', {}).get('telegram_id') == user_id]
                    total_pending_count = len(user_pending)
                    total_pending_chips = sum(s.get('chips', 0) for s in user_pending)
                else:
                    # Fallback to current batch
                    total_pending_count = spin_count
                    total_pending_chips = total_chips
            except Exception as e:
                logger.error(f"Error fetching total pending: {e}")
                total_pending_count = spin_count
                total_pending_chips = total_chips

            # Show current batch + total pending
            if total_pending_count > spin_count:
                # User has multiple batches of pending spins
                admin_message = (
                    f"🎰 <b>NEW SPIN REWARDS</b> 🎰\n\n"
                    f"👤 User: @{username}\n"
                    f"🆔 Telegram ID: <code>{user_id}</code>\n"
                    f"🎮 PPPoker ID: <code>{pppoker_id}</code>\n\n"
                    f"🆕 <b>Latest: {spin_count} spin{'s' if spin_count > 1 else ''} = {total_chips} chips</b>\n"
                    f"📊 <b>TOTAL PENDING: {total_pending_count} spins = {total_pending_chips} chips</b>\n\n"
                    f"Use the button below or /pendingspins to review."
                )
            else:
                # Only one batch pending
                admin_message = (
                    f"🎰 <b>NEW SPIN REWARDS</b> 🎰\n\n"
                    f"👤 User: @{username}\n"
                    f"🆔 Telegram ID: <code>{user_id}</code>\n"
                    f"🎮 PPPoker ID: <code>{pppoker_id}</code>\n\n"
                    f"🎁 <b>{spin_count} spin{'s' if spin_count > 1 else ''}: {total_chips} chips</b>\n\n"
                    f"Use the button below or /pendingspins to review."
                )

            # Create approve button
            keyboard = [
                [InlineKeyboardButton("✅ Approve All", callback_data=f"approve_instant_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Store message IDs in Django database to persist across bot restarts
            # This ensures buttons can be removed even after Railway redeploys
            notification_key = f"spin_reward_{user_id}"

            # Send to super admin with button
            try:
                sent_msg = await app.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=admin_message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                # Store message ID in Django database for later button removal
                try:
                    api.store_notification_message(
                        notification_type='spin_reward',
                        notification_key=notification_key,
                        admin_telegram_id=ADMIN_USER_ID,
                        message_id=sent_msg.message_id
                    )
                    logger.info(f"✅ Stored message ID {sent_msg.message_id} in database for super admin {ADMIN_USER_ID}")
                except Exception as e:
                    logger.error(f"Failed to store message ID in database: {e}")
            except Exception as e:
                logger.error(f"Failed to notify super admin: {e}")

            # Send to regular admins with button
            admins_response = api.get_all_admins()
            logger.info(f"📋 Retrieved admins response: {admins_response}")

            # Handle paginated response
            if isinstance(admins_response, dict) and 'results' in admins_response:
                admins = admins_response['results']
            elif isinstance(admins_response, list):
                admins = admins_response
            else:
                logger.error(f"❌ Unexpected admins response format: {admins_response}")
                admins = []

            admin_notified_count = 1  # Already sent to super admin
            if admins:
                logger.info(f"📊 Total admins found: {len(admins)}")
                for admin in admins:
                    admin_telegram_id = admin.get('telegram_id')
                    logger.info(f"🔍 Processing admin: {admin_telegram_id} (Super admin: {ADMIN_USER_ID})")

                    if admin_telegram_id != ADMIN_USER_ID:
                        try:
                            sent_msg = await app.bot.send_message(
                                chat_id=admin_telegram_id,
                                text=admin_message,
                                parse_mode='HTML',
                                reply_markup=reply_markup
                            )
                            # Store message ID in Django database for later button removal
                            try:
                                api.store_notification_message(
                                    notification_type='spin_reward',
                                    notification_key=notification_key,
                                    admin_telegram_id=admin_telegram_id,
                                    message_id=sent_msg.message_id
                                )
                                logger.info(f"✅ Sent notification to admin {admin_telegram_id}, stored message ID {sent_msg.message_id} in database")
                            except Exception as e:
                                logger.error(f"Failed to store message ID in database: {e}")
                            admin_notified_count += 1
                        except Exception as e:
                            logger.error(f"❌ Failed to notify admin {admin_telegram_id}: {e}")
                    else:
                        logger.info(f"⏭️ Skipping super admin {admin_telegram_id} (already notified)")

                logger.info(f"📬 Total notifications sent: 1 user + {admin_notified_count} admin(s) = {1 + admin_notified_count} messages")
            else:
                logger.warning(f"⚠️ No admins to notify (besides super admin)")

            # Mark spins as notified
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            logger.info(f"⏰ Marking {len(spins)} spins as notified at {now_iso}")

            for spin in spins:
                try:
                    # Use the django_api method to properly mark as notified
                    result = api.update_spin_history(
                        spin_id=spin['id'],
                        notified_at=now_iso
                    )
                    logger.info(f"✅ API response for spin {spin['id']}: {result}")

                    # Verify it was actually updated
                    if result and result.get('notified_at'):
                        logger.info(f"✅ Successfully marked spin {spin['id']} as notified")
                    else:
                        logger.error(f"⚠️ Spin {spin['id']} marked but API returned unexpected response: {result}")
                except Exception as e:
                    logger.error(f"❌ Failed to mark spin {spin['id']} as notified: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"Error sending spin notification: {e}")

    scheduler.add_job(
        check_spin_notifications,
        trigger='interval',
        seconds=3,  # Check every 3 seconds for near-instant notifications
        id='check_spin_notifications',
        name='Check Spin Notifications'
    )

    # Start scheduler after application initializes
    async def post_init(application):
        scheduler.start()
        logger.info("Scheduler started - Daily reports will be sent at midnight (00:00) Maldives time")
        logger.info("50/50 investment expiry check will run every hour")
        logger.info("Spin notifications: Near-instant delivery (3s checks, 2s batching for multiple spins)")

    application.post_init = post_init

    # Add error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by updates."""
        import traceback
        logger.error(f"Exception while handling an update: {context.error}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(None, context.error, context.error.__traceback__))}")
        logger.error(f"Update: {update}")

        # Try to notify the user
        if update and hasattr(update, 'effective_message') and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred while processing your request. Please try again or contact support."
                )
            except Exception:
                pass

    application.add_error_handler(error_handler)

    # Log startup
    logger.info("Bot started successfully!")
    print("🤖 Billionaires PPPoker Bot is running...")
    print("📊 Daily reports scheduled for midnight")
    print("💎 50/50 investment expiry check runs every hour")

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
