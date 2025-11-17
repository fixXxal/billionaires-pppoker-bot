"""
Billionaires PPPoker Club Telegram Bot
Main bot file with all handlers and logic
"""

import os
import logging
import asyncio
from typing import Dict
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sheets_manager import SheetsManager
import admin_panel
import vision_api
from spin_bot import SpinBot
import spin_bot as spin_bot_module

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')

# Initialize Sheets Manager
sheets = SheetsManager(CREDENTIALS_FILE, SPREADSHEET_NAME, TIMEZONE)

# Initialize Spin Bot
spin_bot = SpinBot(sheets, ADMIN_USER_ID, pytz.timezone(TIMEZONE))

# Conversation states
(DEPOSIT_METHOD, DEPOSIT_AMOUNT, DEPOSIT_PPPOKER_ID, DEPOSIT_ACCOUNT_NAME,
 DEPOSIT_PROOF, WITHDRAWAL_METHOD, WITHDRAWAL_AMOUNT, WITHDRAWAL_PPPOKER_ID,
 WITHDRAWAL_ACCOUNT_NAME, WITHDRAWAL_ACCOUNT_NUMBER, JOIN_PPPOKER_ID,
 ADMIN_APPROVAL_NOTES, SUPPORT_CHAT, ADMIN_REPLY_MESSAGE, UPDATE_ACCOUNT_METHOD, UPDATE_ACCOUNT_NUMBER, BROADCAST_MESSAGE,
 PROMO_PERCENTAGE, PROMO_START_DATE, PROMO_END_DATE, SEAT_AMOUNT, SEAT_SLIP_UPLOAD) = range(22)

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
    return sheets.is_admin(user_id, ADMIN_USER_ID)


# Spin Bot Wrapper Functions
async def freespins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for spin bot freespins command"""
    await spin_bot_module.freespins_command(update, context, spin_bot)

async def spin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for spin bot callback"""
    await spin_bot_module.spin_callback(update, context, spin_bot, ADMIN_USER_ID)

