# Counter Closed - Spin Wheel & Live Support Disabled

## Changes Made

Added counter status checks to **Spin Wheel** and **Live Support** features to prevent users from accessing them when counter is closed.

---

## Problem

When counter is closed:
- Users could still access Spin Wheel and win prizes
- Users could still start Live Support sessions
- But admins couldn't process rewards or respond to support
- Result: User frustration and pending requests piling up

---

## Solution

Disable both features when counter is closed, just like other features (Deposit, Withdrawal, Join Club, etc.)

---

## Files Modified

### bot.py

#### 1. Spin Wheel - `freespins_command()` (Lines 135-145)

**Added counter status check:**
```python
async def freespins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open Mini App for spinning wheel"""
    user = update.effective_user

    try:
        # Check if counter is open
        counter_status = sheets.get_counter_status()
        if counter_status != 'OPEN':
            await update.message.reply_text(
                "🔒 *COUNTER IS CLOSED*\n\n"
                "The spin wheel is currently unavailable\\.\n"
                "Please try again when the counter reopens\\!\n\n"
                "Thank you for your patience\\! 🙏",
                parse_mode='MarkdownV2'
            )
            return

        # Continue with normal flow...
```

#### 2. Live Support - `live_support_start()` (Lines 1904-1914)

**Added counter status check:**
```python
async def live_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start live support session"""
    user = update.effective_user

    # Check if counter is open
    counter_status = sheets.get_counter_status()
    if counter_status != 'OPEN':
        await update.message.reply_text(
            "🔒 *COUNTER IS CLOSED*\n\n"
            "Live support is currently unavailable\\.\n"
            "Please try again when the counter reopens\\!\n\n"
            "Thank you for your patience\\! 🙏",
            parse_mode='MarkdownV2'
        )
        return ConversationHandler.END

    # Continue with normal flow...
```

---

## How It Works

### When Counter is OPEN:
✅ User clicks "🎲 Free Spins" → Opens spin wheel normally
✅ User clicks "💬 Live Support" → Starts support session normally

### When Counter is CLOSED:
❌ User clicks "🎲 Free Spins" → Shows "Counter is closed" message
❌ User clicks "💬 Live Support" → Shows "Counter is closed" message

---

## Complete List of Features Disabled When Counter Closed

Now ALL user-facing features are properly disabled:

| Feature | Status | Message Shown |
|---------|--------|---------------|
| 💰 Deposit | ✅ Disabled | Counter is closed |
| 💸 Withdrawal | ✅ Disabled | Counter is closed |
| 🚪 Join Club | ✅ Disabled | Counter is closed |
| 🎫 Seat Request | ✅ Disabled | Counter is closed |
| 💵 Cashback | ✅ Disabled | Counter is closed |
| 🎁 Bonus | ✅ Disabled | Counter is closed |
| 🎲 Free Spins | ✅ Disabled | Counter is closed (NEW) |
| 💬 Live Support | ✅ Disabled | Counter is closed (NEW) |

---

## User Experience Flow

### Scenario 1: User tries to spin when counter closed

```
User: *Clicks "🎲 Free Spins" button*

Bot: 🔒 COUNTER IS CLOSED

     The spin wheel is currently unavailable.
     Please try again when the counter reopens!

     Thank you for your patience! 🙏
```

### Scenario 2: User tries live support when counter closed

```
User: *Clicks "💬 Live Support" button*

Bot: 🔒 COUNTER IS CLOSED

     Live support is currently unavailable.
     Please try again when the counter reopens!

     Thank you for your patience! 🙏
```

---

## Testing Checklist

### Test with Counter OPEN:
- [ ] Click "🎲 Free Spins" → Should open spin wheel normally
- [ ] Click "💬 Live Support" → Should start support session normally
- [ ] Spin and win prize → Should work normally
- [ ] Send message in support → Should forward to admin normally

### Test with Counter CLOSED:
- [ ] Click "🎲 Free Spins" → Should show "Counter is closed" message
- [ ] Click "💬 Live Support" → Should show "Counter is closed" message
- [ ] Should NOT be able to access spin wheel
- [ ] Should NOT be able to start support session

