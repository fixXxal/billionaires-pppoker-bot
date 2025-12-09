"""
Admin Panel for Billionaires PPPoker Bot
Handles all admin commands and approval workflows
Updated: 2025-12-03 - Added spin tracking integration
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
# DJANGO MIGRATION: Using SheetsCompatAPI for backward compatibility
from sheets_compat import SheetsCompatAPI
from dotenv import load_dotenv
import spin_bot as spin_bot_module

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')
DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://localhost:8000/api')

api = SheetsCompatAPI(DJANGO_API_URL)

# Conversation states
ADMIN_NOTES, UPDATE_ACCOUNT_NUMBER = range(2)
# Investment conversation states
INVESTMENT_TELEGRAM_ID, INVESTMENT_AMOUNT, INVESTMENT_NOTES = range(2, 5)
RETURN_SELECT_USER, RETURN_AMOUNT = range(5, 7)
# Exchange rate conversation states
SET_USD_RATE, SET_USDT_RATE = range(7, 9)

# Notification messages storage (will be set by bot.py)
notification_messages = {}

# Spin bot instance (will be set by bot.py)
spin_bot = None


def escape_markdown(text: str) -> str:
    """Escape special markdown characters in user-provided text"""
    if not text:
        return text
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def is_admin(user_id: int) -> bool:
    """Check if user is admin (super admin or regular admin)"""
    return api.is_admin(user_id)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have admin access.")
        return

    # Get current counter status
    counter_status = api.get_counter_status()
    is_open = counter_status.get('is_open', True)  # Django API returns {'is_open': True/False}
    counter_button_text = "🔴 Close Counter" if is_open else "🟢 Open Counter"
    counter_callback = "admin_close_counter" if is_open else "admin_open_counter"

    keyboard = [
        [InlineKeyboardButton("💰 Pending Deposits", callback_data="admin_view_deposits")],
        [InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_view_withdrawals")],
        [InlineKeyboardButton("💵 Pending Cashback", callback_data="admin_view_cashback")],
        [InlineKeyboardButton("💳 Active Credits", callback_data="admin_view_credits")],
        [InlineKeyboardButton("🎮 Pending Join Requests", callback_data="admin_view_joins")],
        [InlineKeyboardButton("🎁 Promotions", callback_data="admin_view_promotions")],
        [InlineKeyboardButton("🏦 Payment Accounts", callback_data="admin_view_accounts")],
        [InlineKeyboardButton("💱 Exchange Rates", callback_data="admin_exchange_rates")],
        [InlineKeyboardButton("💎 50/50 Investments", callback_data="admin_investments")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton(counter_button_text, callback_data=counter_callback)],
        [InlineKeyboardButton("📊 Counter Status", callback_data="admin_counter_status")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🔐 **Admin Panel**\n\nSelect an option:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def admin_view_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending deposits"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        # Called from text message
        query = update
        edit_func = update.message.reply_text

    # Get pending deposits from Django API
    pending_deposits = api.get_pending_deposits()

    if not pending_deposits:
        await edit_func(
            "✅ No pending deposits.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="admin_back")
            ]])
        )
        return

    # Show first pending deposit
    context.user_data['pending_deposits'] = pending_deposits
    context.user_data['current_deposit_index'] = 0

    await show_deposit_details(query, context, pending_deposits[0])


async def show_deposit_details(query, context, deposit):
    """Display deposit details with approval buttons"""
    # Handle both dict (Django API) and list (legacy Sheets) format
    if isinstance(deposit, dict):
        request_id = deposit.get('id')
        # Get user details from nested user_details object
        user_details = deposit.get('user_details', {})
        user_id = user_details.get('telegram_id')
        username = user_details.get('username', 'No username')
        pppoker_id = deposit.get('pppoker_id')
        amount = deposit.get('amount')
        method = deposit.get('method')
        account_name = deposit.get('account_name')
        transaction_ref = deposit.get('proof_image_path', 'N/A')
    else:
        # Legacy array format
        request_id = deposit[0]
        user_id = deposit[1]
        username = deposit[2]
        pppoker_id = deposit[3]
        amount = deposit[4]
        method = deposit[5]
        account_name = deposit[6]
        transaction_ref = deposit[7]

    current_index = context.user_data.get('current_deposit_index', 0)
    total = len(context.user_data.get('pending_deposits', []))

    # Currency
    currency = 'MVR' if method != 'USDT' else 'USD'

    # Clean, organized format
    message_text = f"""💰 <b>{method} DEPOSIT</b> — Request {current_index + 1}/{total}

<b>📋 REQUEST INFO</b>
ID: <code>{request_id}</code>

<b>👤 USER</b>
Username: @{username if username else 'No username'}
User ID: <code>{user_id}</code>

<b>🏦 TRANSACTION</b>
Reference: <code>{transaction_ref}</code>
Amount: <b>{currency} {amount}</b>
From: {account_name}

<b>🎮 PPPOKER</b>
Player ID: <code>{pppoker_id}</code>
"""

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"deposit_approve_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"deposit_reject_{request_id}")
        ]
    ]

    # Add navigation buttons
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="deposit_prev"))
    if current_index < total - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="deposit_next"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("« Back to Panel", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Handle both callback query and regular message
    if hasattr(query, 'edit_message_text'):
        # It's a CallbackQuery
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # It's an Update object, send new message
        await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML')


async def deposit_navigate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate between deposits"""
    query = update.callback_query
    await query.answer()

    direction = query.data.split('_')[1]
    current_index = context.user_data.get('current_deposit_index', 0)
    pending_deposits = context.user_data.get('pending_deposits', [])

    if direction == 'next' and current_index < len(pending_deposits) - 1:
        current_index += 1
    elif direction == 'prev' and current_index > 0:
        current_index -= 1

    context.user_data['current_deposit_index'] = current_index
    await show_deposit_details(query, context, pending_deposits[current_index])


async def deposit_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve deposit request"""
    query = update.callback_query
    await query.answer("Processing approval...")

    try:
        request_id = int(query.data.split('_')[-1])
        admin_id = query.from_user.id

        # Clear any cached state first
        context.user_data.clear()

        logger.info(f"Admin {admin_id} approving deposit {request_id}")

        deposit = api.get_deposit_request(request_id)
        if not deposit:
            logger.error(f"Deposit {request_id} not found")
            await query.edit_message_text(
                text="❌ Deposit request not found.",
                reply_markup=InlineKeyboardMarkup([])
            )
            return ConversationHandler.END

        logger.info(f"Found deposit: {deposit}")

        # Update status using Django API
        result = api.approve_deposit(request_id, admin_id)
        logger.info(f"Approve result: {result}")

        # Notify user with club link button
        user_details = deposit.get('user_details', {})
        user_id = user_details.get('telegram_id') or deposit.get('user')
        username = user_details.get('username', 'User')
        # All deposits are stored in MVR (USDT/USD are converted)
        currency = 'MVR'

        # Add free spins based on deposit amount
        spins_message = ""
        spins_added = 0

        if spin_bot:
            try:
                # Amount is already stored in MVR (USDT/USD are converted at deposit time)
                amount_mvr = float(deposit['amount'])
                method = deposit.get('method', 'BML')

                logger.info(f"🎰 [ADMIN PANEL] SPIN CALCULATION START - User: {user_id}, Amount: {amount_mvr} MVR, Method: {method}")
                logger.info(f"🎲 [ADMIN PANEL] Calling add_spins_from_deposit with amount_mvr={amount_mvr}, user={user_id}")
                spins_added = await spin_bot.add_spins_from_deposit(
                    user_id=user_id,
                    username=username,
                    amount_mvr=amount_mvr,
                    pppoker_id=deposit.get('pppoker_id', '')
                )
                logger.info(f"✅ [ADMIN PANEL] SPIN RESULT: {spins_added} spins added to user {user_id}")

                if spins_added > 0:
                    spins_message = f"\n\n🎰 <b>FREE SPINS BONUS!</b>\n+{spins_added} free spins added!"
                    logger.info(f"🎉 [ADMIN PANEL] User will receive spin message: {spins_added} spins")
                else:
                    logger.info(f"ℹ️ [ADMIN PANEL] No spins added (amount {amount_mvr} MVR below minimum threshold)")
            except Exception as e:
                logger.error(f"❌ [ADMIN PANEL] CRITICAL ERROR adding spins for deposit: {e}")
                logger.error(f"   User ID: {user_id}, Username: {username}, Amount: {amount}, Method: {method}")
                import traceback
                traceback.print_exc()
        else:
            logger.warning(f"⚠️ [ADMIN PANEL] spin_bot is None! Cannot add spins for deposit approval.")

        user_message = (
            f"🎉 <b>DEPOSIT APPROVED!</b> 🎉\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ Your deposit has been successfully approved!\n\n"
            f"💰 <b>Amount:</b> {deposit['amount']} {currency}\n"
            f"🎮 <b>PPPoker ID:</b> <code>{deposit.get('pppoker_id', 'N/A')}</code>\n"
            f"📋 <b>Request ID:</b> <code>{request_id}</code>\n"
            f"{spins_message}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"💎 Your chips have been added to your account!\n"
            f"🎲 Ready to play? Click the button below!\n\n"
            f"Good luck and happy gaming! 🍀"
        )

        club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"
        keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]

        # Add "Play Spins" button if spins were added
        if spins_added > 0:
            keyboard.append([InlineKeyboardButton("🎲 Play Free Spins", callback_data="play_freespins")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML', reply_markup=reply_markup)
            logger.info(f"User {user_id} notified of approval")
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")

        # Edit original notification message to remove buttons for ALL admins
        if request_id in notification_messages:
            for admin_id_msg, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id_msg,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    logger.error(f"Failed to remove buttons for admin {admin_id_msg}: {e}")
            # Clean up the stored message_ids
            del notification_messages[request_id]

        # Check remaining pending deposits
        try:
            pending_deposits = api.get_pending_deposits()
            remaining_msg = f"\n📊 {len(pending_deposits)} pending deposit(s) remaining." if pending_deposits else "\n✅ No more pending deposits."
        except Exception as e:
            logger.error(f"Failed to get pending deposits: {e}")
            remaining_msg = ""

        # Edit message and explicitly remove keyboard
        try:
            await query.message.edit_text(
                text=f"✅ Deposit {request_id} has been approved.\n"
                f"User has been notified."
                f"{remaining_msg}",
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception as e:
            # If edit fails, try deleting and sending new message
            logger.error(f"Failed to edit message: {e}")
            try:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"✅ Deposit {request_id} has been approved.\n"
                    f"User has been notified."
                    f"{remaining_msg}"
                )
            except Exception as e2:
                logger.error(f"Failed to send new message: {e2}")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in deposit_approve: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await query.edit_message_text(
            text=f"❌ Error: {str(e)}",
            reply_markup=InlineKeyboardMarkup([])
        )
        return ConversationHandler.END


async def deposit_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject deposit request"""
    query = update.callback_query
    await query.answer()

    request_id = int(query.data.split('_')[-1])
    context.user_data['pending_action'] = ('deposit', 'reject', request_id)

    await query.edit_message_text(
        f"❌ Rejecting deposit {request_id}\n\n"
        "Please enter rejection reason:",
        reply_markup=None
    )

    return ADMIN_NOTES


