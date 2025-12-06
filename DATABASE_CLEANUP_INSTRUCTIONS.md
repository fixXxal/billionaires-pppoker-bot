# Database Cleanup for Production Launch

## ⚠️ IMPORTANT - Read Before Running

This cleanup script will **DELETE ALL TEST DATA** from your database to prepare for going live with real users.

### What Will Be Deleted:
- ✅ All test users (friends/family accounts)
- ✅ All deposits (test transactions)
- ✅ All withdrawals (test transactions)
- ✅ All spin history (test spins)
- ✅ All spin users (test spin accounts)
- ✅ All join requests (test requests)
- ✅ All seat requests (test requests)
- ✅ All cashback requests (test requests)
- ✅ All support messages (test chats)
- ✅ All 50/50 investments (test investments)
- ✅ All user credits (test credits)
- ✅ All inventory transactions (test transactions)
- ✅ All club balances (test balances)

### What Will Be Kept:
- ✅ Admin accounts (you and super admin)
- ✅ Exchange rates
- ✅ Counter status settings
- ✅ Promo codes (if configured)
- ✅ Spin awards configuration
- ✅ Payment accounts

---

## How to Run the Cleanup

### Step 1: Preview What Will Be Deleted (DRY RUN)

First, run the command WITHOUT `--confirm` to see what will be deleted:

```bash
cd /mnt/c/billionaires
python manage.py cleanup_test_data
```

This will show you:
- How many users will be deleted
- How many transactions will be deleted
- Total records to be removed

**Nothing is deleted in this step - it's just a preview!**

---

### Step 2: Actually Perform the Cleanup

When you're ready to delete everything and go live:

```bash
python manage.py cleanup_test_data --confirm
```

You will be asked to type `DELETE ALL TEST DATA` to confirm.

**This action CANNOT be undone!**

---

## Example Output

### Dry Run (Preview):
```
==============================================================
DATABASE CLEANUP - TEST DATA REMOVAL
==============================================================

Current Database Contents:
  👥 Admins: 2 (WILL BE KEPT)
  👤 Users: 15
  💰 Deposits: 47
  💸 Withdrawals: 12
  🎰 Spin Users: 8
  🎲 Spin History: 234
  📊 Spin Usage: 45
  🚪 Join Requests: 3
  💺 Seat Requests: 7
  🎁 Cashback Requests: 2
  💬 Support Messages: 89
  💎 50/50 Investments: 5
  💳 User Credits: 15
  📦 Inventory Transactions: 0
  🏦 Club Balances: 1

  🗑️  TOTAL RECORDS TO DELETE: 483

==============================================================
DRY RUN MODE - Nothing was deleted
==============================================================

To actually perform the cleanup, run:
  python manage.py cleanup_test_data --confirm
```

### Actual Cleanup:
```
⚠️  WARNING: This will PERMANENTLY DELETE all test data!
⚠️  483 records will be deleted
⚠️  This action CANNOT be undone!

Type "DELETE ALL TEST DATA" to confirm: DELETE ALL TEST DATA

🗑️  Starting cleanup...
  Deleting Support Messages...
    ✅ Deleted 89 support messages
  Deleting 50/50 Investments...
    ✅ Deleted 5 investments
  ...

✅ CLEANUP COMPLETE!
✅ Total records deleted: 483

✅ Kept: 2 admin accounts
✅ Kept: All system settings (exchange rates, promo codes, etc.)

🎉 Database is now clean and ready for production users!
```

---

## After Cleanup - Verify Everything

### 1. Check Django Admin
- Login to `/api/admin/`
- Verify users list is empty (except admins)
- Verify deposits/withdrawals are empty
- Verify spin history is empty

### 2. Check Bot Commands
Run these in Telegram bot:
- `/stats` - Should show 0 users, 0 transactions
- `/pendingspins` - Should show no pending spins
- `/pendingdeposits` - Should show no pending deposits

### 3. Test with Fresh User
Have a real user (not from your test group):
- Start the bot with `/start`
- Register as new user
- Try a small deposit/withdrawal
- Verify everything works

---

## Rollback Plan

**IMPORTANT**: There is NO automatic rollback!

Before running cleanup:
1. Make a backup of your database (Railway should have automatic backups)
2. Or export important data if needed

To restore from Railway backup:
1. Go to Railway dashboard
2. Click on your database
3. Go to "Backups" tab
4. Restore from a backup before cleanup

---

## When to Run This

Run this cleanup **ONCE** before going live with real users:
- ✅ After all testing is complete
- ✅ After verifying all features work
- ✅ Before announcing to real users
- ✅ When you're ready for production launch

**DO NOT run this on a live production database with real users!**

---

## Questions?

If something goes wrong or you need help:
1. Check Railway logs
2. Check Django admin panel
3. Restore from database backup if needed
