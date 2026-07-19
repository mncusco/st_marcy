class TestDownloadFlow:
    def test_download_with_valid_token(self, client, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        token = created["download_token"]
        resp = client.get(f"/download/{token}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "Il_Ritiro_Nella_Selva" in resp.headers.get("content-disposition", "")

    def test_download_with_invalid_token(self, client):
        resp = client.get("/download/invalidtoken123")
        assert resp.status_code == 404

    def test_download_updates_lead(self, client, auth_headers, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        lead_id = created["id"]
        token = created["download_token"]
        client.get(f"/download/{token}")
        resp = client.get(f"/api/leads/{lead_id}", headers=auth_headers)
        assert resp.json()["downloaded_editorial"] is True

    def test_download_track_endpoint(self, client, sample_lead_data):
        created = client.post("/api/leads", json=sample_lead_data).json()
        resp = client.post(f"/api/leads/{created['id']}/download")
        assert resp.status_code == 200
        assert resp.json()["downloaded"] is True
