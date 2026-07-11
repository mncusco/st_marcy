class TestEmailQueue:
    def test_queue_email_on_lead_create(self, client, sample_lead_data):
        resp = client.post("/api/leads", json=sample_lead_data)
        assert resp.status_code == 200
        lead_id = resp.json()["id"]
        auth = _auth_header()
        dashboard = client.get(f"/admin/lead/{lead_id}", headers=auth)
        assert dashboard.status_code == 200

    def test_email_queue_stats_authenticated(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        resp = client.get("/admin", headers=auth_headers)
        assert resp.status_code == 200
        html = resp.text
        assert "Email Queue" in html

    def test_email_process_endpoint(self, client, auth_headers, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        resp = client.post("/admin/email/process", headers=auth_headers, follow_redirects=False)
        assert resp.status_code == 303

    def test_dashboard_requires_auth(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 401

    def test_admin_requires_valid_creds(self, client):
        import base64
        bad = base64.b64encode(b"bad:creds").decode()
        resp = client.get("/admin", headers={"Authorization": f"Basic {bad}"})
        assert resp.status_code == 401


def _auth_header():
    import base64
    creds = base64.b64encode(b"admin:testpass").decode()
    return {"Authorization": f"Basic {creds}"}
