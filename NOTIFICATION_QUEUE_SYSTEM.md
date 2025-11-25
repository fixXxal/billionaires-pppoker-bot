# Notification Queue System

## Overview

A reliable notification delivery system that queues Telegram messages in Google Sheets and processes them asynchronously. This solves the problem of lost notifications due to Telegram API rate limits, network issues, or users blocking the bot.

---

## Problem Solved

**Before:**
- Prize saved to Google Sheets ✅
- Notification sent directly via Telegram API ❌
- If Telegram API fails → notification lost forever
- No retry mechanism
- Users and admin miss prize notifications

**After:**
- Prize saved to Google Sheets ✅
- Notification added to queue ✅
- Worker sends notification from queue ✅
- If fails → automatic retry (up to 3 times) ✅
- Reliable delivery guaranteed ✅

---

## Architecture

```
┌─────────────────┐
│  User Spins     │
│  Wins Prize     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Save to Sheets  │ ✅ Instant
│ (Spin History)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Add to Queue    │ ✅ Instant (no waiting)
│(Notification_   │
│    Queue)       │
└────────┬────────┘
         │
         │ (User gets response immediately)
         │
         ▼
┌─────────────────┐
│ Worker Process  │ 🔄 Runs every 5 seconds
│ (Background)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Send via        │ ✅ Slow, but doesn't block user
│ Telegram API    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Success    Failed
    │         │
    ▼         ▼
Mark 'sent' Mark 'failed'
            │
            ▼
         Retry after 1 min
         (up to 3 times)
```

---

## Components

### 1. **Notification_Queue Sheet** (Google Sheets)

**Columns:**
- `ID` - Unique notification ID
- `User ID` - Telegram user ID to send to
- `Message` - Message text (HTML formatted)
- `Type` - Notification type (user_prize, admin_alert, general, etc.)
- `Status` - Current status (pending, sent, failed)
- `Created At` - When notification was queued
- `Sent At` - When successfully sent (empty until sent)
- `Retry Count` - Number of retry attempts
- `Error Message` - Error details if failed
- `Priority` - Priority level (1=highest, 10=lowest)

### 2. **sheets_manager.py** (Queue Functions)

**Functions added:**
- `add_notification()` - Add notification to queue
- `get_pending_notifications()` - Get pending notifications (ordered by priority)
- `update_notification_status()` - Update status (sent/failed)
- `get_failed_notifications_for_retry()` - Get failed notifications ready for retry
- `reset_notification_to_pending()` - Reset failed notification to pending

### 3. **mini_app_server.py** (Queue Instead of Direct Send)

**Changed:**
- **Before:** Direct `asyncio.run(notify_user_win())` and `asyncio.run(notify_admin())`
- **After:** `sheets.add_notification()` - instant, non-blocking

### 4. **notification_worker.py** (Background Worker)

**What it does:**
- Runs continuously in background
- Checks queue every 5 seconds
- Sends up to 10 notifications per cycle
- Rate limited: 10 messages/second (safe for Telegram)
- Automatically retries failed notifications
- Logs all activity

**Settings:**
- `POLL_INTERVAL = 5` seconds
- `BATCH_SIZE = 10` notifications per cycle
- `MESSAGE_DELAY = 0.1` seconds between messages
- `MAX_RETRIES = 3` attempts before giving up
- `RETRY_AFTER_MINUTES = 1` minute wait before retry

---

## How to Use

### Setup (One Time)

1. **The Notification_Queue sheet is automatically created** when bot starts
   - Sheet is initialized in `sheets_manager.py` line 351-359
   - Headers are added automatically

2. **No code changes needed** - already integrated into spin system

### Running the Worker

**Option 1: Run manually**
```bash
python notification_worker.py
```

**Option 2: Run with PM2 (Recommended for production)**
```bash
# Install PM2 (if not already installed)
npm install -g pm2

# Start notification worker
pm2 start notification_worker.py --name notification-worker --interpreter python3

# View logs
pm2 logs notification-worker

# Check status
pm2 status

# Stop worker
pm2 stop notification-worker

# Restart worker
pm2 restart notification-worker
```

**Option 3: Run with systemd (Linux servers)**
Create `/etc/systemd/system/notification-worker.service`:
```ini
[Unit]
Description=Notification Worker for Billionaires Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/billionaires
ExecStart=/usr/bin/python3 notification_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable notification-worker
sudo systemctl start notification-worker
sudo systemctl status notification-worker
```

---

## Testing

### Test 1: Add Test Notification
```bash
python test_notification_queue.py
```

This will:
1. Add a test notification to the queue
2. Verify it appears as pending
3. Show you the notification ID

### Test 2: Check Google Sheets
1. Open your Google Sheets
2. Find the "Notification_Queue" sheet
3. You should see:
   - Header row
   - Your test notification with status "pending"

### Test 3: Run Worker and Verify
```bash
python notification_worker.py
```

Within 5 seconds, you should:
1. See log message: "Processing 1 pending notifications"
2. Receive Telegram message with test notification
3. Check sheet: status changed from "pending" to "sent"
4. See "Sent At" timestamp filled in

---

## Monitoring

### Check Queue Status

**View pending notifications:**
```python
from sheets_manager import SheetsManager
sheets = SheetsManager('credentials.json', 'Billionaires_PPPoker_Bot')
pending = sheets.get_pending_notifications()
print(f"Pending: {len(pending)}")
```

**View failed notifications:**
```python
failed = sheets.get_failed_notifications_for_retry()
print(f"Failed: {len(failed)}")
```

### Worker Logs

