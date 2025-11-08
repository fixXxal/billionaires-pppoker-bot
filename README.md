# Billionaires PPPoker Club Telegram Bot

A comprehensive Telegram bot for managing your PPPoker club with automated deposit, withdrawal, and member management features.

## Features

- **Deposit Management**: Support for BML, MIB, and USDT payments with payment slip uploads
- **Withdrawal Processing**: Secure withdrawals with account name verification
- **Club Join Requests**: Automated member onboarding workflow
- **Admin Panel**: Interactive admin interface for approving/rejecting requests
- **Live Support**: Direct chat connection between users and admin
- **Google Sheets Integration**: All data stored in Google Sheets for easy access
- **Payment Account Management**: Update payment details directly from Telegram
- **24/7 Availability**: Runs continuously on Railway platform

## Project Structure

```
billionaires/
├── bot.py                  # Main bot file with user-facing features
├── admin_panel.py          # Admin panel and approval workflows
├── sheets_manager.py       # Google Sheets integration
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables (create this)
├── credentials.json       # Google Sheets credentials (create this)
├── Procfile              # Railway deployment config
├── runtime.txt           # Python version specification
└── README.md             # This file
```

## Setup Guide

### Step 1: Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the prompts to name your bot
4. Copy the **Bot Token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Send `/mybots` → Select your bot → Bot Settings → Allow Groups → Turn Off (optional)

### Step 2: Get Your Telegram User ID

