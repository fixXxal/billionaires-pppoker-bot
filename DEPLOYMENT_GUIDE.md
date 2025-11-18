# 🚀 Mini App Deployment Guide

Quick guides for deploying your spin wheel to different platforms.

## Option 1: ngrok (Fastest - For Testing)

**Time**: 2 minutes | **Cost**: Free | **Best for**: Testing

```bash
# 1. Install ngrok
# Download from https://ngrok.com/download

# 2. Start your Mini App server
python mini_app_server.py

# 3. In another terminal, expose it
ngrok http 5000

# 4. Copy the HTTPS URL
# Example: https://abc123.ngrok-free.app

# 5. Update bot.py line 120
mini_app_url = "https://abc123.ngrok-free.app"

# 6. Start your bot
python bot.py
```

**Pros**:
- ✅ Super fast setup
- ✅ No account needed
- ✅ Works immediately

**Cons**:
- ❌ URL changes every restart
- ❌ Not for production
- ❌ Free tier has limits

---

## Option 2: Vercel (Recommended for Production)

**Time**: 10 minutes | **Cost**: Free | **Best for**: Production

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

Create `requirements.txt` (rename from mini_app_requirements.txt):
```
Flask==3.0.0
flask-cors==4.0.0
python-dotenv==1.0.0
gspread==5.12.0
oauth2client==4.1.3
```

### Step 2: Deploy

```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Login
vercel login

# 3. Deploy
vercel

# 4. Follow prompts, then deploy to production
vercel --prod
```

### Step 3: Configure

Your URL will be like: `https://your-project.vercel.app`

Update bot.py:
```python
mini_app_url = "https://your-project.vercel.app"
```

**Pros**:
- ✅ Free forever
- ✅ Automatic HTTPS
- ✅ Fast global CDN
- ✅ Easy updates

**Cons**:
- ❌ Requires GitHub/GitLab
- ❌ Learning curve

---

## Option 3: Render (Easy + Free)

**Time**: 5 minutes | **Cost**: Free | **Best for**: Simple production

### Step 1: Create Account
1. Go to https://render.com
2. Sign up with GitHub

### Step 2: Create Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repo
3. Configure:
   - **Name**: spin-wheel-api
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn mini_app_server:app`
   - **Instance Type**: Free

### Step 3: Add Environment Variables
Add your `.env` variables in Render dashboard:
- `ADMIN_USER_ID`
- `TIMEZONE`
- Google Sheets credentials (as JSON)

### Step 4: Deploy
Click "Create Web Service"

Your URL: `https://spin-wheel-api.onrender.com`

**Pros**:
- ✅ Free tier available
- ✅ Easy setup
- ✅ Auto-deploy from GitHub

**Cons**:
- ❌ Free tier sleeps after inactivity
- ❌ First request may be slow

---

## Option 4: Railway (Modern + Simple)

**Time**: 5 minutes | **Cost**: Free ($5 credit) | **Best for**: Modern apps

### Step 1: Setup
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
railway init

# 4. Add Python buildpack
railway add

# 5. Deploy
railway up
```

### Step 2: Configure
```bash
# Set environment variables
railway variables set ADMIN_USER_ID=your_id
railway variables set TIMEZONE="Indian/Maldives"
```

Your URL: `https://your-app.railway.app`

**Pros**:
- ✅ Modern platform
- ✅ Great DX
- ✅ Free $5/month credit

**Cons**:
- ❌ Credit runs out (need to add card)

---

## Option 5: Your Own VPS (Full Control)

**Time**: 30 minutes | **Cost**: $5-10/month | **Best for**: Full control

### Requirements
- Ubuntu/Debian VPS
- Domain name (optional)

### Setup

```bash
# 1. SSH into your server
ssh user@your-server.com

# 2. Install dependencies
sudo apt update
sudo apt install python3 python3-pip nginx certbot python3-certbot-nginx

# 3. Upload your files
# Use scp, git, or FTP

# 4. Install Python packages
cd /path/to/app
pip3 install -r requirements.txt gunicorn

# 5. Create systemd service
sudo nano /etc/systemd/system/miniapp.service
```

