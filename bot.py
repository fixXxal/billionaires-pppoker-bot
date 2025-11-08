"""
Billionaires PPPoker Club Telegram Bot
Main bot file with all handlers and logic
"""

import os
import logging
import asyncio
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
from sheets_manager import SheetsManager
import admin_panel
import vision_api

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

# Conversation states
(DEPOSIT_METHOD, DEPOSIT_AMOUNT, DEPOSIT_PPPOKER_ID, DEPOSIT_ACCOUNT_NAME,
 DEPOSIT_PROOF, WITHDRAWAL_METHOD, WITHDRAWAL_AMOUNT, WITHDRAWAL_PPPOKER_ID,
 WITHDRAWAL_ACCOUNT_NAME, WITHDRAWAL_ACCOUNT_NUMBER, JOIN_PPPOKER_ID,
 ADMIN_APPROVAL_NOTES, SUPPORT_CHAT, ADMIN_REPLY_MESSAGE, UPDATE_ACCOUNT_METHOD, UPDATE_ACCOUNT_NUMBER, BROADCAST_MESSAGE) = range(17)

# Store for live support sessions
live_support_sessions: Dict[int, int] = {}  # user_id: admin_user_id
support_mode_users: set = set()  # Users currently in support mode
admin_reply_context: Dict[int, int] = {}  # admin_id: user_id (for reply context)
notification_messages: Dict[str, int] = {}  # request_id: message_id (for editing notification buttons)


# Helper Functions
def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID


async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send notification to admin"""
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=message)
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


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
            [KeyboardButton("📋 Admin Panel")],
            [KeyboardButton("📊 View Deposits"), KeyboardButton("💸 View Withdrawals")],
            [KeyboardButton("🎮 View Join Requests"), KeyboardButton("💳 Payment Accounts")],
            [KeyboardButton("👤 User Mode")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        welcome_message = f"""
🔐 <b>ADMIN PANEL</b>

Welcome back, Admin {user.first_name}! 👨‍💼

<b>Quick Access:</b>
📋 <b>Admin Panel</b> - Full admin dashboard
📊 <b>View Deposits</b> - Manage deposit requests
💸 <b>View Withdrawals</b> - Manage withdrawal requests
🎮 <b>View Join Requests</b> - Approve/reject club joins
💳 <b>Payment Accounts</b> - Update payment details
👤 <b>User Mode</b> - Switch to regular user view

Select an option to get started:
"""
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Regular user menu
        keyboard = [
            [KeyboardButton("💰 Deposit"), KeyboardButton("💸 Withdrawal")],
            [KeyboardButton("🎮 Join Club"), KeyboardButton("📊 My Info")],
            [KeyboardButton("💬 Live Support"), KeyboardButton("❓ Help")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        welcome_message = f"""
🎰 <b>Welcome to Billionaires PPPoker Club!</b> 🎰

Hello {user.first_name}! 👋

I'm here to help you with:
💰 <b>Deposits</b> - Add funds to your account
💸 <b>Withdrawals</b> - Cash out your winnings
🎮 <b>Club Access</b> - Join our exclusive club
💬 <b>Live Support</b> - Chat with our admin

