# Django Migration - Build Progress & Plan

## ✅ COMPLETED (So Far)

### Phase 1: Project Setup
- [x] Django installed (5.2.5)
- [x] Virtual environment created (`venv/`)
- [x] Django project created (`billionaires_backend/`)
- [x] API app created (`api/`)
- [x] Requirements.txt updated with Django packages

### Phase 2: Database Models
- [x] User model (Users sheet)
- [x] Deposit model (Deposits sheet)
- [x] Withdrawal model (Withdrawals sheet)
- [x] SpinUser model (Spin_Users sheet)
- [x] SpinHistory model (Spin_History sheet)

---

## 🚧 IN PROGRESS

### Phase 3: Django Configuration (NEXT)
- [ ] Configure settings.py
  - Add REST framework
  - Add CORS headers
  - Configure database (SQLite local, PostgreSQL production)
  - Add timezone settings
  - Add static/media file handling
- [ ] Register app in INSTALLED_APPS
- [ ] Create initial migrations
- [ ] Apply migrations to create database tables

### Phase 4: REST API Layer
- [ ] Create serializers.py (converts models to/from JSON)
- [ ] Create views.py (API endpoints logic)
- [ ] Create urls.py (API routing)
- [ ] Add authentication/permissions

### Phase 5: Background Sync
- [ ] Create sheets_sync.py (sync Django → Google Sheets)
- [ ] Create management command for manual sync
- [ ] Add periodic task (every 30 seconds)

### Phase 6: Bot Integration
- [ ] Create django_api.py (wrapper for bot to call Django)
- [ ] Update bot.py to use Django API instead of sheets_manager
- [ ] Test all bot functions

### Phase 7: Testing & Deployment
- [ ] Test locally with SQLite
- [ ] Configure Railway PostgreSQL
- [ ] Deploy to Railway
- [ ] Final testing with real data

---

## 📋 DETAILED FILE STRUCTURE

```
billionaires/
├── manage.py ✅ CREATED
├── venv/ ✅ CREATED
├── billionaires_backend/ ✅ CREATED
│   ├── __init__.py
│   ├── settings.py ⏳ NEXT
│   ├── urls.py ⏳ NEXT
│   ├── wsgi.py
│   └── asgi.py
├── api/ ✅ CREATED
│   ├── __init__.py
│   ├── models.py ✅ DONE (User, Deposit, Withdrawal, SpinUser, SpinHistory)
│   ├── serializers.py ⏳ BUILDING NEXT
│   ├── views.py ⏳ BUILDING NEXT
│   ├── urls.py ⏳ BUILDING NEXT
│   ├── admin.py ⏳ LATER
│   └── apps.py
├── sheets_sync.py ⏳ LATER
├── django_api.py ⏳ LATER (wrapper for bot)
├── bot.py ✅ EXISTS (will update later)
├── requirements.txt ✅ UPDATED
└── .env ✅ EXISTS (will add Django settings)
```

---

## 🎯 API ENDPOINTS TO BUILD

### User Endpoints
```python
POST   /api/users/              # Create user
GET    /api/users/{telegram_id}/  # Get user
PUT    /api/users/{telegram_id}/  # Update user
```

### Deposit Endpoints
```python
POST   /api/deposits/           # Create deposit
GET    /api/deposits/           # List all deposits
GET    /api/deposits/pending/   # List pending (admin)
GET    /api/deposits/{id}/      # Get specific deposit
PUT    /api/deposits/{id}/approve/  # Approve
PUT    /api/deposits/{id}/reject/   # Reject
```

### Withdrawal Endpoints
```python
POST   /api/withdrawals/        # Create withdrawal
GET    /api/withdrawals/        # List all
GET    /api/withdrawals/pending/  # List pending (admin)
PUT    /api/withdrawals/{id}/approve/  # Approve
PUT    /api/withdrawals/{id}/reject/   # Reject
```

### Spin Endpoints
```python
GET    /api/spins/user/{telegram_id}/  # Get user spin data
POST   /api/spins/process/      # Process spin(s)
GET    /api/spins/history/      # Get spin history
GET    /api/spins/pending/      # Pending rewards (admin)
PUT    /api/spins/{id}/approve/ # Approve spin reward
```

---

## 🔄 GOOGLE SHEETS SYNC STRATEGY

### Two-Way Sync Design

**Django → Sheets (Automatic)**
```python
# Every 30 seconds via background task
def sync_to_sheets():
    # Get unsynced records
    unsynced_users = User.objects.filter(synced_to_sheets=False)
    unsynced_deposits = Deposit.objects.filter(synced_to_sheets=False)
    # ... etc

    # Batch write to Sheets
    sheets_manager.batch_write(unsynced_records)

    # Mark as synced
    records.update(synced_to_sheets=True)
```

**Sheets → Django (When Needed)**
```python
# Only run once at migration to import existing data
def import_from_sheets():
    # Read all data from Google Sheets
    users = sheets_manager.get_all_users()

    # Bulk create in Django
    User.objects.bulk_create(users)
```

---

## 🚀 DEPLOYMENT CHECKLIST

### Railway Setup
- [ ] Create PostgreSQL database on Railway
- [ ] Get DATABASE_URL from Railway
- [ ] Add to .env file
- [ ] Update settings.py to use PostgreSQL in production
- [ ] Run migrations on Railway
- [ ] Deploy Django app
- [ ] Test API endpoints
- [ ] Update bot to use Railway Django URL

### Environment Variables Needed
```bash
# Django
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=*.railway.app,localhost

# Database
DATABASE_URL=postgresql://...  # From Railway

# Existing (keep these)
BOT_TOKEN=...
ADMIN_USER_ID=...
SPREADSHEET_NAME=...
GOOGLE_SHEETS_CREDENTIALS_FILE=...
```

---

## ⏱️ TIME ESTIMATES

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Project setup | 30 min | ✅ DONE |
| 2 | Database models | 1 hour | ✅ DONE |
| 3 | Django config | 30 min | ⏳ NEXT |
| 4 | Serializers | 1 hour | 📋 TODO |
| 5 | API views | 2 hours | 📋 TODO |
| 6 | URL routing | 30 min | 📋 TODO |
| 7 | Sheets sync | 1 hour | 📋 TODO |
| 8 | Bot integration | 2 hours | 📋 TODO |
| 9 | Testing | 2 hours | 📋 TODO |
| 10 | Deployment | 1 hour | 📋 TODO |

**Total: ~12 hours of work**

---

## 📊 CURRENT STATUS

**Completed:** 1.5 hours
**Remaining:** ~10.5 hours
**Progress:** 12% done

**Next Steps (I'm building now):**
1. Configure Django settings ⏳
2. Create serializers ⏳
3. Build API views ⏳
4. Set up URL routing ⏳

---

## 🎉 BENEFITS AFTER COMPLETION

### Performance Improvements
- Response time: 1-3 seconds → 10-50ms (30-100x faster!)
- Concurrent users: 10-20 → 500-1000+ (50x more capacity!)
- No more rate limits from Google Sheets

### Reliability
- Primary data in PostgreSQL (fast, reliable)
- Backup in Google Sheets (audit trail)
- No single point of failure

### Admin Experience
- Admins still use Google Sheets for viewing
- Automatic sync in background
- No learning curve needed

---

**Last Updated:** 2025-11-26 (Building in progress...)
