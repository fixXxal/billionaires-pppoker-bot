# 🔧 Troubleshooting Notifications Not Showing

## ❓ Problem: Deposit notifications not showing to admin

### **Quick Fixes (Try these first):**

## 1️⃣ **Test if Bot Can Send to You**

**Send this command in your bot:**
```
/test
```

**What should happen:**
- You should receive a test notification with buttons
- It will show your Admin ID

**If you DON'T receive it:**
- Problem: Bot can't send messages to your admin account
- **Solution:** See "Fix Admin ID" below

**If you DO receive it:**
- Bot CAN send to you
- Problem is elsewhere
- Continue to next steps

---

## 2️⃣ **Check Your Admin ID**

**Your Admin ID in .env:** `5465086879`

**To verify it's correct:**

1. Open Telegram
2. Search for `@userinfobot`
3. Start it
4. Compare the ID it shows with `5465086879`

**If IDs don't match:**

1. Open `.env` file
2. Change this line:
   ```env
   ADMIN_USER_ID=5465086879
   ```
   To your correct ID (from @userinfobot)
3. Save file
4. Restart bot:
   ```powershell
   # Stop bot (Ctrl+C)
   python bot.py
   ```

---

## 3️⃣ **Check Bot is Running**

Make sure you see:
```
🤖 Billionaires PPPoker Bot is running...
```

**If not:**
- Bot crashed
- Check error messages
- Restart bot

---

## 4️⃣ **Test Deposit Flow**

1. Use another Telegram account (or ask someone)
2. Start your bot
3. Click "💰 Deposit"
4. Complete the full flow
5. Upload a photo

**Watch your terminal/logs for:**
```
INFO: Deposit notification sent to admin for DEP...
INFO: Deposit photo sent to admin for DEP...
```

**If you see these logs:**
- Notification WAS sent
- Check if you blocked the bot?
- Check Telegram spam folder?

**If you see ERROR:**
- Note the error message
- Share it for help

---

## 5️⃣ **Check if You Blocked the Bot**

In Telegram:
1. Find your bot
2. Make sure you haven't blocked it
3. Send `/start` to restart conversation
4. Try `/test` again

---

## 6️⃣ **Verify Bot Token**

**Check `.env` file:**
```env
TELEGRAM_BOT_TOKEN=7236744913:AAGUfV8Fd5wM_DtY6yRAUl85IRZvukVallM
```

**Make sure:**
- Token is correct
- No extra spaces
- No quotes around it

---

## 🐛 **Common Issues & Solutions**

### **Issue 1: "Chat not found" error**

**Cause:** Admin ID is wrong

**Solution:**
1. Get correct ID from @userinfobot
2. Update `.env`
3. Restart bot

---

### **Issue 2: Bot receives deposit but admin doesn't**

**Cause:** Bot token or admin ID mismatch

**Solution:**
1. Run `/test` command
2. Check logs for errors
3. Verify admin ID matches

---

### **Issue 3: Photo not forwarded**

**Cause:** Photo handling error

**Solution:**
- Check bot logs for "Deposit photo sent"
- Try uploading as document instead
- Check file size (max 20MB)

---

### **Issue 4: Buttons not showing**

**Cause:** Old version of python-telegram-bot

**Solution:**
```powershell
pip install --upgrade python-telegram-bot
```

---

## 📝 **Debugging Steps**

### **Step 1: Test Command**
```
/test
```
Result: ✅ or ❌?

### **Step 2: Check Logs**
When someone makes deposit, look for:
```
INFO: Deposit notification sent to admin for DEP...
```

### **Step 3: Check Admin ID**
Compare `.env` with @userinfobot

### **Step 4: Restart Bot**
```powershell
python bot.py
```

### **Step 5: Test Again**
Make test deposit

---

## ✅ **If Everything Works:**

You should see:

**When deposit submitted:**
```
🔔 NEW DEPOSIT REQUEST

Request ID: DEP20250107...
User: John Doe
Amount: 1000 MVR
Method: BML
PPPoker ID: 12345678

[✅ Approve]  [❌ Reject]

📸 Deposit Proof for DEP...
(Photo below)
```

---

## 🆘 **Still Not Working?**

**Check these:**

1. **Bot running?**
   ```powershell
   python bot.py
   ```

2. **Correct admin account?**
   - Are you logged into Telegram with ID: 5465086879?
   - Or using different account?

3. **Bot started?**
   - Have you sent `/start` to your bot?

4. **Python version?**
   ```powershell
   python --version
   ```
   Should be 3.11 or 3.12

5. **Dependencies installed?**
   ```powershell
   pip install -r requirements.txt
   ```

---

## 📞 **Need More Help?**

**Share these details:**
1. Output of `/test` command
2. Bot logs (copy terminal output)
3. Your admin ID from @userinfobot
4. Admin ID in `.env` file
5. Any error messages

---

## 🎯 **Quick Checklist**

- [ ] Bot is running
- [ ] `/test` command works
- [ ] Admin ID matches @userinfobot
- [ ] Bot token is correct
- [ ] Haven't blocked the bot
- [ ] Sent `/start` to bot
- [ ] Using correct Telegram account

---

**Try `/test` command first - it will tell you if notifications work!** 🔍