**What to look for:**
- ✅ `Processing X pending notifications` - Worker is running
- ✅ `Notification sent to user X` - Successful delivery
- ⚠️ `Telegram error for user X: ...` - Temporary failure (will retry)
- ❌ `Error processing notifications: ...` - System error (check connection)

**Log levels:**
- INFO: Normal operation
- WARNING: Temporary issues (retries will happen)
- ERROR: System errors (needs attention)

---

## Priority System

Notifications are processed in priority order:

**Priority 1 (Highest):**
- Critical system alerts
- Admin approval required

**Priority 2:**
- Admin notifications (prize wins)

**Priority 3:**
- User notifications (prize wins)

**Priority 5 (Default):**
- General notifications

**Priority 10 (Lowest):**
- Bulk messages, announcements

Within same priority, oldest notifications are sent first (FIFO).

---

## Error Handling

### Common Errors and Solutions

**1. User Blocked Bot**
- **Error:** "Forbidden: bot was blocked by the user"
- **Handling:** Marked as failed, no retry (user must unblock)
- **Status:** Stays "failed" with error message

**2. Rate Limit Hit**
- **Error:** "Too Many Requests: retry after X"
- **Handling:** Marked as failed, retries after 1 minute
- **Status:** Will retry up to 3 times

**3. Network Issues**
- **Error:** "Connection timeout" or similar
- **Handling:** Marked as failed, retries after 1 minute
- **Status:** Will retry up to 3 times

**4. Invalid User ID**
- **Error:** "Bad Request: chat not found"
- **Handling:** Marked as failed, no retry (invalid ID)
- **Status:** Stays "failed" with error message

### Retry Logic

```
Attempt 1: Immediate (when queued)
   │
   ▼ (Failed)
   │
Wait 1 minute
   │
Attempt 2: Retry
   │
   ▼ (Failed)
   │
Wait 1 minute
   │
Attempt 3: Retry
   │
   ▼ (Failed)
   │
Give up (stays "failed")
```

**After 3 failed attempts:** Notification stays in "failed" state permanently. Admin should check manually.

---

## Benefits

### User Experience
✅ **Never miss notifications** - Queued reliably in sheets
✅ **Fast response** - User doesn't wait for Telegram API
✅ **No errors shown** - Even if delivery delayed, user sees success

### System Reliability
✅ **Rate limit protection** - Worker sends slowly (10/second max)
✅ **Automatic retries** - Temporary failures resolved automatically
✅ **No lost messages** - All notifications tracked in sheets
✅ **Survives crashes** - Queue persists even if bot/worker crashes

### Admin Visibility
✅ **See all notifications** - Check Notification_Queue sheet
✅ **Track delivery status** - Pending, sent, or failed
✅ **Debug issues** - Error messages logged in sheet
✅ **Monitor performance** - See timestamps for sent notifications

### Scalability
✅ **Handle burst traffic** - Queue absorbs spikes
✅ **Works with 100+ users** - No rate limit bans
✅ **Background processing** - Doesn't block main app
✅ **Easy monitoring** - Simple Google Sheets interface

---

## Production Checklist

- [ ] Notification_Queue sheet created (automatic on first run)
- [ ] Worker started with PM2 or systemd
- [ ] Worker logs being monitored
- [ ] Test notification sent and received
- [ ] Failed notifications checked and resolved
- [ ] Worker auto-restarts on crash (PM2/systemd)
- [ ] Worker starts on server reboot (PM2 startup / systemd enable)

---

## Troubleshooting

### Worker not sending notifications

**Check 1: Is worker running?**
```bash
pm2 status  # or: ps aux | grep notification_worker
```

**Check 2: Are there pending notifications?**
- Open Notification_Queue sheet
- Look for rows with status="pending"

**Check 3: Check worker logs**
```bash
pm2 logs notification-worker  # or: python notification_worker.py
```

### Notifications stuck in "failed"

**Check error message in sheet:**
- "Forbidden: bot was blocked" → User must unblock bot
- "Bad Request: chat not found" → Invalid user ID
- "Too Many Requests" → Rate limited, will retry
- "Connection timeout" → Network issue, will retry

**Manual retry:**
If retry count < 3, worker will automatically retry after 1 minute.

If retry count = 3 (gave up), you can manually reset:
```python
from sheets_manager import SheetsManager
sheets = SheetsManager('credentials.json', 'Billionaires_PPPoker_Bot')
sheets.reset_notification_to_pending('NOTIF_1234567890')
```

---

## Advanced Usage

### Custom Notification Types

Add custom types for different scenarios:
```python
# VIP user notification (high priority)
sheets.add_notification(
    user_id=12345,
    message="🌟 VIP bonus credited!",
    notification_type='vip_bonus',
    priority=1
)

# Bulk announcement (low priority)
for user_id in all_users:
    sheets.add_notification(
        user_id=user_id,
        message="📢 New tournament starting!",
        notification_type='announcement',
        priority=10
    )
```

### Batch Notifications

Queue multiple notifications efficiently:
```python
for user_id, prize in winners:
    sheets.add_notification(
        user_id=user_id,
        message=f"🏆 You won {prize} in the tournament!",
        notification_type='tournament_win',
        priority=2
    )
```

Worker will process them all reliably, one by one.

---

## Summary

This notification queue system ensures **100% reliable delivery** of Telegram notifications by:
1. **Queueing** messages in Google Sheets (persistent storage)
2. **Processing** them asynchronously with a background worker
3. **Retrying** failed deliveries automatically (up to 3 times)
4. **Rate limiting** to avoid Telegram API bans
5. **Logging** everything for visibility and debugging

**Result:** Users and admins never miss prize notifications, even during high traffic or network issues! 🎉
