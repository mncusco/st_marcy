import os, sys, re, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["PROJECT_NAME"] = "ST CORE Test"
os.environ["DATABASE_URL"] = "sqlite:///./test_shamanic.db"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass"
os.environ["CONTACT_EMAIL"] = "test@example.com"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["EMAIL_BACKEND"] = "log"
os.environ["DEBUG"] = "true"

from fastapi.testclient import TestClient
from app import app
from database import engine, Base

Base.metadata.create_all(bind=engine)
client = TestClient(app)
auth = {"Authorization": f"Basic {base64.b64encode(b'admin:testpass').decode()}"}

# Create lead
import random
email = f"test{random.randint(10000,99999)}@test.com"
resp = client.post("/api/leads", json={
    "first_name": "Test", "last_name": "User", "email": email
})
lead_id = resp.json()["id"]
print(f"Lead id={lead_id} created")

# Check lead detail page
html = client.get(f"/admin/lead/{lead_id}", headers=auth).text
types = re.findall(r'class="email-type">([^<]+)', html)
print(f"Lead detail email types: {types}")

# Show the email section of lead detail
import re
# Find everything between "Email History" and the next card
idx = html.find("Email History")
if idx >= 0:
    context = html[idx:idx+2000]
    print(f"Full context around Email History ({len(context)} chars):")
    print(repr(context))
    print("=" * 80)
else:
    print("'Email History' not found!")
    for line in html.split('\n'):
        if 'email' in line.lower() or 'queue' in line.lower() or 'placeholder' in line.lower():
            print(f"  LINE: {line.strip()[:150]}")

# Also check lead_emails directly
from schemas import EmailQueueResponse
from services.email_engine import EmailEngine
from database import SessionLocal
db = SessionLocal()
engine = EmailEngine(db)
all_emails = engine.get_recent_emails()
print(f"\nAll recent emails count: {len(all_emails)}")
for e in all_emails:
    print(f"  Email id={e.id} lead_id={e.lead_id} (type {type(e.lead_id)}) type={e.email_type}")
lead_emails = [e for e in all_emails if e.lead_id == lead_id]
print(f"Lead emails filtered: {len(lead_emails)}")
db.close()

# Now check what the route handler would do with a NEW session
from dependencies import get_db as get_db_gen
gen = get_db_gen()
route_db = next(gen)
route_engine = EmailEngine(route_db)
route_emails = route_engine.get_recent_emails()
print(f"\nRoute handler (new session): {len(route_emails)} emails")
for e in route_emails:
    print(f"  Email id={e.id} lead_id={e.lead_id} type={e.email_type}")
route_lead_emails = [e for e in route_emails if e.lead_id == lead_id]
print(f"Route lead emails: {len(route_lead_emails)}")

# Verify template rendering
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")
from models import Lead
lead_obj = route_db.query(Lead).filter(Lead.id == lead_id).first()
from fastapi import Request
# Check what the actual route context would be
print(f"\nLead from route DB: {lead_obj.first_name if lead_obj else 'NOT FOUND'}")
print(f"Route lead emails list: {route_lead_emails}")

route_db.close()
# Close the generator properly
try:
    next(gen)
except StopIteration:
    pass

# Check dashboard
dash = client.get("/admin", headers=auth).text
types2 = re.findall(r'class="email-type">([^<]+)', dash)
print(f"Dashboard email types: {types2}")

# Check DB directly
from database import SessionLocal
db = SessionLocal()
from models import EmailQueue
emails = db.query(EmailQueue).all()
print(f"\nTotal emails in DB: {len(emails)}")
for e in emails:
    print(f"  id={e.id} lead_id={e.lead_id} type={e.email_type} status={e.status}")

# Now simulate what the route does
from schemas import EmailQueueResponse
responses = [EmailQueueResponse.model_validate(e) for e in emails]
print(f"Validated responses: {len(responses)}")
for r in responses:
    print(f"  r.lead_id={r.lead_id} (type={type(r.lead_id)}) r.email_type={r.email_type}")
    print(f"  lead_id param: {lead_id} (type={type(lead_id)})")
    print(f"  match: {r.lead_id == lead_id}")
db.close()

os.remove("./test_shamanic.db") if os.path.exists("./test_shamanic.db") else None
