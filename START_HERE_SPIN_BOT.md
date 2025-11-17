# 🎯 START HERE - Spin Bot Integration

## ⚡ Quick Start (Copy & Paste)

### 📂 Files Overview

```
✅ spin_bot.py                 - Main spin bot code (DO NOT EDIT)
✅ sheets_manager.py            - Updated with spin methods (ALREADY DONE)
📖 SPIN_BOT_README.md           - Complete documentation
📖 SPIN_BOT_SUMMARY.md          - Quick reference guide
📋 INTEGRATION_CODE.txt         - Code to copy
📋 bot_integration.py           - Integration instructions
📋 START_HERE_SPIN_BOT.md       - This file
```

---

## 🚀 Integration in 3 Steps

### Step 1️⃣: Open bot.py and find line ~20-25 (imports section)

**ADD THIS IMPORT:**
```python
from spin_bot import (
    SpinBot, freespins_command, spin_callback,
    spin_again_callback, pendingspins_command,
    approvespin_command, addspins_command, spinsstats_command
)
```

---

### Step 2️⃣: Find line ~52 (after `sheets = SheetsManager(...)`)

**ADD THIS LINE:**
```python
# Initialize Spin Bot
spin_bot = SpinBot(sheets, ADMIN_USER_ID, pytz.timezone(TIMEZONE))
```

---

### Step 3️⃣: Find the `main()` function (around line 4600-4800)

**FIND THIS CODE:**
```python
def main():
    """Start the bot"""
    application = Application.builder().token(TOKEN).build()

    # Add handlers here...
    # ... existing handlers ...
```

**ADD THESE HANDLERS BEFORE `application.run_polling()`:**
```python
    # ========== SPIN BOT HANDLERS ==========
    # User Commands
    application.add_handler(CommandHandler('freespins',
        lambda update, context: freespins_command(update, context, spin_bot)))

    # Spin Callbacks
    application.add_handler(CallbackQueryHandler(
        lambda update, context: spin_callback(update, context, spin_bot, ADMIN_USER_ID),
        pattern='^spin_\\d+$'))
    application.add_handler(CallbackQueryHandler(
        lambda update, context: spin_callback(update, context, spin_bot, ADMIN_USER_ID),
        pattern='^spin_all$'))
    application.add_handler(CallbackQueryHandler(
        lambda update, context: spin_again_callback(update, context, spin_bot),
        pattern='^spin_again$'))

    # Admin Commands
    application.add_handler(CommandHandler('pendingspins',
        lambda update, context: pendingspins_command(update, context, spin_bot, is_admin)))
    application.add_handler(CommandHandler('approvespin',
        lambda update, context: approvespin_command(update, context, spin_bot, is_admin)))
    application.add_handler(CommandHandler('addspins',
        lambda update, context: addspins_command(update, context, spin_bot, is_admin)))
    application.add_handler(CommandHandler('spinsstats',
        lambda update, context: spinsstats_command(update, context, spin_bot, is_admin)))
    # ========================================

    # Run the bot
    application.run_polling()
```

---

## 🎁 BONUS: Auto-Give Spins on Deposits

### Find your deposit approval code

Search for where you approve deposits (look for "Approved" message to users).

**ADD THIS CODE AFTER DEPOSIT IS APPROVED:**

```python
# Add free spins from deposit
try:
    spins_awarded = await spin_bot.add_spins_from_deposit(
        user_id=int(deposit_user_id),  # Replace with your variable
        username=deposit_username,      # Replace with your variable
        amount_mvr=float(deposit_amount) # Replace with your variable
    )

    if spins_awarded > 0:
        try:
            spin_message = (
                f"🎁 *BONUS REWARD* 🎁\n\n"
                f"You received *{spins_awarded} FREE SPINS*\\!\n\n"
                f"🎰 Play now: /freespins\n\n"
                f"Win amazing prizes:\n"
                f"• iPhone 17 Pro Max\n"
                f"• MacBook Pro\n"
                f"• Apple Watch Ultra\n"
                f"• Chips \\& more\\!\n\n"
                f"Good luck\\! 🍀"
            )
            await context.bot.send_message(
                chat_id=int(deposit_user_id),
                text=spin_message,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error notifying user about spins: {e}")
except Exception as e:
    logger.error(f"Error adding spins from deposit: {e}")
```

**Note:** Replace `deposit_user_id`, `deposit_username`, `deposit_amount` with your actual variable names.

---

## ✅ Testing

### 1. Start the bot
```bash
python bot.py
```

### 2. Test as admin (in Telegram)
```
/addspins <your_user_id> 50
```