async def admin_notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process rejection reason"""
    reason = update.message.text.strip()

    action_type, action, request_id = context.user_data['pending_action']
    admin_id = update.effective_user.id

    # This function now only handles rejections (approvals are instant)
    if action_type == 'deposit':
        try:
            logger.info(f"Admin {admin_id} rejecting deposit {request_id} with reason: {reason}")

            deposit = api.get_deposit_request(request_id)
            if not deposit:
                logger.error(f"Deposit {request_id} not found")
                await update.message.reply_text("❌ Deposit request not found.")
                return ConversationHandler.END

            logger.info(f"Found deposit: {deposit}")

            # Reject using Django API
            result = api.reject_deposit(request_id, admin_id, reason)
            logger.info(f"Reject result: {result}")

            # Notify user
            user_details = deposit.get('user_details', {})
            user_id = user_details.get('telegram_id') or deposit.get('user')
            user_message = f"""
❌ **Your Deposit Has Been Rejected**

**Request ID:** `{request_id}`
**Reason:** {reason or 'No reason provided'}

Please contact support if you have any questions.
"""

            try:
                await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
                logger.info(f"User {user_id} notified of rejection")
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
                await update.message.reply_text(f"⚠️ Could not notify user: {e}")

            # Edit original notification message to remove buttons for ALL admins
            if request_id in notification_messages:
                for admin_id_msg, message_id in notification_messages[request_id]:
                    try:
                        await context.bot.edit_message_reply_markup(
                            chat_id=admin_id_msg,
                            message_id=message_id,
                            reply_markup=InlineKeyboardMarkup([])
                        )
                    except Exception as e:
                        logger.error(f"Failed to remove buttons for admin {admin_id_msg}: {e}")
                del notification_messages[request_id]

            # Check remaining pending deposits
            try:
                pending_deposits = api.get_pending_deposits()
                remaining_msg = f"\n📊 {len(pending_deposits)} pending deposit(s) remaining." if pending_deposits else "\n✅ No more pending deposits."
            except Exception as e:
                logger.error(f"Failed to get pending deposits: {e}")
                remaining_msg = ""

            await update.message.reply_text(
                f"✅ Deposit {request_id} has been rejected.\n"
                f"User has been notified."
                f"{remaining_msg}"
            )

        except Exception as e:
            logger.error(f"Error rejecting deposit: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return ConversationHandler.END

    elif action_type == 'withdrawal':
        try:
            logger.info(f"Admin {admin_id} rejecting withdrawal {request_id} with reason: {reason}")

            withdrawal = api.get_withdrawal_request(request_id)
            if not withdrawal:
                logger.error(f"Withdrawal {request_id} not found")
                await update.message.reply_text("❌ Withdrawal request not found.")
                return ConversationHandler.END

            logger.info(f"Found withdrawal: {withdrawal}")

            # Reject using Django API
            result = api.reject_withdrawal(request_id, admin_id, reason)
            logger.info(f"Reject result: {result}")

            # Notify user
            user_details = withdrawal.get('user_details', {})
            user_id = user_details.get('telegram_id') or withdrawal.get('user')
            user_message = f"""
❌ **Your Withdrawal Has Been Rejected**

**Request ID:** `{request_id}`
**Reason:** {reason or 'No reason provided'}

Please contact support if you have any questions.
"""

            try:
                await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
                logger.info(f"User {user_id} notified of rejection")
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
                await update.message.reply_text(f"⚠️ Could not notify user: {e}")

            # Edit original notification message to remove buttons for ALL admins
            if request_id in notification_messages:
                for admin_id_msg, message_id in notification_messages[request_id]:
                    try:
                        await context.bot.edit_message_reply_markup(
                            chat_id=admin_id_msg,
                            message_id=message_id,
                            reply_markup=InlineKeyboardMarkup([])
                        )
                    except Exception as e:
                        logger.error(f"Failed to remove buttons for admin {admin_id_msg}: {e}")
                del notification_messages[request_id]

            # Check remaining pending withdrawals
            try:
                pending_withdrawals = api.get_pending_withdrawals()
                remaining_msg = f"\n📊 {len(pending_withdrawals)} pending withdrawal(s) remaining." if pending_withdrawals else "\n✅ No more pending withdrawals."
            except Exception as e:
                logger.error(f"Failed to get pending withdrawals: {e}")
                remaining_msg = ""

            await update.message.reply_text(
                f"✅ Withdrawal {request_id} has been rejected.\n"
                f"User has been notified."
                f"{remaining_msg}"
            )

        except Exception as e:
            logger.error(f"Error rejecting withdrawal: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(f"❌ Error: {str(e)}")
            return ConversationHandler.END

    elif action_type == 'join':
        join_req = api.get_join_request(request_id)
        if not join_req:
            await update.message.reply_text("❌ Join request not found.")
            return ConversationHandler.END

        # Update status to rejected
        api.update_join_request_status(request_id, 'Rejected', admin_id)

        # Notify user
        user_details = join_req.get('user_details', {})
        user_id = user_details.get('telegram_id') or join_req.get('user_id') or join_req.get('user')
        user_message = (
            f"❌ <b>Your Club Join Request Has Been Declined</b>\n\n"
            f"<b>Request ID:</b> <code>{request_id}</code>\n"
            f"<b>Reason:</b> {reason or 'No reason provided'}\n\n"
            f"Please contact support if you have any questions."
        )

        try:
            await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
            logger.info(f"✅ User {user_id} notified about join request {request_id} rejection")
        except Exception as e:
            logger.error(f"❌ Failed to notify user {user_id} about join rejection: {e}")
            await update.message.reply_text(f"⚠️ Could not notify user: {e}")

        # Edit original notification message to remove buttons for ALL admins
        if request_id in notification_messages:
            for admin_id, message_id in notification_messages[request_id]:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=admin_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup([])
                    )
                except Exception as e:
                    pass
            del notification_messages[request_id]

        # Check remaining pending join requests
        all_join_requests = api.join_requests_sheet.get_all_values()[1:]
        pending_join_requests = [j for j in all_join_requests if len(j) > 5 and j[5] == 'Pending']

        remaining_msg = f"\n📊 {len(pending_join_requests)} pending join request(s) remaining." if pending_join_requests else "\n✅ No more pending join requests."

        await update.message.reply_text(
            f"✅ Join request {request_id} has been rejected.\n"
            f"User has been notified."
            f"{remaining_msg}"
        )

    context.user_data.clear()
    return ConversationHandler.END


# Similar functions for withdrawals
async def admin_view_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending withdrawals"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        # Called from text message
        query = update
        edit_func = update.message.reply_text

    # Get pending withdrawals from Django API
    pending_withdrawals = api.get_pending_withdrawals()

    if not pending_withdrawals:
        await edit_func(
            "✅ No pending withdrawals.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="admin_back")
            ]])
        )
        return

    context.user_data['pending_withdrawals'] = pending_withdrawals
    context.user_data['current_withdrawal_index'] = 0

    await show_withdrawal_details(query, context, pending_withdrawals[0])


async def show_withdrawal_details(query, context, withdrawal):
    """Display withdrawal details with approval buttons"""
    # Handle both dict (Django API) and list (legacy Sheets) format
    if isinstance(withdrawal, dict):
        request_id = withdrawal.get('id')
        # Get user details from nested user_details object
        user_details = withdrawal.get('user_details', {})
        user_id = user_details.get('telegram_id')
        username = user_details.get('username', 'No username')
        pppoker_id = withdrawal.get('pppoker_id')
        amount = withdrawal.get('amount')
        method = withdrawal.get('method')
        account_name = withdrawal.get('account_name')
        account_number = withdrawal.get('account_number')
    else:
        request_id = withdrawal[0]
        user_id = withdrawal[1]
        username = withdrawal[2]
        pppoker_id = withdrawal[3]
        amount = withdrawal[4]
        method = withdrawal[5]
        account_name = withdrawal[6]
        account_number = withdrawal[7]

    current_index = context.user_data.get('current_withdrawal_index', 0)
    total = len(context.user_data.get('pending_withdrawals', []))

    message_text = f"""
💸 <b>WITHDRAWAL REQUEST</b> ({current_index + 1}/{total})

<b>Request ID:</b> <code>{request_id}</code>
<b>User ID:</b> <code>{user_id}</code>
<b>Username:</b> @{username if username else 'No username'}
<b>PPPoker ID:</b> <a href='#'>(tap to copy)</a>
<code>{pppoker_id}</code>
<b>Amount:</b> {amount} {'MVR' if method != 'USDT' else 'USD'}
<b>Method:</b> {method}
<b>Account Name:</b> {account_name}
<b>Account Number:</b> <a href='#'>(tap to copy)</a>
<code>{account_number}</code>
"""

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"withdrawal_approve_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"withdrawal_reject_{request_id}")
        ]
    ]

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="withdrawal_prev"))
    if current_index < total - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="withdrawal_next"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("« Back to Panel", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Handle both callback query and regular message
    if hasattr(query, 'edit_message_text'):
        # It's a CallbackQuery
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # It's an Update object, send new message
        await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML')


async def withdrawal_navigate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate between withdrawals"""
    query = update.callback_query
    await query.answer()

    direction = query.data.split('_')[1]
    current_index = context.user_data.get('current_withdrawal_index', 0)
    pending_withdrawals = context.user_data.get('pending_withdrawals', [])

    if direction == 'next' and current_index < len(pending_withdrawals) - 1:
        current_index += 1
    elif direction == 'prev' and current_index > 0:
        current_index -= 1

    context.user_data['current_withdrawal_index'] = current_index
    await show_withdrawal_details(query, context, pending_withdrawals[current_index])


async def withdrawal_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve withdrawal request"""
    query = update.callback_query
    await query.answer("Processing approval...")

    request_id = int(query.data.split('_')[-1])
    admin_id = query.from_user.id

    # Clear any cached state first
    context.user_data.clear()

    withdrawal = api.get_withdrawal_request(request_id)
    if not withdrawal:
        await query.edit_message_text(
            text="❌ Withdrawal request not found.",
            reply_markup=InlineKeyboardMarkup([])
        )
        return ConversationHandler.END

    # Update status
    api.update_withdrawal_status(request_id, 'Completed', admin_id, 'Approved via admin panel')

    # Notify user with club link button
    user_details = withdrawal.get('user_details', {})
    user_id = user_details.get('telegram_id') or withdrawal.get('user')
    currency = 'MVR' if withdrawal.get('method') != 'USDT' else 'USD'
    user_message = f"✅ <b>Withdrawal completed!</b>\n\n💸 {withdrawal['amount']} {currency} sent to your account"

    club_link = "https://pppoker.club/poker/api/share.php?share_type=club&uid=9630705&lang=en&lan=en&time=1762635634&club_id=370625&club_name=%CE%B2ILLIONAIRES&type=1&id=370625_0"
    keyboard = [[InlineKeyboardButton("🎮 Open BILLIONAIRES Club", url=club_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        pass

    # Edit original notification message to remove buttons for ALL admins
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                pass
        del notification_messages[request_id]

    # Check remaining pending withdrawals
    try:
        pending_withdrawals = api.get_pending_withdrawals()
        remaining_msg = f"\n📊 {len(pending_withdrawals)} pending withdrawal(s) remaining." if pending_withdrawals else "\n✅ No more pending withdrawals."
    except Exception as e:
        remaining_msg = ""

    # Edit message and explicitly remove keyboard
    try:
        await query.message.edit_text(
            text=f"✅ Withdrawal {request_id} has been completed.\n"
            f"User has been notified."
            f"{remaining_msg}",
            reply_markup=InlineKeyboardMarkup([])
        )
    except Exception as e:
        # If edit fails, try deleting and sending new message
        try:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ Withdrawal {request_id} has been completed.\n"
                f"User has been notified."
                f"{remaining_msg}"
            )
        except:
            pass

    return ConversationHandler.END


async def withdrawal_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject withdrawal request"""
    query = update.callback_query
    await query.answer()

    request_id = int(query.data.split('_')[-1])
    context.user_data['pending_action'] = ('withdrawal', 'reject', request_id)

    await query.edit_message_text(
        f"❌ Rejecting withdrawal {request_id}\n\n"
        "Please enter rejection reason:",
        reply_markup=None
    )

    return ADMIN_NOTES


