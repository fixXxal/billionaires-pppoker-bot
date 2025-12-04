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
        [InlineKeyboardButton("💎 50/50 Investments", callback_data="admin_investments")],
        [InlineKeyboardButton("🏦 Club Balances", callback_data="admin_club_balances")],
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
        currency = 'MVR' if deposit.get('method') != 'USDT' else 'USD'

        # Add free spins based on deposit amount
        spins_message = ""
        spins_added = 0

        if spin_bot:
            try:
                # Convert USD/USDT to MVR for spin calculation
                amount = float(deposit['amount'])
                method = deposit.get('method', 'BML')

                logger.info(f"🎰 [ADMIN PANEL] SPIN CALCULATION START - User: {user_id}, Amount: {amount}, Method: {method}")

                if method == 'USD':
                    usd_rate = api.get_exchange_rate('USD', 'MVR') or 15.40
                    amount_mvr = amount * usd_rate
                    logger.info(f"💱 [ADMIN PANEL] Converting {amount} USD to {amount_mvr} MVR (rate: {usd_rate})")
                elif method == 'USDT':
                    usdt_rate = api.get_exchange_rate('USDT', 'MVR') or 15.40
                    amount_mvr = amount * usdt_rate
                    logger.info(f"💱 [ADMIN PANEL] Converting {amount} USDT to {amount_mvr} MVR (rate: {usdt_rate})")
                else:
                    amount_mvr = amount  # Already in MVR
                    logger.info(f"💰 [ADMIN PANEL] Using amount as MVR: {amount_mvr}")

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
        user_id = join_req['user_id']
        user_message = f"""
❌ **Your Club Join Request Has Been Declined**

**Request ID:** `{request_id}`
**Reason:** {reason or 'No reason provided'}

Please contact support if you have any questions.
"""

        try:
            await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
        except Exception as e:
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
    request_id = cashback_request['request_id']
    user_id = cashback_request['user_id']
    username = cashback_request['username']
    pppoker_id = cashback_request['pppoker_id']
    loss_amount = cashback_request['loss_amount']
    cashback_percentage = cashback_request['cashback_percentage']
    cashback_amount = cashback_request['cashback_amount']
    promotion_id = cashback_request.get('promotion_id', 'N/A')
    requested_at = cashback_request.get('requested_at', 'N/A')

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
        f"🎁 Promotion ID: <code>{promotion_id}</code>\n"
        f"📅 Requested: {requested_at}\n\n"
        f"─────────────────────"
    )

    # Build keyboard with approve/reject and navigation
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"cashback_admin_approve_{cashback_request['row_number']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"cashback_admin_reject_{cashback_request['row_number']}")
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
    approver_name = user.username or user.first_name

    # Extract row number from callback data
    row_number = int(query.data.replace("cashback_admin_approve_", ""))

    # Approve the request
    success = api.approve_cashback_request(row_number, approver_name)

    if success:
        # Get the request details for notification
        cashback_data = api.cashback_history_sheet.row_values(row_number)
        target_user_id = int(cashback_data[1])
        username = cashback_data[2]
        cashback_amount = float(cashback_data[6]) if cashback_data[6] else 0

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
                     f"Your cashback will be credited to your account shortly.",
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
    else:
        # Check if already processed by getting current status
        try:
            cashback_data = api.cashback_history_sheet.row_values(row_number)
            if len(cashback_data) >= 9:
                current_status = cashback_data[8]
                if current_status and current_status.lower() != 'pending':
                    username = cashback_data[2] if len(cashback_data) > 2 else 'Unknown'
                    await query.edit_message_text(
                        f"⚠️ <b>Already Processed</b>\n\n"
                        f"This cashback request has already been {current_status.lower()}.\n"
                        f"User: {username}",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
                        ]])
                    )
                    return
        except Exception as e:
            logger.error(f"Error checking cashback status: {e}")

        await query.edit_message_text(
            "❌ Error approving cashback request.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
            ]])
        )


