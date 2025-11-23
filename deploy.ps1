# Deploy script - commits and pushes all changes to Railway

Write-Host "Checking for changes..." -ForegroundColor Yellow

# Add all changes
git add .

# Show status
git status

# Commit with message
git commit -m "Fix cashback notifications, add duplicate prevention, clean PPPoker IDs

- Added duplicate processing prevention for cashback approvals/rejections
- Fixed user notifications for cashback approval and rejection
- Added clean_pppoker_id() helper to sanitize PPPoker ID inputs
- Applied ID cleaning to deposits, withdrawals, club join, and cashback flows
- Simplified cashback eligibility messages
- Added 'Already Processed' warnings for admins"

# Push to GitHub (Railway will auto-deploy)
git push

Write-Host "`nDone! Railway will auto-deploy in ~1-2 minutes." -ForegroundColor Green
