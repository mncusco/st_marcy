"""
Run on Railway: railway run python /app/start_campaign.py
Or copy this file to the app directory first.
"""
import os, sys, logging

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("EMAIL_BACKEND", "smtp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("start_campaign")

from database import SessionLocal
from models import Lead, EmailQueue
from services.automation_engine import AutomationEngine
from config import settings


def run_campaign(db) -> dict:
    leads = db.query(Lead).order_by(Lead.id).all()
    total = len(leads)
    queued = 0
    skipped = 0
    for lead in leads:
        existing = db.query(EmailQueue).filter(
            EmailQueue.lead_id == lead.id,
            EmailQueue.email_type == "editorial_reactivation",
        ).count()
        if existing:
            skipped += 1
            continue
        result = AutomationEngine(db).on_campaign_reactivation(lead)
        if result:
            queued += 1
        db.commit()
    return {"queued": queued, "skipped": skipped, "total": total}


def main():
    logger.info("PUBLIC_URL=%s", settings.PUBLIC_URL)
    db = SessionLocal()
    try:
        result = run_campaign(db)
        logger.info(
            "Done: %d queued, %d skipped (already queued) of %d total",
            result["queued"], result["skipped"], result["total"],
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
