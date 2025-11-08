# Billionaires PPPoker Bot - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USERS                                │
│              (Telegram App on Mobile/Desktop)               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Telegram Bot API
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   BILLIONAIRES BOT                          │
│                  (Running on Railway)                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              bot.py (Main Application)              │   │
│  │                                                     │   │
│  │  • User Command Handlers                          │   │
│  │  • Conversation Flows (Deposit/Withdrawal/Join)   │   │
│  │  • Live Support System                            │   │
│  │  • Message Routing                                │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                       │
│  ┌──────────────────▼──────────────────────────────────┐   │
│  │         admin_panel.py (Admin Features)           │   │
│  │                                                     │   │
│  │  • Admin Command Handlers                         │   │
│  │  • Approval/Rejection Workflows                   │   │
│  │  • Payment Account Management                     │   │
│  │  • Request Navigation System                      │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                       │
│  ┌──────────────────▼──────────────────────────────────┐   │
│  │      sheets_manager.py (Data Layer)               │   │
│  │                                                     │   │
│  │  • Google Sheets API Integration                  │   │
│  │  • CRUD Operations for All Entities               │   │
│  │  • Data Validation & Formatting                   │   │
│  └──────────────────┬──────────────────────────────────┘   │
└────────────────────┼────────────────────────────────────────┘
                     │
                     │ Google Sheets API
                     │
┌────────────────────▼────────────────────────────────────────┐
│                   GOOGLE SHEETS                             │
│              (Cloud Data Storage)                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │    Users     │  │   Deposits   │  │ Withdrawals  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │ Join Requests│  │   Payment    │                       │
│  │              │  │   Accounts   │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow Diagrams

### Deposit Request Flow

```
User                    Bot                 Sheets              Admin
  │                      │                     │                  │
  ├─ Click "Deposit" ───>│                     │                  │
  │                      │                     │                  │
  │<── Select Method ────┤                     │                  │
  │                      │                     │                  │
  ├─ Choose BML ────────>│                     │                  │
  │                      │                     │                  │
  │<── Enter Amount ─────┤                     │                  │
  │                      │                     │                  │
  ├─ 1000 MVR ──────────>│                     │                  │
  │                      │                     │                  │
  │<── PPPoker ID ───────┤                     │                  │
  │                      │                     │                  │
  ├─ 12345678 ──────────>│                     │                  │
  │                      │                     │                  │
  │<── Account Name ─────┤                     │                  │
  │                      │                     │                  │
  ├─ John Doe ──────────>│                     │                  │
  │                      │                     │                  │
  │<── Upload Slip ──────┤                     │                  │
  │                      │                     │                  │
  ├─ [Photo] ───────────>│                     │                  │
  │                      │                     │                  │
  │                      ├─ Create Request ───>│                  │
  │                      │                     │                  │
  │<── Confirmation ─────┤                     │                  │
  │                      │                     │                  │
  │                      ├─ Notify Admin ──────┼─────────────────>│
  │                      │                     │                  │
  │                      │<──── View in Panel ─┼──────────────────┤
  │                      │                     │                  │
  │                      │     Approve/Reject ─┼──────────────────┤
  │                      │                     │                  │
  │                      ├─ Update Status ─────>│                  │
  │                      │                     │                  │
  │<── Notification ─────┤                     │                  │
  │   (Approved!)        │                     │                  │
```

### Admin Approval Flow

```
Admin                   Bot                 Sheets              User
  │                      │                     │                  │
  ├─ /admin ────────────>│                     │                  │
  │                      │                     │                  │
  │<── Admin Panel ──────┤                     │                  │
  │   • Pending Deposits │                     │                  │
  │   • Withdrawals      │                     │                  │
  │   • Join Requests    │                     │                  │
  │                      │                     │                  │
  ├─ View Deposits ─────>│                     │                  │
  │                      │                     │                  │
  │                      ├─ Get Pending ──────>│                  │
  │                      │<────────────────────┤                  │
  │                      │                     │                  │
  │<── Show Request ─────┤                     │                  │
  │   [Details]          │                     │                  │
  │   [✅ Approve]       │                     │                  │
  │   [❌ Reject]        │                     │                  │
  │                      │                     │                  │
  ├─ Click Approve ─────>│                     │                  │
  │                      │                     │                  │
  │<── Enter Notes ──────┤                     │                  │
  │                      │                     │                  │
  ├─ "Verified" ────────>│                     │                  │
  │                      │                     │                  │
  │                      ├─ Update Status ────>│                  │
  │                      │                     │                  │
  │<── Confirmation ─────┤                     │                  │
  │                      │                     │                  │
  │                      ├─ Notify User ───────┼─────────────────>│
  │                      │                     │                  │
```

