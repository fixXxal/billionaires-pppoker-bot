"""
Integration file to add Spin Bot handlers to main bot
Add this to your bot.py file to enable spin functionality
"""

# INTEGRATION INSTRUCTIONS:
#
# 1. Add this import at the top of bot.py (around line 22):
#    from spin_bot import SpinBot, freespins_command, spin_callback, spin_again_callback, pendingspins_command, approvespin_command, addspins_command, spinsstats_command
#
# 2. Initialize SpinBot after sheets manager (around line 52):
#    spin_bot = SpinBot(sheets, ADMIN_USER_ID, pytz.timezone(TIMEZONE))
#
# 3. Add spin command handlers in main() function (around line 4800, before application.run_polling()):
#
#    # Spin Bot Handlers
#    application.add_handler(CommandHandler('freespins', lambda update, context: freespins_command(update, context, spin_bot)))
#    application.add_handler(CallbackQueryHandler(lambda update, context: spin_callback(update, context, spin_bot, ADMIN_USER_ID), pattern='^spin_\\d+$'))
#    application.add_handler(CallbackQueryHandler(lambda update, context: spin_callback(update, context, spin_bot, ADMIN_USER_ID), pattern='^spin_all$'))
#    application.add_handler(CallbackQueryHandler(lambda update, context: spin_again_callback(update, context, spin_bot), pattern='^spin_again$'))
#
#    # Admin Spin Handlers
#    application.add_handler(CommandHandler('pendingspins', lambda update, context: pendingspins_command(update, context, spin_bot, is_admin)))
#    application.add_handler(CommandHandler('approvespin', lambda update, context: approvespin_command(update, context, spin_bot, is_admin)))
#    application.add_handler(CommandHandler('addspins', lambda update, context: addspins_command(update, context, spin_bot, is_admin)))
#    application.add_handler(CommandHandler('spinsstats', lambda update, context: spinsstats_command(update, context, spin_bot, is_admin)))
#
# 4. IMPORTANT: Add spins from deposits - modify your deposit approval handler
#    Find the function that approves deposits (likely around line 1500-2000)
#    After a deposit is approved, add this code:
#
#    # Add free spins from deposit
#    try:
#        spins_awarded = await spin_bot.add_spins_from_deposit(
#            user_id=deposit_data['user_id'],
#            username=deposit_data['username'],
#            amount_mvr=float(deposit_data['amount'])
#        )
#
#        if spins_awarded > 0:
#            # Notify user about free spins
#            try:
#                await context.bot.send_message(
#                    chat_id=deposit_data['user_id'],
#                    text=f"🎁 Bonus: You received {spins_awarded} FREE SPINS!\n\nUse /freespins to play and win prizes!"
#                )
#            except:
#                pass
#    except Exception as e:
#        logger.error(f"Error adding spins from deposit: {e}")
#
# 5. Update the help command to include spin commands:
#    Add to user help menu (around line 600-700):
#    "🎰 /freespins - Play the spin wheel and win prizes!"
#
#    Add to admin help menu (around line 700-800):
#    "🎰 SPIN BOT COMMANDS:\n"
#    "/pendingspins - View pending spin rewards\n"
#    "/approvespin <spin_id> - Approve a reward\n"
#    "/addspins <user_id> <count> - Add spins to user\n"
#    "/spinsstats - View spin statistics"
