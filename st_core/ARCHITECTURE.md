# ST CORE — Architecture

## System Overview

ST CORE is a FastAPI-based backend for Shamanic Travels. It manages lead capture,
editorial delivery, email automation, interview pipeline, AI candidate analysis,
CRM notes, backup/restore, and admin security auditing.

### Stack

- **Framework:** FastAPI (Python 3.14)
- **ORM:** SQLAlchemy 2.x (Declarative Base)
- **Database:** SQLite (dev), PostgreSQL-ready
- **Templating:** Jinja2 (admin dashboard)
- **Auth:** HTTP Basic (admin routes)
- **Testing:** pytest + TestClient

---

## Directory Layout

```
st_core/
  app.py                  # FastAPI app factory, lifespan, middleware
  config.py               # Settings via pydantic-settings + .env
  database.py             # Engine, SessionLocal, Base
  dependencies.py         # get_db() dependency
  security.py             # verify_admin, verify_csrf
  models.py               # All SQLAlchemy models
  schemas.py              # Pydantic request/response schemas
  routes/
    leads.py              # Public API: POST /api/leads, GET /api/leads, etc.
    dashboard.py          # Admin routes: /admin, /admin/lead/{id}, bulk, backups, audit
    download.py           # Public: GET /download/{token}
    health.py             # GET /health
  services/
    lead_service.py       # Lead CRUD, filtering, priority scoring
    email_engine.py       # Email queue processing (log backend)
    automation_engine.py  # Status-triggered automations
    editorial_service.py  # Editorial assignment, download tracking
    interview_service.py  # Interview CRUD
    ai_service.py         # AI candidate analysis
    analytics_service.py  # BI metrics, funnel, sources, pipeline
    note_service.py       # CRM notes CRUD
    backup_service.py     # Backup create/list/restore/delete
  templates/
    dashboard.html        # Main admin dashboard
    lead_detail.html      # Lead detail page
    backups.html          # Backup manager page
    audit_log.html        # Admin audit log page
  tests/
    conftest.py           # Fixtures: client, auth_headers, sample_lead_data, _db
    test_funnel.py        # Tests 1-5: capture, delivery, email, dashboard, interviews, simulated users
    test_operations.py    # Tests 6-12: notes, priority, bulk, audit, backup, widgets, models
  core/
    languages.py          # Language detection from form/header
    error_handlers.py     # Global exception handlers
    logger.py             # Logging setup
```

---

## Data Models

### Lead (leads table)
Core entity. Captured via `POST /api/leads`, managed in admin dashboard.

| Field | Type | Notes |
|-------|------|-------|
| id | int PK | Auto-increment |
| uuid | str(36) | Unique, generated on create |
| first_name, last_name, email | str | Required |
| country, language | str | Nullable |
| status | LeadStatus enum | NEW, CONTACTED, INTERVIEW, APPROVED, BOOKED, COMPLETED, REJECTED, ARCHIVED |
| notes | text | Internal CRM field (legacy) |
| priority_score | int | Computed: download +10, INTERVIEW +30, APPROVED +50, BOOKED +60, COMPLETED +80 |
| estimated_value | float | Manual override for pipeline value |
| downloaded_editorial | bool | Set on PDF download |
| download_token | str(128) | Unique token for PDF access |
| download_expires_at | datetime | 30 days from creation |
| source_page, campaign, referrer | str | Tracking |
| utm_* | str | UTM params |
| ip_address, user_agent | str | Request metadata |
| editorial_edition_id | FK | Editorial assigned |
| created_at, updated_at | datetime | Timestamps |

### LeadNote (lead_notes table)
CRM-style notes attached to leads. Separate from the internal `Lead.notes` field.

| Field | Type |
|-------|------|
| id | int PK |
| lead_id | FK -> leads.id |
| content | text |
| created_by | str(100) |
| created_at | datetime |

### LeadEvent (lead_events table)
Audit trail for lead lifecycle changes. Created by all services automatically.

| Field | Type |
|-------|------|
| id | int PK |
| lead_id | FK |
| event_type | str(50) |
| title | str(255) |
| description | text |
| metadata_json | text |
| created_by | str(100) |
| created_at | datetime |

### LeadDocument, EmailQueue, DownloadEvent, Interview, CandidateAnalysis
See `models.py` for full schema.

### EmailTemplate (email_templates table)
Stores email template definitions. Migration-ready, not yet wired into automation.

| Field | Type |
|-------|------|
| id | int PK |
| name | str(100), unique |
| subject | str(255) |
| body_html, body_text | text |
| language | str(10) |
| active | bool |
| created_at, updated_at | datetime |

### AdminAudit (admin_audit table)
Immutable log of all admin actions (status changes, note adds, bulk ops, backups).

| Field | Type |
|-------|------|
| id | int PK |
| admin_user | str(100) |
| action | str(100) |
| resource_type | str(50) |
| resource_id | str(50) |
| details | text |
| ip_address | str(45) |
| created_at | datetime |

