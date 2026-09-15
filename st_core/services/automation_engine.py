import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from models import EmailQueue, Lead, LeadStatus
from services.email_engine import EmailEngine, TEMPLATE_SUBJECTS, DOWNLOAD_EMAIL_TYPES
from services.task_service import TaskService
from config import settings

logger = logging.getLogger("st_core.automation_engine")

EDITORIAL_DELAY_HOURS = 1
FOLLOWUP_DELAY_DAYS = 3
JOURNEY_REMINDER_DELAY_DAYS = 7
INTERVIEW_DELAY_HOURS = 2
COMPLETION_DELAY_HOURS = 24
APPROVED_DELAY_HOURS = 2
REJECTED_DELAY_HOURS = 1
REACTIVATION_DELAY_HOURS = 0

ACTIVE_STATUSES = ("PENDING", "PROCESSING", "RETRY")


def _download_payload(lead: Lead) -> dict:
    return {
        "download_token": lead.download_token,
        "download_url": f"{settings.PUBLIC_URL}/download/{lead.download_token}" if lead.download_token else None,
    }


class AutomationEngine:
    def __init__(self, db: Session):
        self.db = db
        self.engine = EmailEngine(db)

    def _queue(self, lead: Lead, email_type: str, subject, template_name: str,
               payload: dict | None = None, scheduled_for: datetime | None = None) -> EmailQueue | None:
        """queue_email con guardia: le email che promettono un download NON
        vengono mai accodate se non esiste un download_url valido."""
        if email_type in DOWNLOAD_EMAIL_TYPES:
            resolved = EmailEngine.resolve_download_url(lead, payload)
            if not resolved:
                logger.error(
                    "GUARD: %s blocked for lead %d (%s) — no valid download_url, not queued",
                    email_type, lead.id, lead.email,
                )
                return None
        try:
            return self.engine.queue_email(
                lead=lead,
                email_type=email_type,
                subject=subject,
                template_name=template_name,
                payload=payload,
                scheduled_for=scheduled_for,
            )
        except Exception as e:
            logger.exception("Failed to queue %s for lead %d: %s", email_type, lead.id, e)
            return None

    def on_lead_created(self, lead: Lead) -> list[EmailQueue]:
        queued = []
        # Un nuovo lead non ha ancora scaricato: gli va inviata la email di download.
        if not lead.downloaded_editorial:
            e = self._queue(
                lead=lead,
                email_type="editorial_download",
                subject=TEMPLATE_SUBJECTS["editorial_download"],
                template_name="editorial_download",
                payload=_download_payload(lead),
                scheduled_for=datetime.now(timezone.utc) + timedelta(hours=EDITORIAL_DELAY_HOURS),
            )
            if e:
                queued.append(e)

        e = self._queue(
            lead=lead,
            email_type="followup_3_days",
            subject=TEMPLATE_SUBJECTS["followup_3_days"],
            template_name="followup_3_days",
            scheduled_for=datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DELAY_DAYS),
        )
        if e:
            queued.append(e)

        try:
            TaskService(self.db).auto_create_followup_reminders(lead)
        except Exception as e:
            logger.exception("Failed to auto-create followup reminders for lead %d: %s", lead.id, e)

        return queued

    def on_editorial_download(self, lead: Lead) -> list[EmailQueue]:
        queued = []
        existing = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.lead_id == lead.id,
                EmailQueue.email_type == "editorial_download",
                EmailQueue.status.in_(ACTIVE_STATUSES),
            )
            .count()
        )
        if not existing:
            e = self._queue(
                lead=lead,
                email_type="editorial_download",
                subject=TEMPLATE_SUBJECTS["editorial_download"],
                template_name="editorial_download",
                payload=_download_payload(lead),
                scheduled_for=datetime.now(timezone.utc) + timedelta(hours=EDITORIAL_DELAY_HOURS),
            )
            if e:
                queued.append(e)

        if lead.campaign == "editorial_reactivation_2025":
            fup_existing = (
                self.db.query(EmailQueue)
                .filter(
                    EmailQueue.lead_id == lead.id,
                    EmailQueue.email_type == "followup_3_days",
                    EmailQueue.status.in_(ACTIVE_STATUSES),
                )
                .count()
            )
            if not fup_existing:
                fup = self._queue(
                    lead=lead,
                    email_type="followup_3_days",
                    subject=TEMPLATE_SUBJECTS["followup_3_days"],
                    template_name="followup_3_days",
                    payload=_download_payload(lead),
                    scheduled_for=datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DELAY_DAYS),
                )
                if fup:
                    queued.append(fup)

        return queued

    def on_campaign_reactivation(self, lead: Lead) -> list[EmailQueue]:
        # Idempotenza: se esiste QUALSIASI entry (anche SENT/FAILED), non ri-accodare.
        existing = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.lead_id == lead.id,
                EmailQueue.email_type == "editorial_reactivation",
            )
            .count()
        )
        if existing:
            logger.info("Reactivation already queued/sent for lead %d, skipping", lead.id)
            return []

        payload = _download_payload(lead)
        if not EmailEngine.resolve_download_url(lead, payload):
            logger.error(
                "GUARD: editorial_reactivation blocked for lead %d (%s) — no valid download_url, not queued",
                lead.id, lead.email,
            )
            return []

        lead.campaign = "editorial_reactivation_2025"
        lead.campaign_sent_at = datetime.now(timezone.utc)
        self.db.flush()
        e = self._queue(
            lead=lead,
            email_type="editorial_reactivation",
            subject=TEMPLATE_SUBJECTS["editorial_reactivation"],
            template_name="editorial_reactivation",
            payload=payload,
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=REACTIVATION_DELAY_HOURS),
        )
        return [e] if e else []

    def on_status_changed(self, lead: Lead, old_status: LeadStatus, new_status: LeadStatus) -> list[EmailQueue]:
        queued = []
        now = datetime.now(timezone.utc)

        if new_status == LeadStatus.INTERVIEW and old_status in (LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.OPENED, LeadStatus.CLICKED, LeadStatus.DOWNLOADED, LeadStatus.QUALIFIED):
            e = self.engine.queue_email(
                lead=lead,
                email_type="interview_invitation",
                subject=TEMPLATE_SUBJECTS["interview_invitation"],
                template_name="interview_invitation",
                scheduled_for=now + timedelta(hours=INTERVIEW_DELAY_HOURS),
            )
            queued.append(e)

        if new_status == LeadStatus.APPROVED:
            e = self.engine.queue_email(
                lead=lead,
                email_type="approved",
                subject=TEMPLATE_SUBJECTS["approved"],
                template_name="approved",
                scheduled_for=now + timedelta(hours=APPROVED_DELAY_HOURS),
            )
            queued.append(e)

        if new_status == LeadStatus.REJECTED:
            e = self.engine.queue_email(
                lead=lead,
                email_type="rejected",
                subject=TEMPLATE_SUBJECTS["rejected"],
                template_name="rejected",
                scheduled_for=now + timedelta(hours=REJECTED_DELAY_HOURS),
            )
            queued.append(e)

        if new_status == LeadStatus.BOOKED:
            e = self.engine.queue_email(
                lead=lead,
                email_type="journey_reminder",
                subject=TEMPLATE_SUBJECTS["journey_reminder"],
                template_name="journey_reminder",
                scheduled_for=now + timedelta(days=JOURNEY_REMINDER_DELAY_DAYS),
            )
            queued.append(e)

        if new_status == LeadStatus.COMPLETED:
            e = self.engine.queue_email(
                lead=lead,
                email_type="completion",
                subject=TEMPLATE_SUBJECTS["completion"],
                template_name="completion",
                scheduled_for=now + timedelta(hours=COMPLETION_DELAY_HOURS),
            )
            queued.append(e)

        return queued
