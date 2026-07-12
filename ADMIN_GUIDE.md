# ST CORE — Admin Guide

## Accessing the Dashboard

Navigate to `http://your-domain:8000/admin` and log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from your `.env` file.

## Dashboard Overview

### Stats Bar
Shows total leads broken down by status (New, Contacted, Interview, Approved, Booked, Completed, Rejected, Archived).

### Today's Stats
- **Today's Leads** — leads created today
- **Today's Downloads** — editorial downloads today
- **Pipeline Value** — estimated total value by stage
- **High Priority** — leads with priority score >= 50

### CRM Widgets
- **Today's Tasks** — tasks due today
- **Overdue Tasks** — past-due tasks
- **Upcoming Interviews** — interviews scheduled for today
- **Notifications** — unread system notifications

### Need Attention
Quick-look counts for: New Leads, Need Follow-up (Contacted), Need Approval (Interview), Need Booking (Approved), Upcoming Interviews.

### Email Queue
Monitor and manage outbound emails: pending, sending, failed, sent, retry counts.

## Lead Management

### Status Workflow

```
NEW → CONTACTED → INTERVIEW → APPROVED → BOOKED → COMPLETED
  ↓      ↓           ↓           ↓          ↓
  └──────┴───────────┴───────────┴──────────┴──────→ REJECTED
                                                        ↓
                                                  ARCHIVED
```

### Lead Detail Page
Each lead has a detail page at `/admin/lead/{id}` with:

- **Info** — personal details, source, UTM parameters
- **Status** — change status with one click
- **Tasks** — create, update status, delete tasks
- **Reminders** — generate 3/7/14/30 day follow-up reminders
- **CRM Notes** — add internal notes
- **Email Queue** — view/manage queued emails
- **Interview History** — request, schedule, complete interviews
- **AI Analysis** — auto-generated candidate analysis
- **Documents** — document placeholders
- **Timeline** — full event history

### Bulk Actions
Select multiple leads and:
- Update status in bulk
- Export selected as CSV
- Delete selected leads

## Email Management

- **Process Queue** — send pending emails
- **Send Test** — verify email configuration
- **Cancel/Retry** — manage individual emails
- **Backend** — configure via `EMAIL_BACKEND` (log/smtp)

## Backup & Restore

See [BACKUP.md](BACKUP.md) for full details.

- Web interface at `/admin/backups`
- CLI scripts in `scripts/`

## System Health

### Diagnostics
`GET /admin/diagnostics` returns:
- Service name and version
- Database connection status
- Row counts for all tables
- Environment variable check

### Health Check
`GET /health` returns a simple status endpoint suitable for monitoring systems.

## Audit Log

Every admin action is logged at `/admin/audit-log`:
- Status changes
- Task/reminder CRUD
- Note additions
- Bulk operations
- Email operations
- Backup/restore events
- CSV imports