# Cashback requests
async def admin_view_cashback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending cashback requests"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        query = update
        edit_func = update.message.reply_text

    # Get pending cashback requests
    pending_cashback = api.get_pending_cashback_requests()

    if not pending_cashback:
        await edit_func(
            "✅ No pending cashback requests.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="admin_back")
            ]])
        )
        return

    # Show first pending cashback request
    context.user_data['pending_cashback'] = pending_cashback
    context.user_data['current_cashback_index'] = 0

    await show_cashback_details(query, context, pending_cashback[0])


async def show_cashback_details(query, context, cashback_request):
    """Display cashback request details with approval buttons"""
    # Handle both old Google Sheets format and new Django API format
    request_id = cashback_request.get('id') or cashback_request.get('request_id')

    # Extract user details
    user_details = cashback_request.get('user_details', {})
    user_id = user_details.get('telegram_id') or cashback_request.get('user_id')
    username = user_details.get('username') or cashback_request.get('username')

    pppoker_id = cashback_request.get('pppoker_id', 'N/A')
    loss_amount = float(cashback_request.get('investment_amount') or cashback_request.get('loss_amount', 0))
    cashback_percentage = float(cashback_request.get('cashback_percentage', 0))
    cashback_amount = float(cashback_request.get('cashback_amount', 0))
    requested_at = cashback_request.get('created_at') or cashback_request.get('requested_at', 'N/A')

    current_index = context.user_data.get('current_cashback_index', 0)
    total = len(context.user_data.get('pending_cashback', []))

    message_text = (
        f"💵 <b>CASHBACK REQUEST {current_index + 1}/{total}</b>\n\n"
        f"🎫 Request ID: <code>{request_id}</code>\n"
        f"👤 User: {username} (ID: {user_id})\n"
        f"🎮 PPPoker ID: <b>{pppoker_id}</b>\n\n"
        f"📊 Loss Amount: <b>{loss_amount:.2f} MVR</b>\n"
        f"💰 Cashback Rate: <b>{cashback_percentage}%</b>\n"
        f"💎 Cashback Amount: <b>{cashback_amount:.2f} MVR</b>\n\n"
        f"📅 Requested: {requested_at}\n\n"
        f"─────────────────────"
    )

    # Build keyboard with approve/reject and navigation
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"cashback_admin_approve_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"cashback_admin_reject_{request_id}")
        ]
    ]

    # Add navigation if there are multiple requests
    if total > 1:
        nav_buttons = []
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data="cashback_nav_prev"))
        if current_index < total - 1:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="cashback_nav_next"))
        if nav_buttons:
            keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("« Back to Panel", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Handle both callback query and regular message
    if hasattr(query, 'edit_message_text'):
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML')


async def cashback_navigate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate between cashback requests"""
    query = update.callback_query
    await query.answer()

    direction = query.data.split('_')[2]
    current_index = context.user_data.get('current_cashback_index', 0)
    pending_cashback = context.user_data.get('pending_cashback', [])

    if direction == 'next' and current_index < len(pending_cashback) - 1:
        current_index += 1
    elif direction == 'prev' and current_index > 0:
        current_index -= 1

    context.user_data['current_cashback_index'] = current_index
    await show_cashback_details(query, context, pending_cashback[current_index])


async def cashback_admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approves a cashback request from panel"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    approver_id = user.id
    approver_name = user.username or user.first_name

    try:
        # Extract request_id from callback data
        request_id = int(query.data.replace("cashback_admin_approve_", ""))

        # Approve the request using Django API
        result = api.approve_cashback_request(request_id, approver_id)

        if result:
            # Extract details from result
            username = result['user_details']['username']
            target_user_id = result['user_details']['telegram_id']
            cashback_amount = float(result['cashback_amount'])

            await query.edit_message_text(
                f"✅ <b>Cashback Approved!</b>\n\n"
                f"User: {username}\n"
                f"Amount: {cashback_amount:.2f} MVR\n"
                f"Approved by: {approver_name}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
                ]])
            )

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"✅ <b>Cashback Approved!</b>\n\n"
                         f"💰 Amount: <b>{cashback_amount:.2f} MVR</b>\n\n"
                         f"Your balance has been updated!",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_user_id}: {e}")

            # Remove from pending list and show next
            pending_cashback = context.user_data.get('pending_cashback', [])
            current_index = context.user_data.get('current_cashback_index', 0)

            if current_index < len(pending_cashback):
                pending_cashback.pop(current_index)

            if pending_cashback:
                if current_index >= len(pending_cashback):
                    current_index = len(pending_cashback) - 1
                context.user_data['current_cashback_index'] = current_index
                context.user_data['pending_cashback'] = pending_cashback
                # Show next pending request
                await show_cashback_details(query, context, pending_cashback[current_index])
            else:
                # No more pending requests
                context.user_data.pop('pending_cashback', None)
                context.user_data.pop('current_cashback_index', None)

    except Exception as e:
        logger.error(f"Error approving cashback: {e}")
        await query.edit_message_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
            ]])
        )


async def cashback_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects a cashback request from panel"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    rejector_id = user.id
    rejector_name = user.username or user.first_name

    try:
        # Extract request_id from callback data
        request_id = int(query.data.replace("cashback_admin_reject_", ""))

        # Reject the request using Django API
        result = api.reject_cashback_request(request_id, rejector_id, "Rejected by admin")

        if result:
            # Extract details from result
            username = result['user_details']['username']
            target_user_id = result['user_details']['telegram_id']
            cashback_amount = float(result['cashback_amount'])

            await query.edit_message_text(
                f"❌ <b>Cashback Rejected</b>\n\n"
                f"User: {username}\n"
                f"Amount: {cashback_amount:.2f} MVR\n"
                f"Rejected by: {rejector_name}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
                ]])
            )

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"❌ <b>Cashback Rejected</b>\n\n"
                         f"Your cashback request has been rejected.\n"
                         f"Please contact support if you have questions.",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_user_id}: {e}")

            # Remove from pending list and show next
            pending_cashback = context.user_data.get('pending_cashback', [])
            current_index = context.user_data.get('current_cashback_index', 0)

            if current_index < len(pending_cashback):
                pending_cashback.pop(current_index)

            if pending_cashback:
                if current_index >= len(pending_cashback):
                    current_index = len(pending_cashback) - 1
                context.user_data['current_cashback_index'] = current_index
                context.user_data['pending_cashback'] = pending_cashback
                # Show next pending request
                await show_cashback_details(query, context, pending_cashback[current_index])
            else:
                # No more pending requests
                context.user_data.pop('pending_cashback', None)
                context.user_data.pop('current_cashback_index', None)

    except Exception as e:
        logger.error(f"Error rejecting cashback: {e}")
        await query.edit_message_text(
            f"❌ <b>Error</b>\n\n{str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
            ]])
        )


# ========== CREDITS VIEW ==========
async def admin_view_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all active credits (users who owe money)"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        query = update
        edit_func = update.message.reply_text

    try:
        # Get all active credits
        active_credits = api.get_all_active_credits()

        # Handle paginated response
        if isinstance(active_credits, dict) and 'results' in active_credits:
            active_credits = active_credits['results']

        if not active_credits:
            await edit_func(
                "✅ <b>No Active Credits</b>\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "All users have paid their debts!\n\n"
                "No outstanding balances.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back", callback_data="admin_back")
                ]]),
                parse_mode='HTML'
            )
            return

        # Calculate totals
        total_credits = len(active_credits)
        total_amount = sum(float(credit.get('amount', 0)) for credit in active_credits)

        # Build message
        message = f"💳 <b>ACTIVE CREDITS</b>\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"
        message += f"👥 <b>Total Users:</b> {total_credits}\n"
        message += f"💰 <b>Total Owed:</b> {total_amount:,.2f} MVR\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"

        # List each credit
        for i, credit in enumerate(active_credits[:10], 1):  # Show max 10
            user_details = credit.get('user_details', {})
            username = user_details.get('username', credit.get('username', 'Unknown'))
            username_display = f"@{username}" if username and username != 'Unknown' else "No username"

            # Get PPPoker ID and Telegram ID from user_details
            pppoker_id = user_details.get('pppoker_id') or credit.get('pppoker_id', 'N/A')
            telegram_id = user_details.get('telegram_id', 'N/A')
            created_at = credit.get('created_at', 'N/A')

            # Format date
            if created_at != 'N/A' and isinstance(created_at, str):
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = dt.strftime('%Y-%m-%d')
                except:
                    pass

            message += f"<b>{i}. {username_display}</b>\n"
            message += f"   💰 Owes: <b>{float(credit.get('amount', 0)):,.2f} MVR</b>\n"
            message += f"   🎮 PPPoker ID: {pppoker_id}\n"
            message += f"   👤 Telegram ID: <code>{telegram_id}</code>\n"
            message += f"   📅 Since: {created_at}\n\n"

        if len(active_credits) > 10:
            message += f"<i>... and {len(active_credits) - 10} more</i>\n\n"

        message += f"━━━━━━━━━━━━━━━━━━\n\n"
        message += f"💡 <i>Credits are unpaid debts from users</i>"

        # Add back button
        keyboard = [[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await edit_func(
            message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    except Exception as e:
        logger.error(f"Error viewing credits: {e}")
        await edit_func(
            f"❌ Error loading active credits: {str(e)}\n\n"
            f"Please try again or contact support.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="admin_back")
            ]]),
            parse_mode='HTML'
        )


# Join requests
async def admin_view_joins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending join requests"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        # Called from text message
        query = update
        edit_func = update.message.reply_text

    # Get pending join requests from Django API
    pending_joins = api.get_pending_join_requests()

    if not pending_joins:
        await edit_func(
            "✅ No pending join requests.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="admin_back")
            ]])
        )
        return

    context.user_data['pending_joins'] = pending_joins
    context.user_data['current_join_index'] = 0

    await show_join_details(query, context, pending_joins[0])


async def show_join_details(query, context, join_req):
    """Display join request details with approval buttons"""
    # Handle both dict (Django API) and list (legacy Sheets) format
    if isinstance(join_req, dict):
        request_id = join_req.get('id')
        # Get user details from nested user_details object
        user_details = join_req.get('user_details', {})
        user_id = user_details.get('telegram_id')
        username = user_details.get('username', 'No username')
        first_name = user_details.get('first_name', '')
        last_name = user_details.get('last_name', '')
        pppoker_id = join_req.get('pppoker_id')
    else:
        request_id = join_req[0]
        user_id = join_req[1]
        username = join_req[2]
        first_name = join_req[3]
        last_name = join_req[4]
        pppoker_id = join_req[5]

    current_index = context.user_data.get('current_join_index', 0)
    total = len(context.user_data.get('pending_joins', []))

    message_text = f"""
🎮 <b>CLUB JOIN REQUEST</b> ({current_index + 1}/{total})

<b>Request ID:</b> <code>{request_id}</code>
<b>User ID:</b> <code>{user_id}</code>
<b>Name:</b> {first_name} {last_name}
<b>Username:</b> @{username if username else 'No username'}
<b>PPPoker ID:</b> <a href='#'>(tap to copy)</a>
<code>{pppoker_id}</code>
"""

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"join_approve_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"join_reject_{request_id}")
        ]
    ]

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="join_prev"))
    if current_index < total - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="join_next"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("« Back to Panel", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Handle both callback query and regular message
    if hasattr(query, 'edit_message_text'):
        # It's a CallbackQuery
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # It's an Update object, send new message
        await query.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML')


async def join_navigate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate between join requests"""
    query = update.callback_query
    await query.answer()

    direction = query.data.split('_')[1]
    current_index = context.user_data.get('current_join_index', 0)
    pending_joins = context.user_data.get('pending_joins', [])

    if direction == 'next' and current_index < len(pending_joins) - 1:
        current_index += 1
    elif direction == 'prev' and current_index > 0:
        current_index -= 1

    context.user_data['current_join_index'] = current_index
    await show_join_details(query, context, pending_joins[current_index])


async def join_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve join request"""
    query = update.callback_query
    await query.answer("Processing approval...")

    request_id = int(query.data.split('_')[-1])
    admin_id = query.from_user.id

    # Clear any cached state first
    context.user_data.clear()

    join_req = api.get_join_request(request_id)
    if not join_req:
        await query.edit_message_text(
            text="❌ Join request not found.",
            reply_markup=InlineKeyboardMarkup([])
        )
        return ConversationHandler.END

    # Update status
    api.update_join_request_status(request_id, 'Approved', admin_id)

    # Notify user
    user_details = join_req.get('user_details', {})
    user_id = user_details.get('telegram_id') or join_req.get('user')
    user_message = (
        f"✅ <b>Welcome to Billionaires Club!</b>\n\n"
        f"<b>Request ID:</b> <code>{request_id}</code>\n"
        f"<b>PPPoker ID:</b> {join_req['pppoker_id']}\n\n"
        f"You've been approved to join the club. See you at the tables! 🎰"
    )

    try:
        await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
        logger.info(f"✅ User {user_id} notified about join request {request_id} approval")
    except Exception as e:
        logger.error(f"❌ Failed to notify user {user_id} about join approval: {e}")

    # Edit original notification message to remove buttons for ALL admins
    if request_id in notification_messages:
        for admin_id, message_id in notification_messages[request_id]:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=admin_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup([])
                )
            except Exception as e:
                pass
        del notification_messages[request_id]

    # Check remaining pending join requests
    try:
        pending_join_requests = api.get_pending_join_requests()
        remaining_msg = f"\n📊 {len(pending_join_requests)} pending join request(s) remaining." if pending_join_requests else "\n✅ No more pending join requests."
    except Exception as e:
        remaining_msg = ""

    # Edit message and explicitly remove keyboard
    try:
        await query.message.edit_text(
            text=f"✅ Join request {request_id} has been approved.\n"
            f"User has been notified."
            f"{remaining_msg}",
            reply_markup=InlineKeyboardMarkup([])
        )
    except Exception as e:
        # If edit fails, try deleting and sending new message
        try:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ Join request {request_id} has been approved.\n"
                f"User has been notified."
                f"{remaining_msg}"
            )
        except:
            pass

    return ConversationHandler.END


async def join_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject join request"""
    query = update.callback_query
    await query.answer()

    request_id = int(query.data.split('_')[-1])
    context.user_data['pending_action'] = ('join', 'reject', request_id)

    await query.edit_message_text(
        f"❌ Rejecting join request {request_id}\n\n"
        "Please enter rejection reason:",
        reply_markup=None
    )

    return ADMIN_NOTES


# Payment accounts
async def admin_view_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View and manage payment accounts with interactive buttons"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        # Called from text message
        query = update
        edit_func = update.message.reply_text

    # Get all payment accounts from Django API
    try:
        accounts_response = api.get_all_payment_accounts()
        logger.info(f"📋 Payment accounts response type: {type(accounts_response)}")
        logger.info(f"📋 Payment accounts response: {accounts_response}")

        # Handle different response formats
        if isinstance(accounts_response, list):
            accounts = accounts_response
            logger.info(f"📋 Using list format, {len(accounts)} accounts")
        elif isinstance(accounts_response, dict):
            if 'results' in accounts_response:
                accounts = accounts_response.get('results', [])
                logger.info(f"📋 Using paginated format, {len(accounts)} accounts")
            else:
                # Legacy format - dict keyed by method
                accounts = list(accounts_response.values())
                logger.info(f"📋 Using legacy dict format, {len(accounts)} accounts")
        else:
            accounts = []
            logger.warning(f"📋 Unknown response format: {type(accounts_response)}")

        # Log each account's ID
        for idx, acc in enumerate(accounts):
            if isinstance(acc, dict):
                logger.info(f"📋 Account {idx}: method={acc.get('method')}, id={acc.get('id')}, has_id={bool(acc.get('id'))}")
    except Exception as e:
        logger.error(f"Error fetching payment accounts: {e}")
        import traceback
        traceback.print_exc()
        accounts = []

    message_text = "🏦 <b>Payment Accounts Management</b>\n\n"

    # Build keyboard with edit/delete buttons for each account
    keyboard = []

    if accounts:
        for account in accounts:
            if isinstance(account, dict):
                # Django API format
                method = account.get('method', 'Unknown')
                account_num = account.get('account_number', 'Not set')
                holder = account.get('account_name', 'Not set')
                is_active = account.get('is_active', True)
                account_id = account.get('id')

                status_icon = "✅" if is_active else "❌"
                message_text += f"{status_icon} <b>{method}</b>\n"
                message_text += f"   Account: <code>{account_num}</code>\n"

                if holder and holder != 'Not set' and holder.strip():
                    message_text += f"   Holder: {holder}\n"

                message_text += "\n"

                # Add Edit and Delete/Activate buttons
                # Only add buttons if account has an ID (new format)
                if account_id:
                    if is_active:
                        keyboard.append([
                            InlineKeyboardButton(f"✏️ Edit {method}", callback_data=f"account_edit_{account_id}"),
                            InlineKeyboardButton(f"🗑️ Delete {method}", callback_data=f"account_delete_{account_id}")
                        ])
                    else:
                        keyboard.append([
                            InlineKeyboardButton(f"✏️ Edit {method}", callback_data=f"account_edit_{account_id}"),
                            InlineKeyboardButton(f"✅ Activate {method}", callback_data=f"account_activate_{account_id}")
                        ])
                else:
                    # Old format account without ID - show warning
                    message_text += f"   <i>⚠️ Legacy account (use /update_{method.lower()} to recreate)</i>\n\n"
    else:
        message_text += "<i>No payment accounts configured yet.</i>\n\n"

    message_text += "━━━━━━━━━━━━━━━━━━\n"
    message_text += "💡 <b>Tip:</b> Add payment methods for deposits/withdrawals"

    # Add "Add New Account" button
    keyboard.append([InlineKeyboardButton("➕ Add New Payment Method", callback_data="account_add")])
    keyboard.append([InlineKeyboardButton("« Back to Panel", callback_data="admin_back")])

    await edit_func(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


async def account_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm deletion of payment account"""
    query = update.callback_query
    await query.answer()

    # Extract account ID from callback_data
    logger.info(f"🗑️ Delete button clicked. Callback data: {query.data}")
    account_id = int(query.data.replace("account_delete_", ""))
    logger.info(f"🗑️ Extracted account ID: {account_id}")

    # Get account details
    try:
        logger.info(f"🗑️ Fetching account details for ID {account_id}")
        account = api.get_payment_account(account_id)
        logger.info(f"🗑️ Account fetched: {account}")

        if not account:
            logger.error(f"🗑️ Account {account_id} not found or returned None")
            await query.edit_message_text(
                "❌ Error: Payment account not found",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_accounts")]])
            )
            return

        method = account.get('method', 'Unknown')
        account_num = account.get('account_number', 'N/A')

        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"account_delete_yes_{account_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_view_accounts")
            ]
        ]

        await query.edit_message_text(
            f"⚠️ <b>Confirm Deletion</b>\n\n"
            f"Are you sure you want to delete this payment account?\n\n"
            f"<b>Method:</b> {method}\n"
            f"<b>Account:</b> <code>{account_num}</code>\n\n"
            f"<i>This action cannot be undone!</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error fetching account for deletion: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            f"❌ <b>Error: Account not found</b>\n\n"
            f"Account ID: {account_id}\n"
            f"Error: {str(e)}\n\n"
            f"<i>This might be a legacy account without an ID.\nPlease use \"➕ Add New Payment Method\" to create a new account.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_accounts")]]),
            parse_mode='HTML'
        )


async def account_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute deletion of payment account"""
    query = update.callback_query
    await query.answer()

    # Extract account ID
    account_id = int(query.data.replace("account_delete_yes_", ""))

    try:
        # Delete via Django API
        api.delete_payment_account(account_id)

        await query.answer("✅ Payment account deleted!", show_alert=True)
        # Return to accounts view
        await admin_view_accounts(update, context)
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        await query.edit_message_text(
            f"❌ <b>Error deleting account</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_accounts")]]),
            parse_mode='HTML'
        )


