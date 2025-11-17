# 🎰 Telegram Spin Bot - Complete Guide

## 📋 Overview

A secure, feature-rich spin wheel bot integrated with your Billionaires PPPoker Telegram Bot. Users earn free spins from deposits and can win chips with automatic milestone bonuses.

## ✨ Features

### For Users:
- 🎲 **Free Spins from Deposits** - Automatic spins based on deposit amount
- 🎰 **Spin Wheel** - Win premium prizes (display) and chips (actual rewards)
- ⚡ **Auto-Spin** - Spin 1x, 10x, 50x, 100x, or ALL at once
- 🎁 **Milestone Bonuses** - Extra chips at 10, 100, and 500 spins
- 📊 **Stats Tracking** - View total spins, chips earned, and more

### For Admins:
- ✅ **Reward Approval System** - Approve display prizes
- 📈 **Statistics Dashboard** - Track usage and rewards
- 🎯 **Manual Spin Grants** - Give spins to any user
- 🔒 **Anti-Cheat Protection** - Prevents abuse and manipulation

## 💰 Deposit to Spins Conversion

| Deposit Amount (MVR) | Free Spins |
|---------------------|------------|
| 200                 | 1          |
| 400                 | 2          |
| 600                 | 3          |
| 800                 | 4          |
| 1,000               | 5          |
| 1,200               | 6          |
| 1,400               | 7          |
| 1,600               | 8          |
| 1,800               | 9          |
| 2,000               | 25         |
| 3,000               | 35         |
| 4,000               | 45         |
| 5,000               | 60         |
| 6,000               | 75         |
| 7,000               | 90         |
| 8,000               | 105        |
| 9,000               | 115        |
| 10,000              | 120        |
| 12,000              | 150        |
| 14,000              | 180        |
| 16,000              | 210        |
| 18,000              | 230        |
| 20,000+             | 250        |

## 🎁 Milestone Rewards

| Milestone | Bonus Chips |
|-----------|-------------|
| Every 10 spins  | +2 chips    |
| Every 100 spins | +50 chips   |
| Every 500 spins | +100 chips  |

**Example:** User spins 100 times:
- Gets 10x milestone bonus (10 spins × 2 chips = 20 chips)
- Gets 100 spins milestone bonus (+50 chips)
- **Total milestone bonus: 70 chips**

## 🎰 Prize Wheel Configuration

### Display Prizes (Require Admin Approval):
- 🎁 iPhone 17 Pro Max - 500 chips (very rare)
- 💻 MacBook Pro - 1,000 chips (very rare)
- ⌚ Apple Watch Ultra - 300 chips (rare)
- 🎧 AirPods Pro - 150 chips (uncommon)

### Instant Chip Rewards (Auto-approved):
- 💎 100 Chips (uncommon)
- 💰 50 Chips (common)
- 🪙 25 Chips (common)
- 🎯 10 Chips (very common)
- ⭐ 5 Chips (very common)
- 🎲 2 Chips (very common)

## 👤 User Commands

### `/freespins`
Opens the spin wheel interface. Shows:
- Available spins
- Total spins used
- Total chips earned
- Spin options (1x, 10x, 50x, 100x, ALL)

**Example:**
```
User: /freespins

Bot: 🎰 FREE SPINS 🎰

👤 John
🎲 Available Spins: 25
📊 Total Spins Used: 0
💎 Total Chips Earned: 0

🎁 Win Big Prizes:
• iPhone 17 Pro Max
• MacBook Pro
• Apple Watch Ultra
• AirPods Pro
• Chips (instantly added)

⭐ Choose how many spins:
[🎯 Spin 1x] [🎰 Spin 10x] [⚡ Spin ALL (25x)]
```

## 🛡️ Admin Commands

### `/pendingspins`
View all pending spin rewards that need approval.

**Example:**
```
Admin: /pendingspins

Bot: 🎰 PENDING SPIN REWARDS 🎰

1. User: @john_doe
   🆔 123456789
   🎁 Prize: 🎁 iPhone 17 Pro Max
   💎 Chips: 500
   📅 Date: 2025-01-15 14:30:00
   🔖 ID: SPIN20250115143000

Use /approvespin <spin_id> to approve a reward.
```

### `/approvespin <spin_id>`
Approve a pending reward and notify the user.

