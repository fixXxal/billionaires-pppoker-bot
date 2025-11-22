"""
Admin Panel for Billionaires PPPoker Bot
Handles all admin commands and approval workflows
"""

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from sheets_manager import SheetsManager
from dotenv import load_dotenv

load_dotenv()

ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID'))
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'Billionaires_PPPoker_Bot')
CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
TIMEZONE = os.getenv('TIMEZONE', 'Indian/Maldives')

sheets = SheetsManager(CREDENTIALS_FILE, SPREADSHEET_NAME, TIMEZONE)

# Conversation states
ADMIN_NOTES, UPDATE_ACCOUNT_NUMBER = range(2)

# Notification messages storage (will be set by bot.py)
notification_messages = {}


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
    return sheets.is_admin(user_id, ADMIN_USER_ID)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You don't have admin access.")
        return

    keyboard = [
        [InlineKeyboardButton("💰 Pending Deposits", callback_data="admin_view_deposits")],
        [InlineKeyboardButton("💸 Pending Withdrawals", callback_data="admin_view_withdrawals")],
        [InlineKeyboardButton("🎮 Pending Join Requests", callback_data="admin_view_joins")],
        [InlineKeyboardButton("🎁 Promotions", callback_data="admin_view_promotions")],
        [InlineKeyboardButton("🏦 Payment Accounts", callback_data="admin_view_accounts")],
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

    # Get all deposits from sheet
    all_deposits = sheets.deposits_sheet.get_all_values()[1:]  # Skip header
    pending_deposits = [d for d in all_deposits if len(d) > 8 and d[8] == 'Pending']

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


async def show_deposit_details(query, context, deposit_row):
    """Display deposit details with approval buttons"""
    request_id = deposit_row[0]
    user_id = deposit_row[1]
    username = deposit_row[2]
    pppoker_id = deposit_row[3]
    amount = deposit_row[4]
    method = deposit_row[5]
    account_name = deposit_row[6]
    transaction_ref = deposit_row[7]

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

    request_id = query.data.split('_')[-1]
    admin_id = query.from_user.id

    # Clear any cached state first
    context.user_data.clear()

    deposit = sheets.get_deposit_request(request_id)
    if not deposit:
        await query.edit_message_text(
            text="❌ Deposit request not found.",
            reply_markup=InlineKeyboardMarkup([])
        )
        return ConversationHandler.END

    # Update status
    sheets.update_deposit_status(request_id, 'Approved', admin_id, 'Approved via admin panel')

    # Notify user with club link button
    user_id = deposit['user_id']
    user_message = f"""
✅ **Your Deposit Has Been Approved!**

**Request ID:** `{request_id}`
**Amount:** {deposit['amount']} {'MVR' if deposit['payment_method'] != 'USDT' else 'USD'}
**PPPoker ID:** {deposit['pppoker_id']}

Your chips have been added to your account. Happy gaming! 🎮
"""

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
                pass  # Message might be too old or already deleted
        # Clean up the stored message_ids
        del notification_messages[request_id]

    # Check remaining pending deposits
    all_deposits = sheets.deposits_sheet.get_all_values()[1:]
    pending_deposits = [d for d in all_deposits if len(d) > 8 and d[8] == 'Pending']
    remaining_msg = f"\n📊 {len(pending_deposits)} pending deposit(s) remaining." if pending_deposits else "\n✅ No more pending deposits."

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
        try:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ Deposit {request_id} has been approved.\n"
                f"User has been notified."
                f"{remaining_msg}"
            )
        except:
            pass

    return ConversationHandler.END


async def deposit_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject deposit request"""
    query = update.callback_query
    await query.answer()

    request_id = query.data.split('_')[-1]
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
        deposit = sheets.get_deposit_request(request_id)
        if not deposit:
            await update.message.reply_text("❌ Deposit request not found.")
            return ConversationHandler.END

        # Update status to rejected
        sheets.update_deposit_status(request_id, 'Rejected', admin_id, reason)

        # Notify user
        user_id = deposit['user_id']
        user_message = f"""
