import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["PROJECT_NAME"] = "ST CORE Test"
os.environ["DATABASE_URL"] = "sqlite:///./test_shamanic.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass"
os.environ["CONTACT_EMAIL"] = "test@example.com"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["EMAIL_BACKEND"] = "log"
os.environ["DEBUG"] = "true"

import pytest
from fastapi.testclient import TestClient
from app import app
from database import engine, Base, SessionLocal


def _clean_db():
    import time
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    for _ in range(5):
        try:
            if os.path.exists("./test_shamanic.db"):
                os.remove("./test_shamanic.db")
            break
        except PermissionError:
            time.sleep(0.1)


@pytest.fixture(scope="function", autouse=True)
def _db():
    _clean_db()
    Base.metadata.create_all(bind=engine)
    yield
    _clean_db()


@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def auth_headers():
    import base64
    creds = base64.b64encode(b"admin:testpass").decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture
def sample_lead_data():
    return {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        "country": "UK",
        "language": "en",
        "source_page": "https://shamanictravels.com/apply",
        "campaign": "summer2026",
        "referrer": "https://google.com/search",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "summer_sale",
    }


@pytest.fixture(autouse=True)
def _ensure_all_ebooks():
    import os as _os
    _os.makedirs("./ebooks", exist_ok=True)
    for fname in [
        "Il_Ritiro_Nella_Selva_EN.pdf",
        "Il_Ritiro_Nella_Selva_IT.pdf",
        "Il_Ritiro_Nella_Selva_ES.pdf",
        "Il_Ritiro_Nella_Selva_RU.pdf",
        "Il_Ritiro_Nella_Selva_SR.pdf",
    ]:
        path = f"./ebooks/{fname}"
        if not _os.path.exists(path):
            with open(path, "wb") as f:
                f.write(f"%PDF-dummy {fname}".encode())