---

## Status Machine

Allowed transitions enforce funnel progression:

```
NEW → CONTACTED → INTERVIEW → APPROVED → BOOKED → COMPLETED
 ↓        ↓           ↓          ↓          ↓          ↓
 └── REJECTED ────────────────────────────────────────┘
 └── ARCHIVED (any state can go here)
```

Invalid transitions return HTTP 400.

---

## Priority Score (Simple Heuristic)

Computed automatically on every status change and download:

| Trigger | Points |
|---------|--------|
| Editorial downloaded | +10 |
| Status = INTERVIEW | +30 |
| Status = APPROVED | +50 |
| Status = BOOKED | +60 |
| Status = COMPLETED | +80 |

Displayed on dashboard and lead detail. High-priority (>=50) count shown in operational widgets.

---

## CRM Workflow

1. Admin opens lead detail page
2. Sees profile, timeline, emails, interviews, AI analysis, documents, and **CRM Notes** section
3. Types a note in the textarea and clicks "Add Note"
4. Note is stored in `lead_notes` table, a `LeadEvent` is created for the timeline, and an `AdminAudit` entry is logged
5. Notes are displayed newest-first on lead detail
6. Recent notes across all leads appear in the dashboard sidebar widget

---

## Admin API Routes

### Dashboard
- `GET /admin` — Main dashboard with leads table, filters, pagination, stats, widgets
- `GET /admin/lead/{id}` — Lead detail page
- `POST /admin/lead/{id}` — Update status/notes

### Bulk Actions
- `POST /admin/bulk` — Bulk status update or delete
- `POST /admin/bulk/export` — Export selected leads as CSV

### CRM Notes
- `POST /admin/lead/{id}/notes/add` — Add note to lead
- `GET /admin/lead/{id}/notes` — JSON endpoint for notes

### Backups
- `GET /admin/backups` — Backup manager page
- `POST /admin/backups/create` — Create new backup
- `POST /admin/backups/restore` — Restore from backup
- `POST /admin/backups/delete` — Delete backup

### Security
- `GET /admin/audit-log` — View last 100 admin actions

### Email
- `POST /admin/email/process` — Process pending email queue
- `POST /admin/email/{id}/cancel` — Cancel queued email
- `POST /admin/email/{id}/retry` — Retry failed email

### Interviews
- `POST /admin/lead/{id}/interview/create` — Create interview
- `POST /admin/interview/{id}/schedule` — Schedule with datetime/URL
- `POST /admin/interview/{id}/complete` — Mark completed
- `POST /admin/interview/{id}/cancel` — Cancel
- `POST /admin/interview/{id}/no-show` — Mark no-show

### AI Analysis
- `POST /admin/lead/{id}/analyze` — Run AI analysis
- `POST /admin/lead/{id}/reprocess-automation` — Re-run automation rules

### Export
- `GET /admin/export/leads` — Full CSV export of all leads

---

## Dashboard Widgets

### Top Row
- **Today's Leads** — Count of leads created today
- **Today's Downloads** — Count of downloads today
- **Pipeline Value** — Weighted sum: NEW=0, CONTACTED=100, INTERVIEW=300, APPROVED=500, BOOKED=1000, COMPLETED=1500
- **High Priority** — Leads with priority_score >= 50

### Business Intelligence Section
- Conversion funnel bar chart
- Traffic sources breakdown
- Monthly lead chart (6 months)
- Candidate pipeline grid by stage
- CSV export link

### Sidebar (right column)
- Latest activity timeline
- Email queue stats + recent emails
- AI analysis stats + recent analyses
- Interviews today + upcoming
- Recent CRM notes

---

## Backup Management

Backup service (`services/backup_service.py`):
- Copies database files to `./backups/` directory
- Timestamped filenames: `st_core_backup_YYYYMMDD_HHMMSS_label`
- Retention: max 10 backups by default (oldest auto-deleted)
- Restore creates a safety backup before overwriting
- Supports both directory and single-file databases

---

## Testing Strategy

```
test_funnel.py:       TestLeadCapture (5) + TestEditorialDelivery (4) +
                      TestEmailAutomation (4) + TestDashboard (6) +
                      TestInterviewPipeline (7) + TestSimulatedUsers (16)
                      = 42 tests (full customer journey)

test_operations.py:   TestCRMNotes (6) + TestPriorityScore (8) +
                      TestBulkActions (5) + TestAdminAudit (5) +
                      TestBackupService (4) + TestDashboardWidgets (4) +
                      TestEmailTemplateModel (2)
                      = 34 tests (operational control)

Total: 76 tests
```

Run: `pytest tests/ -v`

Fixtures in `conftest.py`:
- `client` — FastAPI TestClient
- `auth_headers` — HTTP Basic auth for admin routes
- `sample_lead_data` — Standard test lead
- `_db` — Auto create/drop tables per test
- `_ensure_all_ebooks` — Dummy PDF files for download tests
