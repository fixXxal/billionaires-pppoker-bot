# ✅ Complete Mini App Setup - Ready to Go!

## ✅ What I've Already Done For You:

1. ✅ **Installed Flask** - Dependencies are ready in your venv
2. ✅ **Created all files** - Mini App server and HTML are ready
3. ✅ **Modified bot.py** - Mini App integration is done
4. ✅ **Removed old code** - Image sending removed, folder deleted

## 🎯 What YOU Need to Do (3 Steps):

### Step 1: Install ngrok

**Download ngrok**: https://ngrok.com/download

For Windows WSL:
```bash
# Download ngrok for Linux
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Or download directly
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/
```

**Sign up for free account**: https://dashboard.ngrok.com/signup

**Add auth token**:
```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### Step 2: Start Everything (3 Terminals)

**Terminal 1 - Start Mini App Server:**
```bash
cd /mnt/c/billionaires
source venv/bin/activate
python mini_app_server.py
```

**Terminal 2 - Start ngrok:**
```bash
ngrok http 5000
```

Copy the **HTTPS URL** from ngrok output (looks like: `https://abc123.ngrok-free.app`)

**Terminal 3 - Update bot.py and start bot:**
```bash
cd /mnt/c/billionaires
# Edit bot.py line 120 with your ngrok URL
# Then start the bot:
source venv/bin/activate
python bot.py
```

### Step 3: Update bot.py with ngrok URL

Open `bot.py` and change line 120:

**Before:**
```python
mini_app_url = "YOUR_MINI_APP_URL_HERE"  # Line 120
```

**After (use your actual ngrok URL):**
```python
mini_app_url = "https://abc123.ngrok-free.app"  # Replace with YOUR ngrok URL
```

---

## 🚀 Quick Commands (Copy-Paste)

### Option A: Manual Setup (Recommended for learning)

```bash
# Terminal 1
cd /mnt/c/billionaires && source venv/bin/activate && python mini_app_server.py
```

```bash
# Terminal 2
ngrok http 5000
```

```bash
# Terminal 3 (after updating bot.py line 120)
cd /mnt/c/billionaires && source venv/bin/activate && python bot.py
```

### Option B: All-in-One Script (Coming next)

I'll create an automated script for you...

---

## ✅ Verification Checklist

- [ ] Flask installed (already done ✅)
- [ ] ngrok installed
- [ ] ngrok auth token configured
- [ ] Terminal 1: `mini_app_server.py` running
- [ ] Terminal 2: ngrok running, HTTPS URL copied
- [ ] Terminal 3: bot.py line 120 updated with ngrok URL
- [ ] Terminal 3: bot.py running
- [ ] Test: Send `/freespins` in Telegram
- [ ] Test: Click "Open Spin Wheel" button
- [ ] Test: Mini App opens and spins work!

---

## 🆘 Need Help?

**Issue: "ngrok not found"**
- Solution: Install ngrok from https://ngrok.com/download

**Issue: "Flask not installed"**
- Solution: Already installed! Just activate venv: `source venv/bin/activate`

**Issue: "Mini App won't open"**
- Solution: Check that line 120 in bot.py has the correct ngrok HTTPS URL

**Issue: "No spins available"**
- Solution: As admin, add spins: `/addspins YOUR_USER_ID 10`

---

## 📝 What's Next After Setup?

Once everything works with ngrok:

1. **For Production**: Deploy to Vercel (free, permanent URL)
2. **Update bot.py**: Change URL from ngrok to Vercel
3. **Done!** No more ngrok restarts needed

See `DEPLOYMENT_GUIDE.md` for production deployment options.

---

**You're almost there! Just install ngrok and run the 3 terminals!** 🚀