async def account_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate a deleted payment account"""
    query = update.callback_query
    await query.answer()

    # Extract account ID
    account_id = int(query.data.replace("account_activate_", ""))

    try:
        # Activate via Django API
        api.update_payment_account(account_id, is_active=True)

        await query.answer("✅ Payment account activated!", show_alert=True)
        # Return to accounts view
        await admin_view_accounts(update, context)
    except Exception as e:
        logger.error(f"Error activating account: {e}")
        await query.edit_message_text(
            f"❌ <b>Error activating account</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_accounts")]]),
            parse_mode='HTML'
        )


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to admin panel"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("💰 Pending Deposits", callback_data="admin_view_deposits")],
        [InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_view_withdrawals")],
        [InlineKeyboardButton("🎮 Pending Join Requests", callback_data="admin_view_joins")],
        [InlineKeyboardButton("🏦 Payment Accounts", callback_data="admin_view_accounts")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔐 **Admin Panel**\n\nSelect an option:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close admin panel"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Admin panel closed.")


# Promotion Management Handlers
async def admin_view_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View promotions management"""
    query = update.callback_query
    await query.answer()

    active_promo = api.get_active_promotion()
    active_cashback_promo = api.get_active_cashback_promotion()
    all_promos = api.get_all_promotions()
    all_cashback_promos = api.get_all_cashback_promotions()

    message = "🎁 <b>Promotions Management</b>\n\n"

    # Bonus Promotion Section
    message += "<b>💰 Bonus Promotion (Deposits):</b>\n"
    if active_promo:
        message += f"🆔 ID: {active_promo.get('id', 'N/A')}\n"
        message += f"📝 Code: {active_promo.get('code', 'N/A')}\n"
        message += f"💰 Bonus: {active_promo.get('percentage', 0)}%\n"
        message += f"📅 Period: {active_promo.get('start_date', 'N/A')} to {active_promo.get('end_date', 'N/A')}\n\n"
    else:
        message += "No active bonus promotion\n\n"

    # Cashback Promotion Section
    message += "<b>💸 Cashback Promotion (Losses):</b>\n"
    if active_cashback_promo:
        message += f"🆔 ID: {active_cashback_promo.get('id', 'N/A')}\n"
        message += f"📝 Code: {active_cashback_promo.get('code', 'N/A')}\n"
        message += f"💸 Cashback: {active_cashback_promo.get('percentage', 0)}%\n"
        message += f"📅 Period: {active_cashback_promo.get('start_date', 'N/A')} to {active_cashback_promo.get('end_date', 'N/A')}\n\n"
    else:
        message += "No active cashback promotion\n\n"

    message += f"Total bonus promotions: {len(all_promos)}\n"
    message += f"Total cashback promotions: {len(all_cashback_promos)}\n"

    keyboard = [
        [InlineKeyboardButton("➕ Create Bonus Promotion", callback_data="promo_create")],
        [InlineKeyboardButton("💸 Create Cashback Promotion", callback_data="cashback_promo_create")],
        [InlineKeyboardButton("📋 View All Bonus", callback_data="promo_view_all")],
        [InlineKeyboardButton("📋 View All Cashback", callback_data="cashback_promo_view_all")],
    ]

    if active_promo:
        keyboard.append([InlineKeyboardButton("🔴 Deactivate Bonus", callback_data=f"promo_deactivate_{active_promo.get('id')}")])

    if active_cashback_promo:
        keyboard.append([InlineKeyboardButton("🔴 Deactivate Cashback", callback_data=f"cashback_promo_deactivate_{active_cashback_promo.get('id')}")])

    keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def admin_view_all_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all bonus promotions"""
    query = update.callback_query
    await query.answer()

    all_promos = api.get_all_promotions()

    if not all_promos:
        await query.edit_message_text(
            "No bonus promotions found.\n\nUse 'Create Bonus Promotion' to add one.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )
        return

    message = "💰 <b>All Bonus Promotions</b>\n\n"
    for promo in all_promos[-10:]:  # Show last 10
        is_active = promo.get('is_active', False)
        status_emoji = "🟢" if is_active else "⚪"
        message += f"{status_emoji} <b>{promo.get('code', 'N/A')}</b> (ID: {promo.get('id', 'N/A')})\n"
        message += f"   Bonus: {promo.get('percentage', 0)}%\n"
        message += f"   Period: {promo.get('start_date', 'N/A')} to {promo.get('end_date', 'N/A')}\n"
        message += f"   Status: {'Active' if is_active else 'Inactive'}\n\n"

    keyboard = [[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def admin_view_all_cashback_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all cashback promotions"""
    query = update.callback_query
    await query.answer()

    all_cashback_promos = api.get_all_cashback_promotions()

    if not all_cashback_promos:
        await query.edit_message_text(
            "No cashback promotions found.\n\nUse 'Create Cashback Promotion' to add one.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )
        return

    message = "💸 <b>All Cashback Promotions</b>\n\n"
    for promo in all_cashback_promos[-10:]:  # Show last 10
        is_active = promo.get('is_active', False)
        status_emoji = "🟢" if is_active else "⚪"
        message += f"{status_emoji} <b>{promo.get('code', 'N/A')}</b> (ID: {promo.get('id', 'N/A')})\n"
        message += f"   Cashback: {promo.get('percentage', 0)}%\n"
        message += f"   Period: {promo.get('start_date', 'N/A')} to {promo.get('end_date', 'N/A')}\n"
        message += f"   Status: {'Active' if is_active else 'Inactive'}\n\n"

    keyboard = [[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def promo_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deactivate bonus promotion"""
    query = update.callback_query
    await query.answer()

    promotion_id = query.data.split('_')[-1]

    if api.deactivate_promotion(promotion_id):
        await query.edit_message_text(
            f"✅ Bonus promotion {promotion_id} has been deactivated.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )
    else:
        await query.edit_message_text(
            f"❌ Failed to deactivate bonus promotion.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )


async def cashback_promo_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deactivate cashback promotion"""
    query = update.callback_query
    await query.answer()

    promotion_id = query.data.split('_')[-1]

    if api.deactivate_cashback_promotion(promotion_id):
        await query.edit_message_text(
            f"✅ Cashback promotion {promotion_id} has been deactivated.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )
    else:
        await query.edit_message_text(
            f"❌ Failed to deactivate cashback promotion.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )


# REMOVED - Old update payment account handlers (replaced by conversation handlers in bot.py)
# These are now handled by update_payment_account_start() in bot.py with interactive flow


# ========== COUNTER CONTROL HANDLERS ==========

async def admin_counter_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current counter status with detailed information"""
    query = update.callback_query
    await query.answer()

    try:
        status = api.get_counter_status()
        is_open = status.get('is_open', True)

        status_emoji = "🟢" if is_open else "🔴"
        status_text = "OPEN" if is_open else "CLOSED"

        # Format updated_at timestamp nicely
        updated_at = status.get('updated_at', 'N/A')
        if updated_at != 'N/A' and isinstance(updated_at, str):
            from datetime import datetime
            try:
                # Parse ISO format: "2025-01-15T10:30:45.123456Z"
                dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                updated_at = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass  # Keep original if parsing fails

        # Get admin who updated
        updated_by_id = status.get('updated_by', 0)
        updated_by_text = f"Admin ID {updated_by_id}" if updated_by_id != 0 else "System"

        message = f"{status_emoji} <b>COUNTER STATUS</b>\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"
        message += f"Current Status: <b>{status_text}</b>\n\n"
        message += f"📅 Last Updated: {updated_at}\n"
        message += f"👤 Updated By: {updated_by_text}\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"

        if is_open:
            message += "✅ Counter is currently <b>OPEN</b>\n"
            message += "Users can deposit and make requests.\n\n"
            message += "To close counter, go back and click '🔴 Close Counter'"
        else:
            message += "❌ Counter is currently <b>CLOSED</b>\n"
            message += "Users cannot make new requests.\n\n"
            message += "To open counter, go back and click '🟢 Open Counter'"

        keyboard = [[InlineKeyboardButton("« Back to Panel", callback_data="admin_back")]]

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error getting counter status: {e}")
        await query.edit_message_text(
            f"❌ Error loading counter status: {str(e)}\n\n"
            f"Please try again or contact support.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_back")]])
        )


async def admin_close_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate counter closing process"""
    query = update.callback_query
    await query.answer()

    try:
        # Check if already closed
        if not api.is_counter_open():
            await query.edit_message_text(
                "⚠️ <b>Counter is already CLOSED</b>\n\n"
                "The counter is currently not accepting new requests.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_back")]])
            )
            return

        # Ask if admin wants to send announcement
        keyboard = [
            [InlineKeyboardButton("📸 Send with Poster", callback_data="counter_close_with_poster")],
            [InlineKeyboardButton("💬 Send Text Only", callback_data="counter_close_text_only")],
            [InlineKeyboardButton("🚫 No Announcement", callback_data="counter_close_silent")],
            [InlineKeyboardButton("« Cancel", callback_data="admin_back")]
        ]

        await query.edit_message_text(
            "🔴 <b>CLOSE COUNTER</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "You are about to close the counter.\n\n"
            "When closed:\n"
            "• Users cannot deposit\n"
            "• Users cannot withdraw\n"
            "• Users cannot join club\n"
            "• Users cannot request seats\n\n"
            "Do you want to send a closing announcement to all users?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error in admin_close_counter: {e}")
        await query.edit_message_text(
            f"❌ Error: {str(e)}\n\nPlease try again.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_back")]])
        )