async def spin_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for spin again callback"""
    await spin_bot_module.spin_again_callback(update, context, spin_bot)

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


async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send notification to all admins"""
    # Send to super admin
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send notification to super admin: {e}")

    # Send to all regular admins
    try:
        admins = sheets.get_all_admins()
        for admin in admins:
            try:
                await context.bot.send_message(chat_id=admin['admin_id'], text=message, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Failed to send notification to admin {admin['admin_id']}: {e}")
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")


# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    # Create or update user in database
    sheets.create_or_update_user(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )

    # Check if user is admin - show admin menu
    if is_admin(user.id):
        keyboard = [
            [KeyboardButton("📋 Admin Panel"), KeyboardButton("🎰 Spin Management")],
            [KeyboardButton("📊 View Deposits"), KeyboardButton("💸 View Withdrawals")],
            [KeyboardButton("🎮 View Join Requests"), KeyboardButton("💳 Payment Accounts")],
            [KeyboardButton("🎲 Free Spins"), KeyboardButton("👤 User Mode")]
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
🎲 <b>Free Spins</b> - Play spin wheel
👤 <b>User Mode</b> - Switch to regular user view

Select an option to get started:
"""
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Regular user menu
        keyboard = [
            [KeyboardButton("💰 Deposit"), KeyboardButton("💸 Withdrawal")],
            [KeyboardButton("🎲 Free Spins"), KeyboardButton("🎮 Join Club")],
            [KeyboardButton("🪑 Seat"), KeyboardButton("💬 Live Support")],
            [KeyboardButton("📊 My Info"), KeyboardButton("❓ Help")]
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


# User Mode - Switch admin to user view
async def user_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch admin to regular user mode"""
    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("This command is for admins only.")
        return

    keyboard = [
        [KeyboardButton("💰 Deposit"), KeyboardButton("💸 Withdrawal")],
        [KeyboardButton("🎲 Free Spins"), KeyboardButton("🎮 Join Club")],
        [KeyboardButton("🪑 Seat"), KeyboardButton("💬 Live Support")],
        [KeyboardButton("📊 My Info"), KeyboardButton("❓ Help")],
        [KeyboardButton("🔙 Back to Admin")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👤 <b>Switched to User Mode</b>\n\n"
        "You're now viewing the bot as a regular user.\n"
        "Use <b>🔙 Back to Admin</b> to return to admin panel.",
        reply_markup=reply_markup,
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
    user_data = sheets.get_user(update.effective_user.id)

    # Get all configured payment accounts
    payment_accounts = sheets.get_all_payment_accounts()

    # Build keyboard with only configured payment methods
    keyboard = []
    if 'BML' in payment_accounts and payment_accounts['BML']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 BML", callback_data="deposit_bml")])
    if 'MIB' in payment_accounts and payment_accounts['MIB']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 MIB", callback_data="deposit_mib")])
    if 'USD' in payment_accounts and payment_accounts['USD']['account_number']:
        keyboard.append([InlineKeyboardButton("💵 USD", callback_data="deposit_usd")])
    if 'USDT' in payment_accounts and payment_accounts['USDT']['account_number']:
        keyboard.append([InlineKeyboardButton("💎 USDT (TRC20)", callback_data="deposit_usdt")])

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
    account = sheets.get_payment_account(method)
    account_holder = sheets.get_payment_account_holder(method)

    if not account:
        await query.edit_message_text(
            "❌ Payment account not configured. Please contact admin."
        )
        return ConversationHandler.END

    method_names = {'BML': 'Bank of Maldives', 'MIB': 'Maldives Islamic Bank', 'USD': 'USD Bank Transfer', 'USDT': 'USDT (TRC20)'}

    # Ask for receipt/slip directly after showing account details
    if method == 'USDT':
        message = f"💰 <b>Deposit via {method_names[method]}</b>\n\n"

        # Show exchange rate for USDT
        usdt_rate = sheets.get_exchange_rate('USDT')
        if usdt_rate:
            message += f"💱 <b>Current Rate:</b> 1 USDT = {usdt_rate:.2f} MVR\n\n"

        message += f"<b>Wallet Address:</b> <a href='#'>(tap to copy)</a>\n"
        message += f"<code>{account}</code>\n\n"
        message += f"📝 Please send your <b>Transaction ID (TXID)</b> from the blockchain:"

        await query.edit_message_text(message, parse_mode='HTML')
    elif method == 'USD':
        # Build message with exchange rate and account details
        message = f"💰 <b>Deposit via {method_names[method]}</b>\n\n"

        # Show exchange rate for USD
        usd_rate = sheets.get_exchange_rate('USD')
        if usd_rate:
            message += f"💱 <b>Current Rate:</b> 1 USD = {usd_rate:.2f} MVR\n\n"

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
    pppoker_id = update.message.text.strip()

    # Update user's PPPoker ID
    sheets.update_user_pppoker_id(user.id, pppoker_id)

    # Get stored data from context
    method = context.user_data['deposit_method']
    transaction_ref = context.user_data['transaction_ref']
    extracted_details = context.user_data.get('extracted_details')

    # Get amount and account name from extracted details (or use defaults)
    amount = extracted_details['amount'] if extracted_details and extracted_details['amount'] else 0
    account_name = extracted_details['sender_name'] if extracted_details and extracted_details['sender_name'] else "Not extracted"

    # Update user's account name if we extracted it
    if extracted_details and extracted_details['sender_name']:
        sheets.update_user_account_name(user.id, extracted_details['sender_name'])

    # Create deposit request
    request_id = sheets.create_deposit_request(
        user.id,
        user.username,
        pppoker_id,
        amount,
        method,
        account_name,
        transaction_ref
    )

    # Send confirmation to user with extracted reference number
    confirmation_msg = f"✅ **Deposit Request Submitted!**\n\n"
    confirmation_msg += f"**Request ID:** `{request_id}`\n"

    # Show extracted reference number prominently
    if extracted_details and extracted_details['reference_number']:
        confirmation_msg += f"**Slip Reference:** `{extracted_details['reference_number']}`\n"

    confirmation_msg += f"**Amount:** {amount} {'MVR' if method != 'USDT' else 'USD'}\n"
    confirmation_msg += f"**Method:** {method}\n"
    confirmation_msg += f"**PPPoker ID:** {pppoker_id}\n\n"
    confirmation_msg += f"Your request is being reviewed. You'll be notified once processed! ⏳"

    await update.message.reply_text(confirmation_msg, parse_mode='Markdown')

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
    if extracted_details:
        if extracted_details['amount'] and extracted_details['amount'] > 0:
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
        stored_holder_name = sheets.get_payment_account_holder(verified_bank)

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
        stored_account_number = sheets.get_payment_account(verified_bank)

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

    # Currency
    currency = 'MVR' if method != 'USDT' else 'USD'

    # Check for active promotion and user eligibility
    promotion_info = ""
    promotion_bonus = 0
    active_promotion = sheets.get_active_promotion()

    if active_promotion and verified_amount > 0:
        # Check if user is eligible (first deposit during promotion period)
        is_eligible = sheets.check_user_promotion_eligibility(
            user.id,
            pppoker_id,
            active_promotion['promotion_id']
        )

        if is_eligible:
            # Calculate bonus
            promotion_bonus = verified_amount * (active_promotion['bonus_percentage'] / 100)
            total_with_bonus = verified_amount + promotion_bonus

            promotion_info = f"\n\n🎁 <b>PROMOTION BONUS</b>\n" \
                           f"Bonus: {active_promotion['bonus_percentage']}% = <b>{currency} {promotion_bonus:,.2f}</b>\n" \
                           f"Total with bonus: <b>{currency} {total_with_bonus:,.2f}</b>\n" \
                           f"<i>User's first deposit during promotion period</i>"

            # Store promotion info in context for approval handler
            context.bot_data[f'promo_{request_id}'] = {
                'promotion_id': active_promotion['promotion_id'],
                'bonus_amount': promotion_bonus,
                'deposit_amount': verified_amount,
                'pppoker_id': pppoker_id,
                'user_id': user.id,
                'currency': currency
            }

    # Build clean, organized notification
    admin_message = f"""💰 <b>NEW {method} DEPOSIT</b> — {request_id}

👤 <b>USER DETAILS</b>
Name: {user.first_name} {user.last_name or ''}
Username: {username_display}
User ID: <code>{user.id}</code>

🏦 <b>TRANSACTION DETAILS</b>
Reference: <code>{ref_number}</code>
Amount: <b>{currency} {verified_amount:,.2f}</b>
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

    # Get all admin IDs
    all_admin_ids = [ADMIN_USER_ID]
    try:
        regular_admins = sheets.get_all_admins()
        all_admin_ids.extend([admin['admin_id'] for admin in regular_admins])
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")

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
    sheets.update_user_account_name(update.effective_user.id, account_name)

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


# Withdrawal Flow
async def withdrawal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal process"""
    user_data = sheets.get_user(update.effective_user.id)

    if not user_data or not user_data.get('account_name'):
        await update.message.reply_text(
            "⚠️ You need to make at least one deposit first to set up your account name.\n"
            "Withdrawals can only be sent to the same account name used for deposits."
        )
        return ConversationHandler.END

    # Get all configured payment accounts
    payment_accounts = sheets.get_all_payment_accounts()

    # Build keyboard with only configured payment methods
    keyboard = []
    if 'BML' in payment_accounts and payment_accounts['BML']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 BML", callback_data="withdrawal_bml")])
    if 'MIB' in payment_accounts and payment_accounts['MIB']['account_number']:
        keyboard.append([InlineKeyboardButton("🏦 MIB", callback_data="withdrawal_mib")])
    if 'USD' in payment_accounts and payment_accounts['USD']['account_number']:
        keyboard.append([InlineKeyboardButton("💵 USD", callback_data="withdrawal_usd")])
    if 'USDT' in payment_accounts and payment_accounts['USDT']['account_number']:
        keyboard.append([InlineKeyboardButton("💎 USDT (TRC20)", callback_data="withdrawal_usdt")])

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
        f"💸 **Withdrawal from Billionaires Club**\n\n"
        f"**Registered Account Name:** {user_data['account_name']}\n\n"
        f"⚠️ Withdrawals will only be sent to accounts with this name.\n\n"
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

    method_names = {'BML': 'Bank of Maldives', 'MIB': 'Maldives Islamic Bank', 'USD': 'USD Bank Transfer', 'USDT': 'USDT (TRC20)'}

    message = f"💸 <b>Withdrawal via {method_names[method]}</b>\n\n"

    # Show exchange rate for USD/USDT
    if method == 'USD':
        usd_rate = sheets.get_exchange_rate('USD')
        if usd_rate:
            message += f"💱 <b>Current Rate:</b> 1 USD = {usd_rate:.2f} MVR\n\n"
    elif method == 'USDT':
        usdt_rate = sheets.get_exchange_rate('USDT')
        if usdt_rate:
            message += f"💱 <b>Current Rate:</b> 1 USDT = {usdt_rate:.2f} MVR\n\n"

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
    pppoker_id = update.message.text.strip()
    context.user_data['withdrawal_pppoker_id'] = pppoker_id

    method = context.user_data['withdrawal_method']

    if method == 'USDT':
        await update.message.reply_text(
            "💎 Please enter your **USDT wallet address** (TRC20):\n\n"
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
    user_data = sheets.get_user(user.id)

    account_number = update.message.text.strip()
    method = context.user_data['withdrawal_method']
    amount = context.user_data['withdrawal_amount']
    pppoker_id = context.user_data['withdrawal_pppoker_id']
    account_name = user_data['account_name']

    # Create withdrawal request
    request_id = sheets.create_withdrawal_request(
        user.id,
        user.username,
        pppoker_id,
        amount,
        method,
        account_name,
        account_number
    )

    # Send confirmation to user
    await update.message.reply_text(
        f"✅ **Withdrawal Request Submitted!**\n\n"
        f"**Request ID:** `{request_id}`\n"
        f"**Amount:** {amount} {'MVR' if method != 'USDT' else 'USD'}\n"
        f"**Method:** {method}\n"
        f"**PPPoker ID:** {pppoker_id}\n"
        f"**Account Name:** {account_name}\n"
        f"**Account Number:** {account_number}\n\n"
        f"Your request is being processed. You'll be notified once completed! ⏳",
        parse_mode='Markdown'
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
        regular_admins = sheets.get_all_admins()
        all_admin_ids.extend([admin['admin_id'] for admin in regular_admins])
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")

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
    pppoker_id = update.message.text.strip()

    # Create join request
    request_id = sheets.create_join_request(
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        pppoker_id
    )

    # Update user's PPPoker ID
    sheets.update_user_pppoker_id(user.id, pppoker_id)

    # Send confirmation to user
    await update.message.reply_text(
        f"✅ **Club Join Request Submitted!**\n\n"
        f"**Request ID:** `{request_id}`\n"
        f"**PPPoker ID:** {pppoker_id}\n\n"
        f"Your request is being reviewed. You'll be notified once approved! ⏳",
        parse_mode='Markdown'
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
        regular_admins = sheets.get_all_admins()
        all_admin_ids.extend([admin['admin_id'] for admin in regular_admins])
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")

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


# My Info Command
async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user information"""
    user = update.effective_user
    user_data = sheets.get_user(user.id)

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
    user = update.effective_user

    # Check if user has active credit
    existing_credit = sheets.get_user_credit(user.id)
    if existing_credit:
        await update.message.reply_text(
            f"⚠️ **You already have an active credit!**\n\n"
            f"💰 Credit Amount: {existing_credit['amount']} chips/MVR\n"
            f"📅 Created: {existing_credit['created_at']}\n\n"
            f"Please settle your existing credit before requesting a new seat.\n"
            f"Upload your payment slip or contact Live Support.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # Get user's last PPPoker ID from deposits
    user_data = sheets.get_user(user.id)
    if not user_data or not user_data.get('pppoker_id'):
        await update.message.reply_text(
            "❌ **No PPPoker ID found!**\n\n"
            "Please make a deposit first to register your PPPoker ID.\n"
            "Use /start and select 💰 Deposit.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

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

        # Get user's PPPoker ID
        user_data = sheets.get_user(user.id)
        pppoker_id = user_data.get('pppoker_id')

        # Create seat request
        request_id = sheets.create_seat_request(
            user.id,
            user.username,
            pppoker_id,
            amount
        )

        # Store in context for later use
        context.user_data['seat_request_id'] = request_id
        context.user_data['seat_amount'] = amount
        context.user_data['seat_pppoker_id'] = pppoker_id

        # Send confirmation to user
        await update.message.reply_text(
            f"✅ **Seat Request Submitted!**\n\n"
            f"**Request ID:** `{request_id}`\n"
            f"**Amount:** {amount} chips\n"
            f"**PPPoker ID:** {pppoker_id}\n\n"
            f"Your request is being reviewed by the admin. Please wait... ⏳",
            parse_mode='Markdown'
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

        # Send to all admins
        all_admin_ids = [ADMIN_USER_ID]
        try:
            regular_admins = sheets.get_all_admins()
            all_admin_ids.extend([admin['admin_id'] for admin in regular_admins])
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
    all_admins = sheets.get_all_admins()
    admin_ids = [ADMIN_USER_ID]  # Start with super admin
    for admin in all_admins:
        if admin['admin_id'] != ADMIN_USER_ID:
            admin_ids.append(admin['admin_id'])

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
        all_admins = sheets.get_all_admins()
        admin_ids = [ADMIN_USER_ID]  # Start with super admin
        for admin in all_admins:
            if admin['admin_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['admin_id'])

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
        all_admins = sheets.get_all_admins()
        admin_ids = [ADMIN_USER_ID]  # Start with super admin
        for admin in all_admins:
            if admin['admin_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['admin_id'])

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
            handling_admin_info = sheets.get_all_admins()
            handler_name = "Another admin"
            for admin in handling_admin_info:
                if admin['admin_id'] == handling_admin:
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
    all_admins = sheets.get_all_admins()
    admin_ids = [ADMIN_USER_ID]  # Start with super admin
    for admin in all_admins:
        if admin['admin_id'] != ADMIN_USER_ID:
            admin_ids.append(admin['admin_id'])

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
            handling_admin_info = sheets.get_all_admins()
            handler_name = "Another admin"
            for admin in handling_admin_info:
                if admin['admin_id'] == handling_admin:
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
        all_admins = sheets.get_all_admins()
        admin_ids = [ADMIN_USER_ID]  # Start with super admin
        for admin in all_admins:
            if admin['admin_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['admin_id'])

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
        all_admins = sheets.get_all_admins()
        admin_ids = [ADMIN_USER_ID]
        for admin in all_admins:
            if admin['admin_id'] != ADMIN_USER_ID:
                admin_ids.append(admin['admin_id'])

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
    """Generate daily and weekly profit/loss statistics report for automatic notifications"""
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)

    # Define date ranges - ONLY TODAY and THIS WEEK
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now

    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get data from sheets - ONLY TODAY and THIS WEEK
    periods = {
        'TODAY': (today_start, today_end),
        'THIS WEEK': (week_start, today_end)
    }

    # Get exchange rates
    usd_rate = sheets.get_exchange_rate('USD') or 15.40
    usdt_rate = sheets.get_exchange_rate('USDT') or 15.40

    report = "📊 <b>PROFIT/LOSS REPORT</b>\n\n"
    report += f"💱 <b>Current Exchange Rates:</b>\n"
    report += f"1 USD = {usd_rate:.2f} MVR\n"
    report += f"1 USDT = {usdt_rate:.2f} MVR\n\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"

    # Store data for saving to Google Sheets
    report_data = {}

    for period_name, (start, end) in periods.items():
        deposits = sheets.get_deposits_by_date_range(start, end)
        withdrawals = sheets.get_withdrawals_by_date_range(start, end)

        # Separate by currency
        mvr_deposits = sum([d['amount'] for d in deposits if d['method'] in ['BML', 'MIB']])
        usd_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USD'])
        usdt_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USDT'])

        mvr_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] in ['BML', 'MIB']])
        usd_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USD'])
        usdt_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USDT'])

        # Calculate profits per currency
        mvr_profit = mvr_deposits - mvr_withdrawals
        usd_profit = usd_deposits - usd_withdrawals
        usdt_profit = usdt_deposits - usdt_withdrawals

        # Calculate MVR equivalents
        usd_mvr_equiv = usd_profit * usd_rate
        usdt_mvr_equiv = usdt_profit * usdt_rate
        total_mvr_profit = mvr_profit + usd_mvr_equiv + usdt_mvr_equiv

        # Save data for Google Sheets
        prefix = 'today_' if period_name == 'TODAY' else 'week_'
        report_data[f'{prefix}mvr_deposits'] = mvr_deposits
        report_data[f'{prefix}mvr_withdrawals'] = mvr_withdrawals
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
        if mvr_deposits > 0 or mvr_withdrawals > 0:
            mvr_emoji = "📈" if mvr_profit > 0 else "📉" if mvr_profit < 0 else "➖"
            report += f"💰 MVR Deposits: {mvr_deposits:,.2f}\n"
            report += f"💸 MVR Withdrawals: {mvr_withdrawals:,.2f}\n"
            report += f"{mvr_emoji} MVR Profit: {mvr_profit:,.2f}\n\n"

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

        # Total in MVR
        if (mvr_deposits > 0 or mvr_withdrawals > 0 or
            usd_deposits > 0 or usd_withdrawals > 0 or
            usdt_deposits > 0 or usdt_withdrawals > 0):
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

    # Get exchange rates
    usd_rate = sheets.get_exchange_rate('USD') or 15.40
    usdt_rate = sheets.get_exchange_rate('USDT') or 15.40

    report = "📊 <b>PROFIT/LOSS REPORT</b>\n\n"
    report += f"💱 <b>Current Exchange Rates:</b>\n"
    report += f"1 USD = {usd_rate:.2f} MVR\n"
    report += f"1 USDT = {usdt_rate:.2f} MVR\n\n"
    report += f"━━━━━━━━━━━━━━━━━━\n\n"

    for period_name, (start, end) in periods.items():
        deposits = sheets.get_deposits_by_date_range(start, end)
        withdrawals = sheets.get_withdrawals_by_date_range(start, end)

        # Separate by currency
        mvr_deposits = sum([d['amount'] for d in deposits if d['method'] in ['BML', 'MIB']])
        usd_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USD'])
        usdt_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USDT'])

        mvr_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] in ['BML', 'MIB']])
        usd_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USD'])
        usdt_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USDT'])

        # Calculate profits per currency
        mvr_profit = mvr_deposits - mvr_withdrawals
        usd_profit = usd_deposits - usd_withdrawals
        usdt_profit = usdt_deposits - usdt_withdrawals

        # Calculate MVR equivalents
        usd_mvr_equiv = usd_profit * usd_rate
        usdt_mvr_equiv = usdt_profit * usdt_rate
        total_mvr_profit = mvr_profit + usd_mvr_equiv + usdt_mvr_equiv

        report += f"<b>{period_name}</b>\n"

        # MVR Section
        if mvr_deposits > 0 or mvr_withdrawals > 0:
            mvr_emoji = "📈" if mvr_profit > 0 else "📉" if mvr_profit < 0 else "➖"
            report += f"💰 MVR Deposits: {mvr_deposits:,.2f}\n"
            report += f"💸 MVR Withdrawals: {mvr_withdrawals:,.2f}\n"
            report += f"{mvr_emoji} MVR Profit: {mvr_profit:,.2f}\n\n"

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

        # Total in MVR
        if (mvr_deposits > 0 or mvr_withdrawals > 0 or
            usd_deposits > 0 or usd_withdrawals > 0 or
            usdt_deposits > 0 or usdt_withdrawals > 0):
            total_emoji = "📈" if total_mvr_profit > 0 else "📉" if total_mvr_profit < 0 else "➖"
            report += f"<b>{total_emoji} Total Profit (MVR):</b> {total_mvr_profit:,.2f}\n\n"

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

    success = sheets.clear_payment_account('BML')
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

    success = sheets.clear_payment_account('MIB')
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

    success = sheets.clear_payment_account('USD')
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

    success = sheets.clear_payment_account('USDT')
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
        current_rate = sheets.get_exchange_rate('USD')
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

        success = sheets.set_exchange_rate('USD', rate)
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
        current_rate = sheets.get_exchange_rate('USDT')
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

        success = sheets.set_exchange_rate('USDT', rate)
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
        new_admin_user = sheets.get_user(new_admin_id)
        username = new_admin_user.get('username', '') if new_admin_user else ''
        name = ''
        if new_admin_user:
            first_name = new_admin_user.get('first_name', '')
            last_name = new_admin_user.get('last_name', '')
            name = f"{first_name} {last_name}".strip()

        # Add admin
        success = sheets.add_admin(new_admin_id, username, name, user_id)

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
        success = sheets.remove_admin(admin_id_to_remove)

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
        admins = sheets.get_all_admins()

        message = "👥 <b>ADMIN LIST</b>\n\n"
        message += f"🔱 <b>Super Admin:</b>\n"
        message += f"ID: <code>{ADMIN_USER_ID}</code>\n\n"

        if admins:
            message += f"👤 <b>Regular Admins ({len(admins)}):</b>\n\n"
            for admin in admins:
                message += f"━━━━━━━━━━━━━━━━━━\n"
                message += f"<b>ID:</b> <code>{admin['admin_id']}</code>\n"
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
        credits = sheets.get_all_active_credits()

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
            user_display = f"User {credit['user_id']}"
            if credit.get('username'):
                user_display = f"@{credit['username']}"

            message += "━━━━━━━━━━━━━━━━━━\n"
            message += f"<b>User:</b> {user_display}\n"
            message += f"<b>User ID:</b> <code>{credit['user_id']}</code>\n"
            message += f"<b>PPPoker ID:</b> <code>{credit['pppoker_id']}</code>\n"
            message += f"<b>Credit Amount:</b> <b>{credit['amount']} chips/MVR</b>\n"
            message += f"<b>Request ID:</b> {credit['seat_request_id']}\n"
            message += f"<b>Created:</b> {credit['created_at']}\n"
            message += f"<b>Reminders Sent:</b> {credit['reminder_count']}\n\n"

            # Add button for this user
            button_text = f"✅ Clear Credit - {user_display} ({credit['amount']} MVR)"
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"clear_credit_{credit['user_id']}"
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
    credit = sheets.get_user_credit(user_id)
    if not credit:
        await query.edit_message_text(
            "❌ **Credit not found**\n\n"
            "This credit may have already been cleared.",
            parse_mode='Markdown'
        )
        return

    # Clear the credit
    success = sheets.clear_user_credit(user_id)

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

        await query.edit_message_text(
            f"✅ **Credit Cleared Successfully**\n\n"
            f"**User ID:** `{user_id}`\n"
            f"**Username:** {credit.get('username', 'N/A')}\n"
            f"**Amount:** {credit['amount']} chips/MVR\n\n"
            f"User has been notified.\n\n"
            f"_Use /user_credit to view remaining credits._",
            parse_mode='Markdown'
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
    usd_rate = sheets.get_exchange_rate('USD') or 15.40
    usdt_rate = sheets.get_exchange_rate('USDT') or 15.40

    all_data = {}

    for period_name, (start, end) in periods.items():
        deposits = sheets.get_deposits_by_date_range(start, end)
        withdrawals = sheets.get_withdrawals_by_date_range(start, end)

        # Separate by currency
        mvr_deposits = sum([d['amount'] for d in deposits if d['method'] in ['BML', 'MIB']])
        usd_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USD'])
        usdt_deposits = sum([d['amount'] for d in deposits if d['method'] == 'USDT'])

        mvr_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] in ['BML', 'MIB']])
        usd_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USD'])
        usdt_withdrawals = sum([w['amount'] for w in withdrawals if w['method'] == 'USDT'])

        # Calculate profits
        mvr_profit = mvr_deposits - mvr_withdrawals
        usd_profit = usd_deposits - usd_withdrawals
        usdt_profit = usdt_deposits - usdt_withdrawals

        # Calculate total profit in MVR
        usd_mvr_equiv = usd_profit * usd_rate
        usdt_mvr_equiv = usdt_profit * usdt_rate
        total_mvr_profit = mvr_profit + usd_mvr_equiv + usdt_mvr_equiv

        # Store data
        all_data[f'{period_name}_mvr_deposits'] = mvr_deposits
        all_data[f'{period_name}_mvr_withdrawals'] = mvr_withdrawals
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
        credit_summary = sheets.get_daily_credit_summary()
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
            sheets.save_all_reports(all_reports_data)
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
            admins = sheets.get_all_admins()
            for admin in admins:
                try:
                    await application.bot.send_message(
                        chat_id=admin['admin_id'],
                        text=report,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to send daily report to admin {admin['admin_id']}: {e}")
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
    current_details = sheets.get_payment_account_details(context.user_data['update_method'])

    if current_details and current_details.get('account_number'):
        current_text = f"📋 **Current {method_name} Account:**\n"
        current_text += f"Account Number: `{current_details['account_number']}`\n"
        if current_details.get('account_holder'):
            current_text += f"Account Holder: {current_details['account_holder']}\n"
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
            sheets.update_payment_account(method, account_number, None)

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
        sheets.update_payment_account(method, account_number, account_holder)

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

    # Get all user IDs from Google Sheets
    user_ids = sheets.get_all_user_ids()

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
    """Receive promotion percentage"""
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

        # Create promotion
        promotion_id = sheets.create_promotion(
            bonus_percentage=context.user_data['promo_percentage'],
            start_date=context.user_data['promo_start_date'],
            end_date=end_date_str,
            admin_id=update.effective_user.id
        )

        if promotion_id:
            await update.message.reply_text(
                f"✅ **Promotion Created!**\n\n"
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


# Quick Approval/Rejection Handlers
async def quick_approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve deposit from notification"""
    query = update.callback_query

    try:
        logger.info(f"Admin {query.from_user.id} clicked approve button")

        if not is_admin(query.from_user.id):
            await query.answer("❌ Not authorized", show_alert=True)
            return

        request_id = query.data.split('_')[-1]

        # Check if another admin is already processing this request
        if request_id in processing_requests:
            await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
            return

        # Lock this request to this admin
        processing_requests[request_id] = query.from_user.id
        await query.answer("Processing approval...")

        logger.info(f"Approving deposit request: {request_id}")

        deposit = sheets.get_deposit_request(request_id)

        if not deposit:
            await query.edit_message_text(
                f"{query.message.text}\n\n❌ _Request not found in database._",
                parse_mode='Markdown'
            )
            logger.error(f"Deposit request {request_id} not found")
            return

        # Update status
        sheets.update_deposit_status(request_id, 'Approved', query.from_user.id, 'Quick approved')
        logger.info(f"Deposit {request_id} status updated to Approved")

        # Add free spins based on deposit amount
        spins_message = ""
        try:
            amount_mvr = float(deposit['amount'])
            spins_added = await spin_bot.add_spins_from_deposit(
                user_id=deposit['user_id'],
                username=deposit['username'],
                amount_mvr=amount_mvr,
                pppoker_id=deposit.get('pppoker_id', '')
            )
            if spins_added > 0:
                spins_message = f"\n\n🎰 **FREE SPINS BONUS!**\n+{spins_added} free spins added!\nClick button below to play!"
            logger.info(f"Added {spins_added} spins to user {deposit['user_id']} for deposit of {amount_mvr} MVR")
        except Exception as e:
            logger.error(f"Error adding spins for deposit: {e}")

        # Check for promotion bonus
        promo_data = context.bot_data.get(f'promo_{request_id}')
        bonus_message = ""

        if promo_data:
            # Record promotion bonus
            success = sheets.record_promotion_bonus(
                user_id=promo_data['user_id'],
                pppoker_id=promo_data['pppoker_id'],
                promotion_id=promo_data['promotion_id'],
                deposit_request_id=request_id,
                deposit_amount=promo_data['deposit_amount'],
                bonus_amount=promo_data['bonus_amount']
            )

            if success:
                bonus_message = f"\n\n🎁 **PROMOTION BONUS APPLIED!**\n" \
                              f"Bonus: +{promo_data['bonus_amount']:.2f} {promo_data['currency']}\n" \
                              f"Total credited: {promo_data['deposit_amount'] + promo_data['bonus_amount']:.2f} {promo_data['currency']}"
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

        try:
            await context.bot.send_message(
                chat_id=deposit['user_id'],
                text=f"✅ **Your Deposit Has Been Approved!**\n\n"
                     f"**Request ID:** `{request_id}`\n"
                     f"**Amount:** {deposit['amount']} {'MVR' if deposit['payment_method'] != 'USDT' else 'USD'}\n"
                     f"**PPPoker ID:** {deposit['pppoker_id']}{bonus_message}{spins_message}\n\n"
                     f"Your chips have been added to your account. Happy gaming! 🎮",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            logger.info(f"User {deposit['user_id']} notified of approval")
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        # Remove buttons for ALL admins
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                    logger.info(f"Removed approval buttons for admin {admin_id} on deposit {request_id}")
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
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

    request_id = query.data.split('_')[-1]

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
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

    # Remove buttons for ALL admins when rejection starts
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
                logger.info(f"Removed buttons for admin {admin_id} - deposit {request_id} being rejected")
            except Exception as e:
                logger.error(f"Failed to remove buttons for admin {admin_id}: {e}")
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

    request_id = query.data.split('_')[-1]

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    withdrawal = sheets.get_withdrawal_request(request_id)

    if not withdrawal:
        await query.edit_message_text(f"{query.message.text}\n\n❌ _Request not found._", parse_mode='Markdown')
        if request_id in processing_requests:
            del processing_requests[request_id]
        return

    # Update status
    sheets.update_withdrawal_status(request_id, 'Completed', query.from_user.id, 'Quick approved')

    # Notify user with club link button
    club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"
    keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=withdrawal['user_id'],
            text=f"✅ **Your Withdrawal Has Been Processed!**\n\n"
                 f"**Request ID:** `{request_id}`\n"
                 f"**Amount:** {withdrawal['amount']} {'MVR' if withdrawal['payment_method'] != 'USDT' else 'USD'}\n"
                 f"**Method:** {withdrawal['payment_method']}\n"
                 f"**Account:** {withdrawal['account_number']}\n\n"
                 f"Your funds have been transferred. Please check your account. 💰",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except:
        pass

    # Remove buttons for ALL admins
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
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

    request_id = query.data.split('_')[-1]

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
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

    request_id = query.data.split('_')[-1]

    # Check if another admin is already processing this request
    if request_id in processing_requests:
        await query.answer("⛔ Another admin is already processing this request.", show_alert=True)
        return

    # Lock this request to this admin
    processing_requests[request_id] = query.from_user.id
    await query.answer()

    join_req = sheets.get_join_request(request_id)

    if not join_req:
        await query.edit_message_text(f"{query.message.text}\n\n❌ _Request not found._", parse_mode='Markdown')
        if request_id in processing_requests:
            del processing_requests[request_id]
        return

    # Update status
    sheets.update_join_request_status(request_id, 'Approved', query.from_user.id)

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=join_req['user_id'],
            text=f"✅ **Welcome to Billionaires Club!**\n\n"
                 f"**Request ID:** `{request_id}`\n"
                 f"**PPPoker ID:** {join_req['pppoker_id']}\n\n"
                 f"You've been approved to join the club. See you at the tables! 🎰",
            parse_mode='Markdown'
        )
    except:
        pass

    # Remove buttons for ALL admins
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

    request_id = query.data.split('_')[-1]

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
        request_id = '_'.join(parts[2:])  # "SEAT_87D3AC20"
    else:
        request_id = parts[2]

    if request_type == 'deposit':
        deposit = sheets.get_deposit_request(request_id)
        if deposit:
            sheets.update_deposit_status(request_id, 'Rejected', admin_id, reason)

            try:
                await context.bot.send_message(
                    chat_id=deposit['user_id'],
                    text=f"❌ **Your Deposit Has Been Rejected**\n\n"
                         f"**Request ID:** `{request_id}`\n"
                         f"**Reason:** {escape_markdown(reason)}\n\n"
                         f"Please contact support if you have any questions.",
                    parse_mode='Markdown'
                )
            except:
                pass

            await update.message.reply_text(f"✅ Deposit {request_id} rejected. User notified.")

    elif request_type == 'withdrawal':
        withdrawal = sheets.get_withdrawal_request(request_id)
        if withdrawal:
            sheets.update_withdrawal_status(request_id, 'Rejected', admin_id, reason)

            try:
                await context.bot.send_message(
                    chat_id=withdrawal['user_id'],
                    text=f"❌ **Your Withdrawal Has Been Rejected**\n\n"
                         f"**Request ID:** `{request_id}`\n"
                         f"**Reason:** {escape_markdown(reason)}\n\n"
                         f"Please contact support if you have any questions.",
                    parse_mode='Markdown'
                )
            except:
                pass

            await update.message.reply_text(f"✅ Withdrawal {request_id} rejected. User notified.")

    elif request_type == 'join':
        join_req = sheets.get_join_request(request_id)
        if join_req:
            sheets.update_join_request_status(request_id, 'Rejected', admin_id)

            try:
                await context.bot.send_message(
                    chat_id=join_req['user_id'],
                    text=f"❌ **Your Club Join Request Has Been Declined**\n\n"
                         f"**Request ID:** `{request_id}`\n"
                         f"**Reason:** {escape_markdown(reason)}\n\n"
                         f"Please contact support if you have any questions.",
                    parse_mode='Markdown'
                )
            except:
                pass

            await update.message.reply_text(f"✅ Join request {request_id} rejected. User notified.")

    elif request_type == 'seat':
        seat_req = sheets.get_seat_request(request_id)
        if seat_req:
            sheets.reject_seat_request(request_id, admin_id, reason)

            try:
                await context.bot.send_message(
                    chat_id=seat_req['user_id'],
                    text=f"❌ **Your Seat Request Has Been Rejected**\n\n"
                         f"**Request ID:** `{request_id}`\n"
                         f"**Reason:** {escape_markdown(reason)}\n\n"
                         f"Please contact support if you have any questions.",
                    parse_mode='Markdown'
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

    # Extract request_id: "approve_seat_SEAT_87D3AC20" -> "SEAT_87D3AC20"
    request_id = query.data.replace('approve_seat_', '')
    await query.answer()

    # Get seat request details
    try:
        seat_req = sheets.get_seat_request(request_id)
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

    # Approve in database
    success = sheets.approve_seat_request(request_id, query.from_user.id)

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
        payment_accounts = sheets.get_all_payment_accounts()

        # Build payment info message
        payment_info = "💳 **Payment Account Details:**\n\n"

        if 'BML' in payment_accounts and payment_accounts['BML']['account_number']:
            payment_info += f"**BML:**\n`{payment_accounts['BML']['account_number']}`\n"
            if payment_accounts['BML']['account_holder']:
                payment_info += f"Name: {payment_accounts['BML']['account_holder']}\n"
            payment_info += "\n"

        if 'MIB' in payment_accounts and payment_accounts['MIB']['account_number']:
            payment_info += f"**MIB:**\n`{payment_accounts['MIB']['account_number']}`\n"
            if payment_accounts['MIB']['account_holder']:
                payment_info += f"Name: {payment_accounts['MIB']['account_holder']}\n"
            payment_info += "\n"

        # Notify user with payment details
        try:
            await context.bot.send_message(
                chat_id=seat_req['user_id'],
                text=f"✅ **Seat Request Approved!**\n\n"
                     f"**Request ID:** `{request_id}`\n"
                     f"**Amount:** {seat_req['amount']} chips/MVR\n\n"
                     f"{payment_info}\n"
                     f"📸 **Please upload your payment slip/receipt now.**\n\n"
                     f"_You will receive a reminder in 1 minute if slip is not uploaded._",
                parse_mode='Markdown'
            )

            # Store data and add user to credit list
            seat_request_data[seat_req['user_id']] = {
                'request_id': request_id,
                'amount': seat_req['amount'],
                'pppoker_id': seat_req['pppoker_id']
            }

            # Add user to credit list
            sheets.add_user_credit(
                seat_req['user_id'],
                seat_req['username'],
                seat_req['pppoker_id'],
                seat_req['amount'],
                request_id
            )

            # Schedule first reminder (1 minute)
            job = context.job_queue.run_once(
                first_slip_reminder,
                when=60,  # 1 minute
                data=seat_req['user_id'],
                name=f"seat_reminder1_{seat_req['user_id']}"
            )
            seat_reminder_jobs[seat_req['user_id']] = job

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

    # Extract request_id: "reject_seat_SEAT_87D3AC20" -> "SEAT_87D3AC20"
    request_id = query.data.replace('reject_seat_', '')
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
        parse_mode='HTML'
    )


# Seat Slip Upload and Reminder Handlers
async def first_slip_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send first reminder after 1 minute if slip not uploaded"""
    user_id = context.job.data

    # Check if user still has active credit
    credit = sheets.get_user_credit(user_id)
    if not credit:
        # Already settled, cancel
        if user_id in seat_reminder_jobs:
            del seat_reminder_jobs[user_id]
        return

    # Check reminder count
    if credit['reminder_count'] >= 2:
        # Already sent final reminder, don't send again
        return

    # Increment reminder count
    sheets.increment_credit_reminder(user_id)

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
    credit = sheets.get_user_credit(user_id)
    if not credit:
        # Already settled
        if user_id in seat_reminder_jobs:
            del seat_reminder_jobs[user_id]
        return

    # Increment reminder count
    sheets.increment_credit_reminder(user_id)

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
                stored_holder_name = sheets.get_payment_account_holder(method)
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
                stored_account_number = sheets.get_payment_account(method)
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
        regular_admins = sheets.get_all_admins()
        all_admin_ids.extend([admin['admin_id'] for admin in regular_admins])
    except Exception as e:
        logger.error(f"Failed to get admin list: {e}")

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

    # Extract request_id: "settle_seat_SEAT_87D3AC20" -> "SEAT_87D3AC20"
    request_id = query.data.replace('settle_seat_', '')
    await query.answer()

    # Get seat request
    seat_req = sheets.get_seat_request(request_id)
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

    # Settle in database
    success = sheets.settle_seat_request(
        request_id,
        "Slip Upload",  # Payment method
        "OCR Verified",  # Transaction ID
        query.from_user.id
    )

    if success:
        # Clear user credit
        sheets.clear_user_credit(seat_req['user_id'])

        # Clean up tracking
        if seat_req['user_id'] in seat_request_data:
            del seat_request_data[seat_req['user_id']]
        if seat_req['user_id'] in seat_reminder_jobs:
            try:
                seat_reminder_jobs[seat_req['user_id']].schedule_removal()
                del seat_reminder_jobs[seat_req['user_id']]
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
                                f"**User:** @{seat_req['username']} (ID: {seat_req['user_id']})\n"
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
                chat_id=seat_req['user_id'],
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

    # Extract request_id: "reject_slip_SEAT_87D3AC20" -> "SEAT_87D3AC20"
    request_id = query.data.replace('reject_slip_', '')
    await query.answer()

    # Get seat request
    seat_req = sheets.get_seat_request(request_id)
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

    # Update message caption for ALL admins - remove buttons and show who rejected
    if f"slip_{request_id}" in notification_messages:
        for admin_id, message_id in notification_messages[f"slip_{request_id}"]:
            try:
                await context.bot.edit_message_caption(
                    chat_id=admin_id,
                    message_id=message_id,
                    caption=f"📸 **Payment Slip Verification**\n\n"
                            f"**Request ID:** `{request_id}`\n"
                            f"**User:** @{seat_req['username']} (ID: {seat_req['user_id']})\n"
                            f"**PPPoker ID:** {seat_req['pppoker_id']}\n"
                            f"**Amount:** {seat_req['amount']} chips/MVR\n\n"
                            f"❌ <b>REJECTED by {query.from_user.first_name}</b>\nUser notified to reupload.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                logger.error(f"Failed to update message for admin {admin_id}: {e}")
        del notification_messages[f"slip_{request_id}"]

    # Notify user to reupload or contact support
    try:
        await context.bot.send_message(
            chat_id=seat_req['user_id'],
            text=f"❌ **Payment Slip Rejected**\n\n"
                 f"**Request ID:** `{request_id}`\n\n"
                 f"Your payment slip could not be verified.\n\n"
                 f"Please upload a clearer image or contact Live Support.",
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
    if data.startswith("add_spins_amount_"):
        amount = data.replace("add_spins_amount_", "")
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
                InlineKeyboardButton("➕ 10 Spins", callback_data="add_spins_amount_10"),
                InlineKeyboardButton("➕ 25 Spins", callback_data="add_spins_amount_25")
            ],
            [
                InlineKeyboardButton("➕ 50 Spins", callback_data="add_spins_amount_50"),
                InlineKeyboardButton("➕ 100 Spins", callback_data="add_spins_amount_100")
            ],
            [
                InlineKeyboardButton("➕ 250 Spins", callback_data="add_spins_amount_250")
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
        await query.delete_message()
        # Create a fake update for freespins
        update.message = query.message
        await freespins_command(update, context)


# Approve spin callback handler
async def approve_spin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve spin button clicks - approves ALL pending rewards for a user"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.edit_message_text("❌ Admin access required!")
        return

    # Extract data from callback_data
    # Format: approve_user_<user_id>_<spin_id1>,<spin_id2>,<spin_id3>
    data_parts = query.data.replace("approve_user_", "").split("_", 1)
    target_user_id = data_parts[0]
    spin_ids = data_parts[1].split(",") if len(data_parts) > 1 else []

    # Approve all spin IDs for this user
    approved_count = 0
    total_chips = 0

    for spin_id in spin_ids:
        # Call approvespin for each spin_id
        context.args = [spin_id]
        update.message = query.message

        try:
            # Get spin data before approval
            spin_data = spin_bot.sheets.get_spin_by_id(spin_id)
            if spin_data and not spin_data.get('approved'):
                total_chips += int(spin_data.get('chips', 0))

                # Approve this spin
                await approvespin_command(update, context, spin_bot, is_admin)
                approved_count += 1
        except Exception as e:
            logger.error(f"Error approving spin {spin_id}: {e}")

    # Edit the original message to show it was processed
    try:
        await query.edit_message_text(
            f"✅ *APPROVED ALL REWARDS*\n\n"
            f"✅ Approved: {approved_count} rewards\n"
            f"💰 Total Chips: {total_chips}\n"
            f"👤 User ID: `{target_user_id}`\n\n"
            f"User has been notified\\!",
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        pass


# Deposit button callback handler (from no spins message)
async def deposit_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deposit button click from free spins no-spins message"""
    query = update.callback_query
    await query.answer()

    # Delete the current message
    try:
        await query.delete_message()
    except:
        pass

    # Create a fake update with message to trigger deposit_start
    update.message = query.message

    # Call deposit_start to properly start the conversation
    return await deposit_start(update, context)


# Play freespins button callback handler
async def play_freespins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle play freespins button click"""
    query = update.callback_query
    await query.answer()

    # Delete the original message
    try:
        await query.delete_message()
    except:
        pass

    # Create a fake update with message for freespins_command
    update.message = query.message

    # Call freespins command
    await freespins_command(update, context)


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
    elif text == "👤 User Mode":
        return await user_mode(update, context)
    elif text == "🔙 Back to Admin":
        return await start(update, context)
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
    # Create application
    application = Application.builder().token(TOKEN).build()

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

    # Test button handlers
    application.add_handler(CallbackQueryHandler(test_button_handler, pattern="^test_"))

    # Spin bot callback handlers
    application.add_handler(CallbackQueryHandler(spin_callback, pattern="^spin_"))
    application.add_handler(CallbackQueryHandler(spin_again_callback, pattern="^spin_again$"))
    application.add_handler(CallbackQueryHandler(spin_admin_callback, pattern="^spin_admin_"))
    application.add_handler(CallbackQueryHandler(approve_spin_callback, pattern="^approve_(spin_|user_)"))
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
    application.add_handler(CallbackQueryHandler(settle_seat_slip, pattern="^settle_seat_"))
    application.add_handler(CallbackQueryHandler(reject_seat_slip, pattern="^reject_slip_"))
    application.add_handler(CallbackQueryHandler(clear_user_credit_callback, pattern="^clear_credit_"))

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

    # Add conversation handlers
    application.add_handler(deposit_conv)
    application.add_handler(withdrawal_conv)
    application.add_handler(join_conv)
    application.add_handler(seat_conv)
    application.add_handler(support_conv)
    application.add_handler(update_account_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(promo_conv)

    # Photo handler for seat slip uploads
    application.add_handler(MessageHandler(filters.PHOTO, handle_seat_slip_upload))

    # Register admin handlers and share notification_messages dict
    admin_panel.register_admin_handlers(application, notification_messages)

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

    scheduler.start()
    logger.info("Scheduler started - Daily reports will be sent at midnight (00:00) Maldives time")

    # Log startup
    logger.info("Bot started successfully!")
    print("🤖 Billionaires PPPoker Bot is running...")
    print("📊 Daily reports scheduled for midnight")

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
