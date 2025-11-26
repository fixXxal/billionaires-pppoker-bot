# Django + PostgreSQL + Google Sheets Hybrid System
# Migration Plan for Billionaires PPPoker Bot

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot (bot.py)                     │
│                                                               │
│  ┌──────────────────┐              ┌────────────────────┐  │
│  │  User Requests   │─────────────▶│  Django REST API   │  │
│  └──────────────────┘              └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
                    ┌─────────────────────────────────────┐
                    │     PostgreSQL Database (Primary)    │
                    │  - Users                              │
                    │  - Deposits                           │
                    │  - Withdrawals                        │
                    │  - Spin Users                         │
                    │  - Spin History                       │
                    │  - Join Requests                      │
                    └─────────────────────────────────────┘
                                             │
                                             ▼
                    ┌─────────────────────────────────────┐
                    │   Background Sync Task (Celery)      │
                    │   - Syncs Django → Google Sheets     │
                    │   - Non-blocking (doesn't slow users) │
                    └─────────────────────────────────────┘
                                             │
                                             ▼
                    ┌─────────────────────────────────────┐
                    │   Google Sheets (Backup/Reports)     │
                    │   - Admin viewing                     │
                    │   - Audit trail                       │
                    │   - Easy reports                      │
                    └─────────────────────────────────────┘
```

## Benefits

### Performance
- **Fast**: PostgreSQL queries in 10-50ms (vs 1-3 seconds for Sheets)
- **Scalable**: Handle 500-1000+ concurrent users
- **No rate limits**: Unlimited API calls

### Reliability
- **Primary data** in PostgreSQL (fast, reliable)
- **Backup data** in Google Sheets (audit trail)
- **Dual storage** for safety

### Admin Experience
- **Familiar**: Admins still use Google Sheets for viewing/reports
- **Real-time**: Sheets updated automatically in background
- **No learning curve**: Sheets format stays the same

## Project Structure

```
billionaires/
├── manage.py                    # Django management script
├── billionaires_backend/        # Django project folder
│   ├── __init__.py
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Main URL routing
│   ├── wsgi.py                 # WSGI config for deployment
│   └── asgi.py                 # ASGI config
├── api/                         # Django app for REST API
│   ├── __init__.py
│   ├── models.py               # Database models
│   ├── serializers.py          # DRF serializers
│   ├── views.py                # API endpoints
│   ├── urls.py                 # API routing
│   └── tasks.py                # Background sync tasks
├── bot.py                       # Telegram bot (updated to use Django API)
├── sheets_sync.py              # Background sync to Google Sheets
└── requirements.txt            # Updated with Django packages
```

## Database Models

### User Model
```python
class User(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255)
    pppoker_id = models.CharField(max_length=50, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    synced_to_sheets = models.BooleanField(default=False)
```

### Deposit Model
```python
class Deposit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50)  # BTC, USDT, etc.
    account_name = models.CharField(max_length=255)
    proof_image = models.CharField(max_length=500)
    status = models.CharField(max_length=20)  # Pending, Approved, Rejected
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    synced_to_sheets = models.BooleanField(default=False)
```

### Withdrawal Model
```python
class Withdrawal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    synced_to_sheets = models.BooleanField(default=False)
```

### SpinUser Model
```python
class SpinUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    available_spins = models.IntegerField(default=0)
    total_spins_used = models.IntegerField(default=0)
    total_chips_earned = models.IntegerField(default=0)
    synced_to_sheets = models.BooleanField(default=False)
```

### SpinHistory Model
```python
class SpinHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    prize = models.CharField(max_length=100)
    chips = models.IntegerField()
    status = models.CharField(max_length=20)  # Pending, Approved, Auto
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.BigIntegerField(null=True, blank=True)
    synced_to_sheets = models.BooleanField(default=False)
```

## API Endpoints

### User Endpoints
- `POST /api/users/create/` - Create new user
- `GET /api/users/{telegram_id}/` - Get user by Telegram ID
- `PUT /api/users/{telegram_id}/` - Update user info

### Deposit Endpoints
- `POST /api/deposits/` - Create deposit request
- `GET /api/deposits/pending/` - List pending deposits (admin)
- `PUT /api/deposits/{id}/approve/` - Approve deposit
- `PUT /api/deposits/{id}/reject/` - Reject deposit

### Withdrawal Endpoints
- `POST /api/withdrawals/` - Create withdrawal request
- `GET /api/withdrawals/pending/` - List pending withdrawals (admin)
- `PUT /api/withdrawals/{id}/approve/` - Approve withdrawal
- `PUT /api/withdrawals/{id}/reject/` - Reject withdrawal

### Spin Endpoints
- `GET /api/spins/user/{telegram_id}/` - Get user spin data
- `POST /api/spins/process/` - Process spin(s)
- `GET /api/spins/history/{telegram_id}/` - Get spin history
- `GET /api/spins/pending/` - Get pending spin rewards (admin)
- `PUT /api/spins/{id}/approve/` - Approve spin reward

## Background Sync Strategy

### Celery Task (Every 30 seconds)
```python
@celery_app.task
def sync_to_google_sheets():
    # Get all unsynced records
    unsynced_users = User.objects.filter(synced_to_sheets=False)
    unsynced_deposits = Deposit.objects.filter(synced_to_sheets=False)
    unsynced_withdrawals = Withdrawal.objects.filter(synced_to_sheets=False)
    unsynced_spins = SpinHistory.objects.filter(synced_to_sheets=False)

    # Batch sync to Google Sheets
    sheets_manager.batch_sync_users(unsynced_users)
    sheets_manager.batch_sync_deposits(unsynced_deposits)
    sheets_manager.batch_sync_withdrawals(unsynced_withdrawals)
    sheets_manager.batch_sync_spins(unsynced_spins)

    # Mark as synced
    unsynced_users.update(synced_to_sheets=True)
    unsynced_deposits.update(synced_to_sheets=True)
    unsynced_withdrawals.update(synced_to_sheets=True)
    unsynced_spins.update(synced_to_sheets=True)
```

## Migration Steps

### Step 1: Setup Django (Day 1)
1. Create Django project structure
2. Define all database models
3. Create migrations
4. Test locally with SQLite

### Step 2: Create REST API (Day 2)
1. Build all API endpoints
2. Add authentication/authorization
3. Test API with Postman

### Step 3: Update Bot (Day 3)
1. Replace sheets_manager calls with API calls
2. Test bot functionality
3. Ensure backward compatibility

### Step 4: Background Sync (Day 4)
1. Setup Celery + Redis
2. Create sync tasks
3. Test syncing to Google Sheets

### Step 5: Deploy to Railway (Day 5)
1. Configure PostgreSQL on Railway
2. Deploy Django + Bot
3. Test in production
4. Monitor performance

## Rollback Plan

If issues occur:
1. Switch bot back to direct sheets_manager calls
2. Keep Django running in parallel (no data loss)
3. Fix issues and try again
4. Google Sheets always has backup data

## Timeline

- **Day 1-2**: Django setup + models + API
- **Day 3-4**: Bot migration + testing
- **Day 5-6**: Background sync + deployment
- **Day 7**: Final testing + launch

**Total: ~1 week of focused work**

## Success Metrics

After migration:
- ✅ API response time < 100ms (vs 1-3 seconds)
- ✅ Handle 500+ concurrent users
- ✅ Zero Google Sheets rate limit errors
- ✅ Admins can still view data in Sheets
- ✅ All data automatically backed up to Sheets