async def admin_open_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate counter opening process"""
    query = update.callback_query
    await query.answer()

    try:
        # Check if already open
        if api.is_counter_open():
            await query.edit_message_text(
                "⚠️ <b>Counter is already OPEN</b>\n\n"
                "The counter is currently accepting requests.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_back")]])
            )
            return

        # Ask if admin wants to send announcement
        keyboard = [
            [InlineKeyboardButton("📸 Send with Poster", callback_data="counter_open_with_poster")],
            [InlineKeyboardButton("💬 Send Text Only", callback_data="counter_open_text_only")],
            [InlineKeyboardButton("🚫 No Announcement", callback_data="counter_open_silent")],
            [InlineKeyboardButton("« Cancel", callback_data="admin_back")]
        ]

        await query.edit_message_text(
            "🟢 <b>OPEN COUNTER</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "You are about to open the counter.\n\n"
            "When open:\n"
            "• Users can deposit\n"
            "• Users can withdraw\n"
            "• Users can join club\n"
            "• Users can request seats\n\n"
            "Do you want to send an opening announcement to all users?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error in admin_open_counter: {e}")
        await query.edit_message_text(
            f"❌ Error: {str(e)}\n\nPlease try again.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_back")]])
        )


async def admin_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show 50/50 investments menu"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("➕ Add Investment", callback_data="investment_add")],
        [InlineKeyboardButton("📥 Add Return", callback_data="investment_return")],
        [InlineKeyboardButton("📊 View Active (24h)", callback_data="investment_view_active")],
        [InlineKeyboardButton("📈 View Completed", callback_data="investment_view_completed")],
        [InlineKeyboardButton("⏰ Check Expired Now", callback_data="investment_check_expired")],
        [InlineKeyboardButton("« Back", callback_data="admin_back")]
    ]

    await query.edit_message_text(
        "💎 <b>50/50 Investments</b>\n\n"
        "Manage chip investments with trusted players.\n\n"
        "⏰ Investments auto-expire after 24 hours",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def investment_view_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View active investments"""
    query = update.callback_query
    await query.answer()

    try:
        # Get active investments from Django API
        active_investments = api.get_active_investments()

        # Handle paginated response
        if isinstance(active_investments, dict) and 'results' in active_investments:
            active_investments = active_investments['results']

        if not active_investments:
            await query.edit_message_text(
                "💎 <b>Active Investments</b>\n\n"
                "No active investments found.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
            )
            return

        message = "💎 <b>Active Investments</b>\n\n"

        # Group by PPPoker ID
        from collections import defaultdict
        player_groups = defaultdict(lambda: {'total': 0, 'count': 0, 'notes': '', 'date': ''})

        for inv in active_investments:
            pppoker_id = inv.get('pppoker_id', 'Unknown')

            player_groups[pppoker_id]['total'] += float(inv.get('investment_amount', 0))
            player_groups[pppoker_id]['count'] += 1
            if not player_groups[pppoker_id]['notes'] and inv.get('notes'):
                player_groups[pppoker_id]['notes'] = inv.get('notes', '')
            if not player_groups[pppoker_id]['date']:
                player_groups[pppoker_id]['date'] = inv.get('start_date', '')

        # Display grouped
        for pppoker_id, data in player_groups.items():
            player_display = data['notes'] if data['notes'] else pppoker_id

            message += f"🎮 <b>{player_display}</b>\n"
            message += f"💰 {data['total']:.2f} MVR"
            if data['count'] > 1:
                message += f" ({data['count']} investments)"
            message += f"\n🆔 PPPoker: {pppoker_id}\n"
            message += f"📅 {data['date']}\n\n"

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )

    except Exception as e:
        logger.error(f"Error viewing active investments: {e}")
        await query.edit_message_text(
            f"❌ Error loading investments: {str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )


async def investment_view_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View completed investments"""
    query = update.callback_query
    await query.answer()

    try:
        # Get all investments and filter completed
        all_investments = api.get_all_investments()

        # Handle paginated response
        if isinstance(all_investments, dict) and 'results' in all_investments:
            all_investments = all_investments['results']

        # Filter completed and lost
        completed = [inv for inv in all_investments if inv.get('status') == 'Completed']
        lost = [inv for inv in all_investments if inv.get('status') == 'Lost']

        if not completed and not lost:
            await query.edit_message_text(
                "📈 <b>Completed Investments</b>\n\n"
                "No completed or lost investments found.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
            )
            return

        # Calculate stats for completed
        total_investment = sum(float(inv.get('investment_amount', 0)) for inv in completed)
        total_profit_share = sum(float(inv.get('profit_share', 0)) for inv in completed)
        total_loss_share = sum(float(inv.get('loss_share', 0)) for inv in completed)

        # Calculate stats for lost (expired after 24h)
        lost_investment = sum(float(inv.get('investment_amount', 0)) for inv in lost)
        lost_loss_share = sum(float(inv.get('loss_share', 0)) for inv in lost)

        # Club gets: initial investment back + their share of profit
        # Profit share is what the PLAYER gets, so club gets the other 50%
        club_total_profit = total_profit_share  # Club and player split 50/50, so if player gets X, club also gets X

        message = "📈 <b>Completed & Lost Investments</b>\n\n"

        if completed:
            message += f"✅ <b>Completed:</b> {len(completed)}\n"
            message += f"💰 Invested: {total_investment:.2f} MVR\n"
            message += f"🏛️ Club Profit: {club_total_profit:.2f} MVR\n\n"

        if lost:
            message += f"⏰ <b>Lost (24h expired):</b> {len(lost)}\n"
            message += f"💸 Investment Lost: {lost_investment:.2f} MVR\n"
            message += f"❌ Club Loss: {lost_loss_share:.2f} MVR\n\n"

        # Total net result
        total_net = club_total_profit - total_loss_share - lost_loss_share
        message += f"━━━━━━━━━━━━━━━━━━\n"
        message += f"📊 <b>Net Result: "
        if total_net >= 0:
            message += f"+{total_net:.2f} MVR</b>"
        else:
            message += f"{total_net:.2f} MVR</b>"

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )

    except Exception as e:
        logger.error(f"Error viewing completed investments: {e}")
        await query.edit_message_text(
            f"❌ Error loading investments: {str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )


async def investment_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add investment flow"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💎 <b>Add 50/50 Investment</b>\n\n"
        "Enter the player's <b>PPPoker ID</b>:",
        parse_mode='HTML'
    )

    return INVESTMENT_TELEGRAM_ID


async def investment_telegram_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PPPoker ID input"""
    pppoker_id = update.message.text.strip()

    # Store the PPPoker ID
    context.user_data['investment_pppoker_id'] = pppoker_id

    await update.message.reply_text(
        "💰 <b>Investment Amount</b>\n\n"
        "Enter the amount you gave to the player (MVR):",
        parse_mode='HTML'
    )

    return INVESTMENT_AMOUNT


async def investment_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle investment amount input"""
    try:
        amount = float(update.message.text.strip())

        if amount <= 0:
            await update.message.reply_text(
                "❌ Invalid amount. Please enter a positive number:"
            )
            return INVESTMENT_AMOUNT

        context.user_data['investment_amount'] = amount

        await update.message.reply_text(
            "💎 <b>Add Note (Optional)</b>\n\n"
            "Enter player name or note (e.g., 'Ahmed', 'Friend 1')\n"
            "Or send /skip to skip:",
            parse_mode='HTML'
        )

        return INVESTMENT_NOTES

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number (e.g., 1000 or 1000.50):"
        )
        return INVESTMENT_AMOUNT


async def investment_notes_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle investment notes input"""
    from datetime import datetime
    import traceback

    notes = update.message.text.strip() if update.message.text != '/skip' else ''
    pppoker_id = context.user_data['investment_pppoker_id']
    amount = context.user_data['investment_amount']

    try:
        # Create investment with PPPoker ID (no Telegram user required)
        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"💎 Creating investment: pppoker_id={pppoker_id}, amount={amount}, notes={notes}")

        investment = api.create_investment(
            pppoker_id=pppoker_id,
            investment_amount=amount,
            start_date=today,
            notes=notes
        )

        logger.info(f"✅ Investment created successfully: {investment}")

        await update.message.reply_text(
            f"✅ <b>Investment Added!</b>\n\n"
            f"🎮 PPPoker ID: {pppoker_id}\n"
            f"💰 Amount: {amount:.2f} MVR\n"
            f"📝 Notes: {notes or 'N/A'}\n"
            f"📅 Date: {today}\n\n"
            f"⏰ <b>Important:</b> This investment will count as a loss after 24 hours if not returned.",
            parse_mode='HTML'
        )

        # Clear context
        context.user_data.clear()

        return ConversationHandler.END

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error creating investment: {error_msg}")
        logger.error(f"   PPPoker ID: {pppoker_id}, Amount: {amount}, Notes: {notes}")
        traceback.print_exc()

        await update.message.reply_text(
            f"❌ <b>Failed to add investment</b>\n\n"
            f"Error: <code>{error_msg}</code>\n\n"
            f"Please contact support if this persists.",
            parse_mode='HTML'
        )
        context.user_data.clear()
        return ConversationHandler.END