Service file:
```ini
[Unit]
Description=Mini App Server
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/app
Environment="PATH=/usr/local/bin"
ExecStart=/usr/local/bin/gunicorn -w 4 -b 127.0.0.1:5000 mini_app_server:app

[Install]
WantedBy=multi-user.target
```

```bash
# 6. Configure nginx
sudo nano /etc/nginx/sites-available/miniapp
```

Nginx config:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# 7. Enable site
sudo ln -s /etc/nginx/sites-available/miniapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 8. Get SSL certificate
sudo certbot --nginx -d your-domain.com

# 9. Start service
sudo systemctl start miniapp
sudo systemctl enable miniapp
```

Your URL: `https://your-domain.com`

**Pros**:
- ✅ Full control
- ✅ No platform limits
- ✅ Can run bot on same server

**Cons**:
- ❌ More complex
- ❌ Need to manage server
- ❌ Monthly cost

---

## Option 6: PythonAnywhere (Simplest)

**Time**: 5 minutes | **Cost**: Free | **Best for**: Beginners

### Step 1: Sign Up
1. Go to https://www.pythonanywhere.com
2. Create free account

### Step 2: Upload Files
1. Go to "Files" tab
2. Upload `mini_app_server.py`, `spin_wheel.html`, requirements

### Step 3: Install Packages
1. Open "Bash" console
2. Run:
```bash
pip3 install --user -r requirements.txt
```

### Step 4: Create Web App
1. Go to "Web" tab
2. "Add a new web app"
3. Choose Flask
4. Set:
   - **Source code**: `/home/yourusername/miniapp`
   - **Working directory**: Same
   - **WSGI file**: Point to `mini_app_server.py`

Your URL: `https://yourusername.pythonanywhere.com`

**Pros**:
- ✅ Easiest setup
- ✅ Free tier
- ✅ No server management

**Cons**:
- ❌ Limited free tier
- ❌ Slower than others
- ❌ Can't run bot simultaneously on free tier

---

## Comparison Table

| Platform | Cost | Speed | Ease | Best For |
|----------|------|-------|------|----------|
| ngrok | Free | ⚡ Fast | ⭐⭐⭐⭐⭐ Easy | Testing |
| Vercel | Free | ⚡⚡⚡ Very Fast | ⭐⭐⭐⭐ Moderate | Production |
| Render | Free | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ Easy | Simple apps |
| Railway | $5/mo | ⚡⚡⚡ Fast | ⭐⭐⭐⭐ Moderate | Modern apps |
| VPS | $5-10/mo | ⚡⚡ Medium | ⭐⭐ Hard | Full control |
| PythonAnywhere | Free | ⚡ Slow | ⭐⭐⭐⭐⭐ Easiest | Learning |

---

## Recommended Path

### For Testing (Right Now)
```bash
# 1. Use ngrok
python mini_app_server.py  # Terminal 1
ngrok http 5000            # Terminal 2
# Update bot.py with ngrok URL
python bot.py              # Terminal 3
```

### For Production (After Testing)
```bash
# 1. Use Vercel (recommended)
vercel login
vercel
vercel --prod
# Update bot.py with Vercel URL
```

---

## Post-Deployment Checklist

- [ ] Mini App server is running
- [ ] HTTPS URL is accessible
- [ ] Updated `mini_app_url` in bot.py (line ~120)
- [ ] Bot is running
- [ ] Tested `/freespins` command
- [ ] Mini App opens successfully
- [ ] Spin works and shows results
- [ ] Admin notifications work
- [ ] Google Sheets updates correctly

---

## Need Help?

1. **Server won't start**: Check logs for errors
2. **Mini App won't open**: Verify HTTPS URL is correct
3. **CORS errors**: Ensure flask-cors is installed
4. **Database errors**: Check Google Sheets credentials

---

**Choose the option that fits your needs and budget. All options will work!** 🚀
