import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models import EmailQueue, Lead, LeadStatus
from services.email_engine import EmailEngine, TEMPLATE_SUBJECTS
from services.task_service import TaskService

logger = logging.getLogger("st_core.automation_engine")

EDITORIAL_DELAY_HOURS = 1
FOLLOWUP_DELAY_DAYS = 3
JOURNEY_REMINDER_DELAY_DAYS = 7
INTERVIEW_DELAY_HOURS = 2
COMPLETION_DELAY_HOURS = 24
APPROVED_DELAY_HOURS = 2
REJECTED_DELAY_HOURS = 1

class AutomationEngine:
    def __init__(self, db: Session):
        self.db = db
        self.engine = EmailEngine(db)

    def on_lead_created(self, lead: Lead) -> list[EmailQueue]:
        queued = []
        if lead.downloaded_editorial:
            e = self.engine.queue_email(
                lead=lead,
                email_type="editorial_download",
                subject=TEMPLATE_SUBJECTS["editorial_download"],
                template_name="editorial_download",
                payload={"download_token": lead.download_token},
                scheduled_for=datetime.utcnow() + timedelta(hours=EDITORIAL_DELAY_HOURS),
            )
            queued.append(e)

        e = self.engine.queue_email(
            lead=lead,
            email_type="followup_3_days",
            subject=TEMPLATE_SUBJECTS["followup_3_days"],
            template_name="followup_3_days",
            scheduled_for=datetime.utcnow() + timedelta(days=FOLLOWUP_DELAY_DAYS),
        )
        queued.append(e)

        try:
            TaskService(self.db).auto_create_followup_reminders(lead)
        except Exception as e:
            logger.error("Failed to auto-create followup reminders for lead %d: %s", lead.id, e)

        return queued

    def on_editorial_download(self, lead: Lead) -> list[EmailQueue]:
        existing = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.lead_id == lead.id,
                EmailQueue.email_type == "editorial_download",
                EmailQueue.status.in_(["PENDING", "PROCESSING"]),
            )
            .count()
        )
        if existing:
            return []

        e = self.engine.queue_email(
            lead=lead,
            email_type="editorial_download",
            subject=TEMPLATE_SUBJECTS["editorial_download"],
            template_name="editorial_download",
            payload={"download_token": lead.download_token},
            scheduled_for=datetime.utcnow() + timedelta(hours=EDITORIAL_DELAY_HOURS),
        )
        return [e]

    def on_status_changed(self, lead: Lead, old_status: LeadStatus, new_status: LeadStatus) -> list[EmailQueue]:
        queued = []
        now = datetime.utcnow()

        if new_status == LeadStatus.INTERVIEW and old_status in (LeadStatus.NEW, LeadStatus.CONTACTED):
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