async def investment_return_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add return flow - show active investments"""
    query = update.callback_query
    await query.answer()

    # Get active investments
    try:
        active_investments = api.get_active_investments()

        if not active_investments:
            await query.edit_message_text(
                "📥 <b>Add Return</b>\n\n"
                "No active investments found.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
            )
            return ConversationHandler.END

        # Group by user
        from collections import defaultdict
        user_investments = defaultdict(list)

        for inv in active_investments:
            user_id = inv.get('user')
            user_investments[user_id].append(inv)

        # Create buttons for each user
        keyboard = []
        for user_id, investments in user_investments.items():
            total_amount = sum(float(inv.get('investment_amount', 0)) for inv in investments)
            # Get user details from first investment
            user_details = investments[0].get('user_details', {})
            username = user_details.get('username', f'User {user_id}')
            telegram_id = user_details.get('telegram_id', user_id)

            button_text = f"🎮 {username} - {total_amount:.0f} MVR"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"return_user_{user_id}")])

        keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_investments")])

        await query.edit_message_text(
            "📥 <b>Select User to Record Return</b>\n\n"
            "Choose which user returned their investment:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return RETURN_SELECT_USER

    except Exception as e:
        logger.error(f"Error getting active investments: {e}")
        await query.edit_message_text(
            f"❌ Error loading investments: {str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )
        return ConversationHandler.END


async def investment_return_user_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user selection for return"""
    query = update.callback_query
    await query.answer()

    # Extract user_id from callback_data: return_user_123
    user_id = int(query.data.split('_')[2])

    # Get this user's active investments
    try:
        all_active = api.get_active_investments()
        user_investments = [inv for inv in all_active if inv.get('user') == user_id]

        if not user_investments:
            await query.edit_message_text(
                "❌ No active investments found for this user.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
            )
            return ConversationHandler.END

        # Calculate total
        total_investment = sum(float(inv.get('investment_amount', 0)) for inv in user_investments)

        # Store in context
        context.user_data['return_user_id'] = user_id
        context.user_data['return_investments'] = user_investments
        context.user_data['return_total_investment'] = total_investment

        # Get user details
        user_details = user_investments[0].get('user_details', {})
        username = user_details.get('username', f'User {user_id}')

        await query.edit_message_text(
            f"📥 <b>Record Return</b>\n\n"
            f"👤 User: {username}\n"
            f"💰 Total Investment: {total_investment:.2f} MVR\n"
            f"📦 Active Investments: {len(user_investments)}\n\n"
            f"Please send the <b>total return amount</b> (MVR):",
            parse_mode='HTML'
        )

        return RETURN_AMOUNT

    except Exception as e:
        logger.error(f"Error getting user investments: {e}")
        await query.edit_message_text(
            f"❌ Error: {str(e)}",
            parse_mode='HTML'
        )
        return ConversationHandler.END


async def investment_return_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle return amount input and process return"""
    from datetime import datetime

    try:
        return_amount = float(update.message.text.strip())

        if return_amount <= 0:
            await update.message.reply_text(
                "❌ Invalid amount. Please enter a positive number:"
            )
            return RETURN_AMOUNT

        user_id = context.user_data['return_user_id']
        investments = context.user_data['return_investments']
        total_investment = context.user_data['return_total_investment']

        # Calculate profit/loss
        net_profit = return_amount - total_investment

        # 50/50 split
        club_share = total_investment + (net_profit / 2)  # Club gets initial back + 50% of profit
        player_share = net_profit / 2  # Player gets 50% of profit

        # Update all investments to Completed
        today = datetime.now().strftime('%Y-%m-%d')

        for inv in investments:
            inv_id = inv.get('id')
            # Update investment
            api._put(f"investments/{inv_id}/", {
                'status': 'Completed',
                'profit_share': float(player_share / len(investments)),  # Split evenly across all investments
                'loss_share': 0,
                'end_date': today
            })

        # Get user details for confirmation
        user_details = investments[0].get('user_details', {})
        username = user_details.get('username', f'User {user_id}')

        # Format confirmation message
        message = f"✅ <b>Return Recorded!</b>\n\n"
        message += f"👤 User: {username}\n"
        message += f"💰 Investment: {total_investment:.2f} MVR\n"
        message += f"📥 Return: {return_amount:.2f} MVR\n\n"

        if net_profit >= 0:
            message += f"📈 <b>PROFIT: {net_profit:.2f} MVR</b>\n\n"
            message += f"💵 Player Share: {player_share:.2f} MVR\n"
            message += f"🏛️ Club Share: {club_share:.2f} MVR"
        else:
            message += f"📉 <b>LOSS: {abs(net_profit):.2f} MVR</b>\n\n"
            message += f"Club lost {abs(club_share - total_investment):.2f} MVR"

        await update.message.reply_text(message, parse_mode='HTML')

        # Clear context
        context.user_data.clear()

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid amount. Please enter a valid number (e.g., 10000 or 10000.50):"
        )
        return RETURN_AMOUNT
    except Exception as e:
        logger.error(f"Error recording return: {e}")
        await update.message.reply_text(
            f"❌ Error recording return: {str(e)}\n\n"
            f"Please try again or contact support."
        )
        context.user_data.clear()
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any conversation"""
    await update.message.reply_text(
        "❌ Operation cancelled.",
        parse_mode='HTML'
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_investment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel investment conversation"""
    await update.message.reply_text(
        "❌ Operation cancelled.",
        parse_mode='HTML'
    )
    context.user_data.clear()
    return ConversationHandler.END


async def investment_check_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually check and mark expired investments"""
    query = update.callback_query
    await query.answer()

    try:
        # Show processing message
        await query.edit_message_text(
            "⏰ <b>Checking for expired investments...</b>\n\n"
            "Please wait...",
            parse_mode='HTML'
        )

        # Call API to mark expired investments
        marked_count = api.mark_expired_investments_as_lost()

        # Show result
        if marked_count > 0:
            message = (
                f"✅ <b>Expired Investments Marked</b>\n\n"
                f"📊 <b>Count:</b> {marked_count}\n"
                f"❌ <b>Status:</b> Changed to 'Lost'\n\n"
                f"These investments were active for more than 24 hours and have been automatically marked as club losses."
            )
        else:
            message = (
                "✅ <b>Check Complete</b>\n\n"
                "No expired investments found.\n\n"
                "All active investments are still within the 24-hour window."
            )

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )

    except Exception as e:
        logger.error(f"Error checking expired investments: {e}")
        await query.edit_message_text(
            f"❌ Error checking expired investments: {str(e)}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_investments")]])
        )