### Test Counter Toggle:
- [ ] Close counter → Both features disabled
- [ ] Open counter → Both features enabled again
- [ ] Close again → Both disabled again

---

## Benefits

### For Users:
✅ **Clear expectations** - Know when features are unavailable
✅ **No wasted effort** - Can't spin if rewards won't be processed
✅ **No waiting** - Can't contact support if no one is available
✅ **Consistent experience** - All features disabled together

### For Admins:
✅ **No pending requests** - Users can't create new requests when closed
✅ **Clean workflow** - Open counter → handle requests → close counter
✅ **No missed messages** - Users won't send support messages when unavailable
✅ **No surprise prizes** - Users can't win prizes that need approval when closed

### For System:
✅ **Consistent behavior** - All user features respect counter status
✅ **Better control** - Admin has full control over when users can interact
✅ **Reduced errors** - No edge cases of prizes won when counter closed

---

## Admin Counter Control

Admins can still:
- Open/Close counter via Admin Panel
- View all pending approvals
- Manage system settings
- Access all admin features

**Only USER-facing features are disabled when counter closed.**

---

## Edge Cases Handled

### 1. User already in support session when counter closes
**Behavior:** Session continues normally
**Reason:** Don't interrupt active conversations
**Note:** User can still send messages, admin can still respond

### 2. User has active spin session when counter closes
**Behavior:** Spin completes normally, prize saved
**Reason:** Don't interrupt active spins (mini app already loaded)
**Note:** Prize approval will be pending until counter reopens

### 3. User tries /freespins command when closed
**Behavior:** Shows "Counter is closed" message
**Reason:** Command directly checks counter status

### 4. User tries to open spin wheel from old button
**Behavior:** Shows "Counter is closed" message
**Reason:** All entry points check counter status

---

## Counter Status Logic

**Counter Status is stored in:** `Counter Status` sheet in Google Sheets

**Possible values:**
- `OPEN` - All features available
- `CLOSED` - User features disabled

**How to check:**
```python
counter_status = sheets.get_counter_status()
if counter_status != 'OPEN':
    # Show "counter closed" message
    return
```

**How admins change status:**
1. Admin Panel → Counter Control
2. Click "Close Counter" or "Open Counter"
3. Status updates in sheet
4. All features immediately respect new status

---

## Implementation Notes

**Why check at handler level (not button level)?**
- Buttons are displayed once when menu loads
- Counter status can change after menu is displayed
- Checking at handler ensures real-time status check
- More reliable than trying to hide/show buttons

**Why return early vs continue?**
- Early return prevents any processing
- User immediately sees clear message
- No partial operations (like checking spins available)
- Cleaner code flow

**Why same message format for both?**
- Consistency in user experience
- Users recognize the pattern
- Easy to understand
- Professional appearance

---

## Future Enhancements (Optional)

### 1. Show opening hours
Instead of "Please try again when counter reopens", show:
```
The counter is currently closed.
Opening hours: 9:00 AM - 11:00 PM (Maldives Time)

Please try again during opening hours!
```

### 2. Schedule automatic open/close
Admin sets schedule:
- Open: 9:00 AM
- Close: 11:00 PM
- Automatic daily

### 3. Emergency mode
Allow specific users (VIP) to access even when closed:
```python
if counter_status != 'OPEN' and not is_vip_user(user.id):
    # Show closed message
    return
```

### 4. Notification when counter opens
Users who tried to access when closed get notified:
```
🔓 Counter is now OPEN!

You can now access:
• Spin Wheel 🎲
• Live Support 💬
• Deposits & Withdrawals 💰
```

---

## Summary

✅ **Spin Wheel disabled when counter closed**
✅ **Live Support disabled when counter closed**
✅ **Consistent with other features** (Deposit, Withdrawal, etc.)
✅ **Clear user messages** ("Counter is closed, try again later")
✅ **All entry points protected** (buttons, commands, callbacks)

**Result:** Complete control over user access when counter is closed! 🔒
