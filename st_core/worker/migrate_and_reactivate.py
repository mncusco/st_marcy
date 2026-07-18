"""
Run directly on Railway server or locally:
   python worker/migrate_and_reactivate.py

1. Migrates DB schema (adds campaign columns) via raw SQL
2. Iterates all leads, calls on_campaign_reactivation() for each
3. Runs process_pending() to send immediately
"""
import os, sys, logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("EMAIL_BACKEND", "smtp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reactivate")

from database import engine, SessionLocal
from sqlalchemy import text
from models import Lead, EmailQueue
from services.automation_engine import AutomationEngine
from services.email_engine import EmailEngine


def migrate_schema():
    """Add campaign tracking columns if they don't exist."""
    dialect = engine.dialect.name
    logger.info("Database dialect: %s", dialect)
    with engine.connect() as conn:
        if dialect == "sqlite":
            # SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
            # Check if column exists first
            result = conn.execute(text("PRAGMA table_info(leads)")).fetchall()
            cols = {row[1] for row in result}
            if "campaign_sent_at" not in cols:
                conn.execute(text("ALTER TABLE leads ADD COLUMN campaign_sent_at TIMESTAMP"))
                logger.info("Added column: campaign_sent_at")
            if "email_opened" not in cols:
                conn.execute(text("ALTER TABLE leads ADD COLUMN email_opened BOOLEAN DEFAULT 0"))
                logger.info("Added column: email_opened")
            if "email_clicked" not in cols:
                conn.execute(text("ALTER TABLE leads ADD COLUMN email_clicked BOOLEAN DEFAULT 0"))
                logger.info("Added column: email_clicked")
        else:
            # PostgreSQL / Neon
            for col, dtype in [("campaign_sent_at", "TIMESTAMP"), ("email_opened", "BOOLEAN DEFAULT FALSE"), ("email_clicked", "BOOLEAN DEFAULT FALSE")]:
                try:
                    conn.execute(text(f"ALTER TABLE leads ADD COLUMN IF NOT EXISTS {col} {dtype}"))
                    logger.info("Added column: %s", col)
                except Exception as e:
                    logger.warning("Could not add %s: %s", col, e)
        conn.commit()


def reactivate_all_leads():
    db = SessionLocal()
    try:
        leads = db.query(Lead).order_by(Lead.id).all()
        logger.info("Found %d leads total", len(leads))

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
                logger.info("  Queued reactivation for lead %d (%s, lang=%s)", lead.id, lead.email, lead.language)
            db.commit()

        logger.info("Done: %d queued, %d skipped (already queued)", queued, skipped)

        # Process immediately
        if queued > 0:
            logger.info("Processing pending emails...")
            sent = EmailEngine(db).process_pending(batch_size=100)
            logger.info("Sent %d emails", sent)
    finally:
        db.close()


if __name__ == "__main__":
    migrate_schema()
    reactivate_all_leads()
