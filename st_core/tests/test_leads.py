import pytest


class TestLeadCreation:
    def test_create_lead_success(self, client, sample_lead_data):
        resp = client.post("/api/leads", json=sample_lead_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data
        assert "download_token" in data

    def test_create_lead_duplicate_email(self, client, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        resp = client.post("/api/leads", json=sample_lead_data)
        assert resp.status_code == 400
        assert "già registrata" in resp.json()["detail"].lower()

    def test_create_lead_missing_required(self, client):
        resp = client.post("/api/leads", json={"first_name": "Bob"})
        assert resp.status_code == 422

    def test_create_lead_invalid_email(self, client):
        data = {
            "first_name": "Bob",
            "last_name": "Brown",
            "email": "not-an-email",
        }
        resp = client.post("/api/leads", json=data)
        assert resp.status_code == 422


class TestLeadRetrieval:
    def test_get_lead_by_id(self, client, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        resp = client.get(f"/api/leads/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

    def test_get_lead_not_found(self, client):
        resp = client.get("/api/leads/99999")
        assert resp.status_code == 404

    def test_list_leads(self, client, sample_lead_data):
        client.post("/api/leads", json=sample_lead_data)
        resp = client.get("/api/leads")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