async def admin_club_balances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show club balances menu"""
    query = update.callback_query
    await query.answer()

    try:
        # Check if balances are initialized
        initialized = api.is_balances_initialized()

        if not initialized:
            keyboard = [
                [InlineKeyboardButton("⚙️ Set Starting Balances", callback_data="balances_setup")],
                [InlineKeyboardButton("« Back", callback_data="admin_back")]
            ]
            await query.edit_message_text(
                "🏦 <b>Club Balances</b>\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ Balances not initialized yet.\n\n"
                "Please set starting balances to begin tracking club inventory and cash balances.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # Show current balances
        balances = api.get_club_balances()

        # Handle paginated/dict response
        if isinstance(balances, dict) and 'results' in balances:
            balances = balances['results'][0] if balances['results'] else {}

        # Get values with defaults
        chip_inventory = float(balances.get('chip_inventory', 0))
        mvr_balance = float(balances.get('mvr_balance', 0))
        usd_balance = float(balances.get('usd_balance', 0))
        usdt_balance = float(balances.get('usdt_balance', 0))
        chip_cost_basis = float(balances.get('chip_cost_basis', 0))
        avg_chip_rate = float(balances.get('avg_chip_rate', 0))
        last_updated = balances.get('last_updated', 'N/A')

        # Format timestamp
        if last_updated != 'N/A' and isinstance(last_updated, str):
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                last_updated = dt.strftime('%Y-%m-%d %H:%M')
            except:
                pass

        message = "🏦 <b>Club Balances</b>\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"
        message += f"<b>💎 INVENTORY</b>\n"
        message += f"🎲 Chips: <b>{chip_inventory:,.0f}</b>\n"
        message += f"📊 Cost Basis: {chip_cost_basis:,.2f} MVR\n"
        message += f"📈 Avg Rate: {avg_chip_rate:.4f} MVR/chip\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"
        message += f"<b>💰 CASH BALANCES</b>\n"
        message += f"💰 MVR: <b>{mvr_balance:,.2f}</b>\n"
        message += f"💵 USD: <b>{usd_balance:,.2f}</b>\n"
        message += f"💎 USDT: <b>{usdt_balance:,.2f}</b>\n\n"
        message += f"━━━━━━━━━━━━━━━━━━\n\n"
        message += f"🕐 Last Updated: {last_updated}"

        keyboard = [
            [InlineKeyboardButton("🎲 Buy Chips", callback_data="balances_buy_chips")],
            [InlineKeyboardButton("💵 Add Cash", callback_data="balances_add_cash")],
            [InlineKeyboardButton("📊 Transaction History", callback_data="balances_history")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_club_balances")],
            [InlineKeyboardButton("« Back", callback_data="admin_back")]
        ]

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error viewing club balances: {e}")
        await query.edit_message_text(
            f"❌ Error loading club balances: {str(e)}\n\n"
            f"Please try again or contact support.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="admin_back")
            ]])
        )


async def balances_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show transaction history"""
    query = update.callback_query
    await query.answer()

    transactions = api.get_inventory_transactions(limit=10)

    if not transactions:
        await query.edit_message_text(
            "📊 <b>Transaction History</b>\n\n"
            "No transactions found.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_club_balances")]])
        )
        return

    message = "📊 <b>Recent Transactions</b>\n\n"

    for txn in transactions:
        if txn['type'] == 'BUY_CHIPS':
            message += f"🎲 <b>Bought Chips</b>\n"
            message += f"   Amount: {txn['amount']:,.0f} chips\n"
            message += f"   Cost: {txn['cost_value']:,.2f} MVR\n"
            message += f"   Rate: {txn['rate']:.4f} MVR/chip\n"
        elif txn['type'] == 'ADD_CASH':
            message += f"💵 <b>Added Cash</b>\n"
            message += f"   Amount: {txn['amount']:,.2f} {txn['currency']}\n"
            if txn['notes']:
                message += f"   Note: {txn['notes']}\n"

        message += f"   By: {txn['admin']}\n"
        message += f"   {txn['datetime']}\n\n"

    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_club_balances")]])
    )


# Payment Account Add/Edit Conversation Handlers
async def account_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new payment account"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "➕ <b>Add New Payment Method</b>\n\n"
        "Enter the payment method name:\n"
        "(e.g., BML, MIB, USD, USDT, BTC, etc.)",
        parse_mode='HTML'
    )

    from bot import ACCOUNT_ADD_METHOD
    return ACCOUNT_ADD_METHOD


async def account_add_method_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive payment method name"""
    method = update.message.text.strip().upper()

    # Store in context
    context.user_data['new_account_method'] = method

    await update.message.reply_text(
        f"✅ Payment Method: <b>{method}</b>\n\n"
        f"Now enter the account number/wallet address:",
        parse_mode='HTML'
    )

    from bot import ACCOUNT_ADD_NUMBER
    return ACCOUNT_ADD_NUMBER


async def account_add_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive account number"""
    account_number = update.message.text.strip()

    # Store in context
    context.user_data['new_account_number'] = account_number

    await update.message.reply_text(
        f"✅ Account Number: <code>{account_number}</code>\n\n"
        f"Enter the account holder name (or type 'skip' to leave empty):",
        parse_mode='HTML'
    )

    from bot import ACCOUNT_ADD_HOLDER
    return ACCOUNT_ADD_HOLDER


async def account_add_holder_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive account holder name and create account"""
    holder = update.message.text.strip()

    if holder.lower() == 'skip':
        holder = ''

    # Get stored data
    method = context.user_data.get('new_account_method')
    account_number = context.user_data.get('new_account_number')

    try:
        # First, check if an inactive account with this method already exists
        # Call the parent DjangoAPI method using super() pattern
        all_accounts_response = super(type(api), api).get_all_payment_accounts()
        existing_account = None

        # Handle paginated response
        if isinstance(all_accounts_response, list):
            accounts_list = all_accounts_response
        elif isinstance(all_accounts_response, dict) and 'results' in all_accounts_response:
            accounts_list = all_accounts_response['results']
        else:
            accounts_list = []

        # Search for existing account with this method
        for acc in accounts_list:
            if isinstance(acc, dict) and acc.get('method') == method:
                existing_account = acc
                break

        if existing_account and not existing_account.get('is_active', True):
            # Reactivate existing inactive account
            logger.info(f"Reactivating inactive account: {existing_account}")
            account_id = existing_account['id']
            api.update_payment_account(
                account_id,
                account_number=account_number,
                account_name=holder,
                is_active=True
            )
            action = "Reactivated"
        else:
            # Create new account
            api.create_payment_account(
                method=method,
                account_number=account_number,
                account_name=holder
            )
            action = "Created"

        await update.message.reply_text(
            f"✅ <b>Payment Account {action}!</b>\n\n"
            f"<b>Method:</b> {method}\n"
            f"<b>Account:</b> <code>{account_number}</code>\n"
            f"<b>Holder:</b> {holder if holder else 'Not set'}",
            parse_mode='HTML'
        )

        # Clear context
        context.user_data.pop('new_account_method', None)
        context.user_data.pop('new_account_number', None)

    except Exception as e:
        logger.error(f"Error creating payment account: {e}")
        await update.message.reply_text(
            f"❌ <b>Error creating account</b>\n\n{str(e)}",
            parse_mode='HTML'
        )

    from telegram.ext import ConversationHandler
    return ConversationHandler.END


async def account_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing a payment account"""
    query = update.callback_query
    await query.answer()

    # Extract account ID
    account_id = int(query.data.replace("account_edit_", ""))
    context.user_data['edit_account_id'] = account_id

    try:
        account = api.get_payment_account(account_id)

        if not account:
            logger.error(f"Account {account_id} not found or returned None")
            await query.edit_message_text(
                "❌ Error: Payment account not found",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_accounts")]])
            )
            return

        method = account.get('method', 'Unknown')
        current_number = account.get('account_number', 'N/A')
        current_holder = account.get('account_name', '')

        context.user_data['edit_account_method'] = method

        await query.edit_message_text(
            f"✏️ <b>Edit Payment Account</b>\n\n"
            f"<b>Method:</b> {method}\n"
            f"<b>Current Account:</b> <code>{current_number}</code>\n"
            f"<b>Current Holder:</b> {current_holder if current_holder else 'Not set'}\n\n"
            f"Enter new account number (or type 'skip' to keep current):",
            parse_mode='HTML'
        )

        from bot import ACCOUNT_EDIT_NUMBER
        return ACCOUNT_EDIT_NUMBER

    except Exception as e:
        logger.error(f"Error fetching account for edit: {e}")
        await query.edit_message_text(
            f"❌ Error: Account not found",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_accounts")]])
        )
        from telegram.ext import ConversationHandler
        return ConversationHandler.END


