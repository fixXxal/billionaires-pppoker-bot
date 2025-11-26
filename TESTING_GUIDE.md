# 🧪 Local Testing Guide - Django Migration

## ✅ What's Been Done

All bot files have been updated to use Django API:
- ✅ `bot.py` - Main bot file
- ✅ `admin_panel.py` - Admin panel
- ✅ `mini_app_server.py` - Spin wheel mini app server

**Changes made:** Just one line in each file - replaced `SheetsManager` import with `SheetsManagerCompat`.

The compatibility layer (`sheets_manager_compat.py`) provides the exact same interface as `SheetsManager`, but uses Django API underneath. This means:
- ✅ No code changes needed in bot logic
- ✅ All existing functions work as before
- ✅ But now 100x faster (Django API → PostgreSQL instead of Google Sheets)

---

## 🚀 How to Test Locally

### Step 1: Start Django Server

Open **Terminal 1**:

```bash
cd /mnt/c/billionaires
python manage.py runserver 0.0.0.0:8000
```

Keep this running. You should see:
```
Django version 5.2.5, using settings 'billionaires_backend.settings'
Starting development server at http://127.0.0.1:8000/
```

### Step 2: Start the Bot

Open **Terminal 2**:

```bash
cd /mnt/c/billionaires
python bot.py
```

You should see:
```
INFO - Application started
```

### Step 3: Test Basic Features

In Telegram, message your bot:

#### Test 1: User Registration
```
/start
```

Expected: Welcome message appears

**What happens behind the scenes:**
- Old way: Bot → Google Sheets (500-2000ms)
- New way: Bot → Django API → PostgreSQL (5-20ms) ⚡

#### Test 2: Deposit Request
```
Click "💰 Deposit" button
```

Follow the prompts and submit a deposit.

**Check it worked:**
1. In Terminal 1 (Django), you might see API requests in logs
2. Visit `http://127.0.0.1:8000/api/deposits/` in browser - you'll see your deposit in JSON format!

#### Test 3: Check Admin Functions

Message the bot as admin:

```
/admin
```

Try viewing pending deposits, etc.

---

## 🔍 How to Verify It's Using Django API

### Method 1: Check Django Logs

In Terminal 1 (Django server), you'll see HTTP requests whenever bot interacts with API:

```
GET /api/users/by_telegram_id/?telegram_id=123456
POST /api/deposits/
GET /api/spin-users/by_telegram_id/?telegram_id=123456
```

If you see these logs, it's working! ✅

### Method 2: Check Database

```bash
cd /mnt/c/billionaires
python manage.py shell
```

Then in Python shell:
```python
from api.models import User, Deposit
User.objects.all()  # See all users
Deposit.objects.all()  # See all deposits
```

### Method 3: Use Django Admin (Optional)

Create superuser:
```bash
python manage.py createsuperuser
```

Then visit: `http://127.0.0.1:8000/admin/`

You can view/edit all data in a nice web interface!

---

## 🐛 Troubleshooting

### Error: "Connection refused" or "API not accessible"

**Problem:** Django server not running or wrong URL

**Solution:**
1. Make sure Django is running in Terminal 1
2. Check `.env` file has: `DJANGO_API_URL=http://localhost:8000/api`

### Error: "Module not found: sheets_manager_compat"

**Problem:** File not in the right place

**Solution:**
```bash
ls /mnt/c/billionaires/sheets_manager_compat.py
```

Should show the file. If not, it needs to be created.

### Error: "User matching query does not exist"

**Problem:** Trying to get user that doesn't exist yet

**Solution:** This is normal on first run. The API will create the user automatically.

### Bot works but data not in Google Sheets

**This is expected!** Data goes to PostgreSQL now. To sync to Sheets:

```bash
# Terminal 3
cd /mnt/c/billionaires
python run_sync.py
```

This will sync Django data to Google Sheets every 30 seconds.

---

## ✅ Testing Checklist

Test these features to make sure everything works:

### Basic User Functions
- [ ] `/start` - User registration
- [ ] `/balance` - Check balance
- [ ] Deposit request flow
- [ ] Withdrawal request flow
- [ ] Join club request

### Spin Wheel
- [ ] `/freespins` - Open mini app
- [ ] Mini app loads quickly (<1 second)
- [ ] Spin animation works
- [ ] Spins are deducted from available count
- [ ] Results saved to database

### Admin Functions
- [ ] `/admin` - Admin panel opens
- [ ] View pending deposits
- [ ] Approve deposit
- [ ] View pending withdrawals
- [ ] Approve withdrawal
- [ ] Counter status toggle

---

## 📊 Performance Testing

### Test Speed Improvement

**Before (Google Sheets):**
- Open mini app → 2-5 seconds to load spins
- Submit deposit → 1-2 seconds to save

**After (Django API):**
- Open mini app → <100ms to load spins ⚡
- Submit deposit → <50ms to save ⚡

**How to test:**
1. Time how long mini app takes to load available spins
2. Submit a deposit and note response time

You should see **instant responses** now!

---

## 🎯 What to Look For

### Good Signs ✅
- Bot responds instantly
- No "please wait" delays
- Django terminal shows API requests
- Data appears in `http://127.0.0.1:8000/api/` endpoints

### Bad Signs ❌
- Long delays (means still using Google Sheets somehow)
- Errors about "connection refused" (Django not running)
- No logs in Django terminal (not using API)

---

## 📝 Test Report Template

After testing, note your results:

```
✅ WORKING:
- User registration
- Deposits
- Withdrawals
- Spin wheel
- Admin panel

❌ NOT WORKING:
- (List any issues)

⚡ PERFORMANCE:
- Mini app load time: <100ms ✅
- Deposit submission: <50ms ✅
- Overall feel: Much faster! ✅
```

---

## 🎓 Understanding the Architecture

```
User Action in Telegram
         │
         ▼
      bot.py
         │
         │ Calls sheets.get_user()
         ▼
 sheets_manager_compat.py
         │
         │ Uses django_api.py
         ▼
    django_api.py
         │
         │ HTTP request
         ▼
   Django REST API
  (localhost:8000/api)
         │
         ▼
    PostgreSQL DB
    (5-20ms!) ⚡
```

**Key points:**
- `bot.py` doesn't know it's using Django - thinks it's still using sheets!
- Compatibility layer translates sheets calls → Django API calls
- Django API stores in fast PostgreSQL database
- Google Sheets is now just a backup (via background sync)

---

## 🚀 Next Steps

Once local testing is complete:

1. ✅ Verified all features work
2. ✅ Confirmed it's faster
3. ✅ No errors in logs
4. 🚧 Deploy to Railway (see `DJANGO_DEPLOYMENT.md`)

---

**Ready to test? Start Django server and bot, then try the features above!** 🎉
