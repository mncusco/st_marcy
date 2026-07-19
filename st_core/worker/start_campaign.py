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

logger.info("PUBLIC_URL=%s", settings.PUBLIC_URL)

db = SessionLocal()
try:
    leads = db.query(Lead).order_by(Lead.id).all()
    total = len(leads)
    logger.info("Found %d leads total", total)
    
    queued = 0
    skipped = 0
    for lead in leads:
        existing = db.query(EmailQueue).filter(
            EmailQueue.lead_id == lead.id,
            EmailQueue.email_type == "editorial_reactivation",
            EmailQueue.status.in_(["PENDING", "PROCESSING"]),
        ).count()
        if existing:
            skipped += 1
            continue
        engine = AutomationEngine(db)
        result = engine.on_campaign_reactivation(lead)
        if result:
            queued += 1
        db.commit()
    
    logger.info("Done: %d queued, %d skipped (already queued) of %d total", queued, skipped, total)
finally:
    db.close()