**Example:**
```
Admin: /approvespin SPIN20250115143000

Bot: ✅ Reward approved!

User: @john_doe
Prize: 🎁 iPhone 17 Pro Max
Chips: 500

User has been notified.
```

**User receives:**
```
✅ REWARD APPROVED ✅

🎁 Your spin reward has been approved!

Prize: 🎁 iPhone 17 Pro Max
💎 Chips: 500

Your chips have been added to your PPPoker account!
Thank you for playing! 🎰
```

### `/addspins <user_id> <count>`
Manually add spins to a user (for promotions, compensation, etc).

**Example:**
```
Admin: /addspins 123456789 50

Bot: ✅ Added 50 spins to user 123456789!
```

### `/spinsstats`
View overall spin bot statistics.

**Example:**
```
Admin: /spinsstats

Bot: 📊 SPIN BOT STATISTICS 📊

👥 Total Users: 42
🎲 Total Spins Used: 1,250
💎 Total Chips Awarded: 8,450
🎁 Pending Rewards: 3
✅ Approved Rewards: 15

🔝 Top Spinners:
1. john_doe - 250 spins
2. jane_smith - 180 spins
3. poker_king - 150 spins
```

## 📊 Google Sheets Structure

### Spin Users Sheet
Tracks user spin data:
- User ID
- Username
- Available Spins
- Total Spins Used
- Total Chips Earned
- Total Deposit (MVR)
- Created At
- Last Spin At

### Spin Logs Sheet
Records every spin:
- Spin ID
- User ID
- Username
- Prize
- Prize Type (display/chips)
- Chips
- Spin Hash (anti-cheat)
- Spun At
- Approved (Yes/No/Auto)
- Approved By

### Milestone Rewards Sheet
Logs milestone bonuses:
- User ID
- Username
- Milestone Type (10_spins/100_spins/500_spins)
- Milestone Count
- Chips Awarded
- Triggered At Spin Count
- Created At

## 🔒 Security Features

### Anti-Cheat Measures:
1. **Unique Spin Hashing** - Each spin has a unique SHA-256 hash
2. **Rate Limiting** - Max 50 spins per 60 seconds
3. **Timestamp Validation** - Server-side timestamp on every spin
4. **Balance Verification** - Checks available spins before processing

### Audit Trail:
- Every spin is logged with timestamp and hash
- Milestone rewards are tracked separately
- Admin approvals are recorded with admin ID

## 🚀 Installation & Integration

### 1. Files Added:
- ✅ `spin_bot.py` - Main spin bot logic
- ✅ `bot_integration.py` - Integration instructions
- ✅ `SPIN_BOT_README.md` - This file

### 2. Files Modified:
- ✅ `sheets_manager.py` - Added spin-related methods and sheets

### 3. Integration Steps:

**Step 1:** Import spin bot in `bot.py`:
```python
from spin_bot import SpinBot, freespins_command, spin_callback, spin_again_callback, pendingspins_command, approvespin_command, addspins_command, spinsstats_command
```

**Step 2:** Initialize after sheets manager:
```python
spin_bot = SpinBot(sheets, ADMIN_USER_ID, pytz.timezone(TIMEZONE))
```

**Step 3:** Add command handlers in `main()`:
```python
# Spin Bot Handlers
application.add_handler(CommandHandler('freespins', lambda update, context: freespins_command(update, context, spin_bot)))
application.add_handler(CallbackQueryHandler(lambda update, context: spin_callback(update, context, spin_bot, ADMIN_USER_ID), pattern='^spin_\\d+$'))
application.add_handler(CallbackQueryHandler(lambda update, context: spin_callback(update, context, spin_bot, ADMIN_USER_ID), pattern='^spin_all$'))
application.add_handler(CallbackQueryHandler(lambda update, context: spin_again_callback(update, context, spin_bot), pattern='^spin_again$'))

# Admin Spin Handlers
application.add_handler(CommandHandler('pendingspins', lambda update, context: pendingspins_command(update, context, spin_bot, is_admin)))
application.add_handler(CommandHandler('approvespin', lambda update, context: approvespin_command(update, context, spin_bot, is_admin)))
application.add_handler(CommandHandler('addspins', lambda update, context: addspins_command(update, context, spin_bot, is_admin)))
application.add_handler(CommandHandler('spinsstats', lambda update, context: spinsstats_command(update, context, spin_bot, is_admin)))
```

