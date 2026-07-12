import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from config import settings
from models import EmailQueue, EmailStatus, Lead
from schemas import EmailQueueResponse
from providers import ConsoleProvider, SmtpProvider, ResendProvider, SendgridProvider

logger = logging.getLogger("st_core.email_engine")

BACKEND_MAP = {
    "log": ConsoleProvider,
    "console": ConsoleProvider,
    "smtp": SmtpProvider,
    "resend": ResendProvider,
    "sendgrid": SendgridProvider,
}

TEMPLATE_SUBJECTS = {
    "editorial_download": "Your Free Editorial – ST Care",
    "followup_3_days": "Still Thinking? – ST Care",
    "interview_invitation": "Interview Invitation – ST Care",
    "approved": "Application Approved – ST Care",
    "rejected": "Application Update – ST Care",
    "journey_reminder": "Your Journey with ST Care",
    "completion": "Thank You – ST Care",
}

class EmailEngine:
    def __init__(self, db: Session):
        self.db = db

    def _get_backend(self):
        key = settings.EMAIL_BACKEND.lower()
        cls = BACKEND_MAP.get(key, ConsoleProvider)
        return cls()

    def send_test_email(self, to: str) -> dict:
        try:
            html_body = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f2ec;color:#2c2c2c;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e8e3da;padding:40px;">
