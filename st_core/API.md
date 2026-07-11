# ST CORE API

Base URL: `http://localhost:8000`

---

## Authentication

### Admin Routes

All `/admin/*` routes require HTTP Basic Auth.

Configure credentials via `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`.

---

## System

### `GET /health`

Returns service status, version, and database connectivity.

**Response:**
```json
{
  "status": "ok",
  "service": "ST CORE",
  "version": "1.0.0",
  "database": "ok"
}
```

---

## Leads

### `POST /api/leads`

Create a new lead.

**Body** (JSON):
| Field            | Type   | Required | Description                |
|------------------|--------|----------|----------------------------|
| first_name       | string | yes      |                            |
| last_name        | string | yes      |                            |
| email            | string | yes      | Valid email                |
| country          | string | no       |                            |
| language         | string | no       | en, it, es, ru, sr         |
| source_page      | string | no       |                            |
| campaign         | string | no       |                            |
| referrer         | string | no       |                            |
| utm_source       | string | no       |                            |
| utm_medium       | string | no       |                            |
| utm_campaign     | string | no       |                            |

**Response:** `{ "success": true, "id": 1, "download_token": "..." }`

### `GET /api/leads`

List leads (authorized).

### `GET /api/leads/{id}`

Get a single lead by ID.

### `PATCH /api/leads/{id}`

Update lead status/notes.

### `POST /api/leads/{id}/download`

Track editorial download.

---

## Download

### `GET /download/{token}`

Download editorial PDF using token from lead creation.

- Token expires after 30 days.
- Accept-Language header is not required; uses lead's stored language.

**Response:** PDF file attachment.

---

## Admin Dashboard

### `GET /admin`

Main dashboard with filters, pagination, BI, and sidebar widgets.

**Query parameters:**
| Param      | Type   | Description                   |
|------------|--------|-------------------------------|
| status     | string | Filter by lead status         |
| language   | string | Filter by language            |
| country    | string | Filter by country             |
| search     | string | Search name/email/notes       |
| downloaded | bool   | Only downloaded leads         |
| period     | string | today, 7d, 30d                |
| sort_by    | string | created_at, updated_at, etc.  |
| sort_order | string | asc or desc                   |
| page       | int    | Page number (default 1)       |
| per_page   | int    | Items per page (default 20)   |

### `GET /admin/lead/{id}`

Lead detail page with timeline, emails, interviews, AI analysis, documents.

### `POST /admin/lead/{id}`

Update lead status/notes.

### `GET /admin/export/leads`

Download all leads as CSV.

**Headers:** Authorization: Basic ...

---

## Email Queue

### `POST /admin/email/process`

Process pending emails (batch).

### `POST /admin/email/{id}/cancel`

Cancel a pending email.

### `POST /admin/email/{id}/retry`

Retry a failed email.

---

## Interviews

### `POST /admin/lead/{lead_id}/interview/create`

Request an interview for a lead.

### `POST /admin/interview/{id}/schedule`

Schedule an interview.

**Form fields:** `scheduled_at` (datetime-local), `duration_minutes`, `meeting_url`

### `POST /admin/interview/{id}/complete`

Mark interview as completed.

### `POST /admin/interview/{id}/cancel`

Cancel interview.

### `POST /admin/interview/{id}/no-show`

Mark as no-show.

---

## AI Analysis

### `POST /admin/lead/{lead_id}/analyze`

Generate or regenerate AI candidate analysis.

---

## Error Responses

| Status | Meaning       |
|--------|---------------|
| 401    | Unauthorized  |
| 403    | Forbidden     |
| 404    | Not found     |
| 422    | Validation    |
| 500    | Server error  |
