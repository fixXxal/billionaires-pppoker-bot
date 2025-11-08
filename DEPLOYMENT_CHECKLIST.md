# Deployment Checklist - Billionaires PPPoker Bot

Use this checklist to ensure smooth deployment.

## Pre-Deployment Checklist

### 1. Local Setup ✓

- [ ] Python 3.11+ installed
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with all variables
- [ ] `credentials.json` downloaded from Google Cloud
- [ ] Bot token obtained from BotFather
- [ ] Admin user ID obtained

### 2. Configuration ✓

- [ ] Telegram bot token set in `.env`
- [ ] Admin user ID set in `.env`
- [ ] Google Sheets credentials file path correct
- [ ] Spreadsheet name configured
- [ ] Timezone set correctly
- [ ] Payment accounts configured (or ready to update via bot)

### 3. Testing ✓

Run these tests locally:

- [ ] `python setup_helper.py` - All checks pass
- [ ] `python bot.py` - Bot starts without errors
- [ ] `/start` command works in Telegram
- [ ] Main menu displays correctly
- [ ] Can initiate deposit flow
- [ ] Can initiate withdrawal flow
- [ ] Can initiate join club flow
- [ ] Admin commands work (`/admin`)
- [ ] Payment account updates work
- [ ] Live support works
- [ ] Google Sheets creates all worksheets
- [ ] Admin notifications received

### 4. Google Sheets Setup ✓

- [ ] Service account created
- [ ] Google Sheets API enabled
- [ ] Credentials JSON downloaded
- [ ] Service account email noted (you'll need this)
- [ ] Test spreadsheet creation works

### 5. Security ✓

- [ ] `.gitignore` includes `.env`
- [ ] `.gitignore` includes `credentials.json`
- [ ] Bot token is secret
- [ ] Admin user ID is correct
- [ ] No sensitive data in code

## Railway Deployment Checklist

### 1. GitHub Setup ✓

- [ ] GitHub repository created
- [ ] `.gitignore` configured
- [ ] Code pushed to GitHub
- [ ] No `.env` or `credentials.json` in repo

Commands:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/billionaires-bot.git
git push -u origin main
```

### 2. Railway Setup ✓

- [ ] Railway account created
- [ ] GitHub connected to Railway
- [ ] New project created
- [ ] Repository linked

### 3. Environment Variables ✓

Add these in Railway Variables tab:

- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `ADMIN_USER_ID`
- [ ] `GOOGLE_SHEETS_CREDENTIALS_FILE` (set to `credentials.json`)
- [ ] `SPREADSHEET_NAME`
- [ ] `BML_ACCOUNT`
- [ ] `MIB_ACCOUNT`
- [ ] `USDT_WALLET`
- [ ] `TIMEZONE`

### 4. Credentials File ✓

- [ ] `credentials.json` added via Railway Raw Editor
- [ ] File name is exactly `credentials.json`
- [ ] JSON content is valid

### 5. Deployment ✓

- [ ] Deployment triggered
- [ ] Build succeeds
- [ ] No errors in logs
- [ ] Bot process starts

### 6. Post-Deployment Testing ✓

- [ ] Bot responds to `/start`
- [ ] All menu buttons work
- [ ] Deposit flow works
- [ ] Withdrawal flow works
- [ ] Join club flow works
- [ ] Admin panel accessible
- [ ] Notifications received
- [ ] Google Sheets updates
- [ ] Live support works

## Monitoring Checklist

### Daily Checks

- [ ] Bot is responding
- [ ] No errors in Railway logs
- [ ] Requests being processed
- [ ] Google Sheets updating

### Weekly Checks

- [ ] Review all transactions
- [ ] Check for failed requests
- [ ] Monitor user feedback
- [ ] Update payment accounts if needed

### Monthly Checks

- [ ] Backup Google Sheets
- [ ] Review bot performance
- [ ] Update dependencies if needed
- [ ] Check Railway usage/costs

## Troubleshooting Guide

### Bot Not Responding

1. Check Railway logs
2. Verify bot is running
3. Check environment variables
4. Restart deployment

### Google Sheets Errors

1. Verify credentials.json
2. Check service account permissions
3. Ensure API is enabled
4. Check spreadsheet name

### Admin Functions Not Working

1. Verify admin user ID
2. Check if using correct account
3. Review admin panel code
4. Check callback handlers

### Deployment Failures

1. Check build logs
2. Verify requirements.txt
3. Check Python version (runtime.txt)
4. Review Procfile

## Emergency Procedures

### Bot Down

1. Check Railway status
2. Review logs for errors
3. Restart deployment
4. Check environment variables

### Data Loss Prevention

1. Export Google Sheets regularly
2. Keep local backup of configuration
3. Document all changes
4. Test before deploying updates

### Security Breach

1. Immediately revoke bot token
2. Create new bot
3. Update all environment variables
4. Review access logs
5. Notify users if necessary

## Update Procedure

### Updating Bot Code

1. Test changes locally
2. Commit to GitHub
3. Push to main branch
4. Railway auto-deploys
5. Monitor deployment
6. Test in production

### Updating Dependencies

1. Update `requirements.txt`
2. Test locally
3. Deploy to Railway
4. Monitor for issues

### Updating Environment Variables

1. Go to Railway → Variables
2. Update variable
3. Redeploy if needed
4. Verify changes

## Success Metrics

Track these to ensure bot is working well:

- [ ] Response time < 2 seconds
- [ ] No errors in logs
- [ ] All requests processed within 24 hours
- [ ] Users reporting satisfaction
- [ ] Google Sheets updating correctly
- [ ] Admin can access all features

## Support Resources

- Railway Docs: https://docs.railway.app/
- Telegram Bot API: https://core.telegram.org/bots/api
- Google Sheets API: https://developers.google.com/sheets/api
- Python Telegram Bot: https://docs.python-telegram-bot.org/

---

**Last Updated:** 2025-01-07

**Version:** 1.0.0

**Status:** ✅ Ready for Deployment
