# Quick Start Guide - Billionaires PPPoker Bot

## 5-Minute Setup

### 1. Get Your Bot Token (2 minutes)

1. Open Telegram → Search for `@BotFather`
2. Send: `/newbot`
3. Name your bot: `Billionaires Club Bot`
4. Username: `billionaires_pppoker_bot` (must be unique)
5. **Copy the token** - save it!

### 2. Get Your Admin User ID (30 seconds)

1. Search for `@userinfobot` in Telegram
2. Start it
3. **Copy your ID number**

### 3. Setup Google Sheets (2 minutes)

1. Go to: https://console.cloud.google.com/
2. Create new project: "Billionaires Bot"
3. Enable "Google Sheets API"
4. Create Service Account:
   - APIs & Services → Credentials
   - Create Credentials → Service Account
   - Name it "bot-service"
   - Create and continue → Done
5. Click on service account → Keys → Add Key → JSON
6. **Download the JSON file** → Rename to `credentials.json`
7. Place `credentials.json` in your bot folder

### 4. Configure the Bot (1 minute)

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=paste_your_bot_token_here
ADMIN_USER_ID=paste_your_user_id_here
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
SPREADSHEET_NAME=Billionaires_PPPoker_Bot
BML_ACCOUNT=7730000123456
MIB_ACCOUNT=7760000123456
USDT_WALLET=TXxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TIMEZONE=Indian/Maldives
```

### 5. Install & Run (2 minutes)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

You should see: `🤖 Billionaires PPPoker Bot is running...`

### 6. Test It!

1. Open Telegram
2. Search for your bot
3. Send `/start`
4. Try "💰 Deposit"

## Deploy to Railway (5 minutes)

### Quick Railway Deployment

1. Go to https://railway.app/
2. Sign up with GitHub
3. New Project → Deploy from GitHub
4. Connect your GitHub account
5. Push your code to GitHub first:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/billionaires-bot.git
git push -u origin main
```

6. Select your repo in Railway
7. Add variables (from your `.env` file):
   - Click Variables tab
   - Add each variable
8. Add `credentials.json`:
   - Settings → Raw Editor
   - New file: `credentials.json`
   - Paste your JSON content
   - Save
9. Deploy!

Your bot is now live 24/7!

## First Time Usage

### As Admin:

1. Open bot in Telegram
2. Send `/start`
3. Send `/admin` to see admin panel
4. Update payment accounts:
   ```
   /update_bml 7730000123456
   /update_mib 7760000123456
   /update_usdt TXyourwalletaddresshere
   ```

### Share with Users:

Send them your bot username: `@your_bot_username`

They can:
- Make deposits
- Request withdrawals
- Join the club
- Contact support

## Common Issues

**Bot not responding?**
- Check if bot is running: Look for "🤖 Billionaires PPPoker Bot is running..."
- Verify token is correct in `.env`

**Google Sheets error?**
- Make sure `credentials.json` is in the same folder as `bot.py`
- Check file name is exactly `credentials.json`

**Admin commands not working?**
- Verify your user ID is correct
- Make sure you're using the right Telegram account

## Next Steps

1. Test all features locally
2. Configure payment accounts
3. Deploy to Railway
4. Share bot with your club members
5. Monitor Google Sheets for all transactions

## Support Commands

```
/start - Start the bot
/help - Get help
/admin - Admin panel (admin only)
/update_bml [number] - Update BML account
/update_mib [number] - Update MIB account
/update_usdt [address] - Update USDT wallet
/endsupport - End support chat
```

---

**That's it! Your bot is ready to manage your PPPoker club!** 🎰