❌ **Your Deposit Has Been Rejected**

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

        # Check remaining pending deposits
        all_deposits = sheets.deposits_sheet.get_all_values()[1:]
        pending_deposits = [d for d in all_deposits if len(d) > 8 and d[8] == 'Pending']

        remaining_msg = f"\n📊 {len(pending_deposits)} pending deposit(s) remaining." if pending_deposits else "\n✅ No more pending deposits."

        await update.message.reply_text(
            f"✅ Deposit {request_id} has been rejected.\n"
            f"User has been notified."
            f"{remaining_msg}"
        )

    elif action_type == 'withdrawal':
        withdrawal = sheets.get_withdrawal_request(request_id)
        if not withdrawal:
            await update.message.reply_text("❌ Withdrawal request not found.")
            return ConversationHandler.END

        # Update status to rejected
        sheets.update_withdrawal_status(request_id, 'Rejected', admin_id, reason)

        # Notify user
        user_id = withdrawal['user_id']
        user_message = f"""
❌ **Your Withdrawal Has Been Rejected**

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

        # Check remaining pending withdrawals
        all_withdrawals = sheets.withdrawals_sheet.get_all_values()[1:]
        pending_withdrawals = [w for w in all_withdrawals if len(w) > 8 and w[8] == 'Pending']

        remaining_msg = f"\n📊 {len(pending_withdrawals)} pending withdrawal(s) remaining." if pending_withdrawals else "\n✅ No more pending withdrawals."

        await update.message.reply_text(
            f"✅ Withdrawal {request_id} has been rejected.\n"
            f"User has been notified."
            f"{remaining_msg}"
        )

    elif action_type == 'join':
        join_req = sheets.get_join_request(request_id)
        if not join_req:
            await update.message.reply_text("❌ Join request not found.")
            return ConversationHandler.END

        # Update status to rejected
        sheets.update_join_request_status(request_id, 'Rejected', admin_id)

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
        all_join_requests = sheets.join_requests_sheet.get_all_values()[1:]
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

    all_withdrawals = sheets.withdrawals_sheet.get_all_values()[1:]
    pending_withdrawals = [w for w in all_withdrawals if len(w) > 8 and w[8] == 'Pending']

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


async def show_withdrawal_details(query, context, withdrawal_row):
    """Display withdrawal details with approval buttons"""
    request_id = withdrawal_row[0]
    user_id = withdrawal_row[1]
    username = withdrawal_row[2]
    pppoker_id = withdrawal_row[3]
    amount = withdrawal_row[4]
    method = withdrawal_row[5]
    account_name = withdrawal_row[6]
    account_number = withdrawal_row[7]

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

    request_id = query.data.split('_')[-1]
    admin_id = query.from_user.id

    # Clear any cached state first
    context.user_data.clear()

    withdrawal = sheets.get_withdrawal_request(request_id)
    if not withdrawal:
        await query.edit_message_text(
            text="❌ Withdrawal request not found.",
            reply_markup=InlineKeyboardMarkup([])
        )
        return ConversationHandler.END

    # Update status
    sheets.update_withdrawal_status(request_id, 'Completed', admin_id, 'Approved via admin panel')

    # Notify user with club link button
    user_id = withdrawal['user_id']
    user_message = f"""
✅ **Your Withdrawal Has Been Processed!**

**Request ID:** `{request_id}`
**Amount:** {withdrawal['amount']} {'MVR' if withdrawal['payment_method'] != 'USDT' else 'USD'}
**Method:** {withdrawal['payment_method']}
**Account:** {withdrawal['account_number']}