Please select an option from the menu below:
"""
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')


# User Mode - Switch admin to user view
async def user_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch admin to regular user mode"""
    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("This command is for admins only.")
        return

    keyboard = [
        [KeyboardButton("💰 Deposit"), KeyboardButton("💸 Withdrawal")],
        [KeyboardButton("🎮 Join Club"), KeyboardButton("📊 My Info")],
        [KeyboardButton("💬 Live Support"), KeyboardButton("❓ Help")],
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

**💰 Deposit:**
1. Click "💰 Deposit"
2. Choose payment method (BML/MIB/USDT)
3. Enter amount and PPPoker ID
4. Enter your account name (as registered with bank)
5. Upload payment slip or transaction ID
6. Wait for admin approval

**💸 Withdrawal:**
1. Click "💸 Withdrawal"
2. Choose payment method
3. Enter amount and PPPoker ID
4. Provide account details (must match deposit name)
5. Wait for admin processing

**🎮 Join Club:**
1. Click "🎮 Join Club"
2. Enter your PPPoker ID
3. Wait for admin approval

**💬 Live Support:**
- Click "💬 Live Support" to chat directly with admin
- Your messages will be forwarded in real-time
- Type /endsupport to end the chat

Need help? Contact our support team! 🙂
"""

    # Add admin commands only if user is admin
    if is_admin(update.effective_user.id):
        help_text += """

🔐 **Admin Commands:**
- `/admin` - Access admin panel
- `/reply [user_id] [message]` - Reply to user in support
- `/update_bml` - Update BML account
- `/update_mib` - Update MIB account
- `/update_usdt` - Update USDT wallet
- `/broadcast` - Send message to all users
"""

    await update.message.reply_text(help_text, parse_mode='Markdown')


# Deposit Flow
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start deposit process"""
    user_data = sheets.get_user(update.effective_user.id)

    keyboard = [
        [InlineKeyboardButton("🏦 BML", callback_data="deposit_bml")],
        [InlineKeyboardButton("🏦 MIB", callback_data="deposit_mib")],
        [InlineKeyboardButton("💎 USDT (TRC20)", callback_data="deposit_usdt")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
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

    method_names = {'BML': 'Bank of Maldives', 'MIB': 'Maldives Islamic Bank', 'USDT': 'USDT (TRC20)'}

    # Ask for receipt/slip directly after showing account details
    if method == 'USDT':
        await query.edit_message_text(
            f"💰 <b>Deposit via {method_names[method]}</b>\n\n"
            f"<b>Wallet Address:</b>\n"
            f"<code>{account}</code> (tap to copy)\n\n"
            f"📝 Please send your <b>Transaction ID (TXID)</b> from the blockchain:",
            parse_mode='HTML'
        )
    else:
        # Build message with account holder name if available
        message = f"💰 <b>Deposit via {method_names[method]}</b>\n\n"
        message += f"<b>Account Number:</b>\n<code>{account}</code> (tap to copy)\n\n"

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

📸 <i>Payment slip attached below</i>{validation_warnings}"""

    # Create approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_deposit_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quick_reject_deposit_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Send notification message with HTML for better formatting
        notification_msg = await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=admin_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        # Store notification message_id for later editing when admin approves/rejects
        notification_messages[request_id] = notification_msg.message_id
        logger.info(f"Deposit notification sent to admin for {request_id}")

        # Forward proof to admin if it's a photo/document
        photo_file_id = context.user_data.get('photo_file_id')
        document_file_id = context.user_data.get('document_file_id')

        if photo_file_id:
            await context.bot.send_photo(
                chat_id=ADMIN_USER_ID,
                photo=photo_file_id,
                caption=f"📸 Deposit Proof for {request_id}"
            )
            logger.info(f"Deposit photo sent to admin for {request_id}")
        elif document_file_id:
            await context.bot.send_document(
                chat_id=ADMIN_USER_ID,
                document=document_file_id,
                caption=f"📎 Deposit Proof for {request_id}"
            )
            logger.info(f"Deposit document sent to admin for {request_id}")
    except Exception as e:
        logger.error(f"Failed to send deposit notification to admin: {e}")
        logger.error(f"Admin ID: {ADMIN_USER_ID}")
        await update.message.reply_text(
            f"⚠️ Request saved but failed to notify admin. Error logged."
        )

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

    keyboard = [
        [InlineKeyboardButton("🏦 BML", callback_data="withdrawal_bml")],
        [InlineKeyboardButton("🏦 MIB", callback_data="withdrawal_mib")],
        [InlineKeyboardButton("💎 USDT (TRC20)", callback_data="withdrawal_usdt")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
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

    method_names = {'BML': 'Bank of Maldives', 'MIB': 'Maldives Islamic Bank', 'USDT': 'USDT (TRC20)'}

    await query.edit_message_text(
        f"💸 <b>Withdrawal via {method_names[method]}</b>\n\n"
        f"Please enter the amount you want to withdraw (in MVR{' or USD' if method == 'USDT' else ''}):",
        parse_mode='HTML'
    )

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
<b>PPPoker ID:</b> <code>{pppoker_id}</code> (tap to copy)
<b>Account Name:</b> {account_name}
<b>Account Number:</b> <code>{account_number}</code> (tap to copy)
"""

    # Create approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_withdrawal_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quick_reject_withdrawal_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    notification_msg = await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=admin_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    # Store notification message_id for later editing
    notification_messages[request_id] = notification_msg.message_id

    # Clear user data
    context.user_data.clear()

    return ConversationHandler.END


# Join Club Flow
async def join_club_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start join club process"""
    await update.message.reply_text(
        "🎮 **Join Billionaires Club**\n\n"
        "To join our exclusive PPPoker club, please enter your **PPPoker ID**:",
        parse_mode='Markdown'
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
<b>PPPoker ID:</b> <code>{pppoker_id}</code> (tap to copy)
"""

    # Create approval buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"quick_approve_join_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"quick_reject_join_{request_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    notification_msg = await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=admin_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    # Store notification message_id for later editing
    notification_messages[request_id] = notification_msg.message_id

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


# Live Support
async def live_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start live support session"""
    user = update.effective_user

    if user.id in support_mode_users:
        # Show End Support button
        keyboard = [[InlineKeyboardButton("❌ End Support", callback_data="user_end_support")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "💬 You're already in a support session!\n\n"
            "Type your message and it will be sent to our admin.\n"
            "Click the button below to end the session.",
            reply_markup=reply_markup
        )
        return SUPPORT_CHAT

    support_mode_users.add(user.id)
    live_support_sessions[user.id] = ADMIN_USER_ID

    # Show End Support button
    keyboard = [[InlineKeyboardButton("❌ End Support", callback_data="user_end_support")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💬 **Live Support Session Started**\n\n"
        "You're now connected to our admin. Type your message below.\n\n"
        "Click the button below when you're done.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # Notify admin
    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=f"💬 **New Support Session Started**\n\n"
             f"User: {user.first_name} {user.last_name or ''} (@{user.username or 'No username'})\n"
             f"User ID: `{user.id}`\n\n"
             f"Waiting for user's message...",
        parse_mode='Markdown'
    )

    return SUPPORT_CHAT


async def live_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle live support messages"""
    user = update.effective_user

    if user.id not in support_mode_users:
        return ConversationHandler.END

    # Forward message to admin with easy reply buttons
    message_text = f"💬 **Message from {user.first_name}** (@{user.username or 'No username'})\n\n_{update.message.text}_"

    # Create buttons for admin
    keyboard = [
        [
            InlineKeyboardButton("💬 Reply", callback_data=f"support_reply_{user.id}"),
            InlineKeyboardButton("❌ End Chat", callback_data=f"support_end_{user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=ADMIN_USER_ID,
        text=message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    await update.message.reply_text("✅ Message sent to admin.")

    return SUPPORT_CHAT


async def end_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End live support session"""
    user = update.effective_user

    if user.id in support_mode_users:
        support_mode_users.remove(user.id)
        if user.id in live_support_sessions:
            del live_support_sessions[user.id]

        await update.message.reply_text("✅ Support session ended. Thank you!")

        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"💬 Support session ended with {user.first_name} (@{user.username or 'No username'})"
        )
    else:
        await update.message.reply_text("You're not in a support session.")

    return ConversationHandler.END


async def admin_reply_button_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin clicking Reply button"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    # Extract user_id from callback data
    user_id = int(query.data.split('_')[-1])

    # Check if user still in support session
    if user_id not in support_mode_users:
        await query.edit_message_text(
            f"{query.message.text}\n\n⚠️ _User has ended the support session._",
            parse_mode='Markdown'
        )
        return

    # Store user_id for next message from admin
    admin_reply_context[query.from_user.id] = user_id

    await query.edit_message_text(
        f"{query.message.text}\n\n✏️ **Type your reply below:**",
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
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 **Admin:**\n\n{escape_markdown(message)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        await update.message.reply_text("✅ Message sent!")

        # Clear context
        del admin_reply_context[admin_id]

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send: {e}")
        if admin_id in admin_reply_context:
            del admin_reply_context[admin_id]


async def admin_end_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin clicking End Chat button"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])

    if user_id in support_mode_users:
        support_mode_users.remove(user_id)
        if user_id in live_support_sessions:
            del live_support_sessions[user_id]

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="💬 **Support session ended by admin.**\n\nThank you for contacting us!"
            )
        except:
            pass

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

        await query.edit_message_text(
            "✅ **Support session ended.**\n\nThank you! Feel free to start a new session anytime."
        )

        # Notify admin
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"💬 **Support session ended**\n\n"
                 f"User: {user.first_name} (@{user.username or 'No username'}) ended the chat."
        )
    else:
        await query.edit_message_text("You're not in a support session.")

    return ConversationHandler.END


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


# Quick Approval/Rejection Handlers
async def quick_approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve deposit from notification"""
    query = update.callback_query
    await query.answer("Processing approval...")

    try:
        logger.info(f"Admin {query.from_user.id} clicked approve button")

        if not is_admin(query.from_user.id):
            await query.answer("❌ Not authorized", show_alert=True)
            return

        request_id = query.data.split('_')[-1]
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

        # Notify user with club link button
        club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"
        keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=deposit['user_id'],
                text=f"✅ **Your Deposit Has Been Approved!**\n\n"
                     f"**Request ID:** `{request_id}`\n"
                     f"**Amount:** {deposit['amount']} {'MVR' if deposit['payment_method'] != 'USDT' else 'USD'}\n"
                     f"**PPPoker ID:** {deposit['pppoker_id']}\n\n"
                     f"Your chips have been added to your account. Happy gaming! 🎮",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            logger.info(f"User {deposit['user_id']} notified of approval")
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        # Edit message and remove buttons
        try:
            await query.message.edit_text(
                f"{query.message.text}\n\n✅ **APPROVED** by admin\n\n_User has been notified._",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception as e:
            # If edit fails, try without appending original text
            try:
                await query.message.edit_text(
                    f"✅ Deposit {request_id} **APPROVED** by admin\n\n_User has been notified._",
                    reply_markup=InlineKeyboardMarkup([])
                )
            except:
                logger.error(f"Failed to edit message: {e}")

    except Exception as e:
        logger.error(f"Error in quick_approve_deposit: {e}")
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)


async def quick_reject_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick reject deposit - ask for reason"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    request_id = query.data.split('_')[-1]

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_deposit_{request_id}"

    await query.edit_message_text(
        f"❌ Rejecting Deposit Request {request_id}\n\n"
        f"✏️ Please type the rejection reason:",
        reply_markup=None
    )


async def quick_approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve withdrawal from notification"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    request_id = query.data.split('_')[-1]
    withdrawal = sheets.get_withdrawal_request(request_id)

    if not withdrawal:
        await query.edit_message_text(f"{query.message.text}\n\n❌ _Request not found._", parse_mode='Markdown')
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

    # Edit message and remove buttons
    try:
        await query.message.edit_text(
            f"{query.message.text}\n\n✅ **APPROVED** by admin",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([])
        )
    except Exception as e:
        # If edit fails, try without appending original text
        try:
            await query.message.edit_text(
                f"✅ Withdrawal {request_id} **APPROVED** by admin",
                reply_markup=InlineKeyboardMarkup([])
            )
        except:
            pass


async def quick_reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick reject withdrawal - ask for reason"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    request_id = query.data.split('_')[-1]

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_withdrawal_{request_id}"

    await query.edit_message_text(
        f"❌ Rejecting Withdrawal Request {request_id}\n\n"
        f"✏️ Please type the rejection reason:",
        reply_markup=None
    )


async def quick_approve_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick approve join request from notification"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    request_id = query.data.split('_')[-1]
    join_req = sheets.get_join_request(request_id)

    if not join_req:
        await query.edit_message_text(f"{query.message.text}\n\n❌ _Request not found._", parse_mode='Markdown')
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

    # Edit message and remove buttons
    try:
        await query.message.edit_text(
            f"{query.message.text}\n\n✅ **APPROVED** by admin",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([])
        )
    except Exception as e:
        # If edit fails, try without appending original text
        try:
            await query.message.edit_text(
                f"✅ Join Request {request_id} **APPROVED** by admin",
                reply_markup=InlineKeyboardMarkup([])
            )
        except:
            pass


async def quick_reject_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick reject join request - ask for reason"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    request_id = query.data.split('_')[-1]

    # Store request_id for rejection reason
    admin_reply_context[query.from_user.id] = f"reject_join_{request_id}"

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
    request_type = parts[1]  # deposit, withdrawal, or join
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

    # Clear context
    del admin_reply_context[admin_id]


# Message router
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route text messages to appropriate handlers"""
    user_id = update.effective_user.id
    text = update.message.text

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
    elif text == "📊 My Info":
        return await my_info(update, context)
    elif text == "💬 Live Support":
        return await live_support_start(update, context)
    elif text == "❓ Help":
        return await help_command(update, context)
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

    # Test button handlers
    application.add_handler(CallbackQueryHandler(test_button_handler, pattern="^test_"))

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

    # Deposit conversation handler
    deposit_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💰 Deposit$"), deposit_start)
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

    # Add conversation handlers
    application.add_handler(deposit_conv)
    application.add_handler(withdrawal_conv)
    application.add_handler(join_conv)
    application.add_handler(support_conv)
    application.add_handler(update_account_conv)
    application.add_handler(broadcast_conv)

    # Register admin handlers and share notification_messages dict
    admin_panel.register_admin_handlers(application, notification_messages)

    # Add general text handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Log startup
    logger.info("Bot started successfully!")
    print("🤖 Billionaires PPPoker Bot is running...")

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
