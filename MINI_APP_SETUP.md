# Spin Wheel Mini App Setup Guide

## Overview
The spin wheel has been converted from text-based to a **visual Mini App** with real spinning wheel animation!

## What Changed

### REMOVED ❌
- Text-based spin animations
- Old spin callback handlers (spin_1, spin_10, etc.)

### KEPT ✅
- All spin logic (eligibility, cooldowns, rewards, milestones)
- Google Sheets integration
- Admin approval system
- Reward distribution

### NEW ✨
- **spin_wheel.html** - Interactive spinning wheel Mini App
- **mini_app_server.py** - Flask API server for the Mini App
- **Modified freespins_command** - Opens Mini App instead of text

## Files Created

1. **spin_wheel.html** - The Mini App interface with:
   - Animated spinning wheel
   - Real-time spin results
   - Confetti effects for wins
   - Mobile-responsive design

2. **mini_app_server.py** - API server that handles:
   - `/api/get_spins` - Get user's available spins
   - `/api/spin` - Process spin requests
   - Serves the HTML file

3. **mini_app_requirements.txt** - Flask dependencies

## Setup Instructions

### Step 1: Install Dependencies

```bash
pip install -r mini_app_requirements.txt
```

### Step 2: Choose a Hosting Option

You need to host the Mini App on an **HTTPS** server. Here are your options:

#### Option A: ngrok (Quick Testing)
```bash
# Install ngrok from https://ngrok.com/
# Run the Flask server
python mini_app_server.py

# In another terminal, expose it
ngrok http 5000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

#### Option B: GitHub Pages (Free, Permanent)
1. Create a GitHub repository
2. Upload `spin_wheel.html` to the repository
3. Enable GitHub Pages in Settings
4. Your URL will be: `https://yourusername.github.io/repo-name/spin_wheel.html`

**Note**: With GitHub Pages, you'll need to modify the HTML to make API calls directly to your bot or use a separate API server.

#### Option C: Vercel/Netlify (Free, Recommended)
1. Sign up at vercel.com or netlify.com
2. Deploy the `mini_app_server.py` as a serverless function
3. They provide free HTTPS URLs

#### Option D: Your Own Server
- Deploy `mini_app_server.py` on your VPS
- Use nginx + Let's Encrypt for HTTPS
- Point your domain to the server

### Step 3: Update Bot Configuration

Edit `bot.py` and find line ~120:

```python
mini_app_url = "YOUR_MINI_APP_URL_HERE"
```

Replace with your actual URL, for example:
```python
mini_app_url = "https://abc123.ngrok.io"
# OR
mini_app_url = "https://yourusername.github.io/spin-wheel/spin_wheel.html"
```

### Step 4: Run the Services

#### Terminal 1: Run the Mini App Server
```bash
python mini_app_server.py
```

#### Terminal 2: Run the Bot
```bash
python bot.py
```

#### Terminal 3 (if using ngrok): Expose the server
```bash
ngrok http 5000
```

### Step 5: Test

1. Open your Telegram bot
2. Type `/freespins` or click "🎲 Free Spins" button
3. Click "🎰 Open Spin Wheel 🎰"
4. The Mini App should open with the spinning wheel!
5. Click "SPIN NOW!" to spin

## How It Works

### Flow:
1. User clicks `/freespins`
2. Bot shows button "Open Spin Wheel"
3. Button opens Mini App (HTML page)
4. Mini App:
   - Loads user's available spins via `/api/get_spins`
   - Shows spinning wheel
   - When user clicks SPIN:
     - Calls `/api/spin` to process the spin
     - Backend uses existing `spin_bot.process_spin()` logic
     - Animates the wheel to show result
     - Displays win/loss message
5. Admin gets notified if user wins (same as before)

### Security

The Mini App uses Telegram's `initData` for authentication:
- Telegram sends signed data to verify the user
- You should validate this in production (see TODO in `mini_app_server.py`)

## Troubleshooting

### "Mini App URL not set"
- Make sure you updated line 120 in bot.py with your actual URL

### "CORS Error"
- Flask server has CORS enabled, but check browser console
- Make sure the URL in bot.py matches the server URL exactly

### "No spins available"
- User needs to make a deposit first
- Admin can manually add spins: `/addspins USER_ID AMOUNT`

### "Wheel doesn't spin"
- Check browser console for JavaScript errors
- Verify `/api/spin` endpoint is reachable
- Check mini_app_server.py logs

### "Rewards not working"
- Backend uses the same logic as before
- Check Google Sheets "Milestone Rewards" sheet
- Admin approval still required (same as before)

## Production Deployment

For production:

1. **Use a proper HTTPS domain** (required by Telegram)
2. **Add Telegram data validation** in `mini_app_server.py`
3. **Use a production WSGI server**:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 mini_app_server:app
   ```
4. **Set up monitoring** and logging
5. **Configure firewall** to only allow Telegram IPs (optional)

## Reverting to Old System

If you want to go back to the text-based system:

1. Replace `freespins_command` in bot.py with:
```python
async def freespins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for spin bot freespins command"""
    await spin_bot_module.freespins_command(update, context, spin_bot)
```

2. Remove the Mini App handler:
```python
# Remove this line:
application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_mini_app_data))
```

## Support

If you encounter issues:
1. Check the logs (`mini_app_server.py` and `bot.py`)
2. Verify HTTPS is working
3. Test the `/api/get_spins` endpoint directly
4. Check that Google Sheets API is working

## Next Steps

Optional enhancements you can make:
- Add sound effects to the spin
- Customize the prize wheel colors/design
- Add more animations
- Create a leaderboard view
- Add spin history

---

**That's it! Your bot now has a professional spinning wheel Mini App!** 🎰✨
