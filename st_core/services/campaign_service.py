import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import EmailQueue, EmailStatus, Lead
from services.automation_engine import AutomationEngine
from services.email_engine import TEMPLATE_SUBJECTS

logger = logging.getLogger("st_core.campaign_service")

CAMPAIGN_NAME = "editorial_reactivation_2025"
DAILY_LIMIT = 90
ERROR_THRESHOLD = 5
SEND_WINDOW_START = 9  # 9:00
SEND_WINDOW_END = 20    # 20:00


class CampaignService:
    def __init__(self, db: Session):
        self.db = db
        self.automation = AutomationEngine(db)

    def rate_remaining(self) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.email_type == "editorial_reactivation",
                EmailQueue.created_at >= today_start,
                EmailQueue.status.in_([EmailStatus.SENT, EmailStatus.PROCESSING]),
            )
            .count()
        )
        return max(0, DAILY_LIMIT - sent_today)

    def error_count_today(self) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.email_type == "editorial_reactivation",
                EmailQueue.created_at >= today_start,
                EmailQueue.status == EmailStatus.FAILED,
            )
            .count()
        )

    def can_send_today(self) -> tuple[bool, str]:
        remaining = self.rate_remaining()
        if remaining <= 0:
            return False, "Daily limit reached (90/90)"
        errors = self.error_count_today()
        if errors >= ERROR_THRESHOLD:
            return False, f"Error threshold exceeded ({errors}/{ERROR_THRESHOLD})"
        now = datetime.now(timezone.utc)
        hour = now.hour
        if hour < SEND_WINDOW_START or hour >= SEND_WINDOW_END:
            return False, f"Outside send window ({SEND_WINDOW_START}:00-{SEND_WINDOW_END}:00 UTC)"
        return True, f"Ok (remaining={remaining}, errors={errors})"

    def get_unsent_campaign_leads(self) -> list[Lead]:
        return (
            self.db.query(Lead)
            .filter(
                Lead.campaign.is_(None),
                Lead.source == "mailchimp_reactivation",
                Lead.downloaded_editorial.is_(False),
            )
            .order_by(Lead.id)
            .all()
        )

    def get_campaign_leads(self) -> list[Lead]:
        return (
            self.db.query(Lead)
            .filter(
                Lead.campaign == CAMPAIGN_NAME,
                Lead.source == "mailchimp_reactivation",
            )
            .order_by(Lead.id)
            .all()
        )

    def check_db_ready(self) -> list[str]:
        issues = []
        total = (
            self.db.query(Lead)
            .filter(
                Lead.campaign.is_(None),
                Lead.source == "mailchimp_reactivation",
                Lead.downloaded_editorial.is_(False),
            )
            .count()
        )
        if total == 0:
            issues.append("No leads available for reactivation (all already have campaign or downloaded)")
        languages = (
            self.db.query(Lead.language)
            .filter(
                Lead.campaign.is_(None),
                Lead.source == "mailchimp_reactivation",
                Lead.downloaded_editorial.is_(False),
            )
            .distinct()
            .all()
        )
        lang_list = [l[0] for l in languages]
        lang_str = ", ".join(lang_list)
        issues.append(f"Leads available: {total} (languages: {lang_str})")
        for lang in lang_list:
            if lang not in TEMPLATE_SUBJECTS.get("editorial_reactivation", {}):
                issues.append(f"  WARNING: no subject template for language '{lang}'")
        return issues

    def schedule_campaign_emails(self, dry_run: bool = True) -> dict:
        result = {
            "dry_run": dry_run,
            "leads_processed": 0,
            "emails_queued": 0,
            "errors": [],
            "schedule_preview": [],
        }

        leads = self.get_unsent_campaign_leads()
        if not leads:
            result["errors"].append("No leads to process")
            return result

        remaining = self.rate_remaining() if not dry_run else 999
        daily_cap = remaining if not dry_run else 999

        now = datetime.now(timezone.utc)
        base_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if base_time <= now:
            base_time = now + timedelta(hours=1)
        slot_minutes = 0

        for idx, lead in enumerate(leads):
            if idx >= daily_cap:
                result["errors"].append(f"Daily cap reached ({idx} queued, limit {daily_cap})")
                break

            download_url = (
                f"{settings.PUBLIC_URL}/download/{lead.download_token}"
                if lead.download_token
                else None
            )
            if not download_url:
                result["errors"].append(f"Lead {lead.id}: no download_token, skipping")
                continue

            if not dry_run:
                try:
                    emails = self.automation.on_campaign_reactivation(lead)
                    self.db.commit()
                    result["emails_queued"] += len(emails)
                except Exception as e:
                    self.db.rollback()
                    result["errors"].append(f"Lead {lead.id} failed: {e}")
                    continue
            else:
                subject_dict = TEMPLATE_SUBJECTS["editorial_reactivation"]
                lang = lead.language or "en"
                subjects_list = subject_dict.get(lang, subject_dict.get("en", []))
                if isinstance(subjects_list, list):
                    import random
                    subject = random.choice(subjects_list)
                else:
                    subject = str(subjects_list)

            result["leads_processed"] += 1
            scheduled = base_time + timedelta(minutes=slot_minutes)
            slot_minutes += int(1440 / min(daily_cap, len(leads)))
            result["schedule_preview"].append(
                {
                    "id": lead.id,
                    "name": f"{lead.first_name} {lead.last_name or ''}".strip(),
                    "email": lead.email,
                    "language": lead.language or "en",
                    "subject_preview": subject if dry_run else "queued",
                    "scheduled": scheduled.isoformat() if dry_run else None,
                }
            )

        return result

    def dry_run(self) -> dict:
        result = {
            "campaign": CAMPAIGN_NAME,
            "daily_limit": DAILY_LIMIT,
            "send_window": f"{SEND_WINDOW_START}:00-{SEND_WINDOW_END}:00 UTC",
            "check_output": self.check_db_ready(),
            "schedule": self.schedule_campaign_emails(dry_run=True),
        }

        total_missing = 0
        total_present = 0
        lang_counts: Counter = Counter()

        leads = (
            self.db.query(Lead)
            .filter(
                Lead.campaign.is_(None),
                Lead.source == "mailchimp_reactivation",
                Lead.downloaded_editorial.is_(False),
            )
            .all()
        )
        for lead in leads:
            lang_counts[lead.language or "en"] += 1
            total_present += 1

        result["total_leads_found"] = total_present
        result["language_distribution"] = dict(lang_counts)
        result["total_days_estimated"] = max(1, (total_present + DAILY_LIMIT - 1) // DAILY_LIMIT)

        preview_limit = 10
        preview = result["schedule"]["schedule_preview"][:preview_limit]
        result["schedule_preview_first_n"] = preview
        result["schedule_preview_total"] = len(result["schedule"]["schedule_preview"])
        return result

    def get_lead_stats(self) -> dict:
        sent = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.email_type == "editorial_reactivation",
                EmailQueue.status == EmailStatus.SENT,
            )
            .count()
        )
        opened = (
            self.db.query(Lead)
            .filter(
                Lead.campaign == CAMPAIGN_NAME,
                Lead.email_opened == True,
            )
            .count()
        )
        clicked = (
            self.db.query(Lead)
            .filter(
                Lead.campaign == CAMPAIGN_NAME,
                Lead.email_clicked == True,
            )
            .count()
        )
        downloaded = (
            self.db.query(Lead)
            .filter(
                Lead.campaign == CAMPAIGN_NAME,
                Lead.downloaded_editorial == True,
            )
            .count()
        )
        failed = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.email_type == "editorial_reactivation",
                EmailQueue.status == EmailStatus.FAILED,
            )
            .count()
        )
        pending = (
            self.db.query(EmailQueue)
            .filter(
                EmailQueue.email_type == "editorial_reactivation",
                EmailQueue.status == EmailStatus.PENDING,
            )
            .count()
        )
        return {
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "downloaded": downloaded,
            "failed": failed,
            "pending": pending,
            "total_scheduled": sent + failed + pending,
        }
