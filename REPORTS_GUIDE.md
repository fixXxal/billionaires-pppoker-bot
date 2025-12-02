# Financial Reports System - Usage Guide

## Overview
The Billionaires PPPoker Bot now includes comprehensive financial reporting system for admins to track all business metrics.

## Features

### 📊 Report Types
- **Daily Reports** - Today's transactions and activities
- **Weekly Reports** - Last 7 days summary
- **Monthly Reports** - Last 30 days overview
- **6-Month Reports** - Half-year analysis
- **Yearly Reports** - Full year statistics
- **Custom Range** - Any date range you specify

### 💰 Tracked Metrics

#### Financial Summary
- Total Income (Deposits + Investment Profits)
- Total Expenses (Withdrawals + Losses + Cashback + Credits)
- Net Profit/Loss
- Profit Margin %

#### Detailed Breakdowns
1. **Deposits**: Approved, pending, rejected counts and amounts
2. **Withdrawals**: Approved, pending, rejected counts and amounts
3. **50/50 Investments**:
   - Total investment amount
   - Profit vs Loss tracking
   - Active/Completed/Lost counts
   - Net profit from investments
4. **Cashback**: Total given and pending amounts
5. **Spin Rewards**: Total chips awarded, spin counts
6. **User Credits**: Bonuses and adjustments given
7. **User Growth**: New users in period
8. **Inventory**: Purchases and sales tracking

## How to Access Reports

### Option 1: API Endpoint (JSON Format)
Access the JSON API for programmatic use:

```
GET /api/reports/financial/?period=daily
GET /api/reports/financial/?period=weekly
GET /api/reports/financial/?period=monthly
GET /api/reports/financial/?period=6months
GET /api/reports/financial/?period=yearly
GET /api/reports/financial/?period=custom&start_date=2025-01-01&end_date=2025-12-02
```

**Example Response:**
```json
{
  "period": "daily",
  "start_date": "2025-12-02",
  "end_date": "2025-12-02",
  "summary": {
    "total_income": 15000.00,
    "total_expenses": 8000.00,
    "net_profit": 7000.00,
    "profit_margin": "46.67%"
  },
  "deposits": {
    "total_approved": 10000.00,
    "approved_count": 25
  },
  ...
}
```

### Option 2: Visual Dashboard (HTML)
Access the beautiful web dashboard:

```
http://your-domain.com/api/reports/dashboard/
http://your-domain.com/api/reports/dashboard/?period=weekly
http://your-domain.com/api/reports/dashboard/?period=monthly
http://your-domain.com/api/reports/dashboard/?period=custom&start_date=2025-01-01&end_date=2025-12-02
```

The dashboard includes:
- 🎨 Beautiful gradient design
- 📱 Mobile responsive
- 🎯 Easy period selection buttons
- 📅 Custom date range picker
- 📊 Color-coded cards for quick insights
- ✅ Status badges for pending/approved items

## URL Examples

### For Local Development
```
http://localhost:8000/api/reports/financial/?period=daily
http://localhost:8000/api/reports/dashboard/
http://localhost:8000/api/reports/dashboard/?period=monthly
```

### For Production (Railway)
```
https://your-app.up.railway.app/api/reports/financial/?period=daily
https://your-app.up.railway.app/api/reports/dashboard/
https://your-app.up.railway.app/api/reports/dashboard/?period=yearly
```

## Understanding the Profit/Loss Calculation

### Income Sources
1. **Approved Deposits** - Money coming from users
2. **Investment Profits** - 50/50 investment returns

### Expense Sources
1. **Approved Withdrawals** - Money going to users
2. **Investment Losses** - Losses from 50/50 investments
3. **Cashback Given** - Promotional cashback to users
4. **User Credits** - Bonuses, refunds, adjustments

### Net Profit Formula
```
Net Profit = (Deposits + Investment Profits) - (Withdrawals + Investment Losses + Cashback + Credits)
```

### 50/50 Investment Profit Calculation
For each completed investment:
- Club invests: 100 MVR
- Player returns: 1000 MVR
- Net profit: 900 MVR
- Split 50/50:
  - Player gets: 450 MVR
  - Club gets: 450 MVR profit + 100 MVR investment back = **550 MVR total**
- **Club Profit recorded**: 550 MVR ✅

## Security Notes
⚠️ These reports contain sensitive financial data. Ensure:
1. Only admins have access to the URLs
2. Add authentication/authorization if exposed publicly
3. Use HTTPS in production
4. Monitor access logs for unauthorized attempts

## Future Enhancements (Planned)
- [ ] Export to PDF
- [ ] Export to Excel/CSV
- [ ] Email scheduled reports to admins
- [ ] Charts and graphs visualization
- [ ] Comparison with previous periods
- [ ] Transaction-level drill-down

## Support
For issues or questions about reports, check:
1. Django admin logs
2. API response error messages
3. Database connectivity
4. Date format validation (YYYY-MM-DD)