## Component Breakdown

### 1. bot.py - Main Application

**Responsibilities:**
- Initialize Telegram bot application
- Handle user commands (/start, /help)
- Manage conversation flows
- Route messages to appropriate handlers
- Implement live support forwarding

**Key Functions:**
- `start()` - Welcome message and main menu
- `deposit_start()` - Initiate deposit flow
- `withdrawal_start()` - Initiate withdrawal flow
- `join_club_start()` - Initiate join request
- `live_support_start()` - Start support session

### 2. admin_panel.py - Admin Interface

**Responsibilities:**
- Provide admin command handlers
- Display pending requests
- Process approvals/rejections
- Manage payment accounts
- Navigate through requests

**Key Functions:**
- `admin_panel()` - Main admin interface
- `admin_view_deposits()` - Show pending deposits
- `deposit_approve()` - Approve deposit request
- `update_bml()` - Update BML account
- `admin_notes_received()` - Process approval with notes

### 3. sheets_manager.py - Data Layer

**Responsibilities:**
- Connect to Google Sheets API
- Create and manage worksheets
- Perform CRUD operations
- Generate unique request IDs
- Handle timezone conversions

**Key Classes:**
- `SheetsManager` - Main class for all sheet operations

**Key Methods:**
- `create_deposit_request()` - Store deposit data
- `update_deposit_status()` - Update request status
- `get_user()` - Retrieve user information
- `update_payment_account()` - Update payment details

## Security Architecture

### Authentication Layers

```
┌─────────────────────────────────────────┐
│           Bot Token (Layer 1)           │
│     Only bot can connect to Telegram    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      Admin User ID (Layer 2)            │
│   Only specific user can access admin   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│   Service Account (Layer 3)             │
│  Only bot can access Google Sheets      │
└─────────────────────────────────────────┘
```

### Data Protection

1. **Environment Variables**: Sensitive data in `.env`
2. **Credentials File**: Separate JSON file for Google API
3. **No Hardcoding**: All secrets externalized
4. **Access Control**: Admin functions restricted by user ID

## Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│                   GitHub                            │
│              (Source Code Repository)               │
│                                                     │
│  • bot.py                                          │
│  • admin_panel.py                                  │
│  • sheets_manager.py                               │
│  • requirements.txt                                │
│  • Procfile, runtime.txt                           │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Auto-deploy on push
                   │
┌──────────────────▼──────────────────────────────────┐
│                 RAILWAY                             │
│          (Cloud Hosting Platform)                   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │        Environment Variables               │   │
│  │  • TELEGRAM_BOT_TOKEN                       │   │
│  │  • ADMIN_USER_ID                            │   │
│  │  • All other config                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │          credentials.json                   │   │
│  │     (Uploaded via Raw Editor)               │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │         Bot Application                     │   │
│  │      Running 24/7 as Worker                 │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Scalability Considerations

### Current Design
- Single instance deployment
- Single admin user
- All data in Google Sheets

### Future Enhancements
1. **Multiple Admins**: Add admin user list
2. **Database**: Migrate to PostgreSQL for better performance
3. **Caching**: Add Redis for frequent queries
4. **Load Balancing**: Deploy multiple instances
5. **Webhooks**: Switch from polling to webhooks

## Error Handling Strategy

### User-Facing Errors
- Friendly error messages
- Retry mechanisms
- Fallback options

### Admin Notifications
- Critical errors sent to admin
- Log monitoring
- Automated alerts

### Data Integrity
- Transaction logging
- Request ID tracking
- Status validation

## Monitoring & Logging

### What's Logged
- All user requests
- Admin actions
- Error messages
- API calls

### Where Logs Go
- Railway console (real-time)
- Google Sheets (transactions)
- Application logs (debugging)

## Performance Optimization

### Current Optimizations
1. **Async Operations**: All handlers are async
2. **Efficient Queries**: Targeted sheet lookups
3. **Minimal API Calls**: Batch operations where possible

### Bottlenecks to Watch
1. Google Sheets API rate limits (100 requests/100 seconds)
2. Telegram Bot API limits (30 messages/second)
3. Sheet size (performance degrades after 10,000 rows)

## Backup & Recovery

### Automated Backups
- Google Sheets auto-saves
- Version history available

### Manual Backups
- Export sheets regularly
- Keep configuration files safe

### Recovery Procedures
1. Redeploy from GitHub
2. Restore environment variables
3. Upload credentials
4. Verify all functions

---

**This architecture is designed for:**
- Reliability (24/7 uptime)
- Simplicity (easy to maintain)
- Security (multiple layers)
- Scalability (can be enhanced)
