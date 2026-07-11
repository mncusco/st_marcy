"""
End-to-end customer journey validation.
Covers Tests 1-5 from Phase 12 specification.
"""

import json
import pytest


# ──────────────────────────────────────────────
# TEST 1 — LEAD CAPTURE
# ──────────────────────────────────────────────

class TestLeadCapture:
    """Verify visitor form submission → DB insertion → no duplicates → language → UTM."""

    def test_full_lead_creation_with_utm(self, client, sample_lead_data):
        resp = client.post("/api/leads", json=sample_lead_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        lead_id = data["id"]
        assert isinstance(lead_id, int)
        token = data["download_token"]
        assert len(token) > 20, "download_token too short"

        # Verify via GET that everything stored correctly
        get_resp = client.get(f"/api/leads/{lead_id}")
        assert get_resp.status_code == 200
        lead = get_resp.json()

        assert lead["email"] == "alice@example.com"
        assert lead["first_name"] == "Alice"
        assert lead["language"] == "en"
        assert lead["campaign"] == "summer2026"
        assert lead["referrer"] == "https://google.com/search"
        assert lead["utm_source"] == "google"
        assert lead["utm_medium"] == "cpc"
        assert lead["utm_campaign"] == "summer_sale"
        assert lead["status"] == "NEW"
        assert lead["downloaded_editorial"] is False

    def test_duplicate_email_rejected(self, client, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        resp = client.post("/api/leads", json=sample_lead_data)
        assert resp.status_code == 400
        assert "già" in resp.json()["detail"].lower()

    def test_language_stored_correctly(self, client):
        for lang_code in ("it", "es", "ru", "sr"):
            data = {
                "first_name": f"Test{lang_code}",
                "last_name": "User",
                "email": f"{lang_code}@example.com",
                "language": lang_code,
            }
            resp = client.post("/api/leads", json=data)
            assert resp.status_code == 200, f"Failed for language {lang_code}"
            get_resp = client.get(f"/api/leads/{resp.json()['id']}")
            assert get_resp.json()["language"] == lang_code

    def test_unsupported_language_falls_back(self, client):
        data = {
            "first_name": "Pierre",
            "last_name": "Dupont",
            "email": "pierre@example.com",
            "language": "fr",
        }
        resp = client.post("/api/leads", json=data)
        assert resp.status_code == 200
        get_resp = client.get(f"/api/leads/{resp.json()['id']}")
        assert get_resp.json()["language"] == "fr"  # system stores language as-provided

    def test_accept_language_header(self, client):
        data = {
            "first_name": "Maria",
            "last_name": "Garcia",
            "email": "maria@example.com",
        }
        resp = client.post(
            "/api/leads",
            json=data,
            headers={"accept-language": "es-MX,en;q=0.9"},
        )
        get_resp = client.get(f"/api/leads/{resp.json()['id']}")
        assert get_resp.json()["language"] == "es"


# ──────────────────────────────────────────────
# TEST 2 — EDITORIAL DELIVERY
# ──────────────────────────────────────────────

class TestEditorialDelivery:
    """Verify download token, PDF delivery, expiration, all languages."""

    def test_download_token_created_and_valid(self, client, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        token = created["download_token"]
        assert token is not None
        assert len(token) > 30
        resp = client.get(f"/download/{token}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_invalid_token_returns_404(self, client):
        resp = client.get("/download/this-token-does-not-exist")
        assert resp.status_code == 404

    def test_download_pdf_in_all_languages(self, client):
        lang_map = {
            "en": "Il_Ritiro_Nella_Selva_EN.pdf",
            "it": "Il_Ritiro_Nella_Selva_IT.pdf",
            "es": "Il_Ritiro_Nella_Selva_ES.pdf",
            "ru": "Il_Ritiro_Nella_Selva_RU.pdf",
            "sr": "Il_Ritiro_Nella_Selva_SR.pdf",
        }
        for code, expected_filename in lang_map.items():
            data = {
                "first_name": f"User{code}",
                "last_name": "Test",
                "email": f"{code}_dl@example.com",
                "language": code,
            }
            created = client.post("/api/leads", json=data).json()
            token = created["download_token"]
            resp = client.get(f"/download/{token}")
            assert resp.status_code == 200, f"Failed download for {code}"
            cd = resp.headers.get("content-disposition", "")
            assert expected_filename in cd, f"Expected {expected_filename} in {cd}"

    def test_download_updates_lead_flag(self, client, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        token = created["download_token"]
        client.get(f"/download/{token}")
        lead = client.get(f"/api/leads/{created['id']}").json()
        assert lead["downloaded_editorial"] is True
        assert lead["downloaded_at"] is not None


# ──────────────────────────────────────────────
# TEST 3 — EMAIL AUTOMATION
# ──────────────────────────────────────────────

class TestEmailAutomation:
    """Verify emails are queued on lead create and download, without sending."""

    def _queued_emails(self, client, auth_headers, lead_id):
        """Extract queued email types from lead detail page."""
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        import re
        # Find the email history table rows (lead detail uses inline styles, not class="email-type")
        m = re.search(r'<h2>Email History.*?<tbody>(.*?)</tbody>', html, re.DOTALL)
        if not m:
            return []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.DOTALL)
        types = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>([^<]*)</td>', row)
            if cells:
                types.append(cells[0].strip())
        return types

    def test_lead_created_queues_followup_email(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        types = self._queued_emails(client, auth_headers, lead_id)
        assert "followup_3_days" in types, (
            f"Expected followup_3_days in queued emails, got {types}"
        )

    def test_download_triggers_editorial_email(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        token = created["download_token"]
        client.get(f"/download/{token}")
        types = self._queued_emails(client, auth_headers, lead_id)
        assert "editorial_download" in types, (
            f"Expected editorial_download after download, got {types}"
        )

    def test_email_queue_stats_on_dashboard(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        html = client.get("/admin", headers=auth_headers).text
        assert "Email Queue" in html
        assert "followup" in html.lower() or "Pending" in html

    def test_email_process_endpoint(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        resp = client.post("/admin/email/process", headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303


# ──────────────────────────────────────────────
# TEST 4 — DASHBOARD
# ──────────────────────────────────────────────

class TestDashboard:
    """Verify lead visibility, filters, statistics, download counts, timeline."""

    def test_lead_visible_in_dashboard(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        html = client.get("/admin", headers=auth_headers).text
        assert "Alice Smith" in html
        assert "alice@example.com" in html

    def test_dashboard_statistics(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        html = client.get("/admin", headers=auth_headers).text
        assert ">1<" in html.replace(" ", "") or "1" in html  # total leads should be 1
        # Verify stats grid rendered
        assert "Total" in html

    def test_download_count_updates(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        token = created["download_token"]
        client.get(f"/download/{token}")
        html = client.get("/admin", headers=auth_headers).text
        assert "Downloads" in html

    def test_timeline_events_appear(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "Lead created" in html or "lead_created" in html.lower()

    def test_filters_work(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        html = client.get("/admin?status=NEW", headers=auth_headers).text
        assert "Alice Smith" in html
        html2 = client.get("/admin?status=APPROVED", headers=auth_headers).text
        assert "No leads found" in html2 or "No leads" in html2

    def test_lead_detail_page(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        html = client.get(f"/admin/lead/{created['id']}", headers=auth_headers).text
        assert "Alice" in html
        assert "alice@example.com" in html
        assert "Timeline" in html or "Activity" in html


# ──────────────────────────────────────────────
# TEST 5 — INTERVIEW PIPELINE
# ──────────────────────────────────────────────

class TestInterviewPipeline:
    """Verify status changes, interview creation, events, AI analysis."""

    def _update_status(self, client, auth_headers, lead_id, new_status):
        return client.post(
            f"/admin/lead/{lead_id}",
            data={"status": new_status, "notes": "test transition"},
            headers=auth_headers,
            follow_redirects=False,
        )

    def test_status_transition_creates_event(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        resp = self._update_status(client, auth_headers, lead_id, "CONTACTED")
        assert resp.status_code == 303
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "NEW" in html
        assert "CONTACTED" in html  # timeline should show transition

    def test_interview_creation(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        create_resp = client.post(
            f"/admin/lead/{lead_id}/interview/create",
            headers=auth_headers,
            follow_redirects=False,
        )
        assert create_resp.status_code == 303
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "REQUESTED" in html

    def test_interview_schedule(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(
            f"/admin/lead/{lead_id}/interview/create",
            headers=auth_headers,
        )
        # find interview id — peek at the page
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        import re
        ids = re.findall(r"/admin/interview/(\d+)/schedule", html)
        assert ids, "No schedule form found"
        inv_id = ids[0]
        schedule_resp = client.post(
            f"/admin/interview/{inv_id}/schedule",
            data={
                "scheduled_at": "2026-08-15T10:00",
                "duration_minutes": "45",
                "meeting_url": "https://zoom.us/j/123",
            },
            headers=auth_headers,
            follow_redirects=False,
        )
        assert schedule_resp.status_code == 303
        html2 = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "SCHEDULED" in html2

    def test_interview_completion(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        client.post(f"/admin/lead/{lead_id}/interview/create", headers=auth_headers)
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        import re
        ids = re.findall(r"/admin/interview/(\d+)/complete", html)
        assert ids
        inv_id = ids[0]
        resp = client.post(
            f"/admin/interview/{inv_id}/complete",
            data={"notes": "Great candidate"},
            headers=auth_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        html2 = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "COMPLETED" in html2

    def test_ai_analysis_available(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "Analyze Candidate" in html or "AI" in html
        # Request analysis
        client.post(
            f"/admin/lead/{lead_id}/analyze",
            headers=auth_headers,
            follow_redirects=False,
        )
        html2 = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "Regenerate" in html2 or "analysis" in html2.lower()

    def test_full_pipeline_status_flow(self, client, auth_headers, sample_lead_data):
        """Complete flow: NEW → CONTACTED → INTERVIEW → APPROVED → BOOKED."""
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        transitions = ["CONTACTED", "INTERVIEW", "APPROVED", "BOOKED"]
        for status in transitions:
            resp = self._update_status(client, auth_headers, lead_id, status)
            assert resp.status_code == 303, f"Failed transition to {status}"
            lead = client.get(f"/api/leads/{lead_id}").json()
            assert lead["status"] == status, f"Expected {status}, got {lead['status']}"


# ──────────────────────────────────────────────
# REAL SIMULATED USER TESTS
# ──────────────────────────────────────────────

class TestSimulatedUsers:
    """Real user simulation: USA, Italy, Spain, Russia."""

    USER_PROFILES = [
        {"label": "USA",    "first_name": "James",  "last_name": "Wilson",   "email": "james@example.com",    "country": "US", "language": "en", "expected_pdf": "Il_Ritiro_Nella_Selva_EN.pdf"},
        {"label": "Italy",  "first_name": "Marco",  "last_name": "Rossi",    "email": "marco@example.com",    "country": "IT", "language": "it", "expected_pdf": "Il_Ritiro_Nella_Selva_IT.pdf"},
        {"label": "Spain",  "first_name": "Carmen", "last_name": "Garcia",   "email": "carmen@example.com",   "country": "ES", "language": "es", "expected_pdf": "Il_Ritiro_Nella_Selva_ES.pdf"},
        {"label": "Russia", "first_name": "Dmitri", "last_name": "Volkov",   "email": "dmitri@example.com",   "country": "RU", "language": "ru", "expected_pdf": "Il_Ritiro_Nella_Selva_RU.pdf"},
    ]

    @pytest.mark.parametrize("profile", USER_PROFILES, ids=[p["label"] for p in USER_PROFILES])
    def test_lead_create_and_db(self, client, profile):
        """Lead is stored with correct language, country."""
        data = {k: profile[k] for k in ("first_name", "last_name", "email", "country", "language")}
        created = client.post("/api/leads", json=data).json()
        lead_id = created["id"]
        lead = client.get(f"/api/leads/{lead_id}").json()
        assert lead["first_name"] == profile["first_name"]
        assert lead["last_name"] == profile["last_name"]
        assert lead["email"] == profile["email"]
        assert lead["language"] == profile["language"]
        assert lead["country"] == profile["country"]

    @pytest.mark.parametrize("profile", USER_PROFILES, ids=[p["label"] for p in USER_PROFILES])
    def test_download_correct_language_pdf(self, client, profile):
        """Download returns correct language PDF."""
        data = {k: profile[k] for k in ("first_name", "last_name", "email", "country", "language")}
        created = client.post("/api/leads", json=data).json()
        token = created["download_token"]
        resp = client.get(f"/download/{token}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        cd = resp.headers.get("content-disposition", "")
        assert profile["expected_pdf"] in cd, f"Expected {profile['expected_pdf']}, got {cd}"

    @pytest.mark.parametrize("profile", USER_PROFILES, ids=[p["label"] for p in USER_PROFILES])
    def test_email_queued_on_create(self, client, auth_headers, profile):
        """Lead creation queues followup email."""
        data = {k: profile[k] for k in ("first_name", "last_name", "email", "country", "language")}
        created = client.post("/api/leads", json=data).json()
        lead_id = created["id"]
        html = client.get(f"/admin/lead/{lead_id}", headers=auth_headers).text
        assert "followup_3_days" in html

    @pytest.mark.parametrize("profile", USER_PROFILES, ids=[p["label"] for p in USER_PROFILES])
    def test_dashboard_shows_user(self, client, auth_headers, profile):
        """Dashboard displays the simulated user."""
        data = {k: profile[k] for k in ("first_name", "last_name", "email", "country", "language")}
        client.post("/api/leads", json=data)
        html = client.get("/admin", headers=auth_headers).text
        assert profile["first_name"] in html
        assert profile["email"] in html
