# Admin Live Support Guide

## 💬 How to Reply to Users in Live Support

### When a User Contacts Support

When a user clicks "💬 Live Support" and sends you a message, you'll receive:

```
💬 From: John Doe (@johndoe)
User ID: 123456789

I need help with my deposit
```

---

## ✅ How to Reply

### Use the `/reply` Command

**Format:**
```
/reply USER_ID your message here
```

**Example:**
```
/reply 123456789 Hello! I can help you with your deposit. What's your request ID?
```

---

## 📋 Step-by-Step

### Step 1: User Sends Message
User clicks "💬 Live Support" and sends:
```
"I need help with my deposit"
```

### Step 2: You Receive Notification
You get:
```
💬 From: John Doe (@johndoe)
User ID: 123456789

I need help with my deposit
```

### Step 3: Copy the User ID
Copy the number: `123456789`

### Step 4: Send Your Reply
Type in your Telegram:
```
/reply 123456789 Hello John! I can help you. What's your deposit request ID?
```

### Step 5: User Receives Your Message
User sees:
```
💬 Admin Reply:

Hello John! I can help you. What's your deposit request ID?
```

### Step 6: Continue Conversation
- User can send more messages
- You receive each one with their User ID
- Reply using `/reply USER_ID message` each time

### Step 7: End Session
When done, user types `/endsupport` or you can tell them to

---

## 💡 Pro Tips

### 1. Keep User ID Handy
Save the User ID in a note while chatting with them, so you don't have to copy it every time.

### 2. Multi-line Messages
For longer messages, just type normally after the User ID:
```
/reply 123456789 Hi! Your deposit has been approved. The chips will be added to your account within 5 minutes. Let me know if you need anything else!
```

### 3. Multiple Users
If multiple users are in support at once, make sure to use the correct User ID for each reply.

### 4. Check Active Sessions
Only users currently in a support session can receive replies. If they've ended the session, you'll get a warning.

---

## 🎯 Quick Examples

### Example 1: Deposit Help
```
User sends: "My deposit was rejected, why?"
You reply: /reply 123456789 Let me check your deposit. What's your request ID?
User sends: "DEP20250107142530"
You reply: /reply 123456789 I see the issue. The amount didn't match. Please try again with the exact amount.
```

### Example 2: Club Access
```
User sends: "How do I join the club?"
You reply: /reply 123456789 Click "Join Club" in the menu, then enter your PPPoker ID. I'll approve it right away!
```

### Example 3: Payment Issue
```
User sends: "I transferred but didn't get chips"
You reply: /reply 123456789 Don't worry! Let me check. What's your PPPoker ID?
User sends: "12345678"
You reply: /reply 123456789 Found it! I'm processing your deposit now. You'll have chips in 2 minutes.
```

---

## ❌ Error Messages

### "User is not in an active support session"
**Meaning:** User ended their support session or never started one

**Solution:** Ask them to click "💬 Live Support" again

### "Invalid User ID"
**Meaning:** You typed the User ID incorrectly

**Solution:** Make sure you copied the correct number

### "Failed to send message"
**Meaning:** Technical issue (rare)

**Solution:** Try again or restart the bot

---

## 🔄 Complete Workflow

```
┌─────────────────────────────────────────┐
│           USER SIDE                     │
├─────────────────────────────────────────┤
│ 1. Click "💬 Live Support"              │
│ 2. Send message                         │
│ 3. Receive admin reply                  │
│ 4. Continue conversation                │
│ 5. Type /endsupport when done           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│           ADMIN SIDE (YOU)              │
├─────────────────────────────────────────┤
│ 1. Receive notification with User ID    │
│ 2. Type: /reply USER_ID message        │
│ 3. User receives your message           │
│ 4. Repeat step 2 for each reply         │
│ 5. Get notified when user ends session  │
└─────────────────────────────────────────┘
```

---

## 📝 Command Summary

| Command | Usage | Example |
|---------|-------|---------|
| `/reply` | Reply to user | `/reply 123456789 Hello!` |
| `/admin` | Open admin panel | `/admin` |
| `/help` | Show help | `/help` |

---

## 🎓 Practice Examples

Try these commands (replace with real User IDs):

```
/reply 123456789 Hi! How can I help you today?
/reply 123456789 Your deposit has been approved!
/reply 123456789 Please send me your PPPoker ID
/reply 123456789 All set! Your chips are ready. Enjoy the game!
```

---

## 🚨 Important Notes

1. **User ID is Required** - Always include the User ID
2. **Space After User ID** - There must be a space between User ID and message
3. **Active Sessions Only** - Only works if user is in support mode
4. **No Character Limit** - Send messages of any length
5. **Works Anytime** - Reply as soon as you see the message

---

## ✅ Success Checklist

When you reply correctly, you'll see:
```
✅ Message sent to user 123456789
```

The user will see:
```
💬 Admin Reply:

Your message here
```

---

**That's it! You're ready to provide live support!** 🎉

**Quick reminder:** Always use `/reply USER_ID message` format!