### 3. Test as user
```
/freespins
```

Click "Spin 10x" and see the results!

### 4. Test admin panel
```
/spinsstats
/pendingspins
```

---

## 🎨 Customization (Optional)

### Want different prizes?

Edit **spin_bot.py** line 50-65:
```python
self.prize_wheel = [
    {"name": "🎁 iPhone 17 Pro Max", "type": "display", "chips": 500, "weight": 1},
    # Add your own prizes here!
]
```

### Want different deposit amounts?

Edit **spin_bot.py** line 30-48:
```python
self.deposit_tiers = [
    (200, 1),   # 200 MVR = 1 spin
    (400, 2),   # 400 MVR = 2 spins
    # Add your own tiers!
]
```

### Want different milestone rewards?

Edit **spin_bot.py** line 68-72:
```python
self.milestone_rewards = {
    10: 2,      # Every 10 spins = 2 chips
    100: 50,    # Every 100 spins = 50 chips
    500: 100    # Every 500 spins = 100 chips
}
```

---

## 📊 What Gets Created in Google Sheets

When you run the bot, these sheets will automatically be created:

1. **Spin Users** - Tracks each user's spins and chips
2. **Spin Logs** - Records every spin result
3. **Milestone Rewards** - Logs bonus rewards

No manual setup needed! ✨

---

## 🎯 User Commands

| Command | Description |
|---------|-------------|
| `/freespins` | Open spin wheel and play |

---

## 🛡️ Admin Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/pendingspins` | View rewards needing approval | `/pendingspins` |
| `/approvespin <id>` | Approve a reward | `/approvespin SPIN123...` |
| `/addspins <user> <count>` | Give spins to user | `/addspins 123456789 50` |
| `/spinsstats` | View statistics | `/spinsstats` |

---

## 💡 How Admin Approval Works

1. User wins iPhone (display prize)
2. Admin gets notification
3. Admin runs `/pendingspins`
4. Admin runs `/approvespin SPIN123...`
5. Admin manually adds chips to user's PPPoker account
6. User gets automatic notification: "Your reward has been approved!"

**Why manual?** Display prizes (iPhone, MacBook) are for show. Actual reward is chips that admin adds manually.

---

## 🔥 Marketing Your Spin Bot

### Announcement Template:
```
🎰 NEW FEATURE: FREE SPINS! 🎰

Get FREE spins with EVERY deposit!

💰 Deposit → Spins:
• 2,000 MVR = 25 spins
• 5,000 MVR = 60 spins
• 10,000 MVR = 120 spins
• 20,000+ MVR = 250 spins

🎁 Win BIG Prizes:
• iPhone 17 Pro Max
• MacBook Pro
• Apple Watch Ultra
• AirPods Pro
• Instant Chips

🎉 BONUS Rewards:
• Every 10 spins → +2 chips
• Every 100 spins → +50 chips
• Every 500 spins → +100 chips

Try it NOW: /freespins
```

---

## ❓ FAQ

**Q: Do users actually get iPhones?**
A: No, display prizes are for excitement. Users get chips that admin adds manually to their PPPoker account.

**Q: Can I change the prizes?**
A: Yes! Edit spin_bot.py and adjust the prize_wheel array.

**Q: What if I make a mistake?**
A: Don't worry! Your original bot.py is untouched. Just remove the code you added.

**Q: Do I need to create Google Sheets manually?**
A: No! The sheets are created automatically when bot starts.

**Q: How do I test without real deposits?**
A: Use `/addspins <your_id> 100` to give yourself test spins.

---

## 🆘 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'spin_bot'"
**Fix:** Make sure `spin_bot.py` is in the same directory as `bot.py`

### Error: "sheets.get_spin_user not found"
**Fix:** Make sure you updated `sheets_manager.py` (already done!)

### Bot starts but /freespins doesn't work
**Fix:** Check that you added the command handlers in main()

### Users not getting spins from deposits
**Fix:** Add the deposit integration code (Step 3 above)

---

## 📞 Need Help?

1. Read **SPIN_BOT_README.md** for full documentation
2. Check **INTEGRATION_CODE.txt** for exact code snippets
3. Review **SPIN_BOT_SUMMARY.md** for quick reference

---

## ✨ You're Done!

After following steps 1-3, your spin bot is ready!

**Test it now:**
1. Start bot
2. `/addspins <your_id> 50`
3. `/freespins`
4. Click "Spin 10x"
5. Enjoy! 🎰

---

**Total Time:** 5-10 minutes
**Difficulty:** Easy (just copy & paste)
**Risk:** None (original bot untouched)

🎰 **Happy Spinning!** 🎰
