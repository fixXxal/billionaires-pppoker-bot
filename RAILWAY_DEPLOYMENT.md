# 🚂 Railway Deployment Guide - EASY & PERMANENT!

Since you already have Railway, this is **MUCH BETTER** than ngrok!

## ✅ Advantages of Railway:

- ✅ **Permanent URL** - Never changes!
- ✅ **Free tier** - $5 credit/month
- ✅ **Auto HTTPS** - Built-in SSL
- ✅ **Auto restart** - If server crashes
- ✅ **No terminal needed** - Runs in cloud 24/7

## 🚀 Quick Deployment (3 Steps):

### Step 1: Install Railway CLI

```bash
npm install -g @railway/cli
```

### Step 2: Deploy to Railway

```bash
# 1. Go to your project
cd /mnt/c/billionaires

# 2. Login to Railway
railway login

# 3. Create new project
railway init

# 4. Deploy!
railway up

# 5. Generate domain
railway domain
```

That's it! You'll get a URL like: `https://your-app.up.railway.app`

### Step 3: Update bot.py

Edit `bot.py` line 120:

```python
# Change from:
mini_app_url = "YOUR_MINI_APP_URL_HERE"

# To (use your Railway URL):
mini_app_url = "https://your-app.up.railway.app"
```

Then restart your bot:
```bash
python bot.py
```

---

## 📋 Files I Created For You:

1. ✅ **railway.json** - Railway configuration
2. ✅ **Procfile** - Tells Railway how to start your app
3. ✅ **requirements.txt** - All Python dependencies
4. ✅ **Updated mini_app_server.py** - Works with Railway's PORT

---

## 🌐 Alternative: Using Railway Dashboard

If you prefer GUI over CLI:

### 1. Go to Railway Dashboard
- Visit: https://railway.app/dashboard
- Login with your account

### 2. Create New Project
- Click: "New Project"
- Choose: "Empty Project"

### 3. Add Service
- Click: "+ New"
- Choose: "GitHub Repo" (if your code is on GitHub)
- Or: Use Railway CLI to deploy from local

### 4. Configure Environment Variables
Add these in Railway dashboard:
- `ADMIN_USER_ID` = your admin user ID
- `TIMEZONE` = Indian/Maldives
- Add your Google Sheets credentials (from .env file)

### 5. Deploy
- Railway will auto-deploy
- Click "Generate Domain" to get your URL

---

## 🔧 Environment Variables to Add:

Copy these from your `.env` file to Railway dashboard:

```
ADMIN_USER_ID=your_value
TIMEZONE=Indian/Maldives
GOOGLE_SHEETS_CREDENTIALS={"type": "service_account", ...}
```

**Important**: For Google Sheets credentials, copy the entire JSON as a single line.

---

## ✅ Verification Steps:

1. **Check deployment**: Railway should show "Success"
2. **Test URL**: Visit `https://your-app.up.railway.app` in browser
3. **Should see**: Spinning wheel HTML loads
4. **Update bot.py**: Add your Railway URL to line 120
5. **Test bot**: `/freespins` should open Mini App!

---

## 💰 Cost:

Railway free tier includes:
- $5 credit per month
- Should be enough for Mini App server
- Your bot runs on your computer (no Railway cost)

---

## 🆚 Railway vs ngrok:

| Feature | ngrok | Railway |
|---------|-------|---------|
| URL | Changes every restart | Permanent ✅ |
| Cost | Free | Free ($5 credit) |
| Setup | 2 terminals | One-time deploy |
| Uptime | Must keep running | Always on 24/7 ✅ |
| HTTPS | Yes | Yes |
| Best for | Testing | Production ✅ |

---

## 🎯 Quick Commands:

```bash
# Deploy
railway up

# Check status
railway status

# View logs
railway logs

# Get URL
railway domain

# Set environment variable
railway variables set KEY=VALUE

# Open dashboard
railway open
```

---

## 🚀 After Deployment:

1. ✅ Railway gives you permanent URL
2. ✅ Update `bot.py` line 120 with that URL
3. ✅ Run `python bot.py` on your computer
4. ✅ Mini App works 24/7!

**No more ngrok, no more changing URLs!** 🎉

---

## 🆘 Troubleshooting:

**"Deployment failed"**
- Check logs: `railway logs`
- Verify requirements.txt has all dependencies

**"App won't start"**
- Make sure PORT variable is set (Railway does this automatically)
- Check Procfile exists

**"Can't access app"**
- Generate domain: `railway domain`
- Wait 1-2 minutes after deployment

**"Environment variables not working"**
- Add them in Railway dashboard
- Redeploy: `railway up`

---

## ✨ You're Done!

Once deployed to Railway:
- ✅ Permanent HTTPS URL
- ✅ No need to keep terminal open
- ✅ Works 24/7
- ✅ Just update bot.py and you're good to go!

**Much better than ngrok!** 🚂✨