async def account_edit_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive new account number"""
    new_number = update.message.text.strip()

    if new_number.lower() != 'skip':
        context.user_data['edit_account_number'] = new_number
    else:
        context.user_data['edit_account_number'] = None

    await update.message.reply_text(
        f"Enter new account holder name (or type 'skip' to keep current):",
        parse_mode='HTML'
    )

    from bot import ACCOUNT_EDIT_HOLDER
    return ACCOUNT_EDIT_HOLDER


async def account_edit_holder_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive new holder name and update account"""
    new_holder = update.message.text.strip()

    if new_holder.lower() == 'skip':
        new_holder = None

    # Get stored data
    account_id = context.user_data.get('edit_account_id')
    new_number = context.user_data.get('edit_account_number')
    method = context.user_data.get('edit_account_method')

    try:
        # Build update data
        update_data = {}
        if new_number:
            update_data['account_number'] = new_number
        if new_holder:
            update_data['account_name'] = new_holder

        if update_data:
            api.update_payment_account(account_id, **update_data)

            await update.message.reply_text(
                f"✅ <b>Payment Account Updated!</b>\n\n"
                f"<b>Method:</b> {method}\n"
                f"{f'<b>New Account:</b> <code>{new_number}</code>' if new_number else ''}\n"
                f"{f'<b>New Holder:</b> {new_holder}' if new_holder else ''}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("ℹ️ No changes made.")

        # Clear context
        context.user_data.pop('edit_account_id', None)
        context.user_data.pop('edit_account_number', None)
        context.user_data.pop('edit_account_method', None)

    except Exception as e:
        logger.error(f"Error updating payment account: {e}")
        await update.message.reply_text(
            f"❌ <b>Error updating account</b>\n\n{str(e)}",
            parse_mode='HTML'
        )

    from telegram.ext import ConversationHandler
    return ConversationHandler.END


# ==================== EXCHANGE RATE MANAGEMENT ====================

async def admin_exchange_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View and manage exchange rates"""
    query = update.callback_query
    await query.answer("Refreshing rates...")

    try:
        # Get all active exchange rates
        rates = api.get_active_exchange_rates()

        # Build message showing current rates
        import datetime
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        message = f"💱 <b>Exchange Rate Management</b>\n"
        message += f"<i>Last updated: {current_time}</i>\n\n"
        message += "<b>Current Active Rates:</b>\n"

        if rates:
            for rate in rates:
                currency_from = rate.get('currency_from', 'N/A')
                currency_to = rate.get('currency_to', 'N/A')
                rate_value = float(rate.get('rate', 0))  # Convert to float for formatting
                message += f"• {currency_from} → {currency_to}: <b>{rate_value:.2f}</b>\n"
        else:
            message += "No active exchange rates set.\n"

        keyboard = [
            [InlineKeyboardButton("💵 Set USD Rate", callback_data="set_usd_rate")],
            [InlineKeyboardButton("💎 Set USDT Rate", callback_data="set_usdt_rate")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_exchange_rates")],
            [InlineKeyboardButton("« Back to Admin Panel", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error viewing exchange rates: {e}")
        # If error is about message not modified, just acknowledge it
        if "message is not modified" in str(e).lower():
            await query.answer("Rates are already up to date!", show_alert=False)
        else:
            await query.edit_message_text(
                f"❌ Error loading exchange rates: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_back")]])
            )


async def set_usd_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start USD rate setting conversation"""
    query = update.callback_query
    await query.answer()

    # Get current USD rate
    current_rate = api.get_exchange_rate('USD', 'MVR') or 15.42

    await query.edit_message_text(
        f"💵 <b>Set USD Exchange Rate</b>\n\n"
        f"<b>Current Rate:</b> 1 USD = {current_rate:.2f} MVR\n\n"
        f"Please enter the new exchange rate (numbers only):\n"
        f"Example: 15.42 or 17.50",
        parse_mode='HTML'
    )

    return SET_USD_RATE


async def set_usd_rate_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save USD rate"""
    try:
        rate = float(update.message.text.strip())

        if rate <= 0:
            await update.message.reply_text("❌ Rate must be greater than 0. Please try again:")
            return SET_USD_RATE

        # Create or update the exchange rate
        api.set_exchange_rate('USD', 'MVR', rate)
        await update.message.reply_text(
            f"✅ <b>USD Exchange Rate Updated!</b>\n\n"
            f"<b>USD → MVR:</b> {rate:.2f}\n\n"
            f"This rate will be used for all USD deposit conversions.",
            parse_mode='HTML'
        )

        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Invalid rate value. Please enter a number:")
        return SET_USD_RATE
    except Exception as e:
        logger.error(f"Error setting USD rate: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        from telegram.ext import ConversationHandler
        return ConversationHandler.END


async def set_usdt_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start USDT rate setting conversation"""
    query = update.callback_query
    await query.answer()

    # Get current USDT rate
    current_rate = api.get_exchange_rate('USDT', 'MVR') or 15.42

    await query.edit_message_text(
        f"💎 <b>Set USDT Exchange Rate</b>\n\n"
        f"<b>Current Rate:</b> 1 USDT = {current_rate:.2f} MVR\n\n"
        f"Please enter the new exchange rate (numbers only):\n"
        f"Example: 15.42 or 18.50",
        parse_mode='HTML'
    )

    return SET_USDT_RATE


async def set_usdt_rate_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save USDT rate"""
    try:
        rate = float(update.message.text.strip())

        if rate <= 0:
            await update.message.reply_text("❌ Rate must be greater than 0. Please try again:")
            return SET_USDT_RATE

        # Create or update the exchange rate
        api.set_exchange_rate('USDT', 'MVR', rate)
        await update.message.reply_text(
            f"✅ <b>USDT Exchange Rate Updated!</b>\n\n"
            f"<b>USDT → MVR:</b> {rate:.2f}\n\n"
            f"This rate will be used for all USDT deposit conversions.",
            parse_mode='HTML'
        )

        from telegram.ext import ConversationHandler
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Invalid rate value. Please enter a number:")
        return SET_USDT_RATE
    except Exception as e:
        logger.error(f"Error setting USDT rate: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        from telegram.ext import ConversationHandler
        return ConversationHandler.END


def register_admin_handlers(application, notif_messages=None, spin_bot_instance=None):
    """Register all admin handlers"""
    global notification_messages, spin_bot
    if notif_messages is not None:
        notification_messages = notif_messages
    if spin_bot_instance is not None:
        spin_bot = spin_bot_instance
        logger.info(f"✅ [ADMIN PANEL] spin_bot registered successfully: {spin_bot is not None}")
    else:
        logger.error(f"❌ [ADMIN PANEL] spin_bot_instance is None! Spins will NOT work!")

    # Admin panel
    application.add_handler(CommandHandler("admin", admin_panel))

    # NOTE: Update account commands (/update_bml, /update_mib, /update_usdt) are now
    # handled by conversation handlers in bot.py, not here

    # Callback query handlers
    application.add_handler(CallbackQueryHandler(admin_view_deposits, pattern="^admin_view_deposits$"))
    application.add_handler(CallbackQueryHandler(admin_view_withdrawals, pattern="^admin_view_withdrawals$"))
    application.add_handler(CallbackQueryHandler(admin_view_cashback, pattern="^admin_view_cashback$"))
    application.add_handler(CallbackQueryHandler(admin_view_credits, pattern="^admin_view_credits$"))
    application.add_handler(CallbackQueryHandler(admin_view_joins, pattern="^admin_view_joins$"))
    application.add_handler(CallbackQueryHandler(admin_view_promotions, pattern="^admin_view_promotions$"))
    application.add_handler(CallbackQueryHandler(admin_view_all_promotions, pattern="^promo_view_all$"))
    application.add_handler(CallbackQueryHandler(admin_view_all_cashback_promotions, pattern="^cashback_promo_view_all$"))
    application.add_handler(CallbackQueryHandler(promo_deactivate, pattern="^promo_deactivate_"))
    application.add_handler(CallbackQueryHandler(cashback_promo_deactivate, pattern="^cashback_promo_deactivate_"))
    application.add_handler(CallbackQueryHandler(admin_view_accounts, pattern="^admin_view_accounts$"))
    application.add_handler(CallbackQueryHandler(admin_exchange_rates, pattern="^admin_exchange_rates$"))
    application.add_handler(CallbackQueryHandler(admin_counter_status, pattern="^admin_counter_status$"))
    application.add_handler(CallbackQueryHandler(admin_close_counter, pattern="^admin_close_counter$"))
    application.add_handler(CallbackQueryHandler(admin_open_counter, pattern="^admin_open_counter$"))
    # NOTE: admin_broadcast callback is handled by broadcast_conv conversation handler in bot.py
    application.add_handler(CallbackQueryHandler(admin_investments, pattern="^admin_investments$"))
    application.add_handler(CallbackQueryHandler(investment_view_active, pattern="^investment_view_active$"))
    application.add_handler(CallbackQueryHandler(investment_view_completed, pattern="^investment_view_completed$"))
    application.add_handler(CallbackQueryHandler(investment_check_expired, pattern="^investment_check_expired$"))
    # Club Balance feature disabled - not needed, /stats tracks everything automatically
    # application.add_handler(CallbackQueryHandler(admin_club_balances, pattern="^admin_club_balances$"))
    # application.add_handler(CallbackQueryHandler(balances_history, pattern="^balances_history$"))
    application.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    application.add_handler(CallbackQueryHandler(admin_close, pattern="^admin_close$"))

    # Payment Account Management
    application.add_handler(CallbackQueryHandler(account_delete_confirm, pattern="^account_delete_\d+$"))
    application.add_handler(CallbackQueryHandler(account_delete_execute, pattern="^account_delete_yes_\d+$"))
    application.add_handler(CallbackQueryHandler(account_activate, pattern="^account_activate_\d+$"))

    # Deposit navigation
    application.add_handler(CallbackQueryHandler(deposit_navigate, pattern="^deposit_(next|prev)$"))

    # Withdrawal navigation
    application.add_handler(CallbackQueryHandler(withdrawal_navigate, pattern="^withdrawal_(next|prev)$"))

    # Cashback navigation
    application.add_handler(CallbackQueryHandler(cashback_navigate, pattern="^cashback_nav_(next|prev)$"))

    # Join navigation
    application.add_handler(CallbackQueryHandler(join_navigate, pattern="^join_(next|prev)$"))

    # Cashback approval/rejection from admin panel
    application.add_handler(CallbackQueryHandler(cashback_admin_approve, pattern="^cashback_admin_approve_"))
    application.add_handler(CallbackQueryHandler(cashback_admin_reject, pattern="^cashback_admin_reject_"))

    # Approval conversation handler
    approval_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(deposit_approve, pattern="^deposit_approve_"),
            CallbackQueryHandler(deposit_reject, pattern="^deposit_reject_"),
            CallbackQueryHandler(withdrawal_approve, pattern="^withdrawal_approve_"),
            CallbackQueryHandler(withdrawal_reject, pattern="^withdrawal_reject_"),
            CallbackQueryHandler(join_approve, pattern="^join_approve_"),
            CallbackQueryHandler(join_reject, pattern="^join_reject_"),
        ],
        states={
            ADMIN_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_notes_received)],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
        per_message=False,
        name="admin_approval_conv"
    )

    application.add_handler(approval_conv)

    # Investment conversation handlers
    investment_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(investment_add_start, pattern="^investment_add$")],
        states={
            INVESTMENT_TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, investment_telegram_id_received)],
            INVESTMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, investment_amount_received)],
            INVESTMENT_NOTES: [
                CommandHandler('skip', investment_notes_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, investment_notes_received)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_investment)],
        per_user=True,
        per_chat=True,
        per_message=False,
        name="investment_add_conv"
    )

    investment_return_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(investment_return_start, pattern="^investment_return$")],
        states={
            RETURN_SELECT_USER: [CallbackQueryHandler(investment_return_user_selected, pattern="^return_user_")],
            RETURN_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, investment_return_amount_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel_investment)],
        per_user=True,
        per_chat=True,
        per_message=False,
        name="investment_return_conv"
    )

    application.add_handler(investment_add_conv)
    application.add_handler(investment_return_conv)

    # Payment Account Add/Edit Conversation Handlers
    from bot import ACCOUNT_ADD_METHOD, ACCOUNT_ADD_NUMBER, ACCOUNT_ADD_HOLDER, ACCOUNT_EDIT_NUMBER, ACCOUNT_EDIT_HOLDER

    account_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(account_add_start, pattern="^account_add$")],
        states={
            ACCOUNT_ADD_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_add_method_received)],
            ACCOUNT_ADD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_add_number_received)],
            ACCOUNT_ADD_HOLDER: [MessageHandler(filters.TEXT, account_add_holder_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="account_add_conv"
    )

    account_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(account_edit_start, pattern="^account_edit_\d+$")],
        states={
            ACCOUNT_EDIT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_edit_number_received)],
            ACCOUNT_EDIT_HOLDER: [MessageHandler(filters.TEXT, account_edit_holder_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="account_edit_conv"
    )

    application.add_handler(account_add_conv)
    application.add_handler(account_edit_conv)

    # Exchange Rate Conversation Handlers
    set_usd_rate_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_usd_rate_start, pattern="^set_usd_rate$")],
        states={
            SET_USD_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_usd_rate_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="set_usd_rate_conv"
    )

    set_usdt_rate_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_usdt_rate_start, pattern="^set_usdt_rate$")],
        states={
            SET_USDT_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_usdt_rate_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True,
        name="set_usdt_rate_conv"
    )

    application.add_handler(set_usd_rate_conv)
    application.add_handler(set_usdt_rate_conv)
