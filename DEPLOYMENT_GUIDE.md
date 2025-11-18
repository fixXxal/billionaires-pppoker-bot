# 🚀 Mini App Deployment Guide

Quick guides for deploying your spin wheel to different platforms.

---

## ⭐ Option 1: Railway (RECOMMENDED)

**Time**: 5 minutes | **Cost**: Free ($5 credit/month) | **Best for**: Production

### Quick Deploy:

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and deploy
cd /mnt/c/billionaires
railway login
railway init
railway up

# 3. Get your permanent URL
railway domain
```

Your URL: `https://your-app.up.railway.app`

Update bot.py line 120:
```python
mini_app_url = "https://your-app.up.railway.app"
```

**Pros**:
- ✅ Permanent URL (never changes!)
- ✅ Free $5/month credit
- ✅ Auto-deploy from GitHub
- ✅ 24/7 uptime
- ✅ Built-in HTTPS

**Cons**:
- ❌ Requires npm installed

**See**: `RAILWAY_QUICK_START.md` for details

---

## Option 2: Vercel (Easy + Free)

**Time**: 10 minutes | **Cost**: Free forever | **Best for**: Production

### Step 1: Prepare Files

Create `vercel.json`:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "mini_app_server.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "mini_app_server.py"
    }
  ]
}
```

### Step 2: Deploy

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel

# Production
vercel --prod
```

Your URL: `https://your-project.vercel.app`

**Pros**:
- ✅ Free forever
- ✅ Automatic HTTPS
- ✅ Fast global CDN
- ✅ Easy updates

**Cons**:
- ❌ Requires GitHub/GitLab
- ❌ Learning curve

---

## Option 3: Render (Simple)

**Time**: 5 minutes | **Cost**: Free | **Best for**: Simple apps

### Steps:

1. Go to https://render.com
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your repo
5. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn mini_app_server:app`
6. Add environment variables from `.env`
7. Deploy!

Your URL: `https://your-app.onrender.com`

**Pros**:
- ✅ Free tier available
- ✅ Easy setup
- ✅ Auto-deploy from GitHub

**Cons**:
- ❌ Free tier sleeps after inactivity
- ❌ First request may be slow

---

## Option 4: Your Own VPS (Full Control)

**Time**: 30 minutes | **Cost**: $5-10/month | **Best for**: Advanced users

```bash
# 1. SSH into server
ssh user@your-server.com

# 2. Install dependencies
sudo apt update
sudo apt install python3 python3-pip nginx certbot

# 3. Upload files & install packages
pip3 install -r requirements.txt gunicorn

# 4. Configure nginx + SSL
sudo certbot --nginx -d your-domain.com

# 5. Start service
sudo systemctl start miniapp
```

**Pros**:
- ✅ Full control
- ✅ No platform limits

**Cons**:
- ❌ Complex setup
- ❌ Need to manage server
- ❌ Monthly cost

---

## Comparison Table

| Platform | Cost | Speed | Ease | URL | Best For |
|----------|------|-------|------|-----|----------|
| **Railway** ⭐ | Free | ⚡⚡⚡ Fast | ⭐⭐⭐⭐ Easy | Permanent | **Production** |
| Vercel | Free | ⚡⚡⚡ Very Fast | ⭐⭐⭐⭐ Moderate | Permanent | Production |
| Render | Free | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ Easy | Permanent | Simple apps |
| VPS | $5-10/mo | ⚡⚡ Medium | ⭐⭐ Hard | Your domain | Full control |

---

## Recommended Path

### For You (You have Railway):
```bash
# Use Railway - 3 commands!
npm install -g @railway/cli
railway login && railway init && railway up
railway domain
```

### For Others:
1. **Start with Railway** (easiest permanent solution)
2. Or use **Vercel** (if comfortable with GitHub)
3. Avoid VPS unless you need full control

---

## Post-Deployment Checklist

- [ ] Service is deployed successfully
- [ ] HTTPS URL is accessible
- [ ] Updated `mini_app_url` in bot.py (line 120)
- [ ] Bot is running
- [ ] Tested `/freespins` command
- [ ] Mini App opens successfully
- [ ] Spin works and shows results

---

**Recommendation: Use Railway - it's the easiest!** 🚂✨