1. Open Telegram and search for [@userinfobot](https://t.me/userinfobot)
2. Start the bot and it will show your User ID
3. Copy your **User ID** (a number like: `123456789`)

### Step 3: Set Up Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Sheets API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"
4. Create Service Account Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Fill in the service account details
   - Click "Create and Continue"
   - Skip granting additional access (click "Continue" then "Done")
5. Generate JSON Key:
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" → "Create new key"
   - Select "JSON" format
   - Download the file and rename it to `credentials.json`
   - Place it in your project folder

### Step 4: Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` file with your details:
   ```env
   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
   ADMIN_USER_ID=your_telegram_user_id

   # Google Sheets Configuration
   GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
   SPREADSHEET_NAME=Billionaires_PPPoker_Bot

   # Payment Account Details (Initial Values)
   BML_ACCOUNT=7730000123456
   MIB_ACCOUNT=7760000123456
   USDT_WALLET=TXxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # Timezone
   TIMEZONE=Indian/Maldives
   ```

### Step 5: Install Dependencies

Make sure you have Python 3.11+ installed, then:

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 6: Test Locally

```bash
python bot.py
```

If everything is configured correctly, you should see:
```
🤖 Billionaires PPPoker Bot is running...
```

Open Telegram, find your bot, and send `/start` to test!

### Step 7: Deploy to Railway

#### Option A: Deploy via GitHub (Recommended)

1. Create a new GitHub repository
2. Push your code to GitHub (excluding `.env` and `credentials.json`):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/billionaires-bot.git
   git push -u origin main
   ```

3. Go to [Railway.app](https://railway.app/)
4. Sign up/Login with GitHub
5. Click "New Project" → "Deploy from GitHub repo"
6. Select your repository
7. Add Environment Variables:
   - Click on your deployment
   - Go to "Variables" tab
   - Add each variable from your `.env` file
   - For `GOOGLE_SHEETS_CREDENTIALS_FILE`, keep it as `credentials.json`

8. Add Google Credentials:
   - In Railway, go to your project
   - Click "Settings" → "Raw Editor"
   - Create a file named `credentials.json`
   - Paste the contents of your Google credentials JSON file
   - Save

9. Deploy:
   - Railway will automatically deploy your bot
   - Monitor the deployment logs

#### Option B: Deploy via Railway CLI

1. Install Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```

2. Login to Railway:
   ```bash
   railway login
   ```

3. Initialize project:
   ```bash
   railway init
   ```

4. Add environment variables:
   ```bash
   railway variables set TELEGRAM_BOT_TOKEN="your_token"
   railway variables set ADMIN_USER_ID="your_user_id"
   # ... add all other variables
   ```

5. Deploy:
   ```bash
   railway up
   ```

## Using the Bot

### For Users

- **/start** - Start the bot and see the main menu
- **/help** - Get help and instructions
- **💰 Deposit** - Make a deposit to your account
- **💸 Withdrawal** - Request a withdrawal
- **🎮 Join Club** - Request to join the PPPoker club
- **📊 My Info** - View your account information
- **💬 Live Support** - Chat directly with admin
- **/endsupport** - End live support session

### For Admin

- **/admin** - Open admin panel
- **/update_bml [number]** - Update BML account number
- **/update_mib [number]** - Update MIB account number
- **/update_usdt [address]** - Update USDT wallet address

### Admin Panel Features

The admin panel provides an interactive interface to:
- View and approve/reject pending deposits
- View and process pending withdrawals
- View and approve/reject club join requests
- View current payment accounts
- Navigate through multiple pending requests

## Workflow Explanations

### Deposit Workflow

1. User clicks "💰 Deposit"
2. User selects payment method (BML/MIB/USDT)
3. Bot shows payment account details
4. User enters deposit amount
5. User enters PPPoker ID
6. User enters account name (saved for future withdrawals)
7. User uploads payment slip or TXID
8. Bot creates request and notifies admin
9. Admin approves/rejects via admin panel
10. User receives notification of approval/rejection

### Withdrawal Workflow

1. User clicks "💸 Withdrawal"
2. User selects payment method
3. User enters withdrawal amount
4. User enters PPPoker ID
5. User enters account number
6. Bot verifies account name matches deposit account
7. Bot creates request and notifies admin
8. Admin processes via admin panel
9. User receives notification of completion/rejection

### Join Club Workflow

1. User clicks "🎮 Join Club"
2. User enters PPPoker ID
3. Bot creates request and notifies admin
4. Admin approves/rejects via admin panel
5. User receives notification

### Live Support Workflow

1. User clicks "💬 Live Support"
2. Support session starts
3. User messages are forwarded to admin
4. Admin can reply directly
5. User types `/endsupport` to end session

## Google Sheets Structure

The bot automatically creates a spreadsheet with the following worksheets:

### Users Worksheet
- User ID, Username, First Name, Last Name
- PPPoker ID, Registered At, Status, Account Name

### Deposits Worksheet
- Request ID, User ID, Username, PPPoker ID
- Amount, Payment Method, Account Name, Transaction ID/Slip
- Status, Requested At, Processed At, Processed By, Notes

### Withdrawals Worksheet
- Request ID, User ID, Username, PPPoker ID
- Amount, Payment Method, Account Name, Account Number
- Status, Requested At, Processed At, Processed By, Notes

### Join Requests Worksheet
- Request ID, User ID, Username, First Name, Last Name
- PPPoker ID, Status, Requested At, Processed At, Processed By

### Payment Accounts Worksheet
- Payment Method, Account Number, Updated At

## Security Considerations

1. **Never commit** `.env` or `credentials.json` to GitHub
2. Keep your bot token secret
3. Only share your admin user ID with trusted administrators
4. Regularly backup your Google Sheets data
5. Monitor the bot logs for suspicious activity

## Troubleshooting

### Bot not responding
- Check if the bot process is running
- Verify your bot token is correct
- Check Railway logs for errors

### Google Sheets errors
- Verify credentials.json is valid
- Make sure the service account email has edit access to the spreadsheet
- Check if the Google Sheets API is enabled

### Admin panel not working
- Verify your ADMIN_USER_ID is correct
- Check if you're using the correct Telegram account

### Railway deployment issues
- Check environment variables are set correctly
- Verify credentials.json is uploaded
- Review deployment logs for errors

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify all configuration settings
3. Test locally before deploying

## License

This project is created for the Billionaires PPPoker Club. All rights reserved.

## Version

Current Version: 1.0.0

## Updates

To update your bot:
1. Pull the latest code from your repository
2. Update dependencies: `pip install -r requirements.txt --upgrade`
3. Test locally
4. Push to GitHub (Railway will auto-deploy)

---

**Built with Python and python-telegram-bot library**

**Powered by Railway for 24/7 uptime**