Your funds have been transferred. Please check your account. 💰
"""

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
    all_withdrawals = sheets.withdrawals_sheet.get_all_values()[1:]
    pending_withdrawals = [w for w in all_withdrawals if len(w) > 8 and w[8] == 'Pending']
    remaining_msg = f"\n📊 {len(pending_withdrawals)} pending withdrawal(s) remaining." if pending_withdrawals else "\n✅ No more pending withdrawals."

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

    request_id = query.data.split('_')[-1]
    context.user_data['pending_action'] = ('withdrawal', 'reject', request_id)

    await query.edit_message_text(
        f"❌ Rejecting withdrawal {request_id}\n\n"
        "Please enter rejection reason:",
        reply_markup=None
    )

    return ADMIN_NOTES


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

    all_joins = sheets.join_requests_sheet.get_all_values()[1:]
    pending_joins = [j for j in all_joins if len(j) > 6 and j[6] == 'Pending']

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


async def show_join_details(query, context, join_row):
    """Display join request details with approval buttons"""
    request_id = join_row[0]
    user_id = join_row[1]
    username = join_row[2]
    first_name = join_row[3]
    last_name = join_row[4]
    pppoker_id = join_row[5]

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

    request_id = query.data.split('_')[-1]
    admin_id = query.from_user.id

    # Clear any cached state first
    context.user_data.clear()

    join_req = sheets.get_join_request(request_id)
    if not join_req:
        await query.edit_message_text(
            text="❌ Join request not found.",
            reply_markup=InlineKeyboardMarkup([])
        )
        return ConversationHandler.END

    # Update status
    sheets.update_join_request_status(request_id, 'Approved', admin_id)

    # Notify user
    user_id = join_req['user_id']
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
    all_join_requests = sheets.join_requests_sheet.get_all_values()[1:]
    pending_join_requests = [j for j in all_join_requests if len(j) > 5 and j[5] == 'Pending']
    remaining_msg = f"\n📊 {len(pending_join_requests)} pending join request(s) remaining." if pending_join_requests else "\n✅ No more pending join requests."

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

    request_id = query.data.split('_')[-1]
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

    accounts = sheets.get_all_payment_accounts()

    message_text = "🏦 <b>Current Payment Accounts</b>\n\n"

    for method, details in accounts.items():
        if isinstance(details, dict):
            # New format with account_number and account_holder
            account_num = details.get('account_number', 'Not set')
            holder = details.get('account_holder', 'Not set')

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

    active_promo = sheets.get_active_promotion()
    active_cashback_promo = sheets.get_active_cashback_promotion()
    all_promos = sheets.get_all_promotions()
    all_cashback_promos = sheets.get_all_cashback_promotions()

    message = "🎁 **Promotions Management**\n\n"

    # Bonus Promotion Section
    message += "**💰 Bonus Promotion (Deposits):**\n"
    if active_promo:
        message += f"🆔 ID: `{active_promo['promotion_id']}`\n"
        message += f"💰 Bonus: {active_promo['bonus_percentage']}%\n"
        message += f"📅 Period: {active_promo['start_date']} to {active_promo['end_date']}\n\n"
    else:
        message += "No active bonus promotion\n\n"

    # Cashback Promotion Section
    message += "**💸 Cashback Promotion (Losses):**\n"
    if active_cashback_promo:
        message += f"🆔 ID: `{active_cashback_promo['promotion_id']}`\n"
        message += f"💸 Cashback: {active_cashback_promo['cashback_percentage']}%\n"
        message += f"📅 Period: {active_cashback_promo['start_date']} to {active_cashback_promo['end_date']}\n\n"
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
        keyboard.append([InlineKeyboardButton("🔴 Deactivate Bonus", callback_data=f"promo_deactivate_{active_promo['promotion_id']}")])

    if active_cashback_promo:
        keyboard.append([InlineKeyboardButton("🔴 Deactivate Cashback", callback_data=f"cashback_promo_deactivate_{active_cashback_promo['promotion_id']}")])

    keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_back")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_view_all_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all bonus promotions"""
    query = update.callback_query
    await query.answer()

    all_promos = sheets.get_all_promotions()

    if not all_promos:
        await query.edit_message_text(
            "No bonus promotions found.\n\nUse 'Create Bonus Promotion' to add one.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )
        return

    message = "💰 **All Bonus Promotions**\n\n"
    for promo in all_promos[-10:]:  # Show last 10
        status_emoji = "🟢" if promo['status'] == 'Active' else "⚪"
        message += f"{status_emoji} **{promo['promotion_id']}**\n"
        message += f"   Bonus: {promo['bonus_percentage']}%\n"
        message += f"   Period: {promo['start_date']} to {promo['end_date']}\n"
        message += f"   Status: {promo['status']}\n\n"

    keyboard = [[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_view_all_cashback_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all cashback promotions"""
    query = update.callback_query
    await query.answer()

    all_cashback_promos = sheets.get_all_cashback_promotions()

    if not all_cashback_promos:
        await query.edit_message_text(
            "No cashback promotions found.\n\nUse 'Create Cashback Promotion' to add one.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]])
        )
        return

    message = "💸 **All Cashback Promotions**\n\n"
    for promo in all_cashback_promos[-10:]:  # Show last 10
        status_emoji = "🟢" if promo['status'] == 'Active' else "⚪"
        message += f"{status_emoji} **{promo['promotion_id']}**\n"
        message += f"   Cashback: {promo['cashback_percentage']}%\n"
        message += f"   Period: {promo['start_date']} to {promo['end_date']}\n"
        message += f"   Status: {promo['status']}\n\n"

    keyboard = [[InlineKeyboardButton("« Back", callback_data="admin_view_promotions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')


async def promo_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deactivate bonus promotion"""
    query = update.callback_query
    await query.answer()

    promotion_id = query.data.split('_')[-1]

    if sheets.deactivate_promotion(promotion_id):
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

    if sheets.deactivate_cashback_promotion(promotion_id):
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


def register_admin_handlers(application, notif_messages=None):
    """Register all admin handlers"""
    global notification_messages
    if notif_messages is not None:
        notification_messages = notif_messages

    # Admin panel
    application.add_handler(CommandHandler("admin", admin_panel))

    # NOTE: Update account commands (/update_bml, /update_mib, /update_usdt) are now
    # handled by conversation handlers in bot.py, not here

    # Callback query handlers
    application.add_handler(CallbackQueryHandler(admin_view_deposits, pattern="^admin_view_deposits$"))
    application.add_handler(CallbackQueryHandler(admin_view_withdrawals, pattern="^admin_view_withdrawals$"))
    application.add_handler(CallbackQueryHandler(admin_view_joins, pattern="^admin_view_joins$"))
    application.add_handler(CallbackQueryHandler(admin_view_promotions, pattern="^admin_view_promotions$"))
    application.add_handler(CallbackQueryHandler(admin_view_all_promotions, pattern="^promo_view_all$"))
    application.add_handler(CallbackQueryHandler(admin_view_all_cashback_promotions, pattern="^cashback_promo_view_all$"))
    application.add_handler(CallbackQueryHandler(promo_deactivate, pattern="^promo_deactivate_"))
    application.add_handler(CallbackQueryHandler(cashback_promo_deactivate, pattern="^cashback_promo_deactivate_"))
    application.add_handler(CallbackQueryHandler(admin_view_accounts, pattern="^admin_view_accounts$"))
    application.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    application.add_handler(CallbackQueryHandler(admin_close, pattern="^admin_close$"))

    # Deposit navigation
    application.add_handler(CallbackQueryHandler(deposit_navigate, pattern="^deposit_(next|prev)$"))

    # Withdrawal navigation
    application.add_handler(CallbackQueryHandler(withdrawal_navigate, pattern="^withdrawal_(next|prev)$"))

    # Join navigation
    application.add_handler(CallbackQueryHandler(join_navigate, pattern="^join_(next|prev)$"))

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
