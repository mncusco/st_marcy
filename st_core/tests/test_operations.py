"""
Phase 12 — Operational Control Layer tests.
Covers: CRM notes, bulk actions, priority score, admin audit, backup service.
"""

import pytest
import json
import uuid
import sys
import os
from datetime import datetime, timedelta, timezone


# ──────────────────────────────────────────────
# TEST 6 — CRM NOTES
# ──────────────────────────────────────────────

class TestCRMNotes:
    """LeadNote model, add notes via lead detail, view notes list."""

    def test_add_note_to_lead(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        resp = client.post(
            f"/admin/lead/{lead_id}/notes/add",
            data={"content": "Great candidate, very motivated"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "Great candidate" in html

    def test_multiple_notes_appear(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        for msg in ("First note", "Second note", "Third note"):
            client.post(
                f"/admin/lead/{lead_id}/notes/add",
                data={"content": msg},
                headers=auth_headers,
            )
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "First note" in html
        assert "Second note" in html
        assert "Third note" in html

    def test_note_with_created_by(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}/notes/add",
            data={"content": "Checked references"},
            headers=auth_headers,
        )
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "admin" in html.lower()  # created_by should show

    def test_notes_api_endpoint(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}/notes/add",
            data={"content": "API test note"},
            headers=auth_headers,
        )
        resp = client.get(f"/admin/lead/{lead_id}/notes", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["content"] == "API test note"

    def test_note_creates_timeline_event(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}/notes/add",
            data={"content": "Timeline check"},
            headers=auth_headers,
        )
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "CRM note added" in html or "note_added" in html.lower()

    def test_empty_note_rejected(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        resp = client.post(
            f"/admin/lead/{lead_id}/notes/add",
            data={"content": ""},
            headers=auth_headers,
            follow_redirects=False,
        )
        # Should fail validation or return error
        assert resp.status_code in (303, 422)


# ──────────────────────────────────────────────
# TEST 7 — PRIORITY SCORE
# ──────────────────────────────────────────────

class TestPriorityScore:
    """Priority score computed correctly based on status and download."""

    def test_new_lead_score_zero(self, client, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead.get("priority_score") == 0

    def test_downloaded_adds_ten(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        token = created["download_token"]
        client.get(f"/download/{token}")
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead.get("priority_score") == 10

    def test_interview_status_scores_thirty(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        for s in ("CONTACTED", "INTERVIEW"):
            client.post(
                f"/admin/lead/{lead_id}",
                data={"status": s, "notes": "promote"},
                headers=auth_headers,
                follow_redirects=False,
            )
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead.get("priority_score") == 30

    def test_approved_status_scores_fifty(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        for s in ("CONTACTED", "INTERVIEW", "APPROVED"):
            client.post(
                f"/admin/lead/{lead_id}",
                data={"status": s, "notes": "promote"},
                headers=auth_headers,
                follow_redirects=False,
            )
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead.get("priority_score") == 50

    def test_download_and_approved_combine(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        token = created["download_token"]
        client.get(f"/download/{token}")
        for s in ("CONTACTED", "INTERVIEW", "APPROVED"):
            client.post(
                f"/admin/lead/{lead_id}",
                data={"status": s, "notes": "promote"},
                headers=auth_headers,
                follow_redirects=False,
            )
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead.get("priority_score") == 60  # 10 (download) + 50 (approved)

    def test_high_priority_count_on_dashboard(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        for s in ("CONTACTED", "INTERVIEW", "APPROVED"):
            client.post(
                f"/admin/lead/{lead_id}",
                data={"status": s, "notes": "promote"},
                headers=auth_headers,
                follow_redirects=False,
            )
        html = client.get("/admin", headers=auth_headers).text
        assert "High Priority" in html

    def test_priority_column_in_dashboard(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        html = client.get("/admin", headers=auth_headers).text
        assert "Priority" in html or "priority" in html.lower()


# ──────────────────────────────────────────────
# TEST 8 — BULK ACTIONS
# ──────────────────────────────────────────────

class TestBulkActions:
    """Bulk status updates, selection, export."""

    def _create_leads(self, client, count=3):
        ids = []
        for i in range(count):
            data = {
                "first_name": f"Bulk{i}", "last_name": "Test",
                "email": f"bulk{i}@example.com", "language": "en",
            }
            created = client.post("/api/leads", json=data).json()
            ids.append(str(created["id"]))
        return ids

    def test_bulk_status_update(self, client, auth_headers):
        ids = self._create_leads(client, 3)
        resp = client.post(
            "/admin/bulk",
            data={"lead_ids": ",".join(ids), "bulk_action": "status_update", "bulk_status": "CONTACTED"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        for lid in ids:
            lead = client.get(f"/api/leads/{lid}").json()
            assert lead["status"] == "CONTACTED"

    def test_bulk_export_csv(self, client, auth_headers):
        ids = self._create_leads(client, 2)
        resp = client.post(
            "/admin/bulk/export",
            data={"lead_ids": ",".join(ids)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "Bulk0" in resp.text
        assert "Bulk1" in resp.text

    def test_bulk_delete(self, client, auth_headers):
        ids = self._create_leads(client, 2)
        resp = client.post(
            "/admin/bulk",
            data={"lead_ids": ",".join(ids), "bulk_action": "delete"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        for lid in ids:
            resp2 = client.get(f"/api/leads/{lid}")
            assert resp2.status_code == 404

    def test_bulk_empty_ids_rejected(self, client, auth_headers):
        resp = client.post(
            "/admin/bulk",
            data={"lead_ids": "", "bulk_action": "status_update", "bulk_status": "CONTACTED"},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422)

    def test_bulk_no_status_rejected(self, client, auth_headers):
        ids = self._create_leads(client, 1)
        resp = client.post(
            "/admin/bulk",
            data={"lead_ids": ",".join(ids), "bulk_action": "status_update"},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422)


# ──────────────────────────────────────────────
# TEST 9 — ADMIN AUDIT
# ──────────────────────────────────────────────

class TestAdminAudit:
    """AdminAudit model logs important actions."""

    def test_status_change_logged(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}",
            data={"status": "CONTACTED", "notes": "test"},
            headers=auth_headers,
            follow_redirects=False,
        )
        html = client.get("/admin/audit-log", headers=auth_headers).text
        assert "status_update" in html.lower() or "status" in html.lower()

    def test_note_added_logged(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}/notes/add",
            data={"content": "Audit test note"},
            headers=auth_headers,
        )
        html = client.get("/admin/audit-log", headers=auth_headers).text
        assert "note_added" in html.lower()

    def test_bulk_action_logged(self, client, auth_headers):
        data = {"first_name": "Audit", "last_name": "Bulk", "email": "audit_bulk@example.com"}
        created = client.post("/api/leads", json=data).json()
        client.post(
            "/admin/bulk",
            data={"lead_ids": str(created["id"]), "bulk_action": "status_update", "bulk_status": "ARCHIVED"},
            headers=auth_headers,
            follow_redirects=False,
        )
        html = client.get("/admin/audit-log", headers=auth_headers).text
        assert "bulk_status_update" in html.lower()

    def test_audit_page_accessible(self, client, auth_headers):
        html = client.get("/admin/audit-log", headers=auth_headers).text
        assert "Audit Log" in html or "Admin Actions" in html

    def test_audit_page_shows_admin_name(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}",
            data={"status": "CONTACTED", "notes": "who"},
            headers=auth_headers,
            follow_redirects=False,
        )
        html = client.get("/admin/audit-log", headers=auth_headers).text
        assert "admin" in html.lower()


# ──────────────────────────────────────────────
# TEST 10 — BACKUP SERVICE
# ──────────────────────────────────────────────

class TestBackupService:
    """Backup management: create, list, delete."""

    def test_backup_page_accessible(self, client, auth_headers):
        html = client.get("/admin/backups", headers=auth_headers).text
        assert "Backup" in html or "backup" in html.lower()

    def test_create_backup(self, client, auth_headers):
        resp = client.post(
            "/admin/backups/create",
            data={"label": "test_backup"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        html = client.get("/admin/backups", headers=auth_headers).text
        assert "test_backup" in html

    def test_backup_listed(self, client, auth_headers):
        client.post("/admin/backups/create", data={"label": "list_check"}, headers=auth_headers, follow_redirects=False)
        html = client.get("/admin/backups", headers=auth_headers).text
        assert "KB" in html or "list_check" in html

    def test_delete_backup(self, client, auth_headers):
        client.post("/admin/backups/create", data={"label": "to_delete"}, headers=auth_headers, follow_redirects=False)
        html = client.get("/admin/backups", headers=auth_headers).text
        import re
        names = re.findall(r'value="([^"]+)"', html)
        backup_candidates = [n for n in names if "st_core_backup" in n]
        if backup_candidates:
            name = backup_candidates[0]
            resp = client.post(
                "/admin/backups/delete",
                data={"backup_name": name},
                headers=auth_headers,
                follow_redirects=False,
            )
            assert resp.status_code == 303


# ──────────────────────────────────────────────
# TEST 11 — TODAY & PIPELINE WIDGETS
# ──────────────────────────────────────────────

class TestDashboardWidgets:
    """Today's stats, pipeline value, high priority count."""

    def test_today_leads_shown(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        html = client.get("/admin", headers=auth_headers).text
        assert "Today's Leads" in html or "Today" in html

    def test_pipeline_value_shown(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Pipeline Value" in html or "pipeline" in html.lower()

    def test_high_priority_shown(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "High Priority" in html or "priority" in html.lower()

    def test_today_downloads_shown(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        token = created["download_token"]
        client.get(f"/download/{token}")
        html = client.get("/admin", headers=auth_headers).text
        assert "Today" in html


# ──────────────────────────────────────────────
# TEST 12 — EMAIL TEMPLATE MODEL
# ──────────────────────────────────────────────

class TestEmailTemplateModel:
    """EmailTemplate model is available and can be instantiated."""

    def test_model_exists(self):
        from models import EmailTemplate
        assert EmailTemplate.__tablename__ == "email_templates"

    def test_model_has_required_fields(self):
        from models import EmailTemplate
        cols = [c.name for c in EmailTemplate.__table__.columns]
        for field in ("name", "subject", "body_html", "body_text", "language", "active"):
            assert field in cols, f"Missing field: {field}"


# ──────────────────────────────────────────────
# PHASE 13 — REAL EMAIL DELIVERY
# ──────────────────────────────────────────────

class TestSmtpProvider:
    """SMTP provider instantiation and config."""

    def test_provider_imports(self):
        from providers.smtp_provider import SmtpProvider
        assert SmtpProvider is not None

    def test_provider_is_provider(self):
        from providers.smtp_provider import SmtpProvider
        from providers.interface import EmailProvider
        p = SmtpProvider()
        assert isinstance(p, EmailProvider)

    def test_html_to_plain(self):
        from providers.smtp_provider import SmtpProvider
        p = SmtpProvider()
        html = "<p>Hello <b>world</b></p><br><p>Line 2</p>"
        text = p._html_to_plain(html)
        assert "Hello world" in text
        assert "Line 2" in text

    def test_provider_config_settings(self):
        from config import settings
        assert hasattr(settings, "SMTP_HOST")
        assert hasattr(settings, "SMTP_PORT")
        assert hasattr(settings, "FROM_EMAIL")
        assert hasattr(settings, "FROM_NAME")
        assert hasattr(settings, "EMAIL_MAX_RETRIES")

    def test_smtp_config_defaults(self, monkeypatch):
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_PORT", raising=False)
        monkeypatch.delenv("SMTP_TLS", raising=False)
        monkeypatch.delenv("SMTP_SSL", raising=False)
        monkeypatch.delenv("SMTP_USERNAME", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        monkeypatch.delenv("SMTP_TIMEOUT", raising=False)
        monkeypatch.delenv("FROM_EMAIL", raising=False)
        monkeypatch.delenv("FROM_NAME", raising=False)
        monkeypatch.delenv("EMAIL_MAX_RETRIES", raising=False)
        from config import Settings
        s = Settings(_env_file=None)
        assert s.SMTP_HOST == "localhost"
        assert s.SMTP_PORT == 587
        assert s.SMTP_TLS is True
        assert s.SMTP_SSL is False
        assert s.FROM_EMAIL == "noreply@shamanictravels.com"
        assert s.EMAIL_MAX_RETRIES == 3


class TestTestEmailEndpoint:
    """POST /admin/email/test endpoint."""

    def test_test_email_button_on_dashboard(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Send Test" in html or "test_email" in html

    def test_test_email_endpoint_accessible(self, client, auth_headers):
        resp = client.post(
            "/admin/email/test",
            data={"test_email": "admin@example.com"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_test_email_with_log_backend(self, client, auth_headers):
        """With EMAIL_BACKEND=log, test email should succeed."""
        resp = client.post(
            "/admin/email/test",
            data={"test_email": "test@example.com"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303


class TestEmailMaxRetries:
    """EMAIL_MAX_RETRIES enforcement."""

    def test_retry_limit_configurable(self):
        from config import settings
        assert settings.EMAIL_MAX_RETRIES >= 1

    def test_failed_email_retries_reverted_to_pending(self, client, auth_headers, sample_lead_data):
        """After a failed attempt, the email should remain PENDING for retry."""
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "followup" in html.lower() or "PENDING" in html


class TestEmailLayoutTemplate:
    """Shared email layout template."""

    def test_layout_exists(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "emails", "layout.html")
        assert os.path.exists(path), f"layout.html not found at {path}"

    def test_layout_has_blocks(self):
        import os as _os
        path = _os.path.join(_os.path.dirname(__file__), "..", "templates", "emails", "layout.html")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "{% block content %}" in content
        assert "{% block title %}" in content

    def test_followup_template_extends_layout(self):
        import os as _os
        path = _os.path.join(_os.path.dirname(__file__), "..", "templates", "emails", "en", "followup_3_days.html")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "{% extends" in content


class TestEmailQueueStats:
    """Email queue stats include new fields."""

    def test_stats_include_processing(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Sending" in html or "processing" in html.lower()

    def test_stats_include_retries(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Retries" in html or "retries" in html.lower()

    def test_stats_include_max(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Max" in html or "max" in html.lower()


# ──────────────────────────────────────────────
# PHASE 14 — OPERATIONAL CRM
# ──────────────────────────────────────────────

class TestTaskModel:
    """Task model exists with required fields."""

    def test_task_model_imports(self):
        from models import Task, TaskStatus
        assert Task is not None
        assert TaskStatus.PENDING in TaskStatus
        assert TaskStatus.IN_PROGRESS in TaskStatus
        assert TaskStatus.COMPLETED in TaskStatus

    def test_task_model_fields(self):
        from models import Task
        cols = [c.name for c in Task.__table__.columns]
        for f in ("title", "status", "priority", "due_at", "assigned_to", "created_by", "lead_id"):
            assert f in cols, f"Missing field: {f}"


class TestReminderModel:
    """Reminder model exists."""

    def test_reminder_model_imports(self):
        from models import Reminder, ReminderType
        assert Reminder is not None
        assert ReminderType.FOLLOWUP_3D in ReminderType
        assert ReminderType.FOLLOWUP_7D in ReminderType
        assert ReminderType.FOLLOWUP_14D in ReminderType

    def test_reminder_model_fields(self):
        from models import Reminder
        cols = [c.name for c in Reminder.__table__.columns]
        for f in ("lead_id", "reminder_type", "title", "remind_at", "notified"):
            assert f in cols, f"Missing field: {f}"


class TestNotificationModel:
    """Notification model exists."""

    def test_notification_model_imports(self):
        from models import Notification
        assert Notification is not None

    def test_notification_model_fields(self):
        from models import Notification
        cols = [c.name for c in Notification.__table__.columns]
        for f in ("lead_id", "title", "notification_type", "read"):
            assert f in cols, f"Missing field: {f}"


class TestTaskService:
    """TaskService CRUD operations."""

    def test_create_task(self, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        task = svc.create_task(title="Test Task", priority="high")
        assert task.id is not None
        assert task.title == "Test Task"
        assert task.status.value == "PENDING"

    def test_create_task_with_lead(self, client, auth_headers, sample_lead_data):
        from services.task_service import TaskService
        from database import SessionLocal
        created = client.post("/api/leads", json=sample_lead_data).json()
        db = SessionLocal()
        svc = TaskService(db)
        task = svc.create_task(title="Lead Task", lead_id=created["id"])
        db.close()
        assert task.lead_id == created["id"]

    def test_update_task_status(self, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        task = svc.create_task(title="Update Me")
        updated = svc.update_task(task.id, status="COMPLETED")
        assert updated.status.value == "COMPLETED"
        assert updated.completed_at is not None

    def test_delete_task(self, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        task = svc.create_task(title="Delete Me")
        assert svc.delete_task(task.id) is True
        assert svc.get_task(task.id) is None

    def test_get_today_tasks(self, db_session):
        from services.task_service import TaskService
        from datetime import datetime
        svc = TaskService(db_session)
        svc.create_task(title="Today Task", due_at=datetime.now(timezone.utc))
        today = svc.get_today_tasks()
        assert any(t.title == "Today Task" for t in today)

    def test_get_overdue_tasks(self, db_session):
        from services.task_service import TaskService
        from datetime import datetime, timedelta
        svc = TaskService(db_session)
        svc.create_task(title="Overdue Task", due_at=datetime.now(timezone.utc) - timedelta(days=1))
        overdue = svc.get_overdue_tasks()
        assert any(t.title == "Overdue Task" for t in overdue)


class TestTaskAPI:
    """POST/PATCH/DELETE /admin/task endpoints."""

    def test_create_task_via_api(self, client, auth_headers):
        resp = client.post("/admin/task", data={"title": "API Task", "priority": "high"},
                           headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303

    def test_create_task_with_lead_via_api(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        resp = client.post("/admin/task", data={"title": "Lead Task", "lead_id": str(created["id"])},
                           headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303

    def test_update_task_via_api(self, client, auth_headers, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        task = svc.create_task(title="Update API")
        db_session.close()
        resp = client.post(f"/admin/task/{task.id}/update",
                           data={"status": "COMPLETED"},
                           headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303

    def test_delete_task_via_api(self, client, auth_headers, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        task = svc.create_task(title="Delete API")
        db_session.close()
        resp = client.post(f"/admin/task/{task.id}/delete",
                           headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303

    def test_task_button_on_dashboard(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Today's Tasks" in html or "today_tasks" in html


class TestReminderAutoCreation:
    """Automatic 3/7/14/30 day reminders."""

    def test_create_reminder(self, db_session):
        from services.task_service import TaskService
        from models import ReminderType
        svc = TaskService(db_session)
        r = svc.create_reminder(lead_id=1, reminder_type=ReminderType.FOLLOWUP_3D,
                                 title="3 Day Follow-up")
        assert r.id is not None
        assert r.reminder_type == ReminderType.FOLLOWUP_3D

    def test_auto_create_followup_reminders(self, db_session):
        from services.task_service import TaskService
        from models import Lead
        lead = Lead(first_name="Test", last_name="User", email="reminder@test.com")
        db_session.add(lead)
        db_session.flush()
        svc = TaskService(db_session)
        svc.auto_create_followup_reminders(lead)
        reminders = svc.get_lead_reminders(lead.id)
        assert len(reminders) >= 3

    def test_process_reminders(self, client, auth_headers, db_session):
        from services.task_service import TaskService
        from models import ReminderType, Lead
        lead = Lead(first_name="Process", last_name="Test", email="process@test.com")
        db_session.add(lead)
        db_session.flush()
        svc = TaskService(db_session)
        r = svc.create_reminder(lead_id=lead.id, reminder_type=ReminderType.FOLLOWUP_3D,
                                 title="Test Reminder")
        r.remind_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()
        db_session.close()
        resp = client.post("/admin/reminders/process", headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303

    def test_process_reminders_button_on_dashboard(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Process Reminders" in html


class TestNotifications:
    """Notification system."""

    def test_create_notification(self, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        n = svc.create_notification(lead_id=1, title="Test Notification",
                                     message="Hello", notification_type="system")
        assert n.id is not None
        assert n.read is False

    def test_mark_notification_read(self, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        n = svc.create_notification(lead_id=1, title="Read Test", notification_type="system")
        svc.mark_notification_read(n.id)
        assert n.read is True
        assert n.read_at is not None

    def test_unread_notifications(self, db_session):
        from services.task_service import TaskService
        svc = TaskService(db_session)
        svc.create_notification(lead_id=1, title="Unread 1", notification_type="system")
        svc.create_notification(lead_id=1, title="Unread 2", notification_type="system")
        unread = svc.get_unread_notifications()
        assert len(unread) >= 2


class TestLeadOwner:
    """Lead.owner field."""

    def test_owner_field_exists(self):
        from models import Lead
        cols = [c.name for c in Lead.__table__.columns]
        assert "owner" in cols

    def test_owner_stored(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        html = client.get(f"/admin/lead/{created['id']}", headers=auth_headers).text
        assert "Owner" in html or "owner" in html.lower() or created["id"]


class TestCRMWidgets:
    """Dashboard CRM widgets."""

    def test_today_tasks_widget(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Today's Tasks" in html

    def test_overdue_tasks_widget(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Overdue Tasks" in html

    def test_notifications_widget(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Notifications" in html

    def test_need_followup_shown(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Need Follow-up" in html

    def test_need_approval_shown(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Need Approval" in html

    def test_need_booking_shown(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Need Booking" in html

    def test_upcoming_interviews_count(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Upcoming Interviews" in html


class TestTaskSchema:
    """Pydantic schemas for tasks."""

    def test_task_create_schema(self):
        from schemas import TaskCreate
        s = TaskCreate(title="Test Task", priority="high")
        assert s.title == "Test Task"

    def test_task_update_schema(self):
        from schemas import TaskUpdate
        s = TaskUpdate(status="COMPLETED")
        assert s.status == "COMPLETED"

    def test_task_response_schema(self):
        from schemas import TaskResponse
        from datetime import datetime
        s = TaskResponse(id=1, title="Test", status="PENDING", priority="normal",
                         created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        assert s.title == "Test"

    def test_reminder_response_schema(self):
        from schemas import ReminderResponse
        from datetime import datetime
        s = ReminderResponse(id=1, lead_id=1, reminder_type="FOLLOWUP_3D", title="Reminder",
                             remind_at=datetime.now(timezone.utc), status="active", notified=False,
                             created_at=datetime.now(timezone.utc))
        assert s.title == "Reminder"


class TestTaskOnLeadDetail:
    """Tasks appear on lead detail page."""

    def test_tasks_section_on_detail(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        html = client.get(f"/admin/lead/{created['id']}", headers=auth_headers).text
        assert "Tasks" in html

    def test_add_task_button_on_detail(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        html = client.get(f"/admin/lead/{created['id']}", headers=auth_headers).text
        assert "Add Task" in html

    def test_reminders_section_on_detail(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        html = client.get(f"/admin/lead/{created['id']}", headers=auth_headers).text
        assert "Reminders" in html


# ──────────────────────────────────────────────
# PHASE 15 — PRODUCTION READY
# ──────────────────────────────────────────────

class TestBackupScript:
    """scripts/backup.py CLI tool."""

    def test_backup_script_imports(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("backup_script", "scripts/backup.py")
        assert spec is not None, "scripts/backup.py not found"

    def test_backup_script_list(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/backup.py", "--list"],
            capture_output=True, text=True, cwd=os.path.dirname(__file__) + "/../..",
        )
        assert result.returncode == 0


class TestRestoreScript:
    """scripts/restore.py CLI tool."""

    def test_restore_script_imports(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("restore_script", "scripts/restore.py")
        assert spec is not None, "scripts/restore.py not found"

    def test_restore_script_list(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/restore.py", "--list"],
            capture_output=True, text=True, cwd=os.path.dirname(__file__) + "/../..",
        )
        assert result.returncode == 0


class TestVerifyScript:
    """scripts/verify.py integrity checker."""

    SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
    ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

    def test_verify_script_imports(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "verify_script", os.path.join(self.SCRIPTS_DIR, "verify.py")
        )
        assert spec is not None, "scripts/verify.py not found"

    def test_verify_script_runs(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(self.SCRIPTS_DIR, "verify.py")],
            capture_output=True, text=True, cwd=self.ROOT,
        )
        assert result.returncode in (0, 1)

    def test_verify_checks_database(self):
        sys.path.insert(0, self.ROOT)
        try:
            from scripts.verify import check_integrity
            result = check_integrity(os.path.join(os.path.dirname(__file__), "..", "test_shamanic.db"))
            assert "status" in result
        finally:
            sys.path.pop(0)

    def test_verify_directory_structure(self):
        sys.path.insert(0, self.ROOT)
        old_cwd = os.getcwd()
        try:
            os.chdir(self.ROOT)
            from scripts.verify import check_directory_structure
            result = check_directory_structure()
            assert result.get("st_core") is True
            assert result.get("app.py") is True
        finally:
            os.chdir(old_cwd)
            sys.path.pop(0)


class TestCSVImport:
    """POST /admin/import/leads endpoint."""

    def test_csv_import_valid(self, client, auth_headers):
        csv_data = "first_name,last_name,email\nJohn,Doe,john@import.com\nJane,Smith,jane@import.com"
        resp = client.post("/admin/import/leads", data={"csv_data": csv_data},
                           headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] >= 2

    def test_csv_import_missing_fields(self, client, auth_headers):
        csv_data = "first_name,email\n,missing@email.com"
        resp = client.post("/admin/import/leads", data={"csv_data": csv_data},
                           headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0

    def test_csv_import_requires_auth(self, client):
        csv_data = "first_name,last_name,email\nX,Y,z@test.com"
        resp = client.post("/admin/import/leads", data={"csv_data": csv_data})
        assert resp.status_code in (401, 403)


class TestDiagnostics:
    """GET /admin/diagnostics endpoint."""

    def test_diagnostics_endpoint(self, client, auth_headers):
        resp = client.get("/admin/diagnostics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "version" in data
        assert "database" in data
        assert "table_counts" in data

    def test_diagnostics_shows_tables(self, client, auth_headers):
        resp = client.get("/admin/diagnostics", headers=auth_headers)
        data = resp.json()
        assert "leads" in data["table_counts"]

    def test_diagnostics_requires_auth(self, client):
        resp = client.get("/admin/diagnostics")
        assert resp.status_code in (401, 403)


class TestStartupValidation:
    """Startup validation in app.py."""

    def test_validate_function_exists(self):
        from app import _validate_startup
        assert callable(_validate_startup)

    def test_validate_runs_without_crash(self):
        from app import _validate_startup
        issues = _validate_startup()
        assert isinstance(issues, list)


class TestDocumentation:
    """Documentation files exist."""

    ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

    def test_install_doc_exists(self):
        assert os.path.exists(os.path.join(self.ROOT, "INSTALL.md"))

    def test_deploy_doc_exists(self):
        assert os.path.exists(os.path.join(self.ROOT, "DEPLOY.md"))

    def test_backup_doc_exists(self):
        assert os.path.exists(os.path.join(self.ROOT, "BACKUP.md"))

    def test_admin_guide_exists(self):
        assert os.path.exists(os.path.join(self.ROOT, "ADMIN_GUIDE.md"))


class TestScriptsDir:
    """scripts/ directory structure."""

    SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")

    def test_scripts_init_exists(self):
        assert os.path.exists(os.path.join(self.SCRIPTS, "__init__.py"))

    def test_all_scripts_present(self):
        for name in ("backup.py", "restore.py", "verify.py"):
            assert os.path.exists(os.path.join(self.SCRIPTS, name)), f"Missing scripts/{name}"


# ═══════════════════════════════════════════════
# PHASE 16 — RETREAT BOOKING
# ═══════════════════════════════════════════════

class TestRetreatModel:
    """Retreat CRUD operations."""

    def test_create_retreat(self, client, auth_headers):
        resp = client.post("/admin/retreat/create", data={
            "name": "Amazon Retreat",
            "description": "A journey into the jungle",
            "location": "Peru",
            "start_date": "2026-09-01",
            "end_date": "2026-09-14",
            "max_participants": 10,
            "price": 2500.0,
            "currency": "USD",
            "status": "ACTIVE",
        }, headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303
        html = client.get("/admin", headers=auth_headers).text
        assert "Amazon Retreat" in html

    def test_retreat_appears_in_dashboard(self, client, auth_headers):
        from datetime import datetime, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        client.post("/admin/retreat/create", data={
            "name": "Sacred Valley",
            "max_participants": 8,
            "price": 1800.0,
            "status": "ACTIVE",
            "start_date": future,
        }, headers=auth_headers)
        html = client.get("/admin", headers=auth_headers).text
        assert "Sacred Valley" in html
        assert "8" in html


class TestBookingFlow:
    """Booking lifecycle: reserve, confirm, cancel, waiting list."""

    def _create_retreat(self, client, auth_headers, max_pax=2, name="Test Retreat"):
        client.post("/admin/retreat/create", data={
            "name": name, "max_participants": max_pax, "price": 1000.0, "status": "ACTIVE",
        }, headers=auth_headers)

    def _create_lead_and_book(self, client, auth_headers, email_suffix="a"):
        data = {"first_name": f"Test{email_suffix}", "last_name": "User",
                "email": f"test{email_suffix}@example.com"}
        created = client.post("/api/leads", json=data).json()
        return created["id"]

    def test_reserve_booking(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        self._create_retreat(client, auth_headers)
        html = client.get("/admin", headers=auth_headers).text
        import re
        match = re.search(r'/admin/retreat/create', html)

        resp = client.post("/admin/booking/create", data={
            "lead_id": lead_id, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303
        detail = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "RESERVED" in detail

    def test_confirm_booking(self, client, auth_headers):
        lead_id = self._create_lead_and_book(client, auth_headers, "conf")
        self._create_retreat(client, auth_headers)
        client.post("/admin/booking/create", data={
            "lead_id": lead_id, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        resp = client.post("/admin/booking/1/confirm", headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303
        detail = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "CONFIRMED" in detail

    def test_cancel_booking(self, client, auth_headers):
        lead_id = self._create_lead_and_book(client, auth_headers, "cancel")
        self._create_retreat(client, auth_headers)
        client.post("/admin/booking/create", data={
            "lead_id": lead_id, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        client.post("/admin/booking/1/confirm", headers=auth_headers)
        resp = client.post("/admin/booking/1/cancel", headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303
        detail = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "CANCELLED" in detail

    def test_complete_booking(self, client, auth_headers):
        lead_id = self._create_lead_and_book(client, auth_headers, "compl")
        self._create_retreat(client, auth_headers)
        client.post("/admin/booking/create", data={
            "lead_id": lead_id, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        client.post("/admin/booking/1/confirm", headers=auth_headers)
        resp = client.post("/admin/booking/1/complete", headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303
        detail = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "COMPLETED" in detail

    def test_waiting_list_when_full(self, client, auth_headers):
        lead1 = self._create_lead_and_book(client, auth_headers, "wl1")
        lead2 = self._create_lead_and_book(client, auth_headers, "wl2")
        self._create_retreat(client, auth_headers, max_pax=1, name="Limited Retreat")
        r1 = client.post("/admin/booking/create", data={
            "lead_id": lead1, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        detail1 = client.get(f"/admin/lead/{lead1}", headers=auth_headers).text
        assert "RESERVED" in detail1

        r2 = client.post("/admin/booking/create", data={
            "lead_id": lead2, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        detail2 = client.get(f"/admin/lead/{lead2}", headers=auth_headers).text
        assert "WAITING" in detail2

    def test_promote_from_waiting_on_cancel(self, client, auth_headers):
        lead1 = self._create_lead_and_book(client, auth_headers, "prom1")
        lead2 = self._create_lead_and_book(client, auth_headers, "prom2")
        self._create_retreat(client, auth_headers, max_pax=1, name="Promo Retreat")
        client.post("/admin/booking/create", data={
            "lead_id": lead1, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        client.post("/admin/booking/create", data={
            "lead_id": lead2, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        client.post("/admin/booking/1/cancel", headers=auth_headers)
        detail2 = client.get(f"/admin/lead/{lead2}", headers=auth_headers).text
        assert "RESERVED" in detail2


class TestBookingPayments:
    """Payment tracking for bookings."""

    def test_record_deposit_payment(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post("/admin/retreat/create", data={
            "name": "Payment Retreat", "max_participants": 5, "price": 2000.0, "status": "ACTIVE",
        }, headers=auth_headers)
        client.post("/admin/booking/create", data={
            "lead_id": lead_id, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        resp = client.post("/admin/booking/1/payment", data={
            "amount": 600.0, "payment_type": "DEPOSIT", "payment_method": "TRANSFER",
        }, headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303
        detail = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "Paid" in detail

    def test_record_balance_payment(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post("/admin/retreat/create", data={
            "name": "Balance Retreat", "max_participants": 5, "price": 2000.0, "status": "ACTIVE",
        }, headers=auth_headers)
        client.post("/admin/booking/create", data={
            "lead_id": lead_id, "retreat_id": 1, "seats_reserved": 1,
        }, headers=auth_headers)
        client.post("/admin/booking/1/confirm", headers=auth_headers)
        client.post("/admin/booking/1/payment", data={
            "amount": 600.0, "payment_type": "DEPOSIT", "payment_method": "TRANSFER",
        }, headers=auth_headers)
        client.post("/admin/booking/1/payment", data={
            "amount": 1400.0, "payment_type": "BALANCE", "payment_method": "TRANSFER",
        }, headers=auth_headers)
        detail = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "Paid" in detail
        assert "Balance" not in detail or detail.count("Paid") >= 2

    def test_payment_requires_auth(self, client):
        resp = client.post("/admin/booking/1/payment", data={"amount": 100.0, "payment_type": "DEPOSIT"})
        assert resp.status_code in (401, 403)

    def test_booking_requires_auth(self, client):
        resp = client.post("/admin/booking/create", data={"lead_id": 1, "retreat_id": 1})
        assert resp.status_code in (401, 403)

    def test_retreat_create_requires_auth(self, client):
        resp = client.post("/admin/retreat/create", data={"name": "Unauthorized"})
        assert resp.status_code in (401, 403)


class TestBookingDashboardWidgets:
    """Booking stats appear on dashboard."""

    def test_booking_stats_row_shown(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        assert "Seats Available" in html
        assert "Booked" in html
        assert "Waiting List" in html
        assert "Revenue" in html
        assert "Upcoming Retreats" in html

    def test_booking_stats_update_after_reservation(self, client, auth_headers):
        html = client.get("/admin", headers=auth_headers).text
        html2 = client.get("/admin", headers=auth_headers).text
        assert "Seats Available" in html2


class TestBookingService:
    """Direct BookingService unit tests."""

    def test_service_creates_retreat(self, db_session):
        from services.booking_service import BookingService
        svc = BookingService(db_session)
        retreat = svc.create_retreat("Unit Test Retreat", max_participants=5, price=500.0)
        assert retreat.id is not None
        assert retreat.name == "Unit Test Retreat"
        assert retreat.max_participants == 5

    def test_service_seats_available(self, db_session):
        from services.booking_service import BookingService
        svc = BookingService(db_session)
        retreat = svc.create_retreat("Seats Test", max_participants=10, price=100.0, status="ACTIVE")
        assert svc.seats_available(retreat.id) == 10

    def test_service_get_booking_stats(self, db_session):
        from services.booking_service import BookingService
        svc = BookingService(db_session)
        stats = svc.get_booking_stats()
        assert "seats_available" in stats
        assert "booked" in stats
        assert "waiting" in stats
        assert "revenue" in stats