<div style="text-align:center;margin-bottom:30px;"><span style="font-size:24px;letter-spacing:2px;color:#2d5a27;">ST</span> <span style="font-size:24px;letter-spacing:2px;color:#b89a5a;">CARE</span></div>
<h1 style="font-size:20px;font-weight:400;letter-spacing:1px;color:#2d5a27;text-align:center;">Test Email</h1>
<p style="font-size:14px;line-height:1.6;margin-top:24px;">This is a test email from ST CORE.</p>
<p style="font-size:14px;line-height:1.6;">Backend: <strong>{settings.EMAIL_BACKEND}</strong></p>
<p style="font-size:14px;line-height:1.6;">If you received this, your email configuration is working correctly.</p>
<p style="font-size:14px;line-height:1.6;margin-top:24px;">— ST CORE</p>
</div></body></html>"""
            backend = self._get_backend()
            success = backend.send(
                to=to,
                subject=f"Test Email from ST CORE ({settings.EMAIL_BACKEND})",
                html_body=html_body,
                lead_id=0,
                email_type="test",
            )
            return {"success": success, "backend": settings.EMAIL_BACKEND, "to": to}
        except Exception as e:
            logger.exception("Test email failed: %s", e)
            return {"success": False, "error": str(e)}

    def render_template(self, template_name: str, language: str, context: dict) -> str:
        import os
        from jinja2 import Environment, FileSystemLoader

        templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
        loader = FileSystemLoader(templates_dir, encoding="utf-8")
        env = Environment(loader=loader)

        paths = [f"{language}/{template_name}.html"]
        if language != "en":
            paths.append(f"en/{template_name}.html")

        for tmpl in paths:
            try:
                t = env.get_template(tmpl)
                return t.render(**context)
            except Exception:
                continue

        raise FileNotFoundError(f"Template not found in any language: {template_name}")

    def queue_email(
        self,
        lead: Lead,
        email_type: str,
        subject: str,
        template_name: str,
        payload: Optional[dict] = None,
        scheduled_for: Optional[datetime] = None,
    ) -> EmailQueue:
        lang = lead.language or "en"
        normalized = lang.lower().split("-")[0]
        if normalized not in ("en", "it", "es", "ru", "sr"):
            normalized = "en"

        entry = EmailQueue(
            lead_id=lead.id,
            email_type=email_type,
            subject=subject,
            language=normalized,
            status=EmailStatus.PENDING,
            template_name=template_name,
            payload_json=json.dumps(payload) if payload else None,
            scheduled_for=scheduled_for or datetime.utcnow(),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        logger.info("Queued %s email for lead %d (id=%d)", email_type, lead.id, entry.id)
        return entry

    def cancel_email(self, email_id: int) -> bool:
        entry = self.db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
        if not entry or entry.status in (EmailStatus.SENT, EmailStatus.CANCELLED):
            return False
        entry.status = EmailStatus.CANCELLED
        self.db.commit()
        return True

    def retry_email(self, email_id: int) -> bool:
        entry = self.db.query(EmailQueue).filter(EmailQueue.id == email_id).first()
        if not entry or entry.status != EmailStatus.FAILED:
            return False
        entry.status = EmailStatus.PENDING
        entry.attempts = 0
        entry.error_message = None
        self.db.commit()
        return True

    def _render_and_send(self, entry: EmailQueue) -> bool:
        lead = self.db.query(Lead).filter(Lead.id == entry.lead_id).first()
        if not lead:
            logger.error("Lead %d not found for email %d", entry.lead_id, entry.id)
            return False

        try:
            payload = json.loads(entry.payload_json) if entry.payload_json else {}
            context = {
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "language": entry.language,
                "_contact_email": settings.CONTACT_EMAIL,
                **payload,
            }
            html_body = self.render_template(entry.template_name, entry.language, context)

            backend = self._get_backend()
            success = backend.send(
                to=lead.email,
                subject=entry.subject,
                html_body=html_body,
                lead_id=lead.id,
                email_type=entry.email_type,
            )
            return success
        except Exception as e:
            logger.exception("Failed to render/send email %d: %s", entry.id, e)
            return False

    def process_pending(self, batch_size: int = 20) -> int:
        max_retries = settings.EMAIL_MAX_RETRIES
        entries = (
            self.db.query(EmailQueue)
            .filter(EmailQueue.status == EmailStatus.PENDING)
            .filter(EmailQueue.scheduled_for <= datetime.utcnow())
            .filter(EmailQueue.attempts < max_retries)
            .order_by(EmailQueue.created_at.asc())
            .limit(batch_size)
            .all()
        )

        sent_count = 0
        for entry in entries:
            entry.status = EmailStatus.PROCESSING
            entry.attempts += 1
            self.db.commit()

            success = self._render_and_send(entry)
            if success:
                entry.status = EmailStatus.SENT
                entry.sent_at = datetime.utcnow()
                sent_count += 1
            else:
                if entry.attempts >= max_retries:
                    entry.status = EmailStatus.FAILED
                    entry.error_message = f"Failed after {entry.attempts} attempts"
                else:
                    entry.status = EmailStatus.PENDING
                    entry.error_message = f"Attempt {entry.attempts}/{max_retries} failed"
            self.db.commit()

        return sent_count

    def get_queue_stats(self):
        total = self.db.query(func.count(EmailQueue.id)).scalar() or 0
        pending = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.PENDING)
            .scalar()
            or 0
        )
        processing = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.PROCESSING)
            .scalar()
            or 0
        )
        failed = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.FAILED)
            .scalar()
            or 0
        )
        sent = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.SENT)
            .scalar()
            or 0
        )
        cancelled = (
            self.db.query(func.count(EmailQueue.id))
            .filter(EmailQueue.status == EmailStatus.CANCELLED)
            .scalar()
            or 0
        )
        total_retries = (
            self.db.query(func.sum(EmailQueue.attempts))
            .filter(EmailQueue.status != EmailStatus.PENDING)
            .scalar()
            or 0
        )
        max_retries = settings.EMAIL_MAX_RETRIES
        return {
            "total": total,
            "pending": pending,
            "processing": processing,
            "failed": failed,
            "sent": sent,
            "cancelled": cancelled,
            "total_retries": total_retries,
            "max_retries": max_retries,
        }

    def get_recent_emails(self, limit: int = 50):
        entries = (
            self.db.query(EmailQueue)
            .order_by(EmailQueue.created_at.desc())
            .limit(limit)
            .all()
        )
        return [EmailQueueResponse.model_validate(e) for e in entries]