**Step 4:** Add spins from deposits (in deposit approval handler):
```python
# After approving deposit
spins_awarded = await spin_bot.add_spins_from_deposit(
    user_id=deposit_data['user_id'],
    username=deposit_data['username'],
    amount_mvr=float(deposit_data['amount'])
)

if spins_awarded > 0:
    await context.bot.send_message(
        chat_id=deposit_data['user_id'],
        text=f"🎁 Bonus: You received {spins_awarded} FREE SPINS!\n\nUse /freespins to play and win prizes!"
    )
```

**Step 5:** Update help command:
```python
# User help
"🎰 /freespins - Play the spin wheel and win prizes!"

# Admin help
"🎰 SPIN BOT COMMANDS:\n"
"/pendingspins - View pending rewards\n"
"/approvespin <id> - Approve reward\n"
"/addspins <user> <count> - Add spins\n"
"/spinsstats - View statistics"
```

## 🧪 Testing

### Test User Flow:
1. Admin adds spins: `/addspins <your_user_id> 100`
2. User spins: `/freespins`
3. Select: "Spin 10x"
4. Check results and milestone bonuses
5. Try "Spin ALL" to use remaining spins

### Test Admin Flow:
1. User wins display prize (iPhone, MacBook, etc.)
2. Admin checks: `/pendingspins`
3. Admin approves: `/approvespin SPIN123...`
4. User receives notification
5. Check stats: `/spinsstats`

## 🎨 Customization

### Adjust Prize Probabilities:
Edit `spin_bot.py` line ~50-65:
```python
self.prize_wheel = [
    {"name": "🎁 iPhone", "type": "display", "chips": 500, "weight": 1},  # Increase weight = more common
    # ... adjust weights as needed
]
```

### Modify Deposit Tiers:
Edit `spin_bot.py` line ~30-48:
```python
self.deposit_tiers = [
    (200, 1),   # 200 MVR = 1 spin
    (400, 2),   # 400 MVR = 2 spins
    # ... add your own tiers
]
```

### Change Milestone Rewards:
Edit `spin_bot.py` line ~68-72:
```python
self.milestone_rewards = {
    10: 2,     # Every 10 spins = 2 chips
    100: 50,   # Every 100 spins = 50 chips
    500: 100   # Every 500 spins = 100 chips
}
```

## 📞 Support & Troubleshooting

### Common Issues:

**Issue:** "You don't have any spins available"
- **Solution:** Make a deposit or ask admin to add spins with `/addspins`

**Issue:** Admin not receiving pending reward notifications
- **Solution:** Check `ADMIN_USER_ID` in `.env` file

**Issue:** Sheets not updating
- **Solution:** Check Google Sheets API credentials and permissions

**Issue:** "Too many spins in short time" error
- **Solution:** This is anti-cheat protection. Wait 60 seconds and try again.

### Need Help?
- Check integration file: `bot_integration.py`
- Review code comments in `spin_bot.py`
- Check Google Sheets for data logs

## 📈 Best Practices

### For Admins:
1. ✅ Review pending rewards daily with `/pendingspins`
2. ✅ Monitor statistics weekly with `/spinsstats`
3. ✅ Use `/addspins` for promotions and user retention
4. ✅ Keep backup of Google Sheets data

### For Users:
1. 🎲 Use auto-spin (10x, 100x) for faster gameplay
2. 🎯 Watch for milestone bonuses
3. 💰 Larger deposits = more spins = better rewards
4. 📊 Track your stats in `/freespins`

## 🎉 Marketing Ideas

### Promote the Spin Bot:
1. **Announcement:** "🎰 NEW: Get FREE SPINS with every deposit!"
2. **Highlight:** "Win iPhone 17, MacBook, Apple Watch & more!"
3. **Bonus:** "Every 100 spins = 50 FREE chips!"
4. **Urgency:** "Limited time: 2x spins on deposits over 5000 MVR"

### Engagement Tactics:
- Daily spin challenges
- Leaderboards for top spinners
- Special milestone celebrations (user hits 1000 spins)
- Bonus spin weekends

---

## 📄 License & Credits

Built for Billionaires PPPoker Club Telegram Bot
Secure, scalable, and ready for production use.

**Version:** 1.0.0
**Last Updated:** January 2025

---

🎰 **Happy Spinning!** 🎰