async def cashback_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin rejects a cashback request from panel"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    rejector_name = user.username or user.first_name

    # Extract row number from callback data
    row_number = int(query.data.replace("cashback_admin_reject_", ""))

    # Reject the request
    success = api.reject_cashback_request(row_number, rejector_name)

    if success:
        # Get the request details for notification
        cashback_data = api.cashback_history_sheet.row_values(row_number)
        target_user_id = int(cashback_data[1])
        username = cashback_data[2]
        cashback_amount = float(cashback_data[6]) if cashback_data[6] else 0

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
    else:
        # Check if already processed by getting current status
        try:
            cashback_data = api.cashback_history_sheet.row_values(row_number)
            if len(cashback_data) >= 9:
                current_status = cashback_data[8]
                if current_status and current_status.lower() != 'pending':
                    username = cashback_data[2] if len(cashback_data) > 2 else 'Unknown'
                    await query.edit_message_text(
                        f"⚠️ <b>Already Processed</b>\n\n"
                        f"This cashback request has already been {current_status.lower()}.\n"
                        f"User: {username}",
                        parse_mode='HTML',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
                        ]])
                    )
                    return
        except Exception as e:
            logger.error(f"Error checking cashback status: {e}")

        await query.edit_message_text(
            "❌ Error rejecting cashback request.",
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

            pppoker_id = credit.get('pppoker_id', 'N/A')
            user_id = credit.get('user') or credit.get('user_id', 'N/A')
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
            message += f"   👤 User ID: <code>{user_id}</code>\n"
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
    user_message = f"""
✅ **Welcome to Billionaires Club!**

**Request ID:** `{request_id}`
**PPPoker ID:** {join_req['pppoker_id']}

You've been approved to join the club. See you at the tables! 🎰
"""

    try:
        await context.bot.send_message(chat_id=user_id, text=user_message, parse_mode='HTML')
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
    """View payment accounts"""
    # Handle both callback query and text message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        edit_func = query.edit_message_text
    else:
        # Called from text message
        query = update
        edit_func = update.message.reply_text

    accounts = api.get_all_payment_accounts()

    message_text = "🏦 <b>Current Payment Accounts</b>\n\n"

    for method, details in accounts.items():
        if isinstance(details, dict):
            # New format with account_number and account_name
            account_num = details.get('account_number', 'Not set')
            holder = details.get('account_name', 'Not set')

            message_text += f"💳 <b>{method}</b>\n"
            message_text += f"   Account: <code>{account_num}</code>\n"

            if holder and holder != 'Not set' and holder.strip():
                message_text += f"   Holder: {holder}\n"

            message_text += "\n"
        else:
            # Fallback for old simple string format
            message_text += f"💳 <b>{method}:</b> <code>{details}</code>\n\n"

    message_text += "━━━━━━━━━━━━━━━━━━\n"
    message_text += "📝 <b>Update Commands:</b>\n"
    message_text += "<code>/update_bml</code> - Update BML account\n"
    message_text += "<code>/update_mib</code> - Update MIB account\n"
    message_text += "<code>/update_usd</code> - Update USD account\n"
    message_text += "<code>/update_usdt</code> - Update USDT wallet"

    await edit_func(
        message_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Back to Panel", callback_data="admin_back")
        ]]),
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
    application.add_handler(CallbackQueryHandler(admin_counter_status, pattern="^admin_counter_status$"))
    application.add_handler(CallbackQueryHandler(admin_close_counter, pattern="^admin_close_counter$"))
    application.add_handler(CallbackQueryHandler(admin_open_counter, pattern="^admin_open_counter$"))
    application.add_handler(CallbackQueryHandler(admin_investments, pattern="^admin_investments$"))
    application.add_handler(CallbackQueryHandler(investment_view_active, pattern="^investment_view_active$"))
    application.add_handler(CallbackQueryHandler(investment_view_completed, pattern="^investment_view_completed$"))
    application.add_handler(CallbackQueryHandler(investment_check_expired, pattern="^investment_check_expired$"))
    application.add_handler(CallbackQueryHandler(admin_club_balances, pattern="^admin_club_balances$"))
    application.add_handler(CallbackQueryHandler(balances_history, pattern="^balances_history$"))
    application.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    application.add_handler(CallbackQueryHandler(admin_close, pattern="^admin_close$"))

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
