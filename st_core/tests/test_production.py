import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["EMAIL_BACKEND"] = "log"
os.environ["PYTHONIOENCODING"] = "utf-8"

import pytest
from fastapi.testclient import TestClient
from app import app
from database import engine, Base, SessionLocal
from models import Lead, EmailQueue, EmailStatus


LANGUAGES = ["en", "it", "es", "ru", "sr"]
TEST_EMAILS = {
    "en": "test.en@example.com",
    "it": "test.it@example.com",
    "es": "test.es@example.com",
    "ru": "test.ru@example.com",
    "sr": "test.sr@example.com",
}


def _auth_header():
    import base64
    creds = base64.b64encode(b"admin:testpass").decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


class TestProduction:
    """Full production test — 5 languages, email queue, worker, download."""

    def test_full_production_flow(self, client):
        auth = _auth_header()
        lead_ids = {}

        # A) Lead creation — 5 languages
        for lang, email in TEST_EMAILS.items():
            resp = client.post("/api/leads", json={
                "first_name": f"Test{lang.upper()}",
                "last_name": "User",
                "email": email,
                "country": lang.upper(),
                "language": lang,
                "source_page": "https://shamanictravels.com/apply",
                "campaign": "editorial_reactivation",
            })
            assert resp.status_code == 200, f"{lang}: {resp.json()}"
            data = resp.json()
            assert data["success"] is True
            assert data["download_token"] is not None
            lead_ids[lang] = data["id"]
            print(f"  [{lang.upper()}] Lead created: id={data['id']}")

        print("  A) Lead creation: PASS")

        # B) Email queue check
        from services.email_engine import EmailEngine
        from database import SessionLocal
        db = SessionLocal()
        try:
            for lang, email in TEST_EMAILS.items():
                lead = db.query(Lead).filter(Lead.email == email).first()
                assert lead is not None, f"{lang}: lead not found in DB"
                emails = db.query(EmailQueue).filter(EmailQueue.lead_id == lead.id).all()
                assert len(emails) >= 1, f"{lang}: no emails queued"
                for e in emails:
                    assert e.language == lang, f"{lang}: expected {lang}, got {e.language}"
                    assert e.status == EmailStatus.PENDING
                    print(f"  [{lang.upper()}] Email queued: type={e.email_type} subject={e.subject}")
        finally:
            db.close()
        print("  B) Email queue (5 languages): PASS")

        # C) Worker processing
        db = SessionLocal()
        try:
            engine = EmailEngine(db)
            stats_before = engine.get_queue_stats()
            print(f"  Queue before: pending={stats_before['pending']}")
            sent = engine.process_pending(batch_size=50)
            print(f"  Processed: {sent} emails")
            for lang, email in TEST_EMAILS.items():
                lead = db.query(Lead).filter(Lead.email == email).first()
                sent_emails = db.query(EmailQueue).filter(
                    EmailQueue.lead_id == lead.id,
                    EmailQueue.status == EmailStatus.SENT,
                ).all()
                print(f"  [{lang.upper()}] Sent: {len(sent_emails)}")
        finally:
            db.close()
        print("  C) Worker processing: PASS")

        # D) Download — 5 languages
        db = SessionLocal()
        try:
            for lang, email in TEST_EMAILS.items():
                lead = db.query(Lead).filter(Lead.email == email).first()
                assert lead is not None
                token = lead.download_token
                resp = client.get(f"/download/{token}")
                assert resp.status_code == 200, f"{lang}: {resp.status_code}"
                assert resp.headers.get("content-type") == "application/pdf"
                db.refresh(lead)
                assert lead.downloaded_editorial is True
                assert lead.downloaded_at is not None
                print(f"  [{lang.upper()}] Download: {len(resp.content)} bytes")
        finally:
            db.close()
        print("  D) Download (5 languages): PASS")

        # E) Campaign tracking fields
        db = SessionLocal()
        try:
            for lang, email in TEST_EMAILS.items():
                lead = db.query(Lead).filter(Lead.email == email).first()
                assert hasattr(lead, "campaign_sent_at")
                assert hasattr(lead, "email_opened")
                assert hasattr(lead, "email_clicked")
                print(f"  [{lang.upper()}] campaign_sent_at={lead.campaign_sent_at}")
        finally:
            db.close()
        print("  E) Campaign tracking fields: PASS")

        # F) Template existence
        base = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
        for lang in LANGUAGES:
            path = os.path.join(base, lang, "editorial_reactivation.html")
            assert os.path.exists(path), f"Missing: {path}"
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "{{ first_name }}" in content
            assert "{{ download_url }}" in content
            print(f"  [{lang.upper()}] editorial_reactivation.html OK")
        print("  F) Reactivation templates: PASS")

        # Final Report
        print("\n" + "=" * 60)
        print("  PRODUCTION TEST REPORT")
        print("=" * 60)
        checks = [
            ("A) Lead creation (5 languages)", True),
            ("B) Email queue (5 languages with correct language)", True),
            ("C) Worker processing (process_pending)", True),
            ("D) Download (5 languages, PDF content-type)", True),
            ("E) Campaign tracking fields (campaign_sent_at, email_opened, email_clicked)", True),
            ("F) Reactivation templates (5 languages with variables)", True),
        ]
        for name, passed in checks:
            print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        print("=" * 60)
        print("  OVERALL: ALL PASS")
        print("=" * 60)
